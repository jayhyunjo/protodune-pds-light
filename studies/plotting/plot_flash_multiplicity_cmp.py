#!/usr/bin/env python3
"""Compare flash multiplicity (# PDs per flash) between PDHD and PDVD."""
import csv
from collections import defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def mult(path):
    fc = defaultdict(set)
    for r in csv.DictReader(open(path)):
        fc[(int(r["event"]), int(r["flash_id"]))].add(int(r["opchannel"]))
    return np.array([len(v) for v in fc.values()])

pdhd = mult("/tmp/claude-49934/-exp-dune-app-users-jjo-temp/8f9d0c98-979d-46dd-bda2-4331eeb007e3/scratchpad/pdhd_flash.csv")
pdvd = mult("/exp/dune/app/users/jjo/temp/flash_breakdown.csv")

bins = np.arange(0.5, 17.5, 1.0)
fig, ax = plt.subplots(figsize=(9, 5.5))
ax.hist(pdhd, bins=bins, density=True, histtype="stepfilled", alpha=0.55, color="#1f77b4",
        label=f"PDHD  (protodune_opflash)\n  {len(pdhd)} flashes, mean={pdhd.mean():.1f} PDs, {100*np.mean(pdhd>1):.0f}% multi-PD")
ax.hist(pdvd, bins=bins, density=True, histtype="stepfilled", alpha=0.55, color="#d62728",
        label=f"PDVD  (OpFlashFinderVerticalDrift)\n  {len(pdvd)} flashes, mean={pdvd.mean():.1f} PDs, {100*np.mean(pdvd>1):.0f}% multi-PD")
ax.set_yscale("log")
ax.set_xlabel("Number of PDs per flash (multiplicity)")
ax.set_ylabel("Fraction of flashes (normalized)")
ax.set_title("Flash multiplicity: PDHD flashes group many PDs; every PDVD flash is single-PD")
ax.set_xticks(range(1, 17))
ax.legend(loc="upper right", fontsize=9)
ax.grid(alpha=0.25, which="both")
ax.annotate("PDVD: 100% at multiplicity = 1\n(no light grouped across PDs)",
            xy=(1, 1.0), xytext=(4.5, 0.35), fontsize=9, color="#d62728",
            arrowprops=dict(arrowstyle="->", color="#d62728"))
fig.tight_layout()
out = "/exp/dune/app/users/jjo/temp/flash_multiplicity_pdhd_vs_pdvd.png"
fig.savefig(out, dpi=130)
print("wrote", out)
