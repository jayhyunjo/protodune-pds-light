# ProtoDUNE-HD PDS reconstruction & charge–light matching — session summary

Reference / handoff for the PDHD photon-detector (PDS) work: the reco workflow, the
deconvolution + SPE templates, the interactive flash viewer, and geometry / photon-sim
consistency. (Next session pivots to **ProtoDUNE-VD** — see §12.)

---

## 1. Environment & data
- **Software:** `dunesw v10_20_09d00 -q e26:prof`, run inside the SL7 container (EL9 host):
  ```
  apptainer exec -B /cvmfs -B /exp -B /tmp -B /run/user \
    /cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest <cmd>
  ```
- **Geometry: protodunehd v6** (`protodunehdv6_geo`, GDML `protodunehd_v6_refactored.gdml`).
  Set *explicitly* in both reco fcls — it is **not** a side-effect of the dunesw version
  (v10_20_09d00 ships v1/v2/v3/v6/v7 geometry configs + v8 GDML; we chose v6).
- **Data:** 4 runs, raw HDF5 in `/exp/dune/data/users/jjo/pdhd_data/`, products in
  `…/pdhd_data/workflow_out/`:

  | run | note |
  |---|---|
  | 27305 | +x-dominated *light*; APA2 mostly off (~6/40 self-trig ch). Raw still has APA1 full-stream + sparse APA2. |
  | 27980 | both planes |
  | 28084 | both planes |
  | 29107 | both planes (largest, ~1.8 GB final) |

## 2. Two-step workflow — `temp/run_workflow.sh`
1. **Keepup reco** (does the PDS deconvolution): 
   `lar -c standard_reco_protodunehd_keepup.fcl -s <raw>.hdf5 -o <tag>_keepup.root`
2. **Flat tree** (analysis output): 
   `lar -c pds_flat_tree.fcl -s <tag>_keepup.root -T <tag>_final.root`
- Before each `lar`: `source temp/offdev/localProducts*/setup && mrbslp` (for the custom plugins).
- Both fcls set `services.Geometry: @local::protodunehdv6_geo` (+ AuxDetGeometry v6) and
  `services.WireReadout.WireReadoutClass: "DuneApaWireReadout"` (the PDS map fix, §6).
- The `*_keepup.root` files are **kept** — they still hold the raw `pdhddaphne:daq`, which is
  what lets us re-deconvolve downstream (§5d) without re-running the keepup.

## 3. Custom package `pdsoffset` (mrb dev area)
- **Dev area:** `temp/offdev` (`$MRB_SOURCE = temp/offdev/srcs/pdsoffset`).
  ⚠️ A **stale duplicate** at `temp/srcs/pdsoffset` (no `offdev/`) is ignored by mrb — always
  edit under `offdev/srcs/pdsoffset/pdsoffset/`.
