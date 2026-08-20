#!/bin/sh
# run_e3.sh -- experiment E3 (a security-bug database as a training set), end to end.
#
#   1. run train.py -- PART 1 shape-classifies a real Juliet C/C++ slice (frozen census,
#      no network at run time); PART 2 runs the training loop (propose, record-before-
#      verify, mechanically verify against Concrete, cache by shape, generalize to a
#      held-out same-shape test split) against the design doc's sanctioned fallback
#      corpus, and asserts the bad()-proved-safe guardrail every iteration.
#   2. assemble TRAIN-RESULTS.md from the captured artifact via make_results.py.
#
# Everything lands in ./out/: train.txt (stdout+stderr), train.rc (exit code).
# No `set -e` (invalid on WSL bash); the script records the exit code explicitly.
#
# eval/refanalyzer.py and eval/examples.py are imported UNCHANGED by train.py.
# juliet_census.json is a frozen, commit-pinned artifact (see its own `meta` block) --
# this script does NOT hit the network; re-fetching the census is a separate, manual step.

cd "$(dirname "$0")" || exit 1

mkdir -p out

echo "=== E3: a security-bug database as a training set ==="
python3 train.py > out/train.txt 2>&1
echo $? > out/train.rc
cat out/train.txt

echo "=== E3: assembling TRAIN-RESULTS.md ==="
python3 make_results.py

echo "=== E3: done ==="
echo "train.py exit code (0 = guardrail held, all proposals verified as reported): $(cat out/train.rc)"
