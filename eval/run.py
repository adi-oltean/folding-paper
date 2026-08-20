"""run.py -- prints the evaluation chapter's tables.

    python3 eval/run.py                 print the tables
    python3 eval/run.py --out FILE      ... and save them
    python3 eval/run.py --check         assert every expectation; exit nonzero on failure

Everything printed is recomputed from eval/refanalyzer.py + eval/examples.py on every run;
nothing is cached, nothing is randomised, nothing reads a clock.
"""

import sys
import textwrap
from fractions import Fraction

from refanalyzer import (Concrete, analyze, check_pc, dbf, soundness, verdict)
from examples import EXAMPLES, PROBES, SWEEPS

OUT = []
FAILURES = []        # hard failures
DISCREPANCIES = []   # closed-form vs enumeration disagreements, reported distinctly


def p(s=''):
    OUT.append(s)


def num(n):
    """Compact but exact-looking integer rendering for interval widths."""
    if n < 10 ** 7:
        return str(n)
    e = len(str(n)) - 1
    return '%.2fe%d' % (n / float(10 ** e), e)


def frac(f):
    v = float(f)
    if v != 0.0 and abs(v) < 1e-4:
        return '%.2e' % v
    return '%.6f' % v


def rule(w):
    return '-' * w


# =======================================================================================
# Leg B -- per-example verdicts
# =======================================================================================
class Row:
    pass


def run_example(ex):
    r = Row()
    r.ex = ex
    r.pc = check_pc(ex.prog)
    r.mpc = check_pc(ex.mutant)
    r.var = ex.prog.stmts[r.pc][1]
    r.base = analyze(ex.prog)
    r.withf = analyze(ex.prog, ex.facts)
    r.mut = analyze(ex.mutant, ex.facts)
    r.v0 = verdict(ex.prog, r.base, r.pc)
    r.v1 = verdict(ex.prog, r.withf, r.pc)
    r.vm = verdict(ex.mutant, r.mut, r.mpc)
    r.w0 = r.base.width(r.pc, r.var)
    r.w1 = r.withf.width(r.pc, r.var)
    r.con = Concrete(ex.prog)
    r.mcon = Concrete(ex.mutant)
    r.mut_viol = r.mcon.violations[0] if r.mcon.violations else None
    r.own_viol = r.con.violations[0] if r.con.violations else None
    r.sound = soundness(ex.prog, r.withf, r.con) + soundness(ex.prog, r.base, r.con) \
        + soundness(ex.mutant, r.mut, r.mcon)
    r.exhausted = r.con.exhausted or r.mcon.exhausted
    return r


def table1(rows):
    p('TABLE 1  Per-pattern verdicts, interval width at the check site, widening steps')
    p('         (one canonical program per catalogue pattern; the fact injected is exactly')
    p('          the fact the pattern supplies, at the point its validity condition holds)')
    p('')
    hdr = ('  #  axis      program                                          '
           'no fact  with fact  mutant   width(no)  width(with)  ratio      widen  widen')
    p(hdr)
    p('  %-2s %-9s %-48s %-8s %-10s %-8s %-10s %-12s %-10s %-6s %-6s'
      % ('', '', '', '(base)', '(fact)', '(fact)', '(base)', '(fact)', 'with/no',
         '(base)', '(fact)'))
    p('  ' + rule(len(hdr) - 2))
    for r in rows:
        ratio = Fraction(r.w1, r.w0) if r.w0 else Fraction(0)
        p('  %-2d %-9s %-48s %-8s %-10s %-8s %-10s %-12s %-10s %-6d %-6d'
          % (r.ex.num, r.ex.axis, r.ex.title[:48], r.v0, r.v1, r.vm,
             num(r.w0), num(r.w1), frac(ratio),
             r.base.widen_count, r.withf.widen_count))
    p('')


