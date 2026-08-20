#!/usr/bin/env python3
"""
census.py -- syntactic shape-frequency census for Leg C of the folding paper.

Counts occurrences of the folding pattern catalogue's syntactic shapes over a
given file list, using regex/paren-balancing over C source with comments and
string/char literals blanked out first (so matches inside comments or string
literals do not inflate counts).

This is a SYNTACTIC OCCURRENCE counter: it establishes an upper bound on the
number of sites where a fold *could* apply (the shape is present in the
text), not a claim that folding's validity conditions hold at every site (no
def-use analysis, no aliasing, no macro expansion). Each class's regex and
known blind spots are documented in the --help output below and in
eval/census.md.

Usage:
    python3 census.py --dir DIR --files f1.c f2.c ... [--per-file] [--dump-switches]

All file arguments are paths relative to --dir (or absolute).
Prints a LoC table per file, then an aggregate shape-count table, to stdout.
No file writes, no network access, no git commands.
"""

import argparse
import os
import re
import sys


# ---------------------------------------------------------------------------
# Stage 0: strip comments and string/char literal contents (blanked with
# spaces so that character offsets and line numbers are preserved -- this
# matters for the line-distance heuristic used by the clamp detector).
# ---------------------------------------------------------------------------

def strip_comments_and_strings(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j]))
            i = j
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" and j + 1 < n else 1
            j = min(j + 1, n)
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j]))
            i = j
        elif c == "'":
            j = i + 1
            while j < n and text[j] != "'":
                j += 2 if text[j] == "\\" and j + 1 < n else 1
            j = min(j + 1, n)
            out.append(" " * (j - i))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Paren/brace balancing helpers, used to extract for(...)/while(...) clauses
# and switch { ... } bodies without a full C parser.
# ---------------------------------------------------------------------------

def _match_parens(text, open_paren_pos):
    """Given the index of an '(' return the index of its matching ')'."""
    depth = 0
    i = open_paren_pos
    n = len(text)
    while i < n:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _match_braces(text, open_brace_pos):
    depth = 0
    i = open_brace_pos
    n = len(text)
    while i < n:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def split_top_level(s, sep):
    """Split s on sep chars that are not nested inside (), [], {}."""
    parts = []
    depth = 0
    cur = []
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0 and ch == sep:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def find_for_loops(text):
    """Return list of dicts: {init, cond, update, start, line}."""
    loops = []
    for m in re.finditer(r"\bfor\s*\(", text):
        open_pos = m.end() - 1
        close_pos = _match_parens(text, open_pos)
        if close_pos == -1:
            continue
        inner = text[open_pos + 1:close_pos]
        parts = split_top_level(inner, ";")
        line = text.count("\n", 0, m.start()) + 1
        rec = {"start": m.start(), "line": line, "raw": inner}
        if len(parts) == 3:
            rec["init"], rec["cond"], rec["update"] = parts
        else:
            # non-canonical for(...) (e.g. range-like macro usage) -- rare in
            # plain C; record raw only, classified as 'malformed'.
            rec["init"], rec["cond"], rec["update"] = None, None, None
        loops.append(rec)
    return loops


def find_while_loops(text):
    """Return list of dicts: {cond, start, line}. Also matches the trailing
    while(...) of a do/while statement -- a known, minor over-count (a
    do/while's condition is picked up as if it were a second loop header;
    the loop BODY is not double counted, only this one boundary token is
    ambiguous). See blind-spots note in census.md."""
    loops = []
    for m in re.finditer(r"\bwhile\s*\(", text):
        open_pos = m.end() - 1
        close_pos = _match_parens(text, open_pos)
        if close_pos == -1:
            continue
        cond = text[open_pos + 1:close_pos]
        line = text.count("\n", 0, m.start()) + 1
        loops.append({"cond": cond, "start": m.start(), "line": line})
    return loops


