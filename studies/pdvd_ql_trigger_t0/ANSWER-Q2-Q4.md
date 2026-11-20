# PDVD Q-L matching — answers/findings for Q2–Q4

**2026-07-10.** What could be established from the data and dunesw on wcgpu1, and what
must go to the PDS consortium / run coordination. Companion to `ANSWER.md` (Q1).

## Q2 — Cathode X-ARAPUCA SPE normalization

**What we can confirm locally:**
- **There is no per-channel DAPHNE gain/SPE calibration anywhere in dunesw
  v10_21_00d00**: the only PE scale in the reco chain is the flat `SPEArea`
  in the OpHit config (one number for all 40 OpDets), and the official channel map
  (`dunecore/config_data/PDVD_PDS_Mapping_v09162025.json`) carries `eff_Ar`/`eff_Xe`
  but **no gain fields**. So Xin's need is real: nothing official to consume offline.
- The **hardware asymmetry is real by design**: the cathode modules sit on the HV
  plane and are read out via Power-over-Fiber + analog-signal-over-fiber, while the
  membrane modules use conventional (copper) readout to DAPHNE — different front-end,
  different bandwidth. Xin's own shape measurement (cathode FWHM ≈ 0.2 µs vs membrane
  0.35–0.9 µs) is the data-level proof. **Transferring the membrane 1-PE amplitude to
  the cathode is NOT safe**; his area-based transfer as an interim is the right
  workaround, but the absolute scale needs a cathode-specific measurement.
- **The exact PE formula in the standard chain** (no deconvolution on VD): `ophit`
  (`OpHitFinder`, config `protodunevd_ophit` in `duneopdet/fcl/opticaldetectormodules_dune.fcl`)
  runs the `SiPM` pulse finder directly on the raw waveform (pedestal: "Edges",
  3 samples front/tail; threshold 10 ADC; MinWidth 60 samples) and converts with
  `PhotonCalibratorStandard` (larana): **PE = pulse_area / SPEArea + SPEShift
  = area/410 + 0.43**, where area = Σ(ADC−ped) in ADC·ticks (16 ns ticks;
  1 PE = 410 ADC·ticks = 6.56 ADC·µs). `SPESize` (0.451 ADC/PE, amplitude-based)
  is unused since `AreaToPE: true`. Flat for all 40 OpDets, `UseCalibrator: false`.
  **Provenance: 410/0.451 are copied verbatim from `protodune_ophit` (ProtoDUNE-SP),
  whose own comment reads "These calib values would be for MC only"** — the PDVD PE
  scale is a placeholder from another detector's MC, so Xin's SPE effort is not
  duplicating any existing calibration.
