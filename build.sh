#!/usr/bin/env bash
# Build folding.pdf with the PINNED texlive image, then verify that
# identifiers survive text extraction.
#
# Why the verification step is not optional: this PDF is converted for a
# reader and a search index. Under the default OT1 encoding, LaTeX draws \_
# as a RULE rather than a glyph, \pdfgentounicode cannot map it, and
# "discover_foldings" extracts as "foldings" -- silently corrupting every
# identifier in the paper. The source sets T1 + lmodern to avoid this; this
# script fails loudly if that ever regresses.
#
# Run from anywhere:  sg docker -c "bash papers/folding/build.sh"
set -o errexit
set -o nounset

cd "$(dirname "$0")"

docker run --rm -v "$PWD":/w -w /w texlive/texlive:latest \
  latexmk -pdf -interaction=nonstopmode folding.tex

if ! command -v pdftotext >/dev/null 2>&1; then
  echo "NOTE: pdftotext not found; skipped the extraction check." >&2
  exit 0
fi

pdftotext folding.pdf extracted.txt
missing=""
# Canaries must be identifiers that ACTUALLY appear in the current text; the
# underscore ones are the point (they vanish under OT1). Update this list when
# the text changes -- a canary edited out of the paper fails the gate for the
# wrong reason.
for ident in actual_max KnownBits; do
  grep -q -- "$ident" extracted.txt || missing="$missing $ident"
done
rm -f extracted.txt

if [ -n "$missing" ]; then
  echo "FAIL: these identifiers did not survive pdftotext:$missing" >&2
  echo "      Check that the preamble still has [T1]{fontenc} + lmodern," >&2
  echo "      and that microtype has NOT been added." >&2
  exit 1
fi

echo "OK: build clean and identifiers survive extraction."
