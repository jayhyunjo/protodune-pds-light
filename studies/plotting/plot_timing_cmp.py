#!/usr/bin/env python3
"""Timing comparison PDVD vs PDHD: hit PeakTime (relative) vs channel for one event each.
Shows both detectors have time-coincident light (vertical clustering) -> PDVD single-PD
flashes are NOT a timing/coincidence problem."""
import csv
from collections import Counter, defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

S = "/tmp/claude-49934/-exp-dune-app-users-jjo-temp/8f9d0c98-979d-46dd-bda2-4331eeb007e3/scratchpad"

def load(path):
    rows = list(csv.DictReader(open(path)))
    ev = Counter(int(r["event"]) for r in rows); tgt = ev.most_common(1)[0][0]
    t = np.array([float(r["ptime_rel"]) for r in rows if int(r["event"]) == tgt])
    c = np.array([int(r["opchannel"]) for r in rows if int(r["event"]) == tgt])
    pe = np.array([float(r["pe"]) for r in rows if int(r["event"]) == tgt])
    return tgt, t, c, pe

def maxcoinc(t, c, W):
    o = np.argsort(t); t = t[o]; c = c[o]; best = 0
    for i in range(len(t)):
        k = i
        s = set()
        while k < len(t) and t[k] < t[i] + W: s.add(c[k]); k += 1
        best = max(best, len(s))
    return best

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
for ax, (path, name, fmult) in zip(axes, [
        (f"{S}/pdvd_ophit2.csv", "PDVD (run 039252)  —  OpFlashFinderVerticalDrift", "flash max mult = 1"),
        (f"{S}/pdhd_ophit2.csv", "PDHD (run 027305)  —  protodune_opflash",           "flash max mult = 15")]):
    tgt, t, c, pe = load(path)
    mc2 = maxcoinc(t, c, 2.0)
    ax.scatter(t, c, s=6, alpha=0.35, c="k", linewidths=0)
    ax.set_xlabel("hit PeakTime  (relative to event start)")
    ax.set_ylabel("OpChannel")
    ax.set_title(f"{name}\nevent {tgt}: {len(t)} hits, up to {mc2} channels within a 2-unit window")
    ax.text(0.97, 0.03, f"OpHits ARE coincident\n(≤{mc2} PDs within 2 units)\nbut {fmult}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round", fc="#fff3cd", ec="#e0a800"))
    ax.grid(alpha=0.2)
fig.suptitle("Both PDVD and PDHD have time-coincident PD light — so PDVD's single-PD flashes are a FINDER problem, not timing",
             fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.96))
out = "/exp/dune/app/users/jjo/temp/timing_pdvd_vs_pdhd.png"
fig.savefig(out, dpi=130)
print("wrote", out)
