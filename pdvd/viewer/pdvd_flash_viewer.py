#!/usr/bin/env python3
"""PDVD flash viewer -- the flash-centric analog of PDHD flash_viewer.py.

Browse recob::OpFlash one flash at a time (from pdvd .._flash.root, made by
pdvd/scripts/pdvd_dump_flash.py).  Two OpDet position maps (Side X-Z [X=vertical
drift], Top Y-Z) with each PD colored by ITS PE in the current flash; click a PD to
see its RAW waveform at the flash time in the right column.

Decon: ProtoDUNE-VD reco does NOT deconvolve (raw is handed off for WireCell
deconvolution), so the DECONVOLVED panel is intentionally a stub for now -- the
layout mirrors PDHD so a decon source can be wired in later ('Raw only for now').

Two files: the flash file (flash / flash_opdet trees) supplies the flashes + per-PD
PE; the raw-waveform file (raw_waveform tree, from pdvd_dump_rawwf.py) supplies the
click-to-waveform traces.  --rawwf is auto-found next to the flash file / in a sibling
rawwf_out/ if not given.  All time fields (flash time, waveform timestamp) share the
same 16 ns-tick clock, so a flash's waveform is the record with ts <= t_flash <= ts+nsamp.

On click, the raw record shown is the one whose actual pulse (argmax above baseline)
lands nearest the flash time -- self-trigger records overlap heavily, so this (not
"nearest start") is the record carrying the flash's light -- rendered with t=0 at the
flash time. PE color is log-scaled by default (--linear-scale / --pe-max to change).

Markers: squares = X-ARAPUCA, circles = PMT, open grey = no PE this flash, red x = dead.
Keys: ←/→ ±1 flash | ↑/↓ ±10 | pgup/pgdn ±50 | ]/[ ±100 | home/end | s save | q quit.
Interactive:   python pdvd_flash_viewer.py <..._flash.root> [--rawwf <..._rawwf.root>]
Headless:      python pdvd_flash_viewer.py <..._flash.root> --start N [--opdet K] --out flash.png
REQUIRES: numpy, matplotlib, and uproot (laptop) OR pyROOT (container).
"""
import sys, os, csv, argparse, glob
from collections import defaultdict
import numpy as np

TEMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maps")
FULLSTREAM_MIN = 50000     # nsamp above this = full-stream (continuous) readout
TICK_US = 0.016            # 16 ns / sample
DEAD_PMT = {24, 27, 28, 34}


def load_maps(posf):
    pos = {}
    for d in csv.DictReader(open(posf)):
        pos[int(d["opdet"])] = dict(x=float(d["x"]) / 100, y=float(d["y"]) / 100, z=float(d["z"]) / 100,
                                    shape=d["geom_shape"], name=d["json_name"], typ=d["json_pd_type"])
    return pos


def find_rawwf(flashpath, given):
    if given:
        return given
    base = os.path.basename(flashpath).replace("_flash.root", "_rawwf.root")
    d = os.path.dirname(os.path.abspath(flashpath))
    for cand in [os.path.join(d, base),
                 os.path.join(d, "..", "rawwf_out", base),
                 os.path.join(os.path.dirname(d), "rawwf_out", base)]:
        if os.path.exists(cand):
            return cand
    hits = glob.glob(os.path.join(os.path.dirname(d), "rawwf_out", "*_rawwf.root"))
    return hits[0] if hits else None


