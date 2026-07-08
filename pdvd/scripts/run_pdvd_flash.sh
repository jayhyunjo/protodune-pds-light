#!/bin/bash
# Reprocess PDVD raw HDF5 -> plain-ROOT flash file (flash / flash_opdet / ophit trees),
# using the FIXED OpFlashFinderVerticalDrift (studies/pdvd_flash_finder/).
#   raw .hdf5 --[lar pdvd_pds_flash.fcl, mrbslp]--> lean art (ophit+opflash)
#             --[pdvd_dump_flash.py]--> <tag>_flash.root  (plain ROOT, no art dep to read)
#
# Run INSIDE the SL7 container:
#   apptainer exec -B /cvmfs -B /exp -B /tmp -B /run/user \
#     /cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest \
#     bash -lc 'bash <repo>/pdvd/scripts/run_pdvd_flash.sh'
# Overrides: IND (raw .hdf5 dir), OUT, DEV (mrb dev area w/ patched finder),
#            PAT (filename glob, default *), NEV (events/file, default -1 = all).

# NB: no `set -u` -- the ups/dunesw setup scripts reference unset vars.
source /cvmfs/dune.opensciencegrid.org/products/dune/setup_dune.sh >/dev/null 2>&1
setup dunesw v10_21_00d00 -q e26:prof
DEV="${DEV:-/exp/dune/app/users/jjo/vddev}"
source "$DEV"/localProducts*/setup
mrbslp

SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IND="${IND:-/exp/dune/data/users/jjo/pdvd_data}"
OUT="${OUT:-/exp/dune/data/users/jjo/pdvd_data/flash_out}"
FCL="${FCL:-$SDIR/../fcl/pdvd_pds_flash.fcl}"
DUMP="$SDIR/pdvd_dump_flash.py"
PAT="${PAT:-*}"
NEV="${NEV:--1}"
mkdir -p "$OUT" "$OUT/art"

shopt -s nullglob
for f in "$IND"/${PAT}.hdf5; do
  tag=$(basename "$f" .hdf5)
  art="$OUT/art/${tag}_flashreco.root"
  echo "== $tag =="
  lar -c "$FCL" -s "$f" -n "$NEV" -o "$art" -T "$OUT/${tag}_flash_hist.root" > "$OUT/${tag}_reco.log" 2>&1
  rc1=$?
  python "$DUMP" "$art" "$OUT/${tag}_flash.root" --max-events -1 > "$OUT/${tag}_dump.log" 2>&1
  rc2=$?
  echo "  $tag  reco_rc=$rc1  dump_rc=$rc2  -> ${tag}_flash.root"
done
echo "ALL DONE -> $OUT"
ls -lh "$OUT"/*_flash.root 2>/dev/null
