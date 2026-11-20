#!/usr/bin/env python3
"""Analyze the PDVD triglight trees: per-event charge/trigger/light time bases.
Writes ql_trigger_offset.txt (per event) and prints per-run summaries.
All comparisons in the 40-bit-masked DTS domain (the light timestamps' domain).

Conventions:
  rd_timestamp   : ns since epoch (PDVD PDVDDataInterfaceWIBEth) -> ticks = ns/16
  tc_time        : DTS ticks (16 ns)
  light/fs t0    : microseconds = (ticks & 0xffffffffff) * 0.016
  offset_us      : charge_window_start - light_window_start   (what QL matching needs)
"""
import glob, os
import numpy as np
import uproot

OUT = "/nfs/data/1/jjo/tmp/pdvd_flash_validation/out/triglight"
MASK = (1 << 40) - 1
PERIOD_US = (1 << 40) * 0.016  # 40-bit rollover period in us

def to_us40(ticks):
    return (int(ticks) & MASK) * 0.016

def wrap(d):
    """wrap a time difference into (-PERIOD/2, PERIOD/2]"""
    return (d + PERIOD_US / 2) % PERIOD_US - PERIOD_US / 2

rows = []
for f in sorted(glob.glob(f"{OUT}/*_triglight.root")):
    t = uproot.open(f)["triglight/triglight"].arrays(library="np")
    for i in range(len(t["event"])):
        rd_ns = int(t["rd_timestamp"][i])
        ch_us = to_us40(rd_ns // 16)
        tcs = t["tc_time"][i].tolist()
        tct = t["tc_type"][i].tolist()
        tc_us = to_us40(tcs[0]) if tcs else float("nan")
        fs = float(t["fs_t0_us"][i])
        lt = float(t["light_t0_us"][i])
        # families: ns-stamps are TDE (exactly 32-us frame aligned), tick-stamps are BDE (WIBEth)
        ns_min, ns_max = int(t["rd_ns_min"][i]), int(t["rd_ns_max"][i])
        tk_min, tk_max = int(t["rd_tk_min"][i]), int(t["rd_tk_max"][i])
        rows.append(dict(
            run=int(t["run"][i]), subrun=int(t["subrun"][i]), event=int(t["event"][i]),
            rd_ns=rd_ns, rd_spread_us=(int(t["rd_ts_max"][i]) - int(t["rd_ts_min"][i])) / 16 * 0.016,
            n_rd_ns=int(t["n_rd_ns"][i]), n_rd_tk=int(t["n_rd_tk"][i]),
            tde_us=to_us40(ns_min // 16), tde_spread_us=(ns_max - ns_min) / 1000.0,
            bde_us=to_us40(tk_min), bde_spread_us=(tk_max - tk_min) * 0.016,
            tde_minus_bde=wrap(to_us40(ns_min // 16) - to_us40(tk_min)),
            n_tc=len(tcs), tc_type0=tct[0] if tct else -1, tc_types=tct,
            charge_us=ch_us, tc_us=tc_us, fs_t0_us=fs, light_t0_us=lt,
            fs_nsamp_min=int(t["fs_nsamp_min"][i]), fs_nsamp_max=int(t["fs_nsamp_max"][i]),
            dig_nsamp_min=int(t["digit_nsamp_min"][i]) if "digit_nsamp_min" in t else 0,
            dig_nsamp_max=int(t["digit_nsamp_max"][i]) if "digit_nsamp_max" in t else 0,
            n_fs=int(t["n_fullstream"][i]), n_wf=int(t["n_wf"][i]),
            off_charge_fs=wrap(ch_us - fs), off_charge_light=wrap(ch_us - lt),
            off_tc_fs=wrap(tc_us - fs), off_tc_charge=wrap(tc_us - ch_us),
        ))

# per-event table
tbl = "/nfs/data/1/jjo/tmp/pdvd_flash_validation/out/triglight/ql_trigger_offset.txt"
with open(tbl, "w") as fh:
    fh.write("# PDVD per-event charge/trigger/light time bases (DTS clock, 16 ns ticks)\n"
             "# charge_start_us / tc_us / fs_t0_us / light_t0_us are in the 40-bit-masked domain"
             " (same as the rawwf 'timestamp' branch); offsets wrapped to that period\n"
             "# offset_us = charge_window_start - fs_light_window_start  (add to light times to land on charge time base)\n"
             "# charge_tde_us / charge_bde_us: per-crate charge window starts (TDE=top, BDE=bottom CRPs)\n"
             "# run subrun event rd_timestamp_ns tc_type n_tc tc_us charge_tde_us charge_bde_us fs_t0_us light_t0_us fs_nsamp offset_tde_us offset_bde_us\n")
    for r in rows:
        fh.write(f"{r['run']} {r['subrun']} {r['event']} {r['rd_ns']} {r['tc_type0']} {r['n_tc']} "
                 f"{r['tc_us']:.3f} {r['tde_us']:.3f} {r['bde_us']:.3f} {r['fs_t0_us']:.3f} {r['light_t0_us']:.3f} "
                 f"{r['fs_nsamp_max']} {wrap(r['tde_us']-r['fs_t0_us']):.3f} {wrap(r['bde_us']-r['fs_t0_us']):.3f}\n")
print(f"wrote {tbl} ({len(rows)} events)\n")

# per-run summaries
runs = sorted(set(r["run"] for r in rows))
for run in runs:
    rr = [r for r in rows if r["run"] == run]
    for key, label in [("off_tc_fs", "trigger - light_fs_start"),
                       ("off_tc_charge", "trigger - charge_start"),
                       ("off_charge_fs", "charge_start - light_fs_start  (THE offset)")]:
        v = np.array([r[key] for r in rr])
        print(f"run {run} ({len(rr)} evts)  {label:42s} mean={v.mean():12.3f} us  "
              f"std={v.std():8.3f}  min={v.min():12.3f}  max={v.max():12.3f}")
    ns = sorted(set(r["fs_nsamp_max"] for r in rr) | set(r["fs_nsamp_min"] for r in rr))
    tt = {}
    for r in rr:
        for x in r["tc_types"]:
            tt[x] = tt.get(x, 0) + 1
    nt = {r["n_tc"] for r in rr}
    print(f"run {run}  fs_nsamp values: {ns}  ({[f'{n*0.016/1000:.3f} ms' for n in ns]})")
    dg = sorted(set(r["dig_nsamp_min"] for r in rr) | set(r["dig_nsamp_max"] for r in rr))
    print(f"run {run}  charge RawDigit nsamp values: {dg}  "
          f"(at 512 ns/sample: {[f'{n*0.512/1000:.3f} ms' for n in dg]}; at 500 ns: {[f'{n*0.5/1000:.3f} ms' for n in dg]})")
    print(f"run {run}  TC types (all TCs): {tt}   n_tc per event: {sorted(nt)}")
    nns = {r["n_rd_ns"] for r in rr}; ntk = {r["n_rd_tk"] for r in rr}
    bs = np.array([r["bde_spread_us"] for r in rr]); ts_tde = np.array([r["tde_spread_us"] for r in rr])
    bt = np.array([r["tde_minus_bde"] for r in rr])
    print(f"run {run}  RDTimeStamp families: TDE(ns-stored) n={sorted(nns)} BDE(tick-stored) n={sorted(ntk)}")
    print(f"run {run}  within-family window-start spread: BDE max {bs.max():.3f} us, TDE max {ts_tde.max():.3f} us")
    print(f"run {run}  TDE_start - BDE_start: mean={bt.mean():.3f} us  std={bt.std():.3f}  min={bt.min():.3f}  max={bt.max():.3f}")
    # outliers vs run median of the key offset
    v = np.array([r["off_charge_fs"] for r in rr])
    med = np.median(v)
    for r, x in zip(rr, v):
        if abs(x - med) > 50:
            print(f"run {run}  OUTLIER evt {r['event']}: offset {x:.1f} us vs median {med:.1f} us "
                  f"(delta {x-med:+.1f} us), tc_types={r['tc_types']}, n_tc={r['n_tc']}")
    print()
