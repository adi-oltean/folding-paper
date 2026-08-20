# `proof-lean` — Lean 4 mechanization of the parametric core of `research/precision-proofs.md`

This is a self-contained, **zero-dependency** Lean 4 development (core Lean only —
**no Mathlib, no Batteries**) that mechanizes the *all-width* (parametric) core of the
precision argument. It builds sorry-free and is kernel-checked.

The gap it closes: the enumeration seat (`eval/proof/`) discharges the finite-width
claims exhaustively, but recorded that the width-parametric claims were left open
("z3 not importable, all-width claims symbolic, not discharged"). Everything below is
proven for **all** strides, **all** trip counts, and **all** widths `k`, by the Lean kernel.

---

## What is proven

| Note's theorem | Lean name | Statement |
|---|---|---|
| **Thm 1** (valid ⇒ sound), meet core | `FoldingProofs.meet_sound` | In any domain whose `γ` is a meet-morphism: `R ⊆ γ a → R ⊆ γ b → R ⊆ γ (a ⊓ b)`. Injecting a *valid* fact removes no reachable state. |
| Thm 1, concrete instance | `FoldingProofs.Itv.gamma_meet`, `FoldingProofs.interval_meet_sound` | The `Int` interval domain **is** such a domain: `γ (I ⊓ J) = γ I ∩ γ J`, exactly; Thm 1 specialized to it. |
| **Thm 1′** (the gate is load-bearing) | `FoldingProofs.invalid_fold_drops_reachable` | By exhibition: `R = {0}`, baseline `[0,0]`, *invalid* fold `[1,1]` ⇒ the meet drops the reachable state `0`. |
| **Thm 2a**, pointwise half | `FoldingProofs.meet_no_regression` | `γ (a ⊓ b) ⊆ γ a` — the fold never loses precision at `p`. |
| **Thm 2c, affine IV** (∀ `c₀`, ∀ `s>0`, ∀ `m`) | `FoldingProofs.Affine.image_eq_range` | `g(R) = {0,…,m−1}` exactly, both inclusions, where `R = {c₀ + s·k ∣ k < m}` and `g i = (i − c₀)/s`. |
| Thm 2c, affine — no dead band | `FoldingProofs.Affine.hull_exact` (+ `hull_over`, `hull_under`) | `γ([0, m−1]) ↔ g(R)`: the interval hull equals the reachable folded set. Over- **and** under-approximation. |
| **Thm 2c, ZigZag** (∀ `k`) | `FoldingProofs.ZigZag.image_eq_range` | The image of `[−2^k, 2^k)` under `zigzag x = if 0 ≤ x then 2x else −2x−1` is exactly the contiguous range `[0, 2^{k+1})`. |
| Thm 2c, ZigZag — bijection | `FoldingProofs.ZigZag.unzig_zigzag`, `zigzag_unzig`, `zigzag_inj` | `unzig (zigzag x) = x` for **every** `x : Int` (so `zigzag` is injective); `zigzag (unzig y) = y` for `y ≥ 0`. |
| Thm 2c, ZigZag — no dead band | `FoldingProofs.ZigZag.hull_exact` (+ `hull_over`, `hull_under`) | `γ([0, 2^{k+1}−1]) ↔ R_g`, for all `k`. |
| **Cor 2c′** (self-witnessing) | `FoldingProofs.Affine.self_witnessing`, `FoldingProofs.ZigZag.self_witnessing` | Every folded value the abstraction admits has a concrete, genuinely reachable preimage, recovered by inverting the fold (`g⁻¹ j = c₀ + s·j`; `unzig y`). |
| **Thm 3** (inexact ⇒ may-only) | `FoldingProofs.Inexact.hull_strict`, `no_preimage`, `inexact_not_exact` | For offsets `{0,4,6}` with gcd `2`: folded set `{0,2,3}`, hull `[0,3]`; `1 ∈ γ(a_g) ∖ R_g`, and no offset folds to `1` — so an "alarm" at `1` would be a false witness. Discharged by `decide` (kernel evaluation). |

`FoldingProofs/Examples.lean` holds **anti-vacuity spot checks**: closed instances
(`c₀=5, s=3, m=4`; `k=2`; the `{0,4,6}` set) pinning the definitions to the concrete
behaviour the enumeration seat checks, so a definitional typo cannot make the parametric
statements vacuously true.

## What is NOT proven here (deliberate scope)

* **No abstract interpreter, no widening, no fixpoint.** Theorem 1's second half
  ("soundness propagates to every `q` by the standard fixpoint-soundness argument") and
  Theorem 2a's lfp statement are *not* formalized. What is mechanized is the
  **meet-soundness core** — the order-theoretic step the note actually leans on — plus
  the fact that the interval domain satisfies its hypothesis. The widened case remains,
  as the note says, a construction rather than a theorem.