# =======================================================================================
# Leg A -- swept dead-band fractions, measured against the closed forms
# =======================================================================================
def measure_dbf(sp):
    """Returns (reach_size, hull_size, denom_size, note) with everything ENUMERATED."""
    prog = sp.prog
    pt = prog.pt(sp.point)
    con = Concrete(prog, trace=False)
    if con.exhausted:
        return None, None, None, 'enumeration budget exhausted'
    if sp.kind == 'pair':
        i0 = prog.vars.index(sp.vars2[0])
        i1 = prog.vars.index(sp.vars2[1])
        pairs = set((v[i0], v[i1]) for v in con.reach.get(pt, ()))
        xs = [a for a, _ in pairs]
        ys = [b for _, b in pairs]
        hull = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
        return len(pairs), hull, hull, 'box = product of the two tightest intervals'
    if sp.kind == 'bytes':
        base = con.values_at(pt, sp.var)
        touched = set()
        for a in base:
            touched.update(range(a, a + sp.gsz))
        hull = max(touched) - min(touched) + 1
        return len(touched), hull, sp.denom, 'touched bytes of the region'
    S = con.values_at(pt, sp.var)
    hull = max(S) - min(S) + 1
    if sp.denom == 'hull':
        return len(S), hull, hull, 'tightest interval hull'
    if sp.denom == 'baseline':
        w = analyze(prog).width(pt, sp.var)
        if sp.expect_denom is not None and w != sp.expect_denom:
            FAILURES.append('sweep %s: baseline interval width %d != declared %d'
                            % (sp.label, w, sp.expect_denom))
        return len(S), hull, w, 'interval held without the fact (measured)'
    return len(S), hull, sp.denom, 'declared extent'


def table2():
    p('TABLE 2  Swept dead-band fractions: closed form vs. enumeration')
    p('         |S| is the exact reachable set at the point, enumerated by the concrete')
    p('         interpreter.  DBF(hull) uses the tightest interval hull (the design\'s')
    p('         literal definition); DBF(denom) uses the denominator the pattern\'s closed')
    p('         form is a closed form for, named in the last column.')
    p('')
    for sw in SWEEPS:
        p('  pattern %s -- %s   (parameter: %s)'
          % ('/'.join(str(x) for x in sw.patterns), sw.name, sw.param))
        hdr = ('     %-16s %-10s %-12s %-12s %-12s %-11s %-6s %-9s %s'
               % ('param', '|S|', 'hull', 'DBF(hull)', 'DBF(denom)', 'closed form',
                  'match', 'verdicts', 'denominator'))
        p(hdr)
        p('     ' + rule(len(hdr) - 5))
        for sp_ in sw.points:
            if not sp_.enumerable:
                p('     %-16s %-10s %-12s %-12s %-12s %-11s %-6s %-9s %s'
                  % (sp_.label, 'n/a', 'n/a', 'n/a', 'n/a', frac(sp_.design),
                     'n/a', 'n/a', 'not enumerated (budget)'))
                continue
            n, hull, den, why = measure_dbf(sp_)
            if n is None:
                p('     %-16s enumeration budget exhausted' % sp_.label)
                FAILURES.append('sweep %s: enumeration budget exhausted' % sp_.label)
                continue
            d_hull = dbf(n, hull)
            d_den = dbf(n, den)
            ok = (d_den == sp_.design)
            if not ok:
                DISCREPANCIES.append(
                    '%s [%s]: closed form %s = %s, enumeration gives %s (|S|=%d, denom=%d)'
                    % (sw.name, sp_.label, sp_.design_expr, frac(sp_.design),
                       frac(d_den), n, den))
            vs = '-'
            if sp_.verdict:
                pc = check_pc(sp_.prog)
                v0 = verdict(sp_.prog, analyze(sp_.prog), pc)
                v1 = verdict(sp_.prog, analyze(sp_.prog, sp_.facts), pc)
                vs = '%s->%s' % (v0[:4], v1[:4])
            p('     %-16s %-10s %-12s %-12s %-12s %-11s %-6s %-9s %s'
              % (sp_.label, num(n), num(hull), frac(d_hull), frac(d_den),
                 frac(sp_.design), 'YES' if ok else 'NO', vs, why))
        if sw.note:
            for i, ln in enumerate(textwrap.wrap(sw.note, 92)):
                p('     %s%s' % ('note: ' if i == 0 else '      ', ln))
        p('')


