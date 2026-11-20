"""Aggregate the pre-pulse baseline metrics per channel and check them
against the existing verdicts.

Selection: the standard pulse cuts PLUS deco peak at the trigger position
(ipk 50-75 for every template), so ticks 25-45 are genuinely pre-pulse.

Outputs: baseline_summary.csv, plots/fig_baseline.png; prints agreement of
the pre-pulse metric with the recommended template list.
"""

import csv
import glob
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pdhd_deco import VENDOR

OUT_DIR = "/nfs/data/1/jjo/data/PDHD/spe_template_cmp"
HERE = os.path.dirname(os.path.abspath(__file__))
C = {"v1": "#D55E00", "v0": "#0072B2", "np04": "#009E73",
     "FBK": "#E69F00", "HPK": "#56B4E9"}
TEMPLATES = ("v1", "v0", "np04")

d = {}
for fn in sorted(glob.glob(f"{OUT_DIR}/metrics_run*.npz")):
    run = fn.split("metrics_run")[1].split(".")[0]
    m = dict(np.load(fn).items()) | dict(np.load(
        f"{OUT_DIR}/baseline_run{run}.npz").items())
    for k, v in m.items():
        d.setdefault(k, []).append(v)
d = {k: np.concatenate(v) for k, v in d.items()}

sel = (d["raw_amp"] >= 25.0) & (d["raw_min"] > 20)
for t in TEMPLATES:
    sel &= (d[f"{t}_ipk"] >= 50) & (d[f"{t}_ipk"] <= 75) & (d[f"{t}_peak"] > 0)
print(f"selected {sel.sum()} trigger-position pulses")

verd = {int(r["opch"]): r for r in
        csv.DictReader(open(os.path.join(HERE, "channel_verdicts.csv")))}

rows = []
for ch in np.unique(d["opch"][sel]):
    m = sel & (d["opch"] == ch)
    if m.sum() < 20:
        continue
    row = dict(opch=int(ch), vendor=VENDOR[int(ch)], n=int(m.sum()),
               recommended=verd[int(ch)]["recommended"])
    for t in TEMPLATES:
        row[f"{t}_pre"] = float(np.median(d[f"{t}_pre_mean"][m]
                                          / d[f"{t}_peak"][m]))
        row[f"{t}_end"] = float(np.median(d[f"{t}_end_mean"][m]
                                          / d[f"{t}_peak"][m]))
    row["d_pre_v1"] = row["v1_pre"] - row["np04_pre"]
    rows.append(row)

with open(os.path.join(HERE, "baseline_summary.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in sorted(rows, key=lambda r: r["opch"]):
        w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v)
                    for k, v in r.items()})

pre1 = np.array([r["v1_pre"] for r in rows])
pren = np.array([r["np04_pre"] for r in rows])
rec = np.array([r["recommended"] == "np04" for r in rows])
print(f"median pre-pulse level / peak: v1 {np.median(pre1):+.3f}, "
      f"np04 {np.median(pren):+.3f}")
print(f"channels where v1 pre-level worse by >0.02: "
      f"{(pre1 - pren > 0.02).sum()}/{len(rows)} "
      f"(of which already np04-recommended: "
      f"{((pre1 - pren > 0.02) & rec).sum()})")
print(f"keep-v1 channels with v1 pre-level worse by >0.02: "
      f"{sorted(r['opch'] for r in rows if r['d_pre_v1'] > 0.02 and r['recommended'] != 'np04')}")
print(f"np04-recommended channels where np04 pre-level worse by >0.02: "
      f"{sorted(r['opch'] for r in rows if r['d_pre_v1'] < -0.02 and r['recommended'] == 'np04')}")

fig, axes = plt.subplots(1, 2, figsize=(11, 5))
for vend in ("FBK", "HPK"):
    s = [r for r in rows if r["vendor"] == vend]
    axes[0].scatter([r["v1_pre"] for r in s], [r["np04_pre"] for r in s],
                    s=22, c=C[vend], label=vend, alpha=0.85, edgecolors="none")
    axes[1].scatter([r["v1_end"] for r in s], [r["np04_end"] for r in s],
                    s=22, c=C[vend], alpha=0.85, edgecolors="none")
for ax, lo, hi, what in ((axes[0], -0.01, 0.09,
                          "pre-pulse level (ticks 25-45)"),
                         (axes[1], -0.06, 0.02,
                          "record-end level (last 40 ticks)")):
    ax.plot([lo, hi], [lo, hi], color="0.6", lw=0.8, zorder=0)
    ax.axhline(0, color="k", lw=0.5)
    ax.axvline(0, color="k", lw=0.5)
    ax.set(xlim=(lo, hi), ylim=(lo, hi),
           xlabel=f"v1: median {what} / peak",
           ylabel=f"NP04: median {what} / peak")
    ax.grid(alpha=0.25, lw=0.5)
axes[0].legend(frameon=False)
axes[0].set_title("Pre-pulse pedestal (acausal shoulder)")
axes[1].set_title("Record-end level (FFT-circularity residual)")
fig.suptitle("Deco baseline quality, trigger-position pulses "
             "(closer to 0 = better)", y=1.0)
fig.tight_layout()
fig.savefig(f"{HERE}/plots/fig_baseline.png", dpi=130)
print("wrote baseline_summary.csv + plots/fig_baseline.png")
