"""Evidence plots for the SPE-template comparison (v1 / v0 per-channel vs
NP04 vendor-average), from channel_verdicts.csv + kernel_metrics.csv +
median_pulses.npz + kernels.npz.

Writes into plots/:
  fig_summary_scatter.png     per-channel undershoot + integrated-tail, v1 vs NP04
  fig_channel_profile.png     improvement vs channel number (the "list" as a plot)
  fig_mechanism.png           kernel DC-balance vs measured improvement
  fig_kernels_worst.png       SPE kernels of the worst channels
  fig_apa_map.png             recommendation on the PD layout (Y-Z per APA)
  fig_overlays_apa{4,3,2}.png contact sheets: median pulse per channel
  channel_overlays/ch###.png  per-channel evidence plots (all 113)
"""

import csv
import os
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
PLOTS = os.path.join(HERE, "plots")
os.makedirs(os.path.join(PLOTS, "channel_overlays"), exist_ok=True)

GEO_FILE = ("/nfs/data/1/jjo/data/PDHD/np04hd_raw_run027980_0000_dataflow0_"
            "datawriter_0_20240711T160710_final.root")

C = {"v1": "#D55E00", "v0": "#0072B2", "np04": "#009E73",
     "FBK": "#E69F00", "HPK": "#56B4E9"}
TAIL_T = np.arange(-64, 512) * 0.016     # us relative to peak

rows = {int(r["opch"]): r for r in
        csv.DictReader(open(os.path.join(HERE, "channel_verdicts.csv")))}
kern = {}
for r in csv.DictReader(open(os.path.join(HERE, "kernel_metrics.csv"))):
    kern[(r["version"], int(r["opch"]))] = r
mp = np.load(os.path.join(HERE, "median_pulses.npz"))
kwf = np.load(os.path.join(HERE, "kernels.npz"))
CHS = sorted(rows)


def f(ch, key):
    return float(rows[ch][key])


# ---------------------------------------------------------------- fig 1
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
for vend in ("FBK", "HPK"):
    sel = [c for c in CHS if rows[c]["vendor"] == vend]
    axes[0].scatter([abs(f(c, "v1_u_med")) for c in sel],
                    [abs(f(c, "np04_u_med")) for c in sel],
                    s=22, c=C[vend], label=vend, alpha=0.85, edgecolors="none")
    axes[1].scatter([f(c, "v1_negfrac_med") for c in sel],
                    [f(c, "np04_negfrac_med") for c in sel],
                    s=22, c=C[vend], label=vend, alpha=0.85, edgecolors="none")
for c in (60, 50, 40, 105):
    axes[0].annotate(str(c), (abs(f(c, "v1_u_med")), abs(f(c, "np04_u_med"))),
                     textcoords="offset points", xytext=(4, 3), fontsize=8)
    axes[1].annotate(str(c), (f(c, "v1_negfrac_med"), f(c, "np04_negfrac_med")),
                     textcoords="offset points", xytext=(4, 3), fontsize=8)
lim = 0.75
axes[0].plot([0, lim], [0, lim], color="0.6", lw=0.8, zorder=0)
axes[0].set(xlim=(0, lim), ylim=(0, lim),
            xlabel="per-channel v1:  median |undershoot| / peak",
            ylabel="vendor-average NP04:  median |undershoot| / peak",
            title="Tail undershoot depth (below diagonal = NP04 better)")
axes[1].plot([0.02, 30], [0.02, 30], color="0.6", lw=0.8, zorder=0)
axes[1].set(xscale="log", yscale="log", xlim=(0.05, 30), ylim=(0.05, 30),
            xlabel="v1:  median tail negative area / prompt area",
            ylabel="NP04:  median tail negative area / prompt area",
            title="Integrated tail deficit (below diagonal = NP04 better)")
for ax in axes:
    ax.legend(frameon=False)
    ax.grid(alpha=0.25, lw=0.5)
fig.suptitle("PDHD SPE-template comparison, runs 27305/27980/28084/29107 "
             "(170k selected pulses)", y=1.0)
fig.tight_layout()
fig.savefig(f"{PLOTS}/fig_summary_scatter.png", dpi=130)
plt.close(fig)

