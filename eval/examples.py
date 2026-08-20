"""examples.py -- the canonical micro-suite: one program per catalogue pattern (1..16).

Each example carries, verbatim from the paper:
  * the fact the pattern supplies,
  * the pattern's VALIDITY CONDITION (quoted), and why it holds for this program,
  * a MUTANT whose check is genuinely unsafe (a concrete violating execution exists),
    analysed with THE SAME fact injected.

A note on how the mutants are built.  Every mutant here breaks the *check*, never the
*validity condition* of the injected fact: the fact stays valid in the mutant, so injecting
it stays sound, and the mutant tests exactly what the design asks -- that the fold buys no
free lunch, i.e. an unsafe check is still not proven.  Breaking the validity condition
instead is a different experiment: it makes the fact invalid, and injecting an invalid fact
is unsound by construction (the paper's subtractive-failure direction).  That experiment is
run separately, as the validity probes at the bottom of this file, and is reported in its
own table -- it is not counted in the mutant-flip rate.

Approximation notes ("approx=") mark every place where the fact this analyzer can express is
weaker than the fact the paper describes (KnownBits, residue classes, bit-sets).  They are
reprinted as footnotes by run.py.  Nothing here claims a stronger result than it measures.
"""

from fractions import Fraction

from refanalyzer import Builder

W32, W16, W8 = 32, 16, 8


class Ex:
    def __init__(self, num, axis, title, prog, mutant, facts, quote, why,
                 approx=None, mut_note=''):
        self.num, self.axis, self.title = num, axis, title
        self.prog, self.mutant, self.facts = prog, mutant, facts
        self.quote, self.why, self.approx, self.mut_note = quote, why, approx, mut_note


# =======================================================================================
# Pattern 1 -- affine induction variable (time)
# =======================================================================================
def _p1(name, s, N, bound):
    b = Builder(name, W32)
    b.const('i', 0)
    b.label('head'); b.br('<', 'i', N, 'body', 'end')
    b.label('body')
    b.add('t', 'i', 1)                    # a[i+1]
    b.label('chk'); b.check_bound('t', bound)
    b.add('i', 'i', s)
    b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