def find_switches(text):
    """Return list of dicts: {cases: [raw case-label strings], line}.
    Nested switches are NOT excluded from an outer switch's case list (a
    documented blind spot -- nested switch is rare in the sampled code)."""
    switches = []
    for m in re.finditer(r"\bswitch\s*\(", text):
        open_pos = m.end() - 1
        close_pos = _match_parens(text, open_pos)
        if close_pos == -1:
            continue
        j = close_pos + 1
        while j < len(text) and text[j] in " \t\r\n":
            j += 1
        if j >= len(text) or text[j] != "{":
            continue
        body_close = _match_braces(text, j)
        if body_close == -1:
            continue
        body = text[j + 1:body_close]
        cases = re.findall(r"\bcase\s+([^:]+?)\s*:", body)
        line = text.count("\n", 0, m.start()) + 1
        switches.append({"cases": cases, "line": line})
    return switches


# ---------------------------------------------------------------------------
# Class 1: for-loop stride classification.
#
# Definition (fixed for reproducibility -- the task prompt's wording is
# ambiguous about whether the "c > 1" threshold applies to '-=' as well as
# '+='; this script applies it symmetrically: a for-loop update clause is
# "strided" iff it is `var += c` or `var -= c` for an integer literal c > 1;
# "stride-1" iff it is `var++`, `++var`, `var--`, `--var`, `var += 1`, or
# `var -= 1`; anything else (empty update, non-constant step, multi-part
# update via comma, function-call update, etc.) falls in an "other" bucket,
# still counted toward the total.
# ---------------------------------------------------------------------------

_INCR_RE = re.compile(
    r"^(?:\+\+\s*[A-Za-z_]\w*(?:(?:\.|->)[A-Za-z_]\w*|\[[^\]]*\])*"
    r"|[A-Za-z_]\w*(?:(?:\.|->)[A-Za-z_]\w*|\[[^\]]*\])*\s*\+\+)$"
)
_DECR_RE = re.compile(
    r"^(?:--\s*[A-Za-z_]\w*(?:(?:\.|->)[A-Za-z_]\w*|\[[^\]]*\])*"
    r"|[A-Za-z_]\w*(?:(?:\.|->)[A-Za-z_]\w*|\[[^\]]*\])*\s*--)$"
)
_PLUSEQ_RE = re.compile(r"^[A-Za-z_][\w\.\[\]>-]*?\s*\+=\s*(.+)$")
_MINUSEQ_RE = re.compile(r"^[A-Za-z_][\w\.\[\]>-]*?\s*-=\s*(.+)$")
_INT_LIT_RE = re.compile(r"^(0[xX][0-9a-fA-F]+|\d+)[uUlL]*$")


def _int_lit_value(s):
    s = s.strip()
    m = _INT_LIT_RE.match(s)
    if not m:
        return None
    tok = m.group(1)
    return int(tok, 16) if tok.lower().startswith("0x") else int(tok)


def classify_for_update(update):
    """Return one of: stride1, strided, nonconst-stride, multi, no-update,
    other-update."""
    if update is None:
        return "other-update"
    u = update.strip()
    if u == "":
        return "no-update"
    parts = split_top_level(u, ",")
    if len(parts) >= 2:
        return "multi"
    u = parts[0].strip()
    if _INCR_RE.match(u) or _DECR_RE.match(u):
        return "stride1"
    m = _PLUSEQ_RE.match(u) or _MINUSEQ_RE.match(u)
    if m:
        val = _int_lit_value(m.group(1))
        if val is None:
            return "nonconst-stride"
        return "stride1" if val == 1 else "strided"
    return "other-update"


def is_geometric_update(update):
    if update is None:
        return False
    return bool(
        re.search(r"(<<=|>>=)\s*1\b", update)
        or re.search(r"\*=\s*2\b", update)
        or re.search(r"/=\s*2\b", update)
    )


def is_dual_increment_update(update):
    """Update clause with >=2 top-level comma parts, at least 2 of which are
    simple increment/decrement/const-step forms -- the syntactic signature
    of lockstep pointer+index advancement in a for-loop header."""
    if update is None:
        return False
    parts = [p.strip() for p in split_top_level(update, ",")]
    if len(parts) < 2:
        return False
    simple = 0
    for p in parts:
        if _INCR_RE.match(p) or _DECR_RE.match(p):
            simple += 1
            continue
        m = _PLUSEQ_RE.match(p) or _MINUSEQ_RE.match(p)
        if m:
            simple += 1
    return simple >= 2


