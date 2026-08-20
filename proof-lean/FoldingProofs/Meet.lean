import FoldingProofs.Basic

/-!
# Theorem 1 (valid ⇒ sound), mechanized as its order-theoretic core

`research/precision-proofs.md`, Theorem 1:

> At `p`, `R(p) ⊆ γ(Â(p))` (baseline soundness) and `R(p) ⊆ γ(a_F)` (validity),
> so `R(p) ⊆ γ(Â(p)) ∩ γ(a_F)`.  Because `γ` is a complete meet-morphism,
> `γ(Â(p)) ∩ γ(a_F) = γ(Â(p) ⊓ a_F)`.  Hence meeting with `a_F` removes **no**
> reachable state at `p`.

What is mechanized here is exactly that step — the *meet-soundness core*: in any
abstract domain whose concretization is a meet-morphism, injecting a valid fact
preserves the over-approximation.  The fixpoint-propagation half of Theorem 1
("soundness propagates to every `q` by the standard fixpoint-soundness argument")
is deliberately **out of scope**: it is the standard monotone-transformer
argument and would require formalizing an analyzer with widening.

Also mechanized: Theorem 1′ (the gate is load-bearing) by exhibition, and the
pointwise half of Theorem 2a (meeting never loses precision at `p`).
-/

namespace FoldingProofs

/-- An abstract domain presented by exactly what Theorem 1 uses: a meet and a
concretization that is a meet-morphism.  (This is what a Galois connection buys
you; we take it as the interface rather than deriving it, so no lattice library
is needed.  `Itv` below is a concrete witness that the interface is inhabited.) -/
structure MeetDomain (A S : Type) where
  meet : A → A → A
  gamma : A → SetP S
  /-- `γ` is a (finite) meet-morphism: `γ (a ⊓ b) = γ a ∩ γ b`. -/
  gamma_meet : ∀ a b s, gamma (meet a b) s ↔ (gamma a s ∧ gamma b s)

/-- **Theorem 1 core (valid ⇒ sound).**  If the baseline over-approximates the
reachable set (`R ⊆ γ a`) and the injected fold fact is *valid* (`R ⊆ γ b`),
then the folded element still over-approximates: `R ⊆ γ (a ⊓ b)`.
Meeting with a valid fact removes no reachable state. -/
theorem meet_sound {A S : Type} (D : MeetDomain A S) (R : SetP S) (a b : A)
    (hbase : R ⊆ₛ D.gamma a) (hvalid : R ⊆ₛ D.gamma b) :
    R ⊆ₛ D.gamma (D.meet a b) := by
  intro s hs
  exact (D.gamma_meet a b s).mpr ⟨hbase s hs, hvalid s hs⟩

/-- **Theorem 2a, pointwise half (no regression).**  The folded element is below
the baseline: every concrete state it admits was already admitted.  (The
fixpoint/lfp statement of 2a, and the widening caveat, are out of scope here.) -/
theorem meet_no_regression {A S : Type} (D : MeetDomain A S) (a b : A) :
    D.gamma (D.meet a b) ⊆ₛ D.gamma a := by
  intro s hs
  exact ((D.gamma_meet a b s).mp hs).1

/-- The two-sided form: with a valid fold, the reachable set is sandwiched —
sound *and* no worse than baseline. -/
theorem meet_sound_and_tighter {A S : Type} (D : MeetDomain A S) (R : SetP S) (a b : A)
    (hbase : R ⊆ₛ D.gamma a) (hvalid : R ⊆ₛ D.gamma b) :
    R ⊆ₛ D.gamma (D.meet a b) ∧ D.gamma (D.meet a b) ⊆ₛ D.gamma a :=
  ⟨meet_sound D R a b hbase hvalid, meet_no_regression D a b⟩

/-- The interval domain over `Int` is such a domain (witness that `MeetDomain`
is not vacuous, and the instance the folding patterns actually use). -/
def intervalDomain : MeetDomain Itv Int :=
  { meet := Itv.meet, gamma := Itv.gamma, gamma_meet := Itv.gamma_meet }

/-- Theorem 1 core, specialized to intervals. -/
theorem interval_meet_sound (R : SetP Int) (baseline fold : Itv)
    (hbase : R ⊆ₛ baseline.gamma) (hvalid : R ⊆ₛ fold.gamma) :
    R ⊆ₛ (baseline.meet fold).gamma :=
  meet_sound intervalDomain R baseline fold hbase hvalid

/-- **Theorem 1′ (invalid ⇒ possibly unsound; the admission gate is
load-bearing), by exhibition.**  An *invalid* fold — one whose `γ` misses a
reachable state — makes the meet drop that state, destroying soundness.
Witness: `R = {0}`, baseline `[0,0]` (sound), fold fact `[1,1]` (invalid at
`0`); the meet is empty, so the reachable state `0` is gone. -/
theorem invalid_fold_drops_reachable :
    ∃ (R : SetP Int) (baseline fold : Itv) (s : Int),
      R s ∧ R ⊆ₛ baseline.gamma ∧ ¬ fold.gamma s ∧ ¬ (baseline.meet fold).gamma s := by
  refine ⟨(fun x => x = 0), ⟨0, 0⟩, ⟨1, 1⟩, 0, rfl, ?_, ?_, ?_⟩
  · intro x hx
    simp only [Itv.gamma]
    omega
  · simp only [Itv.gamma]
    omega
  · simp only [Itv.gamma, Itv.meet]
    omega

end FoldingProofs
