"""Produce the NP04 vendor-average deconvolution (validated numpy port) for
every raw self-trigger record, and compute per-record tail/undershoot metrics
for the three SPE template sets (v1 stored, v0 stored, NP04 recomputed).

Outputs per run, under OUT_DIR:
  np04deco_run<RUN>.npz   NP04 deco waveforms (float32) + record keys
  metrics_run<RUN>.npz    per-record metrics for v1/v0/np04 + raw-pulse info

Usage: python make_np04_metrics.py <final.root> [more.root ...]
"""

import sys
import numpy as np
import uproot
import awkward as ak

from pdhd_deco import DecoEngine, IGNORE_CHANNELS

OUT_DIR = "/nfs/data/1/jjo/data/PDHD/spe_template_cmp"
KEYS = ["run", "subrun", "event", "opch", "timestamp", "nsamples"]

# deco-waveform metric windows (ticks; 16 ns each)
PROMPT_LO, PROMPT_HI = -10, 40   # prompt integration window around the peak
LATE_N = 128                     # late-baseline window = last 128 ticks (2 us)
PRE_N = 30                       # pre-trigger window for baseline RMS


def load_active(tree):
    meta = tree.arrays(KEYS, library="np")
    mask = ((meta["opch"] < 120)
            & ~np.isin(meta["opch"], list(IGNORE_CHANNELS))
            & (meta["nsamples"] == 1024))
    sel_global = np.where(mask)[0]
    adc_rows = []
    start = 0
    for chunk in tree.iterate(["adc"], step_size=2000, library="ak"):
        n = len(chunk)
        idx = sel_global[(sel_global >= start) & (sel_global < start + n)] - start
        if len(idx):
            adc_rows.append(ak.to_numpy(ak.to_regular(chunk["adc"][idx])))
        start += n
    return {k: v[mask] for k, v in meta.items()}, np.vstack(adc_rows)


def join(meta_a, meta_b):
    kb = list(zip(meta_b["event"], meta_b["opch"], meta_b["timestamp"]))
    pos = {k: i for i, k in enumerate(kb)}
    ia, ib = [], []
    for i, k in enumerate(zip(meta_a["event"], meta_a["opch"],
                              meta_a["timestamp"])):
        j = pos.get(k)
        if j is not None:
            ia.append(i)
            ib.append(j)
    return np.array(ia), np.array(ib)


def deco_metrics(wf):
    """Per-record tail metrics of deconvolved waveforms wf (N, 1024)."""
    n, ns = wf.shape
    rows = np.arange(n)
    ipk = wf.argmax(axis=1)
    peak = wf[rows, ipk]
    # running min from each position to the end -> min of the tail [ipk:]
    revmin = np.minimum.accumulate(wf[:, ::-1], axis=1)[:, ::-1]
    min_tail = revmin[rows, ipk]
    # negative area of the tail [ipk:]
    negcum = np.cumsum(np.clip(wf, None, 0.0)[:, ::-1], axis=1)[:, ::-1]
    neg_area = -negcum[rows, ipk]
    # positive prompt area in [ipk-10, ipk+40)
    off = np.arange(PROMPT_LO, PROMPT_HI)
    win = np.clip(ipk[:, None] + off[None, :], 0, ns - 1)
    prompt_pos = np.clip(wf[rows[:, None], win], 0.0, None).sum(axis=1)
    late_mean = wf[:, -LATE_N:].mean(axis=1)
    pre_rms = wf[:, :PRE_N].std(axis=1)
    return dict(peak=peak, ipk=ipk.astype(np.int16), min_tail=min_tail,
                neg_area=neg_area, prompt_pos=prompt_pos,
                late_mean=late_mean, pre_rms=pre_rms)


def main():
    np04 = DecoEngine("np04")
    for path in sys.argv[1:]:
        f = uproot.open(path)
        meta, adc = load_active(f["rawdump/raw_waveform"])
        run = int(meta["run"][0])

        # inner-join raw records with both stored deco trees; keep only
        # records present in BOTH (fembfilter-rejected events have v0 but no
        # keepup v1 product -> excluded from the comparison)
        joins = {}
        for ver, tname in (("v1", "decodump/deco_waveform"),
                           ("v0", "decodumpv0/deco_waveform")):
            t = f[tname]
            dmeta = t.arrays(KEYS, library="np")
            ia, ib = join(meta, dmeta)
            joins[ver] = (dict(zip(ia, ib)), t)
        keep = np.array(sorted(set(joins["v1"][0]) & set(joins["v0"][0])))
        wfs = {}
        for ver, (iamap, t) in joins.items():
            ib = np.array([iamap[i] for i in keep])
            wfs[ver] = ak.to_numpy(ak.to_regular(
                t.arrays(["adc"], library="ak")["adc"]))[ib]
        dropped = len(adc) - len(keep)
        meta = {k: v[keep] for k, v in meta.items()}
        adc = adc[keep]
        print(f"run {run}: {len(adc)} records"
              + (f" ({dropped} raw-only dropped)" if dropped else ""))

        # NP04 vendor-average deco with the validated Python port
        np04_wf = np.empty_like(wfs["v1"])
        for ch in np.unique(meta["opch"]):
            m = meta["opch"] == ch
            np04_wf[m] = np04.deconvolve(int(ch), adc[m])
        wfs["np04"] = np04_wf
        np.savez_compressed(
            f"{OUT_DIR}/np04deco_run{run}.npz",
            event=meta["event"], opch=meta["opch"],
            timestamp=meta["timestamp"], wf=np04_wf)

        # raw-pulse quantities (selection variables)
        ped = adc[:, :20].mean(axis=1)
        raw_amp = ped[:, None] - adc            # positive-going pulse
        out = dict(run=meta["run"], subrun=meta["subrun"],
                   event=meta["event"], opch=meta["opch"],
                   timestamp=meta["timestamp"],
                   raw_ped=ped.astype(np.float32),
                   raw_amp=raw_amp.max(axis=1).astype(np.float32),
                   raw_min=adc.min(axis=1).astype(np.int16))
        for ver, wf in wfs.items():
            for name, arr in deco_metrics(wf).items():
                out[f"{ver}_{name}"] = arr
        np.savez_compressed(f"{OUT_DIR}/metrics_run{run}.npz", **out)
        print(f"  wrote np04deco_run{run}.npz + metrics_run{run}.npz")


if __name__ == "__main__":
    main()