_PTR_NAME_RE = re.compile(r"ptr", re.IGNORECASE)


def is_pointer_bound_cond(cond):
    """Best-effort: a top-level `lhs (< | !=) rhs` comparison where lhs looks
    like a pointer identifier (contains 'ptr', or is exactly 'p'/'q'/'pp',
    or starts/ends with 'p_'/'_p') or rhs contains 'end' as a substring.
    Naming-convention dependent -- documented blind spot."""
    if cond is None:
        return False
    for m in re.finditer(r"([A-Za-z_]\w*)\s*(<|!=)\s*([A-Za-z_]\w*)", cond):
        lhs, _op, rhs = m.group(1), m.group(2), m.group(3)
        lhsl = lhs.lower()
        if (
            _PTR_NAME_RE.search(lhsl)
            or lhsl in ("p", "q", "pp")
            or lhsl.startswith("p_")
            or lhsl.endswith("_p")
        ):
            return True
        if "end" in rhs.lower():
            return True
    return False


# ---------------------------------------------------------------------------
# Class 2: geometric/shift loop updates -- whole-file occurrence count of the
# four update operators. This is a SUPERSET of "for-loop update clause is
# geometric" (it also matches while-loop-body geometric updates, e.g.
# `for (m = 1; m; m <<= 1)` style bit-iteration where the shift sits as a
# for-loop update, AND `while (m) { ...; m <<= 1; }` style, AND any bare
# doubling/halving statement regardless of whether it sits in a loop at
# all). Blind spot: does not confirm loop membership; a one-off `x <<= 1;`
# outside any loop would still be counted. In the sampled embedded C this
# idiom essentially never appears outside a loop body/update, but this is
# not verified per-site.
# ---------------------------------------------------------------------------

GEOMETRIC_RE = re.compile(r"(<<=|>>=)\s*1\b|\*=\s*2\b|/=\s*2\b")


# ---------------------------------------------------------------------------
# Class 3: bit-slice extraction, two forms. Single level of parens only (no
# nested parens inside the shift/mask sub-expression) -- a documented blind
# spot: `((x + 1) >> k) & m` is missed because of the nested '('.
# ---------------------------------------------------------------------------

BITSLICE_SHIFT_THEN_MASK_RE = re.compile(r"\([^()]*>>[^()]*\)\s*&\s*[A-Za-z0-9_]+")
BITSLICE_MASK_THEN_SHIFT_RE = re.compile(r"\([^()]*&[^()]*\)\s*>>\s*[A-Za-z0-9_]+")


# ---------------------------------------------------------------------------
# Class 4: monotone mask accumulation, `lvalue |= ...`.
# ---------------------------------------------------------------------------

MONOTONE_OR_RE = re.compile(
    r"[A-Za-z_]\w*(?:(?:\.|->)[A-Za-z_]\w*|\[[^\]]*\])*\s*\|="
)


# ---------------------------------------------------------------------------
# Class 5: two-sided clamps, best-effort, two independent sub-detectors:
#   (a) nested ternary  `x < lo ? lo : x > hi ? hi : x`  (and the '>' first
#       mirror, and <=/>=  variants)
#   (b) a pair of `if (x OP bound) x = bound;` statements on the same
#       variable, opposite-direction comparisons, within 6 source lines of
#       each other (proxy for "same clamp block").
# Known blind spots (stated plainly, not fixed): does not catch
# min()/max()/CLAMP()-macro clamps, clamps split across an else-branch
# (`if (x<lo) x=lo; else if (x>hi) x=hi;`), or clamps whose bound expression
# differs textually between the comparison and the assignment (e.g. a cast).
# Macro/function clamp CALLS are counted separately as an informational
# (not officially totalled) number.
# ---------------------------------------------------------------------------

TERNARY_CLAMP_RE = re.compile(
    r"\b([A-Za-z_]\w*)\s*[<>]=?\s*([\w.\[\]]+)\s*\?\s*\2\s*:\s*"
    r"\1\s*[<>]=?\s*([\w.\[\]]+)\s*\?\s*\3\s*:\s*\1\b"
)