# ---------------------------------------------------------------- fig 2
fig, axes = plt.subplots(2, 1, figsize=(13, 6.5), sharex=True)
for ax, key, lab in ((axes[0], "d_u_v1",
                      "improvement in |undershoot|/peak  (v1 - NP04)"),
                     (axes[1], "d_negfrac_v1",
                      "improvement in tail neg. area / prompt  (v1 - NP04)")):
    for c in CHS:
        rec = rows[c]["recommended"] == "np04"
        ax.bar(c, f(c, key), width=0.85, color=C[rows[c]["vendor"]],
               alpha=1.0 if rec else 0.35)
    ax.axhline(0, color="k", lw=0.7)
    ax.set_ylabel(lab, fontsize=9)
    ax.grid(alpha=0.25, lw=0.5, axis="y")
    for x in (40, 80):
        ax.axvline(x - 0.5, color="0.4", lw=0.7, ls="--")
axes[1].set_xlabel("OpChannel")
axes[0].set_ylim(-0.08, None)
for x, t in ((20, "APA4"), (60, "APA3"), (100, "APA2")):
    axes[0].annotate(t, (x, axes[0].get_ylim()[1] * 0.9), ha="center")
h = [plt.Rectangle((0, 0), 1, 1, color=C["FBK"]),
     plt.Rectangle((0, 0), 1, 1, color=C["HPK"]),
     plt.Rectangle((0, 0), 1, 1, color="0.5", alpha=0.35)]
axes[0].legend(h, ["FBK", "HPK", "faded = keep v1"], frameon=False, loc="upper right")
axes[0].set_title("Positive = vendor-average template better; solid bars = "
                  "recommended NP04 (67 channels)")
fig.tight_layout()
fig.savefig(f"{PLOTS}/fig_channel_profile.png", dpi=130)
plt.close(fig)

# ---------------------------------------------------------------- fig 3
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
for vend in ("FBK", "HPK"):
    sel = [c for c in CHS if rows[c]["vendor"] == vend]
    x = [float(kern[("v1", c)]["net_over_pos"]) for c in sel]
    axes[0].scatter(x, [f(c, "d_u_v1") for c in sel], s=22, c=C[vend],
                    label=vend, alpha=0.85, edgecolors="none")
    axes[1].scatter(x, [f(c, "d_negfrac_v1") for c in sel], s=22, c=C[vend],
                    alpha=0.85, edgecolors="none")
axes[0].set(xlabel="v1 SPE kernel net area / positive area (DC balance)",
            ylabel="improvement in |undershoot|/peak with NP04")
axes[1].set(xlabel="v1 SPE kernel net area / positive area (DC balance)",
            ylabel="improvement in tail neg. area / prompt with NP04")
for ax in axes:
    ax.axhline(0, color="k", lw=0.7)
    ax.axvline(0, color="k", lw=0.7)
    ax.grid(alpha=0.25, lw=0.5)
axes[0].legend(frameon=False)
fig.suptitle("Mechanism: kernels with positive net area (not DC-balanced) "
             "produce the undershoot", y=1.0)
fig.tight_layout()
fig.savefig(f"{PLOTS}/fig_mechanism.png", dpi=130)
plt.close(fig)

# ---------------------------------------------------------------- fig 4
worst = sorted(CHS, key=lambda c: -f(c, "d_u_v1"))[:6]
fig, axes = plt.subplots(2, 3, figsize=(13, 6.5), sharex=True)
for ax, ch in zip(axes.ravel(), worst):
    for ver in ("v1", "v0", "np04"):
        h = kwf[f"{ver}_ch{ch}"]
        ax.plot(np.arange(len(h)) * 0.016, h / h.max(), color=C[ver],
                lw=1.1, label=ver if ch == worst[0] else None,
                ls="--" if ver == "v0" else "-")
    ax.axhline(0, color="k", lw=0.5)
    ax.set_title(f"opch {ch}  ({rows[ch]['vendor']}, APA{rows[ch]['apa']})",
                 fontsize=10)
    ax.set_xlim(0, 9)
    ax.grid(alpha=0.25, lw=0.5)
for ax in axes[1]:
    ax.set_xlabel("t [us]")
for ax in axes[:, 0]:
    ax.set_ylabel("SPE kernel / peak")
fig.legend(loc="upper right", frameon=False)
fig.suptitle("SPE kernels, worst channels: the v1/v0 undershoot lobe is too "
             "shallow (kernel net area >> 0, true AC-coupled response "
             "integrates to ~0); NP04 vendor average is DC-balanced")
fig.tight_layout()
fig.savefig(f"{PLOTS}/fig_kernels_worst.png", dpi=130)
plt.close(fig)

