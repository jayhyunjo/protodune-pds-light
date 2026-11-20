# PDHD SPE-template comparison: per-channel v1/v0 vs NP04 vendor-average

**Claim to support:** on a majority of PDHD PDS channels the 2024 NP04
vendor-average SPE templates give better deconvolved waveforms than the
Jun 2025 per-channel v1 templates (and the Nov 2024 v0 ones). This study
produces the per-channel list + supporting plots, and a draft interim fcl.

## Data & method

- 4 runs (27305, 27980, 28084, 29107), flat `_final.root` files
  (`/nfs/data/1/jjo/data/PDHD/`, mirrors of the workflow output). They contain,
  per raw self-trigger record, the **same raw waveform deconvolved with v1**
  (`decodump`, from the production keepup) **and v0** (`decodumpv0`).
- The NP04 vendor-average deconvolution was produced here with **an exact
  numpy port of the LArSoft `Deconvolution` module** (`pdhd_deco.py`),
  configured identically to `protodunehd_deconvolution` (Wiener filter with
  the run-27950 FFT noise templates, AutoScale, 1.5 MHz Gauss post-filter,
  post-BL correction, `IgnoreChannels`), swapping only the SPE kernels —
  i.e. exactly what the `opdecnp04` producer does in LArSoft.
  - **Port validation** (`validate_pydeco.py`): re-deconvolving all ~234k
    records with v1 and v0 kernels reproduces the stored LArSoft waveforms to
    max |diff| ≤ 3e-8 (float32 round-off) on all 4 runs. The NP04 output is
    therefore directly comparable to the stored trees.
- **Pulse selection** (170,010 of 233,768 matched records): raw amplitude
  ≥ 25 ADC (≈ 2–3 PE), no ADC-bottom clipping, deco peak at tick 40–700
  (≥ ~5 µs of tail in the record). Records from events skipped by the keepup
  fembfilter are excluded (no v1 reference).
- **Per-record metrics** on each deconvolved waveform (peak = prompt max):
  - `u_ratio` — min of the tail after the peak / peak ("undershoot depth");
  - `negfrac` — integrated negative area of the tail / positive prompt area
    (tick −10..+40 around the peak) — the PE-integral bias;
  - late-baseline mean (last 2 µs) / peak.
  Per channel: median over selected pulses, all runs combined; per-run medians
  for consistency.

## Results

