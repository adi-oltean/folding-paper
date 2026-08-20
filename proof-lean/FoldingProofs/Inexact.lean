import FoldingProofs.Basic

/-!
# Theorem 3: inexact (non-bijective) folds are may-ONLY — exactness is NOT general

`research/precision-proofs.md`, Theorem 3:

> **Proof by counterexample.**  Offsets `{0,4,6}`; gcd of the set-with-stride is
> `2`; `g` divides by `2` giving `{0,2,3}` — *still non-convex*.  Its interval
> hull is `[0,3]∩ℤ = {0,1,2,3}`, which contains `1 ∉ {0,2,3}`.  So
> `1 ∈ γ(a_g) ∖ R_g`: a dead-band element the abstraction admits but the program
> never reaches.  An "alarm" at the folded value `1` has no `g⁻¹` preimage in
> `R` — it would be a *false* witness.

This is the negative side: it bounds the witness claim of Corollary 2c′ to
bijective folds.  Everything here is a closed concrete statement, discharged by
`decide` (kernel evaluation), so it is a *counterexample receipt*, not an
assertion.
-/

namespace FoldingProofs.Inexact

open FoldingProofs

/-- The offending offset set `{0, 4, 6}` — unequally spaced. -/
def offsets : List Int := [0, 4, 6]

/-- The fold's stride: the gcd of the offsets. -/
def stride : Int := 2

/-- `stride` really is the gcd of the offset set. -/
theorem stride_is_gcd : Int.gcd (Int.gcd 0 4) 6 = 2 := by decide

/-- The reachable set in the folded coordinate, `R_g = g(R) = {0, 2, 3}`. -/
def folded : List Int := offsets.map (fun o => o / stride)

theorem folded_val : folded = [0, 2, 3] := by decide

/-- The interval hull of the folded set: `[0, 3]`. -/
def hull : Itv := ⟨0, 3⟩

/-- The hull really is the hull: it is the tightest interval containing `R_g`
(both endpoints are attained). -/
theorem hull_tight :
    (∀ x ∈ folded, hull.gamma x) ∧ hull.lo ∈ folded ∧ hull.hi ∈ folded := by decide

/-- Over-approximation still holds (Side A is unaffected): `R_g ⊆ γ(a_g)`. -/
theorem hull_over : ∀ x ∈ folded, hull.gamma x := by decide

/-- **Theorem 3 (inexact folds break the under-approximation).**
`γ(a_g) ⊋ R_g`: the value `1` is admitted by the interval hull but is not in the
reachable folded set.  Hence `a_g` is sound may-side but NOT under-approximate. -/
theorem hull_strict : hull.gamma 1 ∧ (1 : Int) ∉ folded := by decide

/-- **The false-witness half of Theorem 3.**  The dead-band value `1` has no
preimage in the concrete offset set: no reachable offset folds to `1`.  So
inverting the fold at `1` would produce a *false* witness — Corollary 2c′ does
not apply to inexact folds. -/
theorem no_preimage : ∀ o ∈ offsets, o / stride ≠ 1 := by decide

/-- The naive inverse `g⁻¹(1) = stride * 1 = 2` is not an offset. -/
theorem naive_preimage_unreachable : stride * 1 ∉ offsets := by decide

/-- Packaged statement of Theorem 3: strict over-approximation, witnessed. -/
theorem inexact_not_exact :
    (∀ x ∈ folded, hull.gamma x) ∧ (∃ y : Int, hull.gamma y ∧ y ∉ folded) :=
  ⟨hull_over, ⟨1, hull_strict.1, hull_strict.2⟩⟩

end FoldingProofs.Inexact
