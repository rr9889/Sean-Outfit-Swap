# Building the mod

The release zip already contains the built mod (`release/`), so this is only for rebuilding or changing the
swap list. Everything here runs against *your own* copy of the game; no game files are in this repository.

## What the build produces

| output | made by | input |
|---|---|---|
| `Global\patchdynamic0.megapack` | `sab_poc cp-addparts` (Rust, see below) | `plan.json`, the game's `Global\Dynamic0.megapack` |
| `plan.changes.json` | `sab_poc cp-addparts` (its report) | — |
| `global.map` | `apply_map.py` | stock `global.map` + `plan.changes.json` + the patch megapack |
| `GameTemplates.wsd` edit | `installer/patch_wsd.py` (runs at install time, not build time) | `installer/torso_swaps.json` |

`plan.json` is the only hand-kept input: for each of the 20 `FBS_*_Disguise` bundles, the soldier twin it
copies from and the model hashes its part slots need. `installer/torso_swaps.json` is the matching list of
BodyPart hash swaps (setup name, slot, old hash, new hash).

## Rebuilding global.map

```
python -I apply_map.py <stock global.map> plan.changes.json <patchdynamic0.megapack> global.map.new
```

It also verifies itself: every changed bundle is re-parsed out of the patch megapack with the new counts and
its mesh/texture tables must match the records it just wrote, in order, hash and size. Untouched records must
be byte-identical. On the shipped data this reproduces `release/global.map` exactly
(`58648a7bc827efe2…`, see `docs/VERIFICATION.md`).

## Rebuilding the bundles (needs the notes repo)

The surgery command is `sab_poc cp-addparts`, which lives in
[notes-on-reversing-the-saboteur](https://github.com/Mercenaries-Fan-Build/notes-on-reversing-the-saboteur)
under `tools/sab_poc` (MIT). `vendor/cp_addparts.rs` here is that file, copied verbatim, so the command is
readable without cloning. To rebuild:

```
cargo build --release            # in tools/sab_poc of the notes repo
sab_poc cp-addparts --game "C:/Saboteur/The Saboteur" --gltf plan.json
```

`cp_addparts.rs` is `include!`d by `tools/sab_poc/src/deploy.rs` and dispatched as `cp-addparts` in
`main.rs`; see `vendor/README.md` for the exact two edits.

Output is one patch megapack with every changed bundle, keyed by the base entry's crc/index, so
`Dynamic0.megapack` is never modified.

## Checking the result

```
python -I check_invariants.py "<game folder>"
```

Reports forward body-setup references and part models that live outside their setup's bundle — the two
conditions that stop a human from spawning (`docs/MECHANISM.md`). Both must be 0.

## End-to-end test without touching the real install

```
mkdir test\France test\Global
copy "C:\Saboteur\The Saboteur\France\loosefiles_BinPC.pack" test\France\
type nul > test\Saboteur.exe
python -I ..\installer\outfit_swap.py install --game test
python -I ..\installer\outfit_swap.py status  --game test
python -I ..\installer\outfit_swap.py uninstall --game test
```

The pack must come back byte-identical to the copy.
