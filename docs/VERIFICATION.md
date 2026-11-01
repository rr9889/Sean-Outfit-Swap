# Verification

Everything below was run on 2026-11-01 against the release files in this repository, on Windows 11 with
Python 3.12, using copies of real game data. No step launches the game.

## Test material

| pack | sha256 (first 16) | what it is |
|---|---|---|
| retail | `4C0F9B2700CE51E5` | untouched `France\loosefiles_BinPC.pack` from a GOG install (`!Backup` copy) |
| modded baseline | `52CB76812148AE5A` | the same pack after a QoL build (camera, weapons, ammo, disguise-trouser swap) |
| release `global.map` | `58648A7BC827EFE2` | `release/global.map` |
| stock `global.map` | `D26758EAF9EDF17F` | `release/global.map.stock` |
| release megapack | `BD964727FD14A0EF` | `release/patchdynamic0.megapack` (45,580,288 bytes) |

## 1. Install round-trip on the modded baseline

```
installer> python -I outfit_swap.py install --game <copy of the modded baseline>
  fixed a forward body-setup reference (moved a part record from index 7005)
  installed: pack c51bc668fe1b, megapack bd964727fd14
installer> python -I outfit_swap.py uninstall --game <same copy>
  uninstalled: pack 52cb76812148, megapack removed
```

- installed pack `C51BC668FE1BE431…` — byte-identical to the pack that was installed in the author's game
  when the mod was built, so the released installer reproduces the built mod exactly;
- uninstall restored `52CB76812148AE5A…` byte for byte (all 49,369,568 bytes).

## 2. Install round-trip on the retail pack

```
installer> python -I outfit_swap.py install --game <copy of the retail pack>
  installed: pack 2a2b22bc599a, megapack bd964727fd14
installer> python -I outfit_swap.py uninstall --game <same copy>
  uninstalled: pack 4c0f9b2700ce, megapack removed
```

- retail install `2A2B22BC599AA8EA…` (no record move: the retail pack has no forward reference, so the
  order fix correctly did nothing);
- uninstall restored the retail pack byte for byte.

A pack that is neither state is refused before anything is written; a pack whose tunic hash is not the
expected one stops the patcher with "found X, expected Y; nothing written", and a foreign
`patchdynamic0.megapack` is never overwritten.

## 3. `global.map` is reproducible from the plan

```
build> python -I apply_map.py release/global.map.stock build/plan.changes.json \
                              release/patchdynamic0.megapack <out>
  global.map: 20 bundle records updated; map size 284388 -> 285476;
  untouched records byte-identical; 20/20 bundles match their map records
```

`<out>` is byte-identical to `release/global.map` (`58648A7B…`). The final check is independent of the
writer: every changed bundle is re-parsed out of the patch megapack using the new counts, and its mesh table
must equal the record's `l2` (hash, usz, in order) and its texture table the record's `l1`. All 20 pass; every
untouched record is byte-identical.

## 4. Engine invariants on the installed data

`build/check_invariants.py` checks the two rules that decide whether a human can spawn (see
`docs/MECHANISM.md`):

| | retail pack | retail + this mod |
|---|---|---|
| body setups with a bundle record | 268 | 268 |
| forward setup → part references | 0 | **0** |
| part models outside the setup's own bundle | 0 of 3288 | **0 of 3288** |

The mod therefore does not introduce the condition that hangs Continue; the model the disguise now points at
is inside the disguise bundle itself.

## 5. What is *not* verified

- **In game.** The mod has never been run. Nothing here proves the tunic renders, that the collar and tie fit
  Sean's shoulders, or that the helmet and other gear still line up.
- **The Continue path on a save made in disguise** — the exact case the bundle surgery exists for. Worst case
  is `FBS_KM_Grunt_Disguise` (its model is registered by only 2 other bundles): disguise as that soldier, save
  in a spare slot, quit completely, start, Continue. A hang means the own-bundle explanation is incomplete.
- **Memory.** 20 rebuilt bundles add ~5 MB of resident-capable asset data; the streamer budget is unknown.
- **Textures.** Copied by name, not resolved through materials. A tunic that looks untextured when no soldier
  is resident points at the texture list in `build/plan.changes.json`.

## Reproducing all of it

```
python -I build/check_invariants.py "<game folder>"
python -I build/apply_map.py release/global.map.stock build/plan.changes.json \
                              release/patchdynamic0.megapack out.map
python -I installer/outfit_swap.py status --game "<game folder>"
```

`python -I` (isolated mode) keeps a stray `PYTHONPATH` from changing which modules the tools import.
