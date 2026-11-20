"""Baseline diagnostic for one channel: median deconvolved waveform in
ABSOLUTE record time (not peak-aligned) for v1/v0/NP04 + the raw pulse,
with zooms on the record start (the PostBLCorrection window, ticks 0-19)
and the record end (FFT-circularity artifact).

Usage: python plot_baseline_diag.py [opch]   (default 30)
Writes plots/fig_baseline_ch<NNN>.png
"""

import os
import sys
import numpy as np
import uproot
import awkward as ak
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/nfs/data/1/jjo/data/PDHD/spe_template_cmp"
HERE = os.path.dirname(os.path.abspath(__file__))
CH = int(sys.argv[1]) if len(sys.argv) > 1 else 30
FILES = {28084: "np04hd_raw_run028084_0300_dataflow0_datawriter_0_"
                "20240720T192229_final.root",
         29107: "np04hd_raw_run029107_0004_dataflow7_datawriter_0_"
                "20240906T163315_final.root"}
C = {"v1": "#D55E00", "v0": "#0072B2", "np04": "#009E73"}

wfs = {t: [] for t in ("v1", "v0", "np04")}
raws = []
for run, fn in FILES.items():
    f = uproot.open(f"/nfs/data/1/jjo/data/PDHD/{fn}")
    met = np.load(f"{OUT}/metrics_run{run}.npz")
    sel = ((met["raw_amp"] >= 25) & (met["raw_min"] > 20)
           & (met["opch"] == CH))
    keys = set(zip(met["event"][sel].tolist(),
                   met["timestamp"][sel].tolist()))
    for t, tn in (("v1", "decodump/deco_waveform"),
                  ("v0", "decodumpv0/deco_waveform")):
        tr = f[tn]
        dm = tr.arrays(["event", "opch", "timestamp"], library="np")
        m = (dm["opch"] == CH) & np.array(
            [(e, ts) in keys for e, ts in
             zip(dm["event"].tolist(), dm["timestamp"].tolist())])
        wfs[t].append(ak.to_numpy(ak.to_regular(
            tr.arrays(["adc"], library="ak")["adc"][m])))
    wfs["np04"].append(np.load(f"{OUT}/np04deco_run{run}.npz")["wf"][sel])
    tr = f["rawdump/raw_waveform"]
    dm = tr.arrays(["event", "opch", "timestamp", "nsamples"], library="np")
    m = (dm["opch"] == CH) & (dm["nsamples"] == 1024) & np.array(
        [(e, ts) in keys for e, ts in
         zip(dm["event"].tolist(), dm["timestamp"].tolist())])
    raws.append(ak.to_numpy(ak.to_regular(
        tr.arrays(["adc"], library="ak")["adc"][m])))

W = {t: np.vstack(v) for t, v in wfs.items()}
R = np.vstack(raws).astype(float)
Rp = R[:, :20].mean(axis=1, keepdims=True) - R      # positive-going pulse

fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
tick = np.arange(1024)
for t in ("v1", "v0", "np04"):
    w = W[t]
    mm = np.median(w / w.max(axis=1, keepdims=True), axis=0)
    axes[0].plot(tick, mm, color=C[t], lw=1, label=t)
    axes[1].plot(tick[:160], mm[:160], color=C[t], lw=1)
    axes[2].plot(tick[-160:], mm[-160:], color=C[t], lw=1)
rm = np.median(Rp / Rp.max(axis=1, keepdims=True), axis=0)
for ax, sl in zip(axes, (slice(None), slice(0, 160), slice(-160, None))):
    ax.plot(tick[sl], rm[sl], color="0.4", lw=0.8, ls=":",
            label="raw" if sl == slice(None) else None)
    ax.axhline(0, color="k", lw=0.4)
    ax.grid(alpha=0.25, lw=0.4)
axes[1].axvspan(0, 20, color="0.85", zorder=0)
axes[0].set_title(f"opch {CH}: median deco / peak (absolute tick)")
axes[0].legend(frameon=False)
axes[1].set_title("record start (grey = PostBLCorrection window 0-19)")
axes[2].set_title("record end (v1/v0 'recovery' = FFT circularity)")
axes[1].set_ylim(-0.1, 0.25)
axes[2].set_ylim(-0.15, 0.1)
for ax in axes:
    ax.set_xlabel("tick (16 ns)")
fig.tight_layout()
out = f"{HERE}/plots/fig_baseline_ch{CH:03d}.png"
fig.savefig(out, dpi=120)
print("wrote", out, f"({len(R)} records)")
