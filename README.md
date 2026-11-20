# protodune-pds-light

Photon-detector (PDS / "light") signal processing and visualization tools for
**ProtoDUNE-VD (NP02)** and **ProtoDUNE-HD (NP04)**.

- **PDVD**: decode the raw light waveforms, dump them to a plain-ROOT flat tree, and
  browse them with an interactive event/waveform viewer.
- **PDHD**: the existing keepup→flat-tree workflow, the `pdsoffset` analyzer package,
  and the flash viewer.

Everything runs against `dunesw` inside the SL7 container:

```bash
apptainer exec -B /cvmfs -B /exp -B /tmp -B /run/user \
  /cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest bash -l
source /cvmfs/dune.opensciencegrid.org/products/dune/setup_dune.sh
setup dunesw v10_21_00d00 -q e26:prof      # PDVD (v10_20_09d00 for the PDHD workflow)
```

---

## Layout

```
pdvd/
  fcl/      pdvd_pds_raw.fcl              decode PDS only (pdvddaphne) -> raw::OpDetWaveform, keep raw
            pdvd_pds_ophit.fcl           pdvddaphne+ophit+opflash+OpFlashAna (OpHit/flash trees)
            pdvd_pds_flash.fcl           pdvddaphne+ophit+opflash, keep recob::OpHit+OpFlash (drop
                                          raw wf); run w/ the FIXED finder (mrbslp) -> lean art
            dump_protodunevd_geometry.fcl geo::DumpGeometry of protodunevd_v5 (OpDet positions)
  scripts/  run_pdvd_pdsraw.sh            batch: raw HDF5 -> <tag>_pdsraw.root (art)
            pdvd_dump_rawwf.py            art raw::OpDetWaveform -> PLAIN-ROOT raw_waveform tree
            run_pdvd_rawwf_dump.sh        batch wrapper for the raw-wf dump
            pdvd_dump_flash.py           art recob::OpFlash/OpHit -> PLAIN-ROOT flash/flash_opdet/ophit
            run_pdvd_flash.sh            batch: raw HDF5 -> plain-ROOT flash file (fixed finder)
  viewer/   pdvd_raw_viewer.py            interactive raw-light EVENT/waveform viewer
            pdvd_flash_viewer.py         interactive FLASH viewer: PE maps + click->raw waveform
  flash/    group_ophits.py               standalone double-precision OpHit->flash grouping; the
                                          reference the fixed finder was validated against (identical)
  maps/     pdvd_v5_opdet_positions.csv   OpDet(0-39) -> x,y,z, type, name  (from the geometry)
            pdvd_offlinechan_to_opdet.csv offline channel(1010-3240) -> OpDet  (from the DAPHNE map)

pdhd/
  fcl/      standard_reco_protodunehd_keepup.fcl, pds_flat_tree.fcl
  scripts/  run_workflow.sh               keepup reco -> flat tree
  viewer/   flash_viewer.py               interactive flash/waveform viewer (raw + deconvolved)
  maps/     opch_vendor.txt               OpCh -> HPK/FBK vendor (all 160)
  pdsoffset/                              custom LArSoft analyzer package (build with mrb):
                                          PDSRawWaveformDump, PDSDecoWaveformDump,
                                          FlashOpDetAna, TriggerOffsetAna

studies/
  pdvd_flash_finder/  the OpFlashFinderVerticalDrift single-PD-flash bug: BUG_REPORT.md (3 root
                      causes + fix), patch/ (patched module + diff vs v10_21_00d00), diagnosis fcls
  pdvd_flashfinder_report/  the WRITE-UP of that bug: report.md/.html (self-contained, figures
                      embedded), slides.pptx, plot_all.py, and the wcgpu1-vs-dunegpvm
                      build-equivalence note. Read pdvd_flash_finder/ for the fix, this for
                      the measurement.
  pdvd_ql_trigger_t0/ the per-event charge<->light time-base offset: ANSWER.md (+ Q2-Q4 on
                      cathode SPE normalization and Ar-vs-Xe per run), the 120-event offset
                      table, and the lean decoders-only fcl. Built on pdhd/pdsoffset's
                      PDVDTriggerLightAna. Headline: light is trigger-locked to +-0.3 us,
                      charge floats +-15 us -- use the per-event, per-crate offset.
  pdhd_spe_template_cmp/  per-channel v1/v0 vs NP04 vendor-average SPE templates: a validated
                      numpy port of the LArSoft Deconvolution module (max |diff| <= 3e-8 vs
                      stored waveforms), per-channel verdicts, and a draft interim fcl.
  plotting/           one-off plotting / ROOT-macro analysis scripts (geometry, PE maps, timing)

docs/
  pdvd_pds_findings.md         distilled ProtoDUNE-VD PDS findings (read this first)
  pdhd_pds_session_summary.md  ProtoDUNE-HD PDS reco/deconvolution session summary
```

