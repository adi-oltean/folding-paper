#!/usr/bin/env python3
"""Exhaustive check of Pattern 1's closed form across all three declared comparators.

The paper declares pattern 1 for `for (i = c0; i BOWTIE L; i += s)` with
BOWTIE in {<, <=, !=}, and states (v16, after the deep-review fix to F3):

  (F1) for `<` :  actual_max = c0 + s*ceil((L - c0)/s) - s
  (F2) for `<=`:  the same expression with L replaced by L+1
  (F3) for `!=`:  exact only when s | (L - c0) AND c0 <= L, and then
                  actual_max = L - s; otherwise the pattern declines the match.
                  Divisibility alone is NOT sufficient: `i=7; i!=5; i+=2` divides
                  evenly (2 | -2) but never reaches 5, so a formula that checked
                  only divisibility would license the unsound fact i<=3 on a loop
                  whose reachable values are 7, 9, 11, ... -- this was caught by
                  an adversarial review of the paper text, after this script's
                  own `limit < c0` guard had already (silently) declined the case
                  without the paper's prose saying why.

  (S1) supplying i <= actual_max is strictly stronger than the header condition
       for `<`  when s > 1 and (L - c0)   !≡ 1 (mod s);
       for `<=` when s > 1 and (L+1 - c0) !≡ 1 (mod s);
       for `!=` unconditionally, the guard having supplied no bound at all.

Every one of those is checked here against a ground-truth simulation of the loop,
over a dense parameter sweep.

Exit 0 iff every obligation holds. Run: python3 eval/proof/check_pattern1.py
"""
from __future__ import annotations

import sys

# Sweep bounds. Small and dense beats large and sparse: every interesting case
# (empty body, single iteration, limit hit exactly, limit overshot) occurs many
# times over inside these ranges.
C0_RANGE = range(-6, 11)
L_RANGE = range(-6, 31)
S_RANGE = range(1, 8)
MAX_ITERS = 10_000          # a `!=` loop that never hits L must not hang the check


def ceil_div(a: int, b: int) -> int:
    """Ceiling of a/b for b > 0, without floats (the paper's ceil is exact)."""
    return -((-a) // b)


def simulate(c0: int, limit: int, s: int, op: str) -> tuple[list[int], bool]:
    """Ground truth: the values i takes on entry to the body.

    Returns (values, terminated). `terminated` is False for a `!=` loop that
    steps past its limit without ever equalling it -- the case the paper says
    the pattern must decline.
    """
    vals: list[int] = []
    i = c0
    for _ in range(MAX_ITERS):
        if op == "<" and not (i < limit):
            return vals, True
        if op == "<=" and not (i <= limit):
            return vals, True
        if op == "!=" and not (i != limit):
            return vals, True
        vals.append(i)
        i += s
    return vals, False


def formula(c0: int, limit: int, s: int, op: str) -> int | None:
    """The paper's closed form; None where the paper declines the match."""
    if op == "<":
        return c0 + s * ceil_div(limit - c0, s) - s
    if op == "<=":
        return c0 + s * ceil_div(limit + 1 - c0, s) - s
    if op == "!=":
        if (limit - c0) % s != 0 or limit < c0:
            return None            # declines: loop never lands on the limit
        return limit - s
    raise AssertionError(op)


def header_bound(limit: int, op: str) -> int | None:
    """The strongest upper bound the loop guard alone gives an interval domain.

    For `!=` this is None: "cannot subtract a point from its interior" -- the
    guard bounds nothing, which is pattern 2's opening observation.
    """
    return {"<": limit - 1, "<=": limit}.get(op)


def predicted_strictly_stronger(c0: int, limit: int, s: int, op: str) -> bool:
    if op == "!=":
        return True
    lim = limit if op == "<" else limit + 1
    return s > 1 and (lim - c0) % s != 1


def main() -> int:
    checked = {"<": 0, "<=": 0, "!=": 0}
    declined = 0
    vacuous = 0
    failures: list[str] = []

    for op in ("<", "<=", "!="):
        for s in S_RANGE:
            for c0 in C0_RANGE:
                for limit in L_RANGE:
                    vals, terminated = simulate(c0, limit, s, op)
                    f = formula(c0, limit, s, op)

                    if f is None:
                        declined += 1
                        # The decline must be necessary: a declined `!=` loop is
                        # exactly one that never terminates at the limit.
                        if terminated and vals:
                            failures.append(
                                f"declined but terminated: {op} c0={c0} L={limit} s={s}"
                            )
                        continue

                    if not terminated:
                        failures.append(
                            f"non-terminating but not declined: {op} c0={c0} L={limit} s={s}"
                        )
                        continue

                    if not vals:
                        # Body never entered; the paper scopes the claim to
                        # loops whose body executes at least once.
                        vacuous += 1
                        continue

                    checked[op] += 1
                    truth = max(vals)

                    # (F1)/(F2)/(F3): the closed form is the last body-entry value.
                    if f != truth:
                        failures.append(
                            f"formula {op} c0={c0} L={limit} s={s}: "
                            f"closed form {f} != actual {truth}"
                        )
                        continue

                    # The fact must be sound: it bounds every body-entry value.
                    if any(v > f for v in vals):
                        failures.append(
                            f"UNSOUND {op} c0={c0} L={limit} s={s}: "
                            f"i <= {f} excludes a reachable {max(vals)}"
                        )

                    # (S1): strictness matches the stated condition exactly.
                    hb = header_bound(limit, op)
                    actually_stronger = True if hb is None else f < hb
                    if actually_stronger != predicted_strictly_stronger(c0, limit, s, op):
                        failures.append(
                            f"strictness {op} c0={c0} L={limit} s={s}: "
                            f"actual_max={f} header={hb} "
                            f"stronger={actually_stronger} predicted="
                            f"{predicted_strictly_stronger(c0, limit, s, op)}"
                        )

    total = sum(checked.values())
    print("=" * 78)
    print("Pattern 1 closed form, all three declared comparators")
    print("=" * 78)
    print(f"  parameter sweep      : c0 in [{C0_RANGE.start},{C0_RANGE.stop - 1}], "
          f"L in [{L_RANGE.start},{L_RANGE.stop - 1}], s in [{S_RANGE.start},{S_RANGE.stop - 1}]")
    print(f"  non-vacuous cases    : {total}"
          f"   ( <  {checked['<']} | <= {checked['<=']} | != {checked['!=']} )")
    print(f"  vacuous (body empty) : {vacuous}")
    print(f"  declined by (F3)     : {declined}")
    print()

    if failures:
        print(f"FAIL: {len(failures)} obligation(s) violated. First 20:")
        for f in failures[:20]:
            print(f"   {f}")
        return 1

    print("  [ok] closed form equals the last body-entry value in every case")
    print("  [ok] the supplied fact bounds every body-entry value (no unsoundness)")
    print("  [ok] strictness holds exactly where the paper says it does")
    print("  [ok] every declined `!=` case provably never lands on its limit")
    print()
    print("RESULT: Pattern 1 verified for <, <= and != .")
    return 0


if __name__ == "__main__":
    sys.exit(main())