def load_flashes(path):
    """-> list of {ev, fl, time, total_pe, yc, zc, pe:{opdet:pe}} sorted by (ev, fl)."""
    flashes = {}
    try:
        import uproot
        f = uproot.open(path)
        t = f["flash"].arrays(["event", "flash_id", "time", "abstime", "total_pe", "n_opdet", "ycenter", "zcenter"], library="np")
        for i in range(len(t["event"])):
            flashes[(int(t["event"][i]), int(t["flash_id"][i]))] = dict(
                ev=int(t["event"][i]), fl=int(t["flash_id"][i]), time=float(t["time"][i]),
                abstime=float(t["abstime"][i]), total_pe=float(t["total_pe"][i]),
                yc=float(t["ycenter"][i]), zc=float(t["zcenter"][i]), pe={})
        o = f["flash_opdet"].arrays(["event", "flash_id", "opdet", "pe"], library="np")
        for i in range(len(o["event"])):
            k = (int(o["event"][i]), int(o["flash_id"][i]))
            if k in flashes:
                flashes[k]["pe"][int(o["opdet"][i])] = float(o["pe"][i])
    except ImportError:
        import ROOT
        fr = ROOT.TFile.Open(path)
        t = fr.Get("flash")
        for e in t:
            flashes[(int(e.event), int(e.flash_id))] = dict(
                ev=int(e.event), fl=int(e.flash_id), time=float(e.time), abstime=float(e.abstime),
                total_pe=float(e.total_pe), yc=float(e.ycenter), zc=float(e.zcenter), pe={})
        o = fr.Get("flash_opdet")
        for e in o:
            k = (int(e.event), int(e.flash_id))
            if k in flashes:
                flashes[k]["pe"][int(e.opdet)] = float(e.pe)
    return [flashes[k] for k in sorted(flashes)]


class LazyRaw:
    """(event, opdet) -> raw waveform records near a flash time, from raw_waveform.
    ADC read once per record and cached."""
    def __init__(self, path):
        self.idx = defaultdict(list)   # (ev,od) -> [(ts, nsamp, entry)]
        self.cache = {}
        self.backend = None
        if path is None:
            return
        try:
            import uproot
            self.f = uproot.open(path)
            self.tree = self.f["raw_waveform"]
            sc = self.tree.arrays(["event", "opdet", "timestamp", "nsamp"], library="np")
            for i in range(len(sc["event"])):
                self.idx[(int(sc["event"][i]), int(sc["opdet"][i]))].append(
                    (float(sc["timestamp"][i]), int(sc["nsamp"][i]), i))
            self.backend = "uproot"
        except ImportError:
            import ROOT
            self.f = ROOT.TFile.Open(path)
            self.tree = self.f.Get("raw_waveform")
            self.tree.SetBranchStatus("*", 0)
            for b in ("event", "opdet", "timestamp", "nsamp"):
                self.tree.SetBranchStatus(b, 1)
            for i in range(self.tree.GetEntries()):
                self.tree.GetEntry(i)
                self.idx[(int(self.tree.event), int(self.tree.opdet))].append(
                    (float(self.tree.timestamp), int(self.tree.nsamp), i))
            self.tree.SetBranchStatus("adc", 1)
            self.backend = "pyROOT"

    def _adc(self, entry):
        if entry in self.cache:
            return self.cache[entry]
        if self.backend == "uproot":
            a = np.asarray(self.tree["adc"].array(entry_start=entry, entry_stop=entry + 1,
                                                  library="np")[0], dtype=np.float64)
        else:
            self.tree.GetEntry(entry)
            v = self.tree.adc
            try:
                a = np.frombuffer(v.data(), dtype=np.int16, count=v.size()).astype(np.float64)
            except Exception:
                a = np.array([v[j] for j in range(v.size())], dtype=np.float64)
        self.cache[entry] = a
        return a

    def match(self, ev, od, tflash, win=2048):
        """The raw record whose PULSE is at the flash time. Self-trigger records overlap
        heavily (each ~1024 samp, triggered far more often than every 16 us), and 'nearest
        start' picks the wrong one, so among records near tflash we choose the one whose
        actual pulse (argmax above baseline) lands closest to tflash -> that's where the
        flash's light is, and it renders at t=0. Full-stream: the one long record containing
        tflash (adc not scanned). Returns (ts, nsamp, entry) or None."""
        recs = self.idx.get((ev, od))
        if not recs:
            return None
        fs = [r for r in recs if r[1] > FULLSTREAM_MIN]
        if fs:
            cont = [r for r in fs if r[0] <= tflash <= r[0] + r[1]]
            return max(cont or fs, key=lambda r: r[0])
        cands = [r for r in recs if r[0] - win <= tflash <= r[0] + r[1]]
        if not cands:
            best = min(recs, key=lambda r: min(abs(tflash - r[0]), abs(tflash - (r[0] + r[1]))))
            dt = min(abs(tflash - best[0]), abs(tflash - (best[0] + best[1])))
            return best if dt <= 4096 else None
        best, bestdt = None, None
        for ts, ns, e in cands:
            a = self._adc(e)
            base = np.median(a[:100]) if len(a) > 100 else np.median(a)
            pk = int(np.argmax(a - base))
            dt = abs((ts + pk) - tflash)
            if bestdt is None or dt < bestdt:
                bestdt, best = dt, (ts, ns, e)
        return best

    def trace(self, ev, od, tflash, half_us=8.0):
        """(t_us_rel_flash, adc_baseline_subtracted, is_zoom) or None."""
        rec = self.match(ev, od, tflash)
        if rec is None:
            return None
        ts, ns, e = rec
        a = self._adc(e)
        base = np.median(a[:100]) if len(a) > 100 else np.median(a)
        a = a - base
        off = tflash - ts                       # flash offset within the record, in samples
        if ns > FULLSTREAM_MIN:                  # full-stream -> zoom around the flash time
            o = int(round(off)); half = int(half_us / TICK_US)
            lo, hi = max(0, o - half), min(len(a), o + half)
            return (np.arange(lo, hi) - off) * TICK_US, a[lo:hi], True
        return (np.arange(len(a)) - off) * TICK_US, a, False