See **`docs/pdvd_pds_findings.md`** for the ProtoDUNE-VD findings summary (reco, geometry,
readout modes, channel quality, the flash-finder defect, and the raw-light handoff).

---

## PDVD quick start

**1. Decode raw light** (raw HDF5 → art file with `raw::OpDetWaveform`, tag `pdvddaphne:daq`):
```bash
IND=/path/to/raw_hdf5_dir  bash pdvd/scripts/run_pdvd_pdsraw.sh
```
Single file: `lar -c pdvd/fcl/pdvd_pds_raw.fcl -s <raw>.hdf5 -o out_pdsraw.root [-n N]`.

**Preferred — with the trigger/charge time base** (the PDVD analog of PDHD's
`trigoff/trigger_offset`; needs `pdsoffset` built in an mrb dev area, `mrbslp`):
```bash
lar -c pdvd/fcl/pdvd_pds_raw_trigoff.fcl -s <raw>.hdf5 \
    -o <tag>_pdsraw.root -T <tag>_triglight.root [-n N]
```
Also runs `tpcrawdecoder`+`triggerrawdecoder` (products dropped from the art output;
only the per-event `triglight` tree is kept in the `-T` file) — this is what lets the
plain-ROOT file carry the charge↔light offset that Q/L matching needs.

**2. Dump to plain ROOT** (readable with uproot/ROOT, no art dependency):
```bash
bash pdvd/scripts/run_pdvd_rawwf_dump.sh
# or: python pdvd/scripts/pdvd_dump_rawwf.py <in_pdsraw.root> <out_rawwf.root> --max-events -1 \
#        [--triglight <tag>_triglight.root]
```
PDHD-style directory layout (old files had the tree at top level; the viewers read both):
`rawdump/raw_waveform` (`run, subrun, event, opchannel, opdet, x, y, z, timestamp, nsamp, adc[]`),
`flashopdet/opdet_geo` (OpDet 0–39 → x,y,z,type,name), and with `--triglight` also
`trigoff/trigger_offset` — per event: CTB beam-trigger time (`tc_us`), per-crate charge
window starts (`charge_tde_us`/`charge_bde_us`), light window start (`fs_t0_us`), and
`offset_*_us = charge_start − light_fullstream_start`, all on the 40-bit-masked DTS-µs
clock of the `timestamp` branch. NB unlike PDHD's `trigoff` (whose `offset_us` is
*trigger−charge*, ~250–282 µs, for trigger-referenced reco'd light), the PDVD offsets are
*charge−light* (~2.1–2.5 ms) because the raw-waveform timestamps are absolute. The light
full-stream window is trigger-locked to ±0.3 µs, but the **charge window floats by
±15 µs event-to-event** (and TDE/BDE start up to 32 µs apart) — use the per-event,
per-crate offset, not a run constant.

**3. View** (laptop: needs `numpy`, `matplotlib`, `uproot`; the maps default to `pdvd/maps/`):
```bash
python pdvd/viewer/pdvd_raw_viewer.py <…_rawwf.root>
```
Two OpDet maps (Side X-Z, Top Y-Z) colored by raw amplitude; click a PD for its waveform(s)
(click again to cycle overlapping PDs); ←/→ step events, ↑/↓ ±10, `t` toggles the self-trigger
waveform display (overlay-by-sample vs spread-by-timestamp). Headless: `--event N --out ev.png`.

