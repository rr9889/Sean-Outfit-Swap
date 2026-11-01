r"""Sean's Outfit Swap installer for The Saboteur.

Every disguise shows the soldier's real uniform instead of Sean's own open-shirted tunic: 24 body-part
swaps in the 20 FBS_*_Disguise setups, plus the soldier tunic / trouser / gear models copied into each
disguise bundle (Global\patchdynamic0.megapack) so the game can always load them.

usage:
  python outfit_swap.py status    [--game <dir>]
  python outfit_swap.py install   [--game <dir>]
  python outfit_swap.py uninstall [--game <dir>]

The three parts have to travel together.  Swapping Sean's tunic for the soldier's without the bundle
surgery leaves a body part pointing at a model that lives in another bundle; the game never requests that
model, so a save made in disguise hangs on Continue (docs/MECHANISM.md).  Which is also why install and
uninstall are all-or-nothing: the pack is only replaced after the backup verifies, the new pack verifies
after the replace, and any failure puts the previous pack back.

What is touched in the game folder:
  France\loosefiles_BinPC.pack        two entries rewritten in place (GameTemplates.wsd, global.map)
  Global\patchdynamic0.megapack       created by install, deleted by uninstall
  nothing else; the stock Global\Dynamic0.megapack is never modified

The pack is patched, not replaced wholesale, so other mods that also edit the pack (camera, weapons, ...)
survive.  Requires Python 3.8+ and a closed game.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch_wsd  # noqa: E402

REL = HERE.parent / "release"
BACKUPS = HERE / "backups"
DEFAULT_GAME = Path(r"C:\Saboteur\The Saboteur")

STOCK_MAP_SHA = "d26758eaf9edf17f2077cdcc16f0e406eb93ac2603c2572d7b30596fdd28d65b"
NEW_MAP_SHA = "58648a7bc827efe20ef6197cec88f214d42c24d1dfe3cb89f81c1e1142d04c63"
MEGAPACK_SHA = "bd964727fd14a0ef838fd76fe3b18599514b795291c305bb5d314fb1c1e24b01"

PACK = "France\\loosefiles_BinPC.pack"
MEGAPACK = "Global\\patchdynamic0.megapack"
TEMPLATES = "GameTemplates.wsd"
GLOBAL_MAP = "global.map"

ALIGN = 0x10
HEADER = 128


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- pack codec
# France\loosefiles_BinPC.pack: repeated { u32 name_crc, u32 size, char name[120], payload, pad to 0x10 }.

def entries(buf):
    out, p = [], 0
    while p < len(buf):
        name_crc, size = struct.unpack_from("<II", buf, p)
        raw = buf[p + 8 : p + HEADER]
        name = raw[: raw.index(b"\0")].decode("ascii")
        if size == 0xFFFFFFFF:
            raise ValueError(f"{name!r} at 0x{p:X}: payload on disk, not handled")
        start = p + HEADER
        out.append((name, name_crc, p, start, size))
        p = (start + size + ALIGN - 1) & ~(ALIGN - 1)
    if p != len(buf):
        raise ValueError(f"pack walk ended at 0x{p:X}, pack is 0x{len(buf):X} bytes")
    return out


def entry(buf, name):
    for e in entries(buf):
        if e[0].lower() == name.lower():
            return e
    raise KeyError(name)


def replace(buf, name, payload):
    """Rebuild the pack with one entry's payload replaced (any size); every other payload is copied as-is."""
    out = bytearray()
    found = False
    for ename, crc, hdr, start, size in entries(buf):
        hit = ename.lower() == name.lower()
        data = payload if hit else buf[start : start + size]
        found |= hit
        header = bytearray(buf[hdr : hdr + HEADER])
        struct.pack_into("<I", header, 4, len(data))
        out += header + data
        out += b"\0" * ((-len(out)) % ALIGN)
    if not found:
        raise KeyError(name)
    entries(bytes(out))       # the result must walk cleanly before it goes anywhere
    return bytes(out)


# ---------------------------------------------------------------- helpers

def game_dir(argv):
    if "--game" in argv:
        i = argv.index("--game")
        if i + 1 >= len(argv):
            sys.exit("--game needs a path")
        return Path(argv[i + 1])
    if os.environ.get("SAB_GAME"):
        return Path(os.environ["SAB_GAME"])
    return DEFAULT_GAME


