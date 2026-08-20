import FoldingProofs.Basic
import FoldingProofs.Meet
import FoldingProofs.Affine
import FoldingProofs.ZigZag
import FoldingProofs.Inexact
import FoldingProofs.Examples
import FoldingProofs.Audit

/-!
# FoldingProofs — Lean 4 mechanization of the parametric core of `precision-proofs.md`

See `README.md`.  Modules:

* `FoldingProofs.Basic`   — state sets as predicates; the interval domain and its `γ`.
* `FoldingProofs.Meet`    — Theorem 1 (valid ⇒ sound), order-theoretic core; Theorem 1′.
* `FoldingProofs.Affine`  — Theorem 2c, affine-IV case, ∀ c₀, ∀ s>0, ∀ m; Cor. 2c′.
* `FoldingProofs.ZigZag`  — Theorem 2c, ZigZag case, ∀ k; Cor. 2c′.
* `FoldingProofs.Inexact` — Theorem 3, the `{0,4,6}` counterexample, by `decide`.
* `FoldingProofs.Audit`   — `#print axioms` for every headline theorem.
-/
