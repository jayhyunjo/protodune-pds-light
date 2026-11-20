# PDVD trigger T0: the per-event charge ↔ light time-base offset

What Q/L matching needs in order to put charge and light on the same clock,
measured per event from the raw DAQ rather than assumed as a run constant.

Imported 2026-11-20 from `~/Work/pdvd-ql-trigger-t0`. The analyzer module this
study is built on is **not** duplicated here — it is the repo's own
[`pdhd/pdsoffset/pdsoffset/PDVDTriggerLightAna_module.cc`](../../pdhd/pdsoffset/pdsoffset/PDVDTriggerLightAna_module.cc)
(the loose copy was byte-identical, md5 `63499d89…`, and was dropped so there
is one canonical source).

| file | what it is |
|---|---|
| `ANSWER.md` | the deliverable: the offset definition, sub-question answers, the PDHD-vs-PDVD `trigger_offset` comparison and Q/L recipe, the suspected 8–16 µs charge-side offset with candidate causes, gotchas, and reproduction steps |
| `ANSWER-Q2-Q4.md` | cathode X-ARAPUCA SPE normalization (Q2); Ar vs Xe measured from the data, and the runs are **not** all the same (Q3); smaller items (Q4) |
| `ql_trigger_offset.txt` | the per-event offset table, 120 events |
| `triglight_summary.txt` | per-run summary statistics |
| `analyze_triglight.py` | produces both from the `triglight` tree |
| `pdvd_triglight.fcl` | the lean variant used here — decoders only, no art output, only the `-T` triglight tree. The repo's `pdvd/fcl/pdvd_pds_raw_trigoff.fcl` is the full version that also writes the art file. |

## The headline

The light full-stream window is **trigger-locked to ±0.3 µs**, but the charge
window **floats by ±15 µs event-to-event**, and the TDE and BDE crates start up
to 32 µs apart. So the charge↔light offset must be taken per event and per
crate — a run constant is wrong by more than the matching tolerance.

Measured on run 39252 (18 events):

| quantity | mean (µs) | std |
|---|---|---|
| trigger − light_fs_start | 5000.428 | 0.292 |
| trigger − charge_start | 2517.758 | 8.827 |
| **charge_start − light_fs_start** (the offset) | **2482.670** | **8.813** |

Note the sign convention differs from PDHD: PDHD's `offset_us` is
*trigger − charge* (~250–282 µs, for trigger-referenced reco'd light), while
the PDVD offsets are *charge − light* (~2.1–2.5 ms) because the raw-waveform
timestamps are absolute. See the README's step-2 section for the full
definition on the 40-bit-masked DTS-µs clock.