def game_running():
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Saboteur.exe", "/NH"], capture_output=True, text=True, timeout=20)
        return "saboteur.exe" in r.stdout.lower()
    except Exception:
        return False


def atomic_write(path, data):
    tmp = path.with_name(path.name + ".outfit-swap-new")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if file_sha(tmp) != sha256(data):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"written file does not verify: {tmp}")
    os.replace(tmp, path)


def backup_pack(pack_bytes):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    path = BACKUPS / f"loosefiles_BinPC.pack.{sha256(pack_bytes)}"
    if path.exists() and file_sha(path) == sha256(pack_bytes):
        return path
    atomic_write(path, pack_bytes)
    return path


STATE = BACKUPS / "install-state.json"


def save_state(obj):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(obj, indent=1), encoding="utf-8")


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return None


def state(game):
    pack_path = game / PACK
    if not pack_path.exists():
        return {"ok": False, "why": f"{pack_path} not found"}
    pack = pack_path.read_bytes()
    gm = pack[entry(pack, GLOBAL_MAP)[3] :][: entry(pack, GLOBAL_MAP)[4]]
    gm_sha = sha256(gm)
    mega = game / MEGAPACK
    mega_sha = file_sha(mega) if mega.exists() else None
    if gm_sha == NEW_MAP_SHA and mega_sha == MEGAPACK_SHA:
        name = "installed"
    elif gm_sha == STOCK_MAP_SHA and mega_sha is None:
        name = "not installed"
    elif gm_sha == STOCK_MAP_SHA and mega_sha == MEGAPACK_SHA:
        name = "half installed (megapack present, pack not patched)"
    elif gm_sha == NEW_MAP_SHA and mega_sha is None:
        name = "half installed (pack patched, megapack missing)"
    else:
        name = "unknown / another mod's files"
    return {"ok": True, "state": name, "map": gm_sha, "mega": mega_sha, "pack": pack, "pack_path": pack_path}


def check_release_files():
    for p, want in ((REL / GLOBAL_MAP, NEW_MAP_SHA), (REL / "global.map.stock", STOCK_MAP_SHA),
                    (REL / "patchdynamic0.megapack", MEGAPACK_SHA)):
        if not p.exists():
            sys.exit(f"mod file missing: {p}\nextract the release zip completely and run the installer from inside it.")
        if file_sha(p) != want:
            sys.exit(f"mod file does not verify: {p}\nre-download the release zip.")


def preflight(game):
    if not (game / "Saboteur.exe").exists():
        sys.exit(f'{game / "Saboteur.exe"} not found.\n'
                 f'Pass the game folder:  outfit_swap.py install --game "D:\\Games\\The Saboteur"')
    if not (game / PACK).exists():
        sys.exit(f'{game / PACK} not found - is this the right game folder?')
    if not (game / "Global").is_dir():
        sys.exit(f'{game / "Global"} not found - is this the right game folder?')
    if game_running():
        sys.exit("Saboteur.exe is running. Close the game first.")


# ---------------------------------------------------------------- commands

def cmd_status(game):
    st = state(game)
    print(f"game:  {game}")
    if not st["ok"]:
        print(f"state: cannot read - {st['why']}")
        return 1
    print(f"state: {st['state']}")
    print(f"  global.map           {st['map']}")
    print(f"  patchdynamic0        {st['mega'] or 'absent'}")
    return 0


