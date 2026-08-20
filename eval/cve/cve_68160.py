"""cve_68160.py -- E1: does folding recover precision on real pre-fix OpenSSL CVE code?

CVE-2025-68160, `linebuffer_write`, `crypto/bio/bf_lbuf.c` (OpenSSL 1.1.1 branch).
  pre-fix source read at parent commit 310f305eb92ea8040d6b3cb75a5feeba8e6acf2f
  fix commit                            4c96fbba618e1940f038012506ee9e21d32ee12c
  (cherry-picked from b21663c35a6f0ed4c8de06855bdc7a6a21f00c2f)
Both cited in research/security-cve-survey.md Part 4d, which is the source of every
line-number/mechanism claim below -- re-derive by reading that file's 4d section
side by side with this one.

WHAT THIS MEASURES (per the survey's Q3 / the task brief -- precision, not detection):
`linebuffer_write`'s main loop clamps two copies against remaining buffer capacity
(bf_lbuf.c lines ~140-149, "SITE1"/"SITE2" below) -- both are genuinely SAFE, both are
predicted by the survey to be FALSE POSITIVES for a non-relational interval analysis
because the clamp's safety depends on a relation (`fill_level + to_copy <= capacity`)
that a plain interval domain loses across the add.  The trailing fallback copy after
the loop (bf_lbuf.c ~193-197, "SITE3") has NO capacity check in the source at all -- it
is the real bug (a short BIO_write can leave a leftover chunk larger than the space the
short write freed).  Question: does injecting the R1 cursor-pair invariant
(`fill_level <= capacity`) at SITE1/SITE2 discharge those two false positives while
leaving SITE3's true alarm untouched (folding is sound: it must never make a real bug
disappear)?

refanalyzer.py (eval/refanalyzer.py) is imported UNCHANGED.  No new fact kind is used:
every fact below is `lepair` (`a <= b`, already in refanalyzer's vocabulary).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from refanalyzer import Builder, Concrete, analyze, soundness, verdict  # noqa: E402

CAP = 16        # ctx->obuf_size -- a fixed capacity chosen by the BIO's caller at creation
MAXCHUNK = 24    # inl -- caller-supplied write length for this call, deliberately > CAP so
                 # the partial/overflow path is reachable
WIDTH = 16       # IR width; CAP/MAXCHUNK are tiny, chosen so the concrete interpreter can
                 # exhaustively enumerate every reachable state (17*25*17 = 7,225 states)


# =======================================================================================
# The IR model
# =======================================================================================
def build_program():
    """Faithful (with documented simplifications -- see MODEL NOTES below) IR encoding of
    `linebuffer_write`'s ONE buffering pass: fill the internal line buffer up to capacity
    (SITE1/SITE2, both correctly clamped in the source), attempt to drain it with one
    BIO_write to the next filter (which may SHORT-WRITE -- RFC-legal, the actual trigger),
    then perform the trailing "no newline found" fallback copy that the source does NOT
    guard (SITE3, the real CVE-2025-68160 write).

    Each IR statement below is commented against the real bf_lbuf.c line it models.

    MODEL NOTES (read before trusting the numbers):
      * `fill` (ctx->obuf_len at entry) is modeled as fully free, input(0,CAP) -- it is a
        persistent struct field carried across calls, and this is the honest treatment of
        "could be mid-buffering, not just a fresh call".
      * `chunk` (inl for this call) is input(0,MAXCHUNK) -- caller/attacker controlled.
      * `drained` (the return of `i = BIO_write(b->next_bio, ctx->obuf, ctx->obuf_len)`,
        bf_lbuf.c:157) must satisfy BIO_write's own interface contract, `0 <= return <=
        requested`, where the requested amount is `fill2` (ctx->obuf_len going into the
        call) -- a RUNTIME VALUE.  This IR's `input` opcode only accepts LITERAL bounds,
        so "returns anything up to fill2" cannot be written as one `input` statement; it
        is built structurally instead (an explicit min-of-two-values clamp via a branch,
        see the `merge` block below), so the `drained <= fill2` contract is a genuine,
        concretely-enforced property, not an unearned assumption injected as a fact.
        (An earlier draft skipped the branch and injected the clamp as a bare fact --
        `soundness()` caught it immediately, see caveats in E1-RESULTS.md.)
      * The two nested loops of the real function (the do-while retry and the "did we
        find a newline" outer loop) are collapsed to ONE pass: fill once, drain once with
        one (possibly short) BIO_write, then go straight to the trailing fallback.  This
        matches exactly the `!foundnl` exit path the survey traces (no trailing newline in
        this call's input -- the path CVE-2025-68160 actually needs), not the general
        multi-iteration case.  A full multi-iteration model would need a memory/string
        model this tiny scalar IR does not have -- simplified and labeled, per instructions.
    """
    b = Builder('linebuffer_write_68160_prefix', WIDTH)

    b.const('cap', CAP)                      # ctx->obuf_size, a fixed per-BIO constant
    b.inp('fill', 0, CAP)                    # ctx->obuf_len on entry (persistent, free)
    b.inp('chunk', 0, MAXCHUNK)              # inl for this call (attacker-controlled)

    # bf_lbuf.c:140   i = ctx->obuf_size - ctx->obuf_len;      (remaining space)
    b.sub('remaining', 'cap', 'fill')

    # bf_lbuf.c:141   if (i >= llen) { ... } else { ... }
    #   true edge (remaining < chunk)  -> SITE2, the "else" / partial-clamp branch
    #   false edge (remaining >= chunk) -> SITE1, the "if" / whole-chunk-fits branch
    b.br('<', 'remaining', 'chunk', 'site2', 'site1')

    # ---- SITE1: bf_lbuf.c:143-144, i >= llen branch --------------------------------
    #   memcpy(&(ctx->obuf[ctx->obuf_len]), in, llen); ctx->obuf_len += llen;
    b.label('site1')
    b.assign('to_copy', 'chunk')             # to_copy = llen = chunk  (all of it fits)
    b.add('fill2', 'fill', 'to_copy')        # fill level after this copy
    b.label('chk_site1')
    b.check_bound('fill2', CAP + 1)          # SITE1 write-safety obligation: fill2 <= CAP
    b.const('chunk2', 0)                     # nothing left unbuffered on this path
    b.jmp('merge')

    # ---- SITE2: bf_lbuf.c:148-149, else branch -------------------------------------
    #   memcpy(&(ctx->obuf[ctx->obuf_len]), in, i); ctx->obuf_len += i;
    b.label('site2')
    b.assign('to_copy', 'remaining')         # to_copy = i = remaining  (clamp to space)
    b.add('fill2', 'fill', 'to_copy')        # fill level after this copy (== CAP exactly)
    b.label('chk_site2')
    b.check_bound('fill2', CAP + 1)          # SITE2 write-safety obligation: fill2 <= CAP
    # the leftover, still-unbuffered part of this call's chunk: chunk - to_copy.
    # `remaining <= chunk` holds here BY CONSTRUCTION of the branch just taken (the
    # guard IS the fact, R1(c)'s own "every guard transfers" mechanism) -- injected as
    # an always-on lepair fact (ALWAYS_FACTS['lbl_chunk2']) so the subtraction doesn't
    # spuriously wrap to TOP for a reason unrelated to the R1 question under test.
    b.label('lbl_chunk2')
    b.sub('chunk2', 'chunk', 'remaining')
    b.jmp('merge')

    # ---- merge: bf_lbuf.c:157 (BIO_write, may short-write) then the trailing fallback
    b.label('merge')
    # i = BIO_write(b->next_bio, ctx->obuf, ctx->obuf_len);   -- bf_lbuf.c:157
    # BIO_write's interface contract is 0 <= return <= requested, and the requested
    # amount here is `fill2`, a RUNTIME value -- this IR's `input` opcode only accepts
    # LITERAL bounds, so "returns anything up to fill2" cannot be written as one `input`
    # statement.  It is instead built structurally, with an explicit clamp (the
    # min-of-two-values idiom, done via a branch since this IR has no `min`
    # primitive) so the clamp is enforced in the CONCRETE semantics too, not merely
    # asserted as a fact: an injected fact must be a genuinely true property of the code,
    # never a stand-in for a missing concrete mechanism (the first draft of this model
    # skipped the branch and injected the clamp as a bare fact -- soundness() caught it
    # immediately: drained could concretely exceed fill2, wrapping fill3.  Fixed here.)
    b.inp('drained_raw', 0, CAP)
    b.br('<', 'drained_raw', 'fill2', 'drain_short', 'drain_full')
    b.label('drain_short')                   # BIO_write returned less than requested
    b.assign('drained', 'drained_raw')
    b.jmp('drain_join')
    b.label('drain_full')                    # BIO_write returned >= requested -> clamp to it
    b.assign('drained', 'fill2')
    b.jmp('drain_join')
    b.label('drain_join')
    # `drained <= fill2` now holds BY CONSTRUCTION on both incoming edges (drain_short:
    # drained = drained_raw < fill2; drain_full: drained = fill2 <= fill2) -- the same
    # conditional-variable-splitting mechanism as pattern 15 (examples.py EX15).  Without
    # this lepair fact the subtraction below still WOULD be sound (it would just widen to
    # TOP), but injecting it keeps the model's SITE3 alarm attributable to the genuine
    # chunk-vs-drain mismatch rather than to unrelated interval noise.
    b.label('lbl_merge_drain')
    b.sub('fill3', 'fill2', 'drained')       # ctx->obuf_len -= i;
    # bf_lbuf.c:193-197 -- the vulnerable trailing fallback:
    #   if (inl > 0) { memcpy(&(ctx->obuf[ctx->obuf_len]), in, inl); ctx->obuf_len += inl; }
    # There is NO capacity check in the source here -- that omission IS the CVE.  The
    # check_bound below is the analyzer's synthetic write-safety obligation at that
    # memcpy (same convention used at SITE1/SITE2 and throughout eval/examples.py), not
    # something the C source contains.
    b.add('fill_final', 'fill3', 'chunk2')
    b.label('chk_site3')
    b.check_bound('fill_final', CAP + 1)     # SITE3 -- THE BUG
    b.halt()

    return b.build(note='CVE-2025-68160 linebuffer_write, pre-fix, one buffering pass')


PROG = build_program()

# Structural facts: true by construction of the branch/BIO_write-contract they record;
# present in BOTH configurations.  Neither expresses "fill_level <= capacity" -- that is
# the ONE fact that differs between the two runs below.
ALWAYS_FACTS = {
    'lbl_chunk2': [('lepair', 'remaining', 'chunk')],
    'lbl_merge_drain': [('lepair', 'drained', 'fill2')],
}

# The R1 fold: the cursor-pair invariant `fill_level <= capacity`, expressed with the
# existing `lepair` relational fact (fill2 <= cap) at exactly the two write sites inside
# the loop -- nothing injected at SITE3, matching the fact that the fix does NOT come
# from folding (the source simply lacks the guard there; a fold cannot manufacture one).
FOLD_FACTS = dict(ALWAYS_FACTS)
FOLD_FACTS['chk_site1'] = [('lepair', 'fill2', 'cap')]
FOLD_FACTS['chk_site2'] = [('lepair', 'fill2', 'cap')]

SITES = [
    ('chk_site1', 'SITE1  fill2 <= cap   (bf_lbuf.c:143-144, memcpy, llen)', False),
    ('chk_site2', 'SITE2  fill2 <= cap   (bf_lbuf.c:148-149, memcpy, i)', False),
    ('chk_site3', 'SITE3  fill_final<=cap (bf_lbuf.c:193-197, memcpy, inl -- THE BUG)', True),
]

EXPECT_BASE = {'chk_site1': 'FAIL', 'chk_site2': 'FAIL', 'chk_site3': 'FAIL'}
EXPECT_FOLD = {'chk_site1': 'PROVEN', 'chk_site2': 'PROVEN', 'chk_site3': 'FAIL'}


# =======================================================================================
# Measurement
# =======================================================================================
def measure():
    out = {}
    base = analyze(PROG, ALWAYS_FACTS)
    fold = analyze(PROG, FOLD_FACTS)
    out['base'] = base
    out['fold'] = fold
    out['verdicts'] = {}
    out['widths'] = {}
    for lbl, _title, _isbug in SITES:
        pc = PROG.pt(lbl)
        var = PROG.stmts[pc][1]
        v0 = verdict(PROG, base, pc)
        v1 = verdict(PROG, fold, pc)
        out['verdicts'][lbl] = (v0, v1)
        out['widths'][lbl] = (base.width(pc, var), fold.width(pc, var))
    return out


def self_check(con):
    """Cross-check the IR model against the concrete interpreter: SITE1/SITE2 must have
    ZERO concrete violations (they are genuinely safe -- confirming the baseline's FAIL
    there really is a false positive, not a modeling bug that introduced a real one), and
    SITE3 must have at least one, with a replayable witness."""
    results = {}
    for lbl, _title, _isbug in SITES:
        pc = PROG.pt(lbl)
        viol = [v for (p, v) in con.violations if p == pc]
        results[lbl] = viol
    return results


def find_witness(con, pc):
    for p, vals in con.violations:
        if p == pc:
            return vals
    return None


def fmt_witness(vals):
    idx = {v: i for i, v in enumerate(PROG.vars)}
    d = {v: vals[idx[v]] for v in PROG.vars}
    return d


# =======================================================================================
# Report
# =======================================================================================
def main(argv):
    out_path = None
    if '--out' in argv:
        out_path = argv[argv.index('--out') + 1]

    lines = []

    def p(s=''):
        lines.append(s)

    p('=' * 100)
    p('E1 -- CVE-2025-68160 (linebuffer_write, crypto/bio/bf_lbuf.c) -- folding precision')
    p('reproduce with:  python3 eval/cve/cve_68160.py   (deterministic; no clock, no rand)')
    p('=' * 100)
    p()
    p('Program: %s (%s)' % (PROG.name, PROG.note))
    p('CAP=%d  MAXCHUNK=%d  width=%d bits' % (CAP, MAXCHUNK, WIDTH))
    p()

    m = measure()
    con = Concrete(PROG)
    sc = self_check(con)

    p('TABLE  site, baseline verdict, with-fold verdict, is-it-the-bug, concrete violations')
    p('  %-9s %-58s %-9s %-9s %-6s %-6s' %
      ('site', 'description', 'BASE', 'FOLD', 'bug?', '#conc.viol'))
    p('  ' + '-' * 100)
    failures = []
    for lbl, title, isbug in SITES:
        v0, v1 = m['verdicts'][lbl]
        nviol = len(sc[lbl])
        p('  %-9s %-58s %-9s %-9s %-6s %-6d' %
          (lbl, title[:58], v0, v1, 'YES' if isbug else 'no', nviol))
        if v0 != EXPECT_BASE[lbl]:
            failures.append('%s: baseline verdict %s, expected %s' % (lbl, v0, EXPECT_BASE[lbl]))
        if v1 != EXPECT_FOLD[lbl]:
            failures.append('%s: with-fold verdict %s, expected %s' % (lbl, v1, EXPECT_FOLD[lbl]))
        if not isbug and nviol != 0:
            failures.append('%s: claimed safe but has %d concrete violation(s) -- '
                             'the false-positive claim is WRONG, this is a real bug' %
                             (lbl, nviol))
        if isbug and nviol == 0:
            failures.append('%s: claimed to be the real bug but has ZERO concrete '
                             'violations -- the "true positive" is an artifact' % lbl)
    p()

    p('Interval widths at the check site (base -> fold):')
    for lbl, title, _isbug in SITES:
        w0, w1 = m['widths'][lbl]
        p('  %-9s %-58s width %5d -> %5d' % (lbl, title[:58], w0, w1))
    p()

    p('SELF-CHECK -- concrete witness for the true bug (SITE3):')
    pc3 = PROG.pt('chk_site3')
    w = find_witness(con, pc3)
    if w is not None:
        wd = fmt_witness(w)
        p('  concrete inputs:  fill(entry obuf_len)=%d  chunk(inl)=%d  drained(BIO_write '
          'ret)=%d' % (wd['fill'], wd['chunk'], wd['drained']))
        p('  derived:          remaining=%d  to_copy=%d  fill2=%d  chunk2(leftover)=%d  '
          'fill3=%d  fill_final=%d  (cap=%d)' %
          (wd['remaining'], wd['to_copy'], wd['fill2'], wd['chunk2'], wd['fill3'],
           wd['fill_final'], CAP))
        p('  reading: the buffer starts %d/%d full; this call asks to write %d bytes; the '
          'in-loop clamp correctly fills the buffer to exactly capacity (%d) and leaves '
          '%d bytes not yet buffered; BIO_write to the next filter returns %d (a short '
          'write, RFC-legal); the trailing fallback then unconditionally appends the '
          'leftover %d bytes starting at offset %d, landing at fill_final=%d > cap=%d -- '
          'the real CVE-2025-68160 overflow, reproduced as a concrete violating execution '
          'in this model.' %
          (wd['fill'], CAP, wd['chunk'], wd['fill2'], wd['chunk2'], wd['drained'],
           wd['chunk2'], wd['fill3'], wd['fill_final'], CAP))
    else:
        failures.append('SITE3: no concrete witness found by the exhaustive interpreter')
        p('  NONE FOUND -- see HARNESS FAILURES below.')
    p()

    p('Concrete state-space size: %d reachable-pc buckets, budget exhausted=%s' %
      (len(con.reach), con.exhausted))
    p()

    p('SOUNDNESS -- does the with-fold abstract state still CONTAIN every concretely '
      'reachable valuation at every program point? (the critical check: did the R1 fact '
      'injection introduce unsoundness, or is it a valid consequence of the code)')
    bad_base = soundness(PROG, m['base'], con)
    bad_fold = soundness(PROG, m['fold'], con)
    p('  baseline soundness violations:  %d' % len(bad_base))
    p('  with-fold soundness violations: %d' % len(bad_fold))
    if bad_base:
        failures.append('BASELINE is unsound: %s' % str(bad_base[0]))
    if bad_fold:
        failures.append('WITH-FOLD is unsound -- the R1 fact as injected is INVALID: %s'
                         % str(bad_fold[0]))
    p()

    n_fp_base = sum(1 for lbl, _t, isbug in SITES if not isbug and m['verdicts'][lbl][0] == 'FAIL')
    n_fp_fold = sum(1 for lbl, _t, isbug in SITES if not isbug and m['verdicts'][lbl][1] == 'FAIL')
    true_alarm_base = m['verdicts']['chk_site3'][0] == 'FAIL'
    true_alarm_fold = m['verdicts']['chk_site3'][1] == 'FAIL'
    p('HEADLINE')
    p('  baseline false positives (safe sites alarming):   %d/2' % n_fp_base)
    p('  with-fold false positives (safe sites alarming):  %d/2' % n_fp_fold)
    p('  true alarm (SITE3) present in baseline:            %s' % true_alarm_base)
    p('  true alarm (SITE3) survives the fold:              %s' % true_alarm_fold)
    if n_fp_base > 0 and n_fp_fold == 0 and true_alarm_base and true_alarm_fold:
        p('  => POSITIVE RESULT: the fold silences every false positive in the loop while')
        p('     the true alarm at the real CVE-2025-68160 site is unaffected -- the')
        p('     precision thesis, measured on real (pre-fix, source-cited) CVE code.')
    elif n_fp_base == n_fp_fold:
        p('  => NULL RESULT: the fold changed nothing measurable here.')
    p()

    if failures:
        p('HARNESS FAILURES')
        for f in failures:
            p('  * ' + f)
        p()
    else:
        p('All harness expectations hold.')
        p()

    text = '\n'.join(lines) + '\n'
    sys.stdout.write(text)
    if out_path:
        with open(out_path, 'w') as fh:
            fh.write(text)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
