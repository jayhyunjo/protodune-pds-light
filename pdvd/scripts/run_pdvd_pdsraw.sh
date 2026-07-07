#!/bin/bash
# Decode the ProtoDUNE-VD PDS and save the RAW light waveforms.
#   raw HDF5  --pdvd_pds_raw.fcl (pdvddaphne)-->  <tag>_pdsraw.root
#                                                 product: raw::OpDetWaveform  tag "pdvddaphne:daq"
#
# Run INSIDE the SL7 container (dunesw v10_21_00d00 is slf7-only, no EL9 build):
#   apptainer exec -B /cvmfs -B /exp -B /tmp -B /run/user \
#     /cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest \
#     bash -lc 'NEVT=2 bash <repo>/pdvd/scripts/run_pdvd_pdsraw.sh'   # quick test
#   ...drop NEVT for all events. Set IND=<your raw-hdf5 dir> to point at your data.
# NOTE: no 'set -u' -- the ups/dunesw setup scripts reference unset vars.

source /cvmfs/dune.opensciencegrid.org/products/dune/setup_dune.sh >/dev/null 2>&1
setup dunesw v10_21_00d00 -q e26:prof

SDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FCL="$SDIR/../fcl/pdvd_pds_raw.fcl"
IND="${IND:-/exp/dune/data/users/jjo/pdvd_data}"   # override: IND=<your raw-hdf5 dir>
OUT="$IND/pdsraw_out"
mkdir -p "$OUT"; cd "$OUT"

NARG=""
if [ -n "${NEVT:-}" ]; then NARG="-n ${NEVT}"; fi

# Process every raw HDF5 in pdvd_data (edit to a fixed list if you prefer).
shopt -s nullglob
FILES=("$IND"/np02vd_raw_*.hdf5)

for f in "${FILES[@]}"; do
  tag=$(basename "${f%.hdf5}")
  echo "############################## $tag ##############################"
  lar -c "$FCL" -s "$f" -o "$OUT/${tag}_pdsraw.root" $NARG \
      > "$OUT/${tag}_pdsraw.log" 2>&1
  rc=$?
  echo "  rc=$rc -> ${tag}_pdsraw.root"
  [ $rc -ne 0 ] && echo "  FAILED (see ${tag}_pdsraw.log)"
done
echo "ALL DONE -> $OUT"
ls -lh "$OUT"/*_pdsraw.root 2>/dev/null
