"""Aggregate the per-record metrics into per-channel verdicts:
does the NP04 vendor-average SPE template outperform the per-channel v1
(and v0) templates on deconvolved-waveform tail quality?

Pulse selection (per record):
  raw_amp >= AMP_MIN ADC  (~2-3 PE; below that tail metrics are noise)
  raw_min >  SAT_MIN      (pulse not clipped at the ADC bottom)
  40 <= ipk <= 700        (>= ~5 us of tail inside the record, all templates)

Per channel x template: median undershoot ratio (min of tail / prompt peak),
median tail-negative-area / prompt-positive-area, median late-baseline ratio.

Verdict (v1 vs NP04, likewise v0):
  vendor-better  : median|u_ratio| improves by > U_DELTA with NP04, and the
                   improvement has the same sign in every run with >= 10
                   selected pulses
  comparable     : |difference| <= U_DELTA
  v1-better      : v1 beats NP04 by > U_DELTA
Channels with < N_MIN selected pulses are 'insufficient-stats'.

Writes channel_verdicts.csv next to this script.
"""

import csv
import glob
import os
import numpy as np

from pdhd_deco import VENDOR

OUT_DIR = "/nfs/data/1/jjo/data/PDHD/spe_template_cmp"
HERE = os.path.dirname(os.path.abspath(__file__))

AMP_MIN = 25.0   # ADC, ~2-3 PE (SPE amp 8.7/13.8 ADC FBK/HPK)
SAT_MIN = 20     # ADC counts above the 14-bit bottom
IPK_LO, IPK_HI = 40, 700
N_MIN = 20
U_DELTA = 0.05   # undershoot-ratio difference that counts as "better"

TEMPLATES = ("v1", "v0", "np04")


def load_all():
    files = sorted(glob.glob(f"{OUT_DIR}/metrics_run*.npz"))
    assert files, f"no metrics files in {OUT_DIR}"
    cols = {}
    for fn in files:
        d = np.load(fn)
        for k in d.files:
            cols.setdefault(k, []).append(d[k])
    return {k: np.concatenate(v) for k, v in cols.items()}


def main():
    d = load_all()
    sel = (d["raw_amp"] >= AMP_MIN) & (d["raw_min"] > SAT_MIN)
    for t in TEMPLATES:
        sel &= (d[f"{t}_ipk"] >= IPK_LO) & (d[f"{t}_ipk"] <= IPK_HI)
        sel &= d[f"{t}_peak"] > 0
    print(f"selected {sel.sum()} / {len(sel)} records")

    # derived per-record ratios
    ratios = {}
    for t in TEMPLATES:
        ratios[f"{t}_u"] = d[f"{t}_min_tail"] / d[f"{t}_peak"]
        ratios[f"{t}_negfrac"] = d[f"{t}_neg_area"] / d[f"{t}_prompt_pos"]
        ratios[f"{t}_late"] = d[f"{t}_late_mean"] / d[f"{t}_peak"]

    runs = np.unique(d["run"])
    rows = []
    for ch in np.unique(d["opch"][sel]):
        m = sel & (d["opch"] == ch)
        row = dict(opch=int(ch), apa=4 - int(ch) // 40, vendor=VENDOR[int(ch)],
                   n_sel=int(m.sum()))
        for t in TEMPLATES:
            row[f"{t}_u_med"] = float(np.median(ratios[f"{t}_u"][m]))
            row[f"{t}_negfrac_med"] = float(np.median(ratios[f"{t}_negfrac"][m]))
            row[f"{t}_late_med"] = float(np.median(ratios[f"{t}_late"][m]))

        for t in ("v1", "v0"):
            # improvement of NP04 over t in |undershoot ratio|
            delta = abs(row[f"{t}_u_med"]) - abs(row["np04_u_med"])
            row[f"d_u_{t}"] = float(delta)
            # per-run consistency
            per_run = []
            for r in runs:
                mr = m & (d["run"] == r)
                if mr.sum() >= 10:
                    per_run.append(
                        np.median(np.abs(ratios[f"{t}_u"][mr]))
                        - np.median(np.abs(ratios["np04_u"][mr])))
            row[f"n_runs_{t}"] = len(per_run)
            consistent = all(x > 0 for x in per_run) if per_run else False
            if row["n_sel"] < N_MIN:
                v = "insufficient-stats"
            elif delta > U_DELTA and consistent:
                v = "vendor-better"
            elif delta > U_DELTA:
                v = "vendor-better-inconsistent"
            elif delta < -U_DELTA:
                v = f"{t}-better"
            else:
                v = "comparable"
            row[f"verdict_{t}"] = v
            # improvement in integrated tail-negative area (PE-integral bias)
            row[f"d_negfrac_{t}"] = float(row[f"{t}_negfrac_med"]
                                          - row["np04_negfrac_med"])

        # recommendation for the interim config, v1 as the reference:
        # switch to the NP04 vendor kernel when it improves the undershoot
        # depth consistently OR clearly improves the integrated tail while
        # not degrading the depth; keep v1 otherwise.
        if row["n_sel"] < N_MIN:
            rec = "insufficient-stats"
        elif (row["d_u_v1"] > U_DELTA and row["verdict_v1"] == "vendor-better") \
                or (row["d_negfrac_v1"] > 0.5 and row["d_u_v1"] > -0.02):
            rec = "np04"
        else:
            rec = "keep-v1"
        row["recommended"] = rec
        rows.append(row)

    fields = list(rows[0].keys())
    with open(os.path.join(HERE, "channel_verdicts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["opch"]):
            w.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v)
                        for k, v in r.items()})

    from collections import Counter
    for t in ("v1", "v0"):
        c = Counter(r[f"verdict_{t}"] for r in rows)
        print(f"verdicts vs {t}: {dict(c)}")
    c = Counter(r["recommended"] for r in rows)
    print(f"recommended: {dict(c)}")
    np04_list = sorted(r["opch"] for r in rows if r["recommended"] == "np04")
    print(f"np04 channels ({len(np04_list)}): {np04_list}")
    print(f"wrote {os.path.join(HERE, 'channel_verdicts.csv')} "
          f"({len(rows)} channels)")


if __name__ == "__main__":
    main()
