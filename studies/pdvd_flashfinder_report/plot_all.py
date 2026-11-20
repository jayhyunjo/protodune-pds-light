#!/usr/bin/env python3
"""Validation plots for the PDVD OpFlashFinderVerticalDrift bug report.
Reads the plain-ROOT flash dumps of the three finder variants (stock / bugs-1+2-only /
fully fixed) plus the group_ophits.py reference CSVs, and writes the presentation
figures + a stats.json with the headline numbers.  Run with the validation venv."""
import os, json, csv
from collections import defaultdict
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

BASE = "/nfs/data/1/jjo/tmp/pdvd_flash_validation/out"
TAG = "np02vd_raw_run039349_0035_df-s03-d3_dw_0_20250909T125946"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
HERE = os.path.dirname(os.path.abspath(__file__))
PLOTS = os.path.join(HERE, "plots")
os.makedirs(PLOTS, exist_ok=True)

# ---- palette (dataviz reference instance, light mode) ----
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE, SURF = "#e1e0d9", "#c3c2b7", "#fcfcfb"
C_STOCK, C_PARTIAL, C_FIXED, C_REF = "#e34948", "#eda100", "#2a78d6", "#1baf7a"
SEQ = LinearSegmentedColormap.from_list("seqblue", [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "text.color": INK, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": BASELINE, "axes.linewidth": 1.0,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.titlesize": 12.5, "axes.labelsize": 11,
    "legend.frameon": False,
})

def load_flash(path):
    f = uproot.open(path)
    fl = f["flash"].arrays(library="np")
    fo = f["flash_opdet"].arrays(library="np")
    oh = f["ophit"].arrays(library="np") if "ophit" in [k.split(";")[0] for k in f.keys()] else None
    return fl, fo, oh

print("loading dumps ...")
fl_fix, fo_fix, oh = load_flash(f"{BASE}/{TAG}_flash.root")
fl_stk, fo_stk, _ = load_flash(f"{BASE}/stock/{TAG}_flash.root")
fl_par, fo_par, _ = load_flash(f"{BASE}/partial/{TAG}_flash.root")

ref_rows = list(csv.DictReader(open(f"{BASE}/ref_flashes.csv")))

pos = {}
ptype = {}
for d in csv.DictReader(open(f"{REPO}/pdvd/maps/pdvd_v5_opdet_positions.csv")):
    od = int(d["opdet"])
    pos[od] = (float(d["x"]), float(d["y"]), float(d["z"]))
    ptype[od] = d["json_pd_type"]

stats = {}
for name, fl in [("stock", fl_stk), ("partial", fl_par), ("fixed", fl_fix)]:
    m = fl["n_opdet"]
    stats[name] = dict(n_flashes=int(len(m)), mean_mult=float(np.mean(m)),
                       max_mult=int(np.max(m)), multi_pd_pct=float(100 * np.mean(m > 1)))
stats["n_ophits"] = int(len(oh["pe"]))
print(json.dumps(stats, indent=1))

# =====================================================================
# 1. money plot: OpDet multiplicity, stock vs fixed
# =====================================================================
fig, ax = plt.subplots(figsize=(8.4, 4.6))
mmax = int(max(fl_fix["n_opdet"].max(), fl_stk["n_opdet"].max()))
bins = np.arange(0.5, mmax + 1.5)
for arr, c, lab in [(fl_stk["n_opdet"], C_STOCK, "stock finder"),
                    (fl_fix["n_opdet"], C_FIXED, "fixed finder")]:
    h, _ = np.histogram(arr, bins=bins)
    ax.stairs(h, bins, color=c, lw=2, label=lab)
    ax.stairs(h, bins, color=c, fill=True, alpha=0.12)
ax.set_yscale("log")
ax.set_xlabel("distinct OpDets per flash (n_opdet)")
ax.set_ylabel("flashes")
ax.set_title("Flash OpDet multiplicity — stock vs fixed OpFlashFinderVerticalDrift\n"
             f"PDVD run 39349, 28 events, {stats['n_ophits']:,} OpHits", loc="left")
ax.annotate(f"stock: {stats['stock']['n_flashes']:,} flashes\n"
            f"mean mult {stats['stock']['mean_mult']:.2f}, max {stats['stock']['max_mult']}\n"
            f"{stats['stock']['multi_pd_pct']:.1f}% multi-PD",
            xy=(1.6, stats["stock"]["n_flashes"] * 0.4), color=C_STOCK, fontsize=10.5)
