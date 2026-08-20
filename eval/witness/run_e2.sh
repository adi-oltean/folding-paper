#!/bin/sh
# run_e2.sh -- experiment E2 (exact folds are self-witnessing), end to end.
#
#   1. run witness.py -- for the three exact-fold E0 patterns (affine IV #1, ZigZag #13,
#      lockstep #16), invert the fold on the mutant's failing check, confirm the recovered
#      concrete input actually violates via refanalyzer's exhaustive interpreter, and
#      contrast against the same inversion applied to the baseline (no-fact) alarm.
#   2. assemble WITNESS-RESULTS.md from the captured artifact via make_results.py.
#
# Everything lands in ./out/: witness.txt (stdout+stderr), witness.rc (exit code).
# No `set -e` (invalid on WSL bash); the script records the exit code explicitly.
#
# eval/refanalyzer.py and eval/examples.py are imported UNCHANGED by witness.py.

cd "$(dirname "$0")" || exit 1

mkdir -p out

echo "=== E2: exact-fold witnesses (patterns 1, 13, 16) ==="
python3 witness.py > out/witness.txt 2>&1
echo $? > out/witness.rc
cat out/witness.txt

echo "=== E2: assembling WITNESS-RESULTS.md ==="
python3 make_results.py

echo "=== E2: done ==="
echo "witness.py exit code (0 = all inversions confirmed, all contrasts held): $(cat out/witness.rc)"
