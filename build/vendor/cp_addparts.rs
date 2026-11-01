// ===========================================================================================
// `cp-addparts`: put part models INTO a body-setup bundle (`include!`d into deploy.rs).
//
// Retail invariant (charport/INVESTIGATION.md 10.4, 5494/5494 references): every model a body setup's parts
// reference is in that setup's OWN bundle. A swap that points a part at a model from another bundle (the
// disguise trousers / soldier tunic) works only while some other bundle with that model happens to be resident;
// otherwise the model is never requested and the human blueprint's IsReady poll never succeeds
// (work/torso/TRACE_NOTES.md). This command restores the invariant: it copies the named models, byte for byte
// and under their own names, from a donor bundle into the target bundle. The stream-skip check
// (CheckForSkipAndSkip) then shares them with a resident copy or loads them from the target.
//
// plan.json:
// { "jobs": [ {"bundle": "FBS_WM_Grunt_Disguise", "donor": "FBS_WM_Grunt",
//              "models": ["CH_NZ_WM_Officer_UB", "0xDD644AAD"],     (names or 0x-hashes)
//              "textures": true} , ...],       (true: also each model's texture name and name_NM, _LOD stripped)
//   "out": "patchdynamic0.megapack", "changes": "changes.json" }
// For each model: the donor's mesh record (table hash == hash(name), AHSM name checked), and its phys record
// (table hash == hash(name)) are appended. Textures (when "textures" is true): per model N the donor textures hashed
// as N, N_NM, and (for N ending in _LOD) the name without _LOD and its _NM, that the target lacks. Records the target already has are skipped. A model missing from the donor is an error.
// Output: one patch megapack with every changed bundle (override keyed by the base entry's crc/index) and
// changes.json (appended records per bundle, for the global.map update).
// Usage: sab_poc cp-addparts --game <G> --gltf <plan.json>
// ===========================================================================================

fn ap_hash(v: &serde_json::Value) -> Result<u32, String> {
    let s = v.as_str().ok_or("hash/name must be a string")?;
    if let Some(h) = s.strip_prefix("0x") {
        return u32::from_str_radix(h, 16).map_err(|e| format!("bad hex {s}: {e}"));
    }
    Ok(pack::pandemic_hash(s))
}

struct ApAdd {
    cat: usize,
    df: albs::DynFile,
    blob: Vec<u8>,
}

