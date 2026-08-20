"""refanalyzer.py -- a textbook worklist interval analysis, plus a concrete interpreter,
for the folding paper's evaluation (leg B).

Nothing here is clever.  It is meant to be READ: the whole trust story of the evaluation is
that a reader can check by eye that (a) the abstract semantics is a sound over-approximation
of the concrete one, and (b) the only extension over a textbook interval analysis is the
fact-injection hook -- folding's consumption mechanism in its smallest honest form.

Contents
  * a tiny explicit IR (unsigned machine integers of a declared width)
  * a concrete interpreter that enumerates the *complete* reachable state set (used to
    measure dead-band fractions and to exhibit violating executions)
  * an interval domain with three small components, all of which are ONLY ever populated by
    injected facts, never synthesised by the transfer functions:
        - a small-set component  (var in S, |S| <= MAXSET)
        - a relational <= side table  (pattern 15)
    plus the plain interval, which the transfer functions do compute.
  * widening to thresholds + a descending (narrowing) pass
  * inject(point, fact): meet a fact into the abstract state at a named program point.

Deliberate imprecisions of the BASELINE domain, both standard for a textbook interval
analysis, both documented in run.py's footnotes:
  F1. bitwise and/or/xor have no interval transfer -- they return TOP (except on singleton
      operands, where they are folded exactly).  Shifts by a constant ARE precise: they are
      multiplication/division by a power of two.
  F2. an operation whose exact integer result may leave [0, 2^w) returns TOP (the concrete
      semantics wraps; the abstract side refuses to guess).  Soundness first.
"""

from collections import deque
from fractions import Fraction

MAXSET = 32          # cap on the small-set component
NARROW_ROUNDS = 4    # descending passes after the widened fixpoint
MAX_ROUNDS = 400     # round-robin cap (ascending and each descending pass)
WIDEN_DELAY = 2      # rounds before widening kicks in at a widening point

# --------------------------------------------------------------------------------------
# IR
# --------------------------------------------------------------------------------------
# An operand is an int (constant) or a str (variable name).
# A statement is a tuple whose head is the opcode; the program point of a statement is its
# index in prog.stmts, and it denotes the state ON ENTRY to that statement.
#
#   ('const', d, k)                 d := k
#   ('assign', d, src)              d := src            (the only set-preserving move)
#   ('bin', d, op, a, b)            d := a op b         op in add sub mul and or xor
#   ('divc', d, a, k) ('modc', d, a, k)
#   ('shlc', d, a, k) ('shrc', d, a, k)
#   ('input', d, lo, hi)            d := any value in [lo,hi]   (nondeterminism)
#   ('br', cmp, a, b, t, f)         cmp in < <= == !=
#   ('jmp', t)
#   ('check_bound', v, n)           prove 0 <= v < n
#   ('check_range', v, lo, hi)      prove lo <= v <= hi
#   ('check_shift', v, w)           prove 0 <= v < w
#   ('halt',)
CHECKS = ('check_bound', 'check_range', 'check_shift')


class Program:
    def __init__(self, name, width, stmts, labels, note=''):
        self.name, self.width, self.stmts, self.labels, self.note = \
            name, width, stmts, labels, note
        self.mask = (1 << width) - 1
        vs = set()
        for s in stmts:
            for x in s[1:]:
                if isinstance(x, str) and x not in ('add', 'sub', 'mul', 'and', 'or',
                                                    'xor', '<', '<=', '==', '!='):
                    vs.add(x)
        self.vars = sorted(vs)
        self.rlabels = {v: k for k, v in labels.items()}

    def pt(self, label):
        return self.labels[label]

    def succs(self, pc):
        s = self.stmts[pc]
        if s[0] == 'br':
            return [s[4], s[5]]
        if s[0] == 'jmp':
            return [s[1]]
        if s[0] == 'halt':
            return []
        return [pc + 1]


