# Folding: Recovering Precision in Interval-Based Static Analysis

A paper on **folding** — recovering precision in sound, interval-based static analysis
without enriching the abstract domain. The reachable states of real programs are often
scattered, with dead bands between them that any convex approximation must include;
folding applies a change of variables so the reachable set becomes compact and a simple
domain represents it exactly.

**Published:** [10.5281/zenodo.22035920](https://doi.org/10.5281/zenodo.22035920)

> Adi Oltean. *Folding: Recovering Precision in Interval-Based Static Analysis.* 2026.
> DOI: [10.5281/zenodo.22035920](https://doi.org/10.5281/zenodo.22035920).

| Path | What |
|---|---|
| `folding.tex` / `folding.pdf` | The paper (single source of truth; `\paperversion` names each revision) |
| `build.sh` | Pinned-toolchain build plus an extraction gate: identifiers must survive `pdftotext`, since the PDF is converted for reading and indexing |
| `eval/` | The reference interval analysis, the pattern experiments, the dead-band measurements, the public-code shape census, and the CVE case study |
| `proof-lean/` | Lean 4 mechanization of the exactness theorems — sorry-free, no external dependencies |

## Reproducing

    python3 eval/run.py            # reprints every table in the evaluation
    python3 eval/run.py --check    # re-asserts every expectation; nonzero on failure
    python3 eval/proof/check_proofs.py
    bash proof-lean/setup.sh       # Lean toolchain, then: lake build

Verification coverage is deliberately uneven and is recorded per theorem rather than
claimed uniformly: `eval/proof/` discharges the exactness theorems by exhaustive
enumeration at finite widths, and `proof-lean/` mechanizes their width-parametric
statements. See `proof-lean/README.md` for exactly what is and is not mechanized.