# ---------------------------------------------------------------- fig 5
geo = uproot.open(GEO_FILE)["flashopdet/opdet_geo"].arrays(library="np")
fig, axes = plt.subplots(1, 3, figsize=(13.5, 5), sharey=True)
apas = {4: (0, 40), 3: (40, 80), 2: (80, 120)}
for ax, (apa, (lo, hi)) in zip(axes, apas.items()):
    for ch in range(lo, hi):
        z, y = geo["z"][ch], geo["y"][ch]
        if ch not in rows:
            ax.scatter(z, y, marker="x", s=45, c="0.55")
            continue
        rec = rows[ch]["recommended"]
        col = C["np04"] if rec == "np04" else "0.75"
        d = f(ch, "d_u_v1")
        ax.scatter(z, y, s=140, c=col, edgecolors="0.3", linewidths=0.5)
        ax.annotate(str(ch), (z, y), ha="center", va="center", fontsize=6)
    ax.set_title(f"APA{apa}  (opch {lo}-{hi-1})")
    ax.set_xlabel("z [cm]")
axes[0].set_ylabel("y [cm]")
h = [plt.Line2D([], [], marker="o", ls="", ms=10, c=C["np04"]),
     plt.Line2D([], [], marker="o", ls="", ms=10, c="0.75"),
     plt.Line2D([], [], marker="x", ls="", ms=8, c="0.55")]
fig.legend(h, ["switch to NP04 vendor template (67)",
               "keep v1 per-channel (46)", "dead/noisy (no deco)"],
           loc="lower center", ncol=3, frameon=False)
fig.suptitle("Recommended interim SPE template per channel (APA1 full-stream "
             "not deconvolved)")
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(f"{PLOTS}/fig_apa_map.png", dpi=130)
plt.close(fig)

# ------------------------------------------------- per-channel overlays
def draw_channel(ax_full, ax_zoom, ch):
    for ver in ("v1", "v0", "np04"):
        k = f"{ver}_ch{ch}"
        if k not in mp:
            return
        n = int(mp[f"{ver}_n_ch{ch}"])
        for ax in (ax_full, ax_zoom):
            ax.plot(TAIL_T, mp[k], color=C[ver], lw=1.0,
                    label=f"{ver} (n={n})" if ax is ax_full else None)
    for ax in (ax_full, ax_zoom):
        ax.axhline(0, color="k", lw=0.4)
        ax.grid(alpha=0.2, lw=0.4)
    ax_zoom.set_ylim(-0.35, 0.15)


for ch in CHS:
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    draw_channel(a1, a2, ch)
    a1.legend(frameon=False, fontsize=8)
    a1.set_ylabel("median pulse / peak")
    a2.set_ylabel("zoom on tail")
    a2.set_xlabel("t - t_peak [us]")
    a1.set_title(f"opch {ch}  ({rows[ch]['vendor']}, APA{rows[ch]['apa']})  "
                 f"—  recommended: {rows[ch]['recommended']}")
    fig.tight_layout()
    fig.savefig(f"{PLOTS}/channel_overlays/ch{ch:03d}.png", dpi=110)
    plt.close(fig)

# contact sheets per APA (5 x 8 grid, tail zoom only)
for apa, (lo, hi) in apas.items():
    chs = [c for c in range(lo, hi) if c in rows]
    fig, axes = plt.subplots(8, 5, figsize=(15, 17), sharex=True, sharey=True)
    for ax in axes.ravel():
        ax.set_visible(False)
    for i, ch in enumerate(sorted(chs)):
        ax = axes.ravel()[i]
        ax.set_visible(True)
        for ver in ("v1", "v0", "np04"):
            ax.plot(TAIL_T, mp[f"{ver}_ch{ch}"], color=C[ver], lw=0.9)
        ax.axhline(0, color="k", lw=0.4)
        ax.set_ylim(-0.35, 0.2)
        rec = rows[ch]["recommended"]
        ax.set_title(f"ch {ch} ({rows[ch]['vendor']})"
                     + ("  -> NP04" if rec == "np04" else ""),
                     fontsize=8,
                     color=(C["np04"] if rec == "np04" else "0.2"))
        ax.tick_params(labelsize=7)
    handles = [plt.Line2D([], [], color=C[v], lw=1.5) for v in
               ("v1", "v0", "np04")]
    fig.legend(handles, ["v1", "v0", "NP04"], loc="upper right", ncol=3,
               frameon=False)
    fig.suptitle(f"APA{apa}: median deconvolved pulse / peak; "
                 "y in [-0.35, 0.2], x = t-t_peak [us]", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(f"{PLOTS}/fig_overlays_apa{apa}.png", dpi=110)
    plt.close(fig)

print("all plots written to", PLOTS)