class Builder:
    """Assembles a Program from labelled pseudo-assembly.  Labels are resolved at build."""

    def __init__(self, name, width):
        self.name, self.width, self.stmts, self.labels, self.fix = name, width, [], {}, []

    def label(self, nm):
        self.labels[nm] = len(self.stmts)
        return self

    def _emit(self, *s):
        self.stmts.append(s)

    def const(self, d, k):        self._emit('const', d, k)
    def assign(self, d, s):       self._emit('assign', d, s)
    def bin(self, d, op, a, b):   self._emit('bin', d, op, a, b)
    def add(self, d, a, b):       self.bin(d, 'add', a, b)
    def sub(self, d, a, b):       self.bin(d, 'sub', a, b)
    def mul(self, d, a, b):       self.bin(d, 'mul', a, b)
    def band(self, d, a, b):      self.bin(d, 'and', a, b)
    def bor(self, d, a, b):       self.bin(d, 'or', a, b)
    def bxor(self, d, a, b):      self.bin(d, 'xor', a, b)
    def divc(self, d, a, k):      self._emit('divc', d, a, k)
    def modc(self, d, a, k):      self._emit('modc', d, a, k)
    def shl(self, d, a, k):       self._emit('shlc', d, a, k)
    def shr(self, d, a, k):       self._emit('shrc', d, a, k)
    def inp(self, d, lo, hi):     self._emit('input', d, lo, hi)
    def jmp(self, t):             self.fix.append((len(self.stmts), 1, t)); self._emit('jmp', t)
    def check_bound(self, v, n):  self._emit('check_bound', v, n)
    def check_range(self, v, a, b): self._emit('check_range', v, a, b)
    def check_shift(self, v, w):  self._emit('check_shift', v, w)
    def halt(self):               self._emit('halt')

    def br(self, cmp_, a, b, t, f):
        self.fix.append((len(self.stmts), 4, t))
        self.fix.append((len(self.stmts), 5, f))
        self._emit('br', cmp_, a, b, t, f)

    def build(self, note=''):
        for (i, slot, lab) in self.fix:
            s = list(self.stmts[i])
            s[slot] = self.labels[lab]
            self.stmts[i] = tuple(s)
        return Program(self.name, self.width, self.stmts, dict(self.labels), note)


# --------------------------------------------------------------------------------------
# Concrete semantics: complete reachable-state enumeration
# --------------------------------------------------------------------------------------
def _ceval(op, a, b):
    if op == 'add': return a + b
    if op == 'sub': return a - b
    if op == 'mul': return a * b
    if op == 'and': return a & b
    if op == 'or':  return a | b
    if op == 'xor': return a ^ b
    raise ValueError(op)


def _cmp(op, a, b):
    if op == '<':  return a < b
    if op == '<=': return a <= b
    if op == '==': return a == b
    if op == '!=': return a != b
    raise ValueError(op)