IF_ASSIGN_BOUND_RE = re.compile(
    r"\bif\s*\(\s*([A-Za-z_]\w*)\s*(<=|>=|<|>)\s*([\w.\[\]]+)\s*\)\s*\{?\s*"
    r"\1\s*=\s*\3\s*;"
)

CLAMP_MACRO_CALL_RE = re.compile(r"\b(MIN|MAX|CLAMP|LIMIT)\s*\(", re.IGNORECASE)


def count_two_sided_clamps(text):
    ternary_matches = list(TERNARY_CLAMP_RE.finditer(text))
    ternary_count = len(ternary_matches)

    # sequential if-pairs
    hits = []
    for m in IF_ASSIGN_BOUND_RE.finditer(text):
        var, op, bound = m.group(1), m.group(2), m.group(3)
        line = text.count("\n", 0, m.start()) + 1
        direction = "lo" if op in ("<", "<=") else "hi"
        hits.append({"var": var, "dir": direction, "line": line, "used": False})

    pair_count = 0
    for i in range(len(hits)):
        if hits[i]["used"]:
            continue
        for j in range(i + 1, len(hits)):
            if hits[j]["used"]:
                continue
            if hits[j]["line"] - hits[i]["line"] > 6:
                break
            if hits[j]["var"] == hits[i]["var"] and hits[j]["dir"] != hits[i]["dir"]:
                hits[i]["used"] = True
                hits[j]["used"] = True
                pair_count += 1
                break

    macro_calls = len(CLAMP_MACRO_CALL_RE.findall(text))
    return ternary_count, pair_count, macro_calls


# ---------------------------------------------------------------------------
# Class 6: narrowing casts to smaller integer types. Excludes pointer casts
# (`(uint8_t *)`) via a negative lookahead. Only the 5 spellings the task
# names are counted; other narrowing spellings (`(short)`, `(unsigned
# char)`, project-local typedefs) are NOT counted -- documented blind spot.
# ---------------------------------------------------------------------------

NARROW_CAST_RE = re.compile(
    r"\(\s*(uint8_t|uint16_t|int8_t|int16_t|char)\s*\)(?!\s*\*)"
)


# ---------------------------------------------------------------------------
# Class 7: sparse-state switch. Case values that parse as integer literals
# are checked for contiguity; switches with any symbolic (enum/macro) case
# label are counted but left "unclassified" by the script -- the task's
# "manually classify the top few" step is done by hand afterward with
# --dump-switches output as the source list.
# ---------------------------------------------------------------------------

_CHAR_LIT_RE = re.compile(r"^'(\\.|[^'])'$")
_ESCAPES = {"\\0": 0, "\\n": 10, "\\t": 9, "\\r": 13, "\\\\": 92, "\\'": 39}


def try_parse_case_int(s):
    s = s.strip()
    v = _int_lit_value(s)
    if v is not None:
        return v
    m = _CHAR_LIT_RE.match(s)
    if m:
        ch = m.group(1)
        if ch in _ESCAPES:
            return _ESCAPES[ch]
        if not ch.startswith("\\"):
            return ord(ch)
    return None


def classify_switch(cases):
    if not cases:
        return "empty"
    values = [try_parse_case_int(c) for c in cases]
    if any(v is None for v in values):
        return "symbolic-unclassified"
    if len(set(values)) != len(values):
        return "sparse-dup"
    span = max(values) - min(values) + 1
    return "contiguous" if span == len(values) else "sparse"


# ---------------------------------------------------------------------------
# Class 9: zigzag / byte-swap idioms.
#   - zigzag encode:  (x << 1) ^ (x >> ...
#   - zigzag decode:  (x >> 1) ^ -(x & 1)   [ '-' and inner parens optional ]
#   - byte-swap shift-or: two or more `(<< | >>) (8|16|24)` shift-by-a-byte-
#     boundary operators combined by '|' within the same statement (a
#     `;`-delimited window is not tracked here; instead any '|' occurring
#     between two such shift tokens with no ';' in between counts).
# Bit-reversal is NOT separately detected -- no reliable syntactic signature
# distinct from the geometric-loop (class 2) and mask-shift (class 3)
# patterns already counted; stated as a limitation, not attempted.
# `__builtin_bswapNN` / `bswap16/32/64`-style library calls are reported as
# an informational side count, NOT included in the class-9 total (the task
# asks specifically for the shift-or idiom, not the library-call idiom).
# ---------------------------------------------------------------------------

