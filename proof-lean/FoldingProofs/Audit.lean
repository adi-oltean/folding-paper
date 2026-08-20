import FoldingProofs.Meet
import FoldingProofs.Affine
import FoldingProofs.ZigZag
import FoldingProofs.Inexact

/-!
# Axiom audit

`#print axioms` for every headline theorem.  A `sorry` anywhere in a proof shows
up here as `sorryAx`; its absence in this output is the sorry-free receipt.
The output appears in the `lake build` log (and can be reproduced on demand with
`lake env lean FoldingProofs/Audit.lean`).
-/

-- Theorem 1 (meet-soundness core) and Theorem 1′
#print axioms FoldingProofs.meet_sound
#print axioms FoldingProofs.meet_no_regression
#print axioms FoldingProofs.interval_meet_sound
#print axioms FoldingProofs.invalid_fold_drops_reachable
#print axioms FoldingProofs.Itv.gamma_meet

-- Theorem 2c, affine case (parametric in c₀, s > 0, m)
#print axioms FoldingProofs.Affine.image_eq_range
#print axioms FoldingProofs.Affine.hull_exact
#print axioms FoldingProofs.Affine.hull_over
#print axioms FoldingProofs.Affine.hull_under
#print axioms FoldingProofs.Affine.self_witnessing

-- Theorem 2c, ZigZag case (parametric in k)
#print axioms FoldingProofs.ZigZag.unzig_zigzag
#print axioms FoldingProofs.ZigZag.zigzag_inj
#print axioms FoldingProofs.ZigZag.image_eq_range
#print axioms FoldingProofs.ZigZag.hull_exact
#print axioms FoldingProofs.ZigZag.self_witnessing

-- Theorem 3 (inexact folds are may-only)
#print axioms FoldingProofs.Inexact.hull_strict
#print axioms FoldingProofs.Inexact.no_preimage
#print axioms FoldingProofs.Inexact.inexact_not_exact
