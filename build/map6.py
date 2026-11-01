"""global.map (MAP6, GLOBAL variant) reader/writer, per notes repo docs/formats/map6.md (2026-10-12).

usage: python -I charport/map6.py dump <global.map> [name_substr]
       python -I charport/map6.py roundtrip <global.map>
Records are kept as raw byte ranges so an unmodified record re-serialises byte-identically.
"""
import struct
import sys
from pathlib import Path


class Rec:
    def __init__(self, d, o):
        s = o
        self.hash, nl = struct.unpack_from("<IH", d, o); o += 6
        self.name = d[o:o + nl - 1].decode("latin-1"); o += nl
        self.a = struct.unpack_from("<3f", d, o); o += 12
        self.b = struct.unpack_from("<3f", d, o); o += 12
        self.u0, self.u1 = struct.unpack_from("<HH", d, o); o += 4
        (n1,) = struct.unpack_from("<I", d, o); o += 4
        self.l1 = [struct.unpack_from("<II", d, o + 8 * k) for k in range(n1)]; o += 8 * n1
        (n2,) = struct.unpack_from("<I", d, o); o += 4
        self.l2 = [struct.unpack_from("<II", d, o + 8 * k) for k in range(n2)]; o += 8 * n2
        (self.q,) = struct.unpack_from("<I", d, o); o += 4
        self.counts = list(struct.unpack_from("<9I", d, o)); o += 36
        (na,) = struct.unpack_from("<I", d, o); o += 4
        self.la = list(struct.unpack_from(f"<{na}I", d, o)); o += 4 * na
        (nb,) = struct.unpack_from("<I", d, o); o += 4
        self.lb = list(struct.unpack_from(f"<{nb & 0xFFFF}I", d, o)); o += 4 * (nb & 0xFFFF)
        self.nb_raw = nb
        (nc,) = struct.unpack_from("<I", d, o); o += 4
        self.lc = []
        for _ in range(nc):
            x, k = struct.unpack_from("<II", d, o); o += 8
            self.lc.append((x, list(struct.unpack_from(f"<{k}I", d, o)))); o += 4 * k
        self.raw = d[s:o]
        self.end = o

    def serialize(self):
        """Rebuild the record bytes from the fields (used after editing l1/l2)."""
        n = self.name.encode("latin-1") + b"\x00"
        out = struct.pack("<IH", self.hash, len(n)) + n + struct.pack("<3f", *self.a) + struct.pack("<3f", *self.b)
        out += struct.pack("<HH", self.u0, self.u1)
        out += struct.pack("<I", len(self.l1)) + b"".join(struct.pack("<II", a, b) for a, b in self.l1)
        out += struct.pack("<I", len(self.l2)) + b"".join(struct.pack("<II", a, b) for a, b in self.l2)
        out += struct.pack("<I", self.q) + struct.pack("<9I", *self.counts)
        out += struct.pack("<I", len(self.la)) + struct.pack(f"<{len(self.la)}I", *self.la)
        out += struct.pack("<I", self.nb_raw) + struct.pack(f"<{len(self.lb)}I", *self.lb)
        out += struct.pack("<I", len(self.lc)) + b"".join(struct.pack("<II", x, len(k)) + struct.pack(f"<{len(k)}I", *k) for x, k in self.lc)
        return out


def parse(d):
    assert d[:4] == b"6PAM", d[:4]
    ndyn, c1 = struct.unpack_from("<II", d, 4)
    o = 12
    l1 = []
    for _ in range(c1):
        r = Rec(d, o); l1.append(r); o = r.end
    (c2,) = struct.unpack_from("<I", d, o); o += 4
    l2 = []
    for _ in range(c2):
        r = Rec(d, o); l2.append(r); o = r.end
    dyn = []
    for _ in range(ndyn):
        r = Rec(d, o); dyn.append(r); o = r.end
    return {"ndyn": ndyn, "list1": l1, "list2": l2, "dyn": dyn, "end": o, "size": len(d)}


def write(m):
    out = bytearray(b"6PAM" + struct.pack("<II", len(m["dyn"]), len(m["list1"])))
    for r in m["list1"]:
        out += r.raw
    out += struct.pack("<I", len(m["list2"]))
    for r in m["list2"]:
        out += r.raw
    for r in m["dyn"]:
        out += r.raw
    return bytes(out)


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    d = Path(path).read_bytes()
    m = parse(d)
    print(f"dynamics {m['ndyn']}, list1 {len(m['list1'])}, list2 {len(m['list2'])}; consumed {m['end']}/{m['size']} bytes")
    if cmd == "roundtrip":
        print("byte-identical:", write(m) == d)
        for r in m["dyn"] + m["list1"] + m["list2"]:
            r.raw = r.serialize()
        print("byte-identical after field re-serialisation:", write(m) == d)
    elif cmd == "dump":
        sub = sys.argv[3].lower() if len(sys.argv) > 3 else ""
        for kind in ("dyn", "list1", "list2"):
            for r in m[kind]:
                if sub in r.name.lower():
                    print(f"[{kind}] {r.name!r} hash={r.hash:08x} u0={r.u0} u1={r.u1} q={r.q:#x} counts={r.counts}")
                    print(f"     l1={[(hex(a), b) for a, b in r.l1]} l2={[(hex(a), b) for a, b in r.l2]} la={r.la} lb={r.lb} lc={r.lc}")