class Concrete:
    """Exhaustive forward exploration of the concrete transition system.

    `reach[pc]` is the exact set of variable valuations reachable on entry to statement pc.
    Machine semantics: every write is taken modulo 2^width (wraparound is DEFINED here).
    `violations` lists concrete check failures, each with a replayable execution trace.
    """

    def __init__(self, prog, budget=2000000, trace=True):
        self.prog, self.budget, self.trace = prog, budget, trace
        self.reach = {}
        self.violations = []
        self.exhausted = False
        self._seen = {}
        self._run()

    def _run(self):
        p = self.prog
        idx = {v: i for i, v in enumerate(p.vars)}
        start = (0, tuple(0 for _ in p.vars))
        seen = {start: None} if self.trace else set([start])
        q = deque([start])
        n = 0
        while q:
            pc, vals = q.popleft()
            n += 1
            if n > self.budget:
                self.exhausted = True
                return
            self.reach.setdefault(pc, set()).add(vals)
            for nxt in self._step(pc, vals, idx):
                if nxt not in seen:
                    if self.trace:
                        seen[nxt] = (pc, vals)
                    else:
                        seen.add(nxt)
                    q.append(nxt)
        if self.trace:
            self._seen = seen

    def _val(self, x, vals, idx):
        return x if isinstance(x, int) else vals[idx[x]]

    def _step(self, pc, vals, idx):
        p, s, m = self.prog, self.prog.stmts[pc], self.prog.mask

        def w(d, v):
            lst = list(vals)
            lst[idx[d]] = v & m
            return [(pc + 1, tuple(lst))]

        k = s[0]
        if k == 'const':  return w(s[1], s[2])
        if k == 'assign': return w(s[1], self._val(s[2], vals, idx))
        if k == 'bin':
            return w(s[1], _ceval(s[2], self._val(s[3], vals, idx),
                                  self._val(s[4], vals, idx)))
        if k == 'divc':   return w(s[1], self._val(s[2], vals, idx) // s[3])
        if k == 'modc':   return w(s[1], self._val(s[2], vals, idx) % s[3])
        if k == 'shlc':   return w(s[1], self._val(s[2], vals, idx) << s[3])
        if k == 'shrc':   return w(s[1], self._val(s[2], vals, idx) >> s[3])
        if k == 'input':
            out = []
            for v in range(s[2], s[3] + 1):
                lst = list(vals)
                lst[idx[s[1]]] = v & m
                out.append((pc + 1, tuple(lst)))
            return out
        if k == 'br':
            t = _cmp(s[1], self._val(s[2], vals, idx), self._val(s[3], vals, idx))
            return [(s[4] if t else s[5], vals)]
        if k == 'jmp':    return [(s[1], vals)]
        if k == 'halt':   return []
        if k in CHECKS:
            if not check_holds_concrete(s, self._val(s[1], vals, idx)):
                self.violations.append((pc, vals))
            return [(pc + 1, vals)]
        raise ValueError(k)

    def values_at(self, pc, var):
        i = self.prog.vars.index(var)
        return set(v[i] for v in self.reach.get(pc, ()))

    def trace_to(self, pc, vals):
        """Replayable execution witness: the list of (pc, valuation) from entry."""
        out, cur = [], (pc, vals)
        seen = getattr(self, '_seen', {})
        while cur is not None:
            out.append(cur)
            cur = seen.get(cur)
        return list(reversed(out))


def check_holds_concrete(s, v):
    if s[0] == 'check_bound': return 0 <= v < s[2]
    if s[0] == 'check_range': return s[2] <= v <= s[3]
    if s[0] == 'check_shift': return 0 <= v < s[2]
    raise ValueError(s[0])


# --------------------------------------------------------------------------------------
# Abstract domain
# --------------------------------------------------------------------------------------
# An abstract value is (lo, hi, S): the interval [lo,hi] and either None or a frozenset of
# concrete values with |S| <= MAXSET.  Invariant: S is None or S subseteq [lo,hi].
# An abstract state is St(v = {var: value}, le = frozenset of (a,b) meaning a <= b), or None
# for bottom.

class St:
    __slots__ = ('v', 'le')

    def __init__(self, v, le=frozenset()):
        self.v, self.le = v, le

    def copy(self):
        return St(dict(self.v), self.le)


def _norm(lo, hi, S, mx):
    lo, hi = max(0, lo), min(mx, hi)
    if lo > hi:
        return None
    if S is not None:
        S = frozenset(x for x in S if lo <= x <= hi)
        if not S:
            return None
        lo, hi = max(lo, min(S)), min(hi, max(S))
    return (lo, hi, S)


def top(mx):
    return (0, mx, None)


def val_join(a, b):
    lo, hi = min(a[0], b[0]), max(a[1], b[1])
    S = None
    if a[2] is not None and b[2] is not None and len(a[2] | b[2]) <= MAXSET:
        S = a[2] | b[2]
    return (lo, hi, S)


def val_meet(a, b, mx):
    S = a[2] if b[2] is None else (b[2] if a[2] is None else (a[2] & b[2]))
    return _norm(max(a[0], b[0]), min(a[1], b[1]), S, mx)


def val_leq(a, b):
    if a[0] < b[0] or a[1] > b[1]:
        return False
    if b[2] is not None and (a[2] is None or not (a[2] <= b[2])):
        return False
    return True


def st_join(a, b):
    if a is None: return b
    if b is None: return a
    return St({k: val_join(a.v[k], b.v[k]) for k in a.v}, a.le & b.le)


def st_meet(a, b, mx):
    if a is None or b is None: return None
    out = {}
    for k in a.v:
        m = val_meet(a.v[k], b.v[k], mx)
        if m is None: return None
        out[k] = m
    return St(out, a.le | b.le)


def st_leq(a, b):
    if a is None: return True
    if b is None: return False
    return all(val_leq(a.v[k], b.v[k]) for k in a.v) and b.le <= a.le


def st_widen(old, new, thr, mx):
    """Interval widening to thresholds; the fact-only components jump to their top."""
    if old is None: return new
    if new is None: return old
    out = {}
    for k in old.v:
        (ol, oh, os_), (nl, nh, ns) = old.v[k], new.v[k]
        lo = ol if nl >= ol else max([t for t in thr if t <= nl], default=0)
        hi = oh if nh <= oh else min([t for t in thr if t >= nh], default=mx)
        S = os_ if os_ is not None and ns is not None and os_ == ns else None
        out[k] = _norm(lo, hi, S, mx) or (lo, hi, None)
    return St(out, old.le & new.le)


# ---- abstract transfer functions ------------------------------------------------------
def _av(x, st, mx):
    return (x, x, frozenset([x])) if isinstance(x, int) else st.v[x]


def abs_bin(op, A, B, mx, ge_zero=False):
    """F1/F2 apply here.  ge_zero: the relational side table certifies a-b >= 0."""
    if A[2] is not None and B[2] is not None and len(A[2]) * len(B[2]) <= MAXSET:
        S = frozenset((_ceval(op, a, b)) & mx for a in A[2] for b in B[2])
        return _norm(min(S), max(S), S, mx)
    if op in ('and', 'or', 'xor'):
        return top(mx)                                   # F1
    lo, hi = {'add': (A[0] + B[0], A[1] + B[1]),
              'sub': (A[0] - B[1], A[1] - B[0]),
              'mul': (A[0] * B[0], A[1] * B[1])}[op]
    if op == 'sub' and lo < 0 and ge_zero:
        lo = 0                                           # pattern 15's side table
    if lo < 0 or hi > mx:
        return top(mx)                                   # F2
    return (lo, hi, None)


def transfer(prog, pc, st):
    """Returns [(successor pc, state)].  `st` is the state on entry to statement pc."""
    s, mx = prog.stmts[pc], prog.mask

    def wr(d, val):
        if val is None: return []
        n = st.copy()
        n.v[d] = val
        n.le = frozenset(p for p in n.le if d not in p)   # kill relations mentioning d
        return [(pc + 1, n)]

    k = s[0]
    if k == 'const':  return wr(s[1], (s[2], s[2], frozenset([s[2]])))
    if k == 'assign': return wr(s[1], _av(s[2], st, mx))   # the set component survives
    if k == 'bin':
        A, B = _av(s[3], st, mx), _av(s[4], st, mx)
        gz = (s[2] == 'sub' and isinstance(s[3], str) and isinstance(s[4], str)
              and (s[4], s[3]) in st.le)
        return wr(s[1], abs_bin(s[2], A, B, mx, gz))
    if k in ('divc', 'modc', 'shlc', 'shrc'):
        A, kk = _av(s[2], st, mx), s[3]
        if k == 'divc': r = (A[0] // kk, A[1] // kk, None)
        elif k == 'shrc': r = (A[0] >> kk, A[1] >> kk, None)
        elif k == 'shlc':
            r = top(mx) if (A[1] << kk) > mx else (A[0] << kk, A[1] << kk, None)   # F2
        else:
            r = ((A[0] % kk, A[1] % kk, None) if A[0] // kk == A[1] // kk
                 else (0, kk - 1, None))
        return wr(s[1], r)
    if k == 'input':  return wr(s[1], (s[2], s[3], None))
    if k == 'br':
        t = refine(st, s[1], s[2], s[3], True, mx)
        f = refine(st, s[1], s[2], s[3], False, mx)
        return [(x, y) for x, y in ((s[4], t), (s[5], f)) if y is not None]
    if k == 'jmp':    return [(s[1], st)]
    if k == 'halt':   return []
    if k in CHECKS:   return [(pc + 1, st)]
    raise ValueError(k)


_NEG = {'<': '>=', '<=': '>', '==': '!=', '!=': '=='}


def refine(st, op, a, b, taken, mx):
    """Condition refinement on a branch edge, both directions, including exact membership
    refinement of the small-set component on == and != edges."""
    o = op if taken else _NEG[op]
    A, B = _av(a, st, mx), _av(b, st, mx)
    na, nb = A, B
    if o == '<':    na, nb = (A[0], min(A[1], B[1] - 1), A[2]), (max(B[0], A[0] + 1), B[1], B[2])
    elif o == '<=': na, nb = (A[0], min(A[1], B[1]), A[2]), (max(B[0], A[0]), B[1], B[2])
    elif o == '>':  na, nb = (max(A[0], B[0] + 1), A[1], A[2]), (B[0], min(B[1], A[1] - 1), B[2])
    elif o == '>=': na, nb = (max(A[0], B[0]), A[1], A[2]), (B[0], min(B[1], A[1]), B[2])
    elif o == '==':
        lo, hi = max(A[0], B[0]), min(A[1], B[1])
        S = A[2] if B[2] is None else (B[2] if A[2] is None else A[2] & B[2])
        na = nb = (lo, hi, S)
    elif o == '!=':
        na, nb = A, B
        if B[0] == B[1]:                       # b is a known point: remove it
            c = B[0]
            SA = None if A[2] is None else frozenset(x for x in A[2] if x != c)
            lo, hi = A[0], A[1]
            if lo == c: lo += 1
            if hi == c: hi -= 1
            na = (lo, hi, SA)
        if A[0] == A[1]:
            c = A[0]
            SB = None if B[2] is None else frozenset(x for x in B[2] if x != c)
            lo, hi = B[0], B[1]
            if lo == c: lo += 1
            if hi == c: hi -= 1
            nb = (lo, hi, SB)
    out = st.copy()
    for var, nv in ((a, na), (b, nb)):
        if isinstance(var, str):
            r = _norm(nv[0], nv[1], nv[2], mx)
            if r is None: return None
            out.v[var] = r
        else:
            r = _norm(nv[0], nv[1], nv[2], mx)
            if r is None: return None
    return out


# ---- fact injection -------------------------------------------------------------------
# Fact forms (exactly what the paper's validity conditions license, nothing more):
#   ('le', v, c)                 v <= c
#   ('ge', v, c)                 v >= c
#   ('in', v, a, b)              v in [a,b]
#   ('set', v, (..))             v in S      (small finite set)
#   ('subst', v, k, u, b)        v == k*u + b     (bidirectional substitution)
#   ('lepair', a, b)             a <= b      (relational side table)
def apply_facts(st, facts, mx):
    if st is None or not facts:
        return st
    for f in facts:
        if st is None:
            return None
        kind = f[0]
        if kind == 'lepair':
            st = st.copy()
            st.le = st.le | frozenset([(f[1], f[2])])
            A, B = st.v[f[1]], st.v[f[2]]
            a = _norm(A[0], min(A[1], B[1]), A[2], mx)
            b = _norm(max(B[0], A[0]), B[1], B[2], mx)
            if a is None or b is None: return None
            st.v[f[1]], st.v[f[2]] = a, b
            continue
        if kind == 'subst':
            _, v, k, u, b = f
            U = st.v[u]
            cur = st.v[v]
            lo, hi = k * U[0] + b, k * U[1] + b
            S = None if U[2] is None else frozenset((k * x + b) & mx for x in U[2])
            nv = val_meet(cur, _norm(lo, hi, S, mx) or (0, mx, None), mx)
            if nv is None: return None
            # inverse direction: u == (v - b)/k
            ulo = max(U[0], -(-(cur[0] - b) // k) if cur[0] - b > 0 else 0)
            uhi = min(U[1], (cur[1] - b) // k) if cur[1] - b >= 0 else -1
            nu = _norm(ulo, uhi, U[2], mx)
            if nu is None: return None
            st = st.copy(); st.v[v], st.v[u] = nv, nu
            continue
        v = f[1]
        cur = st.v[v]
        if kind == 'le':    box = (0, f[2], None)
        elif kind == 'ge':  box = (f[2], mx, None)
        elif kind == 'in':  box = (f[2], f[3], None)
        elif kind == 'set':
            S = frozenset(f[2])
            box = (min(S), max(S), S)
        else:
            raise ValueError(kind)
        nv = val_meet(cur, box, mx)
        if nv is None: return None
        st = st.copy(); st.v[v] = nv
    return st


# --------------------------------------------------------------------------------------
# Fixpoint
# --------------------------------------------------------------------------------------
def thresholds(prog, facts):
    T = {0, prog.mask}
    for s in prog.stmts:
        for x in s[1:]:
            if isinstance(x, int):
                T |= {x, x - 1, x + 1}
    for fl in (facts or {}).values():
        for f in fl:
            for x in f[1:]:
                if isinstance(x, int):
                    T |= {x, x - 1, x + 1}
    return sorted(t for t in T if 0 <= t <= prog.mask)


def back_edge_targets(prog):
    return set(t for pc in range(len(prog.stmts)) for t in prog.succs(pc) if t <= pc)


class Result:
    def __init__(self, entry, widen_count, converged):
        self.entry = entry            # pc -> St|None, AFTER facts are applied
        self.widen_count = widen_count
        self.converged = converged

    def iv(self, pc, var):
        st = self.entry.get(pc)
        return None if st is None else st.v[var][:2]

    def width(self, pc, var):
        s = self.iv(pc, var)
        return 0 if s is None else s[1] - s[0] + 1


def _init_state(prog):
    return St({v: (0, 0, frozenset([0])) for v in prog.vars})


def _F(prog, fx, X, mx):
    """One application of the transfer functional.

    X[pc] is the state on entry to pc BEFORE facts; entry[pc] is the same state after the
    facts at pc have been met in; out[q] is the join of every contribution into q.
    """
    n = len(prog.stmts)
    out, entry = [None] * n, [None] * n
    out[0] = _init_state(prog)
    for pc in range(n):
        if X[pc] is None:
            continue
        st = apply_facts(X[pc], fx.get(pc), mx)
        entry[pc] = st
        if st is None:
            continue
        for (succ, o) in transfer(prog, pc, st):
            out[succ] = st_join(out[succ], o)
    return out, entry


def analyze(prog, facts=None, narrow=True):
    """Ascending Kleene iteration with widening-to-thresholds, then a standard descending
    (narrowing) sequence X := X meet F(X) started FROM the widened post-fixpoint.

    `facts` maps a program point (int pc, or a label name) to a list of facts.  Starting the
    descent from the post-fixpoint -- rather than re-solving from bottom under a cap -- is
    what keeps this a narrowing pass and not a second, sharper fixpoint computation; every
    iterate stays a post-fixpoint, so the result stays sound.
    """
    fx = {}
    for k, v in (facts or {}).items():
        fx[prog.pt(k) if isinstance(k, str) else k] = list(v)
    thr, mx, n = thresholds(prog, fx), prog.mask, len(prog.stmts)
    wp = back_edge_targets(prog)
    X = [None] * n
    X[0] = _init_state(prog)
    wcount, rounds, converged = 0, 0, False
    while rounds < MAX_ROUNDS:
        rounds += 1
        Y, _e = _F(prog, fx, X, mx)
        NX, changed = [], False
        for pc in range(n):
            new = st_join(X[pc], Y[pc])
            if pc in wp and rounds > WIDEN_DELAY and not st_leq(new, X[pc]):
                new = st_widen(X[pc], new, thr, mx)
                wcount += 1
            if not st_leq(new, X[pc]):
                changed = True
            NX.append(new)
        X = NX
        if not changed:
            converged = True
            break
    if narrow and converged:
        for _ in range(NARROW_ROUNDS):
            Y, _e = _F(prog, fx, X, mx)
            NX = [st_meet(X[pc], Y[pc], mx) for pc in range(n)]
            if all(st_leq(a, b) for a, b in zip(X, NX)):
                break
            X = NX
    _Y, entry = _F(prog, fx, X, mx)
    return Result({i: e for i, e in enumerate(entry)}, wcount, converged)


# --------------------------------------------------------------------------------------
# Verdicts and soundness
# --------------------------------------------------------------------------------------
def verdict(prog, res, pc):
    """PROVEN / FAIL / UNREACH for the check at pc.  UNREACH is reported distinctly: an
    empty abstract state proves everything vacuously and must never be counted as a flip."""
    s = prog.stmts[pc]
    st = res.entry.get(pc)
    if st is None:
        return 'UNREACH'
    lo, hi = st.v[s[1]][:2]
    if s[0] == 'check_bound': ok = hi < s[2]
    elif s[0] == 'check_range': ok = lo >= s[2] and hi <= s[3]
    else: ok = hi < s[2]
    return 'PROVEN' if ok else 'FAIL'


def check_pc(prog):
    for pc, s in enumerate(prog.stmts):
        if s[0] in CHECKS:
            return pc
    raise ValueError('no check in ' + prog.name)


def soundness(prog, res, con):
    """Every concrete reachable valuation must be inside the abstract state at its point."""
    bad = []
    for pc, states in con.reach.items():
        st = res.entry.get(pc)
        if st is None:
            bad.append((pc, 'abstract bottom, concrete reachable'))
            continue
        for vals in states:
            for i, v in enumerate(prog.vars):
                lo, hi, S = st.v[v]
                x = vals[i]
                if not (lo <= x <= hi) or (S is not None and x not in S):
                    bad.append((pc, '%s=%d not in [%d,%d]%s'
                                % (v, x, lo, hi, '' if S is None else ' set')))
                    break
    return bad


def dbf(reach_size, hull_size):
    """Dead-band fraction: the share of the convex approximation that is unreachable."""
    return Fraction(0) if hull_size == 0 else Fraction(hull_size - reach_size, hull_size)
