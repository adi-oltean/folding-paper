#!/bin/sh
# run_e1.sh -- experiment E1 (folding precision on real pre-fix OpenSSL CVE code), end to
# end for CVE-2025-68160 (linebuffer_write, crypto/bio/bf_lbuf.c).
#
#   1. run cve_68160.py -- builds the IR model, runs baseline vs. with-fold analysis,
#      cross-checks against the concrete interpreter, checks soundness, prints the report.
#   2. assemble E1-RESULTS.md from the captured artifact via make_results.py.
#
# Everything lands in ./out/: cve_68160.txt (stdout+stderr), cve_68160.rc (exit code).
# No `set -e` (invalid on WSL bash); the script records the exit code explicitly.
#
# eval/refanalyzer.py is imported UNCHANGED by cve_68160.py (see its own header).

cd "$(dirname "$0")" || exit 1

mkdir -p out

echo "=== E1: CVE-2025-68160 -- linebuffer_write (crypto/bio/bf_lbuf.c) ==="
python3 cve_68160.py > out/cve_68160.txt 2>&1
echo $? > out/cve_68160.rc
cat out/cve_68160.txt

echo "=== E1: assembling E1-RESULTS.md ==="
python3 make_results.py

echo "=== E1: done ==="
echo "cve_68160 exit code (0 = all harness expectations held): $(cat out/cve_68160.rc)"
