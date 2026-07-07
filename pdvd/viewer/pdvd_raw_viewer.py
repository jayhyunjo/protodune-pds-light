#!/usr/bin/env python3
"""PDVD raw-light viewer (validation tool) -- PDVD analog of PDHD flash_viewer.py,
for RAW OpDetWaveforms only (no deconvolution, no flashes yet).

Per EVENT: two OpDet position maps (Side X-Z [X=vertical drift], Top Y-Z), each PD
colored by raw amplitude (max ADC above baseline). Squares = X-ARAPUCA, circles = PMT,
open grey = no signal this event, red x = dead (never read out in the file).
Click a PD -> its raw waveform(s) (click again to cycle overlapping PDs):
  - full-stream channels (cathode X-ARAPUCA): the one long continuous trace vs sample
  - self-trigger channels (membrane X-ARAPUCA + PMT): all captures, either overlaid on
    the sample axis (default) or spread by timestamp (press 't' to toggle)
Keys: left/right = prev/next event ; up/down = +/-10 events ; t = waveform mode ; q = quit.

Backend-agnostic: reads the plain-ROOT raw_waveform tree (uproot on a laptop, pyROOT
fallback in the container) or an .npz.

Interactive:   python pdvd_raw_viewer.py <rawwf.root>
Headless dump: python pdvd_raw_viewer.py <rawwf.root> --event N --out ev.png [--opdet K]
"""
import sys, os, csv, argparse
from collections import defaultdict
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle

# default: the repo's maps/ dir (portable, relative to this script); override with --positions/--chanmap
TEMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "maps")
FULLSTREAM_MIN = 50000   # nsamp above this = full-stream (continuous) readout

def load_maps(posf, mapf):
    pos = {}
    for d in csv.DictReader(open(posf)):
        pos[int(d["opdet"])] = dict(x=float(d["x"])/100, y=float(d["y"])/100, z=float(d["z"])/100,
                                    shape=d["geom_shape"], name=d["json_name"], typ=d["json_pd_type"])
    ch2od = {int(d["offline_channel"]): int(d["opdet"]) for d in csv.DictReader(open(mapf))}
    return pos, ch2od

def read_tree(path):
    """rows of (event, opchannel, timestamp, adc np.array). Reads .npz, or the plain-ROOT
    raw_waveform tree via uproot (laptop) / pyROOT (container)."""
    if path.endswith(".npz"):
        d = np.load(path, allow_pickle=True)
        ev, ch, ts, adc = d["event"], d["opchannel"], d["timestamp"], d["adc"]
        return [(int(ev[i]), int(ch[i]), float(ts[i]), np.asarray(adc[i], dtype=float)) for i in range(len(ev))]
    try:
        import uproot
        a = uproot.open(path)["raw_waveform"].arrays(["event", "opchannel", "timestamp", "adc"], library="np")
        return [(int(a["event"][i]), int(a["opchannel"][i]), float(a["timestamp"][i]), np.asarray(a["adc"][i], dtype=float))
                for i in range(len(a["event"]))]
    except ImportError:
        import ROOT
        f = ROOT.TFile.Open(path); t = f.Get("raw_waveform")
        rows = []
        for e in t:
            v = e.adc
            try:
                adc = np.frombuffer(v.data(), dtype=np.int16, count=v.size()).astype(float)
            except Exception:
                adc = np.array([v[j] for j in range(v.size())], dtype=float)
            rows.append((int(e.event), int(e.opchannel), float(e.timestamp), adc))
        return rows

def baseline(adc):
    return np.median(adc) if len(adc) else 0.0

def amp(adc):
    return float(np.max(adc) - baseline(adc)) if len(adc) else 0.0

