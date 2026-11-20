"""Build peak-aligned, peak-normalized MEDIAN deconvolved pulses per channel
for the three template sets, over all 4 runs (selected pulses only).

Output: median_pulses.npz with, per channel ch and template t:
  {t}_ch{ch}   median pulse, samples [-64, +512) ticks around the peak
  {t}_n_ch{ch} number of pulses that entered the median

Usage: python build_median_pulses.py
"""

import glob
import os
import numpy as np
import uproot
import awkward as ak

OUT_DIR = "/nfs/data/1/jjo/data/PDHD/spe_template_cmp"
DATA_DIR = "/nfs/data/1/jjo/data/PDHD"
HERE = os.path.dirname(os.path.abspath(__file__))

LO, HI = 64, 512          # window around the peak [ticks]
CAP = 200                 # max pulses per channel per run
AMP_MIN, SAT_MIN = 25.0, 20

acc = {}                  # (t, ch) -> list of (n, 576) arrays


def add(t, ch, wf, ipk):
    ok = (ipk >= LO) & (ipk + HI < wf.shape[1])
    wf, ipk = wf[ok], ipk[ok]
    if len(wf) > CAP:
        step = len(wf) // CAP
        wf, ipk = wf[::step][:CAP], ipk[::step][:CAP]
    if not len(wf):
        return
    idx = ipk[:, None] + np.arange(-LO, HI)[None, :]
    seg = wf[np.arange(len(wf))[:, None], idx]
    seg = seg / wf[np.arange(len(wf)), ipk][:, None]
    acc.setdefault((t, ch), []).append(seg)


def main():
    for path in sorted(glob.glob(f"{DATA_DIR}/*_final.root")):
        f = uproot.open(path)
        run = None
        for mfn in glob.glob(f"{OUT_DIR}/metrics_run*.npz"):
            m = np.load(mfn)
            if os.path.basename(path).find(f"run0{int(m['run'][0])}") >= 0:
                met, run = m, int(m["run"][0])
                break
        assert run is not None, path
        sel = (met["raw_amp"] >= AMP_MIN) & (met["raw_min"] > SAT_MIN)
        print(f"run {run}: {sel.sum()} selected pulses")

        npz = np.load(f"{OUT_DIR}/np04deco_run{run}.npz")
        for ch in np.unique(met["opch"][sel]):
            m = sel & (met["opch"] == ch)
            add("np04", int(ch), npz["wf"][m], met["np04_ipk"][m])

        for t, tn in (("v1", "decodump/deco_waveform"),
                      ("v0", "decodumpv0/deco_waveform")):
            tr = f[tn]
            dm = tr.arrays(["event", "opch", "timestamp"], library="np")
            pos = {k: i for i, k in enumerate(zip(
                dm["event"].tolist(), dm["opch"].tolist(),
                dm["timestamp"].tolist()))}
            wf_all = ak.to_numpy(ak.to_regular(
                tr.arrays(["adc"], library="ak")["adc"]))
            for ch in np.unique(met["opch"][sel]):
                m = sel & (met["opch"] == ch)
                keys = zip(met["event"][m].tolist(), met["opch"][m].tolist(),
                           met["timestamp"][m].tolist())
                ix = np.array([pos[k] for k in keys])
                add(t, int(ch), wf_all[ix], met[f"{t}_ipk"][m])
            del wf_all

    out = {}
    for (t, ch), segs in acc.items():
        allseg = np.vstack(segs)
        out[f"{t}_ch{ch}"] = np.median(allseg, axis=0).astype(np.float32)
        out[f"{t}_n_ch{ch}"] = np.int32(len(allseg))
    np.savez_compressed(os.path.join(HERE, "median_pulses.npz"), **out)
    print(f"wrote median_pulses.npz ({len(out)//2} channel-templates)")


if __name__ == "__main__":
    main()