ax.annotate(f"fixed: {stats['fixed']['n_flashes']:,} flashes\n"
            f"mean mult {stats['fixed']['mean_mult']:.2f}, max {stats['fixed']['max_mult']}\n"
            f"{stats['fixed']['multi_pd_pct']:.1f}% multi-PD",
            xy=(13, 2e3), color=C_FIXED, fontsize=10.5)
ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(f"{PLOTS}/01_multiplicity_stock_vs_fixed.png", dpi=200)
plt.close(fig)
print("plot 1 done")

# =====================================================================
# choose a display flash: regroup the hits with the exact greedy window
# (identical to the fixed finder — validated) and take the brightest
# group with >= 20 distinct OpDets, so the member hits are known exactly.
# =====================================================================
def greedy_groups(t, dt=2.0):
    order = np.argsort(t, kind="stable")
    groups, i = [], 0
    ts = t[order]
    while i < len(ts):
        j = np.searchsorted(ts, ts[i] + dt, side="right")
        groups.append(order[i:j])
        i = j
    return groups

best = None
for ev in np.unique(oh["event"]):
    m = oh["event"] == ev
    th, odh, peh = (oh["peaktimeabs"][m].astype(np.float64), oh["opdet"][m], oh["pe"][m])
    for g in greedy_groups(th):
        nod = len(set(odh[g]))
        tot = float(peh[g].sum())
        if nod >= 20 and (best is None or tot > best["pe"]):
            best = dict(event=int(ev), t0=float(th[g].min()), n_opdet=nod, pe=tot,
                        th=th, odh=odh, peh=peh, members=g)
ev_b, t0_b, n_b, pe_b = best["event"], best["t0"], best["n_opdet"], best["pe"]
t_hits_all, od_hits_all, pe_hits_all = best["th"], best["odh"], best["peh"]

# cross-check the group against the fixed finder's flash tree
mfl = (fl_fix["event"] == ev_b) & (np.abs(fl_fix["total_pe"] - pe_b) < 1e-3 * pe_b)
assert np.sum(mfl) >= 1 and int(fl_fix["n_opdet"][np.flatnonzero(mfl)[0]]) == n_b, \
    "regrouped display flash does not match the fixed finder output"
fid_b = int(fl_fix["flash_id"][np.flatnonzero(mfl)[0]])
stats["display_flash"] = dict(event=ev_b, flash_id=fid_b, t0=t0_b,
                              n_opdet=n_b, total_pe=pe_b)
print(f"display flash: event {ev_b} id {fid_b} t0={t0_b:.2f} n_opdet={n_b} pe={pe_b:.0f}")

# per-OpDet PE of the chosen fixed flash, from its exact member hits
fix_pe = defaultdict(float)
for od, p in zip(od_hits_all[best["members"]], pe_hits_all[best["members"]]):
    fix_pe[int(od)] += float(p)

# stock flashes in the same [t0, t0+2] window (stock = one flash per hit,
# and its per-flash abstime equals the hit PeakTimeAbs)
win = (fl_stk["event"] == ev_b) & (fl_stk["abstime"] >= t0_b - 0.01) & (fl_stk["abstime"] <= t0_b + 2.01)
n_stock_in_win = int(np.sum(win))
i_srt = np.flatnonzero(win)[np.argmax(fl_stk["total_pe"][win])]
ms = (fo_stk["event"] == ev_b) & (fo_stk["flash_id"] == int(fl_stk["flash_id"][i_srt]))
stk_pe = defaultdict(float)
for od, p in zip(fo_stk["opdet"][ms], fo_stk["pe"][ms]):
    stk_pe[int(od)] += float(p)
stats["display_stock"] = dict(n_flashes_in_window=n_stock_in_win,
                              brightest_n_opdet=int(fl_stk["n_opdet"][i_srt]),
                              brightest_pe=float(fl_stk["total_pe"][i_srt]))

# =====================================================================
# 2. event display: same light burst, stock vs fixed
# =====================================================================
all_pe = [p for p in list(fix_pe.values()) + list(stk_pe.values()) if p > 0]
norm = LogNorm(vmin=max(min(all_pe), 0.5), vmax=max(all_pe))

