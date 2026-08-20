import FoldingProofs.Basic

/-!
# Theorem 2c (affine-IV case): the fold is EXACT, for all strides and all trip counts

`research/precision-proofs.md`, Theorem 2c, first bullet:

> **Affine IV.** `R = {c₀, c₀+s, …, c₀+s(m−1)}`, an arithmetic progression of `m`
> terms.  `g(R) = {0,1,…,m−1}` — the image is the *contiguous* integer range
> `[0, m−1]` … A contiguous integer range equals its own interval hull, so
> `γ(a_g) = [0,m−1]∩ℤ = g(R)`.  `g` is a bijection on `R` (step `s ≠ 0`) …
> Both inclusions hold; `a_g` is exact.

This file proves that statement **parametrically in `c₀`, `s > 0` and `m`** —
the all-width claim the enumeration checker (`eval/proof/`) could only spot-check
at representative widths, and which it explicitly left open ("z3 not importable,
all-width claims symbolic, not discharged").

Headline results:
* `Affine.image_eq_range`   — `g(R) = {0,…,m−1}`, both inclusions, all `s>0`, all `m`.
* `Affine.hull_exact`       — `γ([0, m−1]) = g(R)` exactly: no dead band.
* `Affine.self_witnessing`  — Corollary 2c′: every folded value the abstraction
  admits has a genuinely reachable concrete preimage.
-/

namespace FoldingProofs.Affine

open FoldingProofs

/-- The reachable set of an affine induction variable: `{c₀ + s·k | k < m}`,
an arithmetic progression of `m` terms. -/
def R (c₀ s : Int) (m : Nat) : SetP Int := fun i => ∃ k : Nat, k < m ∧ i = c₀ + s * (k : Int)

/-- The fold map `g(i) = (i − c₀)/s` (exact quotient on `R`). -/
def g (c₀ s : Int) (i : Int) : Int := (i - c₀) / s

/-- The inverse fold `g⁻¹(j) = c₀ + s·j`, used for witness recovery (Cor. 2c′). -/
def ginv (c₀ s : Int) (j : Int) : Int := c₀ + s * j

/-- The image of the reachable set in the folded coordinate, `R_g = g(R)`. -/
def imageR (c₀ s : Int) (m : Nat) : SetP Int := fun j => ∃ i, R c₀ s m i ∧ g c₀ s i = j

/-- The interval hull the analyzer would compute for the folded coordinate:
`[0, m−1]`. -/
def hull (m : Nat) : Itv := ⟨0, (m : Int) - 1⟩

/-- `g` inverts `g⁻¹` — exact quotient, because the progression's step is `s`. -/
theorem g_ginv (c₀ s : Int) (hs : 0 < s) (j : Int) : g c₀ s (ginv c₀ s j) = j := by
  unfold g ginv
  have h : c₀ + s * j - c₀ = s * j := by omega
  rw [h, Int.mul_ediv_cancel_left _ (by omega : s ≠ 0)]

/-- `g⁻¹` inverts `g` on the reachable set: the fold is injective on `R`. -/
theorem ginv_g (c₀ s : Int) (hs : 0 < s) (m : Nat) (i : Int) (hi : R c₀ s m i) :
    ginv c₀ s (g c₀ s i) = i := by
  unfold R at hi
  obtain ⟨k, _, rfl⟩ := hi
  have h : c₀ + s * (k : Int) - c₀ = s * (k : Int) := by omega
  unfold g ginv
  rw [h, Int.mul_ediv_cancel_left _ (by omega : s ≠ 0)]

/-- **Theorem 2c (affine), the exactness core — parametric in `c₀`, `s > 0`, `m`.**

The image of the reachable set under the fold is *exactly* the contiguous
integer range `{0, 1, …, m−1}`: both inclusions, for every stride `s > 0`,
every base `c₀`, and every trip count `m`. -/
theorem image_eq_range (c₀ s : Int) (m : Nat) (hs : 0 < s) (j : Int) :
    imageR c₀ s m j ↔ (0 ≤ j ∧ j < (m : Int)) := by
  unfold imageR R
  constructor
  · rintro ⟨i, ⟨k, hk, rfl⟩, rfl⟩
    have h : c₀ + s * (k : Int) - c₀ = s * (k : Int) := by omega
    unfold g
    rw [h, Int.mul_ediv_cancel_left _ (by omega : s ≠ 0)]
    omega
  · rintro ⟨h0, hm⟩
    have ht : ((j.toNat : Int)) = j := Int.toNat_of_nonneg h0
    refine ⟨ginv c₀ s j, ⟨j.toNat, by omega, ?_⟩, g_ginv c₀ s hs j⟩
    unfold ginv
    rw [ht]

/-- **Theorem 2c (affine), "no dead band".**  The interval hull `[0, m−1]` of the
folded coordinate concretizes to *exactly* the reachable folded set: `a_g` is
simultaneously a sound over-approximation and a sound under-approximation.
Holds for every `m`, including `m = 0` (where `[0, −1]` is empty, matching the
empty reachable set). -/
theorem hull_exact (c₀ s : Int) (m : Nat) (hs : 0 < s) (j : Int) :
    (hull m).gamma j ↔ imageR c₀ s m j := by
  rw [image_eq_range c₀ s m hs j]
  simp only [hull, Itv.gamma]
  omega

/-- Over-approximation direction of 2c (Side A: safety proofs on `a_g` are sound). -/
theorem hull_over (c₀ s : Int) (m : Nat) (hs : 0 < s) :
    imageR c₀ s m ⊆ₛ (hull m).gamma := fun j hj => (hull_exact c₀ s m hs j).mpr hj

/-- Under-approximation direction of 2c (the must side: every admitted point is
genuinely reachable). -/
theorem hull_under (c₀ s : Int) (m : Nat) (hs : 0 < s) :
    (hull m).gamma ⊆ₛ imageR c₀ s m := fun j hj => (hull_exact c₀ s m hs j).mp hj

/-- **Corollary 2c′ (self-witnessing), affine case.**  If a check fails at a
folded value `j` the abstraction admits, then `g⁻¹(j) = c₀ + s·j` is a concrete,
genuinely reachable input mapping to `j` — a witness produced by inversion. -/
theorem self_witnessing (c₀ s : Int) (m : Nat) (hs : 0 < s) (j : Int)
    (hj : (hull m).gamma j) :
    R c₀ s m (ginv c₀ s j) ∧ g c₀ s (ginv c₀ s j) = j := by
  have hmem := (hull_under c₀ s m hs) j hj
  unfold imageR at hmem
  obtain ⟨i, hi, hgi⟩ := hmem
  refine ⟨?_, g_ginv c₀ s hs j⟩
  have : ginv c₀ s j = i := by rw [← hgi]; exact ginv_g c₀ s hs m i hi
  rw [this]
  exact hi

end FoldingProofs.Affine
