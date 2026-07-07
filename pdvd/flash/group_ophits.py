#!/usr/bin/env python3
"""Custom ProtoDUNE-VD flash builder: group recob::OpHits into multi-PD flashes by a
time window, in DOUBLE precision — a drop-in replacement for the buggy
OpFlashFinderVerticalDrift (which single-PDs everything due to (a) FD-scale plane
thresholds and (b) a `float initimecluster` that corrupts the ~5.7e9 PeakTime).

Input: the `opflashana/PerOpHitTree` flat tree (branches EventID, OpChannel,
PeakTimeAbs, PE) produced by `pdvd/fcl/pdvd_pds_ophit.fcl` (pdvddaphne + ophit +
OpFlashAna). Reads with uproot (laptop) or pyROOT (container).

Grouping: sort OpHits by PeakTimeAbs; each flash spans [t0, t0+dt] from its earliest
ungrouped hit (dt in PeakTimeAbs units — dt~2-5 gives ~PDHD-like multiplicity; pin to
µs via DetectorClocks later). Optionally require >= --min-pds distinct OpDets.

  # scan dt to see the coincidence structure:
  python group_ophits.py <perophit.root> --scan
  # build flashes -> CSVs (flashes + per-PD breakdown), for charge-light matching:
  python group_ophits.py <perophit.root> --dt 2 --min-pds 2 --out flashes

Outputs (with --out PREFIX): PREFIX_flashes.csv (event,flash_id,time,n_opdet,total_pe,
ycenter,zcenter) and PREFIX_flash_opdet.csv (event,flash_id,opdet,pe,x,y,z).
"""
import os, sys, csv, argparse
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.join(HERE, "..", "maps")

def load_maps(posf, mapf):
    pos = {int(d["opdet"]): (float(d["x"]), float(d["y"]), float(d["z"])) for d in csv.DictReader(open(posf))}
    ch2od = {int(d["offline_channel"]): int(d["opdet"]) for d in csv.DictReader(open(mapf))}
    return pos, ch2od

def read_ophits(path):
    """event -> list of (peaktimeabs float64, opchannel, pe). uproot then pyROOT."""
    out = defaultdict(list)
    try:
        import uproot
        a = uproot.open(path)["opflashana/PerOpHitTree"].arrays(
            ["EventID", "OpChannel", "PeakTimeAbs", "PE"], library="np")
        for i in range(len(a["EventID"])):
            out[int(a["EventID"][i])].append((float(a["PeakTimeAbs"][i]), int(a["OpChannel"][i]), float(a["PE"][i])))
    except ImportError:
        import ROOT
        f = ROOT.TFile.Open(path); t = f.Get("opflashana/PerOpHitTree")
        for e in t:
            out[int(e.EventID)].append((float(e.PeakTimeAbs), int(e.OpChannel), float(e.PE)))
    return out

def group(evhits, dt):
    """greedy seed-window grouping (double precision). evhits: [(t, opdet, pe)]."""
    evhits = sorted(evhits); flashes, i, n = [], 0, len(evhits)
    while i < n:
        t0 = evhits[i][0]; j = i
        while j < n and evhits[j][0] <= t0 + dt:
            j += 1
        flashes.append(evhits[i:j]); i = j
    return flashes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("perophit")
    ap.add_argument("--dt", type=float, default=2.0, help="time window (PeakTimeAbs units)")
    ap.add_argument("--min-pds", type=int, default=1, help="require >= this many distinct OpDets")
    ap.add_argument("--positions", default=os.path.join(MAPS, "pdvd_v5_opdet_positions.csv"))
    ap.add_argument("--chanmap", default=os.path.join(MAPS, "pdvd_offlinechan_to_opdet.csv"))
    ap.add_argument("--out", default=None, help="output prefix for flashes/flash_opdet CSVs")
    ap.add_argument("--scan", action="store_true", help="print a dt scan and exit")
    a = ap.parse_args()

    pos, ch2od = load_maps(a.positions, a.chanmap)
    raw = read_ophits(a.perophit)
    hits = {ev: [(t, ch2od[ch], pe) for t, ch, pe in v if ch in ch2od] for ev, v in raw.items()}
    print(f"read {sum(len(v) for v in hits.values())} mapped OpHits over {len(hits)} events")

    if a.scan:
        print("\n  dt    nflash  maxMult  meanMult  %multiPD")
        for dt in [0.5, 1, 2, 5, 10, 20, 50, 100]:
            m = [len({od for _, od, _ in g}) for ev in hits for g in group(hits[ev], dt)]
            m = np.array(m)
            print(f"  {dt:6g} {len(m):7d}  {m.max():5d}  {m.mean():7.2f}  {100*np.mean(m > 1):6.1f}")
        return

    fl_rows, fo_rows = [], []
    for ev in sorted(hits):
        fid = 0
        for g in group(hits[ev], a.dt):
            pe_by_od = defaultdict(float)
            for t, od, pe in g:
                pe_by_od[od] += pe
            if len(pe_by_od) < a.min_pds:
                continue
            tot = sum(pe_by_od.values())
            tw = sum(t * pe for t, _, pe in g) / tot if tot else g[0][0]
            yc = sum(pos[od][1] * p for od, p in pe_by_od.items()) / tot if tot else 0
            zc = sum(pos[od][2] * p for od, p in pe_by_od.items()) / tot if tot else 0
            fl_rows.append((ev, fid, tw, len(pe_by_od), tot, yc, zc))
            for od, p in sorted(pe_by_od.items()):
                fo_rows.append((ev, fid, od, p, pos[od][0], pos[od][1], pos[od][2]))
            fid += 1
    mult = [r[3] for r in fl_rows]
    print(f"built {len(fl_rows)} flashes (dt={a.dt}, min_pds={a.min_pds}): "
          f"mean mult={np.mean(mult):.2f}, max={max(mult)}, multi-PD={100*np.mean(np.array(mult) > 1):.0f}%")
    if a.out:
        with open(a.out + "_flashes.csv", "w") as f:
            w = csv.writer(f); w.writerow(["event", "flash_id", "time", "n_opdet", "total_pe", "ycenter", "zcenter"])
            w.writerows(fl_rows)
        with open(a.out + "_flash_opdet.csv", "w") as f:
            w = csv.writer(f); w.writerow(["event", "flash_id", "opdet", "pe", "x", "y", "z"])
            w.writerows(fo_rows)
        print(f"wrote {a.out}_flashes.csv ({len(fl_rows)}) and {a.out}_flash_opdet.csv ({len(fo_rows)})")

if __name__ == "__main__":
    main()
