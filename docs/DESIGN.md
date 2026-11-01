# Design: the soldier's real uniform on every disguise

## The problem

In a Wehrmacht disguise, Sean still wears his own clothes: an open, white-shirted torso instead of the
soldier's tunic, collar and tie. The shipped disguise setups use a Sean-fitted tunic (`FBP_RS_Sean_Nazi_*`,
model `CH_AL_SeanDevlin_Nazi_*_UB`) and Sean's own gear; only the trousers come from the soldier sets in some
of the community's QoL builds. The collar-and-tie look is what the disguise is supposed to be.

## The change

24 body-part swaps across the 20 `FBS_*_Disguise` setups: Sean's Sean-fitted tunic becomes the soldier twin's
real tunic, and his `*_SEAN` accessory parts become the twin's gear. Everything else about the disguise is
untouched — the head, the trousers, the behaviour, the outfit ids the save file stores.

| disguise setup | tunic part after the swap |
|---|---|
| `FBS_GS_General_Disguise` | `FBP_SS_UB_General` |
| `FBS_GS_Grunt_Disguise` | `FBP_GS_UB_Infantry` |
| `FBS_GS_Heavy_Disguise`, `FBS_GS_Officer_Disguise` | `FBP_GS_UB_Officer` |
| `FBS_KM_Grunt_Disguise`, `FBS_KM_Heavy_Disguise` | `FBP_KM_UB_Infantry` |
| `FBS_SS_Flame_FT_Disguise` | `FBP_WM_UB_General` |
| `FBS_SS_General_Disguise`, `FBS_WM_General_Disguise` | `FBP_SS_UB_General` |
| `FBS_SS_Grenadier_Disguise` | `FBP_NT_UB_Infantry` + `FBP_SS_AC_Grenadier01` |
| `FBS_SS_Grunt_Disguise`, `_Heavy_`, `_Sniper_` | `FBP_SS_UB_Infantry` |
| `FBS_SS_Officer_Disguise` | `FBP_SS_UB_Officer` |
| `FBS_WM_Grenadier_Disguise`, `FBS_WM_Grunt_RF_Disguise`, `FBS_WM_Sniper_Disguise` | `FBP_LF_UB_Infantry` |
| `FBS_WM_Grunt_Disguise` | `FBP_WM_UB_Officer` + `FBP_WM_AC_Grunt03` |
| `FBS_WM_Heavy_Disguise` | `FBP_WM_UB_Coat` + `FBP_SS_AC_Heavy03` |
| `FBS_WM_Officer_Disguise` | `FBP_WM_UB_Officer` |

The exact slot/hash pairs are `installer/torso_swaps.json`; the installer refuses to write a swap whose
expected old value is not what it finds.

## Why it is three parts, not one

A tunic swap alone is the change that made the game hang on Continue. The reason is not the swap, it is
where the soldier's model lives: in the soldier bundle, not in the disguise bundle. The engine only ever
loads a body setup's *own* bundle, so the model is never requested and the loading screen waits forever
(details and addresses: `docs/MECHANISM.md`).

So the mod ships, and installs together:

1. **the template edits** — `GameTemplates.wsd` inside `France\loosefiles_BinPC.pack`: the 24 part swaps,
   plus the one record reorder that removes a pre-existing forward body-setup reference if the pack has one;
2. **`global.map`** — the 20 disguise bundle records list the copied models and textures, with counts and the
   `q` field recomputed;
3. **`Global\patchdynamic0.megapack`** — the 20 rebuilt disguise bundles, each carrying the soldier tunic,
   trouser and gear models and their physics, copied byte for byte from its soldier twin.

`Global\Dynamic0.megapack` and every other shipped file are left alone. The pack is patched entry by entry
(`GameTemplates.wsd`, `global.map`) rather than replaced, so camera, weapon or other template mods in the same
pack survive; only those two entries change.

## Install mechanics and safety

- Refuses unless `global.map` is the stock one and no foreign `patchdynamic0.megapack` is present.
- Verifies the release files by sha256 before touching anything.
- Backs up the current pack to `installer\backups\` (named by its sha256, re-verified).
- Writes the new pack to a temporary file, verifies its sha256, then renames it into place; if the final
  check fails it restores the backup.
- Stages the megapack, verifies it, then renames it into place; any failure restores the pack and removes the
  megapack, so the folder ends up as it started.
- Uninstall reverses the two template entries, restores the stock `global.map`, and deletes the megapack.
  The record order is restored from `installer\backups\install-state.json`.

## Test status

Offline verification is in `docs/VERIFICATION.md`: the patched pack, the regenerated `global.map` and the
installed bundle tables all check out against the shipped data, and install/uninstall round-trips are
byte-exact on both a stock pack and a heavily modded one. **The mod has not been run in game yet** — the
author's rule is that the game is launched by a human, not by a tool. First things to look at are listed at
the end of `docs/VERIFICATION.md`.
