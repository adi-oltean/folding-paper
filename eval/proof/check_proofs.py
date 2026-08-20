"""check_proofs.py -- the CHECKER seat for research/precision-proofs.md.

Discharges [CHECK-1]..[CHECK-4] from that note as machine assertions, one run, printing
PROVEN/FAILED per obligation.  A FAILED obligation is reported with its counterexample --
it is the most important thing this script can find, and nothing here is allowed to soften
a failing result to make the table look better.

Imports refanalyzer.py and examples.py UNCHANGED (leg B's analyzer + concrete interpreter,
and the canonical catalogue).  Also imports run.py's measure_dbf (CHECK-2: "cross-check
against run.py output, don't recompute differently") and witness.py's case_affine /
case_zigzag / case_lockstep (CHECK-3's corollary 2c': "if eval/witness already does this,
cite it and do a minimal confirmation rather than duplicating").  Neither is modified;
neither's __main__ block runs on import.

    python3 eval/proof/check_proofs.py           print the report
    python3 eval/proof/check_proofs.py --check    ... and exit nonzero if anything FAILED

Deterministic: no wall-clock, no RNG. Every number below is either enumerated by
refanalyzer.Concrete or computed by closed-form/finite set arithmetic mirroring the memo's
own proofs.
"""

import math
import os
import sys
import textwrap
from fractions import Fraction

EVAL_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, EVAL_DIR)
sys.path.insert(0, os.path.join(EVAL_DIR, 'witness'))

from refanalyzer import Builder, Concrete, analyze, check_pc, dbf, soundness, verdict  # noqa: E402
from examples import (EXAMPLES, PROBES, SWEEPS, EX1, EX13, EX16,  # noqa: E402
                      _p1, _p13, _p16)
import run as run_mod          # noqa: E402  (CHECK-2 cross-check: run.measure_dbf, unmodified)
import witness as witness_mod  # noqa: E402  (CHECK-3 corollary 2c' cases, unmodified)

OUT = []
RESULTS = []   # list of (check_id, status, one_line, detail_lines)


def p(s=''):
    OUT.append(s)


def rule(w=100):
    return '-' * w


def frac(f):
    return '%.6f' % float(f)


def record(check_id, status, summary, detail=()):
    RESULTS.append((check_id, status, summary, list(detail)))


# =======================================================================================
# Shared helper: does a concrete state satisfy a fact IN ISOLATION (membership in gamma(a_F)
# alone, not meeted with the baseline abstract state)?  This is the concrete predicate the
# fact forms license, per refanalyzer.py's own comment on apply_facts:
#   ('le', v, c) v<=c   ('ge', v, c) v>=c   ('in', v, a, b) a<=v<=b   ('set', v, S) v in S
#   ('subst', v, k, u, b) v == k*u + b     ('lepair', a, b) a <= b
# =======================================================================================
def fact_holds(prog, vals, fact):
    idx = {v: i for i, v in enumerate(prog.vars)}

    def val(x):
        return vals[idx[x]]

    kind = fact[0]
    if kind == 'le':
        return val(fact[1]) <= fact[2]
    if kind == 'ge':
        return val(fact[1]) >= fact[2]
    if kind == 'in':
        return fact[2] <= val(fact[1]) <= fact[3]
    if kind == 'set':
        return val(fact[1]) in fact[2]
    if kind == 'subst':
        _, v, k, u, b = fact
        return val(v) == k * val(u) + b
    if kind == 'lepair':
        return val(fact[1]) <= val(fact[2])
    raise ValueError(kind)