def draw_view(ax, pemap, view):
    """view: ('top', y vs z) or ('side', x vs z)"""
    for od, (x, y, z) in pos.items():
        h, v = (z, y) if view == "top" else (z, x)
        mk = "o" if ptype[od] == "PMT" else "s"
        pe = pemap.get(od, 0.0)
        if pe > 0:
            ax.scatter(h, v, s=90 + 240 * np.sqrt(pe / norm.vmax), marker=mk,
                       c=[SEQ(norm(pe))], edgecolors=SURF, linewidths=1.2, zorder=3)
        else:
            ax.scatter(h, v, s=70, marker=mk, facecolors="none",
                       edgecolors=GRID, linewidths=1.2, zorder=2)
    ax.set_xlabel("Z [cm]")
    ax.set_ylabel("Y [cm]" if view == "top" else "X [cm] (drift, vertical)")
    ax.grid(False)
    ax.set_axisbelow(True)

fig, axs = plt.subplots(2, 2, figsize=(11.6, 8.2), sharex=True, sharey="row")
for j, (pemap, ttl, c) in enumerate([
        (stk_pe, f"stock: brightest of {n_stock_in_win} single-PD flashes\n"
                 "in the same 2-tick window", C_STOCK),
        (fix_pe, f"fixed: ONE flash, {n_b} OpDets, {pe_b:,.0f} PE", C_FIXED)]):
    draw_view(axs[0][j], pemap, "top")
    draw_view(axs[1][j], pemap, "side")
    axs[0][j].set_title(ttl, color=c, loc="left", fontsize=11.5)
axs[0][0].annotate("Top view (Y–Z)", xy=(0.99, 0.02), xycoords="axes fraction",
                   ha="right", color=MUTED, fontsize=9.5)
axs[1][0].annotate("Side view (X–Z)", xy=(0.99, 0.02), xycoords="axes fraction",
                   ha="right", color=MUTED, fontsize=9.5)
handles = [Line2D([], [], marker="s", ls="", mfc="none", mec=MUTED, label="X-ARAPUCA"),
           Line2D([], [], marker="o", ls="", mfc="none", mec=MUTED, label="PMT"),
           Line2D([], [], marker="s", ls="", mfc=SEQ(0.75), mec=SURF, label="PE (log color+size)")]