class FlashViewer:
    def __init__(self, flashes, pos, raw, run, pe_max=None, log_scale=False):
        self.flashes, self.pos, self.raw, self.run = flashes, pos, raw, run
        self.log_scale = log_scale
        self.jit = {od: (0.07 * (((od * 7) % 5) - 2), 0.07 * (((od * 3) % 5) - 2)) for od in pos}
        self.i = 0
        self.sel_od = None
        self._last_cand, self._cyc = [], 0
        self.fig = self.cb = None
        seen = set().union(*[set(d["pe"]) for d in flashes]) if flashes else set()
        self.dead = sorted((set(pos) & DEAD_PMT) | (set(pos) - seen))
        allpe = [v for d in flashes for v in d["pe"].values() if v > 0]
        # default scale: 95th pct (log) or 90th pct (linear) so typical flashes show contrast
        self.vmax = float(pe_max) if pe_max else (
            float(np.percentile(allpe, 95 if log_scale else 90)) if allpe else 1.0)

    def dpos(self, od, vi):
        p = self.pos[od]; jx, jy = self.jit[od]
        return p["z"] + jy, p[vi] + jx

    def make_norm(self):
        from matplotlib.colors import Normalize, LogNorm
        if self.log_scale:
            return LogNorm(vmin=1.0, vmax=max(self.vmax, 1.01))
        return Normalize(vmin=0.0, vmax=max(self.vmax, 1.0))

    def draw_maps(self):
        from matplotlib.patches import Rectangle
        d = self.flashes[self.i]
        pe = d["pe"]
        norm = self.make_norm()
        sc = None
        for ax, vi, ylab, ttl in [(self.axS, "x", "X (m) - Drift [vertical]", "Side view (X-Z)"),
                                   (self.axT, "y", "Y (m)", "Top view (Y-Z)")]:
            ax.clear()
            for od, p in self.pos.items():
                z, v = self.dpos(od, vi)
                mk = "s" if p["shape"] == "xarapuca" else "o"
                sz = 90 if p["shape"] == "xarapuca" else 55
                if od in self.dead:
                    ax.scatter(z, v, marker="x", c="red", s=55, linewidths=1.6, zorder=4)
                elif pe.get(od, 0.0) > 0:
                    sc = ax.scatter(z, v, c=[pe[od]], cmap="viridis", norm=norm, marker=mk, s=sz,
                                    edgecolors="k", linewidths=0.4, alpha=0.92, zorder=3)
                else:
                    ax.scatter(z, v, facecolors="none", edgecolors="0.6", marker=mk, s=sz, zorder=2)
            if self.sel_od is not None:
                zs, vs = self.dpos(self.sel_od, vi)
                ax.scatter(zs, vs, s=210, facecolors="none", edgecolors="magenta", linewidths=1.8, zorder=5)
            vhalf = 3.415 if vi == "x" else 3.364
            ax.add_patch(Rectangle((0.006, -vhalf), 2.981, 2 * vhalf, fill=False, edgecolor="red", lw=0.9, zorder=1))
            ax.set_xlim(-2.5, 6.0); ax.set_ylim(-4.5, 4.7); ax.set_aspect("equal", "box")
            ax.set_xlabel("Z (m)"); ax.set_ylabel(ylab); ax.set_title(ttl); ax.grid(alpha=0.2)
        if sc is not None and self.cb is None:
            self.cb = self.fig.colorbar(sc, ax=[self.axS, self.axT], shrink=0.7, pad=0.02)
            self.cb.set_label(f"PE in this flash (fixed {'log' if self.log_scale else 'linear'} scale, "
                              f"vmax={self.vmax:.0f})")
        self.fig.suptitle(f"PDVD flash  run {self.run}   flash {self.i+1}/{len(self.flashes)}   "
                          f"ev {d['ev']} fl {d['fl']}   {len(pe)} PDs   totalPE={d['total_pe']:.0f}   "
                          f"(y,z)=({d['yc']:.0f},{d['zc']:.0f}) cm\n"
                          f"[click PD (again=cycle overlaps); ←/→ flash, ↑/↓ ±10, pg ±50, ][ ±100, s save]",
                          fontsize=10)

    def draw_wf(self):
        d = self.flashes[self.i]; od = self.sel_od
        self.axR.clear(); self.axD.clear()
        # DECON stub (VD reco is raw-only)
        self.axD.set_xticks([]); self.axD.set_yticks([])
        self.axD.text(0.5, 0.5, "no deconvolution in VD reco\n(raw handed off for WireCell decon)",
                      ha="center", va="center", transform=self.axD.transAxes, fontsize=9, color="gray")
        self.axD.set_title("DECONVOLVED (not available)", fontsize=9)
        if od is None:
            self.axR.set_xticks([]); self.axR.set_yticks([])
            self.axR.text(0.5, 0.5, "click a PD for its raw waveform", ha="center", va="center",
                          transform=self.axR.transAxes, fontsize=10, color="gray")
            return
        p = self.pos[od]
        tr = None if self.raw is None else self.raw.trace(d["ev"], od, d["abstime"])
        if tr is None:
            self.axR.set_xticks([]); self.axR.set_yticks([])
            self.axR.text(0.5, 0.5, "dead channel" if od in self.dead else "no raw record near this flash",
                          ha="center", va="center", transform=self.axR.transAxes, fontsize=9, color="gray")
        else:
            t, adc, zoom = tr
            self.axR.plot(t, adc, lw=0.7, color="tab:blue")
            self.axR.axvline(0, color="gray", ls=":", lw=0.7)
            self.axR.set_xlabel("t − t_flash (µs, 16 ns/sample)", fontsize=8)
            self.axR.set_ylabel("raw ADC − baseline", fontsize=8); self.axR.tick_params(labelsize=7)
            self.axR.grid(alpha=0.2)
            tag = "  [full-stream — zoom @ flash]" if zoom else "  [self-trigger]"
            self.axR.set_title(f"OpDet {od} ({p['name']}, {p['typ']})  ev {d['ev']}  "
                               f"PE={d['pe'].get(od, 0):.1f} — RAW{tag}", fontsize=9)

    def candidates(self, ax, x, y, tol=0.6):
        vi = "x" if ax is self.axS else "y"
        c = sorted((((self.dpos(od, vi)[0] - x) ** 2 + (self.dpos(od, vi)[1] - y) ** 2) ** 0.5, od) for od in self.pos)
        near = [od for dd, od in c if dd < tol]
        return near if near else [c[0][1]]

    def on_click(self, e):
        if e.inaxes not in (self.axS, self.axT) or e.xdata is None:
            return
        cand = self.candidates(e.inaxes, e.xdata, e.ydata)
        if cand == self._last_cand:
            self._cyc = (self._cyc + 1) % len(cand)
        else:
            self._last_cand, self._cyc = cand, 0
        self.sel_od = cand[self._cyc]
        self.draw_maps(); self.draw_wf(); self.fig.canvas.draw_idle()

    def on_key(self, e):
        import matplotlib.pyplot as plt
        n = len(self.flashes)
        step = {"right": 1, "left": -1, "up": 10, "down": -10, "pageup": 50, "pagedown": -50,
                "]": 100, "[": -100}.get(e.key)
        if step is not None:
            self.i = min(max(0, self.i + step), n - 1)
        elif e.key == "home":
            self.i = 0
        elif e.key == "end":
            self.i = n - 1
        elif e.key == "s":
            d = self.flashes[self.i]; fn = f"pdvd_flash_run{self.run}_ev{d['ev']}_fl{d['fl']}.png"
            self.fig.savefig(fn, dpi=130); print("saved", fn); return
        elif e.key == "q":
            plt.close(self.fig); return
        else:
            return
        self.draw_maps(); self.draw_wf(); self.fig.canvas.draw_idle()

    def _layout(self):
        import matplotlib.pyplot as plt
        self.fig = plt.figure(figsize=(18, 6.8))
        self.axS = self.fig.add_axes([0.04, 0.10, 0.26, 0.74])
        self.axT = self.fig.add_axes([0.35, 0.10, 0.26, 0.74])
        self.axR = self.fig.add_axes([0.70, 0.57, 0.28, 0.30])
        self.axD = self.fig.add_axes([0.70, 0.12, 0.28, 0.30])
        self.cb = None

    def show(self):
        self._layout(); self.draw_maps(); self.draw_wf()
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        import matplotlib.pyplot as plt
        print("nav: ←→ flash, ↑↓ ±10, pg ±50, ][ ±100, home/end | click a PD = raw waveform | s save | q quit")
        plt.show()

    def save(self, out, od=None):
        self.sel_od = od
        self._layout(); self.draw_maps(); self.draw_wf()
        self.fig.savefig(out, dpi=130); print("wrote", out)