# =======================================================================================
# [CHECK-1] Soundness, both directions.
# =======================================================================================
def check1a_soundness_sweep():
    """(a) Every fold-injected example and every enumerable sweep point: the concrete
    reachable set at each point must be contained in the abstract state -- 0 violations.
    Mirrors run.py's per-example r.sound and sweep_soundness(), computed independently
    here directly from refanalyzer.soundness (the exposed reusable primitive)."""
    bad = []
    exhausted = []

    for ex in EXAMPLES:
        con = Concrete(ex.prog)
        mcon = Concrete(ex.mutant)
        if con.exhausted or mcon.exhausted:
            exhausted.append('pattern %d: enumeration budget exhausted' % ex.num)
            continue
        base = analyze(ex.prog)
        withf = analyze(ex.prog, ex.facts)
        mut = analyze(ex.mutant, ex.facts)
        for label, prog, res, c in (('pattern %d base' % ex.num, ex.prog, base, con),
                                    ('pattern %d with-fact' % ex.num, ex.prog, withf, con),
                                    ('pattern %d mutant' % ex.num, ex.mutant, mut, mcon)):
            b = soundness(prog, res, c)
            for item in b:
                bad.append((label,) + item)

    n_sweep_pts, n_sweep_checked = 0, 0
    for sw in SWEEPS:
        for sp_ in sw.points:
            n_sweep_pts += 1
            if not sp_.enumerable:
                continue
            con = Concrete(sp_.prog, trace=False)
            if con.exhausted:
                exhausted.append('sweep %s/%s: enumeration budget exhausted'
                                 % (sw.name, sp_.label))
                continue
            n_sweep_checked += 1
            for facts, tag in ((None, 'baseline'), (sp_.facts, 'with-fact')):
                res = analyze(sp_.prog, facts)
                b = soundness(sp_.prog, res, con)
                for item in b:
                    bad.append(('sweep %s/%s (%s)' % (sw.name, sp_.label, tag),) + item)

    status = 'PROVEN' if not bad and not exhausted else 'FAILED'
    detail = []
    if exhausted:
        detail.append('enumeration incomplete on %d point(s) (excluded from the count, '
                      'reported separately, not silently passed):' % len(exhausted))
        detail.extend('  - ' + e for e in exhausted)
    if bad:
        detail.append('SOUNDNESS VIOLATIONS (abstract state does not contain a reachable '
                      'concrete state):')
        for item in bad[:20]:
            detail.append('  - %s' % (item,))
        if len(bad) > 20:
            detail.append('  ... and %d more' % (len(bad) - 20))
    summary = ('0 violations across %d examples (base+with-fact+mutant) and %d/%d '
              'enumerable sweep points' % (len(EXAMPLES), n_sweep_checked, n_sweep_pts))
    return status, summary, detail, len(bad)


def check1b_validity_probes():
    """(b) For each of the 3 validity probes: exhibit a concrete reachable state s at the
    fact's injection point with s NOT IN gamma(a_F) -- the meet is provably subtractive.
    If a probe does not drop a reachable state, that contradicts the memo -- reported as a
    FAILED sub-case, not smoothed over."""
    detail = []
    n_ok = 0
    for (num_, what, prog, facts) in PROBES:
        con = Concrete(prog)
        witness_found = None
        for label, flist in facts.items():
            pt = prog.pt(label) if isinstance(label, str) else label
            for vals in con.reach.get(pt, ()):
                for f in flist:
                    if not fact_holds(prog, vals, f):
                        witness_found = (label, pt, vals, f)
                        break
                if witness_found:
                    break
            if witness_found:
                break

        # corroborating chain (Thm 1' full statement): PROVEN verdict on a check a
        # concrete execution actually violates.
        pc = check_pc(prog)
        v = verdict(prog, analyze(prog, facts), pc)
        has_violation = len(con.violations) > 0

        if witness_found is None:
            detail.append('  probe %d (%s): NO witness found -- CONTRADICTS the memo '
                          '(Thm 1\' predicts the meet is subtractive here)' % (num_, what))
        else:
            n_ok += 1
            label, pt, vals, f = witness_found
            idx = {v_: i for i, v_ in enumerate(prog.vars)}
            readable = ', '.join('%s=%d' % (v_, vals[idx[v_]]) for v_ in prog.vars)
            detail.append('  probe %d (%s):' % (num_, what))
            detail.append('    witness s at point %r: {%s}' % (label, readable))
            detail.append('    fact violated: %r  =>  s not in gamma(a_F)' % (f,))
            detail.append('    consequence: verdict=%s, concrete violation exists=%s'
                          % (v, has_violation))
            if not (v == 'PROVEN' and has_violation):
                detail.append('    NOTE: witness confirmed subtractive, but the '
                              'PROVEN+violates chain did not also hold -- reported, not '
                              'hidden')

    status = 'PROVEN' if n_ok == len(PROBES) else 'FAILED'
    summary = '%d/%d probes exhibit a concrete s not in gamma(a_F)' % (n_ok, len(PROBES))
    return status, summary, detail, len(PROBES) - n_ok


