#!/usr/bin/env python3
"""
flash_viewer.py - browse PDS light flash-by-flash from a PDHD '*_final.root'
(full file) or 'run*_viewer.root' (slim file).

Single window:
    cols 0-1 : YZ hit maps   row0 = RAW (+x,-x)   row1 = DECONV (+x,-x)
    col  2   : waveform of the CLICKED PD   row0 = raw   row1 = deconvolved
Click a PD circle -> the waveform column shows that channel's raw + deconvolved
waveform for the current flash's event, and follows that channel as you navigate.

Waveform sources (full *_final.root): raw from rawdump/raw_waveform; deconvolved
from decodump/deco_waveform (uncapped) if present, else decoana (capped).

NAVIGATION:  ←/→ ±1 | ↑/↓ ±10 | pgup/pgdn ±50 | ]/[ ±100 | home/end |
             t = raw integral<->peak | l = channel labels | s = save | q = quit
HEADLESS:    --batch N --out f.png | --list | --probe EV:CH [--out wf.png]
OPTIONS:     --start N | --min-pd K | --raw {integral,peak}
REQUIRES:    numpy, matplotlib, and uproot ('pip install uproot') OR pyROOT.
"""
import argparse, os, re
from collections import defaultdict

APA_OF = lambda ch: {0: "APA4", 1: "APA3", 2: "APA2", 3: "APA1"}[ch // 40]

VENDOR = {}  # OpChannel -> "HPK"/"FBK", loaded from a vendor file if found

# dead/noisy channels the deconvolution drops (its IgnoreChannels MINUS the APA1
# full-stream block 120-159) -> drawn with a red x so bad PDs are visible.
BAD_CHANNELS = {3, 86, 87, 97, 107, 116, 117}


def load_vendor(path):
    """Read 'opch vendor' lines (e.g. '12 HPK'); '#' comments allowed."""
    d = {}
    try:
        for ln in open(path):
            parts = ln.split("#")[0].split()
            if len(parts) >= 2 and parts[0].lstrip("-").isdigit():
                d[int(parts[0])] = parts[1]
    except Exception:
        pass
    return d


class LazyWf:
    """Per-(event,channel) waveform trace near a flash AbsTime, from a flat
    'adc' tree (rawdump/raw_waveform or decodump/deco_waveform); ADC read once."""
    def __init__(self, backend, tree, idx):
        self.backend, self.tree, self.idx = backend, tree, idx
        self.cache, self.tracecache, self.file = {}, {}, None

    def _adc(self, entry):
        import numpy as np
        if self.backend == "uproot":
            return np.asarray(self.tree["adc"].array(entry_start=entry, entry_stop=entry + 1,
                                                      library="np")[0], dtype=np.float64)
        self.tree.GetEntry(entry)
        return np.asarray(self.tree.adc, dtype=np.float64)

    def _match(self, event, ch, abstime):
        recs = self.idx.get((event, ch))
        if not recs:
            return None
        best, bestdt = None, None
        for rec in recs:                            # rec = (ts, ns, entry)
            ts, ns, _ = rec
            if ts <= abstime <= ts + ns:
                return rec
            dt = (ts - abstime) if abstime < ts else (abstime - (ts + ns))
            if bestdt is None or dt < bestdt:
                bestdt, best = dt, rec
        return best if (bestdt is None or bestdt <= 2048) else None

    def get(self, event, ch, abstime):
        rec = self._match(event, ch, abstime)
        if rec is None:
            return None
        e = rec[2]
        if e in self.cache:
            return self.cache[e]
        import numpy as np
        a = self._adc(e); base = np.median(a[:100])
        r = (float(a.max() - base), float(np.clip(a - base, 0, None).sum()))
        self.cache[e] = r
        return r

    def trace(self, event, ch, abstime, half_us=8.0):
        """Return (t_us, adc), or None. For a long full-stream record (APA1,
        ~343808 samp) return a zoom window centred on the flash time (t=0=flash)."""
        import numpy as np
        rec = self._match(event, ch, abstime)
        if rec is None:
            return None
        ts, ns, e = rec
        if e not in self.tracecache:
            self.tracecache[e] = self._adc(e)
        a = self.tracecache[e]
        if ns > 5000:                               # full-stream -> zoom around the flash
            off = int(round(abstime - ts))
            half = int(half_us / 0.016)
            lo = max(0, off - half); hi = min(len(a), off + half)
            return (np.arange(lo, hi) - off) * 0.016, a[lo:hi]
        return np.arange(len(a)) * 0.016, a

    def traces_for(self, ch, cap=1500):
        """All (self-trigger) deconvolved ADC traces for one channel across the whole
        file (for the per-channel overlay/persistence view); reads up to `cap` records."""
        import numpy as np
        es = [e for (ev, c), recs in self.idx.items() if c == ch
              for (ts, ns, e) in recs if ns < 5000]
        if cap and len(es) > cap:
            step = len(es) / cap
            es = [es[int(i * step)] for i in range(cap)]
        out = []
        for e in es:
            try:
                out.append(self._adc(e))
            except Exception:
                pass
        return out


def _build_lazy_uproot(f, path):
    rw = f[path]
    sc = rw.arrays(["event", "opch", "timestamp", "nsamples"], library="np")
    idx = defaultdict(list)
    for i in range(len(sc["event"])):
        idx[(int(sc["event"][i]), int(sc["opch"][i]))].append(
            (float(sc["timestamp"][i]), int(sc["nsamples"][i]), i))   # ALL records incl. APA1 full-stream
    lz = LazyWf("uproot", rw, idx); lz.file = f
    return lz


def _build_lazy_pyroot(tf, path):
    rw = tf.Get(path)
    if not rw:
        return None
    rw.SetBranchStatus("*", 0)
    for b in ("event", "opch", "timestamp", "nsamples"):
        rw.SetBranchStatus(b, 1)
    idx = defaultdict(list)
    for i in range(rw.GetEntries()):
        rw.GetEntry(i)
        idx[(int(rw.event), int(rw.opch))].append(
            (float(rw.timestamp), int(rw.nsamples), i))               # ALL records incl. APA1 full-stream
    rw.SetBranchStatus("adc", 1)
    lz = LazyWf("pyROOT", rw, idx); lz.file = tf
    return lz


def get_deconv_decoana(lazy_raw, run, event, ch, raw_adc):
    """Fallback deconv waveform from decoana (capped) for old files lacking deco_waveform."""
    import numpy as np
    if lazy_raw is None:
        return None
    base = f"decoana/run_{run}_evt_{event}/ch{ch}"
    target = float(np.max(raw_adc)) if raw_adc is not None else None
    if lazy_raw.backend == "uproot":
        f = lazy_raw.file
        try:
            rdir, ddir = f[base + "/raw"], f[base + "/deconv"]
        except Exception:
            return None
        rk = [k.split(";")[0] for k in rdir.keys(recursive=False) if "waveform" in k]
        if not rk:
            return None
        bestK, bestd = rk[0], None
        if target is not None:
            for k in rk:
                d = abs(float(np.max(rdir[k].values())) - target)
                if bestd is None or d < bestd:
                    bestd, bestK = d, k
        try:
            return np.asarray(ddir[bestK].values(), dtype=np.float64)
        except Exception:
            return None
    return None


def plot_waveforms(ax_raw, ax_dec, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04, run, ev, ch, abstime, npe=None):
    import numpy as np
    ax_raw.clear(); ax_dec.clear()
    if ch is None or lazy_raw is None:
        for ax in (ax_raw, ax_dec):
            ax.set_xticks([]); ax.set_yticks([])
        ax_raw.text(0.5, 0.5, "click a PD circle\nto show its waveforms", ha="center", va="center",
                    transform=ax_raw.transAxes, fontsize=10, color="gray")
        return
    def _tr(lz):
        try:
            return lz.trace(ev, ch, abstime) if lz is not None else None
        except Exception:
            return None
    raw = _tr(lazy_raw)                    # (t_us, adc) or None
    if lazy_deco is not None:
        dec = _tr(lazy_deco)
    else:                                  # old files: fall back to decoana (returns a bare array)
        try:
            arr = get_deconv_decoana(lazy_raw, run, ev, ch, raw[1] if raw is not None else None)
        except Exception:
            arr = None
        dec = (np.arange(len(arr)) * 0.016, arr) if arr is not None else None
    dec_v0 = _tr(lazy_deco_v0)
    dec_np04 = _tr(lazy_deco_np04)

    zoom = raw is not None and len(raw[0]) > 0 and raw[0][0] < 0   # full-stream zoom @ flash (APA1)
    if raw is not None:
        ax_raw.plot(raw[0], raw[1], lw=0.7, color="tab:blue")
        if zoom:
            ax_raw.axvline(0, color="gray", ls=":", lw=0.6)
            ax_raw.set_xlabel("t − t_flash (µs)", fontsize=8)
    else:
        ax_raw.text(0.5, 0.5, "no raw record near this flash", ha="center", va="center",
                    transform=ax_raw.transAxes, fontsize=9)
    vend = VENDOR.get(ch)
    vtag = f", {vend}" if vend and vend not in ("?", "UNKNOWN", "-") else ""
    rawtag = "  [full-stream — zoom @ flash]" if zoom else ""
    ax_raw.set_title(f"OpCh {ch} ({APA_OF(ch)}{vtag})  ev {ev} — RAW{rawtag}", fontsize=9)
    ax_raw.set_ylabel("raw ADC", fontsize=8); ax_raw.tick_params(labelsize=7)
    petag = f"   total PE = {npe:.1f}" if npe is not None else ""
    if dec is not None:
        ax_dec.plot(dec[0], dec[1], lw=0.8, color="tab:red", label="v1 (Jun2025)")
    if dec_v0 is not None:
        ax_dec.plot(dec_v0[0], dec_v0[1], lw=0.8, color="tab:blue", alpha=0.85, label="v0 (Nov2024)")
    if dec_np04 is not None:
        ax_dec.plot(dec_np04[0], dec_np04[1], lw=0.8, color="tab:green", alpha=0.85, label="NP04 vendor-avg")
    if dec is None and dec_v0 is None and dec_np04 is None:
        msg = ("no deconvolved waveform\n(APA1 / dead channel — raw only)"
               if raw is not None else "no deconvolved waveform")
        ax_dec.text(0.5, 0.5, msg, ha="center", va="center", transform=ax_dec.transAxes, fontsize=9)
    else:
        ax_dec.legend(fontsize=7, loc="upper right")
    ax_dec.set_title("DECONVOLVED" + petag, fontsize=9)
    ax_dec.set_xlabel("t − t_flash (µs)" if zoom else "time (µs, 16 ns/sample)", fontsize=8)
    ax_dec.set_ylabel("PE/tick", fontsize=8); ax_dec.tick_params(labelsize=7)


def load(path):
    flashes, pos, have_raw, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04 = {}, {}, False, None, None, None, None
    try:
        import uproot
        f = uproot.open(path)
        g = f["flashopdet/opdet_geo"].arrays(["opdet", "x", "y", "z"], library="np")
        pos = {int(o): (float(x), float(y), float(z))
               for o, x, y, z in zip(g["opdet"], g["x"], g["y"], g["z"])}
        t = f["opflashana/FlashBreakdownTree"].arrays(
            ["EventID", "FlashID", "OpChannel", "NPe", "AbsTime"], library="np")
        for ev, fl, ch, pe, ab in zip(t["EventID"], t["FlashID"], t["OpChannel"], t["NPe"], t["AbsTime"]):
            if pe <= 0:
                continue
            d = flashes.setdefault((int(ev), int(fl)),
                                   {"ev": int(ev), "fl": int(fl), "abstime": float(ab), "npe": {}, "raw": {}})
            d["npe"][int(ch)] = float(pe)
        try:
            r = f["rawmatch/flash_rawpe"].arrays(
                ["EventID", "FlashID", "OpChannel", "RawPeak", "RawIntegral"], library="np")
            for ev, fl, ch, pk, ig in zip(r["EventID"], r["FlashID"], r["OpChannel"], r["RawPeak"], r["RawIntegral"]):
                k = (int(ev), int(fl))
                if k in flashes:
                    flashes[k]["raw"][int(ch)] = (float(pk), float(ig))
            have_raw = True
        except Exception:
            try:
                lazy_raw = _build_lazy_uproot(f, "rawdump/raw_waveform"); have_raw = True
            except Exception:
                have_raw = False
        try:
            lazy_deco = _build_lazy_uproot(f, "decodump/deco_waveform")
        except Exception:
            lazy_deco = None
        try:
            lazy_deco_np04 = _build_lazy_uproot(f, "decodumpnp04/deco_waveform")
        except Exception:
            lazy_deco_np04 = None
        try:
            lazy_deco_v0 = _build_lazy_uproot(f, "decodumpv0/deco_waveform")
        except Exception:
            lazy_deco_v0 = None
    except ModuleNotFoundError:
        import ROOT
        tf = ROOT.TFile.Open(path)
        g = tf.Get("flashopdet/opdet_geo")
        for i in range(g.GetEntries()):
            g.GetEntry(i); pos[int(g.opdet)] = (float(g.x), float(g.y), float(g.z))
        t = tf.Get("opflashana/FlashBreakdownTree")
        for i in range(t.GetEntries()):
            t.GetEntry(i)
            if t.NPe <= 0:
                continue
            d = flashes.setdefault((int(t.EventID), int(t.FlashID)),
                                   {"ev": int(t.EventID), "fl": int(t.FlashID),
                                    "abstime": float(t.AbsTime), "npe": {}, "raw": {}})
            d["npe"][int(t.OpChannel)] = float(t.NPe)
        r = tf.Get("rawmatch/flash_rawpe")
        if r:
            for i in range(r.GetEntries()):
                r.GetEntry(i); k = (int(r.EventID), int(r.FlashID))
                if k in flashes:
                    flashes[k]["raw"][int(r.OpChannel)] = (float(r.RawPeak), float(r.RawIntegral))
            have_raw = True
        else:
            lazy_raw = _build_lazy_pyroot(tf, "rawdump/raw_waveform")
            have_raw = lazy_raw is not None
        lazy_deco = _build_lazy_pyroot(tf, "decodump/deco_waveform")
        lazy_deco_v0 = _build_lazy_pyroot(tf, "decodumpv0/deco_waveform")
        lazy_deco_np04 = _build_lazy_pyroot(tf, "decodumpnp04/deco_waveform")
    return pos, [flashes[k] for k in sorted(flashes)], have_raw, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04


def run_app(pos, flashes, run, args, have_raw, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04):
    import matplotlib
    headless = (args.batch is not None) or args.out
    if headless:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm, Normalize
    from matplotlib.cm import ScalarMappable
    import numpy as np

    px = sorted(c for c in pos if pos[c][0] > 0)
    mx = sorted(c for c in pos if pos[c][0] < 0)
    wf = lazy_raw is not None
    nmap_rows = 2 if have_raw else 1
    ncols = 3 if wf else 2

    fig = plt.figure(figsize=(20 if wf else 14, 6.8 * nmap_rows))
    gs = fig.add_gridspec(nmap_rows, ncols, width_ratios=([1, 1, 0.85] if wf else [1, 1]),
                          wspace=0.42, hspace=0.26)
    if have_raw:
        amap = [("RAW", fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])),
                ("DECONV", fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]))]
    else:
        amap = [("DECONV", fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]))]
    ax_wfr = fig.add_subplot(gs[0, 2]) if wf else None
    ax_wfd = fig.add_subplot(gs[1, 2]) if wf else None

    state = {"i": args.start, "raw": args.raw, "labels": True, "selch": None}
    axinfo = {}

    # one DEDICATED colorbar axes per hit-map panel, created ONCE so the colorbar
    # never steals space from the panel on redraw (that bug shrank the -x APA1/2
    # panels a little on every event flip).
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    caxes = {}
    for _k, _axp, _axm in amap:
        for _ax in (_axp, _axm):
            caxes[_ax] = make_axes_locatable(_ax).append_axes("right", size="4.5%", pad=0.06)

    # ---- FIXED color/size scales so the z-axis (PE color) stays constant across flashes ----
    GMIN = {"PE (deconvolved)": 1.0, "raw peak (ADC)": 5.0, "raw integral (ADC·samp)": 50.0}
    GMAX = {}
    # vmax = 99th percentile (robust to saturated outliers) so a linear 0..vmax scale
    # looks like the BEE display; the brightest few channels saturate at the top color.
    if not args.auto_scale:
        _npe = [v for d in flashes for v in d["npe"].values() if v > 0]
        GMAX["PE (deconvolved)"] = args.pe_max or (float(np.percentile(_npe, 99)) if _npe else 100.0)
        if lazy_raw is not None:
            print("computing fixed raw color scale from a sample ...", flush=True)
            rp, ri = [10.0], [100.0]
            for d in flashes[:: max(1, len(flashes) // 50)]:
                for ch in d["npe"]:
                    r = lazy_raw.get(d["ev"], ch, d["abstime"])
                    if r:
                        rp.append(r[0]); ri.append(r[1])
            GMAX["raw peak (ADC)"] = float(np.percentile(rp, 99))
            GMAX["raw integral (ADC·samp)"] = float(np.percentile(ri, 99))
        print(f"fixed color scale ({'log' if args.log_scale else 'linear 0..vmax'}): " +
              ", ".join(f"{k.split()[0]}≤{v:.0f}" for k, v in GMAX.items()), flush=True)

    def make_norm(clab):
        gmx = GMAX.get(clab) or 1.0
        if args.log_scale:
            gmn = GMIN.get(clab, 1.0)
            return LogNorm(vmin=gmn, vmax=max(gmx, gmn * 1.01))
        return Normalize(vmin=0.0, vmax=max(gmx, 1.0))

    def ensure_raw(d):
        if lazy_raw is None or d.get("_rawdone"):
            return
        for ch in list(d["npe"]):
            r = lazy_raw.get(d["ev"], ch, d["abstime"])
            if r:
                d["raw"][ch] = r
        d["_rawdone"] = True

    def apa_labels(ax, chs):
        seen = {}
        for c in chs:
            seen.setdefault(APA_OF(c), []).append(pos[c][2])
        for name, zs in seen.items():
            ax.text(sum(zs) / len(zs), 590, name, ha="center", va="bottom",
                    fontsize=9, color="steelblue", fontweight="bold")

    def value_map(d, kind):
        if kind == "npe":
            return d["npe"], "PE (deconvolved)"
        i = 0 if state["raw"] == "peak" else 1
        return {c: v[i] for c, v in d["raw"].items()}, \
               ("raw peak (ADC)" if state["raw"] == "peak" else "raw integral (ADC·samp)")

    def panel(ax, chs, vmap, title, clab):
        ax.clear(); axinfo[ax] = chs
        if chs:
            ax.scatter([pos[c][2] for c in chs], [pos[c][1] for c in chs],
                       s=12, facecolors="none", edgecolors="lightgray", linewidths=0.5)
            if state["labels"]:
                for c in chs:
                    ax.text(pos[c][2], pos[c][1] - 22, str(c), ha="center", va="top", fontsize=4.5, color="gray")
        bad = [c for c in chs if c in BAD_CHANNELS]
        if bad:
            ax.scatter([pos[c][2] for c in bad], [pos[c][1] for c in bad],
                       marker="x", s=55, color="red", linewidths=1.6, zorder=5)
        lit = [c for c in chs if vmap.get(c, 0) > 0]; sc = None
        if lit:
            v = [vmap[c] for c in lit]
            gmx = GMAX.get(clab) or max(v)
            sc = ax.scatter([pos[c][2] for c in lit], [pos[c][1] for c in lit], c=v,
                            s=[45 + 255 * min(1.0, x / gmx) for x in v], cmap="viridis",
                            norm=make_norm(clab),
                            edgecolors="k", linewidths=0.4, zorder=3)
        apa_labels(ax, chs)
        ax.set_title(f"{title}   ({len(lit)} fired)", fontsize=10)
        ax.set_xlabel("z (cm)", fontsize=8); ax.set_ylabel("y (cm)", fontsize=8)
        ax.set_xlim(-10, 470); ax.set_ylim(-25, 615); ax.set_aspect("auto"); ax.tick_params(labelsize=7)
        return sc

    def draw():
        d = flashes[state["i"]]
        if have_raw:
            ensure_raw(d)
        rawlbl = "integral" if state["raw"] == "integral" else "peak"
        fig.suptitle(f"run {run}   flash {state['i'] + 1}/{len(flashes)}   ev {d['ev']} fl {d['fl']}   "
                     f"{len(d['npe'])} PDs   [click a PD = its waveforms (col 3); raw={rawlbl}; "
                     f"t,l toggle; ←→±1 ↑↓±10 pg±50 ][±100]", fontsize=10)
        for kind, axp, axm in amap:
            kk = "raw" if kind == "RAW" else "npe"
            for ax, chs, side in ((axp, px, "+x"), (axm, mx, "-x")):
                vm, clab = value_map(d, kk)
                sc = panel(ax, chs, vm, f"{kind}  {side}", clab)
                # always draw a colorbar (fixed scale) so the panel keeps a constant
                # size as you flip through flashes, even when no PD fired on this side
                mappable = sc if sc is not None else ScalarMappable(norm=make_norm(clab), cmap="viridis")
                cax = caxes[ax]; cax.cla()
                cb = fig.colorbar(mappable, cax=cax)
                cb.set_label(clab, fontsize=7); cb.ax.tick_params(labelsize=6)
        if wf:
            plot_waveforms(ax_wfr, ax_wfd, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04, run, d["ev"], state["selch"],
                           d["abstime"], d["npe"].get(state["selch"]))
        fig.canvas.draw_idle()

    def on_key(e):
        n = len(flashes); i = state["i"]
        step = {"right": 1, "n": 1, " ": 1, "left": -1, "p": -1, "up": 10, "down": -10,
                "pageup": 50, "pagedown": -50, "]": 100, "+": 100, "[": -100, "-": -100}
        if e.key in step:
            state["i"] = min(max(0, i + step[e.key]), n - 1); draw()
        elif e.key == "home": state["i"] = 0; draw()
        elif e.key == "end": state["i"] = n - 1; draw()
        elif e.key == "t": state["raw"] = "peak" if state["raw"] == "integral" else "integral"; draw()
        elif e.key == "l": state["labels"] = not state["labels"]; draw()
        elif e.key == "s":
            d = flashes[state["i"]]; fn = f"flash_run{run}_ev{d['ev']}_fl{d['fl']}.png"
            fig.savefig(fn, dpi=130); print("saved", fn)
        elif e.key in ("q", "escape"):
            plt.close(fig)

    def on_click(e):
        if not wf or e.inaxes not in axinfo or e.xdata is None:
            return
        chs = axinfo[e.inaxes]
        if not chs:
            return
        c = min(chs, key=lambda c: (pos[c][2] - e.xdata) ** 2 + (pos[c][1] - e.ydata) ** 2)
        if abs(pos[c][2] - e.xdata) < 35 and abs(pos[c][1] - e.ydata) < 35:
            state["selch"] = c
            d = flashes[state["i"]]
            plot_waveforms(ax_wfr, ax_wfd, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04, run, d["ev"], c, d["abstime"],
                           d["npe"].get(c))
            fig.canvas.draw_idle()

    draw()
    if headless:
        out = args.out or f"flash_{args.batch}.png"; fig.savefig(out, dpi=130); print("wrote", out); return
    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.canvas.mpl_connect("button_press_event", on_click)
    print("nav: ←→±1 ↑↓±10 pg±50 ][±100 home/end | t=raw peak/integral | l=labels | "
          "s=save | click a PD=waveforms | q=quit")
    plt.show()


def main():
    ap = argparse.ArgumentParser(description="Browse PDS light per flash (raw+deconv YZ); click a PD for in-panel waveforms.")
    ap.add_argument("file")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--min-pd", type=int, default=1)
    ap.add_argument("--raw", choices=["integral", "peak"], default="integral")
    ap.add_argument("--pe-max", type=float, default=None,
                    help="fix the deconvolved-PE color-scale max (default: dataset-wide max)")
    ap.add_argument("--auto-scale", action="store_true",
                    help="per-flash color scale (default: FIXED scale, same across all flashes)")
    ap.add_argument("--log-scale", action="store_true",
                    help="logarithmic color scale (default: LINEAR 0..vmax, like the BEE display)")
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--probe", default=None, help="EV:CH -> render that channel's raw+deconv waveform and exit")
    ap.add_argument("--overlay-ch", type=int, default=None,
                    help="CH -> overlay ALL deconvolved waveforms for that channel across the file "
                         "(one panel per template v1/v0/NP04), then exit")
    ap.add_argument("--normalize", action="store_true",
                    help="with --overlay-ch: peak-normalize each waveform (compare shapes, not amplitudes)")
    ap.add_argument("--vendor-file", default=None, help="text file 'opch vendor' (HPK/FBK) to label PDs")
    a = ap.parse_args()

    m = re.search(r"run0*(\d+)", os.path.basename(a.file))
    run = m.group(1) if m else "?"

    # load OpChannel->vendor (HPK/FBK) if a file is given or found next to the script / in CWD
    for cand in [a.vendor_file, "opch_vendor.txt",
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "opch_vendor.txt")]:
        if cand and os.path.exists(cand):
            VENDOR.update(load_vendor(cand))
            print(f"loaded {len(VENDOR)} channel vendors from {cand}")
            break
    pos, flashes, have_raw, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04 = load(a.file)
    print(f"run {run}: {len(flashes)} flashes; raw panels: {'YES' if have_raw else 'NO'}; "
          f"waveforms on click: {'YES' if lazy_raw is not None else 'no'}; "
          f"deco v1: {'YES' if lazy_deco is not None else 'no'}; "
          f"deco overlays: v0={'Y' if lazy_deco_v0 is not None else 'n'} NP04={'Y' if lazy_deco_np04 is not None else 'n'}")

    if a.probe:
        import matplotlib
        if a.out: matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ev, ch = (int(x) for x in a.probe.split(":"))
        fl = next((d for d in flashes if d["ev"] == ev and ch in d["npe"]),
                  next((d for d in flashes if d["ev"] == ev), None))
        ab = fl["abstime"] if fl else 0.0
        fig = plt.figure(figsize=(9, 6)); a1, a2 = fig.subplots(2, 1)
        plot_waveforms(a1, a2, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04, run, ev, ch, ab,
                       fl["npe"].get(ch) if fl else None)
        fig.tight_layout()
        if a.out:
            fig.savefig(a.out, dpi=120); print("wrote", a.out)
        else:
            plt.show()
        return

    if a.overlay_ch is not None:
        import matplotlib
        headless = a.out is not None
        if headless: matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        readers = [(nm, lz, cl) for nm, lz, cl in
                   (("v0 (Nov2024)", lazy_deco_v0, "tab:blue"),
                    ("v1 (Jun2025)", lazy_deco, "tab:red"),
                    ("NP04 vendor-avg", lazy_deco_np04, "tab:green")) if lz is not None]
        if not readers:
            print("no deconvolved trees in this file"); return
        # one-time bulk pass: bucket up to CAP waveforms per channel for each template.
        # (reading entry-by-entry over hundreds of records per channel is far too slow,
        #  esp. with uproot -> do a single chunked scan of each deco tree instead.)
        CAP = 200
        from collections import defaultdict
        def build_index(lz):
            trs = defaultdict(list); cnt = defaultdict(int)
            if lz.backend == "uproot":
                for ck in lz.tree.iterate(["opch", "nsamples", "adc"], step_size="100 MB", library="np"):
                    oc, ns, ad = ck["opch"], ck["nsamples"], ck["adc"]
                    for i in range(len(oc)):
                        if ns[i] >= 5000:
                            continue
                        c = int(oc[i]); cnt[c] += 1
                        if len(trs[c]) < CAP:
                            trs[c].append(np.asarray(ad[i], dtype=np.float32))
            else:
                t = lz.tree
                for b in ("opch", "nsamples", "adc"):
                    t.SetBranchStatus(b, 1)
                for i in range(t.GetEntries()):
                    t.GetEntry(i)
                    if t.nsamples >= 5000:
                        continue
                    c = int(t.opch); cnt[c] += 1
                    if len(trs[c]) < CAP:
                        trs[c].append(np.asarray(t.adc, dtype=np.float32))
            return trs, cnt
        print("indexing deconvolved waveforms per channel (one-time, ~a few seconds) ...", flush=True)
        idx = []
        for nm, lz, cl in readers:
            trs, cnt = build_index(lz)
            idx.append((trs, cnt))
            print(f"    {nm}: {sum(cnt.values())} waveforms", flush=True)
        chans = sorted({c for _, cnt in idx for c in cnt})
        if not chans:
            print("no deconvolved channels"); return
        state = {"ci": min(range(len(chans)), key=lambda i: abs(chans[i] - a.overlay_ch))}
        fig, axes = plt.subplots(len(readers), 1, sharex=True,
                                 figsize=(9.5, 2.6 * len(readers)), squeeze=False)
        axes = list(axes[:, 0])
        def draw():
            ch = chans[state["ci"]]
            vend = VENDOR.get(ch)
            vtag = f", {vend}" if vend and vend not in ("?", "UNKNOWN", "-") else ""
            for ax, (nm, lz, cl), (trs_d, cnt_d) in zip(axes, readers, idx):
                ax.clear()
                trs = trs_d.get(ch, [])
                if a.normalize:
                    trs = [t / (np.max(np.abs(t)) or 1.0) for t in trs]
                for t in trs:
                    ax.plot(np.arange(len(t)) * 0.016, t, lw=0.6, color=cl, alpha=0.30)
                tot = cnt_d.get(ch, 0)
                lab = f"{tot} waveforms" + (f" (showing {len(trs)})" if tot > len(trs) else "")
                ax.set_title(f"{nm}  —  {lab}", fontsize=9)
                ax.set_ylabel("PE/tick" + (" (peak-norm)" if a.normalize else ""), fontsize=8)
                ax.grid(alpha=0.2); ax.tick_params(labelsize=7)
            axes[-1].set_xlabel("time within snippet (µs, 16 ns/sample)", fontsize=8)
            fig.suptitle(f"run {run}   OpCh {ch} ({APA_OF(ch)}{vtag}) — all deconvolved waveforms"
                         + ("  [peak-normalized]" if a.normalize else "")
                         + "     [ ←/→ channel · ↑/↓ ±10 · q ]", fontsize=11)
            fig.canvas.draw_idle()
        def on_key(e):
            n = len(chans)
            step = {"right": 1, "left": -1, "up": 10, "down": -10, "pageup": 40, "pagedown": -40}
            if e.key in step:
                state["ci"] = min(max(0, state["ci"] + step[e.key]), n - 1); draw()
            elif e.key == "home": state["ci"] = 0; draw()
            elif e.key == "end": state["ci"] = n - 1; draw()
            elif e.key in ("q", "escape"): plt.close(fig)
        draw(); fig.tight_layout()
        if headless:
            fig.savefig(a.out, dpi=120); print("wrote", a.out); return
        fig.canvas.mpl_connect("key_press_event", on_key)
        plt.show()
        return

    flashes = [d for d in flashes if len(d["npe"]) >= a.min_pd]
    if a.list:
        return
    if not flashes:
        print("nothing to show"); return
    if a.batch is not None:
        a.start = a.batch
    a.start = max(0, min(a.start, len(flashes) - 1))
    run_app(pos, flashes, run, a, have_raw, lazy_raw, lazy_deco, lazy_deco_v0, lazy_deco_np04)


if __name__ == "__main__":
    main()