**4. Flashes → plain ROOT** (needs the **fixed** finder — build the patched `duneopdet` in an mrb
dev area, see `studies/pdvd_flash_finder/`, then `source vddev/localProducts*/setup; mrbslp`):
```bash
DEV=/path/to/vddev  bash pdvd/scripts/run_pdvd_flash.sh          # raw HDF5 -> <tag>_flash.root
# per file: lar -c pdvd/fcl/pdvd_pds_flash.fcl -s <raw>.hdf5 -o <tag>_flashreco.root [-n N]
#           python pdvd/scripts/pdvd_dump_flash.py <tag>_flashreco.root <tag>_flash.root
```
Trees (plain ROOT, no art dependency): `flash` (per flash: time, total_pe, n_opdet, y/z center+width),
`flash_opdet` (per flash per OpDet: pe, x, y, z), `ophit` (per OpHit). All keyed by run/subrun/event.

**5. Flash viewer** (laptop: `numpy`, `matplotlib`, `uproot`; auto-finds the sibling `_rawwf.root`):
```bash
python pdvd/viewer/pdvd_flash_viewer.py <…_flash.root> [--rawwf <…_rawwf.root>]
```
Flash-by-flash: Side (X-Z) + Top (Y-Z) OpDet maps colored by each PD's PE in the flash (log
scale), with the **CRP layout overlaid** (orange; toggle `c`) — Top view shows the Y=0 CRP split
+ TPC grid, Side view the top/bottom anode planes + cathode. Click a PD for its raw waveform: the
capture whose pulse is nearest the flash, drawn on a per-capture time axis with the flash time
marked (grey + "NOT in this flash" if that PD had no PE in the flash). Decon panel is a stub (VD
reco is raw-only). ←/→ ±1 flash, ↑/↓ ±10, pg ±50, `c` CRP, `s` save. Headless: `--start N
[--opdet K] --out flash.png`.

---

## Key PDVD facts (v5 geometry)

- **40 OpDets**: 8 cathode X-ARAPUCAs (C1–C8, on the cathode, *inside* the active volume),
  8 membrane X-ARAPUCAs (M1–M8, on the ±Y walls), 24 PMTs (periphery/ends). Only the cathode
  XA sit inside the active TPC volume; the rest ring it from the boundaries (all usable for
  charge–light matching — the light pattern across all PDs encodes position).
- **Raw ADC**: baseline ≈ 2700 (X-ARAPUCA) / ≈ 8600 (PMT); saturates at 16383 (14-bit).
- **Two readout modes**: cathode X-ARAPUCAs = **full-stream** (one continuous ~468k-sample
  waveform/event); membrane X-ARAPUCAs + PMTs = **self-trigger** (many short 1024-sample
  captures/event). X-ARAPUCA pulses are slow/broad, PMT pulses fast/sharp → they need
  different deconvolution templates.
- **4 dead PMTs**: OpDet 24/27/28/34 (offline ch 3090/3120/3130/3190) — never read out.
- **No deconvolution** in VD reco (unlike PDHD): the raw waveforms are handed off for
  downstream WireCell deconvolution + charge–light matching.
- **Flash finder was broken for VD** (`OpFlashFinderVerticalDrift`, dunesw v10_21_00d00): three
  bugs (FD-scale plane thresholds, a `float` time-seed precision loss at VD timestamps, and a
  sorted-vs-original hit-index mismatch) made every flash single-PD. **Fixed** by replacing the
  clustering with a double-precision greedy time-window grouping — now multi-PD (max ~28, mean
  ~2.8 OpDets/flash at `MaximumTimeWindow=2`), matching `pdvd/flash/group_ophits.py` exactly.
  See `studies/pdvd_flash_finder/` (BUG_REPORT.md + patch). Build the patched `duneopdet` in an
  mrb dev area and run the standard reco with `mrbslp`.

## PDHD workflow

`pdhd/scripts/run_workflow.sh` runs the two-step keepup→flat-tree workflow (`dunesw v10_20_09d00`).
It uses the `pdhd/pdsoffset/` analyzer modules, which must be built in an mrb dev area first
(`mrb g`/copy the package, `mrbsetenv; mrb b`, `mrbslp`). The PDHD flat trees drive
`pdhd/viewer/flash_viewer.py`.