# =======================================================================================
# [CHECK-2] Strict recovery: closed-form DBFs re-asserted, cross-checked against run.py's
# own measure_dbf (imported, not recomputed), AND the FAIL->PROVEN verdict flip at the
# check site for every point that carries one.
# =======================================================================================
def check2_strict_recovery():
    detail = []
    n_pts, n_dbf_ok, n_flip_ok = 0, 0, 0
    dbf_bad, flip_bad = [], []

    for sw in SWEEPS:
        for sp_ in sw.points:
            if not sp_.enumerable:
                continue
            n_pts += 1
            n, hull, den, why = run_mod.measure_dbf(sp_)
            if n is None:
                dbf_bad.append('%s/%s: enumeration budget exhausted' % (sw.name, sp_.label))
                continue
            d_den = dbf(n, den)
            ok = (d_den == sp_.design)
            if ok:
                n_dbf_ok += 1
            else:
                dbf_bad.append('%s/%s: closed form %s = %s, measured %s (|S|=%d, denom=%d, '
                               '%s)' % (sw.name, sp_.label, sp_.design_expr, frac(sp_.design),
                                       frac(d_den), n, den, why))

            if sp_.verdict:
                pc = check_pc(sp_.prog)
                v0 = verdict(sp_.prog, analyze(sp_.prog), pc)
                v1 = verdict(sp_.prog, analyze(sp_.prog, sp_.facts), pc)
                if v0 == 'FAIL' and v1 == 'PROVEN':
                    n_flip_ok += 1
                else:
                    flip_bad.append('%s/%s: verdict flip is %s->%s, expected FAIL->PROVEN'
                                    % (sw.name, sp_.label, v0, v1))

    n_flip_pts = sum(1 for sw in SWEEPS for sp_ in sw.points if sp_.enumerable and sp_.verdict)

    if dbf_bad:
        detail.append('closed-form / enumeration discrepancies:')
        detail.extend('  - ' + d for d in dbf_bad)
    if flip_bad:
        detail.append('verdict-flip discrepancies:')
        detail.extend('  - ' + d for d in flip_bad)

    status = 'PROVEN' if not dbf_bad and not flip_bad else 'FAILED'
    summary = ('closed forms confirmed %d/%d points; verdict flip FAIL->PROVEN confirmed '
              '%d/%d points' % (n_dbf_ok, n_pts, n_flip_ok, n_flip_pts))
    return status, summary, detail, len(dbf_bad) + len(flip_bad)


# =======================================================================================
# [CHECK-3] EXACTNESS of the bijective folds -- the crux.
# =======================================================================================
def _is_contiguous(S):
    """S (a finite set of ints) equals its own interval hull -- both inclusions of
    gamma(hull(S)) == S in one predicate, since S subseteq gamma(hull(S)) always holds by
    construction of the hull; the only content is gamma(hull(S)) subseteq S."""
    if not S:
        return True, set()
    lo, hi = min(S), max(S)
    gamma = set(range(lo, hi + 1))
    missing_from_S = gamma - S      # gamma(hull) not subseteq S  => dead band
    return (not missing_from_S), missing_from_S


