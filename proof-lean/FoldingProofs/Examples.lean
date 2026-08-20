import FoldingProofs.Affine
import FoldingProofs.ZigZag
import FoldingProofs.Inexact

/-!
# Anti-vacuity spot checks

The parametric theorems would still typecheck if a definition had a typo that
made the statements vacuous (e.g. an empty reachable set).  These closed
instances pin the definitions to the concrete behaviour the enumeration seat
(`eval/proof/`) checks, all by `decide` or by instantiating the theorems.
-/

namespace FoldingProofs.Examples

open FoldingProofs

/-! ## Affine: `c₀ = 5`, `s = 3`, `m = 4` — `R = {5, 8, 11, 14}`, `g(R) = {0,1,2,3}` -/

example : Affine.R 5 3 4 11 := ⟨2, by decide, by decide⟩
example : Affine.g 5 3 11 = 2 := by decide
example : Affine.ginv 5 3 2 = 11 := by decide

/-- `2` is in the folded image, via the parametric theorem. -/
example : Affine.imageR 5 3 4 2 :=
  (Affine.image_eq_range 5 3 4 (by decide) 2).mpr (by decide)

/-- `4` is *not* in the folded image (the hull `[0,3]` stops there). -/
example : ¬ Affine.imageR 5 3 4 4 := by
  intro h
  have := (Affine.image_eq_range 5 3 4 (by decide) 4).mp h
  omega

/-- Self-witnessing, concretely: the hull value `3` recovers the reachable input `14`. -/
example : Affine.R 5 3 4 (Affine.ginv 5 3 3) ∧ Affine.g 5 3 (Affine.ginv 5 3 3) = 3 :=
  Affine.self_witnessing 5 3 4 (by decide) 3 (by decide)

/-! ## ZigZag: `k = 2` — domain `[-4, 4)`, image `[0, 8)` -/

example : ZigZag.zigzag 0 = 0 := by decide
example : ZigZag.zigzag (-1) = 1 := by decide
example : ZigZag.zigzag 1 = 2 := by decide
example : ZigZag.zigzag (-4) = 7 := by decide
example : ZigZag.zigzag 3 = 6 := by decide
example : ZigZag.unzig 5 = -3 := by decide
example : ZigZag.unzig 6 = 3 := by decide

/-- `7` (the top of the folded range at `k = 2`) is reachable. -/
example : ZigZag.imageR 2 7 := (ZigZag.image_eq_range 2 7).mpr (by decide)

/-- `8` is not: the image is exactly `[0, 2^3)`. -/
example : ¬ ZigZag.imageR 2 8 := by
  intro h
  have := (ZigZag.image_eq_range 2 8).mp h
  omega

/-! ## Inexact `{0,4,6}`: the dead band is real -/

example : Inexact.folded = [0, 2, 3] := by decide
example : (1 : Int) ∈ [(0 : Int), 1, 2, 3] := by decide      -- 1 is in the hull's enumeration
example : (1 : Int) ∉ Inexact.folded := by decide

end FoldingProofs.Examples
