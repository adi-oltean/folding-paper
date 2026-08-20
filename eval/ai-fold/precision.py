"""precision.py -- experiment E0, the PRECISION leg.

Expresses the original form and the proposed twin form of each E0 case in the reference
mini-IR and runs `eval/refanalyzer.py` UNCHANGED (imported as-is; nothing in it is extended,
subclassed, monkey-patched, or re-implemented here).  No facts are injected anywhere: the
whole point of AI-driven folding is that the TWIN must be provable by the PLAIN analysis,
with the folded information carried by the program form instead of by an injected fact.
Input ranges are therefore encoded with the IR's own `input` construct, never with facts.

Everything below is measurement.  Where the original turns out to PROVE a check the memo
predicted it would FAIL, that is reported as-is; the baseline is never weakened to make a
twin look better.

--------------------------------------------------------------------------------------
LOWERING (read this before reading any verdict)
--------------------------------------------------------------------------------------
The IR has both bitwise opcodes (`and`/`or`/`xor`, which go to TOP -- refanalyzer's
documented imprecision F1) and exact `modc`/`shrc`/`shlc` for division-like operations by a
constant.  A C front end must therefore choose how to lower `x & 0xffff`.  Both choices are
sound and both are defensible, and the choice materially moves case 1, so BOTH are run:

  lowering B ("bitwise-opaque"):  every C `&`, `|`, `^`, `~` lowers to the IR's bitwise
      opcode.  This is the strictest reading of "textbook interval domain".
  lowering M ("mask-as-modulus"): a C mask `x & (2^n - 1)` on an unsigned operand lowers to
      `modc x, 2^n`, because on unsigned values that mask IS modular reduction -- a
      syntactic, always-valid front-end rule.  Every other bitwise operator (including `|`,
      `^`, `~`, and `&` with a non-mask or non-constant operand) still lowers to the bitwise
      opcode.  In particular `~x` does NOT become `2^n - 1 - x`: that identity needs the
      range precondition x < 2^n, so it is not a syntactic lowering.

The two lowerings have IDENTICAL concrete semantics -- they differ only in which abstract
transfer function the front end selects -- and each is applied identically to the original
and to the twin of a case.  Casts (`(unsigned short)x`) are a language-level truncation, not
a bitwise operator, and lower to `modc` under both.

Run:  python3 precision.py        (writes out/precision.json, prints a report)
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, '..')))

from refanalyzer import Builder, Concrete, analyze, verdict   # noqa: E402  (path first)

W32 = 32
W16 = 16
OUT = os.path.join(_HERE, 'out')


# =======================================================================================
# helpers
# =======================================================================================
def mask_lower(b, d, s, bits, lowering):
    """Lower the C expression `s & ((1<<bits)-1)` for an unsigned operand."""
    if lowering == 'M':
        b.modc(d, s, 1 << bits)
    else:
        b.band(d, s, (1 << bits) - 1)


def cast_lower(b, d, s, bits):
    """Lower a C conversion to the unsigned type of `bits` bits (truncation, not a mask)."""
    b.modc(d, s, 1 << bits)


def check(prog, res, label, var):
    pc = prog.pt(label)
    iv = res.iv(pc, var)
    return {'verdict': verdict(prog, res, pc),
            'interval': None if iv is None else [iv[0], iv[1]],
            'var': var}


def pairs_at(prog, con, label, invar, outvar):
    pc = prog.pt(label)
    ai, bi = prog.vars.index(invar), prog.vars.index(outvar)
    return set((t[ai], t[bi]) for t in con.reach.get(pc, ()))


# =======================================================================================
# CASE 1 -- csum_from32to16
# =======================================================================================
# original (checksum.h:142-146):
#     sum += (sum >> 16) | (sum << 16);
#     return (unsigned short)(sum >> 16);
#
# The value the `return` casts is the analogue, in each form, of "the result": `rp` in the
# original, `r` in the twin.  Both are checked, plus the post-cast return value.
def c1_orig(lo=0, hi=0xFFFFFFFF, name='case1-orig'):
    b = Builder(name, W32)
    b.inp('sum', lo, hi)
    b.shr('hi', 'sum', 16)          # sum >> 16
    b.shl('sl', 'sum', 16)          # sum << 16      (uint32; shlc truncates on write)
    b.bor('c', 'hi', 'sl')          # |              (bitwise in BOTH lowerings)
    b.add('s2', 'sum', 'c')         # sum += ...     (wraps)
    b.shr('rp', 's2', 16)           # sum >> 16      <- the value the return casts
    cast_lower(b, 'res', 'rp', 16)  # (unsigned short)
    b.label('chk_10000'); b.check_range('rp', 0, 0x10000)
    b.label('chk_ffff'); b.check_range('rp', 0, 0xFFFF)
    b.label('chk_ret'); b.check_range('res', 0, 0xFFFF)
    b.halt()
    return b.build()


def c1_twin(lowering, lo=0, hi=0xFFFFFFFF, name=None):
    b = Builder(name or ('case1-twin-' + lowering), W32)
    b.inp('sum', lo, hi)
    mask_lower(b, 'lo', 'sum', 16, lowering)   # sum & 0xffffu
    b.shr('hi', 'sum', 16)
    b.add('t', 'lo', 'hi')
    mask_lower(b, 'tl', 't', 16, lowering)     # t & 0xffffu
    b.shr('th', 't', 16)
    b.add('r', 'tl', 'th')                     # <- the value the return casts
    cast_lower(b, 'res', 'r', 16)              # (unsigned short)
    b.label('chk_10000'); b.check_range('r', 0, 0x10000)
    b.label('chk_ffff'); b.check_range('r', 0, 0xFFFF)
    b.label('chk_ret'); b.check_range('res', 0, 0xFFFF)
    b.halt()
    return b.build()


def py_c1_orig(x):
    m = 0xFFFFFFFF
    s = (x + (((x >> 16) | ((x << 16) & m)) & m)) & m
    return (s >> 16) & 0xFFFF


def py_c1_twin(x):
    t = (x & 0xFFFF) + (x >> 16)
    r = (t & 0xFFFF) + (t >> 16)
    return r & 0xFFFF


# =======================================================================================
# CASE 2 -- nanopb ZigZag
# =======================================================================================
# The analog has width n; `value` is a signed n-bit integer, held in the IR as its unsigned
# two's-complement bit pattern v in [0, 2^n).  The IR itself is 32 bits wide so that the
# n-bit truncations are explicit (`modc 2^n`) and the check `result < 2^(k+1)` is not
# vacuously satisfied by the declared width.
#
# Input-range encoding, NO facts:  `value in [-2^k, 2^k)` is two intervals of bit patterns,
# [0, 2^k) and [2^n - 2^k, 2^n), and the IR's `input` yields one interval.  So the entry has
# two `input` sites, each followed by ITS OWN copy of the source's `if (value < 0)` test.
# The two function bodies are shared and verbatim.  This is a splitting of the entry, not of
# the function; it is applied identically to the original and to the twin.
def c2(form, n, k, lowering, name=None):
    N = 1 << n
    half = N >> 1
    smask_bits = n - 1                     # ((T)-1) >> 1 is the low n-1 bits
    b = Builder(name or ('case2-%s-n%d-k%d-%s' % (form, n, k, lowering)), W32)

    b.inp('sel', 0, 1)
    b.br('==', 'sel', 0, 'pin', 'nin')
    b.label('pin')
    b.inp('v', 0, (1 << k) - 1)            # value in [0, 2^k)
    b.br('<', 'v', half, 'nonneg', 'neg')  # if (value < 0)
    b.label('nin')
    b.inp('v', N - (1 << k), N - 1)        # value in [-2^k, 0)
    b.br('<', 'v', half, 'nonneg', 'neg')  # if (value < 0)   -- same test, duplicated entry

    b.label('nonneg')
    if form == 'orig':
        b.shl('z0', 'v', 1)                # (T_unsigned)value << 1
    else:
        b.mul('z0', 'v', 2)                # 2*(T_unsigned)value
    cast_lower(b, 'z', 'z0', n)
    b.jmp('end')

    b.label('neg')
    if form == 'orig':
        mask_lower(b, 'm', 'v', smask_bits, lowering)   # (T_unsigned)value & mask
        b.shl('m1', 'm', 1)                             # << 1
        cast_lower(b, 'm2', 'm1', n)
        b.bxor('zz', 'm2', N - 1)                       # ~   (bitwise in BOTH lowerings)
        cast_lower(b, 'z', 'zz', n)
    else:
        b.sub('w', N - 1, 'v')                          # (T_unsigned)(-(value + 1))
        cast_lower(b, 'w', 'w', n)
        b.mul('z0', 'w', 2)
        b.add('z0', 'z0', 1)                            # 2*... + 1
        cast_lower(b, 'z', 'z0', n)
    b.jmp('end')

    b.label('end')
    b.label('chk'); b.check_range('z', 0, (1 << (k + 1)) - 1)
    b.halt()
    return b.build()


def py_c2_orig(v, n):
    N = 1 << n
    smask = (N - 1) >> 1
    if v >= (N >> 1):
        return (~(((v & smask) << 1) & (N - 1))) & (N - 1)
    return (v << 1) & (N - 1)


def py_c2_twin(v, n):
    N = 1 << n
    if v >= (N >> 1):
        return (2 * ((N - 1 - v) & (N - 1)) + 1) & (N - 1)
    return (2 * v) & (N - 1)


# =======================================================================================
# CASE 3 -- _find_first_bit
# =======================================================================================
# Configuration for the IR run: BITS = 4 bits per word, size = 16 (so 4 words).  Memory is
# not modelled, so each word fetch `addr[idx]` is a fresh nondeterministic `input` over the
# whole word range, and `__ffs(val)` of a nonzero BITS-bit word is a fresh nondeterministic
# `input` over [0, BITS-1] -- both over-approximations, and both GENEROUS to the original
# (the analysis is handed __ffs's range for free).
def c3_orig(size=16, bits=4, name='case3-orig'):
    b = Builder(name, W16)
    b.const('sz', size)
    b.const('idx', 0)
    b.label('head')
    b.mul('t', 'idx', bits)                       # idx * BITS_PER_LONG
    b.br('<', 't', 'sz', 'body', 'out')
    b.label('body')
    b.inp('val', 0, (1 << bits) - 1)              # val = addr[idx]
    b.br('!=', 'val', 0, 'found', 'cont')
    b.label('cont')
    b.add('idx', 'idx', 1)
    b.jmp('head')
    b.label('found')
    b.inp('bp', 0, bits - 1)                      # __ffs(val), val != 0
    b.mul('u', 'idx', bits)
    b.add('c', 'u', 'bp')                         # idx * BITS_PER_LONG + __ffs(val)
    b.label('chk_pre'); b.check_bound('c', size + 1)   # diagnostic: the PRE-min composition
    b.br('<', 'c', 'sz', 'takec', 'takesz')       # min(c, sz)
    b.label('takec'); b.assign('ret', 'c'); b.jmp('done')
    b.label('takesz'); b.assign('ret', 'sz'); b.jmp('done')
    b.label('out'); b.assign('ret', 'sz'); b.jmp('done')
    b.label('done')
    b.label('chk'); b.check_bound('ret', size + 1)     # retval <= size
    b.halt()
    return b.build()


def c3_twin(size=16, name='case3-twin'):
    b = Builder(name, W16)
    b.const('sz', size)
    b.const('k', 0)
    b.label('head')
    b.br('<', 'k', 'sz', 'body', 'out')
    b.label('body')
    b.inp('bit', 0, 1)                            # (addr[k/BITS] >> (k%BITS)) & 1
    b.br('!=', 'bit', 0, 'found', 'cont')
    b.label('cont')
    b.add('k', 'k', 1)
    b.jmp('head')
    b.label('found'); b.assign('ret', 'k'); b.jmp('done')
    b.label('out'); b.assign('ret', 'sz'); b.jmp('done')
    b.label('done')
    b.label('chk'); b.check_bound('ret', size + 1)
    b.halt()
    return b.build()


# =======================================================================================
# self-tests: the IR transliterations must agree with the C semantics
# =======================================================================================
def selftests():
    """Concrete-semantics cross-checks of the IR encodings against Python models of the C.

    These validate the TRANSLITERATION (the thing a reader must trust about this file); the
    equivalence proofs themselves are the compiled C drivers, not these.
    """
    out = []

    # -- case 1: three input windows, both forms, both lowerings --------------------------
    for (lo, hi, tag) in ((0, 4095, 'low'),
                          (0x0001FE00, 0x00020200, 'fold-carry'),
                          (0xFFFFF000, 0xFFFFFFFF, 'high')):
        p = c1_orig(lo, hi, 'c1-orig-st-' + tag)
        con = Concrete(p, trace=False)
        got = pairs_at(p, con, 'chk_ret', 'sum', 'res')
        exp = set((x, py_c1_orig(x)) for x in range(lo, hi + 1))
        out.append(('case1 orig IR == C, window ' + tag, got == exp and not con.exhausted,
                    len(exp)))
        for lw in ('B', 'M'):
            p = c1_twin(lw, lo, hi, 'c1-twin-%s-st-%s' % (lw, tag))
            con = Concrete(p, trace=False)
            got = pairs_at(p, con, 'chk_ret', 'sum', 'res')
            exp = set((x, py_c1_twin(x)) for x in range(lo, hi + 1))
            out.append(('case1 twin(%s) IR == C, window %s' % (lw, tag),
                        got == exp and not con.exhausted, len(exp)))
        # and, at these windows, orig == twin concretely
        out.append(('case1 orig == twin on window ' + tag,
                    all(py_c1_orig(x) == py_c1_twin(x) for x in range(lo, hi + 1)),
                    hi - lo + 1))

    # -- case 2: 8-bit analog, k = 6 (small enough for complete concrete enumeration) -----
    n, k = 8, 6
    dom = list(range(0, 1 << k)) + list(range((1 << n) - (1 << k), 1 << n))
    for form, pymodel in (('orig', py_c2_orig), ('twin', py_c2_twin)):
        for lw in ('B', 'M'):
            p = c2(form, n, k, lw, 'c2-%s-%s-st' % (form, lw))
            con = Concrete(p, trace=False)
            got = pairs_at(p, con, 'chk', 'v', 'z')
            exp = set((v, pymodel(v, n)) for v in dom)
            out.append(('case2 %s(%s) IR == C at n=%d,k=%d' % (form, lw, n, k),
                        got == exp and not con.exhausted, len(exp)))
    out.append(('case2 orig == twin on the full 8-bit domain',
                all(py_c2_orig(v, 8) == py_c2_twin(v, 8) for v in range(256)), 256))

    # -- case 3: complete concrete enumeration of the IR models ---------------------------
    for p in (c3_orig(), c3_twin()):
        con = Concrete(p, trace=False)
        i = p.vars.index('ret')
        rets = set(t[i] for t in con.reach.get(p.pt('chk'), ()))
        out.append(('case3 %s: concrete ret set == {0..16}' % p.name,
                    rets == set(range(17)) and not con.exhausted, len(rets)))
        out.append(('case3 %s: no concrete check violation' % p.name,
                    len(con.violations) == 0, len(con.violations)))
    return out


# =======================================================================================
# main
# =======================================================================================
def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    report = {'cases': {}, 'selftests': [], 'no_facts_injected': True}

    print('=' * 88)
    print('E0 precision leg -- eval/refanalyzer.py imported unchanged, NO injected facts')
    print('=' * 88)

    # ---- self-tests --------------------------------------------------------------------
    print('\n[self-tests: IR transliteration vs. the C semantics]')
    ok_all = True
    for (nm, ok, cnt) in selftests():
        ok_all = ok_all and bool(ok)
        report['selftests'].append({'name': nm, 'ok': bool(ok), 'n': cnt})
        print('  %-58s %-4s  (%d)' % (nm, 'ok' if ok else 'FAIL', cnt))
    report['selftests_all_ok'] = ok_all

    # ---- case 1 ------------------------------------------------------------------------
    print('\n[case 1 -- csum_from32to16, IR width 32, input = all 2^32]')
    c1 = {}
    forms = [('orig', c1_orig(), 'rp'),
             ('twin-B', c1_twin('B'), 'r'),
             ('twin-M', c1_twin('M'), 'r')]
    for tag, prog, resvar in forms:
        res = analyze(prog)
        c1[tag] = {'chk_10000': check(prog, res, 'chk_10000', resvar),
                   'chk_ffff': check(prog, res, 'chk_ffff', resvar),
                   'chk_ret': check(prog, res, 'chk_ret', 'res'),
                   'converged': res.converged}
        for cn in ('chk_10000', 'chk_ffff', 'chk_ret'):
            e = c1[tag][cn]
            print('  %-8s %-10s %-7s  %s = %s'
                  % (tag, cn, e['verdict'], e['var'], e['interval']))
    report['cases']['case1'] = c1

    # ---- case 2 ------------------------------------------------------------------------
    print('\n[case 2 -- nanopb ZigZag, IR width 32, analog width n, value in [-2^k, 2^k)]')
    c2r = {}
    for (n, k) in ((16, 15), (16, 14), (16, 13), (8, 7), (8, 6)):
        key = 'n%d-k%d' % (n, k)
        c2r[key] = {'n': n, 'k': k, 'bound': (1 << (k + 1)) - 1,
                    'vacuous': (k + 1 >= n)}
        for form in ('orig', 'twin'):
            for lw in ('B', 'M'):
                prog = c2(form, n, k, lw)
                res = analyze(prog)
                e = check(prog, res, 'chk', 'z')
                c2r[key]['%s-%s' % (form, lw)] = e
                print('  n=%2d k=%2d %-4s %-3s  %-7s  z = %-14s  bound z <= %d%s'
                      % (n, k, form, lw, e['verdict'], e['interval'],
                         (1 << (k + 1)) - 1, '   [VACUOUS: k+1 == n]'
                         if k + 1 >= n else ''))
    report['cases']['case2'] = c2r

    # ---- case 3 ------------------------------------------------------------------------
    print('\n[case 3 -- _find_first_bit, IR width 16, BITS=4, size=16]')
    c3 = {}
    po, pt = c3_orig(), c3_twin()
    ro, rt = analyze(po), analyze(pt)
    c3['orig'] = {'chk': check(po, ro, 'chk', 'ret'),
                  'chk_pre': check(po, ro, 'chk_pre', 'c'),
                  'converged': ro.converged}
    c3['twin'] = {'chk': check(pt, rt, 'chk', 'ret'), 'converged': rt.converged}
    print('  orig  chk      %-7s  ret = %s' % (c3['orig']['chk']['verdict'],
                                               c3['orig']['chk']['interval']))
    print('  orig  chk_pre  %-7s  c   = %s   (idx*BITS + __ffs, BEFORE the kernel min())'
          % (c3['orig']['chk_pre']['verdict'], c3['orig']['chk_pre']['interval']))
    print('  twin  chk      %-7s  ret = %s' % (c3['twin']['chk']['verdict'],
                                               c3['twin']['chk']['interval']))
    report['cases']['case3'] = c3

    with open(os.path.join(OUT, 'precision.json'), 'w') as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    print('\nwrote out/precision.json')
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
