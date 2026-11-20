# PDVD trigger T0 — per-event charge ↔ light time-base offset

**Answer to Q1 of the Q-L matching questions (Xin), 2026-07-10.**
Extracted directly from the raw HDF5 DAQ records of all five files on hand
(runs 039252 / 039253 / 039349, 120 events), via the PDVD decoders
(`tpcrawdecoder` = PDVDTPCReader, `triggerrawdecoder` = PDVDTriggerReader4,
`pdvddaphne` = DAPHNEReaderPDVD; dunesw v10_21_00d00).

## The deliverable

**`ql_trigger_offset.txt`** — per event (all 120 events):
`run subrun event rd_timestamp_ns tc_type n_tc tc_us charge_tde_us charge_bde_us fs_t0_us light_t0_us fs_nsamp offset_tde_us offset_bde_us`

- `offset_*_us = charge_window_start − light_fullstream_window_start`, per crate
  (TDE = top CRPs, BDE = bottom CRPs — they start up to 32 µs apart, see below).
- All `*_us` columns are in the **same domain as the rawwf `timestamp` branch**:
  DTS ticks masked to 40 bits × 0.016 µs (rollover period 17 592.186 s). So
  `light_time + offset_us` puts any light time directly on the charge time base.

Per-run summary (`triglight_summary.txt` has the full printout):

| run | trigger − light_fs_start | trigger − charge_start | **charge_start − light_fs_start** |
|---|---|---|---|
| 039252 | 5000.4 ± 0.3 µs | 2517.8 ± 8.8 µs | **2482.7 ± 8.8 µs** (2470.9–2499.0) |
| 039253 | 5000.6 ± 0.3 µs | 2512.4 ± 12.1 µs | **2488.2 ± 12.1 µs** (2469.4–2500.8) |
| 039349 | 2500.5 ± 0.3 µs | 416.8 ± 9.2 µs | **2083.7 ± 9.2 µs** (2068.2–2099.6) |

(charge_start here = TDE crate; BDE = TDE + 17 ± 9 µs, per-event value in the table.)

## Sub-question answers

**1. Is the light window at a fixed offset from the trigger?**
Yes — the light **full-stream record start is trigger-locked to ±0.3 µs**
(< 1 DAPHNE frame): trigger − fs_start = 5000.4 µs (7.5 ms records,
runs 039252/3) and 2500.5 µs (5.3 ms records, run 039349); per-run DAQ
constants. **The charge window is the one that floats**: trigger −
charge_start jitters by ±15 µs event-to-event (std 9–12 µs) — that is why a
run-level constant T can never beat ~±15 µs (≈ ±2.5 cm of drift) and why the
statistical A/C-crosser fit stalls: the per-event table removes this entirely.

**The 4 ms "outlier" (039349 evt 19549) is not real**: its directly-measured
offset is 2075.6 µs — dead center of the run band. Caution on the anchor
though: "earliest light record start" (any record) is NOT the window start —
the self-trigger streams open before the full-stream record and their earliest
capture fluctuates (fs_start − earliest_any = up to 40 µs in 039252, up to
180 µs in 039253, up to **430 µs** in 039349). Anchor light t0 on the
**earliest full-stream record** (nsamp > 100k) — that is the trigger-locked
quantity; the table gives both (`fs_t0_us`, `light_t0_us`).

**2. What sets the record lengths?**
Per-run DAQ configuration, quantized to one DAPHNE frame (64 samples):
light 468 800/468 864 samples = 7.501 ms (039252/3) and 331 264/331 328 =
5.301 ms (039349). The charge window is a *different* per-run constant, NOT
always 5 ms: RawDigit lengths are 5.000 ms in 039252/3 (9 766 samples @512 ns
BDE / 10 000 @500 ns TDE) but **3.200 ms in 039349** (6 250 / 6 400). Window
geometry (relative to trigger): 039252/3 light [−5.0, +2.5] ms, charge
[−2.52, +2.48] ms; 039349 light [−2.5, +2.8] ms, charge [−0.42, +2.78] ms —
light always covers the charge window.

**3. Beam-trigger time record?**
Yes. The TriggerCandidates in the raw data **are CTB beam triggers**:
types 15/20/22 = kCTBBeamChkvHL/HLx/HxLx (Cherenkov H·L combinations) plus a
few 29 = kCTBOffSpillSnapshot; 1–3 TCs per event. `time_candidate` is on the
DTS clock (16 ns ticks, 64-bit) — table column `tc_us` (masked to the light
domain). This is the cleanest common anchor: both the light window (±0.3 µs)
and the charge window (±15 µs) are placed relative to it.

