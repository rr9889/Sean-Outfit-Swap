# Why a swapped outfit needs bundle surgery

Two engine behaviours make "just point the disguise at the soldier's tunic" a save-corrupting change. Both
were traced in the GOG build of `Saboteur.exe` (32-bit, `0x400000` image base) and are reproducible from the
data alone with `build/check_invariants.py`. Grades: **PROVEN** = read in the disassembly or counted in the
shipped data; **INFERRED** = follows from what is proven.

## 1. A body part's model must live in the setup's own bundle

Every human is assembled from an `FxHumanBodySetup` (FBS) record: `Head`, `UpperBody`, `LowerBody`, `GearA-C`
and an unnamed undershirt slot, each holding `{variation id, part, probability}`. Each part (`FBP_*`) names
its models, and those models are meshes registered by an asset bundle — the FBS record in `global.map` whose
`l2` table lists the meshes and `l1` the textures.

- **PROVEN**: in the retail data, 5494 of 5494 part models are registered by the setup's *own* bundle. Not
  "usually" — all of them.
- **PROVEN**: `WSHumanBlueprint::IsReady` (`0x506fb0`) asks the body setup (`0x515ef0`), which asks every part
  (`0x5192f0`, head `0x519140`), which resolves each model hash through the global hash table
  (`FUN_00453070`) and then asks the registered resource `IsLoaded`. **No request is ever issued for another
  bundle's model.** The only thing that gets loaded is the body setup's own bundle record.
- **PROVEN**: the waiters have no timeout. `0x989800` with `param_2=1` is `while(true){ if (IsReady) break; }`;
  the human spawn gate (~`0x8372a1`) retries every tick and never gives up; the world-load path `0x43cc20`
  has one bounded 50-iteration wait, but the human wait is not it.

So a part pointing at a model that no resident bundle registered keeps `IsReady` false forever. The player
human never spawns, and the loading screen never finishes. That is the "Continue hangs on a save made in
disguise" failure. It is rare in a normal session only because a soldier bundle that carries the model is
usually resident by then; **loading a save requests nothing**:

- **PROVEN**: `WSPlayer::LoadData` (`0x5b5840`) reads six part-blueprint name hashes (call to `0x515450`) and
  re-points blueprints; it never requests a model resource. The victim actor is gone, so the soldier bundle
  is resident only by chance.

Hence the surgery: copy the soldier's models into each disguise bundle, **byte for byte, under their own
names**. `CheckForSkipAndSkip` (`0x65fd6c`) then shares them with a resident copy, or loads them from the
disguise bundle when there is none. No rename, no hash change, nothing for the templates to know about.

## 2. A setup that references a part defined later draws no body parts

- **PROVEN**: a body setup rendered before a part it references has been built resolves a null model pointer
  per slot and silently skips the slot (`WSFxHumanBodySetup::Render`, `0x518490`: null ⇒ no draw, no wait).
- **PROVEN**: retail never does this — 0 forward body-setup → part references in 2192 records. A pack that
  carries the disguise-trouser swap has exactly one (`FBS_GS_Grunt_Disguise` at index 6685 →
  `FBP_NZ_Pants_GS` at 7005), which is why that one disguise's legs may not draw.
- **INFERRED**: the effect was seen in game with the SS woman port, where a forward reference produced a
  bodyless spawn.

The installer fixes this only when it is present, and remembers the record's original index so uninstall can
put the templates back exactly as they were.

## 3. Why the parts are copied and not re-pointed at the soldier's own part

Re-pointing a body setup at `FBP_WM_UB_Officer` (the soldier's part record) is tempting and wrong: that part
record still names models registered only by soldier bundles, so it reintroduces case 1. The mod instead swaps
the *model hashes inside Sean's part* for the soldier's model hashes, and copies those models into the
disguise bundle. The part record keeps its identity, its name and its bundle.

## 4. What the surgery changed, per disguise bundle

For each of the 20 `FBS_*_Disguise` bundles, `build/plan.json` names the soldier twin as donor and asks for
the models its part slots need. `sab_poc cp-addparts` appends, per model:

| table | what is appended |
|---|---|
| `tables[0]` (meshes) | the donor's 6-word DynFile record verbatim (hash, offset, size, usz, flags, hash2) plus the blob; the MSHA hash already equals `hash(name)` in retail data |
| `tables[1]` (physics) | the donor's physics record whose table hash is `hash(name)` (retail is one physics record per mesh) |
| `tables[3]` (textures) | the donor's DTEX records for `name` and `name_NM` (and `_LOD` stripped), when the target bundle does not already have them |

and `global.map` gets the matching `l2`/`l1` appends with `counts[0]+=meshes`, `counts[1]+=textures`,
`counts[2]+=phys`, `q = 24*(mesh+texture+phys)+4` — a rule that holds for all 268 retail body-setup records.
All 20 bundles go into one `Global\patchdynamic0.megapack`, keyed by each base entry's crc/index, so
`Global\Dynamic0.megapack` itself is never modified.

## 5. Cost and risk

Each rebuilt bundle grows 0.17–0.39 MB (20 bundles, ~5 MB total, megapack 45.6 MB). The streamer's memory
budget for that is unknown. Textures were picked by name, not by material; where the donor lacks a texture the
tunic draws with whatever the material resolves to. A disguise whose tunic model the game cannot load at all
would fall back to the old failure mode, which is why the installer refuses to patch a pack it does not
recognise instead of half-applying the change.

## 6. Sources

- `docs/DESIGN.md` — what the mod changes, and the three parts that have to travel together.
- `build/vendor/cp_addparts.rs` — the bundle-surgery command, copied from
  [notes-on-reversing-the-saboteur](https://github.com/Mercenaries-Fan-Build/notes-on-reversing-the-saboteur)
  (MIT), where the format documentation lives.
