"""Validate the numpy Deconvolution port against the LArSoft-produced trees.

For every raw self-trigger record in the flat files, re-deconvolve with the
v1 and v0 SPE templates in Python and compare with the stored
decodump/decodumpv0 waveforms (which LArSoft produced from the same raw
records). Agreement at float32 round-off level certifies the port, so the
NP04 vendor-average deco produced the same way is directly comparable.

Usage: python validate_pydeco.py <final.root> [more.root ...]
"""

import sys
import numpy as np
import uproot
import awkward as ak

from pdhd_deco import DecoEngine, IGNORE_CHANNELS

KEYS = ["run", "subrun", "event", "opch", "timestamp", "nsamples"]


def load_active(tree):
    """Load meta + 1024-sample adc matrix for deconvolvable records."""
    meta = tree.arrays(KEYS, library="np")
    mask = ((meta["opch"] < 120)
            & ~np.isin(meta["opch"], list(IGNORE_CHANNELS))
            & (meta["nsamples"] == 1024))
    adc_rows = []
    sel_global = np.where(mask)[0]
    # read adc in chunks to avoid materializing APA1 full-stream records
    start = 0
    for chunk in tree.iterate(["adc"], step_size=2000, library="ak"):
        n = len(chunk)
        idx = sel_global[(sel_global >= start) & (sel_global < start + n)] - start
        if len(idx):
            adc_rows.append(ak.to_numpy(ak.to_regular(chunk["adc"][idx])))
        start += n
    adc = np.vstack(adc_rows)
    meta = {k: v[mask] for k, v in meta.items()}
    return meta, adc


def record_keys(meta):
    return np.stack([meta["event"], meta["opch"]], axis=1), meta["timestamp"]


def align(meta_a, meta_b):
    """Inner-join on (event, opch, timestamp): return (ia, ib) index arrays
    so that a[ia] and b[ib] are matched rows. Events rejected by the keepup's
    fembfilter have raw records but no deco records, so a full match is not
    guaranteed."""
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


def main():
    engines = {"v1": DecoEngine("v1"), "v0": DecoEngine("v0")}
    trees = {"v1": "decodump/deco_waveform", "v0": "decodumpv0/deco_waveform"}

    for path in sys.argv[1:]:
        f = uproot.open(path)
        meta, adc = load_active(f["rawdump/raw_waveform"])
        print(f"\n=== {path.split('/')[-1]}: {len(adc)} active records ===")
        for ver, tname in trees.items():
            t = f[tname]
            dmeta = t.arrays(KEYS, library="np")
            ia, ib = align(meta, dmeta)
            if len(ia) < len(adc):
                print(f"  {ver}: {len(adc) - len(ia)} raw records without "
                      f"stored deco (fembfilter-skipped events) — excluded")
            stored = ak.to_numpy(ak.to_regular(
                t.arrays(["adc"], library="ak")["adc"]))[ib]
            opch = meta["opch"][ia]
            madc = adc[ia]
            worst = 0.0
            worst_rel = 0.0
            per_ch_bad = {}
            for ch in np.unique(opch):
                m = opch == ch
                out = engines[ver].deconvolve(int(ch), madc[m])
                ref = stored[m]
                d = np.abs(out - ref)
                scale = np.maximum(np.abs(ref).max(axis=1, keepdims=True), 1e-3)
                rel = (d / scale).max()
                worst = max(worst, float(d.max()))
                worst_rel = max(worst_rel, float(rel))
                if rel > 1e-4:
                    per_ch_bad[int(ch)] = float(rel)
            print(f"  {ver}: max |diff| = {worst:.3e}  "
                  f"max rel-to-peak diff = {worst_rel:.3e}  "
                  f"channels above 1e-4: {per_ch_bad if per_ch_bad else 'none'}")


if __name__ == "__main__":
    main()