* **No finite-width analyzer behaviour.** Concrete per-width behaviour (E0/E1 programs,
  the validity probes, dead-band fractions, verdict flips) is covered by the enumeration
  seat in `eval/` and `eval/proof/`, which is exhaustive at those widths. This
  development is the complement: the ∀-width statements enumeration cannot reach.
* **Thm 2b** (strict recovery / dead-band fractions) is a closed-form + enumeration
  result and is not mechanized here.
* **Lockstep** (the third bijective fold in Thm 2c) is not mechanized; its folded
  coordinate is literally the affine case (`i ∈ [0, n)`), so `Affine.hull_exact` with
  `c₀ = 0, s = 1` covers the folded-coordinate claim, and the two-dimensional statement
  (both counters together) is left to the enumeration seat.
* **Stride sign.** Every affine statement above is universally quantified over `s > 0`
  (ascending loops). Descending loops (`i -= s`) are not mechanized and rest on the
  enumeration seat's finite-width check.
* **Division convention.** Lean's `/` on `Int` is Euclidean (remainder always
  nonnegative); C's `/` truncates toward zero. `Affine.image_eq_range`'s `g i = (i −
  c₀)/s` uses Lean's convention, which agrees with C's truncating division exactly on the
  grids these folds use — offsets that are `c₀` plus a nonnegative multiple of `s`, the
  only inputs a matched pattern ever applies `g` to — but not in general off that grid.
  The mechanized statement should be read under that restriction, not as a claim that the
  two conventions coincide everywhere.

## Build

Requires only [elan](https://github.com/leanprover/elan) (the Lean toolchain manager).
No Mathlib, no `lake exe cache get`, no network beyond fetching the toolchain itself.

```bash
bash setup.sh            # locates/installs elan, then builds
# or, if lake is already on PATH:
lake build
```

On **this** machine, elan lives at `~/.elan/bin` (not on `PATH`) and toolchain
`leanprover/lean4:v4.33.0` (pinned in `lean-toolchain`) is already installed, so a cold
build takes about five seconds:

```bash
~/.elan/bin/lake --dir=/path/to/folding-paper/proof-lean build
```

## Sorry-free receipt

`FoldingProofs/Audit.lean` runs `#print axioms` on every headline theorem; the output is
printed during `lake build` and can be reproduced with:

```bash
lake env lean FoldingProofs/Audit.lean
```

Output (2026-08-20, Lean 4.33.0) — **no `sorryAx`**, and no `Lean.ofReduceBool` /
`Lean.trustCompiler` (i.e. no `native_decide`), only the three standard axioms:

```
'FoldingProofs.meet_sound' does not depend on any axioms
'FoldingProofs.meet_no_regression' does not depend on any axioms
'FoldingProofs.interval_meet_sound' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.invalid_fold_drops_reachable' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.Itv.gamma_meet' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.Affine.image_eq_range' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.Affine.hull_exact' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.Affine.hull_over' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.Affine.hull_under' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.Affine.self_witnessing' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.ZigZag.unzig_zigzag' depends on axioms: [propext, Quot.sound]
'FoldingProofs.ZigZag.zigzag_inj' depends on axioms: [propext, Quot.sound]
'FoldingProofs.ZigZag.image_eq_range' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.ZigZag.hull_exact' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.ZigZag.self_witnessing' depends on axioms: [propext, Classical.choice, Quot.sound]
'FoldingProofs.Inexact.hull_strict' depends on axioms: [propext, Quot.sound]
'FoldingProofs.Inexact.no_preimage' does not depend on any axioms
'FoldingProofs.Inexact.inexact_not_exact' depends on axioms: [propext, Quot.sound]
```

(`propext`, `Classical.choice`, `Quot.sound` are Lean's three standard axioms, consistent
with ZFC + inaccessibles; they enter through `omega`/`decide` and `simp`. `sorryAx` would
appear here if any proof were incomplete.)

## Layout

```
lean-toolchain            leanprover/lean4:v4.33.0
lakefile.toml             one library, zero dependencies
setup.sh                  cold-machine build script
FoldingProofs.lean        root module (imports everything)
FoldingProofs/Basic.lean      state sets as predicates; interval domain + γ
FoldingProofs/Meet.lean       Thm 1 core, Thm 1′, Thm 2a pointwise
FoldingProofs/Affine.lean     Thm 2c affine (∀ c₀, s>0, m) + Cor 2c′
FoldingProofs/ZigZag.lean     Thm 2c zigzag (∀ k) + Cor 2c′
FoldingProofs/Inexact.lean    Thm 3, the {0,4,6} counterexample
FoldingProofs/Examples.lean   anti-vacuity spot checks
FoldingProofs/Audit.lean      #print axioms for all headline theorems
```