## PDHD vs PDVD `trigger_offset` — and the Q/L-matching recipe

The PDHD `trigoff/trigger_offset` and the PDVD one answer the same question —
"how do I put light times on the charge waveform's time axis?" — but through
different routes, because the two files hand off different processing levels:

- **PDHD** files carry *reconstructed* light (deconvolution + OpHit/OpFlash ran in
  art), so all light times are already **trigger-relative** (DetectorClocks). The
  only missing number is where the charge window sits relative to the trigger;
  PDHD's `offset_us = TC_time − RDTimeStamp` (trigger − charge_start, ~250–282 µs)
  is exactly that refinement over the nominal 250 µs. Usage there:
  `t_on_charge_axis = t_flash(trigger-rel.) + offset_us`.
- **PDVD** files carry *raw* light with **absolute** DAQ timestamps (40-bit-masked
  DTS µs) — no reco, no trigger re-basing. So the tree carries the direct map
  between the two windows: `offset_{tde,bde}_us = charge_window_start −
  light_fullstream_start` (~2.1–2.5 ms — big only because the PDVD DAQ opens the
  light window 2.5–5 ms before the trigger; nothing anomalous). The trigger time
  `tc_us` is also included, so the PDHD-style quantity is recoverable as
  `tc_us − charge_*_us` if ever wanted.

**Recipe (PDVD):** for a light feature at absolute time `t_light` (µs, same domain
as the `timestamp` branch — e.g. `timestamp + i×0.016` for full-stream sample `i`):

1. Light time relative to the light window: `t̃ = t_light − fs_t0_us`
   (use the **full-stream window start** as light t=0 — it is trigger-locked to
   ±0.3 µs; "earliest record" is not).