ZIGZAG_ENCODE_RE = re.compile(
    r"\(\s*[\w.\[\]>-]+\s*<<\s*1\s*\)\s*\^\s*\(\s*[\w.\[\]>-]+\s*>>"
)
ZIGZAG_DECODE_RE = re.compile(
    r"\(\s*[\w.\[\]>-]+\s*>>\s*1\s*\)\s*\^\s*-?\(?\s*[\w.\[\]>-]+\s*&\s*1\b"
)
_SHIFT_BYTE_RE = re.compile(r"(<<|>>)\s*(8|16|24)\b")
BSWAP_BUILTIN_RE = re.compile(r"\b(__builtin_bswap\d+|bswap(16|32|64))\b")


def count_byteswap_shiftor(text):
    matches = list(_SHIFT_BYTE_RE.finditer(text))
    count = 0
    i = 0
    while i < len(matches) - 1:
        a, b = matches[i], matches[i + 1]
        between = text[a.end():b.start()]
        if "|" in between and ";" not in between:
            count += 1
            i += 2
        else:
            i += 1
    return count


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------

def analyze_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    loc = len(raw.splitlines())
    text = strip_comments_and_strings(raw)

    result = {"path": path, "loc": loc}

    # --- class 1: for-loop stride classification ---
    for_loops = find_for_loops(text)
    for_buckets = {
        "stride1": 0, "strided": 0, "nonconst-stride": 0,
        "multi": 0, "no-update": 0, "other-update": 0,
    }
    dual_increment = 0
    ptr_bound_for = 0
    for lp in for_loops:
        bucket = classify_for_update(lp["update"])
        for_buckets[bucket] += 1
        if is_dual_increment_update(lp["update"]):
            dual_increment += 1
        if is_pointer_bound_cond(lp["cond"]):
            ptr_bound_for += 1
    result["for_total"] = len(for_loops)
    result["for_buckets"] = for_buckets

    # --- while loops (denominator + pointer-bound source) ---
    while_loops = find_while_loops(text)
    ptr_bound_while = sum(1 for w in while_loops if is_pointer_bound_cond(w["cond"]))
    result["while_total"] = len(while_loops)

    result["lockstep_dual_increment"] = dual_increment
    result["lockstep_ptr_bound"] = ptr_bound_for + ptr_bound_while

    # --- class 2: geometric/shift loop updates (whole-file occurrence) ---
    result["geometric_shift"] = len(GEOMETRIC_RE.findall(text))

    # --- class 3: bit-slice extraction ---
    result["bitslice_shift_then_mask"] = len(BITSLICE_SHIFT_THEN_MASK_RE.findall(text))
    result["bitslice_mask_then_shift"] = len(BITSLICE_MASK_THEN_SHIFT_RE.findall(text))

    # --- class 4: monotone mask accumulation ---
    result["monotone_or"] = len(MONOTONE_OR_RE.findall(text))

    # --- class 5: two-sided clamps ---
    ternary_n, pair_n, macro_n = count_two_sided_clamps(text)
    result["clamp_ternary"] = ternary_n
    result["clamp_if_pair"] = pair_n
    result["clamp_macro_call_informational"] = macro_n

    # --- class 6: narrowing casts ---
    result["narrowing_cast"] = len(NARROW_CAST_RE.findall(text))

    # --- class 7: sparse-state switch ---
    switches = find_switches(text)
    sw_classes = {"contiguous": 0, "sparse": 0, "sparse-dup": 0,
                  "symbolic-unclassified": 0, "empty": 0}
    for sw in switches:
        sw_classes[classify_switch(sw["cases"])] += 1
    result["switch_total"] = len(switches)
    result["switch_classes"] = sw_classes
    result["_switches_raw"] = switches  # for --dump-switches

    # --- class 8: lockstep / pointer-bound loops (union count) ---
    result["lockstep_total"] = (
        dual_increment + ptr_bound_for + ptr_bound_while
    )

    # --- class 9: zigzag / byte-swap ---
    zz_enc = len(ZIGZAG_ENCODE_RE.findall(text))
    zz_dec = len(ZIGZAG_DECODE_RE.findall(text))
    bswap_shiftor = count_byteswap_shiftor(text)
    result["zigzag_encode"] = zz_enc
    result["zigzag_decode"] = zz_dec
    result["byteswap_shiftor"] = bswap_shiftor
    result["zigzag_byteswap_total"] = zz_enc + zz_dec + bswap_shiftor
    result["bswap_builtin_informational"] = len(BSWAP_BUILTIN_RE.findall(text))

    return result


