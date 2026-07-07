#!/usr/bin/env python3
"""Clearer timing plot: number of DISTINCT PDs firing per short time slice, vs time.
A real multi-PD coincidence => a spike. Shows PDVD light IS coincident (spikes),
so single-PD flashes are a finder problem."""
import csv
from collections import Counter, defaultdict
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

S = "/tmp/claude-49934/-exp-dune-app-users-jjo-temp/8f9d0c98-979d-46dd-bda2-4331eeb007e3/scratchpad"

def load(path):
    rows = list(csv.DictReader(open(path)))
    ev = Counter(int(r["event"]) for r in rows); tgt = ev.most_common(1)[0][0]
    t = np.array([float(r["ptime_rel"]) for r in rows if int(r["event"]) == tgt])
    c = np.array([int(r["opchannel"]) for r in rows if int(r["event"]) == tgt])
    return tgt, t, c

def profile(t, c, binw):
    # distinct channels per bin of width binw
    order = np.argsort(t); t = t[order]; c = c[order]
    nb = int(t[-1] / binw) + 1
    per = defaultdict(set)
    for ti, ci in zip(t, c):
        per[int(ti / binw)].add(ci)
    x = np.array(sorted(per)) * binw
    y = np.array([len(per[int(xx / binw)]) for xx in x])
    return x, y

fig, axes = plt.subplots(2, 1, figsize=(11, 8))
for ax, (path, name, binw, fmult) in zip(axes, [
        (f"{S}/pdvd_ophit2.csv", "PDVD (run 039252) — OpFlashFinderVerticalDrift", 2.0, 1),
        (f"{S}/pdhd_ophit2.csv", "PDHD (run 027305) — protodune_opflash",           2.0, 15)]):
    tgt, t, c = load(path)
    x, y = profile(t, c, binw)
    med = int(np.median(y)); mx = int(y.max())
    ax.plot(x, y, lw=0.7, color="#1f77b4")
    ax.axhline(fmult, color="#d62728", ls="--", lw=1.2,
               label=f"finder's max flash multiplicity = {fmult}")
    ax.set_title(f"{name} — event {tgt}: distinct PDs per {binw:g}-unit slice "
                 f"(median={med}, PEAK={mx})")
    ax.set_xlabel("hit PeakTime (relative to event start)")
    ax.set_ylabel(f"# distinct PDs\nper {binw:g}-unit slice")
    ax.legend(loc="upper right", fontsize=9); ax.grid(alpha=0.25)
fig.suptitle("Distinct PDs firing per short time slice: spikes = real multi-PD coincidences in the raw OpHits",
             fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.97))
out = "/exp/dune/app/users/jjo/temp/timing_profile_pdvd_vs_pdhd.png"
fig.savefig(out, dpi=130); print("wrote", out)

# quantify burst-vs-uniform
for path, name in [(f"{S}/pdvd_ophit2.csv","PDVD"), (f"{S}/pdhd_ophit2.csv","PDHD")]:
    tgt, t, c = load(path); x, y = profile(t, c, 2.0)
    print(f"{name}: distinct-PDs-per-2-unit-slice  median={np.median(y):.0f}  90th={np.percentile(y,90):.0f}  max={y.max():.0f}")
