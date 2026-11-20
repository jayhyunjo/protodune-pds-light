# `OpFlashFinderVerticalDrift` produces only single-PD flashes on ProtoDUNE-VD — diagnosis, fix, and validation

**J. Jo — 2026-07-09**

- **Package:** `duneopdet` v10_21_00d00 (dunesw v10_21_00d00, `-q e26:prof`), module `duneopdet/OpticalDetector/OpFlashFinderVerticalDrift_module.cc`, config `protodunevd_opflash`.
- **Data:** ProtoDUNE-VD (NP02) cosmics, raw `np02vd_raw_run039349_0035_df-s03-d3_dw_0_20250909T125946.hdf5`, 28 events, `protodunevd_v5` geometry (40 OpDets: 8 cathode X-ARAPUCAs, 8 membrane X-ARAPUCAs, 24 PMTs).
- **Chain:** `pdvddaphne` (PDS decode) → `ophit` → `opflash`, i.e. `pdvd/fcl/pdvd_pds_flash.fcl` of the [protodune-pds-light](https://github.com/jayhyunjo/protodune-pds-light) repo, run in the SL7 container against cvmfs.

## Executive summary

The stock VD flash finder assigns essentially **one OpDet to every flash** — on this file, **160,419 flashes from 160,430 OpHits** (one flash per hit; mean multiplicity 1.00004, max 2). Coincident scintillation light seen across up to ~27 PDs is never grouped, so flash-based charge–light matching is impossible. The cause is **three independent bugs**: (1) hard-coded far-detector-scale geometry thresholds that never match ProtoDUNE-VD, (2) a `float` cluster-seed time that cannot represent PDVD timestamps to better than ~1024 ticks, and (3) — decisively — a **sorted-vs-original index mismatch** that assigns the *wrong hits* to each flash. Replacing the clustering with a double-precision greedy time-window grouping that returns original hit indices fixes the module; its output was validated **flash-by-flash identical** (all 43,763 flashes: same OpDet multiplicity, total PE agreeing to < 6×10⁻⁸ relative) against an independent Python grouping of the same OpHits.

| build | flashes (28 evts) | mean mult | max mult | multi-PD |
|---|---|---|---|---|
| stock v10_21_00d00 | 160,419 | 1.00004 | 2 | 0.004 % |
| bugs 1+2 fixed only | 43,919 | 1.74 | 5 | 72.6 % |
| **full fix (patched)** | **43,763** | **2.91** | **27** | **72.8 %** |

## 1. The symptom

The OpDet-multiplicity distribution collapses to a spike at 1 with the stock finder; the fixed finder recovers a spectrum reaching 27 distinct OpDets per flash:

![multiplicity](plots/01_multiplicity_stock_vs_fixed.png)

Looking at one bright scintillation burst (event 19409, brightest ≥20-PD flash): the fixed finder reports **one flash with 20 OpDets and 293,343 PE**; the stock finder splinters the same 2-tick window into **29 single-PD flashes** (the brightest of which — a single cathode X-ARAPUCA with 212,237 PE — is all an analyzer would see at that time):

![display](plots/02_flash_display_stock_vs_fixed.png)

The light really is coincident — the OpHits line up across the detector within the 2-tick window; the finder was dropping the association, not the data:

![raster](plots/03_ophit_raster.png)

## 2. Root causes — three independent bugs

### Bug 1 — far-detector-scale plane thresholds never fire

`getNeighbors()` decides which detector "plane" a pair of hits belongs to with hard-coded coordinates — cathode `Cx = −320`, membrane `RMy/LMy = ±700`. In `protodunevd_v5` the cathode X-ARAPUCAs sit at **X ≈ 0** and the membrane X-ARAPUCAs at **|Y| ≈ 418**, so *none* of the seven plane branches is ever satisfied: no pair of hits is ever declared neighbours.

### Bug 2 — `float` cluster-seed time at PDVD timestamps

The cluster seed time `initimecluster` is a 32-bit `float`, but PDVD `PeakTime` values are ~1.6×10¹⁰ ticks. The float32 spacing (ULP) at that magnitude is **1024 ticks — 512× the entire `MaximumTimeWindow = 2` cut**. The seed time gets snapped onto the float32 grid, so the `dtmax < 2` test selects hits in a 2-tick window centred up to ±512 ticks *away from the seed* (−146 ticks for the seed shown below), i.e. it tests the wrong window entirely:

![float](plots/04_float_precision.png)

### Bug 3 (decisive) — sorted-position vs original-index mismatch

`getNeighbors()` returns hit indices as **positions in the time-sorted array**, but `ConstructFlash()` and the `art::Ptr` flash↔hit associations consume them as **original `HitVector` indices**. Only the seed is pushed with its original index; every neighbour is a sorted position misused as an original index. Each flash is therefore built from the *wrong hits* — membership, PE sums, positions and associations are all corrupted. This bug is detector-independent: it corrupts any detector where the sorted and original hit orders differ (i.e. always).

The three-way comparison isolates it: fixing bugs 1+2 alone restores a plausible *flash count* (43,919 vs 43,763) but the flash *contents* remain wrong — mean multiplicity 1.74 instead of 2.91, max 5 instead of 27:

![isolation](plots/05_bug_isolation.png)

## 3. The fix

Replace the `getNeighbors` + BFS clustering inside `AssignHitsToFlash()` with a **greedy time-window grouping in double precision returning original hit indices**: sort hits by `PeakTime`; each flash spans `[t0, t0 + MaximumTimeWindow]` from its earliest ungrouped hit. No spatial cut is applied — at ProtoDUNE-VD scale every PD seeing coincident light belongs to the same flash; spatial structure is recovered downstream from the per-OpDet PE pattern. `AddHitContribution()`/`ConstructFlash()` were already correct, so once the grouping feeds them the right hits, multi-PD `recob::OpFlash` come out directly.

Patch (diff vs the pristine `v10_21_00d00` tag) and full patched module:
`protodune-pds-light/studies/pdvd_flash_finder/patch/`.

## 4. Validation

The patched C++ finder was compared flash-by-flash against `pdvd/flash/group_ophits.py` — an independent, standalone double-precision grouping of the *same* OpHits (`opflashana/PerOpHitTree`). Over all 28 events: identical flash count per event (43,763 total), **Δn_opdet = 0 for every flash**, and per-flash total PE agreeing to float-precision roundoff (max |ΔPE/PE| = 5.9×10⁻⁸):

![identity](plots/06_validation_identity.png)

## 5. The remaining knob

The greedy window `MaximumTimeWindow` (default 2) is the only tuning parameter left: it sets how finely bursts are split. The scan below (python reference grouping) shows flash count and multiplicity vs the window; the default sits on a smooth slope — no cliff — and gives ~1,560 flashes/event on this cosmics data:

![scan](plots/07_dt_scan.png)

## 6. Notes for upstream

- Bugs 1 and 3 are geometry/indexing defects, not tunings; bug 3 corrupts the flash↔OpHit `art::Ptr` associations on **any** detector.
- A spatial/topological cut could be reintroduced deliberately (e.g. to separate simultaneous distant flashes), but it must use the actual detector geometry and a consistent index space — the stock cut did neither.
- The `float`→`double` seed-time issue will recur anywhere absolute DAQ timestamps are carried in single precision; VD timestamps already exceed float32 integer resolution by 3 orders of magnitude.

## Appendix — reproduction

Everything below runs on wcgpu1 (cvmfs + apptainer) inside the SL7 container:

```bash
# environment
apptainer exec -B /cvmfs -B $HOME -B /nfs/data \
  /cvmfs/singularity.opensciencegrid.org/fermilab/fnal-dev-sl7:latest bash
source /cvmfs/dune.opensciencegrid.org/products/dune/setup_dune.sh
setup dunesw v10_21_00d00 -q e26:prof

# patched finder: mrb dev area with duneopdet @ v10_21_00d00 + patch, then
source vddev/localProducts_dune_v10_21_00d00_e26_prof/setup; mrbslp

# reco + flat dump (repo: protodune-pds-light)
lar -c pdvd/fcl/pdvd_pds_flash.fcl -s <raw>.hdf5 -o flashreco.root -T hist.root
python pdvd/scripts/pdvd_dump_flash.py flashreco.root flash.root

# independent cross-check
python pdvd/flash/group_ophits.py hist.root --dt 2 --min-pds 1 --out ref
```

Raw HDF5 inputs: `/nfs/data/1/xning/container/dune_data/hdf5/PDVD/`. The three finder variants, logs, art/plain-ROOT outputs and the dev area are under `/nfs/data/1/jjo/tmp/pdvd_flash_validation/`. Plots regenerate with `plot_all.py` (venv in the same directory); headline numbers in `stats.json`.