def check3_affine():
    rows = []
    for s in (2, 4, 8):
        for m in (4, 8, 16):
            N = s * m
            prog = _p1('p1chk-s%d-m%d' % (s, m), s, N, N)
            pt = prog.pt('body')
            con = Concrete(prog, trace=False)
            R = con.values_at(pt, 'i')
            c0 = 0
            grid_ok = all((i - c0) % s == 0 for i in R)
            Rg = set((i - c0) // s for i in R)
            exact, missing = _is_contiguous(Rg)
            rows.append(dict(s=s, m=m, trip=len(R), Rg_size=len(Rg), grid_ok=grid_ok,
                             exact=exact, missing=missing))
    return rows


def check3_lockstep():
    rows = []
    for n in (4, 8, 16):
        base, stride = 0, 1
        prog = _p16('p16chk-n%d' % n, n, base, stride, n)
        pt = prog.pt('body')
        con = Concrete(prog, trace=False)
        idx_i = prog.vars.index('i')
        idx_p = prog.vars.index('p')
        pairs = set((v[idx_i], v[idx_p]) for v in con.reach.get(pt, ()))
        expected_pairs = set((i, base + stride * i) for i in range(n))
        pairs_exact = (pairs == expected_pairs)
        Rg = set(v[idx_i] for v in con.reach.get(pt, ()))
        i_exact, missing = _is_contiguous(Rg)
        rows.append(dict(n=n, pairs_exact=pairs_exact, i_exact=i_exact,
                         pairs=pairs, expected_pairs=expected_pairs, missing=missing))
    return rows


def _p13_full(name, k, bound):
    """Same expression shape as examples._p13, WITHOUT the x>=0 restriction: x ranges
    over the full k-bit bit pattern, i.e. every two's-complement value in
    [-2^(k-1), 2^(k-1)).  This is the object Theorem 2c's ZigZag proof is actually about
    (the full bijection); examples.py's EX13 deliberately restricts to the non-negative
    half (its own docstring: "8-bit ZigZag, x >= 0"), which is a documented, WEAKER
    approximation (DBF=1/2, examples.py's own approx footnote), not the theorem's subject.
    check3_zigzag_half_asbuilt() below tests that weaker, as-implemented instance too, and
    the two results are reported side by side rather than conflated."""
    mask = (1 << k) - 1
    b = Builder(name, 2 * k if k <= 16 else 64)
    b.inp('x', 0, mask)
    b.shr('s', 'x', k - 1)
    b.mul('m', 's', mask)
    b.shl('y', 'x', 1)
    b.band('y', 'y', mask)
    b.bxor('z', 'y', 'm')
    b.label('chk'); b.check_bound('z', bound)
    b.halt()
    return b.build()


def check3_zigzag_full():
    rows = []
    for k in (4, 8, 12):
        prog = _p13_full('p13full-k%d' % k, k, (1 << k) - 1)
        pt = check_pc(prog)
        con = Concrete(prog, trace=False)
        Rg = con.values_at(pt, 'z')
        exact, missing = _is_contiguous(Rg)
        expected = set(range(0, 1 << k))
        full_match = (Rg == expected)
        rows.append(dict(k=k, domain=1 << k, Rg_size=len(Rg), exact=exact,
                         full_match=full_match, missing=missing,
                         exhausted=con.exhausted))
    return rows


def check3_zigzag_half_asbuilt():
    """The as-implemented catalogue instance (EX13's builder, x>=0 only).  Expected to be
    NOT exact (DBF=1/2), per examples.py's own approx footnote.  Reported for honesty, NOT
    counted against CHECK-3's PROVEN/FAILED verdict, since it tests a documented weaker
    approximation, not Theorem 2c's stated claim (the full bijection, checked above)."""
    rows = []
    for k in (4, 8, 12):
        prog = _p13('p13half-k%d' % k, k, (1 << k) - 1)
        pt = check_pc(prog)
        con = Concrete(prog, trace=False)
        Rg = con.values_at(pt, 'z')
        exact, missing = _is_contiguous(Rg)
        lo, hi = min(Rg), max(Rg)
        rows.append(dict(k=k, Rg_size=len(Rg), hull=(hi - lo + 1), exact=exact,
                         dbf=dbf(len(Rg), hi - lo + 1)))
    return rows


SYMBOLIC_ARGUMENT = """\
  Affine IV (all s > 0, all trip counts m >= 1, all widths w with no wraparound):
    R = {c0, c0+s, ..., c0+s(m-1)}, an arithmetic progression.  g(i) = (i-c0)/s is exact
    integer division on every element of R by construction (each element is c0 plus a
    multiple of s).  g is therefore a bijection R -> {0,...,m-1}: injective because s != 0,
    and its image is the full contiguous range {0,...,m-1} because g is literally the index
    of the term in the progression.  No case split on s, m or w is needed -- the argument is
    uniform, so it holds for ALL s, m, w simultaneously (w only enters through the
    already-excluded wraparound case, per the pattern's own validity condition).

  ZigZag (all widths k >= 1):
    Partition the signed domain [-2^(k-1), 2^(k-1)) into x >= 0 (2^(k-1) elements) and
    x < 0 (2^(k-1) elements).  On x >= 0, g(x) = 2x is injective and its image is exactly
    the even values {0, 2, ..., 2^k - 2} (2^(k-1) of them).  On x < 0, g(x) = -2x-1 is
    injective and its image is exactly the odd values {1, 3, ..., 2^k - 1} (2^(k-1) of
    them, since x ranges over -1..-2^(k-1)).  Evens union odds of [0, 2^k) is [0, 2^k)
    itself, with no overlap and no gap -- a partition, not a cover with slack.  This holds
    for every k with the same two-case argument; no per-k enumeration is logically needed
    (the enumeration above is the finite-width RECEIPT, not the reason it's true).
"""


def check3():
    detail = []
    aff = check3_affine()
    lock = check3_lockstep()
    zz_full = check3_zigzag_full()
    zz_half = check3_zigzag_half_asbuilt()

    aff_bad = [r for r in aff if not (r['grid_ok'] and r['exact'])]
    lock_bad = [r for r in lock if not (r['pairs_exact'] and r['i_exact'])]
    zzf_bad = [r for r in zz_full if not (r['exact'] and r['full_match'])]

    detail.append('affine IV -- g(i)=(i-c0)/s, c0=0 fixed by the builder:')
    for r in aff:
        mark = 'exact' if (r['grid_ok'] and r['exact']) else 'NOT EXACT'
        detail.append('  s=%-2d m=%-3d  |R|=%-3d |R_g|=%-3d  grid_ok=%-5s  %s%s'
                      % (r['s'], r['m'], r['trip'], r['Rg_size'], r['grid_ok'], mark,
                         '' if not r['missing'] else ('  missing=%s' % sorted(r['missing']))))

    detail.append('lockstep -- g(p,i)=i, recovery p=base+s*i (base=0, s=1):')
    for r in lock:
        mark = 'exact' if (r['pairs_exact'] and r['i_exact']) else 'NOT EXACT'
        detail.append('  n=%-3d  pairs_exact=%-5s  i_range_exact=%-5s  %s'
                      % (r['n'], r['pairs_exact'], r['i_exact'], mark))

    detail.append('ZigZag, FULL bijection (Theorem 2c\'s actual subject, tested via a '
                  'full-domain variant of _p13\'s own expression, dropping the x>=0 '
                  'restriction -- refanalyzer.Concrete enumerated):')
    for r in zz_full:
        mark = 'exact' if (r['exact'] and r['full_match']) else 'NOT EXACT'
        exh = '  [ENUMERATION EXHAUSTED]' if r['exhausted'] else ''
        detail.append('  k=%-2d  domain=%-6d |R_g|=%-6d full_match=%-5s  %s%s'
                      % (r['k'], r['domain'], r['Rg_size'], r['full_match'], mark, exh))

    detail.append('ZigZag, AS-BUILT catalogue instance (examples.py EX13/pattern-13, '
                  'x>=0 half only -- informational, NOT part of the CHECK-3 verdict; '
                  'this restriction and its DBF=1/2 are already documented in examples.py\'s '
                  'approx footnote for pattern 13):')
    for r in zz_half:
        detail.append('  k=%-2d  |R_g|=%-6d hull=%-6d exact=%-5s dbf=%s%s'
                      % (r['k'], r['Rg_size'], r['hull'], r['exact'], frac(r['dbf']),
                         '  <- expected NOT exact, matches examples.py\'s own footnote'
                         if not r['exact'] else '  ** UNEXPECTED: as-built half is exact **'))

    # corollary 2c' -- import witness.py's own cases, minimal confirmation, no duplication
    detail.append('')
    detail.append('corollary 2c\' (self-witnessing): citing eval/witness/witness.py, '
                  'calling case_affine()/case_zigzag()/case_lockstep() unmodified:')
    wit_bad = []
    for name, fn in (('affine', witness_mod.case_affine),
                     ('zigzag', witness_mod.case_zigzag),
                     ('lockstep', witness_mod.case_lockstep)):
        r = fn()
        ok = r['concrete_reachable'] and r['concrete_violates']
        if not ok:
            wit_bad.append(name)
        detail.append('  %-9s inverted input: %-40s reachable=%-5s violates=%-5s  %s'
                      % (name, r['inverted_input'], r['concrete_reachable'],
                         r['concrete_violates'], 'OK' if ok else 'FAILED'))

    detail.append('')
    detail.append('width-parametric claim (all k / all s,m -- no solver available):')
    for ln in SYMBOLIC_ARGUMENT.splitlines():
        detail.append('  ' + ln)

    bad_total = len(aff_bad) + len(lock_bad) + len(zzf_bad) + len(wit_bad)
    status = 'PROVEN' if bad_total == 0 else 'FAILED'
    summary = ('affine %d/%d exact, lockstep %d/%d exact, ZigZag-full %d/%d exact, '
              'corollary-2c\' %d/3 confirmed  [ZigZag as-built half-domain instance is '
              'informational, correctly non-exact, not counted]'
              % (len(aff) - len(aff_bad), len(aff), len(lock) - len(lock_bad), len(lock),
                 len(zz_full) - len(zzf_bad), len(zz_full), 3 - len(wit_bad)))
    return status, summary, detail, bad_total, dict(z3_available=False)


# =======================================================================================
# [CHECK-4] Inexact folds are may-ONLY: Theorem 3's {0,4,6} counterexample.
# =======================================================================================
def check4_inexact_convexification():
    """Pure finite set arithmetic, mirroring the memo's own proof of Theorem 3 exactly (the
    memo's proof needs no program execution either -- it is a counterexample about the
    map g and the set S = {0,4,6}, not about any specific IR encoding of it).  refanalyzer/
    examples are not needed here for the same reason they are not needed in the memo's own
    proof text; this is noted explicitly rather than manufacturing machinery to use them."""
    detail = []
    S = {0, 4, 6}
    g_gcd = math.gcd(math.gcd(0, 4), 6)   # gcd(0,4,6): gcd(0,x)=x, so this is gcd(4,6)=2
    Rg = set(x // g_gcd for x in S)       # {0,2,3}
    lo, hi = min(Rg), max(Rg)
    gamma_hull = set(range(lo, hi + 1))   # {0,1,2,3}
    dead_band = gamma_hull - Rg           # {1}

    strict = bool(dead_band)              # gamma(hull) strictly a superset of R_g
    exhibit_ok = 1 in dead_band

    # no reachable g^-1 preimage for the dead-band element 1: g^-1(1) = 1*g_gcd = 2, and
    # 2 must not be a member of the ORIGINAL offset set S (the only "reachable" offsets).
    j = 1
    preimage = j * g_gcd
    no_preimage = preimage not in S

    detail.append('  S (original offsets)         = %s' % sorted(S))
    detail.append('  gcd(S)                        = %d' % g_gcd)
    detail.append('  R_g = g(S) = S / gcd(S)        = %s' % sorted(Rg))
    detail.append('  hull(R_g)                     = [%d, %d]' % (lo, hi))
    detail.append('  gamma(hull(R_g))               = %s' % sorted(gamma_hull))
    detail.append('  gamma(hull) \\ R_g (dead band)  = %s' % sorted(dead_band))
    detail.append('  gamma(a_g) strictly superset of R_g   : %s' % strict)
    detail.append('  1 exhibited in the dead band   : %s' % exhibit_ok)
    detail.append('  g^-1(1) = 1*gcd(S) = %d         : %s (not in S)' % (preimage, no_preimage))

    ok = strict and exhibit_ok and no_preimage
    status = 'PROVEN' if ok else 'FAILED'
    summary = ('gamma(a_g) strictly contains R_g (%s); dead-band witness 1 exhibited '
              '(%s); no g^-1 preimage for it (%s)' % (strict, exhibit_ok, no_preimage))
    return status, summary, detail, 0 if ok else 1


# =======================================================================================
def main(argv):
    check_mode = '--check' in argv

    p('=' * 100)
    p('PROOF CHECKER -- research/precision-proofs.md, [CHECK-1]..[CHECK-4]')
    p('reproduce with:  python3 eval/proof/check_proofs.py   (deterministic; no clock, '
     'no randomness)')
    p('=' * 100)
    p('')

    # ---- CHECK-1a ----
    s1a, m1a, d1a, n1a = check1a_soundness_sweep()
    record('CHECK-1a', s1a, m1a, d1a)

    # ---- CHECK-1b ----
    s1b, m1b, d1b, n1b = check1b_validity_probes()
    record('CHECK-1b', s1b, m1b, d1b)

    s1 = 'PROVEN' if (s1a == 'PROVEN' and s1b == 'PROVEN') else 'FAILED'

    # ---- CHECK-2 ----
    s2, m2, d2, n2 = check2_strict_recovery()
    record('CHECK-2', s2, m2, d2)

    # ---- CHECK-3 ----
    s3, m3, d3, n3, extra3 = check3()
    record('CHECK-3', s3, m3, d3)

    # ---- CHECK-4 ----
    s4, m4, d4, n4 = check4_inexact_convexification()
    record('CHECK-4', s4, m4, d4)

    p('SUMMARY TABLE')
    p('')
    hdr = '  %-10s %-8s %s' % ('check', 'status', 'summary')
    p(hdr)
    p('  ' + rule(len(hdr) - 2))
    p('  %-10s %-8s %s' % ('CHECK-1a', s1a, m1a))
    p('  %-10s %-8s %s' % ('CHECK-1b', s1b, m1b))
    p('  %-10s %-8s %s' % ('CHECK-1', s1, '(a) and (b) both directions of soundness'))
    p('  %-10s %-8s %s' % ('CHECK-2', s2, m2))
    p('  %-10s %-8s %s' % ('CHECK-3', s3, m3))
    p('  %-10s %-8s %s' % ('CHECK-4', s4, m4))
    p('')

    for cid, status, summary, detail in RESULTS:
        p('%s  [%s]' % (cid, status))
        p('  ' + summary)
        for ln in detail:
            p(ln if ln.startswith('  ') else '  ' + ln)
        p('')

    all_status = [s1a, s1b, s2, s3, s4]
    failed = [rid for rid, st, _, _ in RESULTS if st == 'FAILED']
    p('=' * 100)
    if failed:
        p('RESULT: %d/%d sub-obligations FAILED: %s' % (len(failed), len(RESULTS), failed))
        p('A failed obligation here is a machine-confirmed counterexample to the memo -- ')
        p('see the corresponding section above for the concrete witness. Not fudged, not ')
        p('weakened.')
    else:
        p('RESULT: all obligations PROVEN. 0 soundness violations; 0 closed-form/verdict-')
        p('flip discrepancies; bijective-fold exactness confirmed by set equality at every ')
        p('tested width; the negative-side (inexact-fold) counterexample confirmed.')
    p('=' * 100)

    text = '\n'.join(OUT) + '\n'
    sys.stdout.write(text)

    if check_mode:
        return 1 if failed else 0
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
