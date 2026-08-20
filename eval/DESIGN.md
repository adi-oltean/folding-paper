# Evaluation design — measuring recovered precision

**Goal:** a paper chapter with quantitative, *statistical* evidence of how much precision
folding recovers — organized, reproducible, and independent of any private
implementation. Everything reported must be reproducible from this repo by a reader with
Python.

## Why the obvious approach is unavailable, and what replaces it

An A/B over a production analyzer is not available here (and would tie the paper to a
particular implementation, which it deliberately avoids). The replacement is stronger for
a technique paper: three independent legs, each with a different epistemic status.

| Leg | What it establishes | Epistemic status |
|---|---|---|
| **A. Closed-form dead-band fractions** | The precision a fold recovers *by construction*, per pattern, as exact formulas with parameter sweeps | Proved arithmetic — no code needed to trust it |
| **B. Reference-analyzer micro-suite** | That an actual interval analysis realizes those gains: verdict flips (FAIL→PROVEN) and width ratios on canonical programs, with soundness witnesses | Measured, receipt-backed — `python3 eval/run.py` reprints every number in the chapter |
| **C. Shape frequency in public code** | That the folded shapes are what real embedded code is made of — the gains are not strawmen | Counted on pinned public commits — commands included |

The three multiply: (frequency of shape) × (dead-band fraction of its fold) is the
expected precision recovered on real code, and each factor is independently checkable.

## Leg A — the metric and the closed forms

**Dead-band fraction (DBF)** at a program point: the share of a convex approximation
that is unreachable, `DBF = 1 − |S_reach| / |γ(a)|`.
This is exactly "the fraction of the interval that is dead bands," i.e. what folding
eliminates; DBF is the precision *available* to recover, and a fold that renders the set
contiguous recovers all of it.

**Reconciliation (2026-08-20, from the build):** the closed forms below are each exact
against a specific, NAMED denominator, not uniformly against the tightest hull —
patterns 1/2 against *the interval the analysis holds without the fact*, 5/6 against
*the declared byte extent of the region*, 13 against *the k-bit encoded space*; patterns
3, 14, 16 coincide with the hull. The harness prints both `DBF(hull)` and `DBF(denom)`,
declares each formula's denominator before measuring, and checks against the declared
one — nothing was reclassified after seeing a number.

Per-pattern closed forms (each verified in leg B's harness, then swept):

| Pattern | DBF | Sweep |
|---|---|---|
| 1/2 affine IV, stride s | `(s−1)/s` (→ 1 as s grows) | s ∈ {2,4,8,16,64} |
| 3 geometric IV, width w | `1 − w/2^{w−1}` (≈1 already at w=8) | w ∈ {8,16,32,64} |
| 5/6 struct of size Z, k fields of size g accessed | `1 − k·g/Z` | realistic Z,k,g grid |
| 13 ZigZag on k-bit inputs | signed hull vs image: recovers the negative half — DBF `≈ 1/2` for the naive transport | k ∈ {8,16,32} |
| 14 sparse states, k legal codes over range R | `1 − k/R` (one-hot: `1 − w/2^{w−1}` again) | k, R grids |
| 16 lockstep pair over an n-point line in an n×n box | `1 − 1/n` | n sweep |

These curves are the "statistical" heart: not one number, but how recovered precision
scales with the shape parameter — and the observation that several patterns approach
DBF → 1, where a convex domain retains asymptotically *no* information without the fold.

**Second metric — verdict discharge.** DBF is domain-side; what a user feels is whether
the safety check proves. Leg B measures it directly.

## Leg B — the reference analyzer and the example-selection rule

**The analyzer** (`eval/refanalyzer.py`, target ≤ ~500 lines, no dependencies): a
textbook worklist interval analysis over a tiny loop IR (const/assign/add/mul/branch on
comparisons/back-edge/array-bounds-check), with standard widening-to-thresholds and ONE
extension: a fact-injection hook — `inject(point, var, fact)` — which is folding's
consumption mechanism in its smallest honest form. No pattern *detection* is
implemented or needed: the paper's validity conditions say what may be injected; the
harness injects exactly those facts and nothing else.

**The example-selection rule (the "organized way"):** the catalogue itself is the
sampling frame — **one canonical program per pattern, all sixteen**, no cherry-picking
within a pattern. Each example must satisfy four admission criteria:

1. **Minimal**: smallest program exhibiting the shape (fits in the appendix listing).
2. **Check-carrying**: contains one safety check (array bound / shift admissibility /
   value range) that plain intervals FAIL and the injected fact PROVES — the verdict
   flip is the measurement.
3. **Witness-carrying**: a mutant of the same program whose check is *genuinely unsafe*
   must STILL FAIL with the fact injected — the no-free-lunch control, one per example.
   (A fold that flipped the mutant would be unsound; the harness asserts this.)
4. **Parameterized** where the pattern has a natural parameter — the same program at
   s = 2,4,8,…, w = 8,16,32,… — so leg A's curves are *measured*, not just derived.

**Reported per example:** verdict without fact / with fact / mutant-with-fact (must be
FAIL); interval width at the check site, both ways; widening iterations both ways.
**Aggregate table for the chapter:** 16 rows → discharge rate (expected 16/16 flips with
0/16 mutant flips), median width ratio, and the swept curves for the parameterized
patterns.

**Trust story printed in the chapter:** the analyzer is small enough to read, the
injected facts are exactly the paper's validity-conditioned facts, and every number
reprints with one command. The harness also *re-verifies leg A*: for each swept point it
enumerates the concrete reachable set by direct simulation and checks the closed-form
DBF against it — the same brute-force discipline the paper's claim verification used.

## Leg C — shape frequency on public code

The point: the shapes are common, so the gains matter. Method: pinned-commit counts on
**public** embedded codebases only — candidates: nanopb (protobuf codec), libcsp
(CubeSat protocol stack), plus one or two widely known ones (zlib, FreeRTOS kernel) for
breadth. For each: repo, commit sha, LoC; counts per shape class (strided loops,
geometric/shift loops, bit-slice masks, monotone `|=` accumulation, clamps, zigzag,
sparse-state switches, lockstep pointer iteration) with the counting expressions
included so the numbers re-derive. Present as a frequency table + the ratio of
value-shaping sites to countable loops (the census result, now on public code only).

*Discipline:* counting is syntactic and stated as such (an occurrence count, not a
provability claim); no private codebase appears; each count's command is in
`eval/census.md`.

## What the chapter will NOT claim

- No claim about any production analyzer's precision or performance.
- No timing/performance numbers at all (out of scope for the note).
- No claim that DBF equals end-to-end alarm reduction — the chapter states the chain
  explicitly: frequency (C) says the shapes occur; DBF (A) says how much information the
  hull discards there; discharge (B) says an interval analysis with the fact proves what
  it otherwise cannot.

## Build plan

1. `eval/refanalyzer.py` + `eval/examples.py` (16 canonical + 16 mutants + sweeps) +
   `eval/run.py` (prints the chapter's tables; `--check` mode asserts all expectations —
   16 flips, 0 mutant flips, closed-form DBF matches simulation).
2. `eval/census.md` + `eval/census.py` over pinned public checkouts.
3. The chapter (`\section{How much precision is recovered}`) written ONLY from `run.py`
   output.
