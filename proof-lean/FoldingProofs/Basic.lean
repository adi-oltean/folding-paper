/-!
# Basic vocabulary: concrete state sets and the interval domain

Shared definitions for the mechanization of `research/precision-proofs.md`.

Deliberately Mathlib-free: a "set of concrete states" is just a predicate
`S → Prop`, and the abstract domain is an explicit interval record with an
explicit concretization `γ`.  Nothing here needs lattice or `Set` infrastructure.
-/

namespace FoldingProofs

/-- A set of concrete states, as a predicate.  (Stands in for `℘(States)` in
the note's notation; we avoid Mathlib's `Set` to keep the project dependency-free.) -/
abbrev SetP (S : Type) := S → Prop

/-- Set inclusion for `SetP`. -/
def SubsetP {S : Type} (A B : SetP S) : Prop := ∀ s, A s → B s

@[inherit_doc] infix:50 " ⊆ₛ " => SubsetP

theorem SubsetP.refl {S : Type} (A : SetP S) : A ⊆ₛ A := fun _ h => h

theorem SubsetP.trans {S : Type} {A B C : SetP S} (h₁ : A ⊆ₛ B) (h₂ : B ⊆ₛ C) :
    A ⊆ₛ C := fun s hs => h₂ s (h₁ s hs)

/-! ## The interval domain over `Int` -/

/-- An interval abstract element `[lo, hi]` (empty when `hi < lo`). -/
structure Itv where
  lo : Int
  hi : Int
  deriving DecidableEq, Repr

/-- Concretization: the integers the interval admits.  Note `γ ⟨lo, hi⟩ = ∅`
whenever `hi < lo`, so no separate `⊥` element is needed. -/
def Itv.gamma (I : Itv) : SetP Int := fun x => I.lo ≤ x ∧ x ≤ I.hi

/-- Membership in an interval's concretization is decidable — this is what lets
the concrete counterexample of Theorem 3 be discharged by `decide`. -/
instance (I : Itv) (x : Int) : Decidable (I.gamma x) :=
  inferInstanceAs (Decidable (I.lo ≤ x ∧ x ≤ I.hi))

/-- Meet (greatest lower bound) of two intervals. -/
def Itv.meet (I J : Itv) : Itv := ⟨max I.lo J.lo, min I.hi J.hi⟩

/-- Order on intervals: `I ⊑ J` iff `I`'s concretization is contained in `J`'s.
Defined syntactically so it is decidable; `Itv.le_iff_gamma` relates the two. -/
def Itv.le (I J : Itv) : Prop := (I.hi < I.lo) ∨ (J.lo ≤ I.lo ∧ I.hi ≤ J.hi)

/-- **γ is a meet-morphism on intervals** — the concrete fact Theorem 1 rests on:
`γ (a ⊓ b) = γ a ∩ γ b`, exactly (not merely `⊆`). -/
theorem Itv.gamma_meet (I J : Itv) (x : Int) :
    (I.meet J).gamma x ↔ (I.gamma x ∧ J.gamma x) := by
  simp only [Itv.meet, Itv.gamma]
  omega

/-- Meeting can only shrink the concretization (`a ⊓ b ⊑ a`). -/
theorem Itv.gamma_meet_le_left (I J : Itv) : (I.meet J).gamma ⊆ₛ I.gamma := by
  intro x hx
  exact ((Itv.gamma_meet I J x).mp hx).1

theorem Itv.gamma_meet_le_right (I J : Itv) : (I.meet J).gamma ⊆ₛ J.gamma := by
  intro x hx
  exact ((Itv.gamma_meet I J x).mp hx).2

end FoldingProofs