pub fn cp_addparts(f: &Flags) -> Result<(), String> {
    let plan_txt = std::fs::read_to_string(&f.gltf).map_err(|e| format!("read plan {}: {e}", f.gltf))?;
    let plan: serde_json::Value = serde_json::from_str(&plan_txt).map_err(|e| format!("parse plan: {e}"))?;
    let base = std::path::Path::new(&f.gltf).parent().unwrap().to_path_buf();
    let jobs = plan["jobs"].as_array().ok_or("plan.jobs")?;
    let mp = pack::Megapack::open(&format!("{}/Global/Dynamic0.megapack", f.game))?;
    let dyns = albs::load_dyns(&f.game)?;

    // group jobs by target bundle, keeping first-seen order
    let mut order: Vec<String> = vec![];
    for j in jobs {
        let b = j["bundle"].as_str().ok_or("job.bundle")?.to_string();
        if !order.contains(&b) {
            order.push(b);
        }
    }

    let mut entries: Vec<(u32, u32, Vec<u8>)> = vec![];
    let mut changes: Vec<String> = vec![];
    for target in &order {
        let t_index = pack::pandemic_hash(target);
        let td = dyns.iter().find(|d| d.asset_index == t_index).ok_or_else(|| format!("{target}: no global.map record"))?;
        let t_entry = *mp.entries().iter().find(|e| e.index == t_index).ok_or_else(|| format!("{target}: not in Dynamic0"))?;
        let sub = mp.slice(&t_entry);
        let b = albs::parse_bundle(sub, td)?;
        let mut tables = b.tables.clone();
        let trailing = &sub[b.tbl_end + b.data_ext..];
        let mut blobs: Vec<Vec<Vec<u8>>> = (0..4).map(|c| tables[c].iter().map(|df| {
            let off = b.tbl_end + df[1] as usize;
            sub[off..off + df[2] as usize].to_vec()
        }).collect()).collect();
        let n0: Vec<usize> = tables.iter().map(|t| t.len()).collect();
        let mut added: Vec<ApAdd> = vec![];
        let mut skipped: Vec<String> = vec![];

        for j in jobs.iter().filter(|j| j["bundle"].as_str() == Some(target.as_str())) {
            let donor = j["donor"].as_str().ok_or("job.donor")?;
            let d_index = pack::pandemic_hash(donor);
            let dd = dyns.iter().find(|d| d.asset_index == d_index).ok_or_else(|| format!("{donor}: no global.map record"))?;
            let d_entry = *mp.entries().iter().find(|e| e.index == d_index).ok_or_else(|| format!("{donor}: not in Dynamic0"))?;
            let dsub = mp.slice(&d_entry);
            let db = albs::parse_bundle(dsub, dd)?;
            let dblob = |df: &albs::DynFile| dsub[db.tbl_end + df[1] as usize..db.tbl_end + (df[1] + df[2]) as usize].to_vec();

            let with_tex = j.get("textures").and_then(|v| v.as_bool()).unwrap_or(false);
            let mut want_tex: Vec<u32> = vec![];
            for m in j["models"].as_array().ok_or("job.models")? {
                let name = m.as_str().ok_or("model name")?;
                let h = ap_hash(m)?;
                let have = |tables: &Vec<albs::DynFile>| tables.iter().any(|df| df[0] == h);
                if have(&tables[0]) && have(&tables[1]) {
                    skipped.push(format!("{name} (already in {target})"));
                    continue;
                }
                let mi = db.tables[0].iter().position(|df| df[0] == h).ok_or_else(|| format!("{name}: not a mesh of donor {donor}"))?;
                let got = cp_slot_name(dsub, db.tbl_end, &db.tables[0][mi]);
                if !name.starts_with("0x") && got != name {
                    return Err(format!("{name}: donor slot name is {got:?}"));
                }
                if with_tex {
                    let stem = got.strip_suffix("_LOD").unwrap_or(&got).to_string();
                    for n in [got.clone(), format!("{got}_NM"), stem.clone(), format!("{stem}_NM")] {
                        want_tex.push(pack::pandemic_hash(&n));
                    }
                }
                let pi = db.tables[1].iter().position(|df| df[0] == h).ok_or_else(|| format!("{name}: no phys record in donor {donor}"))?;
                if !have(&tables[0]) {
                    added.push(ApAdd { cat: 0, df: db.tables[0][mi], blob: dblob(&db.tables[0][mi]) });
                    tables[0].push(db.tables[0][mi]);
                    blobs[0].push(dblob(&db.tables[0][mi]));
                }
                if !have(&tables[1]) {
                    added.push(ApAdd { cat: 1, df: db.tables[1][pi], blob: dblob(&db.tables[1][pi]) });
                    tables[1].push(db.tables[1][pi]);
                    blobs[1].push(dblob(&db.tables[1][pi]));
                }
            }
            for th in want_tex {
                if tables[albs::CAT_TEX].iter().any(|df| df[0] == th) {
                    continue;
                }
                if let Some(ti) = db.tables[albs::CAT_TEX].iter().position(|df| df[0] == th) {
                    let df = db.tables[albs::CAT_TEX][ti];
                    added.push(ApAdd { cat: albs::CAT_TEX, df, blob: dblob(&df) });
                    tables[albs::CAT_TEX].push(df);
                    blobs[albs::CAT_TEX].push(dblob(&df));
                } else {
                    skipped.push(format!("texture {th:08X} (not in donor {donor})"));
                }
            }
        }
        if added.is_empty() {
            println!("{target}: nothing to add ({})", skipped.join("; "));
            continue;
        }

        // serialise (same layout as cp_deploy / albs::rebuild_bundle)
        let mut data = vec![];
        let mut cursor = 0u32;
        for c in 0..4 {
            for i in 0..tables[c].len() {
                tables[c][i][1] = cursor;
                tables[c][i][2] = blobs[c][i].len() as u32;
                cursor += blobs[c][i].len() as u32;
                data.extend_from_slice(&blobs[c][i]);
            }
        }
        let mut out = b"ALBS".to_vec();
        out.extend_from_slice(&0u32.to_le_bytes());
        for t in &tables {
            for df in t {
                for &w in df {
                    out.extend_from_slice(&w.to_le_bytes());
                }
            }
        }
        out.extend_from_slice(&data);
        out.extend_from_slice(trailing);

        // verify against the NEW per-category counts: re-parse, consistency, original records unchanged
        let nd = albs::Dyn { asset_index: td.asset_index, name: td.name.clone(), n_mesh: tables[0].len() as u32,
                             n_phys: tables[1].len() as u32, n_flash: tables[2].len() as u32, n_tex: tables[3].len() as u32 };
        let vb = albs::parse_bundle(&out, &nd)?;
        cp_bundle_consistency(&out, &vb)?;
        for c in 0..4 {
            for i in 0..n0[c] {
                let (o, n) = (&b.tables[c][i], &vb.tables[c][i]);
                let ob = &sub[b.tbl_end + o[1] as usize..b.tbl_end + (o[1] + o[2]) as usize];
                let nb = &out[vb.tbl_end + n[1] as usize..vb.tbl_end + (n[1] + n[2]) as usize];
                if o[0] != n[0] || o[3] != n[3] || o[5] != n[5] || ob != nb {
                    return Err(format!("{target}: original record cat {c} #{i} changed"));
                }
            }
        }
        let rec = |cat: usize| -> Vec<String> {
            added.iter().filter(|a| a.cat == cat).map(|a| format!("{{\"hash\":\"0x{:08X}\",\"usz\":{},\"h1\":\"0x{:08X}\"}}", a.df[0], a.df[3], a.df[5])).collect()
        };
        println!("{target}: +{} mesh +{} phys +{} tex (donor bytes, {} -> {} B){}", rec(0).len(), rec(1).len(), rec(albs::CAT_TEX).len(),
                 sub.len(), out.len(), if skipped.is_empty() { String::new() } else { format!("; skipped: {}", skipped.join("; ")) });
        changes.push(format!("{{\"bundle\":\"{target}\",\"index\":\"0x{t_index:08X}\",\"mesh\":[{}],\"phys\":[{}],\"tex\":[{}]}}",
                             rec(0).join(","), rec(1).join(","), rec(albs::CAT_TEX).join(",")));
        entries.push((t_entry.crc, t_entry.index, out));
    }

    let patch = base.join(plan["out"].as_str().unwrap_or("patchdynamic0.megapack"));
    albs::write_patch_megapack(patch.to_str().unwrap(), &entries)?;
    let vmp = pack::Megapack::open(patch.to_str().unwrap())?;
    if vmp.entries().len() != entries.len() {
        return Err("patch megapack entry count mismatch".into());
    }
    let ch = base.join(plan["changes"].as_str().unwrap_or("changes.json"));
    std::fs::write(&ch, format!("{{\"bundles\":[{}]}}", changes.join(","))).map_err(|e| format!("write changes: {e}"))?;
    println!("PASS cp-addparts: {} bundles -> {}, changes -> {}", entries.len(), patch.display(), ch.display());
    Ok(())
}
