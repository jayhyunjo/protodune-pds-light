# PDVD flash-finder bug: report, slides, and validation plots

The **write-up** for the `OpFlashFinderVerticalDrift` single-PD-flash defect.
The **code** — `BUG_REPORT.md`, the patched module, the diff against
dunesw v10_21_00d00, and the diagnosis fcls — lives next door in
[`../pdvd_flash_finder/`](../pdvd_flash_finder/). Read that one for the fix;
read this one for the measurement and the presentation.

Imported 2026-11-20 from `~/Work/pdvd-flashfinder-report`, where it had been
sitting apart from the study it documents.

| file | what it is |
|---|---|
| `report.md` / `report.html` | the full report (J. Jo, 2026-07-09). The HTML embeds all 7 figures as base64, so it is self-contained and needs nothing from `plots/`. |
| `slides.pptx` | 10-slide version |
| `equivalence_wcgpu1_vs_dunegpvm.md` | validation that the wcgpu1 and dunegpvm builds agree — cited from `~/Work/protodune-bsm/PLAN.md` |
| `plot_all.py` | regenerates the figures |
| `build_slides.py` | builds `slides.pptx` from the report |
| `stats.json` | the headline numbers |
| `plots/` | the 7 PNGs — **untracked** by the repo's `.gitignore` binary policy; regenerable with `plot_all.py`, and already embedded in `report.html` |

## The result in one table

28 events of run 039349, `protodunevd_v5`:

| build | flashes | mean mult | max mult | multi-PD |
|---|---|---|---|---|
| stock v10_21_00d00 | 160,419 | 1.00004 | 2 | 0.004 % |
| bugs 1+2 fixed only | 43,919 | 1.74 | 5 | 72.6 % |
| **full fix (patched)** | **43,763** | **2.91** | **27** | **72.8 %** |

Three independent bugs: FD-scale geometry thresholds that never match PDVD, a
`float` cluster-seed time that cannot represent PDVD timestamps to better than
~1024 ticks, and — decisively — a sorted-vs-original hit-index mismatch that
assigned the wrong hits to each flash.

## Regenerating

`plot_all.py` reads `BASE = /nfs/data/1/jjo/tmp/pdvd_flash_validation/out`
(the validation outputs) and resolves `REPO` from its own location, so it
works from anywhere inside the repo. If the NFS staging area has been cleaned,
the figures cannot be rebuilt without rerunning the validation chain — the
embedded copies in `report.html` are then the record.