def cmd_install(game):
    preflight(game)
    check_release_files()
    st = state(game)
    if not st["ok"]:
        sys.exit(st["why"])
    if st["state"] == "installed":
        print("Sean's Outfit Swap is already installed.")
        return 0
    if st["mega"] and st["mega"] != MEGAPACK_SHA:
        sys.exit(f'{game / MEGAPACK} already exists and is not this mod\'s.\n'
                 f'Remove it first (it belongs to another mod) - nothing changed.')
    if st["map"] != STOCK_MAP_SHA:
        sys.exit(f"France\\loosefiles_BinPC.pack has an unexpected global.map ({st['map'][:16]}).\n"
                 f"Nothing changed. This mod needs the stock map (another mod has replaced it).")

    pack, pack_path = st["pack"], st["pack_path"]
    wsd = pack[entry(pack, TEMPLATES)[3] :][: entry(pack, TEMPLATES)[4]]
    print("patching GameTemplates.wsd (tunic + gear swaps, template order) ...")
    try:
        new_wsd, meta = patch_wsd.apply_all(wsd)
    except (ValueError, AssertionError) as exc:
        sys.exit(f"cannot patch this pack: {exc}")
    if meta["order_moved_from"] is not None:
        print(f"  fixed a forward body-setup reference (moved a part record from index {meta['order_moved_from']})")
    new_map = (REL / GLOBAL_MAP).read_bytes()
    new_pack = replace(replace(pack, TEMPLATES, new_wsd), GLOBAL_MAP, new_map)
    digest = sha256(new_pack)

    backup = backup_pack(pack)
    print(f"backed up the current pack -> {backup.name}")
    replaced = False
    try:
        atomic_write(pack_path, new_pack)
        replaced = True
        if file_sha(pack_path) != digest:
            raise RuntimeError("the installed pack does not match the patched pack")
        mega_src = REL / "patchdynamic0.megapack"
        staggered = game / MEGAPACK
        staged = staggered.with_name(staggered.name + ".outfit-swap-new")
        shutil.copyfile(mega_src, staged)
        if file_sha(staged) != MEGAPACK_SHA:
            raise RuntimeError("the staged megapack does not match the release file")
        os.replace(staged, staggered)
        if file_sha(staggered) != MEGAPACK_SHA:
            raise RuntimeError("the installed megapack does not verify")
    except Exception as exc:
        print(f"install failed: {exc}")
        print("rolling back ...")
        if replaced:
            atomic_write(pack_path, pack)
        (game / MEGAPACK).unlink(missing_ok=True)
        (game / MEGAPACK).with_name((game / MEGAPACK).name + ".outfit-swap-new").unlink(missing_ok=True)
        sys.exit("rolled back - the game folder is as it was.")

    print(f"installed: pack {digest[:12]}, megapack {MEGAPACK_SHA[:12]}")
    save_state({"installed_pack": digest, "order_moved_from": meta["order_moved_from"]})
    print("A save made while disguised now stores the uniform's part ids; uninstall does not remove them.")
    return 0


def cmd_uninstall(game):
    preflight(game)
    st = state(game)
    if not st["ok"]:
        sys.exit(st["why"])
    if st["state"] == "not installed":
        print("Sean's Outfit Swap is not installed.")
        return 0
    if st["state"] != "installed":
        sys.exit(f"refusing: state is '{st['state']}'. Put the game back to a known state first.\n"
                 f"Backups of every pack are in {BACKUPS}")

    pack, pack_path = st["pack"], st["pack_path"]
    wsd = pack[entry(pack, TEMPLATES)[3] :][: entry(pack, TEMPLATES)[4]]
    meta = load_state()
    if meta and meta.get("installed_pack") not in (None, sha256(pack)):
        print(f"note: the saved install state is for pack {str(meta.get('installed_pack'))[:12]}, "
              f"this pack is {sha256(pack)[:12]}; the record order may not restore exactly")
    print("reverting GameTemplates.wsd ...")
    try:
        new_wsd = patch_wsd.revert_all(wsd, meta)
    except (ValueError, AssertionError) as exc:
        sys.exit(f"cannot revert this pack: {exc}")
    new_map = (REL / "global.map.stock").read_bytes()
    new_pack = replace(replace(pack, TEMPLATES, new_wsd), GLOBAL_MAP, new_map)
    digest = sha256(new_pack)

    backup = backup_pack(pack)
    print(f"backed up the installed pack -> {backup.name}")
    replaced = False
    try:
        atomic_write(pack_path, new_pack)
        replaced = True
        if file_sha(pack_path) != digest:
            raise RuntimeError("the restored pack does not match")
        (game / MEGAPACK).unlink(missing_ok=True)
    except Exception as exc:
        print(f"uninstall failed: {exc}")
        print("rolling back ...")
        if replaced:
            atomic_write(pack_path, pack)
        sys.exit("rolled back - the game folder is as it was.")

    print(f"uninstalled: pack {digest[:12]}, megapack removed")
    STATE.unlink(missing_ok=True)
    print("Saves made while disguised under this mod store the soldier part ids; reinstall before loading them.")
    return 0


def main(argv):
    mode = argv[0] if argv else ""
    if mode not in ("install", "uninstall", "status"):
        sys.exit(__doc__)
    game = game_dir(argv)
    return {"install": cmd_install, "uninstall": cmd_uninstall, "status": cmd_status}[mode](game)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
