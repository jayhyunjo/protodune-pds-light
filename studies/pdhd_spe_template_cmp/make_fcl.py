"""Generate the interim mixed SPE-template fcl from channel_verdicts.csv:
channels where the NP04 vendor-average outperforms v1 get the NP04 kernel,
the rest keep their v1 per-channel kernel. Noise templates / IgnoreChannels /
filter settings are inherited from the v1 table (overlay on
protodunehd_deconvolution, like protodunehd_pds_channels_data_v1).

Writes protodunehd_template_list_v1_np04mix.fcl next to this script.
"""

import csv
import os

from pdhd_deco import spe_template_map, VENDOR

HERE = os.path.dirname(os.path.abspath(__file__))

rows = {int(r["opch"]): r for r in
        csv.DictReader(open(os.path.join(HERE, "channel_verdicts.csv")))}
v1_files = {ch: "v1/" + os.path.basename(p)
            for ch, p in spe_template_map("v1").items()}

files = ["SPE_NP04_FBK_2024_without_pretrigger.dat",
         "SPE_NP04_HPK_2024_without_pretrigger.dat"]
findex = {f: i for i, f in enumerate(files)}
chans, tmpls = [], []
n_np04 = 0
for ch in sorted(v1_files):
    if rows[ch]["recommended"] == "np04":
        fn = files[0] if VENDOR[ch] == "FBK" else files[1]
        n_np04 += 1
    else:
        fn = v1_files[ch]
        if fn not in findex:
            findex[fn] = len(files)
            files.append(fn)
    chans.append(ch)
    tmpls.append(findex[fn])

lines = []
lines.append("#include \"protodunehd_template_list_v1.fcl\"")
lines.append("BEGIN_PROLOG")
lines.append("")
lines.append("# Interim PDHD SPE-template set (data): NP04 vendor-average")
lines.append(f"# kernels on the {n_np04} channels where they outperform the")
lines.append("# v1 per-channel kernels (deep tail undershoot from the v1")
lines.append("# kernels' positive net area), v1 per-channel kernels kept on")
lines.append(f"# the remaining {len(chans)-n_np04} channels.")
lines.append("# Derived from runs 27305/27980/28084/29107; see")
lines.append("# protodune-pds-light/studies/pdhd_spe_template_cmp/.")
lines.append("protodunehd_template_list_v1_np04mix: {")
lines.append("   @table::protodunehd_template_list_v1")
lines.append("")
lines.append("   SPETemplatePath: \"ProtoDUNE/HD/opdetresponse/\"")
lines.append("   SPETemplateFiles: [")
for i, fn in enumerate(files):
    comma = "," if i < len(files) - 1 else ""
    lines.append(f"      \"{fn}\"{comma}")
lines.append("   ]")


def seq(vals, per_line=15):
    out = []
    for i in range(0, len(vals), per_line):
        chunk = ", ".join(str(v) for v in vals[i:i + per_line])
        tail = "," if i + per_line < len(vals) else ""
        out.append(f"      {chunk}{tail}")
    return out


lines.append("   SPETemplateMapChannels: [")
lines += seq(chans)
lines.append("   ]")
lines.append("   SPETemplateMapTemplates: [")
lines += seq(tmpls)
lines.append("   ]")
lines.append("}")
lines.append("")
lines.append("END_PROLOG")

out = os.path.join(HERE, "protodunehd_template_list_v1_np04mix.fcl")
with open(out, "w") as fh:
    fh.write("\n".join(lines) + "\n")
print(f"wrote {out}: {n_np04} channels -> NP04, "
      f"{len(chans)-n_np04} keep v1, {len(files)} template files")
