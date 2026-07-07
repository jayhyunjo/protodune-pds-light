#!/bin/bash
# Two-step workflow over the PDHD raw files:
#   (1) keepup reco            : hdf5            -> <tag>_keepup.root  (art)
#   (2) flat tree + offset     : <tag>_keepup.root -> <tag>_final.root (plain ROOT:
#                                PDS flat trees + waveform histos + trigger_offset)
#
# Usage (inside the SL7 container):
#   NEVT=2 bash run_workflow.sh      # quick test: 2 events/file
#   bash run_workflow.sh             # all events
# NOTE: no 'set -u' -- the ups/dunesw setup scripts reference unset vars and
# would abort a nounset shell before any reco runs.

source /cvmfs/dune.opensciencegrid.org/products/dune/setup_dune.sh >/dev/null 2>&1
setup dunesw v10_20_09d00 -q e26:prof
source /exp/dune/app/users/jjo/temp/offdev/localProducts*/setup
mrbslp                                    # puts TriggerOffsetAna plugin on the path

FCLDIR=/exp/dune/app/users/jjo/temp
IND=/exp/dune/data/users/jjo/pdhd_data
OUT=/exp/dune/data/users/jjo/pdhd_data/workflow_out
mkdir -p "$OUT"; cd "$OUT"

# event-count flag: NEVT unset/empty -> all events
NARG=""
if [ -n "${NEVT:-}" ]; then NARG="-n ${NEVT}"; fi

FILES=(
  np04hd_raw_run027305_0001_dataflow2_datawriter_0_20240619T173255.hdf5
  np04hd_raw_run027980_0000_dataflow0_datawriter_0_20240711T160710.hdf5
  np04hd_raw_run028084_0300_dataflow0_datawriter_0_20240720T192229.hdf5
  np04hd_raw_run029107_0004_dataflow7_datawriter_0_20240906T163315.hdf5
)

for f in "${FILES[@]}"; do
  tag="${f%.hdf5}"
  echo "############################## $tag ##############################"
  if [ ! -f "$IND/$f" ]; then echo "  MISSING input $IND/$f -- skip"; continue; fi

  echo "[1/2] keepup reco ..."
  lar -c "$FCLDIR/standard_reco_protodunehd_keepup.fcl" -s "$IND/$f" \
      -o "$OUT/${tag}_keepup.root" $NARG > "$OUT/${tag}_keepup.log" 2>&1
  rc1=$?
  echo "      keepup rc=$rc1 -> ${tag}_keepup.root"
  [ $rc1 -ne 0 ] && { echo "      FAILED keepup (see ${tag}_keepup.log)"; continue; }

  echo "[2/2] flat tree + trigger offset ..."
  lar -c "$FCLDIR/pds_flat_tree.fcl" -s "$OUT/${tag}_keepup.root" \
      -T "$OUT/${tag}_final.root" $NARG > "$OUT/${tag}_flat.log" 2>&1
  rc2=$?
  echo "      flat   rc=$rc2 -> ${tag}_final.root"
done
echo "ALL DONE -> $OUT"
ls -lh "$OUT"/*_final.root 2>/dev/null
