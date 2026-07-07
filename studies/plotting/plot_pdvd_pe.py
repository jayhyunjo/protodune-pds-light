#!/usr/bin/env python3
"""ProtoDUNE-VD per-event light map: OpDets colored by PE (log), Side (XZ) + Top (YZ).
PE = sum over all flashes in the event, per OpDet (flash_breakdown.csv, OpChannel 0-39).
Positions from pdvd_v5_opdet_positions.csv (cm -> m)."""
import csv
from collections import Counter, defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle

POS = "/exp/dune/app/users/jjo/temp/pdvd_v5_opdet_positions.csv"
FB  = "/exp/dune/app/users/jjo/temp/flash_breakdown.csv"
OUT = "/exp/dune/app/users/jjo/temp/pdvd_v5_pe_event.png"

pos = {}
for d in csv.DictReader(open(POS)):
    pos[int(d["opdet"])] = (float(d["x"])/100, float(d["y"])/100, float(d["z"])/100, d["geom_shape"])

rows = list(csv.DictReader(open(FB)))
events = sorted({int(r["event"]) for r in rows})
ev = events[0]

pe = defaultdict(float)
for r in rows:
    if int(r["event"]) == ev:
        pe[int(r["opchannel"])] += float(r["npe"])

# stats
mult = Counter((int(r["event"]), int(r["flash_id"])) for r in rows)
top_flash = max(mult.items(), key=lambda kv: kv[1])
nlit = sum(1 for c in pe if pe[c] > 0)
vmax = max(pe.values()); vmin = max(min(v for v in pe.values() if v > 0), 1e-1)
print(f"event {ev}: {nlit}/40 OpDets lit, PE sum range [{vmin:.2g}, {vmax:.2g}]")
print(f"most-multiplicity flash: {top_flash[0]} with {top_flash[1]} OpDets")

def draw(ax, vidx, ylabel, title):
    norm = LogNorm(vmin=vmin, vmax=vmax)
    sc = None
    for od,(x,y,z,shape) in pos.items():
        v = [x,y,z][vidx]; p = pe.get(od,0.0)
        mk = "s" if shape=="xarapuca" else "o"
        sz = 90 if shape=="xarapuca" else 55
        if p > 0:
            sc = ax.scatter(z, v, c=[p], cmap="viridis", norm=norm, marker=mk, s=sz,
                            edgecolors="k", linewidths=0.4, zorder=3)
        else:
            ax.scatter(z, v, facecolors="none", edgecolors="0.6", marker=mk, s=sz, zorder=2)
    ax.add_patch(Rectangle((0.0,-3.35),3.0,6.7, fill=False, edgecolor="red", lw=1.0, zorder=1))
    ax.set_xlabel("Z (m)"); ax.set_ylabel(ylabel); ax.set_title(title)
    ax.set_xlim(-2.5,6.0); ax.set_ylim(-4.5,4.7); ax.set_aspect("equal","box"); ax.grid(alpha=0.25)
    return sc

fig,(a1,a2) = plt.subplots(1,2, figsize=(13.5,6.5))
draw(a1,0,"X (m) - Drift","Side view (avg along Y)")
sc = draw(a2,1,"Y (m)","Top view (avg along X)")
cb = fig.colorbar(sc, ax=[a1,a2], shrink=0.8, pad=0.02); cb.set_label("PE (sum over flashes)")
fig.suptitle(f"ProtoDUNE-VD event {ev}: detected light per OpDet  (squares=X-ARAPUCA, circles=PMT; open=no PE)", fontsize=11)
fig.savefig(OUT, dpi=130, bbox_inches="tight")
print("wrote", OUT)