class Viewer:
    def __init__(self, rows, pos, ch2od):
        self.pos, self.ch2od = pos, ch2od
        # tiny deterministic jitter (m) so coincident markers in a projection separate
        self.jit = {od: (0.07*(((od*7) % 5) - 2), 0.07*(((od*3) % 5) - 2)) for od in pos}
        self.byev = defaultdict(lambda: defaultdict(list))   # event -> opdet -> [(ch, ts, adc)]
        for ev, ch, ts, adc in rows:
            od = ch2od.get(ch)
            if od is not None:
                self.byev[ev][od].append((ch, ts, adc))
        self.events = sorted(self.byev)
        seen = set().union(*[set(self.byev[e]) for e in self.events]) if self.events else set()
        self.dead = sorted(set(pos) - seen)   # never read out anywhere in the file
        self.ie = 0
        self.sel_od = None            # currently selected OpDet (persists across events)
        self.wf_mode = "overlay"      # self-trigger display: 'overlay' (vs sample) or 'time' (spread by timestamp)
        self._last_cand = []; self._cyc = 0
        self.fig = None

    def dpos(self, od, vi):        # display coord in a projection (z, x|y) with jitter
        p = self.pos[od]; jx, jy = self.jit[od]
        return p["z"] + jy, p[vi] + jx

    def metric(self, ev):
        return {od: max((amp(a) for _, _, a in wfs), default=0.0) for od, wfs in self.byev[ev].items()}

    def draw_maps(self):
        ev = self.events[self.ie]
        m = self.metric(ev)
        vals = [v for v in m.values() if v > 0]
        vmax = max(vals) if vals else 1.0
        vmin = max(min(vals) if vals else 1.0, 1.0)
        norm = LogNorm(vmin=vmin, vmax=vmax) if vmax > vmin else None
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
                elif m.get(od, 0.0) > 0:
                    sc = ax.scatter(z, v, c=[m[od]], cmap="viridis", norm=norm, marker=mk, s=sz,
                                    edgecolors="k", linewidths=0.4, alpha=0.9, zorder=3)
                else:
                    ax.scatter(z, v, facecolors="none", edgecolors="0.6", marker=mk, s=sz, zorder=2)
            if self.sel_od is not None:   # highlight the selected PD
                zs, vs = self.dpos(self.sel_od, vi)
                ax.scatter(zs, vs, s=210, facecolors="none", edgecolors="magenta", linewidths=1.8, zorder=5)
            # real active-volume bounds from protodunevd_v5 geometry (X±341.5, Y±336.4, Z 0.6-298.7 cm)
            vhalf = 3.415 if vi == "x" else 3.364
            ax.add_patch(Rectangle((0.006, -vhalf), 2.981, 2*vhalf, fill=False, edgecolor="red", lw=0.9, zorder=1))
            ax.set_xlim(-2.5, 6.0); ax.set_ylim(-4.5, 4.7); ax.set_aspect("equal", "box")
            ax.set_xlabel("Z (m)"); ax.set_ylabel(ylab); ax.set_title(ttl); ax.grid(alpha=0.2)
        if sc is not None and self.cb is None:
            self.cb = self.fig.colorbar(sc, ax=[self.axS, self.axT], shrink=0.7, pad=0.02)
            self.cb.set_label("raw amplitude (max ADC - baseline)")
        self.fig.suptitle(f"PDVD raw light - event {ev}  ({self.ie+1}/{len(self.events)})   "
                          f"[click PD (again=cycle overlaps); ←/→ event, ↑/↓ ±10, t = wf mode]   "
                          f"red x = dead ({len(self.dead)})", fontsize=10)

    def draw_wf(self, od=None):
        self.axW.clear()
        ev = self.events[self.ie]
        if od is None or od not in self.byev[ev]:
            self.axW.set_title("dead channel" if od in self.dead else "click a PD for its raw waveform")
        else:
            p = self.pos[od]; wfs = self.byev[ev][od]
            fullstream = max(len(a) for _, _, a in wfs) > FULLSTREAM_MIN
            if fullstream:
                for ch, ts, adc in wfs:
                    self.axW.plot(np.arange(len(adc)), adc, lw=0.5, label=f"ch {ch}")
                self.axW.set_xlabel("sample"); mode = "FULL-STREAM"
            elif self.wf_mode == "time":
                t0 = min(ts for _, ts, _ in wfs)
                for ch, ts, adc in sorted(wfs, key=lambda w: w[1]):
                    self.axW.plot((ts - t0) + np.arange(len(adc)), adc, lw=0.6)
                self.axW.set_xlabel("time (rel. to first capture; timestamp + sample idx)"); mode = "SELF-TRIG [time]"
            else:
                for ch, ts, adc in wfs:
                    self.axW.plot(np.arange(len(adc)), adc, lw=0.5, alpha=0.4)
                self.axW.set_xlabel("sample"); mode = "SELF-TRIG [overlay]"
            self.axW.set_title(f"OpDet {od} ({p['name']}, {p['typ']}) - {mode}\n"
                               f"{len(wfs)} waveform(s), event {ev}, (x,y,z)=({p['x']:.1f},{p['y']:.1f},{p['z']:.1f}) m")
            if fullstream:
                self.axW.legend(fontsize=7, loc="upper right")
        self.axW.set_ylabel("ADC"); self.axW.grid(alpha=0.2)

    def candidates(self, ax, x, y, tol=0.6):
        """OpDets within tol (m) of the click in this projection, nearest first;
        falls back to the single nearest if none within tol."""
        vi = "x" if ax is self.axS else "y"
        c = sorted((((self.dpos(od, vi)[0]-x)**2 + (self.dpos(od, vi)[1]-y)**2)**0.5, od) for od in self.pos)
        near = [od for d, od in c if d < tol]
        return near if near else [c[0][1]]

    def on_click(self, event):
        if event.inaxes not in (self.axS, self.axT) or event.xdata is None:
            return
        cand = self.candidates(event.inaxes, event.xdata, event.ydata)
        if cand == self._last_cand:            # repeated click on same cluster -> cycle through overlaps
            self._cyc = (self._cyc + 1) % len(cand)
        else:
            self._last_cand, self._cyc = cand, 0
        self.sel_od = cand[self._cyc]
        self.draw_maps(); self.draw_wf(self.sel_od); self.fig.canvas.draw_idle()

    def on_key(self, event):
        step = {"right": 1, "left": -1, "up": 10, "down": -10}.get(event.key)
        if step is not None:
            self.ie = (self.ie + step) % len(self.events)
        elif event.key == "t":
            self.wf_mode = "time" if self.wf_mode == "overlay" else "overlay"
            self.draw_wf(self.sel_od); self.fig.canvas.draw_idle(); return
        elif event.key == "q":
            plt.close(self.fig); return
        else:
            return
        self.draw_maps(); self.draw_wf(self.sel_od); self.fig.canvas.draw_idle()

    def _layout(self):
        self.fig = plt.figure(figsize=(15, 6.5))
        self.axS = self.fig.add_axes([0.05, 0.1, 0.27, 0.76])
        self.axT = self.fig.add_axes([0.36, 0.1, 0.27, 0.76])
        self.axW = self.fig.add_axes([0.72, 0.12, 0.26, 0.74])
        self.cb = None

    def show(self):
        self._layout(); self.draw_maps(); self.draw_wf()
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        plt.show()

    def save(self, ev, out, od=None):
        self.ie = self.events.index(ev); self.sel_od = od
        self._layout(); self.draw_maps(); self.draw_wf(od)
        self.fig.savefig(out, dpi=130); print("wrote", out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rawwf")
    ap.add_argument("--positions", default=f"{TEMP}/pdvd_v5_opdet_positions.csv")
    ap.add_argument("--chanmap", default=f"{TEMP}/pdvd_offlinechan_to_opdet.csv")
    ap.add_argument("--event", type=int, default=None)
    ap.add_argument("--opdet", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    pos, ch2od = load_maps(a.positions, a.chanmap)
    v = Viewer(read_tree(a.rawwf), pos, ch2od)
    if not v.events:
        sys.exit("no events with mappable channels found")
    print(f"events: {v.events[:3]}...  dead OpDets (never read out): {v.dead}")
    if a.out:
        matplotlib.use("Agg")
        v.save(a.event if a.event is not None else v.events[0], a.out, a.opdet)
    else:
        v.show()

if __name__ == "__main__":
    main()
