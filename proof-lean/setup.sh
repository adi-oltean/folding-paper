#!/usr/bin/env bash
# Build the FoldingProofs Lean 4 development from a cold checkout.
#
# The project has ZERO external Lean dependencies (no Mathlib, no Batteries), so
# there is nothing to download beyond the Lean toolchain itself and no
# `lake exe cache get` step. On a machine that already has elan, this is a
# ~5 second build.
#
# Usage:  bash setup.sh          (from this directory)

set -o errexit
set -o nounset

cd "$(dirname "$0")"

# 1. Locate elan (the Lean toolchain manager). It is usually at ~/.elan/bin but
#    is often not on PATH.
if command -v lake >/dev/null 2>&1; then
  LAKE=lake
elif [ -x "$HOME/.elan/bin/lake" ]; then
  LAKE="$HOME/.elan/bin/lake"
  export PATH="$HOME/.elan/bin:$PATH"
else
  echo "elan/lake not found. Installing elan (Lean toolchain manager)..."
  curl -sSf https://elan.lean-lang.org/elan-init.sh | sh -s -- -y --default-toolchain none
  export PATH="$HOME/.elan/bin:$PATH"
  LAKE="$HOME/.elan/bin/lake"
fi

# 2. elan reads ./lean-toolchain and installs that exact toolchain on demand
#    (leanprover/lean4:v4.33.0). No manual `elan toolchain install` needed.
echo "Toolchain: $(cat lean-toolchain)"

# 3. Build. Elaboration + kernel checking of every declaration happens here;
#    the `#print axioms` audit output is printed by FoldingProofs/Audit.lean.
"$LAKE" build

echo
echo "Build finished. To re-print the axiom audit on demand:"
echo "  $LAKE env lean FoldingProofs/Audit.lean"
