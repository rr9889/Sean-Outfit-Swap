"""Check the two data invariants the disguise outfit swap depends on, against an installed game folder.

usage: python -I check_invariants.py "C:\\Saboteur\\The Saboteur"

Reads France\\loosefiles_BinPC.pack (GameTemplates.wsd + global.map) and the patch megapack if present, then
reports:

  1. forward references - a body setup whose BodyPart points at a part record defined LATER in
     GameTemplates.wsd.  Retail has 0.  A setup is built before a part defined after it, so such a setup
     draws no body parts (docs/MECHANISM.md section 2).
  2. part models outside the setup's own bundle - 5494 of 5494 retail references point at a model that the
     setup's own bundle registers (global.map l2).  A reference to a model that only another bundle has
     works only while that bundle happens to be resident; on a save load nothing requests it and Continue
     waits forever (docs/MECHANISM.md section 1).

Both must print 0 with the mod installed.

This tool identifies a "model" the way the engine does: a 4-byte value in a part record that is registered
as a mesh (global.map l2) by some bundle.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "installer"))
import map6  # noqa: E402
from patch_wsd import pandemic_hash, templates  # noqa: E402

HEADER, ALIGN = 128, 0x10


def entries(buf):
    out, p = [], 0
    while p < len(buf):
        crc, size = struct.unpack_from("<II", buf, p)
        name = buf[p + 8 : p + HEADER][: buf[p + 8 : p + HEADER].index(b"\0")].decode("ascii")
        out.append((name, p + HEADER, size))
        p = (p + HEADER + size + ALIGN - 1) & ~(ALIGN - 1)
    return out


def read_entry(pack, name):
    for n, start, size in entries(pack):
        if n.lower() == name.lower():
            return pack[start : start + size]
    raise KeyError(name)


def main(argv):
    game = Path(argv[1]) if len(argv) > 1 else Path(r"C:\Saboteur\The Saboteur")
    pack = (game / "France" / "loosefiles_BinPC.pack").read_bytes()
    wsd = read_entry(pack, "GameTemplates.wsd")
    gmap = read_entry(pack, "global.map")
    m = map6.parse(gmap)

    own = {r.name: {h for h, _ in r.l2} for r in m["dyn"]}
    owner = {}
    for r in m["dyn"]:
        for h, _ in r.l2:
            owner.setdefault(h, set()).add(r.name)

    tpls = list(templates(wsd))
    index = {name: i for i, name, _, _ in tpls}
    setups = {name: pairs for _, name, typ, pairs in tpls if typ == "FxHumanBodySetup"}
    parts = {name: pairs for _, name, typ, pairs in tpls if typ == "FxHumanBodyPart"}

    PART = pandemic_hash("BodyPart")
    forward, outside, checked, setups_ok = 0, 0, 0, 0
    for sname, pairs in setups.items():
        if sname not in own:
            continue                       # no bundle record: not a spawned body setup
        bad_order, bad_model = [], []
        for h, _, data in pairs:
            if h != PART or len(data) != 4:
                continue
            pname = struct.unpack("<I", data)[0]
            pname = next((n for n in parts if pandemic_hash(n) == pname), None)
            if pname is None:
                continue
            if index[pname] > index[sname]:
                bad_order.append(pname)
            for ph, _, pdata in parts[pname]:
                if len(pdata) != 4:
                    continue
                v = struct.unpack("<I", pdata)[0]
                if v in owner:
                    checked += 1
                    if v not in own[sname]:
                        bad_model.append(f"{pname}->{sorted(owner[v])[:2]}")
        if bad_order or bad_model:
            print(f"FAIL {sname}: forward {bad_order} outside {bad_model[:4]}")
            forward += len(bad_order)
            outside += len(bad_model)
        else:
            setups_ok += 1
    print(f"body setups with a bundle record: {len([s for s in setups if s in own])} ({setups_ok} clean)")
    print(f"forward references (setup -> part defined later): {forward}")
    print(f"part models outside the setup's own bundle: {outside} of {checked}")
    return 1 if (forward or outside) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
