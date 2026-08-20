#!/bin/sh
# run_proof.sh -- reproduce the proof-checker report for research/precision-proofs.md.
#
#   ./eval/proof/run_proof.sh              print the report
#   ./eval/proof/run_proof.sh --check      ... and exit nonzero if any [CHECK-n] FAILED
#
# Deterministic: no wall-clock, no RNG. Run from anywhere; resolves its own directory.

DIR=$(dirname "$0")
exec python3 "$DIR/check_proofs.py" "$@"
