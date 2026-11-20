"""Template-level comparison of the SPE kernels themselves (v0, v1, NP04).

The Wiener deconvolution divides by the kernel spectrum; a kernel whose tail
does not match the true per-PE response shows up directly as a tail artifact
(undershoot) in every deconvolved waveform. The kernel's net area (= its DC
Fourier component H(0)) relative to its positive lobe is the headline
"DC balance" number.

Writes kernel_metrics.csv (one row per channel x template set) and
kernels.npz (the kernels, for plotting) next to this script.
"""

import csv
import os
import numpy as np

from pdhd_deco import (DecoEngine, IGNORE_CHANNELS, VENDOR, SAMPLES)

HERE = os.path.dirname(os.path.abspath(__file__))


def kernel_row(h):
    ipk = int(np.argmax(h))
    peak = float(h[ipk])
    pos = float(np.clip(h, 0, None).sum())
    neg = float(-np.clip(h, None, 0).sum())
    net = float(h.sum())
    # tail = everything after the first return to <=0 following the peak
    after = np.where(h[ipk:] <= 0)[0]
    itail = ipk + (int(after[0]) if len(after) else 0)
    tail = float(h[itail:].sum())
    return dict(peak=peak, ipk=ipk, pos_area=pos, neg_area=neg,
                net_area=net, net_over_pos=net / pos if pos else np.nan,
                tail_start=itail, tail_area=tail,
                tail_over_pos=tail / pos if pos else np.nan)


def main():
    channels = [c for c in range(120) if c not in IGNORE_CHANNELS]
    engines = {v: DecoEngine(v) for v in ("v0", "v1", "np04")}

    rows = []
    kernels = {}
    for ver, eng in engines.items():
        for ch in channels:
            h, amp = eng.kernel(ch)
            r = kernel_row(h)
            r.update(version=ver, opch=ch, vendor=VENDOR[ch], apa=4 - ch // 40)
            rows.append(r)
            kernels[f"{ver}_ch{ch}"] = h.astype(np.float32)

    fields = ["version", "opch", "vendor", "apa", "peak", "ipk", "pos_area",
              "neg_area", "net_area", "net_over_pos", "tail_start",
              "tail_area", "tail_over_pos"]
    with open(os.path.join(HERE, "kernel_metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.6g}" if isinstance(r[k], float) else r[k])
                        for k in fields})
    np.savez_compressed(os.path.join(HERE, "kernels.npz"), **kernels)

    # quick console summary per version
    for ver in engines:
        nop = np.array([r["net_over_pos"] for r in rows if r["version"] == ver])
        print(f"{ver:5s} net_area/pos_area: median={np.median(nop):+.3f} "
              f"min={nop.min():+.3f} max={nop.max():+.3f}  "
              f"|>0.1|: {(np.abs(nop) > 0.1).sum()}/{len(nop)} channels")


if __name__ == "__main__":
    main()
