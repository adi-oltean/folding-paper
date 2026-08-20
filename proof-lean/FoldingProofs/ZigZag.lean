import FoldingProofs.Basic

/-!
# Theorem 2c (ZigZag case): the fold is a bijection onto a contiguous range, for ALL k

`research/precision-proofs.md`, Theorem 2c, second bullet:

> **ZigZag.** `g` is the standard bijection `ℤ∩[−2^k, 2^k) → [0, 2^{k+1}) ∩ ℤ`
> with well-defined inverse (`y even ↦ y/2`, `y odd ↦ −(y+1)/2`).  For input
> range `[−2^k, 2^k)` the image is the *entire* contiguous range `[0, 2^{k+1})`;
> interval hull equals the set; bijection gives both inclusions.  Exact.

Everything below is **parametric in `k : Nat`** — the ∀k claim that enumeration
could only check at representative widths.

Headline results:
* `ZigZag.unzig_zigzag`  — left inverse, for *every* integer (no domain hypothesis needed).
* `ZigZag.zigzag_unzig`  — right inverse on `y ≥ 0`.
* `ZigZag.image_eq_range` — the image of `[−2^k, 2^k)` is exactly `[0, 2^{k+1})`, ∀k.
* `ZigZag.hull_exact`     — the interval hull equals the reachable folded set: no dead band.
* `ZigZag.self_witnessing` — Corollary 2c′ for zigzag.
-/

namespace FoldingProofs.ZigZag

open FoldingProofs

/-- The ZigZag fold: `x ↦ 2x` for `x ≥ 0`, `x ↦ −2x − 1` for `x < 0`. -/
def zigzag (x : Int) : Int := if 0 ≤ x then 2 * x else -2 * x - 1

/-- Its inverse: `y even ↦ y/2`, `y odd ↦ −(y+1)/2`. -/
def unzig (y : Int) : Int := if y % 2 = 0 then y / 2 else -((y + 1) / 2)

/-- The concrete domain at width `k`: the signed range `[−2^k, 2^k)`. -/
def domain (k : Nat) : SetP Int := fun x => -(2 ^ k) ≤ x ∧ x < 2 ^ k

/-- The image of the domain under the fold, `R_g = zigzag(domain)`. -/
def imageR (k : Nat) : SetP Int := fun y => ∃ x, domain k x ∧ zigzag x = y

/-- The interval hull the analyzer computes for the folded coordinate:
`[0, 2^{k+1} − 1]`. -/
def hull (k : Nat) : Itv := ⟨0, 2 ^ (k + 1) - 1⟩

theorem two_pow_pos (k : Nat) : (0 : Int) < 2 ^ k := by
  induction k with
  | zero => decide
  | succ n ih => rw [Int.pow_succ]; omega

theorem two_pow_succ (k : Nat) : (2 : Int) ^ (k + 1) = 2 * 2 ^ k := by
  rw [Int.pow_succ]; omega

/-- **`unzig` is a left inverse of `zigzag` on all of `ℤ`** — hence `zigzag` is
injective (`zigzag_inj` below). -/
theorem unzig_zigzag (x : Int) : unzig (zigzag x) = x := by
  unfold unzig zigzag
  split <;> split <;> omega

/-- `zigzag` is injective. -/
theorem zigzag_inj (x y : Int) (h : zigzag x = zigzag y) : x = y := by
  have hx : unzig (zigzag x) = x := unzig_zigzag x
  have hy : unzig (zigzag y) = y := unzig_zigzag y
  rw [h] at hx
  exact hx.symm.trans hy

/-- **`zigzag` is a right inverse of `unzig` on the nonnegative integers.** -/
theorem zigzag_unzig (y : Int) (hy : 0 ≤ y) : zigzag (unzig y) = y := by
  unfold unzig zigzag
  split <;> split <;> omega

/-- `zigzag` maps the domain into the nonnegative range (the easy inclusion). -/
theorem zigzag_mem (k : Nat) (x : Int) (hx : domain k x) :
    0 ≤ zigzag x ∧ zigzag x < 2 ^ (k + 1) := by
  unfold domain at hx
  obtain ⟨hlo, hhi⟩ := hx
  have hs := two_pow_succ k
  unfold zigzag
  split <;> omega

/-- `unzig` maps the range back into the domain (the surjectivity inclusion). -/
theorem unzig_mem (k : Nat) (y : Int) (h0 : 0 ≤ y) (h1 : y < 2 ^ (k + 1)) :
    domain k (unzig y) := by
  have hs := two_pow_succ k
  have hp := two_pow_pos k
  unfold domain unzig
  split <;> omega

/-- **Theorem 2c (ZigZag), the exactness core — parametric in `k`.**

The image of `[−2^k, 2^k)` under the ZigZag fold is *exactly* the contiguous
range `[0, 2^{k+1})`: both inclusions, for every `k`. -/
theorem image_eq_range (k : Nat) (y : Int) :
    imageR k y ↔ (0 ≤ y ∧ y < 2 ^ (k + 1)) := by
  unfold imageR
  constructor
  · rintro ⟨x, hx, rfl⟩
    exact zigzag_mem k x hx
  · rintro ⟨h0, h1⟩
    exact ⟨unzig y, unzig_mem k y h0 h1, zigzag_unzig y h0⟩

/-- **Theorem 2c (ZigZag), "no dead band".**  The interval hull `[0, 2^{k+1}−1]`
concretizes to *exactly* the reachable folded set — over- and
under-approximation at once, for every `k`. -/
theorem hull_exact (k : Nat) (y : Int) : (hull k).gamma y ↔ imageR k y := by
  rw [image_eq_range k y]
  simp only [hull, Itv.gamma]
  omega

theorem hull_over (k : Nat) : imageR k ⊆ₛ (hull k).gamma :=
  fun y hy => (hull_exact k y).mpr hy

theorem hull_under (k : Nat) : (hull k).gamma ⊆ₛ imageR k :=
  fun y hy => (hull_exact k y).mp hy

/-- **Corollary 2c′ (self-witnessing), ZigZag case.**  Every folded value the
abstraction admits has a concrete, genuinely reachable preimage, recovered by
inversion: `unzig y ∈ [−2^k, 2^k)` and `zigzag (unzig y) = y`. -/
theorem self_witnessing (k : Nat) (y : Int) (hy : (hull k).gamma y) :
    domain k (unzig y) ∧ zigzag (unzig y) = y := by
  simp only [hull, Itv.gamma] at hy
  obtain ⟨h0, h1⟩ := hy
  exact ⟨unzig_mem k y h0 (by omega), zigzag_unzig y h0⟩

end FoldingProofs.ZigZag
