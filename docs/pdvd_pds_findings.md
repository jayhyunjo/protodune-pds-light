# ProtoDUNE-VD PDS (light) — findings & notes

Working notes on the ProtoDUNE-VD photon-detector data and reco.
Context: `dunesw v10_21_00d00 -q e26:prof`, geometry **`protodunevd_v5`**, run inside the
SL7 container. Data: `np02vd_raw_*.hdf5` (runs 039252/039253/039349).

---

## 1. VD light reco does NOT deconvolve
Stock VD PDS chain: `pdvddaphne` (`DAPHNEReaderPDVD` → `raw::OpDetWaveform`, tag
**`pdvddaphne:daq`**) → `ophit` (`OpHitFinder`, runs directly on raw ADC) → `opflash`
(`OpFlashFinderVerticalDrift`). There is **no `recob::OpWaveform` / no `Deconvolution`
module anywhere** in VD reco (unlike PDHD). PE is computed as area÷gain in `ophit`
(`AreaToPE:true`, flat `SPEArea:410` for all channels — no per-channel calibration by default).

We therefore save the **raw** waveforms and hand them off; any deconvolution is a
downstream step (Xin's WireCell `OpDecon`).

## 2. Geometry & channel maps (v5)
**40 OpDets:**
- 8 **cathode X-ARAPUCAs** (C1–C8, OpDet 4–11) — on the cathode plane, X≈0
- 8 **membrane X-ARAPUCAs** (M1–M8, OpDet 0–3,12,13,18,19) — on the ±Y walls, |Y|≈418 cm
- 24 **PMTs** (OpDet 14–17, 20–39) — periphery / Z-ends, X≈−206…−336 cm

**Two channel numberings:** `recob::OpHit::OpChannel` = offline readout channel
(**1010–3240**; X-ARAPUCAs gang 2 channels/PD, PMTs 1); `recob::OpFlash::PEs()` is indexed
by a **compact 0–45** index ≈ the OpDet index. Maps in `pdvd/maps/`:
`pdvd_v5_opdet_positions.csv` (OpDet → x,y,z,type,name) and
`pdvd_offlinechan_to_opdet.csv` (offline channel → OpDet), derived from `geo::DumpGeometry`
of `protodunevd_v5` + the DAPHNE map `PDVD_PDS_Mapping_v09162025.json`.

**Active volume** (real bounds, union of the 16 TPC active boxes): X ±341.5, Y ±336.4,
Z 0.6–298.7 cm — double-drift, cathode at X≈±3. Only the **cathode XA are inside** the
active volume; membrane XA sit on the ±Y walls and PMTs at the Z-ends. But **all PDs view
the active volume and are usable for charge–light matching** — they're mounted on the
boundaries and the light *pattern* across all of them encodes position. Cathode XA are the
primary detectors (face the drift, most light).

## 3. Readout modes
- **Cathode XA = full-stream**: one continuous **~468,800-sample** waveform per gang-channel
  per event (the whole ~7.5 ms window). Baseline ≈ 2700.
- **Membrane XA + PMTs = self-trigger**: many short **1024-sample** captures per event (one per
  threshold crossing). PMT baseline ≈ 8600.
- ADC is 14-bit, saturates at **16383**.

## 4. Waveform features
- **X-ARAPUCA pulses are slow/broad** (WLS bars → SiPMs + LAr scintillation fast+slow ~1.6 µs
  profile) → in an overlay they align at the *leading edge* but not the *peak*. **PMT pulses
  are fast/sharp** → align cleanly. ⇒ X-ARAPUCA and PMT need **different deconvolution
  templates**.
- **ADC saturation rollover**: on the largest pulses the peak *wraps to 0* instead of clipping
  at 16383 (e.g. `…15849, 0, 0, 15340…`) — a digitizer overflow. The peak is corrupted (reads
  low), so amplitude/PE for these pulses are wrong. **Flag/mask** them (a sample ≈0 between
  near-saturation samples, or `min≈0 & max>15000`).

## 5. Channel quality (survey, run039252, 18 events)
Response = 95th-pct(max ADC − baseline); SNR = response / robust-noise.
- **4 DEAD PMTs**: OpDet **24, 27, 28, 34** (offline 3090/3120/3130/3190) — no data at all
  (likely one DAPHNE slot/link off).
- **Response spans ~20×**: cathode XA ~14000 (**saturate ~100%** of captures — a real
  calibration concern for the primary matching detectors), membrane XA 500–3300, PMTs 308–5824.
- **OpDet 14 is the weakest PMT** — mostly noise per event (biggest pulse across 18 events only
  ~1100 ADC vs ~7000–8000 for a strong PMT; in many events *all* its captures are noise-level).
  Not dead, but effectively marginal → down-weight or exclude.
- ⇒ **per-channel gain calibration is needed**; the flat `SPEArea 410` is wrong for all of them.

## 6. Flash finder is broken for VD
`OpFlashFinderVerticalDrift` produces **single-PD flashes** (mean 1.0 PD/flash) vs PDHD's
multi-PD flashes (mean 4.3). Two problems: (a) the `protodunevd_opflash` plane thresholds
(`Cx=-320`, `RMy/LMy=±700`) are **FD-scale**, so they don't match v5 geometry (cathode X≈0,
membrane |Y|≈418) and the grouping branches almost never fire; (b) even with the plane cut
disabled the finder still fails to group clearly-coincident hits (the light *is* coincident —
~36 channels fire within a 2 µs window). So it's a **finder defect** (config + clustering),
**not** the data. Diagnosis fcls in `studies/pdvd_flash_finder/`.

For charge–light matching we'll need to **fix/retune the finder** or **build a custom
time-window OpHit grouping**. Likely a shipped-config bug worth reporting to the VD
PDS/software group.

## 7. Deliverable to Xin
Raw-light **plain-ROOT** flat trees (`raw_waveform`, via `pdvd/scripts/pdvd_dump_rawwf.py`) —
no deconvolution, no charge reco. Xin runs WireCell `OpDecon` + charge–light matching. Ship
with the maps and the caveats above (dead channels, per-channel gain, saturation rollover,
XA-vs-PMT templates).

## Open items
- Fix PDVD flash reco (`OpFlashFinderVerticalDrift`) or roll a custom OpHit time-grouping.
- Per-channel gain calibration; saturation flagging in the dump.
- Confirm with PDS/DAQ: the 4 dead PMTs, and whether the ADC wrap-to-0 is expected.
