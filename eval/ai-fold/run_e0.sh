#!/bin/sh
# run_e0.sh -- experiment E0 (AI-driven folding), end to end.
#
#   1. compile the four equivalence drivers with gcc -O2
#   2. run them in sequence (case 1, 2, 3, then the negative control)
#   3. run the IR precision leg (precision.py -> eval/refanalyzer.py, unchanged)
#   4. regenerate E0-RESULTS.md from the captured artifacts
#
# Everything lands in ./out/ : <name>.txt (stdout+stderr), <name>.rc (exit code).
# The negative control is EXPECTED to exit nonzero; that is its passing outcome.
#
# No `set -e` (invalid on WSL bash); each step records its own exit code and
# make_results.py reports them.

cd "$(dirname "$0")" || exit 1

CC=/usr/bin/gcc
CFLAGS="-O2 -Wall -Wextra -std=c99"

mkdir -p out

echo "=== E0: compiling (gcc -O2) ==="

$CC $CFLAGS -o out/equiv_case1 equiv_case1.c
if [ $? -ne 0 ]; then echo "compile failed: equiv_case1.c"; exit 1; fi

$CC $CFLAGS -o out/equiv_case2 equiv_case2.c
if [ $? -ne 0 ]; then echo "compile failed: equiv_case2.c"; exit 1; fi

$CC $CFLAGS -o out/equiv_case3 equiv_case3.c
if [ $? -ne 0 ]; then echo "compile failed: equiv_case3.c"; exit 1; fi

$CC $CFLAGS -o out/equiv_case_neg equiv_case_neg.c
if [ $? -ne 0 ]; then echo "compile failed: equiv_case_neg.c"; exit 1; fi

echo "=== E0: case 1 -- csum_from32to16, full 2^32 exhaustive ==="
./out/equiv_case1 > out/case1.txt 2>&1
echo $? > out/case1.rc
cat out/case1.txt

echo "=== E0: case 2 -- nanopb ZigZag, 8/16/32-bit exhaustive + 64-bit boundary & sample ==="
./out/equiv_case2 > out/case2.txt 2>&1
echo $? > out/case2.rc
cat out/case2.txt

echo "=== E0: case 3 -- _find_first_bit, two exhaustive configurations ==="
./out/equiv_case3 > out/case3.txt 2>&1
echo $? > out/case3.rc
cat out/case3.txt

echo "=== E0: negative control -- proposal N (nonzero exit is the PASSING outcome) ==="
./out/equiv_case_neg > out/neg.txt 2>&1
echo $? > out/neg.rc
cat out/neg.txt

echo "=== E0: precision leg -- eval/refanalyzer.py unchanged, no injected facts ==="
python3 precision.py > out/precision.txt 2>&1
echo $? > out/precision.rc
cat out/precision.txt

echo "=== E0: assembling E0-RESULTS.md ==="
python3 make_results.py

echo "=== E0: done ==="
echo "equivalence exit codes (0 = EQUIV): case1=$(cat out/case1.rc) case2=$(cat out/case2.rc) case3=$(cat out/case3.rc)"
echo "negative control exit code (nonzero = correctly REJECTED): neg=$(cat out/neg.rc)"
echo "precision exit code (0 = all self-tests passed): $(cat out/precision.rc)"