def main():
    import re
    ap = argparse.ArgumentParser(description="Browse PDVD recob::OpFlash flash-by-flash; click a PD for its raw waveform.")
    ap.add_argument("flashfile")
    ap.add_argument("--rawwf", default=None, help="raw_waveform file (auto-found if omitted)")
    ap.add_argument("--positions", default=f"{TEMP}/pdvd_v5_opdet_positions.csv")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--event", type=int, default=None, help="jump to the first flash of this event")
    ap.add_argument("--min-pd", type=int, default=1, help="only flashes with >= this many PDs")
    ap.add_argument("--pe-max", type=float, default=None, help="fix the PE color-scale max (default: 90th/95th pct)")
    ap.add_argument("--linear-scale", action="store_true", help="linear PE color scale (default: log)")
    ap.add_argument("--opdet", type=int, default=None, help="headless: preselect this OpDet's waveform")
    ap.add_argument("--out", default=None, help="headless: save a PNG and exit")
    a = ap.parse_args()

    m = re.search(r"run0*(\d+)", os.path.basename(a.flashfile))
    run = m.group(1) if m else "?"
    pos = load_maps(a.positions)
    flashes = load_flashes(a.flashfile)
    flashes = [d for d in flashes if len(d["pe"]) >= a.min_pd]
    if not flashes:
        sys.exit("no flashes to show")
    rawpath = find_rawwf(a.flashfile, a.rawwf)
    raw = LazyRaw(rawpath)
    print(f"run {run}: {len(flashes)} flashes (min-pd={a.min_pd}); "
          f"raw waveforms: {rawpath if rawpath else 'NONE (maps only)'} "
          f"[{raw.backend}]" if rawpath else f"run {run}: {len(flashes)} flashes; NO raw file")

    if a.event is not None:
        a.start = next((k for k, d in enumerate(flashes) if d["ev"] == a.event), a.start)
    a.start = max(0, min(a.start, len(flashes) - 1))

    v = FlashViewer(flashes, pos, raw, run, pe_max=a.pe_max, log_scale=not a.linear_scale)
    v.i = a.start
    if a.out:
        import matplotlib
        matplotlib.use("Agg")
        v.save(a.out, a.opdet)
    else:
        v.show()


if __name__ == "__main__":
    main()