- **Undershoot depth:** NP04 better by > 0.05·peak, consistently in every run,
  on **27 channels** ("vendor-better"); the worst are opch 60, 50, 40 (FBK,
  APA3-x0 positions) with median undershoot −0.67/−0.56/−0.32 of peak under v1
  vs ≈ −0.09 under NP04, and the HPK block 0,1,10,11,20,21,30,41,… at −0.28…−0.10
  vs ≈ −0.05. 85 channels comparable; **1 channel (105, FBK) where v1 is
  better** (NP04's average shape leaves a local −0.12 dip).
- **Integrated tail:** this is the dominant effect. Median over channels of
  median `negfrac`: **v1 = 1.09** (the undershoot integrates to *more than
  the prompt pulse* and does not recover within the 16 µs record) vs
  **NP04 = 0.36**; v1 worse by > 0.1 on **93 of 113 channels**.
- **v0 ≈ v1** everywhere (the tail pathology was not introduced in v1; v1 is
  a re-scaled/re-fit of the same extraction — kernel shapes differ ≤ ~15 %).
- **The flagged channels are not random** (`fig_apa_map.png`): the top four
  PD rows of *every* APA face (opch ≡ 0–3 mod 10) are systematically flagged,
  plus whole columns on APA4/APA3 — pointing to a systematic problem in the
  v1 per-channel extraction for those positions (e.g. calibration-light
  exposure), not to statistical fit quality.
- **Mechanism (template-level cross-check, `kernel_metrics.py`):** the v1/v0
  kernels are not DC-balanced: median net-area/positive-area **+0.18**, up to
  **+0.59** (93/113 above +0.1). The NP04 vendor averages are DC-balanced
  (≈ 0.00). The DAPHNE front-end response is AC-coupled — the true per-PE
  response integrates to ≈ 0 — so a kernel with large positive net area
  under-models the SPE undershoot lobe (visible directly in
  `fig_kernels_worst.png`: v1/v0 lobes reach ≈ −0.15 of peak where NP04
  reaches ≈ −0.30). Dividing the raw waveform by such a kernel leaves the
  unmodeled part of the real undershoot in every deconvolved pulse. The
  measured per-channel improvement correlates directly with the v1 kernel's
  net area (`fig_mechanism.png`).

## Baseline / pedestal behaviour (follow-up)

The pre-pulse "baseline" of the deconvolved waveform is also
template-dependent (first seen on opdet 30). In absolute record time
(`plot_baseline_diag.py`, `fig_baseline_ch030.png` / `ch060.png`):

- All templates are pinned to ~0 in ticks 0–19 by the module's
  `ApplyPostBLCorrection` (that window is genuinely pre-pulse for
  trigger-position records, so the pinning itself is unbiased).
- **v1/v0 rise ~25 ticks (~0.4 µs) before the raw pulse even starts** — an
  acausal Wiener shoulder from kernel shape mismatch. Median pre-pulse level
  (ticks 25–45, trigger-position pulses, 151k records): **v1 +1.9 % of peak
  vs NP04 +0.7 %**; amplitude-dependent (v1: +11 % of peak for sub-PE pulses,
  +2.4 % for bright ones), so fixed hit thresholds see a
  template- and amplitude-dependent pedestal.
- **The end-of-record "recovery" of the v1/v0 undershoot is not physical**:
  the deconvolution is a circular FFT, so the record end is forced back to
  the (pinned) record-start level. Median end level: v1 up to −3.5 % of peak,
  NP04 within −0.5 %. Do not read the last ~2 µs of a v1 deco record as
  baseline recovery.
- Included in the evaluation (`add_baseline_metrics.py`,
  `analyze_baseline.py` → `baseline_summary.csv`, `fig_baseline.png`):
  the pre-pulse metric **flips no verdicts** — the 10 channels where v1's
  pre-level is worse by > 2 % of peak are all already NP04-recommended, and
  no NP04-recommended channel is worse on it. If anything the main-table
  numbers are conservative for v1: the circularity artifact truncates the
  measured tail-negative area.

## Recommendation (interim config)

Switch **67 channels** to the vendor-average NP04 kernels, keep v1 on the 46
channels where it is comparable or better (criterion: undershoot-depth
improvement > 0.05 consistent across runs, OR integrated-tail improvement
> 0.5 without degrading undershoot depth):

```
0,1,2,4,5,6,7,8,9,10,11,12,13,15,16,17,18,19,20,21,22,23,28,29,30,31,32,33,
40,41,42,43,50,51,52,53,59,60,61,62,63,64,69,70,71,72,73,74,76,78,79,
80,81,82,83,90,91,92,93,100,101,102,103,110,111,112,113
```

Draft fcl: `protodunehd_template_list_v1_np04mix.fcl` (generated by
`make_fcl.py`), a drop-in replacement for `protodunehd_template_list_v1` in
`protodunehd_deconvolution` — same noise templates, IgnoreChannels and filter
settings, only the SPE kernel map changes. If a simpler config is preferred,
the pure vendor table (`protodunehd_pds_channels_mc` applied to data, as
`opdecnp04` does) is better than v1 on the integrated-tail metric for 93/113
channels and worse on undershoot depth only on a handful of FBK channels
(105, 67, 77, 57, 47 — by ≤ 0.06·peak).

## Files

| file | content |
|---|---|
| `channel_verdicts.csv` | per-channel metrics, verdicts, recommendation |
| `kernel_metrics.csv` | per-kernel net area / tail shape (v0/v1/NP04) |
| `protodunehd_template_list_v1_np04mix.fcl` | draft interim template list |
| `pdhd_deco.py` | validated numpy port of the Deconvolution module |
| `validate_pydeco.py` | port-vs-stored-trees validation |
| `make_np04_metrics.py` | NP04 deco production + per-record metrics |
| `aggregate_verdicts.py` | selection, per-channel aggregation, verdicts |
| `kernel_metrics.py`, `build_median_pulses.py`, `make_plots.py`, `make_fcl.py` | cross-check, evidence plots, fcl generator |
| `add_baseline_metrics.py`, `analyze_baseline.py`, `plot_baseline_diag.py` | pre-pulse/record-end baseline follow-up |
| `baseline_summary.csv` | per-channel pre-pulse + end levels per template |
| `plots/fig_baseline.png`, `plots/fig_baseline_ch{030,060}.png` | baseline evidence |
| `plots/fig_summary_scatter.png` | per-channel v1-vs-NP04, both metrics |
| `plots/fig_channel_profile.png` | improvement vs channel number |
| `plots/fig_mechanism.png` | kernel DC-balance ↔ measured improvement |
| `plots/fig_kernels_worst.png` | the offending kernels |
| `plots/fig_apa_map.png` | recommendation on the PD layout |
| `plots/fig_overlays_apa{4,3,2}.png` | median-pulse contact sheets |
| `plots/channel_overlays/ch###.png` | per-channel evidence (all 113) |

Derived waveform/metric data: `/nfs/data/1/jjo/data/PDHD/spe_template_cmp/`.

## Caveats

- This compares SPE templates **within the LArSoft `Deconvolution` module**
  (Wiener + post-filter). It does not reproduce WCT `OpDecon` numerically
  (same kernels, different filter), but the kernel DC-balance mechanism is
  filter-independent.
- Metrics are waveform-level. OpHit/OpFlash-level impact (PE totals, fake
  hits on the undershoot recovery) was not re-run here; the integrated-tail
  metric is the direct proxy for the PE-integral bias.
- Saturated pulses (ADC bottom) are excluded; templates are anyway not
  expected to describe clipped pulses.
- The per-channel v1 set remains the right long-term goal — with kernels
  extracted so that the tail is faithful (net area ≈ 0), it should beat the
  vendor average on channels like 105 where the average shape visibly
  mismatches.