# =======================================================================================
# Aggregate
# =======================================================================================
def table3(rows):
    flips = [r for r in rows if r.v0 == 'FAIL' and r.v1 == 'PROVEN']
    mflips = [r for r in rows if r.vm == 'PROVEN']
    ratios = sorted(Fraction(r.w1, r.w0) for r in rows if r.w0)
    k = len(ratios)
    med = ratios[k // 2] if k % 2 else (ratios[k // 2 - 1] + ratios[k // 2]) / 2
    unsound = [r for r in rows if r.sound]
    nowit = [r for r in rows if r.mut_viol is None]
    p('TABLE 3  Aggregate')
    p('')
    p('     verdict discharge (FAIL -> PROVEN)        %d/%d' % (len(flips), len(rows)))
    p('     mutant flips (unsafe check proven)        %d/%d   [must be 0]'
      % (len(mflips), len(rows)))
    p('     mutants with a concrete counterexample    %d/%d' % (len(rows) - len(nowit),
                                                                len(rows)))
    p('     soundness violations (abstract vs. concrete enumeration)   %d' % len(unsound))
    p('     median width ratio at the check site      %s' % frac(med))
    p('     width ratio range                         %s .. %s'
      % (frac(ratios[0]), frac(ratios[-1])))
    p('     closed-form DBF discrepancies             %d' % len(DISCREPANCIES))
    p('')


def table4(rows):
    p('TABLE 4  No-free-lunch controls: the concrete counterexample behind each mutant')
    p('')
    hdr = ('  #  mutation                                                     '
           'concrete violating execution')
    p(hdr)
    p('  ' + rule(len(hdr) - 2))
    for r in rows:
        w = 'none'
        if r.mut_viol:
            pc, vals = r.mut_viol
            s = r.ex.mutant.stmts[pc]
            v = vals[r.ex.mutant.vars.index(s[1])]
            steps = len(r.mcon.trace_to(pc, vals))
            w = '%s=%d fails %s after %d steps' % (s[1], v, s[0], steps)
        p('  %-2d %-60s %s' % (r.ex.num, r.ex.mut_note[:60], w))
    p('')


def table5():
    p('TABLE 5  Validity probes -- the OTHER failure direction (not counted anywhere above)')
    p('         Each row breaks the pattern\'s validity condition and injects the fact')
    p('         anyway.  The fact is then invalid, meeting it is subtractive, and the')
    p('         analysis proves a check that a concrete execution violates.  This is the')
    p('         soundness obligation of the paper\'s section on validity, exhibited.')
    p('')
    hdr = ('  #  broken validity condition                 verdict   violation   '
           'fact ok?  outcome')
    p(hdr)
    p('  ' + rule(len(hdr) - 2))
    for (num_, what, prog, facts) in PROBES:
        pc = check_pc(prog)
        res = analyze(prog, facts)
        con = Concrete(prog)
        v = verdict(prog, res, pc)
        viol = 'yes' if con.violations else 'no'
        # does the injected fact actually hold on every concrete state at its point?
        holds = 'yes'
        for lbl, fl in facts.items():
            pt = prog.pt(lbl)
            for f in fl:
                vals = con.values_at(pt, f[1])
                if f[0] == 'le' and any(x > f[2] for x in vals):
                    holds = 'NO'
                if f[0] == 'set' and any(x not in f[2] for x in vals):
                    holds = 'NO'
        if v == 'PROVEN' and viol == 'yes' and holds == 'NO':
            note = 'UNSOUND, as the paper predicts'
        elif holds == 'yes':
            note = 'fact still valid; no unsoundness'
        else:
            note = 'invalid fact, check still fails'
        p('  %-2d %-42s %-9s %-11s %-9s %s'
          % (num_, what[:42], v, viol, holds, note))
    p('')


# =======================================================================================
def footnotes(rows):
    p('FOOTNOTES')
    p('')
    p('  [A] Baseline domain.  The BASELINE column is a textbook interval analysis:')
    p('      bitwise and/or/xor have no interval transfer and return TOP (they are folded')
    p('      exactly on singleton operands); shifts by a constant ARE precise, being')
    p('      multiplication/division by a power of two.  Any operation whose exact integer')
    p('      result may leave [0, 2^w) returns TOP -- the concrete semantics wraps, the')
    p('      abstract side refuses to guess.  Widening is to thresholds drawn from the')
    p('      program\'s and the fact\'s constants, followed by a standard descending pass.')
    p('')
    p('  [B] Fact-only components.  The small-set component and the relational <= side')
    p('      table are NEVER synthesised by a transfer function -- they are populated only')
    p('      by injected facts, and propagate through copies, joins, meets and comparison')
    p('      edges.  The baseline therefore stays a plain interval analysis.')
    p('')
    p('  [C] Mutants break the CHECK, never the pattern\'s validity condition, so the')
    p('      injected fact stays valid and injecting it stays sound; the mutant tests that')
    p('      the fold buys no free lunch.  Breaking the validity condition instead is the')
    p('      other failure direction and is reported separately in TABLE 5.')
    p('')
    p('  [D] Approximations.  Where the fact this analyzer can express is weaker than the')
    p('      fact the paper describes, the weaker fact is what was injected:')
    for r in rows:
        if r.ex.approx:
            w = textwrap.wrap(r.ex.approx, 78)
            p('      pattern %-2d %s' % (r.ex.num, w[0]))
            for ln in w[1:]:
                p('                 ' + ln)
    p('')
    p('  [E] Soundness.  For every program, every variant and every sweep point, the')
    p('      abstract state at each program point was checked to CONTAIN the complete')
    p('      concrete reachable set at that point, enumerated by the interpreter.')
    p('')
    p('  [F] UNREACH is reported as its own verdict: an empty abstract state proves every')
    p('      check vacuously and is never counted as a discharge.')
    p('')
    p('  [G] DBF denominators.  DESIGN.md defines DBF against "the tightest convex')
    p('      approximation".  For patterns 3, 14 and 16 that is what its closed form is a')
    p('      closed form for, and DBF(hull) = DBF(denom) in TABLE 2.  For patterns 1/2,')
    p('      5/6 and 13 the design\'s formula is a closed form for a DIFFERENT, larger')
    p('      denominator -- respectively the interval the analysis holds without the fact,')
    p('      the declared byte extent of the region, and the k-bit encoded space -- so')
    p('      both fractions are printed and each sweep says which one its formula matches.')
    p('      No formula was chosen after seeing the measurement: each derivation is in the')
    p('      comment above its sweep in examples.py, and --check compares against the')
    p('      denominator that comment declares.')
    p('')


def header():
    p('=' * 100)
    p('FOLDING -- EVALUATION HARNESS OUTPUT')
    p('reproduce with:  python3 eval/run.py        (deterministic; no clock, no randomness)')
    p('=' * 100)
    p('')


def sweep_soundness():
    """Leg A's programs are analysed too: with the fact injected, containment must hold."""
    bad = 0
    for sw in SWEEPS:
        for sp_ in sw.points:
            if not sp_.enumerable:
                continue
            con = Concrete(sp_.prog, trace=False)
            if con.exhausted:
                FAILURES.append('sweep %s: enumeration exhausted' % sp_.label)
                continue
            for facts in (None, sp_.facts):
                b = soundness(sp_.prog, analyze(sp_.prog, facts), con)
                if b:
                    bad += 1
                    FAILURES.append('sweep %s unsound: %s' % (sp_.label, b[0]))
    return bad


def main(argv):
    check = '--check' in argv
    out = None
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]

    rows = [run_example(ex) for ex in EXAMPLES]
    header()
    table1(rows)
    table2()
    table3(rows)
    table4(rows)
    table5()
    footnotes(rows)

    nsweep_bad = sweep_soundness()

    # --- hard expectations --------------------------------------------------------
    for r in rows:
        if r.v0 != 'FAIL':
            FAILURES.append('pattern %d: baseline verdict is %s, expected FAIL'
                            % (r.ex.num, r.v0))
        if r.v1 != 'PROVEN':
            FAILURES.append('pattern %d: with-fact verdict is %s, expected PROVEN'
                            % (r.ex.num, r.v1))
        if r.vm != 'FAIL':
            FAILURES.append('pattern %d: MUTANT verdict is %s, expected FAIL'
                            % (r.ex.num, r.vm))
        if r.mut_viol is None:
            FAILURES.append('pattern %d: mutant has no concrete violating execution'
                            % r.ex.num)
        if r.own_viol is not None:
            FAILURES.append('pattern %d: the SAFE program has a concrete violation'
                            % r.ex.num)
        if r.sound:
            FAILURES.append('pattern %d: soundness violation %s' % (r.ex.num, r.sound[0]))
        if r.exhausted:
            FAILURES.append('pattern %d: enumeration budget exhausted' % r.ex.num)

    if DISCREPANCIES:
        p('CLOSED-FORM DISCREPANCIES (enumeration disagrees with DESIGN.md)')
        p('')
        for d in DISCREPANCIES:
            p('  * ' + d)
        p('')
        p('  These are recorded, not reconciled: the closed form in DESIGN.md and the')
        p('  measurement disagree, and the paper author decides which is wrong.')
        p('')

    if FAILURES:
        p('HARNESS FAILURES')
        p('')
        for f in FAILURES:
            p('  * ' + f)
        p('')
    else:
        p('All harness expectations hold: 16/16 verdict flips, 0/16 mutant flips with a')
        p('concrete counterexample behind every mutant, and containment of the enumerated')
        p('concrete reachable set at every point of every program.')
        p('')

    text = '\n'.join(OUT) + '\n'
    sys.stdout.write(text)
    if out:
        with open(out, 'w') as fh:
            fh.write(text)
    if check:
        bad = len(FAILURES) + len(DISCREPANCIES) + nsweep_bad
        if bad:
            sys.stderr.write('--check FAILED: %d failure(s), %d closed-form '
                             'discrepancy(ies)\n' % (len(FAILURES), len(DISCREPANCIES)))
            return 1
        sys.stderr.write('--check OK\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
