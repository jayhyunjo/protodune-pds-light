#!/bin/bash
# Dump the PDVD raw light waveforms from the pdsraw ART files into PLAIN-ROOT flat trees
# (raw_waveform tree) -- the _final.root analog for the Xin handoff.
# Run INSIDE the SL7 container.
#   apptainer exec -B /cvmfs -B /exp -B /tmp -B /run/user \
#     /cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest \
#     bash -lc 'bash <repo>/pdvd/scripts/run_pdvd_rawwf_dump.sh'
# Override IND (dir of *_pdsraw.root) and OUT if your data lives elsewhere.

source /cvmfs/dune.opensciencegrid.org/products/dune/setup_dune.sh >/dev/null 2>&1
setup dunesw v10_21_00d00 -q e26:prof

SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IND="${IND:-/exp/dune/data/users/jjo/pdvd_data/pdsraw_out}"
OUT="${OUT:-/exp/dune/data/users/jjo/pdvd_data/rawwf_out}"
DUMP="$SDIR/pdvd_dump_rawwf.py"
mkdir -p "$OUT"

for f in "$IND"/*_pdsraw.root; do
  case "$f" in *TEST2*) continue;; esac
  tag=$(basename "${f%_pdsraw.root}")
  python "$DUMP" "$f" "$OUT/${tag}_rawwf.root" --max-events -1 > "$OUT/${tag}_rawwf.log" 2>&1
  echo "  $tag  rc=$?  -> ${tag}_rawwf.root"
done
echo "ALL DONE -> $OUT"
ls -lh "$OUT"/*_rawwf.root 2>/dev/null
