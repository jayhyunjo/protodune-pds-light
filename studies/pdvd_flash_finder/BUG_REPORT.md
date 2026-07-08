# `OpFlashFinderVerticalDrift` produces only single-PD flashes on ProtoDUNE-VD

**Package / version:** `duneopdet` v10_21_00d00 (dunesw v10_21_00d00), module
`duneopdet/OpticalDetector/OpFlashFinderVerticalDrift_module.cc`.
**Config:** `protodunevd_opflash` (`opticaldetectormodules_dune.fcl`).
**Symptom:** every `recob::OpFlash` contains essentially **one** OpDet. Coincident
scintillation light seen across many PDs is never grouped into a single flash, so
flash-based charge–light matching is impossible.

Data: ProtoDUNE-VD (NP02) cosmics, run 039252, `protodunevd_v5` geometry (40 OpDets:
8 cathode X-ARAPUCAs, 8 membrane X-ARAPUCAs, 24 PMTs).

## Quantitative symptom

Flash OpDet-multiplicity (distinct OpDets with PE>0 per flash), 2 events, from
`opflashana/FlashBreakdownTree`:

| build | # flashes | max mult | mean mult | multi-PD |
|-------|-----------|----------|-----------|----------|
| stock v10_21_00d00 | — | **1** | 1.00 | 0% |
| **fixed** | 4302 | **28** | 2.77 | 70% |

The "fixed" column matches an independent double-precision OpHit grouping
(`pdvd/flash/group_ophits.py`) run on the *same* OpHits — max 28, mean 2.77, 70%
multi-PD — i.e. the light really is coincident; the finder was dropping it.

## Root cause — three independent bugs

### 1. FD-scale per-plane thresholds never match ProtoDUNE-VD geometry
`getNeighbors` groups hits with per-plane spatial cuts hard-coded to far-detector
values: cathode `Cx = -320`, membrane `RMy/LMy = ±700`. In `protodunevd_v5` the
cathode X-ARAPUCAs sit at X ≈ 0 and the membrane X-ARAPUCAs at |Y| ≈ 418, so **no
plane branch ever fires** and hits are never declared neighbours.

### 2. `float initimecluster` corrupts the time cut at VD timestamps
The cluster seed time is carried as `float`. ProtoDUNE-VD `PeakTime ≈ 5.7e9`; at that
magnitude a 32-bit float ULP is ≈ 512, far larger than the `MaximumTimeWindow = 2.0`
cut, so `dtmax = |initimecluster - PeakTime|` is meaningless and the time-window test
is effectively random.

### 3. (decisive) index space mismatch between clustering and flash construction
`getNeighbors` returns **sorted positions** (indices into the `sorted[]` order),
pushing them into the per-flash list. But `ConstructFlash` indexes the hit vector by
**original hit index** (`HitVector.at(HitID)`), and the flash↔OpHit associations do
`art::Ptr(handle, hitIndex)` with the same values. Only the seed is pushed as an
original index (`sorted[h]`); every neighbour is a sorted position used as if it were
an original index. So the *wrong* hits are assigned to each flash — membership,
`PEs()`, positions and associations are all corrupted, collapsing each flash to ~1
OpDet. Fixing (1) and (2) alone only raises max multiplicity from 1 to 3; (3) is what
actually breaks the grouping.

## Fix

Replace the `getNeighbors` + BFS clustering in `AssignHitsToFlash` with a simple
greedy time-window grouping in double precision, returning **original** hit indices:

- sort hit indices by `PeakTime`;
- each flash spans `[t0, t0 + MaximumTimeWindow]` from its earliest ungrouped hit;
- push `sorted[j]` (the original index) into the flash's hit list.

No spatial cut is applied: at ProtoDUNE-VD scale every PD that sees a coincident flash
belongs to that flash (spatial separation is recovered later from the per-OpDet PE
pattern, not by pre-splitting the flash). `AddHitContribution` / `ConstructFlash` were
already correct (`PEs` indexed by `OpDetFromOpChannel`, positions by
`OpDetGeoFromOpChannel`), so once grouping feeds them the right hits, multi-PD
`recob::OpFlash` come out directly. `getNeighbors` is left in place but unused.

See `patch/OpFlashFinderVerticalDrift.patch` (diff vs the pristine v10_21_00d00 tag)
and `patch/OpFlashFinderVerticalDrift_module.cc` (the full patched module).

## Notes / open questions for upstream

- The greedy window is `MaximumTimeWindow` (default 2.0). Flash count is ~2150/event
  at 2.0 on this data; that single knob sets how finely bursts are split and is the
  only remaining tuning parameter.
- A spatial/topological cut could be reintroduced deliberately (e.g. to separate two
  simultaneous flashes far apart in Y/Z), but it must use ProtoDUNE-VD geometry and a
  consistent index space — the stock cut did neither.
- Bugs (1) and (3) are geometry/indexing bugs, not tunings — they affect any detector
  where the sorted and original hit orders differ (i.e. always).
