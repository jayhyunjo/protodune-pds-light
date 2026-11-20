"""Per-record baseline/pedestal metrics of the deconvolved waveforms, for the
pre-pulse region the SPE-template comparison did not cover:

  start_mean  mean of ticks 0-19    (the module's PostBLCorrection window)
  pre_mean    mean of ticks 25-45   (between BL window and the trigger pulse)
  end_mean    mean of ticks 984-1023 (record end; FFT-circularity check)

Meaningful as "pre-pulse pedestal" only for records with the main pulse at
the standard trigger position (deco ipk ~50-75); the aggregation applies that
cut. Writes baseline_run<RUN>.npz per run, aligned row-by-row with
metrics_run<RUN>.npz.

Usage: python add_baseline_metrics.py <final.root> [...]
"""

import os
import sys
import numpy as np
import uproot
import awkward as ak

OUT_DIR = "/nfs/data/1/jjo/data/PDHD/spe_template_cmp"


def cols(wf):
    return dict(start_mean=wf[:, :20].mean(axis=1),
                pre_mean=wf[:, 25:45].mean(axis=1),
                end_mean=wf[:, -40:].mean(axis=1))


def main():
    for path in sys.argv[1:]:
        f = uproot.open(path)
        run = None
        for r in (27305, 27980, 28084, 29107):
            if f"run0{r}" in os.path.basename(path):
                run = r
        met = np.load(f"{OUT_DIR}/metrics_run{run}.npz")
        keys = list(zip(met["event"].tolist(), met["opch"].tolist(),
                        met["timestamp"].tolist()))
        out = {}
        for t, tn in (("v1", "decodump/deco_waveform"),
                      ("v0", "decodumpv0/deco_waveform")):
            tr = f[tn]
            dm = tr.arrays(["event", "opch", "timestamp"], library="np")
            pos = {k: i for i, k in enumerate(zip(
                dm["event"].tolist(), dm["opch"].tolist(),
                dm["timestamp"].tolist()))}
            ix = np.array([pos[k] for k in keys])
            wf = ak.to_numpy(ak.to_regular(
                tr.arrays(["adc"], library="ak")["adc"]))[ix]
            for name, arr in cols(wf).items():
                out[f"{t}_{name}"] = arr.astype(np.float32)
            del wf
        npz = np.load(f"{OUT_DIR}/np04deco_run{run}.npz")
        assert np.array_equal(npz["event"], met["event"])
        for name, arr in cols(npz["wf"]).items():
            out[f"np04_{name}"] = arr.astype(np.float32)
        np.savez_compressed(f"{OUT_DIR}/baseline_run{run}.npz", **out)
        print(f"run {run}: wrote baseline_run{run}.npz ({len(keys)} records)")


if __name__ == "__main__":
    main()