- **UPDATE — per-channel PDVD SPE constants DO exist (preliminary), from duneopdet
  v10_21_02d00 onwards**: `PhotonCalibratorDUNE.fcl`
  (github.com/DUNE/duneopdet, imported from Laura Paulucci's `lp_pdvdcalibrator`
  branch, fcl'd by V. Pec 2026-02) defines period-keyed per-channel `SPESizes` for
  all 56 offline channels: `protodunevd_photoncalibrator_config_beam_v100` (early,
  "DO NOT USE"), `_v200` (Jul 10–16, "DO NOT USE"), `_v300` (Aug 2–8), and
  `_v400_1`/`_v400_2` (**Aug 10 onwards — the config that covers runs
  039252/039253/039349**). `_v400_2` has **dedicated cathode values (290–794
  ADC·ticks/PE, from Ajib's low-PE background study,
  indico.fnal.gov/event/69308 contribution 333039) distinct from membrane values
  (86–236, from Henrique's "finger plots", np02-config-v4.0.0.csv in
  waffles/np02_data/calibration_data)** — cathode ≈ 2–4× membrane, consistent with
  the different PoF front-end. Caveats in the file itself: membrane values "most
  likely underestimated by a factor 2–3"; all 24 PMT values are placeholders (100).
  NOT applied by default: no fcl wires the service in and `protodunevd_ophit`
  keeps `UseCalibrator: false` — to use it:
  `services.PhotonCalibratorService: @local::protodunevd_photoncalibrator_config_beam_v400_2`
  + `physics.producers.ophit.UseCalibrator: true` (per-channel PE = area/SPESizes[ch];
  bad channels → PE = 0).
- **For the experts** (PDS consortium / DAPHNE team — concretely: Laura Paulucci
  (calibrator), Henrique (membrane finger plots), Ajib (cathode study), and the
  waffles calibration-data maintainers): (a) final (non-"factor 2–3") SPE fits for
  the v400 period, especially the PoF cathode channels; (b) whether dedicated
  low-light / LED runs exist where the cathode 1-PE peak is resolved (the DAPHNE
  self-trigger threshold in physics runs sits at/above 1 PE there, so physics data
  alone cannot resolve it — confirmed by our data); (c) the PoF front-end
  transimpedance/gain numbers for an electronics-based cross-check.

## Q3 — Argon or Xenon? **The runs are NOT all the same — measured from the data**

Two independent checks on the raw waveforms we processed:

1. **Scintillation slow component** (average TPB-PMT self-trigger waveform,
   amplitude-normalized, tail fit; PEN PMTs cross-check, two fit windows):

   | run | date | tail τ_eff | verdict |
   |---|---|---|---|
   | 039252 | Aug 30 | **0.6–1.0 µs** (TPB & PEN consistent) | slow component strongly quenched/transferred — **Xe-doped-like** |
   | 039253 | Aug 30 | **0.6–0.7 µs** | same |
   | 039349 | Sep 09 | **1.5–2.0 µs** (late fits pile-up-limited) | **Ar-like** (triplet ≈ 1.4–1.6 µs + pile-up) |

2. **Ar-blind channel activity**: OpDet 13 (M7, `wls=PTP+Q`, `eff_Ar=0`, `eff_Xe=0.03`
   in the official map) is ACTIVE in all runs (~180–260 captures/event, real pulses,
   ~½ the amplitude of a normal membrane XA). OpDet 33 (`wls=NONE`, blind to both)
   sees only a low rate (4–14/event; plausibly Cherenkov in the PMT glass). ch 13's
   activity in the *Ar-like* run 39349 suggests its `eff_Ar=0` is not physically
   exact (e.g. it may see wavelength-shifted light from neighboring modules), so the
   time profile is the more reliable discriminator.

**Implication for Q/L matching: the photon model likely must be chosen PER RUN —
039252/039253 look Xe-doped, 039349 looks pure-Ar.** A single 128 nm (Ar) config for
all three is inconsistent with the measured time profiles. Please confirm against the
NP02 run log / slow-controls (doping history between Aug 30 and Sep 9, 2025) — the
data cannot tell 10 ppm Xe from some other strong quencher, only that the light time
structure differs decisively between the two run periods.

**Efficiencies**: the official map v09162025 answers this directly — it has BOTH
columns per channel: `eff_Ar` (XA 0.03, TPB PMT 0.12, PEN 0.036, with 13/24/33/34 at 0)
and `eff_Xe` (same values, but 13→0.03 and 24/34→0.036 become live; 33 stays 0).
NB Xin cited v04152025 — see Q4 below, that version is outdated for these runs.

**Channel liveness at 175 nm** (from `eff_*`): Ar-blind set = **{13, 24, 33, 34}**
(NOT {13, 29, 32, 39}): ch 29/39 are plain PEN (live at both wavelengths per the map)
and the uncoated PMT is **ch 33 (offline 3180)**, not 32. At 175 nm, 13/24/34 become
live — but 24/34 are absent from the DAQ readout anyway (below), so in practice
switching Ar→Xe only unmasks **ch 13**, and ch 33 stays masked always.

## Q4 — smaller items

- **DAPHNE↔module map**: the authoritative map for these runs is what the offline
  decoder itself uses: `PDVD_PDS_Mapping_v09162025.json` in `dunecore v10_21_00d00`
  (`channel`, `name` M1–M8/C1–C8, `pd_type`, `wls`, `eff_Ar`, `eff_Xe`, and the full
  `HardwareChannel` list: Slot/Link/DaphneChannel/OfflineChannel). Three versions ship;
  **v04152025 → v07082025 changed `name`+`HardwareChannel` for ALL 40 channels**
  (i.e. the module pairing itself was corrected), and v07082025 → v09162025 changed
  `wls`/`eff` for 24 channels. So anything derived from v04152025 (including its
  efficiency associations) should be re-based onto v09162025. This is also consistent
  with jjo's v5-geometry finding (v4 had the Arapucas y-mirrored; data agrees with v5).
- **Dead channels**: confirmed from the raw data — OpDets **24, 27, 28, 34** produce
  zero records in all five files (all four on the DAPHNE readout side; 24/34 are the
  PEN+Q PMTs, so at 128 nm only 27/28 represent lost acceptance), and OpDet 14
  (offline 3010, TPB PMT) is present but with no usable gain. **No per-run bad-channel
  database exists in dunesw for PDVD PDS** — a static mask is currently the only
  option; ask the PDS consortium whether they maintain a run-registry-based list.
- **Run 039324 light data**: not on wcgpu1 (only 039252/039253/039349 raw HDF5 were
  staged in `/nfs/data/1/xning/container/dune_data/hdf5/PDVD/`). Xin's charge-side
  039324 artifacts exist, so only the light is missing. Two routes: (a) whoever staged
  the five existing files pulls the 039324 file(s) the same way; (b) fetch from
  FNAL dCache — needs a DUNE token (`htgettoken`); with a token available on wcgpu1
  the whole light chain (decode → rawwf+trigoff) runs here in ~4 min/file.
- **Charge-side tickinfo**: agreed, the right long-term fix — the info is already in
  the art event as `raw::RDTimeStamp` (per channel), so the WCT charge extraction can
  fill the frame `tickinfo` time directly. Two traps for whoever implements it:
  (1) PDVD's decoder stores TDE stamps in **ns** and BDE stamps in **16-ns DTS ticks**
  (factor 16 — see ANSWER.md), and (2) the two crates' window starts differ by
  0–32 µs, so the frame time must be per-crate, not global. Until then the
  `trigoff/trigger_offset` tree in the new rawwf files is the per-event source.