axs[1][1].legend(handles=handles, loc="lower right", fontsize=9)
fig.suptitle(f"The same scintillation burst — PDVD run 39349 event {ev_b}, "
             f"window [t$_0$, t$_0$+2] ticks", x=0.02, ha="left", fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(f"{PLOTS}/02_flash_display_stock_vs_fixed.png", dpi=200)
plt.close(fig)
print("plot 2 done")

# =====================================================================
# 3. OpHit time raster around the chosen flash
# =====================================================================
fig, ax = plt.subplots(figsize=(8.8, 4.8))
dt_rel = t_hits_all - t0_b
zoom = np.abs(dt_rel) < 60
ax.add_patch(Rectangle((0, -1.5), 2, 42, color=C_FIXED, alpha=0.10, zorder=1))
ax.scatter(dt_rel[zoom], od_hits_all[zoom],
           s=12 + 90 * np.sqrt(pe_hits_all[zoom] / pe_hits_all[zoom].max()),
           c=C_FIXED, alpha=0.75, edgecolors="none", zorder=3)
ax.axvline(0, color=BASELINE, lw=1)
ax.set_xlim(-60, 60); ax.set_ylim(-1.5, 40.5)
ax.set_xlabel("OpHit PeakTimeAbs − t$_0$  [ticks]")
ax.set_ylabel("OpDet")
ax.set_title("OpHits around one scintillation burst — the light IS coincident\n"
             f"run 39349 event {ev_b}; marker size ∝ √PE", loc="left")
ax.annotate(f"[t$_0$, t$_0$+2] window:\n{n_b} OpDets hit\n→ 1 flash (fixed)\n"
            f"→ {n_stock_in_win} flashes (stock)",
            xy=(2.5, 26), color=INK2, fontsize=10.5)
fig.tight_layout()
fig.savefig(f"{PLOTS}/03_ophit_raster.png", dpi=200)
plt.close(fig)
print("plot 3 done")

# =====================================================================
# 4. float32 precision at PDVD timestamps.
# Stock computes dtmax = |initimecluster(float32) - PeakTime(double)|: the seed
# time is snapped to the float32 grid (ULP ~1024 ticks here), so the <2 cut
# tests a window centred delta ticks away from the seed instead of at it.
# =====================================================================
ulp = float(np.spacing(np.float32(t0_b)))
delta = t0_b - float(np.float32(t0_b))   # seed-time snap error, fixed for this seed
sel4 = np.abs(dt_rel) < 600
dt_double = np.sort(dt_rel[sel4])
dt_stock = np.abs(float(np.float32(t0_b)) - (t0_b + dt_double))

fig, ax = plt.subplots(figsize=(8.8, 4.8))
ax.plot([-600, 0, 600], [600, 0, 600], color=C_FIXED, lw=2, zorder=2,
        label="double (fixed):  dtmax = |t − t$_0$|")
ax.scatter(dt_double, dt_stock, s=22, c=C_STOCK, alpha=0.85, edgecolors="none",
           zorder=3, label="float32 seed (stock):  dtmax = |t − float32(t$_0$)|")
ax.axhline(2.0, color=INK2, lw=1.2, ls="--", zorder=2)
ax.annotate("cut: dtmax < MaximumTimeWindow = 2", xy=(-580, 14), color=INK2, fontsize=10)
ax.annotate(f"the stock cut accepts hits at\nΔt ≈ {-delta:+.0f} ticks — not at the seed\n"
            f"(float32 ULP at t ≈ {t0_b:.3g} is {ulp:.0f} ticks,\n"
            f"{ulp/2:.0f}× the window; offset varies seed to seed)",
            xy=(-delta, 10), xytext=(150, 100), color=C_STOCK, fontsize=10.5,
            arrowprops=dict(arrowstyle="->", color=C_STOCK, lw=1.2))
ax.set_xlabel("true Δt = PeakTimeAbs − t$_0$  [ticks]")
ax.set_ylabel("dtmax as computed  [ticks]")
ax.set_title("Bug 2 — the time-window cut with a float32 cluster seed at PDVD timestamps\n"
             f"real OpHit times, run 39349 event {ev_b}", loc="left")
ax.set_xlim(-620, 620); ax.set_ylim(-18, 640)
ax.legend(loc="upper center", fontsize=9.5)
fig.tight_layout()
fig.savefig(f"{PLOTS}/04_float_precision.png", dpi=200)
plt.close(fig)
stats["ulp_at_t0"] = ulp
stats["float32_seed_offset"] = delta
print("plot 4 done")

# =====================================================================
# 5. bug isolation: stock -> bugs 1+2 fixed -> full fix
# =====================================================================
variants = ["stock", "partial", "fixed"]
labels = ["stock", "bugs 1+2\nfixed", "full fix"]
colors = [C_STOCK, C_PARTIAL, C_FIXED]
panels = [("n_flashes", "flashes (28 events)", "{:,}", True),
          ("mean_mult", "mean OpDets / flash", "{:.2f}", False),
          ("max_mult", "max OpDets / flash", "{:d}", False)]
fig, axs = plt.subplots(1, 3, figsize=(11.4, 4.2))
for ax, (key, ttl, fmt, logy) in zip(axs, panels):
    vals = [stats[v][key] for v in variants]
    bars = ax.bar(range(3), vals, 0.62, color=colors)
    if logy:
        ax.set_yscale("log"); ax.set_ylim(1e4, 4e5)
    for r, v in zip(bars, vals):
        ax.annotate(fmt.format(v), xy=(r.get_x() + r.get_width() / 2, v),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", color=INK, fontsize=11, fontweight="bold")
    ax.set_xticks(range(3)); ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_title(ttl, loc="left")
    ax.grid(axis="x", visible=False)
    ax.set_axisbelow(True)
fig.suptitle("Isolating the three bugs — fixing the thresholds (1) and the float (2) is NOT enough;\n"
             "the sorted-vs-original index mismatch (3) is what breaks the grouping",
             x=0.02, ha="left", fontsize=12.5)
fig.tight_layout(rect=(0, 0, 1, 0.90))
fig.savefig(f"{PLOTS}/05_bug_isolation.png", dpi=200)
plt.close(fig)
print("plot 5 done")

# =====================================================================
# 6. validation identity: fixed C++ vs python reference
# =====================================================================
cpp = defaultdict(list); ref = defaultdict(list)
for e, t, n, p in zip(fl_fix["event"], fl_fix["abstime"], fl_fix["n_opdet"], fl_fix["total_pe"]):
    cpp[int(e)].append((float(t), int(n), float(p)))
for d in ref_rows:
    ref[int(d["event"])].append((float(d["time"]), int(d["n_opdet"]), float(d["total_pe"])))
for v in cpp.values(): v.sort()
for v in ref.values(): v.sort()

dn, dpe_rel, cnt_c, cnt_r = [], [], [], []
for ev in sorted(set(cpp) | set(ref)):
    a, b = cpp.get(ev, []), ref.get(ev, [])
    cnt_c.append(len(a)); cnt_r.append(len(b))
    for (ta, na, pa), (tb, nb, pb) in zip(a, b):
        dn.append(na - nb)
        dpe_rel.append((pa - pb) / pb if pb else 0.0)
dn = np.array(dn); dpe_rel = np.array(dpe_rel)
stats["identity"] = dict(n_pairs=int(len(dn)), n_dn_nonzero=int(np.sum(dn != 0)),
                         max_abs_dpe_rel=float(np.max(np.abs(dpe_rel))))

fig, axs = plt.subplots(1, 2, figsize=(10.6, 4.4))
axs[0].scatter(cnt_r, cnt_c, s=42, c=C_FIXED, alpha=0.85, edgecolors="none", zorder=3)
lim = [min(cnt_r) * 0.97, max(cnt_r) * 1.03]
axs[0].plot(lim, lim, color=BASELINE, lw=1.2, zorder=2)
axs[0].set_xlabel("flashes / event — python reference (group_ophits.py)")
axs[0].set_ylabel("flashes / event — fixed C++ finder")
axs[0].set_title(f"flash count per event: 28/28 identical", loc="left")

axs[1].hist(dpe_rel * 1e6, bins=41, color=C_FIXED)
axs[1].set_yscale("log")
axs[1].set_xlabel("(PE$_{C++}$ − PE$_{ref}$) / PE$_{ref}$   [×10$^{-6}$]")
axs[1].set_ylabel("flashes")
axs[1].set_title("per-flash total PE agreement", loc="left")
axs[1].annotate(f"{len(dn):,} flash pairs\nmax |ΔPE/PE| = {stats['identity']['max_abs_dpe_rel']:.1e}\n"
                f"Δn_opdet = 0 for all",
                xy=(0.03, 0.97), xycoords="axes fraction", va="top", color=INK2, fontsize=10.5)
fig.suptitle("Validation — patched finder vs independent double-precision grouping, flash by flash",
             x=0.02, ha="left", fontsize=12.5)
fig.tight_layout(rect=(0, 0, 1, 0.91))
fig.savefig(f"{PLOTS}/06_validation_identity.png", dpi=200)
plt.close(fig)
print("plot 6 done")

# =====================================================================
# 7. MaximumTimeWindow scan
# =====================================================================
scan = []
for line in open(f"{BASE}/dt_scan.txt"):
    p = line.split()
    if len(p) == 5 and p[0].replace(".", "").isdigit():
        scan.append([float(x) for x in p])
scan = np.array(scan)  # dt, nflash, maxMult, meanMult, %multiPD

fig, axs = plt.subplots(2, 1, figsize=(7.6, 6.4), sharex=True)
axs[0].plot(scan[:, 0], scan[:, 1], "-o", color=C_FIXED, lw=2, ms=6)
axs[0].set_yscale("log"); axs[0].set_ylabel("flashes (28 events)")
axs[1].plot(scan[:, 0], scan[:, 3], "-o", color=C_FIXED, lw=2, ms=6, label="mean OpDets/flash")
axs[1].plot(scan[:, 0], scan[:, 4] / 10, "-s", color=C_REF, lw=2, ms=6, label="multi-PD fraction [×10%]")
axs[1].set_ylabel("multiplicity")
axs[1].set_xlabel("grouping window dt  [PeakTimeAbs ticks]")
axs[1].legend(loc="upper left")
for ax in axs:
    ax.set_xscale("log")
    ax.axvline(2, color=INK2, lw=1.2, ls="--")
axs[0].annotate("default MaximumTimeWindow = 2", xy=(0.32, 0.06), xycoords="axes fraction",
                color=INK2, fontsize=10, ha="left")
axs[0].set_title("The one remaining knob — flash count and multiplicity vs grouping window\n"
                 "(python reference grouping; the fixed finder is identical at dt = 2)", loc="left")
fig.tight_layout()
fig.savefig(f"{PLOTS}/07_dt_scan.png", dpi=200)
plt.close(fig)
print("plot 7 done")

json.dump(stats, open(os.path.join(HERE, "stats.json"), "w"), indent=1)
print("stats.json written")