AGG_KEYS = [
    "loc", "for_total", "while_total",
    "geometric_shift",
    "bitslice_shift_then_mask", "bitslice_mask_then_shift",
    "monotone_or",
    "clamp_ternary", "clamp_if_pair", "clamp_macro_call_informational",
    "narrowing_cast",
    "switch_total",
    "lockstep_dual_increment", "lockstep_ptr_bound", "lockstep_total",
    "zigzag_encode", "zigzag_decode", "byteswap_shiftor",
    "zigzag_byteswap_total", "bswap_builtin_informational",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="base directory")
    ap.add_argument("--files", nargs="+", required=True,
                     help="file paths, relative to --dir unless absolute")
    ap.add_argument("--per-file", action="store_true",
                     help="also print the full per-file breakdown")
    ap.add_argument("--dump-switches", action="store_true",
                     help="print every switch's raw case-label list, for manual "
                          "sparse/contiguous classification")
    args = ap.parse_args()

    paths = []
    for f in args.files:
        p = f if os.path.isabs(f) else os.path.join(args.dir, f)
        paths.append(p)

    per_file = []
    for p in paths:
        if not os.path.isfile(p):
            print("ERROR: not a file: %s" % p, file=sys.stderr)
            sys.exit(1)
        per_file.append(analyze_file(p))

    print("=== LoC per file (wc -l equivalent: physical line count) ===")
    total_loc = 0
    for r in per_file:
        print("%6d  %s" % (r["loc"], r["path"]))
        total_loc += r["loc"]
    print("%6d  TOTAL (%d files)" % (total_loc, len(per_file)))
    print()

    agg = {k: 0 for k in AGG_KEYS}
    for_buckets_agg = {"stride1": 0, "strided": 0, "nonconst-stride": 0,
                        "multi": 0, "no-update": 0, "other-update": 0}
    sw_classes_agg = {"contiguous": 0, "sparse": 0, "sparse-dup": 0,
                       "symbolic-unclassified": 0, "empty": 0}
    for r in per_file:
        for k in AGG_KEYS:
            agg[k] += r[k]
        for k, v in r["for_buckets"].items():
            for_buckets_agg[k] += v
        for k, v in r["switch_classes"].items():
            sw_classes_agg[k] += v

    if args.per_file:
        print("=== per-file breakdown ===")
        for r in per_file:
            print("--- %s ---" % r["path"])
            for k in AGG_KEYS:
                if k == "loc":
                    continue
                print("  %-32s %d" % (k, r[k]))
            print("  for_buckets: %s" % r["for_buckets"])
            print("  switch_classes: %s" % r["switch_classes"])
        print()

    print("=== AGGREGATE (%d files, %d total LoC) ===" % (len(per_file), total_loc))
    print()
    print("class 1: for-loop stride classification")
    print("  for-loops total          : %d" % agg["for_total"])
    print("  stride-1 (unit step)     : %d" % for_buckets_agg["stride1"])
    print("  strided (|step| > 1)     : %d" % for_buckets_agg["strided"])
    print("  non-constant step        : %d" % for_buckets_agg["nonconst-stride"])
    print("  multi-clause update      : %d" % for_buckets_agg["multi"])
    print("  no update clause         : %d" % for_buckets_agg["no-update"])
    print("  other/unclassified update: %d" % for_buckets_agg["other-update"])
    print()
    print("class 2: geometric/shift loop updates (<<=1, >>=1, *=2, /=2)")
    print("  occurrences               : %d" % agg["geometric_shift"])
    print()
    print("class 3: bit-slice extraction")
    print("  (expr >> k) & mask form    : %d" % agg["bitslice_shift_then_mask"])
    print("  (expr & mask) >> k form    : %d" % agg["bitslice_mask_then_shift"])
    print("  total                      : %d" % (agg["bitslice_shift_then_mask"] + agg["bitslice_mask_then_shift"]))
    print()
    print("class 4: monotone mask accumulation (x |= ...)")
    print("  occurrences                : %d" % agg["monotone_or"])
    print()
    print("class 5: two-sided clamps (best-effort)")
    print("  nested-ternary form         : %d" % agg["clamp_ternary"])
    print("  sequential if-pair form      : %d" % agg["clamp_if_pair"])
    print("  total                        : %d" % (agg["clamp_ternary"] + agg["clamp_if_pair"]))
    print("  [informational, not totalled] MIN/MAX/CLAMP/LIMIT macro calls: %d"
          % agg["clamp_macro_call_informational"])
    print()
    print("class 6: narrowing casts ((uint8_t)/(uint16_t)/(int8_t)/(int16_t)/(char))")
    print("  occurrences                  : %d" % agg["narrowing_cast"])
    print()
    print("class 7: sparse-state switch")
    print("  switches total               : %d" % agg["switch_total"])
    print("  contiguous (numeric)         : %d" % sw_classes_agg["contiguous"])
    print("  sparse (numeric, non-contig) : %d" % sw_classes_agg["sparse"])
    print("  sparse-dup (repeated values) : %d" % sw_classes_agg["sparse-dup"])
    print("  symbolic (unclassified)      : %d" % sw_classes_agg["symbolic-unclassified"])
    print("  empty (no case labels)       : %d" % sw_classes_agg["empty"])
    print()
    print("class 8: lockstep pointer iteration")
    print("  dual-increment for-loop update: %d" % agg["lockstep_dual_increment"])
    print("  pointer-bound loop condition  : %d" % agg["lockstep_ptr_bound"])
    print("  union total                   : %d" % agg["lockstep_total"])
    print()
    print("class 9: zigzag / byte-swap idioms")
    print("  zigzag encode  (x<<1)^(x>>..) : %d" % agg["zigzag_encode"])
    print("  zigzag decode  (x>>1)^-(x&1)  : %d" % agg["zigzag_decode"])
    print("  byte-swap shift-or            : %d" % agg["byteswap_shiftor"])
    print("  total                         : %d" % agg["zigzag_byteswap_total"])
    print("  [informational, not totalled] __builtin_bswap*/bswapNN calls: %d"
          % agg["bswap_builtin_informational"])
    print()
    print("denominator for the value-shaping-vs-countable-loops ratio")
    print("  countable loops (for + while): %d" % (agg["for_total"] + agg["while_total"]))
    value_shaping = (
        agg["geometric_shift"]
        + agg["bitslice_shift_then_mask"] + agg["bitslice_mask_then_shift"]
        + agg["monotone_or"]
        + agg["clamp_ternary"] + agg["clamp_if_pair"]
        + agg["narrowing_cast"]
        + agg["zigzag_byteswap_total"]
    )
    print("  value-shaping sites (2+3+4+5+6+9): %d" % value_shaping)
    denom = agg["for_total"] + agg["while_total"]
    if denom:
        print("  ratio value-shaping / countable loops: %.2f" % (value_shaping / denom))

    if args.dump_switches:
        print()
        print("=== switch dump (for manual sparse/contiguous spot-check) ===")
        for r in per_file:
            for sw in r["_switches_raw"]:
                cls = classify_switch(sw["cases"])
                print("%s:%d  [%s]  cases=%d  %s" % (
                    r["path"], sw["line"], cls, len(sw["cases"]), sw["cases"]))


if __name__ == "__main__":
    main()