2. Time on the charge axis (µs from that crate's charge-window start):
   `t_chg = t̃ − offset_X_us`, with `X = tde` for top-CRP channels, `bde` for
   bottom (the two crates start up to 32 µs apart — don't mix them).
3. Charge sample index: `s = t_chg / 0.512` (BDE, 512 ns/sample) or `/ 0.500`
   (TDE). A deposit that made the flash at `t_chg` and was recorded at sample
   `s_hit` has drift time `Δt = s_hit·pitch − t_chg`, and `x = v_drift · Δt`
   (sign per drift volume).

Use the **per-event** values: the charge window placement jitters by ±15 µs
event-to-event (≈ ±2.5 cm of drift at v≈1.6 mm/µs) even though the light window
is trigger-locked; a run constant cannot remove that. If computing time
differences from raw numbers yourself, wrap at the 40-bit rollover
(2⁴⁰ × 16 ns = 17 592.186 s).

## The suspected 8–16 µs charge-side offset — candidates and how to tell them apart

Four independent effects in this timing chain produce shifts of exactly that size.
Measured magnitudes (per event, from the triglight trees):

| # | candidate | magnitude | signature |
|---|---|---|---|
| A | **light-anchor mismatch**: Xin's light t=0 is the *earliest-any-record* start (`dump_light_t0.py` = our `light_t0_us`), but `offset_*_us` is defined against the *full-stream* start (`fs_t0_us`). | fs_t0 − light_t0 = **+12.3 ± 9.0 µs (run 039252)**, +28.6 ± 43.2 (039253), **+260–277 ± 90 (039349)** | run-dependent mean; identical for both crates; constant vs drift. If the residual is ~12 µs on 039252 but ~0.3 ms on 039349, this is it. |
| B | **crate mismatch**: one offset column applied to all channels. | TDE−BDE = **−17.8 ± 8.9 µs** (039252; similar in all runs; range −32…0) | opposite shifts for top-CRP vs bottom-CRP channels; varies event to event. |
| C | **run-constant instead of per-event offset**. | 0 mean, **±9–12 µs (std) event scatter** (peak-to-peak ~30 µs) | no net bias; residual varies event-by-event, correlated with `tc_us − charge_*_us`. |
| D | **TDE sample-pitch assumption**: TDE is 500 ns/sample, BDE 512 ns; a common-tick frame or a 512 ns assumption skews TDE times by 2.4 % of the time-into-window. | 0 → +77 µs across the 3.2 ms window; = 8–16 µs at 0.33–0.67 ms into the window | linear in sample index; top-CRP channels only. |

Discriminating plot: QL time residual (i) per run, (ii) split top vs bottom CRP,
(iii) vs sample index, (iv) event-by-event. Each candidate has a unique pattern.

**Crate map verified from data + geometry (2026-07-13)**: the ns-stamped RDTimeStamp
family covers offline channels **6144–12287**, whose wires sit in TPCs at
**X = +172 cm → top CRPs → TDE** (`charge_tde_us` / `offset_top`); the tick-stamped
family covers **0–6143** at **X = −172 cm → bottom → BDE** (`charge_bde_us` /
`offset_bot`). The tree's column labels are correct. Audit of the provided numbers:
BDE tick arithmetic verified in the decoder source; TDE stamps exactly 32-µs
frame-aligned in all 120 events (the decoder's latent `start_tick*500/16` unit quirk
is dormant — start_tick ≡ 0 throughout); fs window trigger-locked ±0.3 µs against
the CTB TCs; within-crate spread exactly 0; stored-value roundoff ~2×10⁻⁶ µs.
No crate-symmetric µs-level error found in the provided quantities.

**Status after reviewing the actual light chain** (`wcp-porting-img/pdvd/run_light_evt.sh`
@ 62c7176 + `PDVDOpWaveformSource.cxx`, 2026-07-13): **candidate A is excluded** — the
WCT light frame's tick origin is the min-over-ALL-records t0 (population instances
deliberately share it), every record is placed at `start − t0` (cathode full-stream
correctly sits `fs_t0 − light_t0` into the frame), and the run script computes the
offsets against the same t0, cross-checked against the tree per event. The anchor
cancels exactly. Remaining suspects, in order: (1) the anode-index ↔ crate assignment
in `[offset_bot, offset_top][idx]` (flip = ±17.8 ± 9 µs, crate-antisymmetric);
(2) a constant shift inside the charge SP chain (field-response time offset /
tick trimming — run-independent; charge input itself is art RawDigits, so tick 0 =
RDTimeStamp at the source); (3) TDE 500 ns vs 512 ns pitch in the charge frame
(drift-position slope); (4) the −64-tick snippet-timestamp semantics (1.024 µs,
inter-population only — worth one DAPHNE-expert confirmation).

Fixes: (A) anchor light times on `fs_t0_us` (all 16 full-stream records share ONE
start per event — measured spread exactly 0), or equivalently use
`offset_X_us + (fs_t0_us − light_t0_us)` when keeping the earliest-record anchor —
both columns are in `trigger_offset`; (B) use `offset_tde_us` for top-CRP channels
and `offset_bde_us` for bottom; (C) always per-event values; (D) convert TDE
samples with 0.500 µs, BDE with 0.512 µs before any common-grid resampling.

## Gotchas found on the way (also upstream-worthy)

- **`raw::RDTimeStamp` units are inconsistent in the PDVD decoder**: the 6 144
  TDE channels carry ns-since-epoch (exactly 32 µs = 64×500 ns frame-aligned),
  the 6 144 BDE channels carry 16-ns DTS ticks (factor 16 apart). Within each
  crate all channels share one window start exactly; **between crates the
  starts differ by 0–32 µs** (each starts on its own frame boundary), so
  "charge window start" is per-crate — the table carries both columns.
- The DAPHNE decoder masks timestamps to 40 bits before converting to µs
  (`DAPHNEInterface3_tool.cc`) — rollover every ~4.9 h; all comparisons here
  are done in that domain.
- **Flash-finder warning** (separate issue, full report available): the stock
  `OpFlashFinderVerticalDrift` in dunesw produces corrupted, single-PD flashes
  on PDVD (3 bugs; we have a validated patched module). Irrelevant to raw-
  waveform work, but if any `t_flash` is ever taken from standard PDVD reco
  `recob::OpFlash`, it must come from the patched finder.

## Reproduction

`PDVDTriggerLightAna_module.cc` (analyzer, built in the pdsoffset package of
the vddev mrb area on wcgpu1), `pdvd_triglight.fcl` (decoders only, no reco,
~40 s/28-event file), `analyze_triglight.py` (table + summaries). Dev area:
`/nfs/data/1/jjo/tmp/pdvd_flash_validation/vddev`; outputs incl. per-file
TTrees: `/nfs/data/1/jjo/tmp/pdvd_flash_validation/out/triglight/`.