- **Modules** (`*_module.cc` + one `cet_build_plugin` each in that dir's `CMakeLists.txt`):
  - `TriggerOffsetAna` — per-event TPC↔trigger time offset → `trigger_offset` tree.
  - `FlashOpDetAna` — `opdet_geo` (all OpDet positions) + `flash_opdet` (PE/OpDet/flash).
  - `PDSRawWaveformDump` — every `raw::OpDetWaveform` → `raw_waveform` tree (also a histogram mode).
  - `PDSDecoWaveformDump` — `recob::OpWaveform` → `deco_waveform` tree, **uncapped** (decoana caps at ~400/evt).
- Build: `mrbsetenv; mrb b`. If `buildtool: not found`, `export PATH="$CETMODULES_DIR/bin:$PATH"`.
- ⚠️ Don't name a module `RawWaveformDump` — collides with larrecodnn; hence the `PDS` prefix.

## 4. `_final.root` tree inventory (per run)
- `opflashana/FlashBreakdownTree` — per-(flash,channel) recob PE (`NPe`) + `AbsTime`.
- `flashopdet/opdet_geo` + `flashopdet/flash_opdet` — OpDet positions + PE per flash.
- `rawdump/raw_waveform` — **all** raw OpDetWaveforms. **Verified all 4 files have BOTH**:
  self-trigger (ch 0–119, ~1024 samp, 16 ns) **and** APA1 full-stream (ch 120–159, ~343808 samp;
  27305 ~187584). ~30–34 events/file.
- `decodump/deco_waveform` — **v1** deconvolved waveforms (production, §5).
- `decodumpv0/deco_waveform` — **v0** (Nov2024 per-channel) deconvolved waveforms (§5).
- `decodumpnp04/deco_waveform` — **NP04 vendor-average** deconvolved waveforms (§5d).
- `rawhist/…` (per-record raw TH1S), `decoana/…`, `trigoff/trigger_offset`.

## 5. Deconvolution & SPE templates (the main topic)

### 5a. Three deconvolutions in the output (v0, v1, NP04 — for direct comparison)
| tree | template | where deconvolved |
|---|---|---|
| `decodump/deco_waveform` | **v1** (per-channel, Jun2025) | **keepup reco** (`opdec`); flat job only *dumps* it |
| `decodumpv0/deco_waveform` | **v0** (per-channel, Nov2024) | **flat job** (producer `opdecv0`, re-run on saved raw) |
| `decodumpnp04/deco_waveform` | **NP04** (2 vendor averages) | **flat job** (producer `opdecnp04`, re-run on saved raw) |

Producers `opdecv0` = `protodunehd_deconvolution + @table::protodunehd_pds_channels_data_v0`
and `opdecnp04` = `… + protodunehd_pds_channels_mc`, both on `physics.reco: [opdecv0, opdecnp04]`,
`InputModule:"pdhddaphne" InstanceName:"daq"`; v1 comes straight from the stored keepup `opdec`.

### 5b. How v1 is produced (the production deconvolution)
- Keepup `opdec` = `@local::protodunehd_deconvolution` (InputModule `pdhddaphne`, instance `daq`).
- `protodunehd_deconvolution` = LArSoft `Deconvolution` module + `@table::protodunehd_pds_channels_data_v1`.
- **v1** = `protodunehd_template_list_v1` = **Jun2025 per-channel SPE kernels**, 113 channels,
  `SPETemplatePath: ProtoDUNE/HD/opdetresponse/v1/` (files `run28368/28370/28492_…_Jun2025.txt`).
- **Map is strictly per-channel (1:1):** `SPETemplateMapChannels=[0,1,2,4,…,119]`,
  `SPETemplateMapTemplates=[0,1,…,112]` → OpCh *c* deconvolved with the kernel named `…_CH<c>_…`.
- `IgnoreChannels = [-1, 3, 86, 87, 97, 107, 116, 117, 120…159]` → **113 channels deconvolved**
  (the 7 dead/noisy + the 40 APA1 full-stream get **no** deco).
- Algorithm: divide raw by the per-channel SPE kernel in Fourier space, Wiener + Gaussian
  post-filter, FFT noise template, AutoScale by SPE peak → `recob::OpWaveform` (~PE/tick).
- `decodump` (`PDSDecoWaveformDump`, `OpWaveformTag:"opdec"`) reads that stored product and dumps it.

### 5c. SPE template landscape (this confused us for a while — resolved)
Two **separate** categories:
- **Vendor-level pairs** in `duneopdet/config_data/` (2 files = 1 FBK + 1 HPK each):
  `SPE_CAEN_*_2022`, `SPE_DAPHNE2_*_2022`, **`SPE_DAPHNE2_*_2024`**, **`SPE_NP04_*_2024_without_pretrigger`**.
  - `SPE_NP04_*_2024_without_pretrigger.dat` = `SPE_DAPHNE2_*_2024.dat` with the pre-trigger
    trimmed (byte-identical post-peak; peak 8.72/13.83 ADC FBK/HPK; net-area ≈ 0, DC-balanced).
    Also mirrored in the stash `ProtoDUNE/HD/opdetresponse/SPE_NP04_*` (the copy `opdecnp04` loads).
- **Per-channel sets** in the osgstorage stash `…/ProtoDUNE/HD/opdetresponse/`:
  `v0/` = Nov2024 (`SPE_Template_run28370/28492_…_{hpk|fbk}_Nov2024.txt`, vendor in name),
  `v1/` = Jun2025 (`run…_Change_Scale_…Jun2025.txt`, no vendor in name). Both 113 channels.

### 5d. NP04 vendor-average = "Xin's method", reproduced in LArSoft
- Colleague **Xin** uses 2 vendor-average kernels in **WireCell `OpDecon`** (extracted into
  `cfg/pgrapher/experiment/pdhd/pdhd-spe-templates.json` from the same `SPE_NP04_*` `.dat`).
- LArSoft equivalent already exists: **`protodunehd_pds_channels_mc`** (= `_data_dummy`) uses the
  2 NP04 kernels + a **68-FBK / 92-HPK** vendor→template map.
- We added a producer to the flat job: `opdecnp04 = { @table::protodunehd_deconvolution
  @table::protodunehd_pds_channels_mc }` (keeps v1's filter/noise/ignore, swaps SPE kernels),
  on `physics.reco`, dumped by `decodumpnp04`. **This re-deconvolves the saved raw — no keepup re-run.**
- ⚠️ Same templates ≠ same result as Xin: WCT `OpDecon` ≠ LArSoft `Deconvolution` (different filter /
  normalization / tail). Expect similar prompt pulse, different tail.

### 5e. HPK/FBK vendor map → `temp/opch_vendor.txt`
- **All 160 channels**, from `protodunehd_pds_channels_data_dummy/_mc` `FBKChannels`(68)/`HPKChannels`(92);
  matches the per-channel v0 filename vendors with **0 mismatches**, and adds APA1.
  Per-APA: APA4 36 HPK/4 FBK; APA3 24 FBK/16 HPK; APA2 24 HPK/16 FBK; APA1 24 FBK/16 HPK.
- The viewer auto-loads this file to label clicked PDs.

### 5f. Channel mapping in deconvolution
- Hardware → offline OpChannel (0–159) is done **upstream** by the `pdhddaphne` raw decoder
  (DAPHNE channel map), *before* deconvolution.
- Inside deconvolution: only **OpChannel → template** lookups (`SPETemplateMapChannels` for SPE,
  `NoiseTemplateMapChannels` for the Wiener noise) + `IgnoreChannels`. No channel renumbering.
- Output keeps the same OpChannel; in PDHD **OpChannel == OpDet (1:1)**.
- **Verified** (resolved `opdec`/`opdecnp04` configs): each channel deconvolved with its own
  vendor's template — FBK→FBK, HPK→HPK, 0 mismatches.

### 5g. Key deconvolution finding
- **NP04 vs v1** (same raw): prompt-pulse peaks agree ~10–15 %, but **v1 over-subtracts the tail
  into a deep negative undershoot** while **NP04 stays ≈ flat** (DC-balanced vendor kernel) —
  consistent with the SPE-kernel comparison plot (v1 has large +net-area; NP04 ≈ 0).
- Earlier raw-vs-deco study (run 27305 ev150): raw and deco rank channels differently (raw
  brightest ≠ deco brightest) — uncalibrated/over-subtracting commissioning templates distort
  per-channel PE; the **raw waveform is the more faithful relative-light measure** for matching.

## 6. The WireReadout / OpChannel-map fix (important)
- PDHD's geometry name ("protodunehdv6") matches only "protodune", so `DUNEWireReadout` fell back to
  the **ProtoDUNE-SP** optical map (256 ch) → channels **40–47, 88–95** flagged invalid →
  `OpHitFinderDeco` silently dropped their OpHits/PE (thousands of "unrecognized channel" errors).
- **Fix (config-only, no rebuild):** `services.WireReadout.WireReadoutClass: "DuneApaWireReadout"`
  (NOpChannels=160, all valid, 1:1 OpChannel↔OpDet). Applied to **both** the keepup fcl and
  `pds_flat_tree.fcl` (must match, or `FlashBreakdownTree` reads past the PE vector → phantom OpCh 160–255).
- **APA ↔ OpChannel map (verified via `PD2HDChannelMap`):**
  OpCh **0–39 = APA4** (+x, hi-z), **40–79 = APA3** (+x, lo-z), **80–119 = APA2** (−x, hi-z),
  **120–159 = APA1** (−x, lo-z). PD numbering is drift-side-major (≠ geometry's z-major TPC index).

## 7. `temp/flash_viewer.py` (interactive per-flash light browser)
- Backend-agnostic: prefers **uproot** (laptop), falls back to **pyROOT** (container).
- Layout: 2×2 YZ hit maps (RAW +x/−x on top, DECONV +x/−x below) + a waveform column.
- Click a PD → its **raw** (top) + **deconvolved** (bottom) waveforms; deco panel **overlays
  v1 (red), v0 (blue), and NP04 vendor-avg (green)** and shows `total PE` (recob OpFlash PE for that ch/flash).
- **Color scale:** fixed dataset-wide, **linear, 0…99th-percentile** (BEE-display style);
  `--log-scale`, `--auto-scale`, `--pe-max V` override. Each panel has a **dedicated colorbar axes**
  (fixes a bug where panels shrank on every flip). Maps use `aspect="auto"` (fill the box).
- **Dead/noisy channels** {3, 86, 87, 97, 107, 116, 117} drawn with a **red ✗** (APA1 not marked).
- **APA1 raw** (full-stream, no deco) shown as a ±8 µs zoom around the flash time on click.
- Vendor (HPK/FBK) shown in the waveform title (from `opch_vendor.txt`).
- `--probe EV:CH [--out f.png]` = headless single-channel dump; it auto-jumps to the **lowest
  flash-id where that channel is lit** (so clicking a channel in a flash where it didn't fire shows
  "no raw record near this flash" — that's expected, not a bug).
- `--overlay-ch CH [--normalize]` = **interactive** per-channel **persistence** view: overlays ALL
  deconvolved waveforms for a channel across the whole file, one panel per template (v0/v1/NP04, top→bottom);
  **←/→ flip channel**, ↑/↓ ±10, q. `--normalize` peak-normalizes each (compare shapes/tails, not
  amplitude). `--out f.png` = one-shot headless save of the start channel.
- ⚠️ The viewer is **PDHD-specific** (the `APA_OF`, `BAD_CHANNELS`, v6 PD positions, ±x split).

## 8. Geometry v6 / v7 / v8 (all in `dunecore/v10_20_09d00/gdml/`, build-generated; not in github gdml dirs)
- **v6 → v7:** 58 lines — material additions (`foam_protoDUNE_RPUF`, `FR4SussexAPA`) + whitespace.
  **No positions moved.**
- **v7 → v8:** 474-line diff, **entirely X-ARAPUCA / OpDet `y`-positions** (`posArapuca…`,
  `posOpArapuca…`) — 208 positions, **y only** (x, z unchanged), shifted **+7.4 … row-dependent
  −12.6 … +9.0 cm**; the per-row y-layout was refined (12 rows → ~20). So **v8 is a PD-position
  correction.** (+8 field-cage module positions ±11.03 cm.) Lines ~64478–66393 of the v8 GDML.
- **There is no `protodunehdv8_geo` config** in this dunesw (only GDML); to use v8 you'd define one.

## 9. Photon visibility / semi-analytical model (verified v6-consistent)
- PDHD has **3 fast-sim options** in `PDFastSim_dune.fcl`:
  - `protodune_hd_pdfastsim_par` — **semi-analytical (Gaisser-Hillas, `PDFastSimPAR`)**, uses
    `protodune_hd_vuv_hits_parameterization` + `ProtoDUNEHDOpticalPath`. **Reads OpDet positions from
    the runtime geometry** → set `services.Geometry = protodunehdv6_geo` to match the data; the
    Nhits params are version-agnostic fit coefficients (no baked library).
  - `protodune_hd_pdfastsim_ann_ar` — `PDFastSimANN` ML computable graph
    `protodune_hd_128nm_tf2.6`, **"generated for protodunehd_v6_refactored.gdml"** (v6 baked into the graph).
  - `protodune_hd_pdfastsim_pvs` — voxel **library** (uses a `…photonvisibilityservice` from
    `photpropservices_dune.fcl`): **v6** (`…v6_hybridModel…` / `lib_protodunehd_v6_refactored…`) — use this;
    the older **v2** (`Photon_library_protoDUNEhd_v2_refactored…`) would NOT match v6.
- **`photpropservices_dune.fcl` only holds the *library* (PVS) configs** — the semi-analytical model
  is configured in the `PDFastSim` module (`PDFastSim_dune.fcl` + `opticalsimparameterisations_dune.fcl`),
  **not** in photpropservices. That's why no "semi-analytical block" is found there.
- **No v7/v8 PDHD photon model exists** → v6 is the latest and matches the v6 data. Bottom line for
  charge–light matching: run the prediction with **v6**, consistent with the data.

## 10. Misc resolved questions
- 27305 is **not** raw-"+x-only": APA4+APA3 fully self-triggered, **APA1 full-stream present (40 ch)**,
  APA2 mostly off (~6/40). "+x-only" referred to the dominant *flash light*.
- "9 PDs fire" / "bright PD with dark neighbours" in self-trigger = per-channel thresholds +
  SPE-deconvolution distortion (real DAQ behaviour, not a bug).

## 11. Key paths
```
temp/run_workflow.sh                      two-step driver
temp/standard_reco_protodunehd_keepup.fcl keepup reco (opdec = v1)
temp/pds_flat_tree.fcl                     flat trees (+ opdecnp04 NP04 re-deco)
temp/offdev/srcs/pdsoffset/pdsoffset/      custom modules ($MRB_SOURCE)  [edit HERE, not temp/srcs]
temp/flash_viewer.py                       interactive viewer
temp/opch_vendor.txt                       OpCh -> HPK/FBK (all 160)
/exp/dune/data/users/jjo/pdhd_data/workflow_out/*_final.root   outputs (v1 + NP04 deco trees)
$DUNEOPDET_DIR/fcl/{Deconvolution,dune_opdet_channels,PDFastSim_dune,photpropservices_dune,opticalsimparameterisations_dune}.fcl
$DUNECORE_DIR/gdml/protodunehd_v{6,7,8}_refactored.gdml
```

## 12. For the ProtoDUNE-VD pivot (next session)
The same machinery has VD analogs worth checking first:
- **Geometry:** `protodunevd_v2/v4/v5` GDMLs + `protodunevdvN_geo` configs (cathode + membrane PDs,
  different X-ARAPUCA layout & channel count; verify the OpChannel↔OpDet map and WireReadout class).
- **Photon-sim:** `protodune_vd_v2/v4/v5_pdfastsim_ann_*` ANN computable graphs
  (`protodune_vd_vN_128nm/175nm_tf2.6`) — each "generated for protodunevd_vN…gdml" → pick the graph
  matching the VD data geometry (same v6-style consistency check as §9).
- **Deconvolution/SPE:** check whether VD uses the same `Deconvolution` module + a VD channel table
  (`protodunevd_pds_channels_*`?) and where the VD SPE templates live.
- **Viewer:** `flash_viewer.py` is PDHD-specific (APA split, `APA_OF`, `BAD_CHANNELS`, v6 positions) —
  would need a VD geometry/channel-map adaptation.
- Reuse the workflow pattern (keepup → flat, keep the raw, dump trees) and the `pdsoffset` modules
  (they're detector-agnostic except FlashOpDetAna's geometry use).
