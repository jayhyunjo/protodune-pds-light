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
            dump_protodunevd_geometry.fcl geo::DumpGeometry of protodunevd_v5 (OpDet positions)
  scripts/  run_pdvd_pdsraw.sh            batch: raw HDF5 -> <tag>_pdsraw.root (art)
            pdvd_dump_rawwf.py            art raw::OpDetWaveform -> PLAIN-ROOT raw_waveform tree
            run_pdvd_rawwf_dump.sh        batch wrapper for the dump
  viewer/   pdvd_raw_viewer.py            interactive raw-light event/waveform viewer
  flash/    group_ophits.py               custom double-precision OpHit->flash grouping (multi-PD
                                          flashes; replaces the buggy OpFlashFinderVerticalDrift).
                                          Input from fcl/pdvd_pds_ophit.fcl (pdvddaphne+ophit+OpFlashAna)
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
  pdvd_flash_finder/  fcls used to diagnose the OpFlashFinderVerticalDrift single-PD-flash bug
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

**2. Dump to plain ROOT** (`raw_waveform` tree; readable with uproot/ROOT, no art dependency):
```bash
bash pdvd/scripts/run_pdvd_rawwf_dump.sh
# or: python pdvd/scripts/pdvd_dump_rawwf.py <in_pdsraw.root> <out_rawwf.root> --max-events -1
```
`raw_waveform` branches: `run, subrun, event, opchannel, opdet, x, y, z, timestamp, nsamp, adc[]`.

**3. View** (laptop: needs `numpy`, `matplotlib`, `uproot`; the maps default to `pdvd/maps/`):
```bash
python pdvd/viewer/pdvd_raw_viewer.py <…_rawwf.root>
```
Two OpDet maps (Side X-Z, Top Y-Z) colored by raw amplitude; click a PD for its waveform(s)
(click again to cycle overlapping PDs); ←/→ step events, ↑/↓ ±10, `t` toggles the self-trigger
waveform display (overlay-by-sample vs spread-by-timestamp). Headless: `--event N --out ev.png`.

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
- **Flash finder is broken for VD** (`OpFlashFinderVerticalDrift`): FD-scale plane thresholds
  + a clustering issue mean it fails to group coincident hits → every flash is single-PD.
  See `studies/pdvd_flash_finder/`. (Charge–light matching therefore needs a fixed finder or a
  custom time-window OpHit grouping — TODO.)

## PDHD workflow

`pdhd/scripts/run_workflow.sh` runs the two-step keepup→flat-tree workflow (`dunesw v10_20_09d00`).
It uses the `pdhd/pdsoffset/` analyzer modules, which must be built in an mrb dev area first
(`mrb g`/copy the package, `mrbsetenv; mrb b`, `mrbslp`). The PDHD flat trees drive
`pdhd/viewer/flash_viewer.py`.
