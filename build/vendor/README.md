# vendored: `cp_addparts.rs`

Copied verbatim from
[notes-on-reversing-the-saboteur](https://github.com/Mercenaries-Fan-Build/notes-on-reversing-the-saboteur)
`tools/sab_poc/src/cp_addparts.rs` (MIT, © Mercenaries-Fan-Build). It is the one build step this repository
does not implement itself: appending mesh / physics / texture records to an existing bundle and writing the
patch megapack. Everything else the mod needs is in `build/` and `installer/`.

It is not a standalone crate. To run it, in a checkout of that repository:

1. put this file at `tools/sab_poc/src/cp_addparts.rs`;
2. it is `include!`d at the end of `tools/sab_poc/src/deploy.rs`:
   ```rust
   include!("cp_deploy.rs");
   include!("cp_addparts.rs");
   ```
3. add the dispatch arm in `tools/sab_poc/src/main.rs`:
   ```rust
   "cp-addparts" => deploy::cp_addparts(&flags),
   ```

Then:

```
cargo run --release -- cp-addparts --game "C:/Saboteur/The Saboteur" --gltf "path/to/plan.json"
```

Its input and output are described at the top of the file and in `../plan.json` / `../plan.changes.json`.

If the upstream project later grows the same command (or renames it), prefer upstream and drop this copy.
