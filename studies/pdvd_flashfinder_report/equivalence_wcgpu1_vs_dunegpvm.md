# wcgpu1 (BNL) vs dunegpvm (FNAL) — environment equivalence validation

**2026-07-09.** Question: does the SL7-container + cvmfs setup on wcgpu1 produce the *same
physics output* as the same workflows run on dunegpvm? Every dunegpvm-produced reference
available in/alongside the `protodune-pds-light` repo was reproduced on wcgpu1 and compared.

| # | check | dunegpvm reference | wcgpu1 result | verdict |
|---|-------|--------------------|---------------|---------|
| 1 | PDVD raw workflow (`pdvd_pds_raw.fcl` + `pdvd_dump_rawwf.py`), run 39252, 18 events | `_rawwf.root` produced at FNAL (`/exp/dune/data/...`, copied to `/nfs/data/1/jjo/data/PDVD/`) | 43,808 waveforms, all 10 scalar branches **and every ADC sample of all 43,808 waveforms identical** | **bit-identical** |
| 2 | PDVD fixed flash finder, run 39252, 2 events (BUG_REPORT.md table) | 4,302 flashes, max mult 28, mean 2.77, 70 % multi-PD | 4,302 flashes, max 28, mean 2.77, 70 % | **exact match** |
| 3 | `protodunevd_v5` geometry (`geo::DumpGeometry`) | `pdvd/maps/pdvd_v5_opdet_positions.csv` (derived on dunegpvm) | all 40 OpDet centres, max Δ = 0 cm | **identical** |
| 4 | PDHD keepup → flat-tree workflow (`dunesw v10_20_09d00` + `pdsoffset`), run 27305, events 150+154 | `_final.root` produced at FNAL (`/nfs/data/1/jjo/data/PDHD/`) | all 11 flat trees (raw + deconvolved waveforms, OpHit/flash trees, flash↔hit matches, trigger offsets, OpDet geometry — 3,027 entries) **identical branch by branch** | **identical** |

## Why this is a strong test

- Check 1 exercises the **entire I/O + decode stack** end to end: cvmfs products, the SL7
  container runtime, HDF5 reading (`DAPHNEReaderPDVD`), art event processing, geometry/channel
  maps, pyROOT dumping — one differing bit anywhere would show up in the 112M-sample ADC
  comparison. It came out bit-identical.
- Check 2 exercises the **mrb dev-area build path** (clone duneopdet at tag, patch, build with
  the container toolchain) plus ophit+opflash reco — the wcgpu1-built binary reproduces the
  dunegpvm-built binary's output exactly, including float-accumulation-sensitive quantities
  (mean multiplicity to 2 decimals, per-flash grouping).
- Check 3 pins the geometry description itself.
- Check 4 (PDHD) adds the other detector, an older dunesw release (v10_20_09d00), the full
  charge keepup reco (TPC decode + dataprep + deconvolution), and a second custom-built
  package (`pdsoffset`) — and every derived quantity, including the deconvolved waveforms,
  came out identical for the overlapping events.

**Conclusion: the wcgpu1 SL7-container environment is output-equivalent to dunegpvm** for
both the PDVD and PDHD workflows in this repo — same decoded bits, same reco results, same
geometry, for both cvmfs-released and locally-built (mrb) code.

## Reproduction

Scripts in `/nfs/data/1/jjo/tmp/pdvd_flash_validation/`: `run_raw.sh` (check 1),
`run_flash_variant.sh local fixed_39252_n2 ... 2` (check 2), the geometry dump in
`out/geom/` (check 3), `build_offdev.sh` + `run_pdhd.sh` (check 4), and the comparison
scripts `compare_pdhd.py` (+ inline snippets recorded in the session log). Raw HDF5 inputs:
`/nfs/data/1/xning/container/dune_data/hdf5/{PDVD,PDHD}/`.
