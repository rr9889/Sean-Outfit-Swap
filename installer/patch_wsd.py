"""GameTemplates.wsd (AULB) edits for Sean's Outfit Swap.

Two edits, both of which keep the file size and every record count, so the pack entry can be replaced in
place:

  1. order_apply()  when (and only when) a body setup references a body part that is defined LATER in the
                    file, move that part so it comes first.  The engine builds a setup before the parts
                    defined after it, and such a setup draws no body parts.  Retail has 0 forward
                    references; a pack that already carries the disguise-trouser swap has exactly one
                    (FBS_GS_Grunt_Disguise -> FBP_NZ_Pants_GS).  Packs without one are left alone.
  2. torso_apply()  24 BodyPart hash swaps in the 20 FBS_*_Disguise setups: Sean's own open-shirted tunic
                    and his "SEAN" gear become the soldier twin's real tunic / collar / gear.  The swap
                    list is torso_swaps.json, next to this file.

Install applies order then torso; uninstall reverts torso then order.  Every rewrite checks the value it
expects to find and refuses to write anything if it is not there, so an unknown pack is left untouched.
Because the order fix moves one record, apply_all() also returns the record's original index; the
installer stores it so uninstall can put the record back exactly where it was.

Standalone use (development / self-test):
  python -I patch_wsd.py <apply|revert> <in.wsd> <out.wsd>
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PART_NAME = "BodyPart"
ORDER_PART = "FBP_NZ_Pants_GS"
ORDER_SETUP = "FBS_GS_Grunt_Disguise"


def pandemic_hash(s):
    """The engine's case-insensitive name hash (FNV-1a variant with the 0x2A tail step)."""
    h = 0x811C9DC5
    for c in s.encode("ascii"):
        h = (((c | 0x20) ^ h) * 0x01000193) & 0xFFFFFFFF
    return ((h ^ 0x2A) * 0x01000193) & 0xFFFFFFFF


class Record:
    """One AULB template record, kept as raw bytes unless rewritten.

    Record: u32 total_size (bytes after this field), u32 unk1, u32 unk2, u32 name_len, name\0,
    u32 type_len, type\0, u32 pair_count, pair_count x (u32 hash, u32 size, data).
    """

    def __init__(self, raw):
        self.raw = raw
        self.dirty = False
        total, self.unk1, self.unk2 = struct.unpack_from("<III", raw, 0)
        self.marker = total == 8 and self.unk1 == 0 and self.unk2 == 0
        if self.marker:
            return
        q = 12
        (nl,) = struct.unpack_from("<I", raw, q)
        self.name = raw[q + 4 : q + 4 + nl - 1].decode("latin-1")
        q += 4 + nl
        (tl,) = struct.unpack_from("<I", raw, q)
        self.type = raw[q + 4 : q + 4 + tl - 1].decode("latin-1")
        q += 4 + tl
        (pc,) = struct.unpack_from("<I", raw, q)
        q += 4
        self.pairs = []
        for _ in range(pc):
            h, ds = struct.unpack_from("<II", raw, q)
            self.pairs.append([h, raw[q + 8 : q + 8 + ds]])
            q += 8 + ds
        self.exact = q == len(raw)

    def serialize(self):
        if not self.dirty:
            return self.raw
        n = self.name.encode("latin-1") + b"\0"
        t = self.type.encode("latin-1") + b"\0"
        body = struct.pack("<II", self.unk1, self.unk2)
        body += struct.pack("<I", len(n)) + n + struct.pack("<I", len(t)) + t
        body += struct.pack("<I", len(self.pairs))
        for h, d in self.pairs:
            body += struct.pack("<II", h, len(d)) + bytes(d)
        return struct.pack("<I", len(body)) + body


def parse(buf):
    assert buf[:4] == b"AULB", "not a GameTemplates.wsd (missing AULB magic)"
    (count,) = struct.unpack_from("<I", buf, 4)
    recs, p = [], 8
    while len(recs) < count and p + 12 <= len(buf):
        (total,) = struct.unpack_from("<I", buf, p)
        recs.append(Record(buf[p : p + 4 + total]))
        p += 4 + total
    assert p == len(buf), f"record walk ended at {p}, file is {len(buf)}"
    return count, recs


def write(recs):
    out = bytearray(b"AULB" + struct.pack("<I", len(recs)))
    for r in recs:
        out += r.serialize()
    return bytes(out)


def templates(buf):
    """Walk records by their stored total_size (not by the pair list), yielding (idx, name, type, pairs)."""
    assert buf[:4] == b"AULB", "not an AULB file"
    (count,) = struct.unpack_from("<I", buf, 4)
    p = 8
    for idx in range(count):
        if p + 12 > len(buf):
            return
        total, unk1, unk2 = struct.unpack_from("<III", buf, p)
        rec_end = p + 4 + total
        if total == 8 and unk1 == 0 and unk2 == 0:
            p = rec_end
            continue
        q = p + 12
        (nl,) = struct.unpack_from("<I", buf, q)
        name = buf[q + 4 : q + 4 + nl - 1].decode("ascii", "replace")
        q += 4 + nl
        (tl,) = struct.unpack_from("<I", buf, q)
        typ = buf[q + 4 : q + 4 + tl - 1].decode("ascii", "replace")
        q += 4 + tl
        (pc,) = struct.unpack_from("<I", buf, q)
        q += 4
        pairs = []
        for _ in range(pc):
            if q + 8 > rec_end:
                break
            h, ds = struct.unpack_from("<II", buf, q)
            pairs.append((h, q + 8, buf[q + 8 : q + 8 + ds]))
            q += 8 + ds
        yield idx, name, typ, pairs
        p = rec_end


