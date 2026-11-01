"""Update global.map to match the bundles rebuilt by `sab_poc cp-addparts`, then verify it independently.

usage: python -I apply_map.py <global.map in> <changes.json> <patchdynamic0.megapack> <global.map out>

For every rebuilt bundle's record: l2 (meshes) += appended (hash, usz); l1 (textures) += appended (hash, usz);
counts[0] += meshes, counts[1] += textures, counts[2] += phys; q = 24 * (c0 + c1 + c2) + 4.  That q rule holds
for all 268 stock body-setup records (checked 2026-10-31).

Verification, all of it independent of the writer: every changed bundle blob is re-parsed out of the patch
megapack with the NEW counts, and its mesh / texture tables must equal the record's l2 / l1 (hash, usz, in
order); every record that was not touched must be byte-identical to the input.
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "installer"))
import map6  # noqa: E402
from patch_wsd import pandemic_hash  # noqa: E402

gm_in, ch_path, patch, gm_out = (Path(a) for a in sys.argv[1:5])
data = gm_in.read_bytes()
m = map6.parse(data)
changes = json.loads(ch_path.read_text())["bundles"]
recs = {r.hash: r for r in m["dyn"]}
h = lambda s: int(s, 16)  # noqa: E731
touched = set()
for c in changes:
    r = recs[h(c["index"])]
    mesh, phys, tex = c["mesh"], c["phys"], c["tex"]
    r.l2 += [(h(x["hash"]), x["usz"]) for x in mesh]
    r.l1 += [(h(x["hash"]), x["usz"]) for x in tex]
    r.counts[0] += len(mesh)
    r.counts[1] += len(tex)
    r.counts[2] += len(phys)
    r.q = 24 * (r.counts[0] + r.counts[1] + r.counts[2]) + 4
    r.raw = r.serialize()
    touched.add(r.name)
out = map6.write(m)
gm_out.write_bytes(out)

# ---- independent verification
m2 = map6.parse(out)
assert len(m2["dyn"]) == len(m["dyn"]) and m2["end"] == len(out)
old = map6.parse(data)
for a, b in zip(old["dyn"] + old["list1"] + old["list2"], m2["dyn"] + m2["list1"] + m2["list2"]):
    if a.name not in touched:
        assert a.raw == b.raw, f"untouched record {a.name} changed"
pb = patch.read_bytes()
assert pb[:4] == b"00PM", "not a patch megapack"
n = struct.unpack_from("<I", pb, 4)[0]
blobs = {}
for i in range(n):
    crc, index, size, off = struct.unpack_from("<IIIQ", pb, 8 + 20 * i)
    blobs[index] = pb[off : off + size]
byname = {r.name: r for r in m2["dyn"]}
problems = 0
for name in sorted(touched):
    r = byname[name]
    blob = blobs[pandemic_hash(name)]
    assert blob[:4] == b"ALBS"
    c = r.counts
    cnt = [c[0], c[2], 0, c[1]]            # mesh, phys, flash, tex
    p, tables = 8, []
    for k in cnt:
        t = [struct.unpack_from("<6I", blob, p + 24 * i) for i in range(k)]
        p += 24 * k
        tables.append(t)
    mesh_ok = [(x[0], x[3]) for x in tables[0]] == r.l2
    tex_ok = [(x[0], x[3]) for x in tables[3]] == r.l1
    phys_ok = len(tables[1]) == len(tables[0]) and {x[0] for x in tables[1]} == {x[0] for x in tables[0]}
    q_ok = r.q == 24 * (c[0] + c[1] + c[2]) + 4
    if not (mesh_ok and tex_ok and phys_ok and q_ok):
        problems += 1
        print(f"FAIL {name}: mesh {mesh_ok} tex {tex_ok} phys {phys_ok} q {q_ok}")
print(f"global.map: {len(touched)} bundle records updated; map size {len(data)} -> {len(out)}; "
      f"untouched records byte-identical; {len(touched) - problems}/{len(touched)} bundles match their map records")
sys.exit(1 if problems else 0)
