"""witness.py -- E2: exact folds are self-witnessing.

Claim under test (`research/folding-witnesses-and-learning.md`, "Why folding is
unusually well-suited to the witness side"): for a BIJECTIVE fold, over- and
under-approximation coincide on the folded variable -- the folded interval is
simultaneously an over- AND an under-approximation, because E0 already measured zero
dead-band-fraction discrepancy for these three patterns (`eval/RESULTS.txt` TABLE 2).
Consequence: an alarm on an exactly-folded variable is decidable, and the fold's
INVERSE is a witness generator -- no separate symbolic-execution engine.

Three E0 catalogue patterns are exact folds (examples.py's own docstring on each):
  pattern  1  affine induction variable   i = s*j + c0            (EX1 / EX1.mutant)
  pattern 13  ZigZag bijective transport  z = 2x  (x >= 0 half)   (EX13 / EX13.mutant)
  pattern 16  lockstep elimination        p = s*i + base          (EX16 / EX16.mutant)

For each, on the MUTANT (the E0-supplied unsafe variant -- same fact, broken check):
  1. analyze(mutant, fact) -> the exact folded interval at the check; read off the
     folded coordinate's failing value.
  2. invert the fold's closed form to a concrete input.
  3. RUN refanalyzer.Concrete -- the exhaustive concrete interpreter -- and CONFIRM the
     recovered input is reachable and actually fails the check (an executable witness,
     checked, not asserted).
  4. CONTRAST: on the SAME mutant, the baseline (no-fact) analysis also alarms (FAIL) --
     over-approximate alarms are trivial on these mutants, per the design note. Apply the
     identical inversion recipe to the BASELINE's (wider, non-exact) interval and show it
     does not yield a witness: either the "recovered" candidate falls outside the
     program's own input domain, or it is not among the states the concrete interpreter
     actually reaches. The alarm is real; the witness is not, absent the fold.

refanalyzer.py is imported UNCHANGED. No new fact kind, no new IR opcode.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from refanalyzer import Builder, Concrete, analyze, check_pc, verdict  # noqa: E402
from examples import EX1, EX13, EX16, _p1_actual_max  # noqa: E402

OUT = []
FAILURES = []


def p(s=''):
    OUT.append(s)


def rule(w=88):
    return '-' * w


# =======================================================================================
# Case 1 -- pattern 1, affine induction variable.  Fold: i = s*j + c0 (here c0 = 0).
# The checked variable is t = i + 1 (an exact, non-folded successor of i); the fact is
# injected on i itself, so "the folded coordinate's failing value" is read off i, not t.
# =======================================================================================
def case_affine():
    ex = EX1
    s, c0 = 2, 0                       # from examples.py's _p1(name, s, N, bound) call: s=2
    mut = ex.mutant
    pc = check_pc(mut)                 # check_bound(t, bound) at 'chk'

    with_fold = analyze(mut, ex.facts)
    st = with_fold.entry[pc]
    i_lo, i_hi = st.v['i'][:2]
    i_fail = i_hi                      # the folded coordinate's failing value
    t_fail = st.v['t'][:2][1]

    # step 2: invert i = s*j + c0  =>  j = (i_fail - c0) / s   (the loop's trip index)
    assert (i_fail - c0) % s == 0, 'affine inversion: i_fail not on the s-grid'
    j = (i_fail - c0) // s

    # step 3: run refanalyzer's concrete interpreter and confirm
    con = Concrete(mut)
    i_idx, t_idx = mut.vars.index('i'), mut.vars.index('t')
    reached_at_chk = con.reach.get(pc, ())
    matched = [v for v in reached_at_chk if v[i_idx] == i_fail]
    confirmed_reachable = len(matched) > 0
    confirmed_violates = any((pc, v) in con.violations for v in matched)

    # exactness (E0 TABLE 2's zero-dead-band finding): the WITH-FACT interval's hull
    # equals the TRUE reachable hull of i at this point, enumerated by Concrete -- not
    # "lo==hi" (the fact tracks the whole loop's reachable range, one value per
    # iteration, not a single point).
    true_i_vals = [v[i_idx] for v in reached_at_chk]
    true_hull = (min(true_i_vals), max(true_i_vals))
    exact = (i_lo, i_hi) == true_hull

    # step 4: contrast -- baseline (no fact), same inversion recipe, on the same mutant
    base = analyze(mut)
    bst = base.entry[pc]
    bi_lo, bi_hi = bst.v['i'][:2]
    base_verdict = verdict(mut, base, pc)
    # the mutant's loop guard is `i < N` with N a program constant appearing as a
    # threshold, so even the BASELINE narrows i somewhat; the honest "no witness" point
    # is that the baseline interval is NOT exact (it may hold points -- e.g. odd i, for
    # a stride-2 program -- that the loop never actually reaches: dead band).  Report
    # both: whether the interval matches the true hull, and whether the SAME
    # concrete-lookup step confirms a reachable violation at the *baseline*-derived
    # candidate with no privileged knowledge of the fold's formula.
    base_exact = (bi_lo, bi_hi) == true_hull
    base_i_fail = bi_hi
    base_matched = [v for v in reached_at_chk if v[i_idx] == base_i_fail]
    base_confirmed = len(base_matched) > 0 and \
        any((pc, v) in con.violations for v in base_matched)

    return {
        'name': 'pattern 1 -- affine IV', 'mut_note': ex.mut_note,
        'fold_var': 'i', 'checked_var': 't',
        'folded_failing_value': i_fail, 'fold_exact': exact,
        'inverted_input': 'j=%d (trip index), i=s*j+c0=%d' % (j, i_fail),
        'checked_value_at_failure': t_fail,
        'concrete_reachable': confirmed_reachable, 'concrete_violates': confirmed_violates,
        'contrast_verdict': base_verdict,
        'contrast_interval': (bi_lo, bi_hi), 'contrast_exact': base_exact,
        'contrast_witness': base_confirmed,
    }


# =======================================================================================
# Case 2 -- pattern 13, ZigZag bijective transport, non-negative half.  For k-bit ZigZag
# restricted to x in [0, 2^(k-1)-1] the sign bit is always 0, so z = (x<<1) exactly:
# z is EVEN and x = z // 2 inverts it exactly.  This is the one case with a genuine free
# INPUT (`b.inp('x', ...)`), so step 3 is literal: build a fixed-input copy of the
# mutant with x replaced by the recovered constant, and run the interpreter on it.
# =======================================================================================
def _p13_fixed(name, k, bound, x_val):
    """Same shape as examples.py's _p13, with the free input `x` fixed to x_val --
    this is the "run the interpreter on the recovered input" step, literally."""
    mask = (1 << k) - 1
    b = Builder(name, 2 * k if k <= 16 else 64)
    b.const('x', x_val)                # was: b.inp('x', 0, (1 << (k - 1)) - 1)
    b.shr('s', 'x', k - 1)
    b.mul('m', 's', mask)
    b.shl('y', 'x', 1)
    b.band('y', 'y', mask)
    b.bxor('z', 'y', 'm')
    b.label('chk'); b.check_bound('z', bound)
    b.halt()
    return b.build()


def case_zigzag():
    ex = EX13
    k = 8
    mut = ex.mutant
    bound = mut.stmts[check_pc(mut)][2]           # 254, read off the built program
    pc = check_pc(mut)

    with_fold = analyze(mut, ex.facts)
    st = with_fold.entry[pc]
    z_lo, z_hi = st.v['z'][:2]
    z_fail = z_hi

    # step 2: invert z = 2x (x >= 0 half) => x = z // 2
    assert z_fail % 2 == 0, 'zigzag inversion: z_fail is not even'
    x_fail = z_fail // 2

    # step 3: build the fixed-input witness program and run the concrete interpreter
    fixed = _p13_fixed('p13-mut-witness', k, bound, x_fail)
    con = Concrete(fixed)
    fpc = check_pc(fixed)
    reached_z = con.values_at(fpc, 'z')
    confirmed_reachable = z_fail in reached_z
    confirmed_violates = len(con.violations) > 0

    # exactness: the WITH-FACT interval's hull equals the true reachable hull of z over
    # the mutant's FULL input domain (enumerated once, free-input x in [0,127]).  Note
    # (examples.py's own approximation footnote): z only takes EVEN values, so the hull
    # is exact at the boundary (what the inversion uses) even though interior odd points
    # in the hull are dead band -- boundary-exactness is what self-witnessing needs.
    con_full = Concrete(mut)
    true_z_vals = con_full.values_at(pc, 'z')
    true_hull = (min(true_z_vals), max(true_z_vals))
    exact = (z_lo, z_hi) == true_hull

    # step 4: contrast -- baseline (no fact), same inversion, same fixed-input rerun
    base = analyze(mut)
    bst = base.entry[pc]
    bz_lo, bz_hi = bst.v['z'][:2]
    base_verdict = verdict(mut, base, pc)
    base_exact = (bz_lo, bz_hi) == true_hull
    bx_fail = bz_hi // 2 if bz_hi % 2 == 0 else None
    in_domain = bx_fail is not None and 0 <= bx_fail <= (1 << (k - 1)) - 1
    base_confirmed = False
    if in_domain:
        base_fixed = _p13_fixed('p13-mut-witness-baseline', k, bound, bx_fail)
        bcon = Concrete(base_fixed)
        base_confirmed = len(bcon.violations) > 0

    return {
        'name': 'pattern 13 -- ZigZag transport', 'mut_note': ex.mut_note,
        'fold_var': 'z (= 2x)', 'checked_var': 'z',
        'folded_failing_value': z_fail, 'fold_exact': exact,
        'inverted_input': 'x=%d' % x_fail,
        'checked_value_at_failure': z_fail,
        'concrete_reachable': confirmed_reachable, 'concrete_violates': confirmed_violates,
        'contrast_verdict': base_verdict,
        'contrast_interval': (bz_lo, bz_hi), 'contrast_exact': base_exact,
        'contrast_witness': base_confirmed,
        'contrast_note': ('candidate x=%d out of the declared input domain [0,%d]'
                           % (bx_fail, (1 << (k - 1)) - 1) if bx_fail is not None and not in_domain
                           else ('z_fail=%d is odd -- no x inverts it (not even a candidate)'
                                 % bz_hi if bx_fail is None else '')),
    }


# =======================================================================================
# Case 3 -- pattern 16, lockstep elimination.  Fold: p = s*i + base (here s=1, base=0,
# so p and i are numerically identical -- the degenerate case of the substitution fold).
# Like pattern 1, the program has no free input (i, p are fully determined by the fixed
# loop bound n); the "recovered input" is which iteration the fold points to.
# =======================================================================================
def case_lockstep():
    ex = EX16
    s, base = 1, 0                     # from _p16(name, n, base, s, bound) call: base=0, s=1
    mut = ex.mutant
    pc = check_pc(mut)                 # check_bound(p, bound) at 'chk'

    with_fold = analyze(mut, ex.facts)
    st = with_fold.entry[pc]
    p_lo, p_hi = st.v['p'][:2]
    p_fail = p_hi

    # step 2: invert p = s*i + base  =>  i = (p_fail - base) / s
    assert (p_fail - base) % s == 0, 'lockstep inversion: p_fail not on the s-grid'
    i_fail = (p_fail - base) // s

    # step 3: run the concrete interpreter and confirm
    con = Concrete(mut)
    i_idx, p_idx = mut.vars.index('i'), mut.vars.index('p')
    reached_at_chk = con.reach.get(pc, ())
    matched = [v for v in reached_at_chk if v[i_idx] == i_fail and v[p_idx] == p_fail]
    confirmed_reachable = len(matched) > 0
    confirmed_violates = any((pc, v) in con.violations for v in matched)

    # exactness: WITH-FACT hull vs the true reachable hull of p at this point
    true_p_vals = [v[p_idx] for v in reached_at_chk]
    true_hull = (min(true_p_vals), max(true_p_vals))
    exact = (p_lo, p_hi) == true_hull

    # step 4: contrast
    base_res = analyze(mut)
    bst = base_res.entry[pc]
    bp_lo, bp_hi = bst.v['p'][:2]
    base_verdict = verdict(mut, base_res, pc)
    base_exact = (bp_lo, bp_hi) == true_hull
    bi_fail = (bp_hi - base) // s if (bp_hi - base) % s == 0 else None
    base_matched = []
    if bi_fail is not None:
        base_matched = [v for v in reached_at_chk if v[i_idx] == bi_fail and v[p_idx] == bp_hi]
    base_confirmed = len(base_matched) > 0 and \
        any((pc, v) in con.violations for v in base_matched)

    return {
        'name': 'pattern 16 -- lockstep elimination', 'mut_note': ex.mut_note,
        'fold_var': 'p (= i)', 'checked_var': 'p',
        'folded_failing_value': p_fail, 'fold_exact': exact,
        'inverted_input': 'i=%d' % i_fail,
        'checked_value_at_failure': p_fail,
        'concrete_reachable': confirmed_reachable, 'concrete_violates': confirmed_violates,
        'contrast_verdict': base_verdict,
        'contrast_interval': (bp_lo, bp_hi), 'contrast_exact': base_exact,
        'contrast_witness': base_confirmed,
    }


CASES = [case_affine, case_zigzag, case_lockstep]


# =======================================================================================
def main():
    p('=' * 100)
    p('E2 -- EXACT FOLDS ARE SELF-WITNESSING')
    p('reproduce with:  python3 eval/witness/witness.py   (deterministic; no clock, no randomness)')
    p('=' * 100)
    p('')

    results = []
    for fn in CASES:
        r = fn()
        results.append(r)

    p('TABLE 1  Exact-fold witnesses (the WITH-FOLD side)')
    p('')
    for r in results:
        p('  %s' % r['name'])
        p('    mutation:                %s' % r['mut_note'])
        p('    fold variable:           %s   (checked variable: %s)'
          % (r['fold_var'], r['checked_var']))
        p('    fold interval matches the TRUE reachable hull (zero dead-band, E0 TABLE 2): %s'
          % r['fold_exact'])
        p('    folded coordinate failing value:   %s' % r['folded_failing_value'])
        p('    inverted concrete input:           %s' % r['inverted_input'])
        p('    checked value at failure:          %s' % r['checked_value_at_failure'])
        p('    concrete interpreter: input reachable? %-5s  violates check? %-5s'
          % (r['concrete_reachable'], r['concrete_violates']))
        if not (r['concrete_reachable'] and r['concrete_violates']):
            FAILURES.append('%s: inversion did NOT reproduce a confirmed violation'
                            % r['name'])
        p('')

    p('TABLE 2  Contrast -- the SAME mutant, baseline (no-fact) alarm, same inversion recipe')
    p('         An over-approximate alarm alone is not a witness; only the exact fold')
    p('         makes the inversion trustworthy.  (design doc: "alarm-without-witness")')
    p('')
    hdr = ('  %-28s %-9s %-16s %-10s %-9s %s'
           % ('pattern', 'verdict', 'interval', 'exact?', 'witness?', 'note'))
    p(hdr)
    p('  ' + rule(len(hdr) - 2))
    for r in results:
        note = r.get('contrast_note', '')
        if not note and not r['contrast_witness']:
            note = 'baseline interval is not exact -- inverted candidate is spurious'
        p('  %-28s %-9s %-16s %-10s %-9s %s'
          % (r['name'][:28], r['contrast_verdict'], str(r['contrast_interval']),
             r['contrast_exact'], r['contrast_witness'], note[:40]))
        if r['contrast_verdict'] != 'FAIL':
            FAILURES.append('%s: baseline verdict is %s, expected FAIL (alarm should '
                            'still fire without the fold)' % (r['name'], r['contrast_verdict']))
        if r['contrast_exact']:
            FAILURES.append('%s: baseline interval turned out EXACT -- the contrast is '
                            'not meaningful for this case (report as a finding, not a bug)'
                            % r['name'])
        if r['contrast_witness']:
            FAILURES.append('%s: baseline-derived inversion ALSO produced a confirmed '
                            'witness -- the intended contrast did not hold; report as a '
                            'finding' % r['name'])
    p('')

    p('SUMMARY')
    p('')
    n_ok = sum(1 for r in results if r['concrete_reachable'] and r['concrete_violates'])
    p('  exact-fold witnesses confirmed by the concrete interpreter: %d/%d' % (n_ok, len(results)))
    n_contrast_ok = sum(1 for r in results
                        if r['contrast_verdict'] == 'FAIL' and not r['contrast_exact']
                        and not r['contrast_witness'])
    p('  contrast cases where the baseline alarms but yields NO witness: %d/%d'
      % (n_contrast_ok, len(results)))
    p('')

    if FAILURES:
        p('FINDINGS / FAILURES')
        p('')
        for f in FAILURES:
            p('  * ' + f)
        p('')
    else:
        p('All 3 exact-fold cases: inversion reproduced a confirmed concrete violation, and')
        p('the same inversion applied to the baseline (no-fact) alarm on the same mutant')
        p('produced no witness in every case.')
        p('')

    text = '\n'.join(OUT) + '\n'
    sys.stdout.write(text)
    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
