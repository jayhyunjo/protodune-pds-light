#!/usr/bin/env python3
"""Quick ProtoDUNE-VD OpDet layout: Side view (X vs Z) + Top view (Y vs Z).
Black dots = optical detectors (squares = X-ARAPUCA, circles = PMT).
Reads temp/pdvd_v5_opdet_positions.csv (cm -> m)."""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

CSV = "/exp/dune/app/users/jjo/temp/pdvd_v5_opdet_positions.csv"
OUT = "/exp/dune/app/users/jjo/temp/pdvd_v5_opdet_layout.png"

rows = []
with open(CSV) as f:
    for d in csv.DictReader(f):
        rows.append(dict(opdet=int(d["opdet"]),
                         x=float(d["x"])/100.0, y=float(d["y"])/100.0, z=float(d["z"])/100.0,
                         shape=d["geom_shape"], typ=d["json_pd_type"], name=d["json_name"]))

xa  = [r for r in rows if r["shape"] == "xarapuca"]
pmt = [r for r in rows if r["shape"] == "pmt"]

def draw(ax, vkey, ylabel, title):
    ax.scatter([r["z"] for r in xa],  [r[vkey] for r in xa],  c="k", marker="s", s=45, label="X-ARAPUCA")
    ax.scatter([r["z"] for r in pmt], [r[vkey] for r in pmt], c="k", marker="o", s=18, label="PMT")
    # approximate active (CRP) volume guide, from the reference figure: Z in [0,3] m
    ax.add_patch(Rectangle((0.0, -3.35), 3.0, 6.7, fill=False, edgecolor="red", lw=1.2))
    ax.set_xlabel("Z (m)"); ax.set_ylabel(ylabel); ax.set_title(title)
    ax.set_xlim(-2.5, 6.0); ax.set_ylim(-4.5, 4.7)
    ax.set_aspect("equal", adjustable="box"); ax.grid(alpha=0.25)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)

fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 6.5))
draw(a1, "x", "X (m) - Drift", "ProtoDUNE-VD OpDets - Side view (avg along Y)")
draw(a2, "y", "Y (m)",         "ProtoDUNE-VD OpDets - Top view (avg along X)")
fig.suptitle("ProtoDUNE-VD v5 optical detectors (40): 8 membrane + 8 cathode X-ARAPUCA, 24 PMT", fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(OUT, dpi=130)
print("wrote", OUT, "  (xarapuca=%d, pmt=%d)" % (len(xa), len(pmt)))
