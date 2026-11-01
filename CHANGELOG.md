# Changelog

## 1.0.0 (2026-11-01)
- First release: the soldier's real tunic, collar, tie and gear on all 20 disguise sets (24 body-part swaps).
- The soldier tunic / trouser / gear models are copied into each disguise bundle in a patch megapack, so a save
  made in disguise can no longer wait forever for a model that no resident bundle registered.
- Fixes the one forward body-setup → body-part reference a disguise-trouser swap leaves behind, when the pack
  has one.
- Installer: hash-checked pack patching (only `GameTemplates.wsd` and `global.map` are touched), backup,
  automatic rollback, `status` and `uninstall`.
- Verified offline: byte-exact install/uninstall round-trips on a retail pack and on a modded one, `global.map`
  reproduced from the build plan, and the two engine invariants at 0 violations. Not yet run in game.