def load_swaps():
    return json.loads((HERE / "torso_swaps.json").read_text())


def _refs_part(buf, setup_name, part_name):
    """True when a body setup has a BodyPart slot pointing at part_name."""
    want = pandemic_hash(part_name)
    PART = pandemic_hash(PART_NAME)
    for _, name, typ, pairs in templates(buf):
        if name != setup_name:
            continue
        return any(h == PART and len(d) == 4 and struct.unpack("<I", d)[0] == want for h, _, d in pairs)
    raise ValueError(f"{setup_name} not found in the templates")


def order_apply(buf):
    """Move ORDER_PART before ORDER_SETUP if, and only if, ORDER_SETUP references it from further down.

    Returns (templates, original_index).  original_index is None when nothing was moved, which is the
    normal case for a stock pack: the part is not referenced at all there, so there is no forward
    reference to fix.
    """
    count, recs = parse(buf)
    idx = {r.name: i for i, r in enumerate(recs) if not r.marker}
    for n in (ORDER_PART, ORDER_SETUP):
        if n not in idx:
            raise ValueError(f"{n} not found in the templates")
    referenced = _refs_part(buf, ORDER_SETUP, ORDER_PART)
    if idx[ORDER_PART] < idx[ORDER_SETUP] or not referenced:
        return buf, None
    original = idx[ORDER_PART]
    rec = recs.pop(original)
    recs.insert(idx[ORDER_SETUP], rec)
    out = buf[:8] + write(recs)[8:]      # keep the retail header (its count is not len(records))
    if len(out) != len(buf):
        raise ValueError("order fix changed the file size")
    idx2 = {r.name: i for i, r in enumerate(recs) if not r.marker}
    if not (idx2[ORDER_PART] < idx2[ORDER_SETUP] and _refs_part(out, ORDER_SETUP, ORDER_PART)):
        raise ValueError("order fix did not produce a valid ordering")
    return out, original


def order_revert(buf, original_index):
    """Put ORDER_PART back at original_index (the position it had before apply)."""
    if original_index is None:
        if _refs_part(buf, ORDER_SETUP, ORDER_PART):
            raise ValueError(
                f"{ORDER_SETUP} now references {ORDER_PART}, but this pack was installed without moving it; "
                f"cannot restore the original record order")
        return buf
    count, recs = parse(buf)
    idx = {r.name: i for i, r in enumerate(recs) if not r.marker}
    for n in (ORDER_PART, ORDER_SETUP):
        if n not in idx:
            raise ValueError(f"{n} not found in the templates")
    if idx[ORDER_PART] != idx[ORDER_SETUP] - 1:
        raise ValueError(f"{ORDER_PART} is not immediately before {ORDER_SETUP}; the templates were changed since install")
    rec = recs.pop(idx[ORDER_PART])
    if not 0 < original_index <= len(recs):
        raise ValueError(f"stored original index {original_index} is out of range")
    recs.insert(original_index, rec)
    out = buf[:8] + write(recs)[8:]
    if len(out) != len(buf):
        raise ValueError("order revert changed the file size")
    return out


def _torso(buf, direction):
    swaps = load_swaps()
    orig = buf
    out = bytearray(orig)
    PART = pandemic_hash(PART_NAME)
    bysetup = {}
    for s in swaps:
        bysetup.setdefault(s["setup"], []).append(s)
    seen = set()
    for idx, name, typ, pairs in templates(orig):
        if typ != "FxHumanBodySetup" or name not in bysetup:
            continue
        parts = [(off, d) for h, off, d in pairs if h == PART and len(d) == 4]
        for s in bysetup[name]:
            if direction == "apply":
                want_old, want_new = s["old"], s["new"]
            else:
                want_old, want_new = s["new"], s["old"]
            if s["slot"] >= len(parts):
                raise ValueError(f"{name}: no BodyPart slot {s['slot']}")
            off, d = parts[s["slot"]]
            if d.hex() != want_old:
                raise ValueError(f"{name} slot {s['slot']}: found {d.hex()}, expected {want_old} for {direction}; nothing written")
            out[off : off + 4] = bytes.fromhex(want_new)
        seen.add(name)
    missing = sorted(set(bysetup) - seen)
    if missing:
        raise ValueError(f"setups not found: {missing}; nothing written")
    diff = sum(1 for a, b in zip(out, orig) if a != b)
    if len(out) != len(orig) or diff > 4 * len(swaps):
        raise ValueError(f"unexpected change size ({diff} bytes); nothing written")
    return bytes(out)


def torso_apply(buf):
    """Sean's fitted tunic / gear -> the soldier twin's real ones (24 swaps in 20 setups)."""
    return _torso(buf, "apply")


def torso_revert(buf):
    return _torso(buf, "revert")


def apply_all(buf):
    """Returns (new templates, {"order_moved_from": index or None})."""
    ordered, original = order_apply(buf)
    return torso_apply(ordered), {"order_moved_from": original}


def revert_all(buf, meta=None):
    orig_index = (meta or {}).get("order_moved_from")
    return order_revert(torso_revert(buf), orig_index)


def main(argv):
    if len(argv) != 4 or argv[1] not in ("apply", "revert"):
        sys.exit(__doc__)
    data = Path(argv[2]).read_bytes()
    if argv[1] == "apply":
        out, meta = apply_all(data)
    else:
        out, meta = revert_all(data), None
    Path(argv[3]).write_bytes(out)
    print(f"{argv[1]}: {len(load_swaps())} swaps; {len(out)} bytes (unchanged size); wrote {argv[3]}")


if __name__ == "__main__":
    main(sys.argv)