def _p1_actual_max(c0, L, s):
    return c0 + s * (-(-(L - c0) // s)) - s        # ceil division, the paper's formula


EX1 = Ex(
    1, 'time', 'affine IV (i += 2, a[i+1], len 20)',
    _p1('p1', 2, 20, 20), _p1('p1-mut', 2, 20, 19),
    {'body': [('le', 'i', _p1_actual_max(0, 20, 2))]},
    "i is not modified in the body other than by the loop increment, its address is not "
    "taken, and the increment does not wrap at the operand's type "
    "(actual_max + s representable).",
    "i is written only by `i += 2`; there is no aliasing in this IR; actual_max + s = 20 "
    "< 2^32.  actual_max = c0 + s*ceil((L-c0)/s) - s = 0 + 2*10 - 2 = 18, so a[i+1] "
    "touches at most a[19].",
    mut_note='array length 20 -> 19; a[19] is then out of bounds.')

# =======================================================================================
# Pattern 2 -- while-!= induction variable (time)
# =======================================================================================
def _p2(name, s, N, bound):
    b = Builder(name, W32)
    b.const('i', 0)
    b.label('head'); b.br('!=', 'i', N, 'body', 'end')
    b.label('body'); b.label('chk'); b.check_bound('i', bound)
    b.add('i', 'i', s)
    b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


EX2 = Ex(
    2, 'time', 'while-!= IV (i != 20, i += 4)',
    _p2('p2', 4, 20, 20), _p2('p2-mut', 4, 20, 16),
    {'body': [('le', 'i', 16)]},
    "a single increment site, no other writes, no address-taking, divisibility of N - c0 "
    "by the stride, and c0 <= N.",
    "i is written only by `i += 4`; 20 - 0 = 5*4 is divisible by the stride; 0 <= 20.  The "
    "iterates are 0,4,8,12,16 and the guard is never stepped over, so the last body-entry "
    "value is m = N - s = 16 (the '!=' bracket of the paper's symbolic-bound checker: "
    "m + s = L).",
    mut_note='array length 20 -> 16; i = 16 is then out of bounds.')

# =======================================================================================
# Pattern 3 -- geometric induction variable (time)
# =======================================================================================
def _p3(name, w, bound):
    b = Builder(name, w)
    b.const('m', 1)
    b.const('t', 0)
    b.label('head'); b.br('!=', 'm', 0, 'body', 'end')
    b.label('body'); b.label('chk'); b.check_shift('t', bound)
    b.shl('m', 'm', 1)                    # truncates back to the declared width
    b.add('t', 't', 1)
    b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


def _p3_facts(w):
    return {'body': [('le', 't', w - 1),
                     ('set', 'm', tuple(1 << e for e in range(w)))]}


EX3 = Ex(
    3, 'time', 'geometric IV (uint8: m = 1; m; m <<= 1)',
    _p3('p3', 8, 8), _p3('p3-mut', 8, 7), _p3_facts(8),
    "m is modified only by the one shift or multiply, and the operand is unsigned; for "
    "loops that terminate by shifting the bit out, the termination argument is a width "
    "fact at the operand's DECLARED type.",
    "m is written only by `m <<= 1` on an unsigned 8-bit operand; the assignment truncates "
    "back to uint8, so the loop runs exactly 8 times and the exponent t lies in [0,7]. "
    "The single-set-bit fact is m in {1,2,...,128}.",
    mut_note='shift width 8 -> 7; t = 7 is then an inadmissible shift.')

# =======================================================================================
# Pattern 4 -- polynomial accumulator (time)
# =======================================================================================
def _p4(name, T, hi):
    b = Builder(name, W32)
    b.const('i', 0)
    b.const('s', 0)
    b.label('head'); b.br('<', 'i', T, 'body', 'end')
    b.label('body')
    b.add('s', 's', 'i')
    b.add('i', 'i', 1)
    b.jmp('head')
    b.label('end'); b.label('chk'); b.check_range('s', 0, hi)
    b.halt()
    return b.build()


EX4 = Ex(
    4, 'time', 'polynomial accumulator (s += i, 16 iters)',
    _p4('p4', 16, 120), _p4('p4-mut', 16, 119),
    {'end': [('le', 's', 120)]},
    "the accumulator is written only by the recognized update, and the bound is evaluated "
    "at the folded trip count.",
    "s is written only by `s += i`; the trip count is the folded 16, and the triangular "
    "closed form t(t-1)/2 = 16*15/2 = 120 bounds s at exit.",
    mut_note='accumulator bound 120 -> 119; s reaches exactly 120.')

# =======================================================================================
# Pattern 5 -- struct field factoring (space)
# =======================================================================================
def _p5(name, n, Z, off, g, bound):
    b = Builder(name, W32)
    b.const('p', 0)
    b.label('head'); b.br('<', 'p', n * Z, 'body', 'end')
    b.label('body')
    b.add('q', 'p', off)                  # &a[e].f
    b.add('q', 'q', g - 1)                # last byte of the field
    b.label('chk'); b.check_bound('q', bound)
    b.add('p', 'p', Z)
    b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


EX5 = Ex(
    5, 'space', 'struct field factoring (4 x 8B, field at +4)',
    _p5('p5', 4, 8, 4, 4, 32), _p5('p5-mut', 4, 8, 4, 4, 31),
    {'body': [('le', 'p', 24)]},
    "the accessed object's declared element type matches the factored size.",
    "the cursor p walks the declared 8-byte element stride of a 4-element array, so it is "
    "element-aligned and p <= (n-1)*Z = 24; factoring the access into element index, "
    "element size and field offset checks the index against the element count rather than "
    "the byte extent, giving q = p + 4 + 3 <= 31.",
    mut_note='byte extent 32 -> 31; the last field byte is exactly 31.')

# =======================================================================================
# Pattern 6 -- stride-union convexification (space)
# =======================================================================================
def _p6(name, n, Z, k, g, bound):
    offs = tuple(j * g for j in range(k))
    b = Builder(name, W32)
    b.const('p', 0)
    b.label('outer'); b.br('<', 'p', n * Z, 'obody', 'end')
    b.label('obody'); b.const('off', 0)
    b.label('inner'); b.br('<', 'off', k * g, 'ibody', 'next')
    b.label('ibody')
    b.add('abase', 'p', 'off')
    b.add('a', 'abase', g - 1)
    b.label('chk'); b.check_bound('a', bound)
    b.add('off', 'off', g)
    b.jmp('inner')
    b.label('next'); b.add('p', 'p', Z)
    b.jmp('outer')
    b.label('end'); b.halt()
    return b.build(), offs


_P6 = _p6('p6', 3, 16, 3, 4, 48)
_P6M = _p6('p6-mut', 3, 16, 3, 4, 43)

EX6 = Ex(
    6, 'space', 'stride-union convexification (3x16B, f 0/4/8)',
    _P6[0], _P6M[0],
    {'ibody': [('le', 'p', 32), ('set', 'off', (0, 4, 8))]},
    "the offsets and stride are those of the declared layout, and every access in the "
    "folded region goes through the recognized index expressions.",
    "the three offsets {0,4,8} and the 16-byte stride are the declared layout; every "
    "access in the loop is p + off + (g-1).  Dividing the offsets by their gcd 4 maps "
    "{0,4,8} to the convex {0,1,2}, i.e. off in {0,4,8}; with p element-aligned "
    "(p <= (n-1)*Z = 32) the touched address is at most 32 + 8 + 3 = 43.",
    mut_note='byte extent 48 -> 43; the last touched byte is exactly 43.')

# =======================================================================================
# Pattern 7 -- residue partition (space)
# =======================================================================================
def _p7(name, N, bound):
    b = Builder(name, W32)
    b.const('j', 0)
    b.const('ph', 0)
    b.label('head'); b.br('<', 'j', 2 * N, 'body', 'end')
    b.label('body'); b.br('==', 'ph', 0, 'even', 'odd')
    b.label('even')
    b.add('t', 'j', 1)                    # the paired odd slot buf[j+1]
    b.label('chk'); b.check_bound('t', bound)
    b.const('ph', 1)
    b.add('j', 'j', 1)
    b.jmp('head')
    b.label('odd'); b.const('ph', 0)
    b.add('j', 'j', 1)
    b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


EX7 = Ex(
    7, 'space', 'residue partition (pair buf[j], buf[j+1])',
    _p7('p7', 8, 16), _p7('p7-mut', 8, 15),
    {'even': [('set', 'j', tuple(range(0, 16, 2)))]},
    "every access to the region is through an index expression with a recognized residue.",
    "the cursor j advances by one with an alternating phase, and the pair access happens "
    "only on the even phase; the per-phase fact for that phase is j == 0 (mod 2), which "
    "over the guarded range [0,16) is exactly j in {0,2,...,14}, so buf[j+1] touches at "
    "most index 15.",
    mut_note='buffer length 16 -> 15; index 15 is then out of bounds.')

# =======================================================================================
# Pattern 8 -- bitfield decomposition (value)
# =======================================================================================
def _p8(name, bound):
    b = Builder(name, W16)
    b.inp('a', 0, 15)                     # 4-bit field
    b.inp('bb', 0, 255)                   # 8-bit field
    b.shl('h', 'a', 8)
    b.bor('h', 'h', 'bb')
    b.label('chk'); b.check_bound('h', bound)
    b.halt()
    return b.build()


EX8 = Ex(
    8, 'value', 'bitfield decomposition (h = (a4<<8)|b8)',
    _p8('p8', 4096), _p8('p8-mut', 4095),
    {'chk': [('le', 'h', 4095)]},
    "the declared field widths.",
    "the declared widths are 4 and 8 bits packed at offsets 8 and 0, so bits 12..15 of h "
    "are known zero.",
    approx="KnownBits approximated: the fact is the known-zero mask h & 0xF000 == 0; it is "
           "injected as its interval consequence h <= 0x0FFF, which is exact here because "
           "the known-zero bits are the top bits.",
    mut_note='table size 4096 -> 4095; h = 4095 is reachable.')

# =======================================================================================
# Pattern 9 -- modular arithmetic (value)
# =======================================================================================
def _p9(name, bound):
    b = Builder(name, W16)
    b.inp('x', 0, 255)
    b.divc('q', 'x', 16)
    b.mul('u', 'q', 16)
    b.sub('r', 'x', 'u')                  # r = x - 16*(x/16)
    b.label('chk'); b.check_bound('r', bound)
    b.halt()
    return b.build()


EX9 = Ex(
    9, 'value', 'modular arithmetic (r = x - 16*(x/16))',
    _p9('p9', 16), _p9('p9-mut', 15),
    {'chk': [('in', 'r', 0, 15)]},
    "the sign convention of C's truncating division.",
    "x is unsigned, so C's truncating division gives the Euclidean pair: x = 16*q + r with "
    "0 <= r < 16.  The interval domain loses this because x - 16*q is a difference of two "
    "independently-bounded quantities.",
    mut_note='table size 16 -> 15; r = 15 is reachable.')

# =======================================================================================
# Pattern 10 -- bit-slice range (value)
# =======================================================================================
def _p10(name, bound):
    b = Builder(name, W16)
    b.inp('x', 0, 4095)
    b.shr('t', 'x', 4)
    b.band('t', 't', 63)
    b.label('chk'); b.check_bound('t', bound)
    b.halt()
    return b.build()


EX10 = Ex(
    10, 'value', 'bit-slice range (t = (x >> 4) & 0x3F)',
    _p10('p10', 64), _p10('p10-mut', 63),
    {'chk': [('in', 't', 0, 63)]},
    "the expression shape alone.",
    "the expression is literally (x >> k) & m with a non-negative literal mask m = 63, so "
    "the slice lies in [0, m] for any operand -- no condition on x is needed.",
    mut_note='table size 64 -> 63; t = 63 is reachable.')

# =======================================================================================
# Pattern 11 -- monotone mask accumulation (value)
# =======================================================================================
def _p11(name, bound):
    b = Builder(name, W16)
    b.const('f', 0)
    b.const('bit', 1)
    b.const('i', 0)
    b.label('head'); b.br('<', 'i', 4, 'body', 'end')
    b.label('body')
    b.bor('f', 'f', 'bit')
    b.shl('bit', 'bit', 1)
    b.add('i', 'i', 1)
    b.jmp('head')
    b.label('end'); b.label('chk'); b.check_bound('f', bound)
    b.halt()
    return b.build()


EX11 = Ex(
    11, 'value', 'monotone mask accumulation (f |= bit)',
    _p11('p11', 16), _p11('p11-mut', 15),
    {'end': [('le', 'f', 15)]},
    "all writes are recognized accumulations.",
    "f is written only by `f |= bit`, so it grows monotonically within the set of bits ever "
    "supplied; the supplied bits are 1,2,4,8, so f's bit set is a subset of the low four.",
    approx="bit-set approximated: the fact is the grown-only bit set {0,1,2,3}; it is "
           "injected as its interval consequence f <= 15, exact because the supplied bits "
           "are the low four.",
    mut_note='table size 16 -> 15; f = 15 is reachable.')

# =======================================================================================
# Pattern 12 -- two-sided clamp (value)
# =======================================================================================
def _p12(name, lo, hi, chk_hi):
    b = Builder(name, W16)
    b.inp('v', 0, 1000)
    b.sub('d', 'v', lo)                   # (unsigned)(v - LO) <= (HI - LO): the branchless
    b.br('<=', 'd', hi - lo, 'inr', 'cl')  # two-sided range test, wraps for v < LO
    b.label('inr'); b.assign('x', 'v'); b.jmp('use')
    b.label('cl'); b.const('x', lo)
    b.label('use'); b.label('chk'); b.check_range('x', lo, chk_hi)
    b.halt()
    return b.build()


EX12 = Ex(
    12, 'value', 'two-sided clamp ((unsigned)(v-100) <= 100)',
    _p12('p12', 100, 200, 200), _p12('p12-mut', 100, 200, 199),
    {'use': [('in', 'x', 100, 200)]},
    "the clamp dominates the uses with no intervening reassignment of the clamped "
    "variable.",
    "both paths into `use` pass the clamp: the in-range path is guarded by the branchless "
    "test (unsigned)(v-100) <= 100, which is exactly 100 <= v <= 200, and the other path "
    "assigns the saturation value 100.  x is not reassigned between the clamp and the use.",
    mut_note='accepted upper end 200 -> 199; x = 200 is reachable.')

# =======================================================================================
# Pattern 13 -- bijective encoding transport (value)
# =======================================================================================
def _p13(name, k, bound):
    mask = (1 << k) - 1
    b = Builder(name, 2 * k if k <= 16 else 64)
    b.inp('x', 0, (1 << (k - 1)) - 1)     # the non-negative half of the k-bit signed range
    b.shr('s', 'x', k - 1)                # sign bit
    b.mul('m', 's', mask)                 # all-ones mask if negative
    b.shl('y', 'x', 1)
    b.band('y', 'y', mask)
    b.bxor('z', 'y', 'm')                 # zigzag(x) = (x << 1) ^ (x >> (k-1))
    b.label('chk'); b.check_bound('z', bound)
    b.halt()
    return b.build()


EX13 = Ex(
    13, 'value', 'bijective transport (8-bit ZigZag, x >= 0)',
    _p13('p13', 8, 255), _p13('p13-mut', 8, 254),
    {'chk': [('in', 'z', 0, 254)]},
    "the expression matches the bijection's canonical form at the operand's promoted "
    "width.",
    "the expression is ZigZag's canonical form (x << 1) ^ (x >> (k-1)) at k = 8, so the "
    "once-per-bijection lemma applies: x in [-2^(k-1), 2^(k-1)) maps onto [0, 2^k), and the "
    "non-negative half x in [0, 2^(k-1)) maps exactly onto the even values of "
    "[0, 2^k - 2].",
    approx="the exact image is the EVEN values of [0,254] (128 points); it is injected as "
           "the image interval [0,254] the paper's transport lemma gives, not as the "
           "128-element set.",
    mut_note='buffer length 255 -> 254; z = 254 is reachable.')

# =======================================================================================
# Pattern 14 -- sparse-state rank (control)
# =======================================================================================
def _p14(name, codes, steps, bound):
    k = len(codes)
    last = codes[-1]
    b = Builder(name, W16)
    b.const('st', codes[0])
    b.const('n', 0)
    b.label('head'); b.br('<', 'n', steps, 'body', 'end')
    b.label('body'); b.br('!=', 'st', last, 'use', 'adv')
    b.label('use')
    b.assign('idx', 'st')
    b.label('chk'); b.check_bound('idx', bound)
    b.jmp('adv')
    b.label('adv')
    for j in range(k):
        b.label('t%d' % j)
        b.br('==', 'st', codes[j], 's%d' % j, 't%d' % (j + 1))
    b.label('t%d' % k); b.jmp('cont')
    for j in range(k):
        b.label('s%d' % j); b.const('st', codes[(j + 1) % k]); b.jmp('cont')
    b.label('cont'); b.add('n', 'n', 1); b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


_C14 = (1, 4, 16)

EX14 = Ex(
    14, 'control', 'sparse-state rank (state in {1,4,16})',
    _p14('p14', _C14, 6, 5), _p14('p14-mut', _C14, 6, 4),
    {'body': [('set', 'st', _C14)]},
    "every assignment to the state variable -- its initialization included -- is a member "
    "of S, and its address is not taken.",
    "the four writes to st are the initialization st = 1 and the three transition "
    "assignments 1 -> 4 -> 16 -> 1, all members of S = {1,4,16}; no address is taken.  On "
    "the `st != 16` edge the set refines to {1,4}, so the rank-indexed table access is in "
    "bounds -- an interval can only remove 16 from the END of [1,16], not from the set.",
    mut_note='table size 5 -> 4; idx = 4 is reachable.')

# =======================================================================================
# Pattern 15 -- conditional variable splitting (relation)
# =======================================================================================
def _p15(name, bound):
    b = Builder(name, W16)
    b.inp('a', 0, 100)
    b.inp('bb', 0, 100)
    b.br('<=', 'a', 'bb', 'lo', 'hi')
    b.label('lo'); b.assign('x', 'a'); b.assign('y', 'bb'); b.jmp('m')
    b.label('hi'); b.assign('x', 'bb'); b.assign('y', 'a')
    b.label('m'); b.sub('d', 'y', 'x')
    b.label('chk'); b.check_bound('d', bound)
    b.halt()
    return b.build()


EX15 = Ex(
    15, 'relation', 'conditional variable splitting (d = y - x)',
    _p15('p15', 101), _p15('p15-mut', 100),
    {'m': [('lepair', 'x', 'y')]},
    "both branches are recognized single assignments.",
    "each branch assigns x and y once, from a and b in the order the guard establishes, so "
    "x <= y holds on both incoming edges of the merge.  The join loses it; the relational "
    "side table keeps it, and the subtraction y - x is then non-negative.",
    mut_note='table size 101 -> 100; d = 100 is reachable (a=0, b=100).')

# =======================================================================================
# Pattern 16 -- lockstep elimination (relation)
# =======================================================================================
def _p16(name, n, base, s, bound):
    b = Builder(name, W32)
    b.const('i', 0)
    b.const('p', base)
    b.label('head'); b.br('<', 'i', n, 'body', 'end')
    b.label('body'); b.label('chk'); b.check_bound('p', bound)
    b.add('p', 'p', s)
    b.add('i', 'i', 1)
    b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


EX16 = Ex(
    16, 'relation', 'lockstep elimination (p++ with i++, len 8)',
    _p16('p16', 8, 0, 1, 8), _p16('p16-mut', 8, 0, 1, 7),
    {'body': [('subst', 'p', 1, 'i', 0)]},
    "both variables are updated in the same iterations with the recognized strides, and "
    "neither is modified elsewhere in the loop.",
    "p and i are each written once per iteration, by p += 1 and i += 1, and nowhere else; "
    "with p = base + s*i = i the guard on i transports to p, which is otherwise unguarded "
    "and widens to the whole type.",
    mut_note='array length 8 -> 7; p = 7 is reachable.')


EXAMPLES = [EX1, EX2, EX3, EX4, EX5, EX6, EX7, EX8,
            EX9, EX10, EX11, EX12, EX13, EX14, EX15, EX16]


# =======================================================================================
# Sweeps -- leg A's curves, MEASURED
# =======================================================================================
# A sweep point declares how its dead-band fraction is measured:
#   kind='var'   DBF of one variable's reachable set at a point
#   kind='pair'  DBF of a pair's reachable set inside the product box (the 2-D case)
#   kind='bytes' DBF of the touched byte set of an address cursor (the space patterns)
# and which denominator the DESIGN's closed form is a closed form FOR:
#   denom='hull'      the tightest interval hull of the reachable set (the design's literal
#                     definition of DBF)
#   denom='baseline'  the interval the analysis holds at that point WITHOUT the fact; the
#                     expected value is stated and asserted, so it is measured, not assumed
#   denom=<int>       a declared extent (byte extent of the region / encoded value space),
#                     with the derivation given in the comment above the sweep
class SP:
    def __init__(self, label, prog, facts, point, kind, design, design_expr,
                 var=None, vars2=None, denom='hull', expect_denom=None, gsz=1,
                 enumerable=True, verdict=False):
        self.label, self.prog, self.facts, self.point = label, prog, facts, point
        self.kind, self.design, self.design_expr = kind, design, design_expr
        self.var, self.vars2, self.denom = var, vars2, denom
        self.expect_denom, self.gsz = expect_denom, gsz
        self.enumerable, self.verdict = enumerable, verdict


class Sweep:
    def __init__(self, patterns, name, param, points, note=''):
        self.patterns, self.name, self.param = patterns, name, param
        self.points, self.note = points, note


# --- sweep 1: affine IV, stride s ------------------------------------------------------
# m = 8 iterations, N = s*m.  Reachable i at body entry = {0,s,...,s(m-1)}, |S| = m.  The
# convex approximation the analysis holds without the fold is the guard interval [0, N-1],
# of size N = s*m, so DBF = 1 - m/(s*m) = (s-1)/s exactly.  (Against the tightest HULL,
# [0, s(m-1)], the fraction is 1 - m/(s(m-1)+1), which tends to (s-1)/s as m grows; both
# are printed.)
def sweep1():
    pts = []
    for s in (2, 4, 8, 16, 64):
        m, N = 8, 8 * s
        pts.append(SP('s=%d' % s, _p1('p1-s%d' % s, s, N, N),
                      {'body': [('le', 'i', _p1_actual_max(0, N, s))]},
                      'body', 'var', Fraction(s - 1, s), '(s-1)/s',
                      var='i', denom='baseline', expect_denom=N, verdict=True))
    return Sweep([1, 2], 'affine induction variable', 's', pts,
                 note="the design's (s-1)/s is a closed form for the DBF(denom) column -- "
                      'the interval the analysis holds without the fact, [0,N-1].  Against '
                      'the tightest hull [0,s(m-1)] the fraction is 1 - m/(s(m-1)+1) '
                      '(printed), which tends to (s-1)/s as the trip count m grows; here '
                      'm = 8.')


# --- sweep 3: geometric IV, width w ----------------------------------------------------
# Reachable m at body entry = {1,2,...,2^(w-1)}: w points inside the hull [1, 2^(w-1)] of
# size 2^(w-1), so DBF = 1 - w/2^(w-1) exactly -- the design's closed form, hull-based.
def sweep3():
    pts = []
    for w in (8, 16, 32, 64):
        pts.append(SP('w=%d' % w, _p3('p3-w%d' % w, w, w), _p3_facts(w),
                      'body', 'var', Fraction((1 << (w - 1)) - w, 1 << (w - 1)),
                      '1 - w/2^(w-1)', var='m', denom='hull', verdict=True))
    return Sweep([3], 'geometric induction variable', 'w', pts)


# --- sweep 5/6: struct of size Z, k fields of size g -----------------------------------
# The touched byte set over n elements is n*k*g bytes; the region the bounds check is
# against is the byte extent n*Z.  DBF = 1 - n*k*g/(n*Z) = 1 - k*g/Z exactly.  The
# numerator is enumerated (every touched byte), the denominator is the declared extent.
def sweep56():
    pts, n, g = [], 3, 4
    for Z in (8, 16, 32):
        for k in range(1, min(3, Z // g) + 1):
            prog, _o = _p6('p56-Z%dk%d' % (Z, k), n, Z, k, g, n * Z)
            pts.append(SP('Z=%d k=%d g=%d' % (Z, k, g), prog,
                          {'ibody': [('le', 'p', (n - 1) * Z),
                                     ('set', 'off', tuple(j * g for j in range(k)))]},
                          'chk', 'bytes', Fraction(Z - k * g, Z), '1 - k*g/Z',
                          var='abase', denom=n * Z, gsz=g))
    return Sweep([5, 6], 'struct field factoring / stride-union convexification',
                 'Z,k,g', pts)


# --- sweep 13: ZigZag on k-bit inputs --------------------------------------------------
# Naive transport of the non-negative half: 2^(k-1) inputs map onto the even values of the
# k-bit encoded space [0, 2^k), which is the interval the transport has without the fold.
# DBF = 1 - 2^(k-1)/2^k = 1/2 exactly, for every k (the design's "approx 1/2").  Against
# the tightest hull [0, 2^k - 2] it is 1 - 2^(k-1)/(2^k - 1); both are printed.
def sweep13():
    pts = []
    for k in (8, 16, 32):
        ok = k <= 16
        pts.append(SP('k=%d' % k, _p13('p13-k%d' % k, k, (1 << k) - 1),
                      {'chk': [('in', 'z', 0, (1 << k) - 2)]},
                      'chk', 'var', Fraction(1, 2), '1/2',
                      var='z', denom=1 << k, enumerable=ok, verdict=ok))
    return Sweep([13], 'ZigZag bijective transport', 'k', pts,
                 note="the design's 1/2 is exact against the k-bit encoded space [0,2^k) "
                      '(the DBF(denom) column); against the tightest hull [0,2^k-2] it is '
                      "1 - 2^(k-1)/(2^k-1), the design's 'approx 1/2'.  k=32 is not "
                      'enumerated: 2^31 concrete inputs exceeds the enumeration budget, so '
                      'that row is closed-form only.')


# --- sweep 14: sparse states, k legal codes over range R -------------------------------
# Codes are spread over [0,R) including 0 and R-1, so the hull is exactly R wide and
# DBF = 1 - k/R.  The one-hot rows use codes {1,2,...,2^(w-1)}, hull [1, 2^(w-1)], giving
# the design's 1 - w/2^(w-1) again.
def sweep14():
    pts = []
    for R in (16, 64, 256):
        for k in (2, 4, 8):
            codes = tuple(sorted(set(j * (R - 1) // (k - 1) for j in range(k))))
            if len(codes) != k:
                continue
            pts.append(SP('R=%d k=%d' % (R, k),
                          _p14('p14-R%dk%d' % (R, k), codes, k + 2, codes[-2] + 1),
                          {'body': [('set', 'st', codes)]},
                          'body', 'var', Fraction(R - k, R), '1 - k/R',
                          var='st', denom='hull', verdict=True))
    for w in (8, 16):
        codes = tuple(1 << e for e in range(w))
        pts.append(SP('one-hot w=%d' % w,
                      _p14('p14-oh%d' % w, codes, w + 2, codes[-2] + 1),
                      {'body': [('set', 'st', codes)]},
                      'body', 'var',
                      Fraction((1 << (w - 1)) - w, 1 << (w - 1)), '1 - w/2^(w-1)',
                      var='st', denom='hull', verdict=True))
    return Sweep([14], 'sparse-state rank', 'R,k', pts)


# --- sweep 16: lockstep pair over an n-point line in an n x n box ----------------------
# The reachable (i,p) pairs at body entry are the n points of the line p = i; the product
# of the two tightest intervals is the n x n box, so DBF = 1 - n/n^2 = 1 - 1/n exactly.
def sweep16():
    pts = []
    for n in (4, 8, 16, 32, 64):
        pts.append(SP('n=%d' % n, _p16('p16-n%d' % n, n, 0, 1, n),
                      {'body': [('subst', 'p', 1, 'i', 0)]},
                      'body', 'pair', Fraction(n - 1, n), '1 - 1/n',
                      vars2=('i', 'p'), denom='hull', verdict=True))
    return Sweep([16], 'lockstep elimination', 'n', pts)


SWEEPS = [sweep1(), sweep3(), sweep56(), sweep13(), sweep14(), sweep16()]


# =======================================================================================
# Validity probes -- the OTHER direction of failure (reported separately, never counted
# in the mutant-flip rate).  Each takes a canonical example, breaks the pattern's VALIDITY
# CONDITION rather than the check, and injects the same fact anyway.  The paper's point is
# that this direction is subtractive: the analysis then PROVES a check that a concrete
# execution violates.  These runs are unsound BY CONSTRUCTION -- that is the finding.
# =======================================================================================
def _p1_bodywrite():
    """Pattern 1's validity condition fails: the body writes i as well as the increment,
    so the effective stride is 1 and the iterates leave the residue the fold assumed."""
    b = Builder('p1-invalid-bodywrite', W32)
    b.const('i', 0)
    b.label('head'); b.br('<', 'i', 20, 'body', 'end')
    b.label('body')
    b.add('t', 'i', 1)
    b.label('chk'); b.check_bound('t', 20)
    b.add('i', 'i', 2)
    b.sub('i', 'i', 1)                    # the extra body write to the IV
    b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


def _p2_nondiv():
    """Pattern 2's validity condition fails: the stride does not divide N - c0, so the
    iterates step over the limit and wrap instead of terminating at it."""
    return _p2('p2-invalid-stride', 3, 20, 20)


def _p14_escape():
    """Pattern 14's validity condition fails: one transition writes a non-member of S."""
    b = Builder('p14-invalid-write', W16)
    b.const('st', 1)
    b.const('n', 0)
    b.label('head'); b.br('<', 'n', 6, 'body', 'end')
    b.label('body'); b.br('!=', 'st', 16, 'use', 'adv')
    b.label('use'); b.assign('idx', 'st')
    b.label('chk'); b.check_bound('idx', 5)
    b.jmp('adv')
    b.label('adv'); b.br('==', 'st', 1, 'esc', 'adv2')
    b.label('adv2'); b.br('==', 'st', 4, 's16', 'cont')
    b.label('esc'); b.const('st', 20); b.jmp('cont')   # 20 is not in S = {1,4,16}
    b.label('s16'); b.const('st', 16); b.jmp('cont')
    b.label('cont'); b.add('n', 'n', 1); b.jmp('head')
    b.label('end'); b.halt()
    return b.build()


# (pattern, what was broken, program, the fact injected anyway, the fact's point/var)
PROBES = [
    (1, 'body writes i besides the increment', _p1_bodywrite(),
     {'body': [('le', 'i', 18)]}),
    (2, 'stride 3 does not divide N - c0 = 20', _p2_nondiv(),
     {'body': [('le', 'i', 16)]}),
    (14, 'a transition writes 20, not a member of S', _p14_escape(),
     {'body': [('set', 'st', _C14)]}),
]
