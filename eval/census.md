# Leg C — shape-frequency census on public embedded codebases

**Purpose.** Establish that the shapes in the folding pattern catalogue
(`folding.tex`, §"The pattern catalogue") are common in real, public embedded C —
so the precision gains in Legs A/B are not strawmen. Every number below is a
**syntactic occurrence count**, reproduced by one command against
`eval/census.py`, over twelve public C codebases pinned at a commit sha (the
original four plus eight added in a later pass), plus one C++ codebase
(Chromium) reported separately as context only, never folded into the C
totals. No private codebase appears anywhere in this document or in the
counted sources.

**Discipline (per `eval/DESIGN.md`, Leg C):**
- Counting is syntactic (regex + paren-balancing over comment/string-stripped
  source), not semantic. A count is an **upper bound on the number of sites
  where a fold could apply**, never a claim that folding's validity conditions
  (`folding.tex` §"The soundness obligation") hold at that site — no def-use,
  no aliasing, no macro expansion, no type checking is performed.
- Zeros are reported as zeros; a class that returns 0 for a codebase is stated
  as such, not omitted.
- Every regex/parsing rule is defined precisely below and lives in
  `eval/census.py`; every number reproduces with the one command shown per
  codebase.
- Classes where the regex is judged too weak to trust as a frequency measure
  are flagged explicitly in "Known-weak classes" below, with what was done
  about it (manual spot-check, not a fix — fixing would break the "syntactic
  occurrence, one script" reproducibility contract).

## Method summary

`eval/census.py` (single script, unchanged across every codebase in this
document including the eight added later — reused byte-for-byte, no other
tooling):

1. Strips `/* */` and `//` comments and blanks the contents of `"..."` and
   `'...'` literals (character positions preserved) so matches inside comments
   or string data don't inflate counts.
2. Extracts `for(...)`/`while(...)` clauses and `switch { }` bodies by
   paren/brace balancing (not a full C parser — no preprocessor expansion, no
   nested-switch exclusion; see blind spots below).
3. Applies one regex or structural rule per shape class (defined in the class
   tables below; source of truth is `eval/census.py`).

Invocation used for every codebase in this document:
```
python3 eval/census.py --dir <checkout-dir> --files <file...>
```
(`--per-file` prints the same breakdown per file instead of only aggregated;
`--dump-switches` prints every switch's raw case-label list, used here for the
manual sparse/contiguous spot-check in class 7.)

## Shape classes — precise definitions

| # | Class | Rule (see `eval/census.py`) |
|---|---|---|
| 1 | For-loop stride | Parse `for(init;cond;update)`. `update` classified: `stride1` = `x++`/`++x`/`x--`/`--x`/`x+=1`/`x-=1`; `strided` = `x+=c` or `x-=c` for integer literal `c>1` (the **c>1 threshold is applied symmetrically to both `+=` and `-=`** — the task wording was ambiguous on this point; this is the fixed, documented choice); `nonconst-stride` = `+=`/`-=` by a non-literal; `multi`/`no-update`/`other-update` = everything else. Total = all matched `for(...)` headers. |
| 2 | Geometric/shift loop | Whole-file regex `(<<=\|>>=)\s*1\b \| \*=\s*2\b \| /=\s*2\b`. **Not** restricted to loop-update position (superset — see blind spots). |
| 3 | Bit-slice extraction | Two regexes, single paren level only: `\([^()]*>>[^()]*\)\s*&\s*IDENT` (shift-then-mask) and `\([^()]*&[^()]*\)\s*>>\s*IDENT` (mask-then-shift). |
| 4 | Monotone mask accumulation | `IDENT(.field\|->field\|[idx])*\s*\|=` |
| 5 | Two-sided clamp | Best-effort, two sub-forms: (a) nested ternary `x OP a ? a : x OP b ? b : x`; (b) a pair of `if (x OP bound) x = bound;` statements on the same variable with opposite-direction comparisons within 6 source lines. MIN/MAX/CLAMP/LIMIT macro-call sites counted separately, informationally, not in the class total. |
| 6 | Narrowing cast | `\((uint8_t\|uint16_t\|int8_t\|int16_t\|char)\)` not followed by `*` (excludes pointer casts). Only these 5 spellings — see blind spots. |
| 7 | Sparse-state switch | All `switch(...)  { }` bodies; case labels parsed as int literals (decimal/hex/char) where possible and checked for contiguity (`max-min+1 == count`); switches with any non-literal (enum/macro) case label are counted but left `symbolic-unclassified` by the script — resolved by hand for a spot-check (see class 7 results). |
| 8 | Lockstep pointer iteration | Union of: (a) for-loop update clauses with ≥2 top-level comma-separated simple step expressions (`p++, i++`-style); (b) `for`/`while` conditions of the form `lhs (< \| !=) rhs` where `lhs` looks like a pointer name (`ptr` substring, or `p`/`q`/`pp`, or `p_`/`_p` affixes) or `rhs` contains `end` as a substring. |
| 9 | ZigZag / byte-swap | `zigzag_encode` = `(x << 1) ^ (x >> ...`; `zigzag_decode` = `(x >> 1) ^ -(x & 1)`(paren-optional); `byteswap_shiftor` = two `(<<\|>>) (8\|16\|24)` shift tokens joined by `\|` with no `;` between them in the same statement. Bit-reversal is **not** separately detected (no signature distinct from classes 2/3 — stated as a limitation, not attempted). `__builtin_bswap*`/`bswapNN` calls counted informationally, not in the total (task asks for the shift-or idiom, not the library-call idiom). |

Denominator for the frequency ratio: "countable loops" = total `for` + total
`while` headers matched (structural counts, classes above). "Value-shaping
sites" = classes {2, 3, 4, 5, 6, 9} summed — the bit-slice/shift/mask/clamp/
narrowing-cast/encoding-transport shapes, mirroring the motivating sentence in
`folding.tex` §"Value folds": *"bit-slice masks, shifts, narrowing casts and
flag accumulations outnumber countable loops several-fold."*

---

## Codebase 1: nanopb

- Upstream: `https://github.com/nanopb/nanopb.git`
- Pinned commit: `4e73df5a72e470a8195c3efdaf1d0e45e22c3af7`
- Verified via: `git remote get-url origin` and `git log -1 --format=%H` on a
  local checkout already at this commit.
- Files counted (core codec sources, per task scope): `pb_encode.c`,
  `pb_decode.c`, `pb_common.c`

Reproduce:
```
git clone https://github.com/nanopb/nanopb.git
git -C nanopb checkout 4e73df5a72e470a8195c3efdaf1d0e45e22c3af7
python3 eval/census.py --dir nanopb --files pb_encode.c pb_decode.c pb_common.c
```

| File | LoC (physical lines) |
|---|---|
| pb_encode.c | 1006 |
| pb_decode.c | 1763 |
| pb_common.c | 388 |
| **Total** | **3157** |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 8 / 8 / 0 |
| 2. geometric/shift loop updates | 4 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 29 / 0 = **29** |
| 4. monotone mask `\|=` | 11 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 0) |
| 6. narrowing casts | 0 |
| 7. switches (total / contiguous / sparse / symbolic) | 9 / 1 / 0 / 8 |
| 8. lockstep (dual-incr / ptr-bound) | 0 / 0 = **0** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 2 = **2** |
| countable loops (for+while) | 32 |
| value-shaping sites (2+3+4+5+6+9) | 46 |
| **ratio, value-shaping / countable loops** | **1.44** |
| ratio, value-shaping / **for-loops only** | **5.75** |

**Class 7 manual spot-check (all 8 symbolic switches resolved by reading
`pb.h`):**
- `PB_LTYPE_*` switch (`pb_encode.c:373,684`, `pb_decode.c:419`; 11 cases,
  values `0x00`–`0x09`, `0x0B`): **near-contiguous with one gap** — `0x0A`
  (`PB_LTYPE_EXTENSION`) is deliberately excluded from these switches and
  handled elsewhere (default branch).
- `PB_WT_*` wire-type switch (`pb_decode.c:320,341`; 5 cases): values
  `{0,1,2,5,255}` — **sparse**, with `255` (`PB_WT_PACKED`) as an
  out-of-band sentinel.
- `PB_HTYPE_*` switch (`pb_decode.c:490,652`; 4 cases): values
  `{0x00,0x10,0x20,0x30}` = `{0,16,32,48}` — **sparse, deliberately
  nibble-spaced** (packed into a separate nibble of a one-byte field
  alongside `PB_LTYPE_MASK`).
- `PB_ATYPE_*` switch (`pb_decode.c:847`; 3 cases): values
  `{0x00,0x80,0x40}` = `{0,128,64}` — **sparse, bit-packed** (top two bits
  of the same field).
- The one auto-classified `contiguous` switch (`pb_common.c:20`, values
  `{0,1,2}`) is genuinely contiguous.

  **Net finding:** all 8 of nanopb's symbolic switches are sparse when
  resolved — the automated numeric-only classifier's 1-contiguous/0-sparse/
  8-unclassified split understates sparse-switch prevalence by construction
  (it cannot see symbolic case labels); true split for this file set is
  **1 contiguous / 8 sparse**.

---

## Codebase 2: libcsp

- Upstream: `https://github.com/libcsp/libcsp.git`
- Pinned commit: `57c5c4857f30dd083bb373fbc79a65c6ae9f1a62`
- Verified via: `git remote get-url origin` and `git log -1 --format=%H` on a
  local checkout already at this commit.
- Files counted: all 23 files matching `src/*.c` (top-level only, not
  `src/arch/`, `src/bindings/`, `src/crypto/`, `src/drivers/`,
  `src/interfaces/`).

Reproduce:
```
git clone https://github.com/libcsp/libcsp.git
git -C libcsp checkout 57c5c4857f30dd083bb373fbc79a65c6ae9f1a62
python3 eval/census.py --dir libcsp --files src/csp_bridge.c src/csp_buffer.c \
  src/csp_conn.c src/csp_crc32.c src/csp_debug.c src/csp_dedup.c \
  src/csp_hex_dump.c src/csp_id.c src/csp_iflist.c src/csp_init.c \
  src/csp_io.c src/csp_port.c src/csp_promisc.c src/csp_qfifo.c \
  src/csp_rdp.c src/csp_rdp_queue.c src/csp_route.c src/csp_rtable_cidr.c \
  src/csp_rtable_stdio.c src/csp_service_handler.c src/csp_services.c \
  src/csp_sfp.c src/csp_yaml.c
```

| File | LoC | File | LoC |
|---|---|---|---|
| csp_bridge.c | 69 | csp_promisc.c | 62 |
| csp_buffer.c | 225 | csp_qfifo.c | 65 |
| csp_conn.c | 426 | csp_rdp.c | 975 |
| csp_crc32.c | 146 | csp_rdp_queue.c | 117 |
| csp_debug.c | 30 | csp_route.c | 298 |
| csp_dedup.c | 48 | csp_rtable_cidr.c | 144 |
| csp_hex_dump.c | 58 | csp_rtable_stdio.c | 118 |
| csp_id.c | 282 | csp_service_handler.c | 336 |
| csp_iflist.c | 300 | csp_services.c | 223 |
| csp_init.c | 52 | csp_sfp.c | 269 |
| csp_io.c | 437 | csp_yaml.c | 295 |
| csp_port.c | 161 | | |
| **Total (23 files)** | **5136** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 21 / 19 / 0 (2 other-update) |
| 2. geometric/shift loop updates | 0 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 12 / 0 = **12** |
| 4. monotone mask `\|=` | 15 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 0) |
| 6. narrowing casts | 8 |
| 7. switches (total / contiguous / sparse / symbolic) | 3 / 0 / 0 / 3 |
| 8. lockstep (dual-incr / ptr-bound) | 0 / 0 = **0** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 0 = **0** |
| countable loops (for+while) | 48 |
| value-shaping sites (2+3+4+5+6+9) | 35 |
| **ratio, value-shaping / countable loops** | **0.73** |
| ratio, value-shaping / **for-loops only** | **1.67** |

**Class 7 manual spot-check (all 3 symbolic switches resolved by reading
`csp_conn.h`, `csp_cmp.h`, `csp_types.h`):**
- RDP connection-state switch (`csp_rdp.c:496`; `csp_rdp_state_t`, 5 cases):
  values `{0,1,2,3,4}` — **contiguous** (plain sequential enum).
- CMP management-command switch (`csp_service_handler.c:208`; 9 cases over
  `#define CSP_CMP_*`): values `{1,2,3,4,5,6,7,8,9}` — **contiguous**
  (on-wire opcodes assigned sequentially, no gaps).
- Service-port switch (`csp_service_handler.c:261`; `csp_service_port_t`, 7
  cases): values `{0,1,2,3,4,5,6}` — **contiguous** (plain sequential enum).

  **Net finding:** unlike nanopb, all 3 of libcsp's symbolic switches resolve
  to genuinely **contiguous** ranges — the true split here is 3 contiguous /
  0 sparse, the opposite conclusion a naive "symbolic ⇒ assume sparse"
  heuristic would reach. This is exactly why the census script leaves
  symbolic switches unclassified rather than guessing.

**Lockstep/pointer-bound absence (class 8 = 0) is a genuine finding, not a
regex miss:** a targeted search for pointer-named identifiers (`ptr`
substring, or `p`/`q`) compared against anything, and for `end`-named bounds,
found **zero** matches anywhere in these 23 files. libcsp's buffer handling
goes through length-prefixed `csp_packet_t`/`csp_buffer_t` objects rather than
raw pointer-walk loops in this file set — the abstraction choice, not a
detector weakness.

---

## Codebase 3: zlib

- Upstream: `https://github.com/madler/zlib.git`
- Pinned commit: `e3dc0a85b7032e98380dec011bc8f2c2ee0d8fca`
- Obtained via `git clone --depth 1` (shallow clone), sha read via
  `git log -1 --format=%H` immediately after.
- Files counted: all `*.c` files at repo root (15 files: `adler32.c`,
  `compress.c`, `crc32.c`, `deflate.c`, `gzclose.c`, `gzlib.c`, `gzread.c`,
  `gzwrite.c`, `infback.c`, `inffast.c`, `inflate.c`, `inftrees.c`, `trees.c`,
  `uncompr.c`, `zutil.c`).

Reproduce:
```
git clone https://github.com/madler/zlib.git
git -C zlib checkout e3dc0a85b7032e98380dec011bc8f2c2ee0d8fca
python3 eval/census.py --dir zlib --files adler32.c compress.c crc32.c \
  deflate.c gzclose.c gzlib.c gzread.c gzwrite.c infback.c inffast.c \
  inflate.c inftrees.c trees.c uncompr.c zutil.c
```

| File | LoC | File | LoC |
|---|---|---|---|
| adler32.c | 164 | infback.c | 579 |
| compress.c | 99 | inffast.c | 321 |
| crc32.c | 983 | inflate.c | 1413 |
| deflate.c | 2185 | inftrees.c | 424 |
| gzclose.c | 23 | trees.c | 1119 |
| gzlib.c | 609 | uncompr.c | 101 |
| gzread.c | 668 | zutil.c | 312 |
| gzwrite.c | 701 | | |
| **Total (15 files)** | **9701** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 81 / 59 / 0 (1 multi, 21 no-update) |
| 2. geometric/shift loop updates | 10 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 16 / 6 = **22** |
| 4. monotone mask `\|=` | 12 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: **7**) |
| 6. narrowing casts | 0 |
| 7. switches (total / contiguous / sparse / symbolic) | 12 / 3 / 4 / 5 |
| 8. lockstep (dual-incr / ptr-bound) | 0 / 6 = **6** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 4 = **4** |
| countable loops (for+while) | 212 |
| value-shaping sites (2+3+4+5+6+9) | 48 |
| **ratio, value-shaping / countable loops** | **0.23** |
| ratio, value-shaping / **for-loops only** | **0.59** |

**Class 7 manual spot-check (2 of 5 symbolic switches read in full):**
- `gzlib.c:117` (mode-flag switch, 14 cases): case labels are single-char
  literals (`'r'`,`'w'`,`'a'`,`'+'`,`'b'`,`'e'`,`'x'`,`'f'`,`'h'`,`'R'`,`'F'`,
  ...) — **note:** the script's comment/string-stripping stage blanks char
  literal *contents* (by design, to avoid matching regex fragments inside
  string data), which means these case labels appear as blank strings in the
  auto-classifier's output; this switch is only correctly identified as
  sparse by manual reading of the source, not automatically. ASCII values
  (`'r'`=114, `'w'`=119, `'a'`=97, `'+'`=43, ...) are **highly sparse**
  (fopen-mode-style flag-character dispatch — textbook pattern 14).
- `inflate.c:505` (`inflate_mode` state switch, 35 cases): the enum is
  declared `HEAD = 16180` then auto-incrementing (`FLAGS`, `TIME`, ... no
  further explicit values) — **contiguous** (`16180..16214`). **However**
  this switch's case list as extracted by the script also includes `'0'`,
  `'1'`, `'2'`, `STORED`, `COPY_`, `COPY`, `TABLE`, ... — these belong to a
  **nested** `switch (BITS(2))` inside the `TYPEDO` case body. The script
  does not exclude nested-switch bodies from the outer switch's case list (a
  documented blind spot in `census.py`'s `find_switches`); this is the one
  place in the four-codebase sample where that blind spot is visibly
  triggered. The true `inflate_mode` switch is 35-9=26-ish top-level cases,
  all contiguous; a handful of the listed labels belong to the inner
  block-type switch instead.

  The remaining 3 symbolic switches (`gzread.c:252` `LOOK`/`COPY`/`GZIP`,
  `infback.c:227` similar inflate-state pattern, `inftrees.c:190`
  `CODES`/`LENS`/`DISTS`) were not individually resolved — flagged as
  unclassified rather than guessed, consistent with the method stated above.

---

## Codebase 4: FreeRTOS kernel

- Upstream: `https://github.com/FreeRTOS/FreeRTOS-Kernel.git`
- Pinned commit: `ce221a8bb468e462ca6b435cef66a9636e00baf4`
- Obtained via `git clone --depth 1` (shallow clone), sha read via
  `git log -1 --format=%H` immediately after.
- Files counted: all `*.c` files at repo root. The task named 6
  (`tasks.c`, `queue.c`, `list.c`, `stream_buffer.c`, `timers.c`,
  `event_groups.c`); the root also contains `croutine.c` (a 7th root `*.c`
  file, the deprecated co-routine module) — included for completeness under
  the stated selection rule "root `*.c` files", noted here transparently
  rather than silently dropped or silently added.

Reproduce:
```
git clone https://github.com/FreeRTOS/FreeRTOS-Kernel.git
git -C FreeRTOS-Kernel checkout ce221a8bb468e462ca6b435cef66a9636e00baf4
python3 eval/census.py --dir FreeRTOS-Kernel --files tasks.c queue.c list.c \
  stream_buffer.c timers.c event_groups.c croutine.c
```

| File | LoC |
|---|---|
| tasks.c | 8967 |
| queue.c | 3391 |
| list.c | 248 |
| stream_buffer.c | 1757 |
| timers.c | 1343 |
| event_groups.c | 887 |
| croutine.c | 407 |
| **Total (7 files)** | **17000** |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 37 / 25 / 0 (8 no-update, 4 other) |
| 2. geometric/shift loop updates | 0 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 0 / 0 = **0** |
| 4. monotone mask `\|=` | 12 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 0) |
| 6. narrowing casts | 60 |
| 7. switches (total / contiguous / sparse / symbolic) | 4 / 0 / 0 / 4 |
| 8. lockstep (dual-incr / ptr-bound) | 0 / 4 = **4** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 0 = **0** |
| countable loops (for+while) | 78 |
| value-shaping sites (2+3+4+5+6+9) | 72 |
| **ratio, value-shaping / countable loops** | **0.92** |
| ratio, value-shaping / **for-loops only** | **1.95** |

Class 3 (bit-slice) = 0 is confirmed genuine, not a regex miss: these 7 files
contain **zero** `>>` tokens at all (checked directly), so no shift-based
bit-slice idiom can appear — the kernel's list/scheduler/queue logic in this
file set doesn't do bit-level field extraction (it lives elsewhere in the
tree, e.g. port layers, out of scope here).

**Class 7 manual spot-check (2 of 4 symbolic switches read in full):**
- `tasks.c:7459` (`eTaskState`, 6 cases): values `{0,1,2,3,4,5}` —
  **contiguous** (plain sequential enum).
- `tasks.c:8040,8183` (`eNotifyAction`, 5 cases, same enum both sites):
  values `{0,1,2,3,4}` — **contiguous** (plain sequential enum).
- `timers.c:995` (`tmrCOMMAND_*`, 9 cases): the defining constants were not
  located in the 7-file set (defined outside it); **not resolved** — left
  unclassified rather than assumed, though FreeRTOS's consistent style in the
  two resolved cases suggests contiguous is likely here too.

---

## Codebase 5: Linux kernel (three pinned subsystem slices, reported as separate rows)

- Upstream (canonical public mirror): `https://github.com/torvalds/linux.git`
  (also mirrored at `https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git`)
- Local checkout used: a private-workspace checkout (path omitted; read-only;
  per task scope, only `git -C <path> log -1 --format=%H` and
  `git -C <path> remote get-url origin` were run against it — no other git
  commands, no state changes).
- Pinned commit: `8934827db5403eae57d4537114a9ff88b0a8460f`
- **Note on origin:** `git remote get-url origin` on this local checkout
  returned a local filesystem path rather than a GitHub URL, i.e. this
  checkout is itself cloned from another local mirror, not directly
  from GitHub. Reported here transparently per the task's read-only-git
  constraint (only `log -1`/`remote get-url origin` were permitted, so this
  could not be chased further); the commit sha above is independently
  checkable against the canonical public upstream URLs given.
- Three subsystem slices censused separately, each as its own row in the
  aggregate/ratio tables below (not merged into one Linux row), per task
  instruction.

### 5a. lib/ core utility C files (curated ~24-file "plain algorithms" subset)

`lib/*.c` has 212 files total, most of which are kernel-infrastructure glue
(kobject/sysfs, notifier-error-injection shims, debugobjects, self-test
harnesses, device-tree/fdt helpers, per-arch libgcc intrinsics) rather than
"plain algorithms." The task asked for the curated ~24-file subset — selected
by hand from the full `lib/*.c` listing using this rule: **pure data-structure
and value-transform code** (trees, hash tables, sorting/searching, string/bit
primitives, one general-purpose codec) **with no kernel-infrastructure
coupling** (no kobject/sysfs, no notifier chains, no `_test.c`/`_benchmark.c`
self-test harnesses, no device-tree/fdt, no per-arch intrinsics). Excluded
close calls: `glob.c`, `hexdump.c`, `union_find.c`, `win_minmax.c`,
`textsearch.c`+`ts_*.c` (Boyer-Moore/KMP/FSM search engine), `kstrtox.c`,
`cmdline.c`, `parser.c`, `vsprintf.c`, `generic-radix-tree.c` — all
defensible "plain algorithm" candidates too, dropped only to keep the curated
set close to the ~24 the task named; the selection is a judgment call, not a
canonical list, and is stated here so it can be second-guessed.

Selected files (24): `base64.c`, `bitmap.c`, `bitrev.c`, `bsearch.c`,
`btree.c`, `checksum.c`, `hweight.c`, `idr.c`, `interval_tree.c`, `kfifo.c`,
`list_sort.c`, `llist.c`, `maple_tree.c`, `min_heap.c`, `plist.c`,
`radix-tree.c`, `rbtree.c`, `rhashtable.c`, `siphash.c`, `sort.c`, `string.c`,
`uuid.c`, `xarray.c`, `xxhash.c`.

Reproduce:
```
python3 eval/census.py --dir /path/to/linux --files lib/base64.c lib/bitmap.c \
  lib/bitrev.c lib/bsearch.c lib/btree.c lib/checksum.c lib/hweight.c \
  lib/idr.c lib/interval_tree.c lib/kfifo.c lib/list_sort.c lib/llist.c \
  lib/maple_tree.c lib/min_heap.c lib/plist.c lib/radix-tree.c lib/rbtree.c \
  lib/rhashtable.c lib/siphash.c lib/sort.c lib/string.c lib/uuid.c \
  lib/xarray.c lib/xxhash.c
```

### file listing (24 files)

| File | LoC | File | LoC |
|---|---|---|---|
| lib/base64.c | 184 | lib/bitmap.c | 888 |
| lib/bitrev.c | 47 | lib/bsearch.c | 36 |
| lib/btree.c | 795 | lib/checksum.c | 164 |
| lib/hweight.c | 68 | lib/idr.c | 668 |
| lib/interval_tree.c | 156 | lib/kfifo.c | 595 |
| lib/list_sort.c | 257 | lib/llist.c | 94 |
| lib/maple_tree.c | 7268 | lib/min_heap.c | 70 |
| lib/plist.c | 311 | lib/radix-tree.c | 1608 |
| lib/rbtree.c | 601 | lib/rhashtable.c | 1256 |
| lib/siphash.c | 538 | lib/sort.c | 357 |
| lib/string.c | 882 | lib/uuid.c | 134 |
| lib/xarray.c | 2481 | lib/xxhash.c | 364 |
| **Total (24 files)** | **19822** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 131 / 93 / 1 |
| 2. geometric/shift loop updates | 2 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 20 / 1 = **21** |
| 4. monotone mask `|=` | 80 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 16) |
| 6. narrowing casts | 5 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 30 / 7 / 0 / 0 / 23 |
| 8. lockstep (dual-incr / ptr-bound) | 2 / 14 = **16** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 3 = **3** |
| countable loops (for+while) | 306 |
| value-shaping sites (2+3+4+5+6+9) | 111 |
| **ratio, value-shaping / countable loops** | **0.36** |
| ratio, value-shaping / **for-loops only** | **0.85** |

### 5b. crypto/*.c (top-level only, all 124 files)

Every top-level `crypto/*.c` file (not `crypto/async_tx/`, not any other
subdirectory) — no curation, per task instruction ("crypto/ *.c (top-level
only)").

Reproduce:
```
python3 eval/census.py --dir /path/to/linux --files crypto/*.c
```

### file listing (124 files)

| File | LoC | File | LoC |
|---|---|---|---|
| crypto/842.c | 87 | crypto/acompress.c | 582 |
| crypto/adiantum.c | 693 | crypto/aead.c | 315 |
| crypto/aegis128-core.c | 577 | crypto/aegis128-neon-inner.c | 345 |
| crypto/aegis128-neon.c | 60 | crypto/aes.c | 66 |
| crypto/af_alg.c | 1329 | crypto/ahash.c | 1095 |
| crypto/akcipher.c | 254 | crypto/algapi.c | 1119 |
| crypto/algboss.c | 254 | crypto/algif_aead.c | 528 |
| crypto/algif_hash.c | 470 | crypto/algif_rng.c | 339 |
| crypto/algif_skcipher.c | 441 | crypto/anubis.c | 699 |
| crypto/api.c | 743 | crypto/arc4.c | 82 |
| crypto/aria_generic.c | 314 | crypto/authenc.c | 454 |
| crypto/authencesn.c | 448 | crypto/blake2b.c | 111 |
| crypto/blowfish_common.c | 398 | crypto/blowfish_generic.c | 133 |
| crypto/bpf_crypto_skcipher.c | 83 | crypto/camellia_generic.c | 1073 |
| crypto/cast5_generic.c | 540 | crypto/cast6_generic.c | 280 |
| crypto/cast_common.c | 286 | crypto/cbc.c | 187 |
| crypto/ccm.c | 941 | crypto/chacha.c | 175 |
| crypto/chacha20poly1305.c | 486 | crypto/cipher.c | 119 |
| crypto/cmac.c | 260 | crypto/crc32.c | 129 |
| crypto/crc32c.c | 166 | crypto/cryptd.c | 1153 |
| crypto/crypto_engine.c | 656 | crypto/crypto_null.c | 155 |
| crypto/crypto_user.c | 506 | crypto/ctr.c | 360 |
| crypto/cts.c | 410 | crypto/deflate.c | 261 |
| crypto/des_generic.c | 134 | crypto/df_sp80090a.c | 222 |
| crypto/dh.c | 927 | crypto/dh_helper.c | 120 |
| crypto/drbg.c | 1904 | crypto/ecb.c | 228 |
| crypto/ecc.c | 1710 | crypto/ecdh.c | 247 |
| crypto/ecdh_helper.c | 83 | crypto/ecdsa-p1363.c | 161 |
| crypto/ecdsa-x962.c | 238 | crypto/ecdsa.c | 347 |
| crypto/echainiv.c | 153 | crypto/ecrdsa.c | 298 |
| crypto/essiv.c | 648 | crypto/fcrypt.c | 420 |
| crypto/fips.c | 102 | crypto/gcm.c | 1131 |
| crypto/geniv.c | 152 | crypto/ghash-generic.c | 162 |
| crypto/hctr2.c | 481 | crypto/hkdf.c | 573 |
| crypto/hmac.c | 581 | crypto/jitterentropy-kcapi.c | 370 |
| crypto/jitterentropy-testing.c | 295 | crypto/jitterentropy.c | 826 |
| crypto/kdf_sp800108.c | 157 | crypto/khazad.c | 876 |
| crypto/kpp.c | 142 | crypto/krb5enc.c | 504 |
| crypto/lrw.c | 429 | crypto/lskcipher.c | 589 |
| crypto/lz4.c | 99 | crypto/lz4hc.c | 97 |
| crypto/lzo-rle.c | 101 | crypto/lzo.c | 101 |
| crypto/md4.c | 241 | crypto/md5.c | 236 |
| crypto/michael_mic.c | 176 | crypto/mldsa.c | 201 |
| crypto/pcbc.c | 195 | crypto/pcrypt.c | 387 |
| crypto/proc.c | 103 | crypto/rmd160.c | 351 |
| crypto/rng.c | 225 | crypto/rsa-pkcs1pad.c | 379 |
| crypto/rsa.c | 437 | crypto/rsa_helper.c | 186 |
| crypto/rsassa-pkcs1.c | 437 | crypto/scatterwalk.c | 204 |
| crypto/scompress.c | 404 | crypto/seed.c | 469 |
| crypto/seqiv.c | 178 | crypto/serpent_generic.c | 609 |
| crypto/sha1.c | 240 | crypto/sha256.c | 419 |
| crypto/sha3.c | 166 | crypto/sha512.c | 425 |
| crypto/shash.c | 587 | crypto/sig.c | 182 |
| crypto/simd.c | 481 | crypto/skcipher.c | 888 |
| crypto/sm3_generic.c | 72 | crypto/sm4.c | 184 |
| crypto/sm4_generic.c | 92 | crypto/streebog_generic.c | 1074 |
| crypto/tcrypt.c | 2860 | crypto/tea.c | 262 |
| crypto/testmgr.c | 5808 | crypto/twofish_common.c | 693 |
| crypto/twofish_generic.c | 196 | crypto/wp512.c | 1145 |
| crypto/xcbc.c | 208 | crypto/xctr.c | 191 |
| crypto/xor.c | 174 | crypto/xts.c | 476 |
| crypto/xxhash_generic.c | 106 | crypto/zstd.c | 315 |
| **Total (124 files)** | **58432** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 262 / 222 / 11 |
| 2. geometric/shift loop updates | 4 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 167 / 1 = **168** |
| 4. monotone mask `|=` | 137 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 152) |
| 6. narrowing casts | 0 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 34 / 6 / 8 / 1 / 19 |
| 8. lockstep (dual-incr / ptr-bound) | 9 / 2 = **11** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 3 = **3** |
| countable loops (for+while) | 399 |
| value-shaping sites (2+3+4+5+6+9) | 312 |
| **ratio, value-shaping / countable loops** | **0.78** |
| ratio, value-shaping / **for-loops only** | **1.19** |

### 5c. net/ipv4/*.c (all 102 files)

Every `net/ipv4/*.c` file — no curation.

Reproduce:
```
python3 eval/census.py --dir /path/to/linux --files net/ipv4/*.c
```

### file listing (102 files)

| File | LoC | File | LoC |
|---|---|---|---|
| net/ipv4/af_inet.c | 2068 | net/ipv4/ah4.c | 602 |
| net/ipv4/arp.c | 1525 | net/ipv4/bpf_tcp_ca.c | 349 |
| net/ipv4/cipso_ipv4.c | 2325 | net/ipv4/datagram.c | 124 |
| net/ipv4/devinet.c | 2907 | net/ipv4/esp4.c | 1209 |
| net/ipv4/esp4_offload.c | 414 | net/ipv4/fib_frontend.c | 1713 |
| net/ipv4/fib_notifier.c | 72 | net/ipv4/fib_rules.c | 529 |
| net/ipv4/fib_semantics.c | 2259 | net/ipv4/fib_trie.c | 3041 |
| net/ipv4/fou_bpf.c | 117 | net/ipv4/fou_core.c | 1284 |
| net/ipv4/fou_nl.c | 49 | net/ipv4/gre_demux.c | 221 |
| net/ipv4/gre_offload.c | 287 | net/ipv4/icmp.c | 1766 |
| net/ipv4/igmp.c | 3197 | net/ipv4/inet_connection_sock.c | 1578 |
| net/ipv4/inet_diag.c | 1119 | net/ipv4/inet_fragment.c | 700 |
| net/ipv4/inet_hashtables.c | 1381 | net/ipv4/inet_timewait_sock.c | 360 |
| net/ipv4/inetpeer.c | 289 | net/ipv4/ip_forward.c | 181 |
| net/ipv4/ip_fragment.c | 753 | net/ipv4/ip_gre.c | 1868 |
| net/ipv4/ip_input.c | 679 | net/ipv4/ip_options.c | 641 |
| net/ipv4/ip_output.c | 1692 | net/ipv4/ip_sockglue.c | 1785 |
| net/ipv4/ip_tunnel.c | 1339 | net/ipv4/ip_tunnel_core.c | 1176 |
| net/ipv4/ip_vti.c | 744 | net/ipv4/ipcomp.c | 206 |
| net/ipv4/ipconfig.c | 1847 | net/ipv4/ipip.c | 702 |
| net/ipv4/ipmr.c | 3332 | net/ipv4/ipmr_base.c | 446 |
| net/ipv4/metrics.c | 91 | net/ipv4/netfilter.c | 99 |
| net/ipv4/netlink.c | 33 | net/ipv4/nexthop.c | 4155 |
| net/ipv4/ping.c | 1187 | net/ipv4/proc.c | 572 |
| net/ipv4/protocol.c | 70 | net/ipv4/raw.c | 1125 |
| net/ipv4/raw_diag.c | 259 | net/ipv4/route.c | 3799 |
| net/ipv4/syncookies.c | 507 | net/ipv4/sysctl_net_ipv4.c | 1729 |
| net/ipv4/tcp.c | 5362 | net/ipv4/tcp_ao.c | 2442 |
| net/ipv4/tcp_bbr.c | 1199 | net/ipv4/tcp_bic.c | 229 |
| net/ipv4/tcp_bpf.c | 760 | net/ipv4/tcp_cdg.c | 428 |
| net/ipv4/tcp_cong.c | 538 | net/ipv4/tcp_cubic.c | 555 |
| net/ipv4/tcp_dctcp.c | 313 | net/ipv4/tcp_diag.c | 688 |
| net/ipv4/tcp_fastopen.c | 689 | net/ipv4/tcp_highspeed.c | 186 |
| net/ipv4/tcp_htcp.c | 317 | net/ipv4/tcp_hybla.c | 194 |
| net/ipv4/tcp_illinois.c | 360 | net/ipv4/tcp_input.c | 7816 |
| net/ipv4/tcp_ipv4.c | 3742 | net/ipv4/tcp_lp.c | 357 |
| net/ipv4/tcp_metrics.c | 1059 | net/ipv4/tcp_minisocks.c | 1020 |
| net/ipv4/tcp_nv.c | 501 | net/ipv4/tcp_offload.c | 478 |
| net/ipv4/tcp_output.c | 4662 | net/ipv4/tcp_plb.c | 109 |
| net/ipv4/tcp_recovery.c | 162 | net/ipv4/tcp_scalable.c | 65 |
| net/ipv4/tcp_sigpool.c | 366 | net/ipv4/tcp_timer.c | 905 |
| net/ipv4/tcp_ulp.c | 168 | net/ipv4/tcp_vegas.c | 340 |
| net/ipv4/tcp_veno.c | 238 | net/ipv4/tcp_westwood.c | 309 |
| net/ipv4/tcp_yeah.c | 239 | net/ipv4/tunnel4.c | 298 |
| net/ipv4/udp.c | 4061 | net/ipv4/udp_bpf.c | 172 |
| net/ipv4/udp_diag.c | 299 | net/ipv4/udp_offload.c | 999 |
| net/ipv4/udp_tunnel_core.c | 280 | net/ipv4/udp_tunnel_nic.c | 1011 |
| net/ipv4/udp_tunnel_stub.c | 7 | net/ipv4/udplite.c | 136 |
| net/ipv4/xfrm4_input.c | 228 | net/ipv4/xfrm4_output.c | 46 |
| net/ipv4/xfrm4_policy.c | 245 | net/ipv4/xfrm4_protocol.c | 306 |
| net/ipv4/xfrm4_state.c | 24 | net/ipv4/xfrm4_tunnel.c | 119 |
| **Total (102 files)** | **107529** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 336 / 219 / 7 |
| 2. geometric/shift loop updates | 10 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 7 / 0 = **7** |
| 4. monotone mask `|=` | 344 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 188) |
| 6. narrowing casts | 1 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 207 / 7 / 10 / 0 / 190 |
| 8. lockstep (dual-incr / ptr-bound) | 13 / 2 = **15** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 21 = **21** |
| countable loops (for+while) | 512 |
| value-shaping sites (2+3+4+5+6+9) | 383 |
| **ratio, value-shaping / countable loops** | **0.75** |
| ratio, value-shaping / **for-loops only** | **1.14** |
---

## Codebase 6: OpenSSL

- Upstream: `https://github.com/openssl/openssl.git`
- Obtained via `git clone --depth 1` (shallow clone) into the scratchpad; sha
  read via `git log -1 --format=%H` immediately after.
- Pinned commit: `2924476b5591e691e904c4baf57894c526c4b8de`
- Files counted: `crypto/*.c` (69 top-level files) plus
  `crypto/{aes,sha,modes,bn}/*.c` (9 + 11 + 11 + 43 = 74 files) — one
  combined dataset per task instruction ("crypto/*.c + crypto/{aes,sha,modes,bn}/*.c"),
  139 files total.

Reproduce:
```
git clone --depth 1 https://github.com/openssl/openssl.git openssl
python3 eval/census.py --dir openssl --files crypto/*.c crypto/aes/*.c \
  crypto/sha/*.c crypto/modes/*.c crypto/bn/*.c
```

### file listing (139 files)

| File | LoC | File | LoC |
|---|---|---|---|
| crypto/LPdir_nyi.c | 56 | crypto/LPdir_unix.c | 170 |
| crypto/LPdir_vms.c | 207 | crypto/LPdir_win.c | 203 |
| crypto/LPdir_win32.c | 43 | crypto/aes/aes_cbc.c | 31 |
| crypto/aes/aes_cbc_vaes_intrinsic.c | 389 | crypto/aes/aes_cfb.c | 49 |
| crypto/aes/aes_core.c | 1852 | crypto/aes/aes_ecb.c | 32 |
| crypto/aes/aes_ige.c | 295 | crypto/aes/aes_misc.c | 23 |
| crypto/aes/aes_ofb.c | 25 | crypto/aes/aes_wrap.c | 33 |
| crypto/aligned_alloc.c | 68 | crypto/armcap.c | 477 |
| crypto/array_alloc.c | 94 | crypto/asn1_dsa.c | 253 |
| crypto/bn/bn_add.c | 177 | crypto/bn/bn_asm.c | 1081 |
| crypto/bn/bn_blind.c | 310 | crypto/bn/bn_const.c | 147 |
| crypto/bn/bn_conv.c | 284 | crypto/bn/bn_ctx.c | 367 |
| crypto/bn/bn_depr.c | 63 | crypto/bn/bn_dh.c | 1423 |
| crypto/bn/bn_div.c | 462 | crypto/bn/bn_err.c | 56 |
| crypto/bn/bn_exp.c | 1520 | crypto/bn/bn_exp2.c | 198 |
| crypto/bn/bn_gcd.c | 690 | crypto/bn/bn_gf2m.c | 1189 |
| crypto/bn/bn_intern.c | 195 | crypto/bn/bn_kron.c | 140 |
| crypto/bn/bn_lib.c | 1213 | crypto/bn/bn_mod.c | 334 |
| crypto/bn/bn_mont.c | 508 | crypto/bn/bn_mpi.c | 85 |
| crypto/bn/bn_mul.c | 669 | crypto/bn/bn_nist.c | 1220 |
| crypto/bn/bn_ppc.c | 56 | crypto/bn/bn_prime.c | 617 |
| crypto/bn/bn_print.c | 72 | crypto/bn/bn_rand.c | 412 |
| crypto/bn/bn_recp.c | 192 | crypto/bn/bn_rsa_fips186_5.c | 451 |
| crypto/bn/bn_s390x.c | 180 | crypto/bn/bn_shift.c | 216 |
| crypto/bn/bn_sparc.c | 72 | crypto/bn/bn_sqr.c | 231 |
| crypto/bn/bn_sqrt.c | 367 | crypto/bn/bn_srp.c | 545 |
| crypto/bn/bn_word.c | 200 | crypto/bn/bn_x931p.c | 247 |
| crypto/bn/rsaz_exp.c | 316 | crypto/bn/rsaz_exp_x2.c | 708 |
| crypto/bsearch.c | 57 | crypto/comp_methods.c | 59 |
| crypto/context.c | 723 | crypto/core_algorithm.c | 199 |
| crypto/core_fetch.c | 175 | crypto/core_namemap.c | 565 |
| crypto/cpt_err.c | 89 | crypto/cpuid.c | 232 |
| crypto/cryptlib.c | 269 | crypto/ctype.c | 313 |
| crypto/cversion.c | 128 | crypto/defaults.c | 175 |
| crypto/der_writer.c | 198 | crypto/deterministic_nonce.c | 240 |
| crypto/dllmain.c | 50 | crypto/ebcdic.c | 393 |
| crypto/ex_data.c | 502 | crypto/getenv.c | 101 |
| crypto/indicator_core.c | 54 | crypto/info.c | 301 |
| crypto/init.c | 499 | crypto/initthread.c | 495 |
| crypto/loongarchcap.c | 17 | crypto/mem.c | 441 |
| crypto/mem_clr.c | 25 | crypto/mem_sec.c | 750 |
| crypto/modes/cbc128.c | 168 | crypto/modes/ccm128.c | 442 |
| crypto/modes/cfb128.c | 207 | crypto/modes/ctr128.c | 212 |
| crypto/modes/cts128.c | 330 | crypto/modes/gcm128.c | 1638 |
| crypto/modes/ocb128.c | 563 | crypto/modes/ofb128.c | 84 |
| crypto/modes/siv128.c | 394 | crypto/modes/wrap128.c | 333 |
| crypto/modes/xts128.c | 161 | crypto/modes/xts128gb.c | 199 |
| crypto/o_dir.c | 37 | crypto/o_fopen.c | 126 |
| crypto/o_init.c | 21 | crypto/o_str.c | 499 |
| crypto/packet.c | 591 | crypto/param_build.c | 490 |
| crypto/param_build_set.c | 129 | crypto/params.c | 1723 |
| crypto/params_dup.c | 259 | crypto/params_from_text.c | 339 |
| crypto/passphrase.c | 345 | crypto/ppccap.c | 329 |
| crypto/provider.c | 158 | crypto/provider_child.c | 317 |
| crypto/provider_conf.c | 430 | crypto/provider_core.c | 2659 |
| crypto/provider_predefined.c | 32 | crypto/punycode.c | 316 |
| crypto/quic_vlint.c | 81 | crypto/riscvcap.c | 157 |
| crypto/s390xcap.c | 915 | crypto/self_test_core.c | 160 |
| crypto/sha/keccak1600.c | 1285 | crypto/sha/sha1_one.c | 81 |
| crypto/sha/sha1dgst.c | 80 | crypto/sha/sha256.c | 447 |
| crypto/sha/sha3.c | 354 | crypto/sha/sha3_encode.c | 158 |
| crypto/sha/sha3_x4_avx512vl.c | 213 | crypto/sha/sha512.c | 826 |
| crypto/sha/sha_loongarch.c | 41 | crypto/sha/sha_ppc.c | 31 |
| crypto/sha/sha_riscv.c | 48 | crypto/sleep.c | 134 |
| crypto/sparcv9cap.c | 240 | crypto/sparse_array.c | 216 |
| crypto/ssl_err.c | 635 | crypto/threads_common.c | 414 |
| crypto/threads_lib.c | 27 | crypto/threads_none.c | 331 |
| crypto/threads_pthread.c | 1321 | crypto/threads_win.c | 803 |
| crypto/time.c | 49 | crypto/trace.c | 559 |
| crypto/uid.c | 55 | | |
| **Total (139 files)** | **51755** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 426 / 343 / 13 |
| 2. geometric/shift loop updates | 27 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 315 / 27 = **342** |
| 4. monotone mask `|=` | 220 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 0) |
| 6. narrowing casts | 60 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 74 / 2 / 2 / 0 / 70 |
| 8. lockstep (dual-incr / ptr-bound) | 21 / 5 = **26** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 23 = **23** |
| countable loops (for+while) | 667 |
| value-shaping sites (2+3+4+5+6+9) | 672 |
| **ratio, value-shaping / countable loops** | **1.01** |
| ratio, value-shaping / **for-loops only** | **1.58** |
---

## Codebase 7: SQLite

- Upstream: `https://github.com/sqlite/sqlite.git`
- Obtained via `git clone --depth 1` (shallow clone); sha read via
  `git log -1 --format=%H` immediately after.
- Pinned commit: `912706d94a5b9dc20fffc335ab4be0606bd2d4ab`
- Files counted: all 125 files matching `src/*.c` — no curation. This
  includes SQLite's own `test*.c`/`test_*.c` TCL-harness test-instrumentation
  files (part of the upstream `src/` tree, not a separate test directory);
  flagged here rather than silently included or excluded, per task scope
  ("src/*.c").

Reproduce:
```
git clone --depth 1 https://github.com/sqlite/sqlite.git sqlite
python3 eval/census.py --dir sqlite --files src/*.c
```

### file listing (125 files)

| File | LoC | File | LoC |
|---|---|---|---|
| src/alter.c | 3089 | src/analyze.c | 2012 |
| src/attach.c | 631 | src/auth.c | 279 |
| src/backup.c | 796 | src/bitvec.c | 495 |
| src/btmutex.c | 309 | src/btree.c | 11655 |
| src/build.c | 5845 | src/callback.c | 547 |
| src/carray.c | 564 | src/complete.c | 371 |
| src/date.c | 1881 | src/dbpage.c | 505 |
| src/dbstat.c | 906 | src/delete.c | 1034 |
| src/expr.c | 7789 | src/fault.c | 87 |
| src/fkey.c | 1488 | src/func.c | 3514 |
| src/global.c | 411 | src/hash.c | 273 |
| src/insert.c | 3471 | src/json.c | 5741 |
| src/legacy.c | 141 | src/loadext.c | 948 |
| src/main.c | 5267 | src/malloc.c | 898 |
| src/mem0.c | 59 | src/mem1.c | 291 |
| src/mem2.c | 528 | src/mem3.c | 687 |
| src/mem5.c | 585 | src/memdb.c | 937 |
| src/memjournal.c | 440 | src/mutex.c | 383 |
| src/mutex_noop.c | 215 | src/mutex_unix.c | 413 |
| src/mutex_w32.c | 384 | src/notify.c | 335 |
| src/os.c | 447 | src/os_kv.c | 1097 |
| src/os_unix.c | 8582 | src/os_win.c | 5344 |
| src/pager.c | 7896 | src/pcache.c | 936 |
| src/pcache1.c | 1287 | src/pragma.c | 3104 |
| src/prepare.c | 1111 | src/printf.c | 1729 |
| src/random.c | 157 | src/resolve.c | 2367 |
| src/rowset.c | 502 | src/select.c | 9037 |
| src/status.c | 446 | src/table.c | 198 |
| src/tclsqlite.c | 4662 | src/test1.c | 9536 |
| src/test2.c | 751 | src/test3.c | 683 |
| src/test4.c | 737 | src/test5.c | 216 |
| src/test6.c | 1104 | src/test8.c | 1453 |
| src/test9.c | 200 | src/test_autoext.c | 221 |
| src/test_backup.c | 150 | src/test_bestindex.c | 981 |
| src/test_blob.c | 317 | src/test_btree.c | 62 |
| src/test_config.c | 862 | src/test_delete.c | 156 |
| src/test_demovfs.c | 683 | src/test_devsym.c | 525 |
| src/test_fs.c | 920 | src/test_func.c | 957 |
| src/test_hexio.c | 475 | src/test_init.c | 291 |
| src/test_intarray.c | 391 | src/test_journal.c | 869 |
| src/test_loadext.c | 128 | src/test_malloc.c | 1468 |
| src/test_md5.c | 443 | src/test_multiplex.c | 1369 |
| src/test_mutex.c | 497 | src/test_onefile.c | 831 |
| src/test_osinst.c | 1221 | src/test_pcache.c | 468 |
| src/test_quota.c | 1965 | src/test_rtree.c | 503 |
| src/test_schema.c | 367 | src/test_sqllog.c | 556 |
| src/test_superlock.c | 356 | src/test_syscall.c | 764 |
| src/test_tclsh.c | 200 | src/test_tclvar.c | 563 |
| src/test_thread.c | 663 | src/test_vdbecov.c | 116 |
| src/test_vfs.c | 1697 | src/test_window.c | 349 |
| src/test_wsd.c | 84 | src/threads.c | 275 |
| src/tokenize.c | 899 | src/treeview.c | 1328 |
| src/trigger.c | 1581 | src/update.c | 1362 |
| src/upsert.c | 330 | src/utf.c | 597 |
| src/util.c | 2230 | src/vacuum.c | 429 |
| src/vdbe.c | 9574 | src/vdbeapi.c | 2699 |
| src/vdbeaux.c | 5753 | src/vdbeblob.c | 534 |
| src/vdbemem.c | 2257 | src/vdbesort.c | 2947 |
| src/vdbetrace.c | 192 | src/vdbevtab.c | 446 |
| src/vtab.c | 1384 | src/wal.c | 4649 |
| src/walker.c | 261 | src/where.c | 7894 |
| src/wherecode.c | 3002 | src/whereexpr.c | 1997 |
| src/window.c | 3112 | | |
| **Total (125 files)** | **207986** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 1615 / 1134 / 23 |
| 2. geometric/shift loop updates | 11 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 59 / 5 = **64** |
| 4. monotone mask `|=` | 512 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 7 = **7** (macro-call info: 67) |
| 6. narrowing casts | 17 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 166 / 23 / 4 / 1 / 138 |
| 8. lockstep (dual-incr / ptr-bound) | 104 / 54 = **158** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 10 = **10** |
| countable loops (for+while) | 2264 |
| value-shaping sites (2+3+4+5+6+9) | 621 |
| **ratio, value-shaping / countable loops** | **0.27** |
| ratio, value-shaping / **for-loops only** | **0.38** |
---

## Codebase 8: lwIP

- Upstream: `https://github.com/lwip-tcpip/lwip.git`
- Obtained via `git clone --depth 1` (shallow clone); sha read via
  `git log -1 --format=%H` immediately after.
- Pinned commit: `3d896ba0a37ff3ce73270ca5e230707fe47f60e3`
- Files counted: `src/core/*.c` (20 files) + `src/core/ipv4/*.c` (9 files),
  29 files total — one combined dataset per task instruction.

Reproduce:
```
git clone --depth 1 https://github.com/lwip-tcpip/lwip.git lwip
python3 eval/census.py --dir lwip --files src/core/*.c src/core/ipv4/*.c
```

### file listing (29 files)

| File | LoC | File | LoC |
|---|---|---|---|
| src/core/altcp.c | 717 | src/core/altcp_alloc.c | 87 |
| src/core/altcp_tcp.c | 578 | src/core/def.c | 286 |
| src/core/dns.c | 1657 | src/core/inet_chksum.c | 608 |
| src/core/init.c | 390 | src/core/ip.c | 167 |
| src/core/ipv4/acd.c | 557 | src/core/ipv4/autoip.c | 380 |
| src/core/ipv4/dhcp.c | 2000 | src/core/ipv4/etharp.c | 1251 |
| src/core/ipv4/icmp.c | 408 | src/core/ipv4/igmp.c | 801 |
| src/core/ipv4/ip4.c | 1176 | src/core/ipv4/ip4_addr.c | 323 |
| src/core/ipv4/ip4_frag.c | 896 | src/core/mem.c | 1004 |
| src/core/memp.c | 447 | src/core/netif.c | 1857 |
| src/core/pbuf.c | 1554 | src/core/raw.c | 673 |
| src/core/stats.c | 172 | src/core/sys.c | 148 |
| src/core/tcp.c | 2696 | src/core/tcp_in.c | 2198 |
| src/core/tcp_out.c | 2260 | src/core/timeouts.c | 456 |
| src/core/udp.c | 1321 | | |
| **Total (29 files)** | **27068** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 137 / 66 / 0 |
| 2. geometric/shift loop updates | 2 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 9 / 6 = **15** |
| 4. monotone mask `|=` | 40 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 0) |
| 6. narrowing casts | 2 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 20 / 1 / 0 / 0 / 19 |
| 8. lockstep (dual-incr / ptr-bound) | 1 / 20 = **21** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 5 = **5** |
| countable loops (for+while) | 224 |
| value-shaping sites (2+3+4+5+6+9) | 64 |
| **ratio, value-shaping / countable loops** | **0.29** |
| ratio, value-shaping / **for-loops only** | **0.47** |
---

## Codebase 9: musl libc

- Upstream: `https://git.musl-libc.org/git/musl` (the official musl repo;
  the task's suggested `github.com/bminor/musl` mirror URL returned
  "Repository not found" at clone time — reported here as a genuine finding,
  not silently substituted; the official URL was used instead).
- Obtained via `git clone --depth 1` (shallow clone); sha read via
  `git log -1 --format=%H` immediately after.
- Pinned commit: `f21a96538f78fa8e2040831b4209b35f2fb581da`
- Files counted: `src/string/*.c` (74 files) + `src/stdlib/*.c` (22 files) +
  `src/stdio/*.c` (116 files), 212 files total — one combined dataset.
  musl's style is one function per file, so most files are single-digit to
  low-double-digit LoC (e.g. `strcmp.c` is 7 lines) — this codebase has by
  far the smallest total LoC (6675) of the sample despite the largest file
  count (212).

Reproduce:
```
git clone --depth 1 https://git.musl-libc.org/git/musl musl
python3 eval/census.py --dir musl --files src/string/*.c src/stdlib/*.c src/stdio/*.c
```

### file listing (212 files)

| File | LoC | File | LoC |
|---|---|---|---|
| src/stdio/__fclose_ca.c | 6 | src/stdio/__fdopen.c | 61 |
| src/stdio/__fmodeflags.c | 16 | src/stdio/__fopen_rb_ca.c | 22 |
| src/stdio/__lockfile.c | 23 | src/stdio/__overflow.c | 10 |
| src/stdio/__stdio_close.c | 14 | src/stdio/__stdio_exit.c | 25 |
| src/stdio/__stdio_read.c | 24 | src/stdio/__stdio_seek.c | 7 |
| src/stdio/__stdio_write.c | 39 | src/stdio/__stdout_write.c | 11 |
| src/stdio/__toread.c | 19 | src/stdio/__towrite.c | 23 |
| src/stdio/__uflow.c | 11 | src/stdio/asprintf.c | 13 |
| src/stdio/clearerr.c | 10 | src/stdio/dprintf.c | 12 |
| src/stdio/ext.c | 57 | src/stdio/ext2.c | 24 |
| src/stdio/fclose.c | 38 | src/stdio/feof.c | 14 |
| src/stdio/ferror.c | 14 | src/stdio/fflush.c | 47 |
| src/stdio/fgetc.c | 7 | src/stdio/fgetln.c | 21 |
| src/stdio/fgetpos.c | 9 | src/stdio/fgets.c | 49 |
| src/stdio/fgetwc.c | 68 | src/stdio/fgetws.c | 28 |
| src/stdio/fileno.c | 16 | src/stdio/flockfile.c | 9 |
| src/stdio/fmemopen.c | 131 | src/stdio/fopen.c | 31 |
| src/stdio/fopencookie.c | 135 | src/stdio/fprintf.c | 12 |
| src/stdio/fputc.c | 7 | src/stdio/fputs.c | 10 |
| src/stdio/fputwc.c | 40 | src/stdio/fputws.c | 29 |
| src/stdio/fread.c | 38 | src/stdio/freopen.c | 53 |
| src/stdio/fscanf.c | 14 | src/stdio/fseek.c | 48 |
| src/stdio/fsetpos.c | 6 | src/stdio/ftell.c | 39 |
| src/stdio/ftrylockfile.c | 46 | src/stdio/funlockfile.c | 13 |
| src/stdio/fwide.c | 16 | src/stdio/fwprintf.c | 13 |
| src/stdio/fwrite.c | 38 | src/stdio/fwscanf.c | 15 |
| src/stdio/getc.c | 9 | src/stdio/getc_unlocked.c | 9 |
| src/stdio/getchar.c | 7 | src/stdio/getchar_unlocked.c | 6 |
| src/stdio/getdelim.c | 83 | src/stdio/getline.c | 6 |
| src/stdio/gets.c | 15 | src/stdio/getw.c | 8 |
| src/stdio/getwc.c | 7 | src/stdio/getwchar.c | 9 |
| src/stdio/ofl.c | 18 | src/stdio/ofl_add.c | 11 |
| src/stdio/open_memstream.c | 99 | src/stdio/open_wmemstream.c | 106 |
| src/stdio/pclose.c | 13 | src/stdio/perror.c | 30 |
| src/stdio/popen.c | 61 | src/stdio/printf.c | 12 |
| src/stdio/putc.c | 9 | src/stdio/putc_unlocked.c | 9 |
| src/stdio/putchar.c | 7 | src/stdio/putchar_unlocked.c | 6 |
| src/stdio/puts.c | 10 | src/stdio/putw.c | 7 |
| src/stdio/putwc.c | 7 | src/stdio/putwchar.c | 9 |
| src/stdio/remove.c | 19 | src/stdio/rename.c | 14 |
| src/stdio/rewind.c | 9 | src/stdio/scanf.c | 14 |
| src/stdio/setbuf.c | 6 | src/stdio/setbuffer.c | 7 |
| src/stdio/setlinebuf.c | 7 | src/stdio/setvbuf.c | 29 |
| src/stdio/snprintf.c | 13 | src/stdio/sprintf.c | 12 |
| src/stdio/sscanf.c | 14 | src/stdio/stderr.c | 18 |
| src/stdio/stdin.c | 17 | src/stdio/stdout.c | 18 |
| src/stdio/swprintf.c | 13 | src/stdio/swscanf.c | 14 |
| src/stdio/tempnam.c | 47 | src/stdio/tmpfile.c | 29 |
| src/stdio/tmpnam.c | 27 | src/stdio/ungetc.c | 20 |
| src/stdio/ungetwc.c | 35 | src/stdio/vasprintf.c | 15 |
| src/stdio/vdprintf.c | 11 | src/stdio/vfprintf.c | 703 |
| src/stdio/vfscanf.c | 339 | src/stdio/vfwprintf.c | 372 |
| src/stdio/vfwscanf.c | 332 | src/stdio/vprintf.c | 6 |
| src/stdio/vscanf.c | 9 | src/stdio/vsnprintf.c | 50 |
| src/stdio/vsprintf.c | 7 | src/stdio/vsscanf.c | 27 |
| src/stdio/vswprintf.c | 58 | src/stdio/vswscanf.c | 38 |
| src/stdio/vwprintf.c | 7 | src/stdio/vwscanf.c | 10 |
| src/stdio/wprintf.c | 13 | src/stdio/wscanf.c | 15 |
| src/stdlib/abs.c | 6 | src/stdlib/atof.c | 6 |
| src/stdlib/atoi.c | 16 | src/stdlib/atol.c | 17 |
| src/stdlib/atoll.c | 17 | src/stdlib/bsearch.c | 20 |
| src/stdlib/div.c | 6 | src/stdlib/ecvt.c | 20 |
| src/stdlib/fcvt.c | 25 | src/stdlib/gcvt.c | 9 |
| src/stdlib/imaxabs.c | 6 | src/stdlib/imaxdiv.c | 6 |
| src/stdlib/labs.c | 6 | src/stdlib/ldiv.c | 6 |
| src/stdlib/llabs.c | 6 | src/stdlib/lldiv.c | 6 |
| src/stdlib/qsort.c | 229 | src/stdlib/qsort_nr.c | 14 |
| src/stdlib/strtod.c | 30 | src/stdlib/strtol.c | 56 |
| src/stdlib/wcstod.c | 64 | src/stdlib/wcstol.c | 81 |
| src/string/bcmp.c | 8 | src/string/bcopy.c | 8 |
| src/string/bzero.c | 8 | src/string/explicit_bzero.c | 8 |
| src/string/index.c | 8 | src/string/memccpy.c | 34 |
| src/string/memchr.c | 27 | src/string/memcmp.c | 8 |
| src/string/memcpy.c | 124 | src/string/memmem.c | 149 |
| src/string/memmove.c | 42 | src/string/mempcpy.c | 7 |
| src/string/memrchr.c | 11 | src/string/memset.c | 90 |
| src/string/rindex.c | 8 | src/string/stpcpy.c | 29 |
| src/string/stpncpy.c | 32 | src/string/strcasecmp.c | 16 |
| src/string/strcasestr.c | 10 | src/string/strcat.c | 7 |
| src/string/strchr.c | 7 | src/string/strchrnul.c | 28 |
| src/string/strcmp.c | 7 | src/string/strcpy.c | 7 |
| src/string/strcspn.c | 17 | src/string/strdup.c | 10 |
| src/string/strerror_r.c | 19 | src/string/strlcat.c | 9 |
| src/string/strlcpy.c | 34 | src/string/strlen.c | 22 |
| src/string/strncasecmp.c | 17 | src/string/strncat.c | 10 |
| src/string/strncmp.c | 9 | src/string/strncpy.c | 7 |
| src/string/strndup.c | 12 | src/string/strnlen.c | 7 |
| src/string/strpbrk.c | 7 | src/string/strrchr.c | 6 |
| src/string/strsep.c | 13 | src/string/strsignal.c | 126 |
| src/string/strspn.c | 20 | src/string/strstr.c | 154 |
| src/string/strtok.c | 13 | src/string/strtok_r.c | 12 |
| src/string/strverscmp.c | 34 | src/string/swab.c | 13 |
| src/string/wcpcpy.c | 6 | src/string/wcpncpy.c | 6 |
| src/string/wcscasecmp.c | 7 | src/string/wcscasecmp_l.c | 6 |
| src/string/wcscat.c | 7 | src/string/wcschr.c | 8 |
| src/string/wcscmp.c | 7 | src/string/wcscpy.c | 8 |
| src/string/wcscspn.c | 10 | src/string/wcsdup.c | 10 |
| src/string/wcslen.c | 8 | src/string/wcsncasecmp.c | 9 |
| src/string/wcsncasecmp_l.c | 6 | src/string/wcsncat.c | 10 |
| src/string/wcsncmp.c | 7 | src/string/wcsncpy.c | 9 |
| src/string/wcsnlen.c | 8 | src/string/wcspbrk.c | 7 |
| src/string/wcsrchr.c | 8 | src/string/wcsspn.c | 8 |
| src/string/wcsstr.c | 105 | src/string/wcstok.c | 12 |
| src/string/wcswcs.c | 6 | src/string/wmemchr.c | 7 |
| src/string/wmemcmp.c | 7 | src/string/wmemcpy.c | 8 |
| src/string/wmemmove.c | 13 | src/string/wmemset.c | 8 |
| **Total (212 files)** | **6675** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 134 / 65 / 1 |
| 2. geometric/shift loop updates | 1 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 0 / 0 = **0** |
| 4. monotone mask `|=` | 45 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 34) |
| 6. narrowing casts | 1 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 20 / 1 / 0 / 0 / 19 |
| 8. lockstep (dual-incr / ptr-bound) | 36 / 1 = **37** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 10 = **10** |
| countable loops (for+while) | 202 |
| value-shaping sites (2+3+4+5+6+9) | 57 |
| **ratio, value-shaping / countable loops** | **0.28** |
| ratio, value-shaping / **for-loops only** | **0.43** |
---

## Codebase 10: curl

- Upstream: `https://github.com/curl/curl.git`
- Obtained via `git clone --depth 1` (shallow clone); sha read via
  `git log -1 --format=%H` immediately after.
- Pinned commit: `9b29495863c967e2768ea1c517f3ad28a50a9a1b`
- Files counted: all 127 files matching `lib/*.c` — no curation.

Reproduce:
```
git clone --depth 1 https://github.com/curl/curl.git curl
python3 eval/census.py --dir curl --files lib/*.c
```

### file listing (127 files)

| File | LoC | File | LoC |
|---|---|---|---|
| lib/altsvc.c | 716 | lib/amigaos.c | 239 |
| lib/api.c | 451 | lib/bufq.c | 619 |
| lib/bufref.c | 138 | lib/cf-h1-proxy.c | 1005 |
| lib/cf-h2-proxy.c | 1509 | lib/cf-haproxy.c | 241 |
| lib/cf-https-connect.c | 818 | lib/cf-ip-happy.c | 1022 |
| lib/cf-recvbuf.c | 157 | lib/cf-setup.c | 479 |
| lib/cf-socket.c | 2416 | lib/cfilters.c | 1103 |
| lib/conncache.c | 1014 | lib/connect.c | 476 |
| lib/content_encoding.c | 877 | lib/cookie.c | 1694 |
| lib/creds.c | 192 | lib/cshutdn.c | 528 |
| lib/curl_addrinfo.c | 647 | lib/curl_ed25519.c | 175 |
| lib/curl_endian.c | 83 | lib/curl_fnmatch.c | 385 |
| lib/curl_fopen.c | 164 | lib/curl_get_line.c | 69 |
| lib/curl_gethostname.c | 96 | lib/curl_gssapi.c | 705 |
| lib/curl_memrchr.c | 53 | lib/curl_ntlm_core.c | 667 |
| lib/curl_range.c | 91 | lib/curl_sasl.c | 908 |
| lib/curl_sha512_256.c | 847 | lib/curl_share.c | 486 |
| lib/curl_sspi.c | 215 | lib/curl_threads.c | 235 |
| lib/curl_trc.c | 780 | lib/cw-out.c | 503 |
| lib/cw-pause.c | 216 | lib/dict.c | 325 |
| lib/dllmain.c | 64 | lib/dynhds.c | 385 |
| lib/easy.c | 1437 | lib/easygetopt.c | 97 |
| lib/easyoptions.c | 394 | lib/escape.c | 228 |
| lib/fake_addrinfo.c | 202 | lib/file.c | 718 |
| lib/fileinfo.c | 44 | lib/formdata.c | 866 |
| lib/ftp.c | 4518 | lib/ftplistparser.c | 1093 |
| lib/getenv.c | 69 | lib/getinfo.c | 672 |
| lib/gopher.c | 226 | lib/hash.c | 388 |
| lib/headers.c | 425 | lib/hmac.c | 170 |
| lib/hsts.c | 646 | lib/http.c | 5099 |
| lib/http1.c | 347 | lib/http2.c | 3002 |
| lib/http_aws_sigv4.c | 1238 | lib/http_chunks.c | 686 |
| lib/http_digest.c | 162 | lib/http_httpsig.c | 692 |
| lib/http_negotiate.c | 266 | lib/http_ntlm.c | 255 |
| lib/http_proxy.c | 778 | lib/idn.c | 388 |
| lib/if2ip.c | 262 | lib/imap.c | 2328 |
| lib/ldap.c | 985 | lib/llist.c | 270 |
| lib/macos.c | 50 | lib/md4.c | 466 |
| lib/md5.c | 613 | lib/memdebug.c | 579 |
| lib/mime.c | 2282 | lib/mprintf.c | 1256 |
| lib/mqtt.c | 1032 | lib/multi.c | 4241 |
| lib/multi_ev.c | 647 | lib/multi_ntfy.c | 213 |
| lib/netrc.c | 694 | lib/openldap.c | 1311 |
| lib/parsedate.c | 606 | lib/peer.c | 732 |
| lib/pingpong.c | 412 | lib/pop3.c | 1718 |
| lib/progress.c | 759 | lib/protocol.c | 536 |
| lib/proxy.c | 676 | lib/psl.c | 104 |
| lib/rand.c | 230 | lib/ratelimit.c | 306 |
| lib/request.c | 502 | lib/rtsp.c | 1055 |
| lib/select.c | 727 | lib/sendf.c | 1496 |
| lib/setopt.c | 2934 | lib/sha256.c | 512 |
| lib/slist.c | 139 | lib/smb.c | 1243 |
| lib/smtp.c | 2020 | lib/socketpair.c | 364 |
| lib/socks.c | 1373 | lib/socks_gssapi.c | 601 |
| lib/socks_sspi.c | 536 | lib/splay.c | 377 |
| lib/strcase.c | 146 | lib/strequal.c | 95 |
| lib/strerror.c | 680 | lib/system_win32.c | 100 |
| lib/telnet.c | 1581 | lib/tftp.c | 1358 |
| lib/thrdpool.c | 502 | lib/thrdqueue.c | 433 |
| lib/transfer.c | 902 | lib/uint-bset.c | 233 |
| lib/uint-hash.c | 235 | lib/uint-spbset.c | 305 |
| lib/uint-table.c | 202 | lib/url.c | 2622 |
| lib/urlapi.c | 2173 | lib/version.c | 681 |
| lib/ws.c | 2069 | | |
| **Total (127 files)** | **100403** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 336 / 189 / 1 |
| 2. geometric/shift loop updates | 2 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 62 / 1 = **63** |
| 4. monotone mask `|=` | 183 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 0) |
| 6. narrowing casts | 79 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 313 / 9 / 13 / 0 / 291 |
| 8. lockstep (dual-incr / ptr-bound) | 8 / 5 = **13** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 12 = **12** |
| countable loops (for+while) | 702 |
| value-shaping sites (2+3+4+5+6+9) | 339 |
| **ratio, value-shaping / countable loops** | **0.48** |
| ratio, value-shaping / **for-loops only** | **1.01** |
---
## Aggregate table (12 C codebases — 4 original + 8 added in this pass)

| Codebase | LoC | for-loops (total/stride1/strided) | geometric | bit-slice | monotone `\|=` | clamp | narrow-cast | switches (total/contig/sparse/symbolic) | lockstep | zigzag/byteswap |
|---|---|---|---|---|---|---|---|---|---|---|
| nanopb | 3157 | 8 / 8 / 0 | 4 | 29 | 11 | 0 | 0 | 9 / 1 / 0 / 8 | 0 | 2 |
| libcsp | 5136 | 21 / 19 / 0 | 0 | 12 | 15 | 0 | 8 | 3 / 0 / 0 / 3 | 0 | 0 |
| zlib | 9701 | 81 / 59 / 0 | 10 | 22 | 12 | 0 | 0 | 12 / 3 / 4 / 5 | 6 | 4 |
| FreeRTOS-Kernel | 17000 | 37 / 25 / 0 | 0 | 0 | 12 | 0 | 60 | 4 / 0 / 0 / 4 | 4 | 0 |
| linux lib/ (24-file curated) | 19822 | 131 / 93 / 1 | 2 | 21 | 80 | 0 | 5 | 30 / 7 / 0 / 23 | 16 | 3 |
| linux crypto/ (124 files) | 58432 | 262 / 222 / 11 | 4 | 168 | 137 | 0 | 0 | 34 / 6 / 9 / 19 | 11 | 3 |
| linux net/ipv4/ (102 files) | 107529 | 336 / 219 / 7 | 10 | 7 | 344 | 0 | 1 | 207 / 7 / 10 / 190 | 15 | 21 |
| OpenSSL (139 files) | 51755 | 426 / 343 / 13 | 27 | 342 | 220 | 0 | 60 | 74 / 2 / 2 / 70 | 26 | 23 |
| SQLite (125 files) | 207986 | 1615 / 1134 / 23 | 11 | 64 | 512 | 7 | 17 | 166 / 23 / 5 / 138 | 158 | 10 |
| lwIP (29 files) | 27068 | 137 / 66 / 0 | 2 | 15 | 40 | 0 | 2 | 20 / 1 / 0 / 19 | 21 | 5 |
| musl (212 files) | 6675 | 134 / 65 / 1 | 1 | 0 | 45 | 0 | 1 | 20 / 1 / 0 / 19 | 37 | 10 |
| curl (127 files) | 100403 | 336 / 189 / 1 | 2 | 63 | 183 | 0 | 79 | 313 / 9 / 13 / 291 | 13 | 12 |
| **Total (12 codebases)** | **614664** | **3524 / 2442 / 57** | **73** | **743** | **1611** | **7** | **233** | **892 / 60 / 43 / 789** | **307** | **93** |

(switches "sparse" column above folds in the small `sparse-dup` sub-bucket —
5 sites total across the sample: 1 in linux crypto/, 1 in SQLite — so the
four numbers per row still sum to the row's switch total.)

## Ratio table — value-shaping sites vs. countable loops (all 12 C codebases)

| Codebase | value-shaping sites | countable loops (for+while) | ratio (÷ for+while) | for-loops only | ratio (÷ for-loops only) |
|---|---|---|---|---|---|
| nanopb | 46 | 32 | 1.44 | 8 | 5.75 |
| libcsp | 35 | 48 | 0.73 | 21 | 1.67 |
| zlib | 48 | 212 | 0.23 | 81 | 0.59 |
| FreeRTOS-Kernel | 72 | 78 | 0.92 | 37 | 1.95 |
| linux lib/ (curated) | 111 | 306 | 0.36 | 131 | 0.85 |
| linux crypto/ | 312 | 399 | 0.78 | 262 | 1.19 |
| linux net/ipv4/ | 383 | 512 | 0.75 | 336 | 1.14 |
| OpenSSL | 672 | 667 | 1.01 | 426 | 1.58 |
| SQLite | 621 | 2264 | 0.27 | 1615 | 0.38 |
| lwIP | 64 | 224 | 0.29 | 137 | 0.47 |
| musl | 57 | 202 | 0.28 | 134 | 0.43 |
| curl | 339 | 702 | 0.48 | 336 | 1.01 |
| **All 12, aggregate** | **2760** | **5646** | **0.49** | **3524** | **0.78** |

**On the "several-fold" claim in `folding.tex`, updated with the larger
sample.** Adding eight codebases does not rescue the "outnumber countable
loops several-fold" claim as a blanket statement, and complicates it
further. Under the for+while denominator, the aggregate ratio across all 12
C codebases is **0.49** — below 1×, i.e. value-shaping sites are, in
aggregate, *less* numerous than countable loops, not several-fold more.
Under the for-loops-only denominator the aggregate is **0.78×**, still below
1×. Only **OpenSSL (1.01×)** clears 1× under the for+while denominator among
the new eight; nanopb (5.75×), linux crypto/ (1.19×), linux net/ipv4/
(1.14×), OpenSSL (1.58×), and curl (1.01×) clear 1× under the for-loops-only
denominator, but none in this larger sample reaches nanopb's 5.75× except
nanopb itself. SQLite (0.27 / 0.38) and musl (0.28 / 0.43) sit at the low
end alongside zlib, all query-engine/libc-general code where control flow
(tree walks, VM dispatch, parsing) dominates over bit/mask/clamp
value-shaping. The claim as originally scoped to "codec/protocol code" is
still the best-supported reading: nanopb (pure wire-format codec) is the
strongest single data point, and the two codec-adjacent slices with the next
highest for-loops-only ratios are OpenSSL crypto (1.58, dense with
bit-slice/mask primitives) and curl's HTTP/protocol library (1.01) — while
general-purpose libc (musl), a query engine (SQLite), and a TCP/IP network
stack's control-flow-heavy core (lwIP, linux net/ipv4/) all sit at or below
parity. **This reinforces, rather than changes, the earlier recommendation:**
scope "several-fold" to codec/protocol/crypto-primitive code specifically;
it is not a general property of C.

## C++ context table (Chromium) — NOT part of the C aggregate above

**This table is context only.** The paper's shape-frequency claim is about C
(`folding.tex` targets a C-to-verifiable-C static subset); Chromium is C++
and is reported separately, never folded into the 12-codebase C total or
ratio table above.

### Codebase 11 (C++ context): Chromium

- Upstream: `https://github.com/chromium/chromium` (via
  `git clone --depth 1 --filter=blob:none --sparse`, then
  `git sparse-checkout set base net/base`)
- Pinned commit: `32a630c4fe397978f938a2dd10b4c3ea271c6a98`
- **Outcome: included, not abandoned.** Disk usage stayed far under the 4 GB
  budget throughout: 92 MB immediately after the blobless sparse clone, 143 MB
  after `sparse-checkout set base net/base` materialized the working tree —
  roughly 3% of the abandonment threshold. No errors at any step.
- Files counted: `base/*.cc` (151 files) + `base/numerics/*.cc` (1 file) +
  `net/base/*.cc` (189 files) = 341 files, per task instruction.
  **`base/numerics/*.cc` matched only 1 file** (`byte_conversions_unittest.cc`,
  a test), **not** the `checked_math`/`safe_conversions`/`clamped_math`
  implementations the task specifically called out — those live entirely in
  header files (`checked_math.h`, `checked_math_impl.h`,
  `safe_conversions.h`, `clamped_math.h`, ...), which the `*.cc` glob cannot
  reach. This is a genuine, reportable finding about the C++ idiom itself:
  **`checked_math`-style safety wrappers in Chromium are template/header-only
  and syntactically invisible to a `.cc`-file census** — not a script bug,
  but a scope mismatch inherent to how modern C++ header-only numeric
  libraries are structured (the opposite of the paper's C static-subset
  style, where such logic would normally live in a translation unit).
- **`base/*.cc` and `net/base/*.cc` are not curated**: per task instruction
  ("census over base/*.cc + ...") the raw glob was used as-is. This pulls in
  a large fraction of `_unittest.cc` and `_fuzzer.cc` files alongside
  production code (a quick scan of the file listing below shows roughly a
  third to half of `base/*.cc` entries are `_unittest.cc`) — test code is
  counted identically to production code in every class below. Flagged
  here rather than silently filtered, consistent with how the C rows above
  handle similar in-scope test/harness files (SQLite's `test*.c`, FreeRTOS's
  `croutine.c`).

Reproduce:
```
git clone --depth 1 --filter=blob:none --sparse https://github.com/chromium/chromium chromium
git -C chromium sparse-checkout set base net/base
python3 eval/census.py --dir chromium --files base/*.cc base/numerics/*.cc net/base/*.cc
```

### file listing (341 files)

| File | LoC | File | LoC |
|---|---|---|---|
| base/at_exit.cc | 119 | base/at_exit_unittest.cc | 87 |
| base/atomicops.cc | 66 | base/atomicops_unittest.cc | 256 |
| base/auto_reset_unittest.cc | 69 | base/barrier_callback_unittest.cc | 167 |
| base/barrier_closure.cc | 60 | base/barrier_closure_unittest.cc | 88 |
| base/base64.cc | 169 | base/base64_decode_fuzzer.cc | 17 |
| base/base64_encode_fuzzer.cc | 43 | base/base64_unittest.cc | 188 |
| base/base64url.cc | 180 | base/base64url_unittest.cc | 241 |
| base/base_paths.cc | 116 | base/base_paths_android.cc | 71 |
| base/base_paths_apple.cc | 50 | base/base_paths_fuchsia.cc | 56 |
| base/base_paths_posix.cc | 102 | base/base_paths_win.cc | 261 |
| base/big_endian_perftest.cc | 138 | base/bit_cast_unittest.cc | 30 |
| base/bits_unittest.cc | 147 | base/build_time_unittest.cc | 33 |
| base/byte_size.cc | 124 | base/byte_size_unittest.cc | 2124 |
| base/callback_list.cc | 40 | base/callback_list_unittest.cc | 641 |
| base/cancelable_callback_unittest.cc | 269 | base/check.cc | 473 |
| base/check_deref_unittest.cc | 58 | base/check_example.cc | 41 |
| base/check_is_test.cc | 26 | base/check_is_test_unittest.cc | 15 |
| base/check_op.cc | 133 | base/check_unittest.cc | 827 |
| base/command_line.cc | 860 | base/command_line_fuzzer.cc | 146 |
| base/command_line_rust_shim.cc | 86 | base/command_line_unittest.cc | 1037 |
| base/compiler_hardening_test.cc | 128 | base/component_export_unittest.cc | 83 |
| base/cpu.cc | 359 | base/cpu_unittest.cc | 201 |
| base/enterprise_util.cc | 13 | base/enterprise_util_win.cc | 40 |
| base/environment.cc | 110 | base/environment_unittest.cc | 98 |
| base/feature_list.cc | 1464 | base/feature_list_internal.cc | 28 |
| base/feature_list_unittest.cc | 1920 | base/features.cc | 292 |
| base/file_descriptor_posix.cc | 26 | base/file_descriptor_store.cc | 74 |
| base/file_version_info_win.cc | 206 | base/file_version_info_win_unittest.cc | 173 |
| base/gmock_unittest.cc | 130 | base/immediate_crash_unittest.cc | 246 |
| base/lazy_instance_helpers.cc | 69 | base/lazy_instance_unittest.cc | 322 |
| base/libcpp_hardening_test.cc | 67 | base/linux_util.cc | 248 |
| base/linux_util_unittest.cc | 76 | base/location.cc | 125 |
| base/location_unittest.cc | 40 | base/logging.cc | 1295 |
| base/logging_chromeos.cc | 93 | base/logging_unittest.cc | 1051 |
| base/logging_win.cc | 157 | base/moving_window_unittest.cc | 207 |
| base/native_library_fuchsia.cc | 115 | base/native_library_posix.cc | 71 |
| base/native_library_unittest.cc | 213 | base/native_library_win.cc | 209 |
| base/no_destructor_unittest.cc | 232 | base/numerics/byte_conversions_unittest.cc | 243 |
| base/observer_list_internal.cc | 18 | base/observer_list_perftest.cc | 141 |
| base/observer_list_threadsafe.cc | 27 | base/observer_list_threadsafe_unittest.cc | 605 |
| base/observer_list_types.cc | 16 | base/observer_list_unittest.cc | 1213 |
| base/one_shot_event.cc | 92 | base/one_shot_event_unittest.cc | 174 |
| base/os_compat_android.cc | 43 | base/parameter_pack_unittest.cc | 87 |
| base/path_service.cc | 402 | base/path_service_unittest.cc | 478 |
| base/pending_task.cc | 79 | base/pickle.cc | 591 |
| base/pickle_fuzzer.cc | 139 | base/pickle_unittest.cc | 788 |
| base/protobuf_hardening_test.cc | 45 | base/rand_util.cc | 230 |
| base/rand_util_fuchsia.cc | 61 | base/rand_util_perftest.cc | 59 |
| base/rand_util_posix.cc | 180 | base/rand_util_unittest.cc | 486 |
| base/rand_util_win.cc | 97 | base/run_loop.cc | 353 |
| base/run_loop_rust_shim.cc | 25 | base/run_loop_unittest.cc | 676 |
| base/safe_numerics_unittest.cc | 2385 | base/scoped_add_feature_flags.cc | 92 |
| base/scoped_add_feature_flags_unittest.cc | 85 | base/scoped_clear_last_error_unittest.cc | 57 |
| base/scoped_clear_last_error_win.cc | 20 | base/scoped_environment_variable_override.cc | 51 |
| base/scoped_generic_unittest.cc | 375 | base/scoped_multi_source_observation_unittest.cc | 226 |
| base/scoped_native_library.cc | 41 | base/scoped_native_library_unittest.cc | 50 |
| base/scoped_observation_unittest.cc | 297 | base/security_unittest.cc | 114 |
| base/sequence_checker.cc | 29 | base/sequence_checker_impl.cc | 203 |
| base/sequence_checker_unittest.cc | 533 | base/sequence_token.cc | 108 |
| base/sequence_token_unittest.cc | 203 | base/simdutf_shim.cc | 20 |
| base/stack_canary_linux.cc | 108 | base/stack_canary_linux_unittest.cc | 45 |
| base/state_transitions_unittest.cc | 100 | base/std_clamp_unittest.cc | 47 |
| base/stl_util_unittest.cc | 236 | base/supports_user_data.cc | 150 |
| base/supports_user_data_unittest.cc | 152 | base/sync_socket.cc | 31 |
| base/sync_socket_posix.cc | 218 | base/sync_socket_unittest.cc | 318 |
| base/sync_socket_win.cc | 320 | base/sys_byteorder_unittest.cc | 75 |
| base/syslog_logging.cc | 185 | base/thread_annotations_unittest.cc | 59 |
| base/token.cc | 87 | base/token_unittest.cc | 91 |
| base/tools_sanity_unittest.cc | 478 | base/traits_bag_unittest.cc | 202 |
| base/tuple_unittest.cc | 111 | base/unguessable_token.cc | 67 |
| base/unguessable_token_unittest.cc | 216 | base/unsafe_buffers_unittest.cc | 35 |
| base/uuid.cc | 182 | base/uuid_unittest.cc | 207 |
| base/value_iterators.cc | 115 | base/value_iterators_unittest.cc | 242 |
| base/values.cc | 1418 | base/values_unittest.cc | 2441 |
| base/version.cc | 209 | base/version_unittest.cc | 229 |
| base/vlog.cc | 184 | base/vlog_unittest.cc | 187 |
| net/base/address_family.cc | 61 | net/base/address_family_unittest.cc | 30 |
| net/base/address_list.cc | 154 | net/base/address_list_unittest.cc | 292 |
| net/base/address_map_cache_linux.cc | 57 | net/base/address_map_linux.cc | 18 |
| net/base/address_tracker_linux.cc | 736 | net/base/address_tracker_linux_fuzzer.cc | 39 |
| net/base/address_tracker_linux_test_util.cc | 145 | net/base/address_tracker_linux_unittest.cc | 904 |
| net/base/auth.cc | 44 | net/base/backoff_entry.cc | 187 |
| net/base/backoff_entry_serializer.cc | 175 | net/base/backoff_entry_serializer_fuzzer.cc | 177 |
| net/base/backoff_entry_serializer_unittest.cc | 405 | net/base/backoff_entry_unittest.cc | 314 |
| net/base/base64.cc | 54 | net/base/base64_unittest.cc | 129 |
| net/base/bssl_refcounted.cc | 52 | net/base/canonicalize_host_fuzzer.cc | 29 |
| net/base/chunked_upload_data_stream.cc | 117 | net/base/chunked_upload_data_stream_unittest.cc | 370 |
| net/base/connection_endpoint_metadata.cc | 131 | net/base/connection_endpoint_metadata_test_util.cc | 130 |
| net/base/connection_endpoint_metadata_unittest.cc | 51 | net/base/connection_migration_information.cc | 40 |
| net/base/data_url.cc | 517 | net/base/data_url_fuzzer.cc | 45 |
| net/base/data_url_unittest.cc | 469 | net/base/directory_lister.cc | 206 |
| net/base/directory_lister_unittest.cc | 289 | net/base/directory_listing_unittest.cc | 97 |
| net/base/does_url_match_filter.cc | 48 | net/base/does_url_match_filter_unittest.cc | 184 |
| net/base/elements_upload_data_stream.cc | 160 | net/base/elements_upload_data_stream_unittest.cc | 878 |
| net/base/expiring_cache_unittest.cc | 309 | net/base/fake_proxy_delegate.cc | 66 |
| net/base/features.cc | 1044 | net/base/file_stream.cc | 140 |
| net/base/file_stream_context.cc | 278 | net/base/file_stream_context_posix.cc | 121 |
| net/base/file_stream_context_win.cc | 250 | net/base/file_stream_unittest.cc | 1174 |
| net/base/filename_util.cc | 184 | net/base/filename_util_icu.cc | 96 |
| net/base/filename_util_internal.cc | 341 | net/base/filename_util_unittest.cc | 797 |
| net/base/fuzzer_test_support.cc | 63 | net/base/hash_value.cc | 113 |
| net/base/hash_value_unittest.cc | 26 | net/base/hex_utils.cc | 24 |
| net/base/host_mapping_rules.cc | 150 | net/base/host_mapping_rules_unittest.cc | 194 |
| net/base/host_port_pair.cc | 148 | net/base/host_port_pair_fuzzer.cc | 11 |
| net/base/host_port_pair_unittest.cc | 198 | net/base/interval_test.cc | 277 |
| net/base/io_buffer.cc | 193 | net/base/io_buffer_unittest.cc | 231 |
| net/base/ip_address.cc | 628 | net/base/ip_address_unittest.cc | 1106 |
| net/base/ip_address_util.cc | 46 | net/base/ip_address_util_unittest.cc | 46 |
| net/base/ip_endpoint.cc | 330 | net/base/ip_endpoint_unittest.cc | 532 |
| net/base/is_potentially_trustworthy.cc | 440 | net/base/is_potentially_trustworthy_unittest.cc | 77 |
| net/base/isolation_info.cc | 525 | net/base/isolation_info_unittest.cc | 881 |
| net/base/load_flags_to_string.cc | 66 | net/base/load_flags_to_string_unittest.cc | 35 |
| net/base/load_timing_info.cc | 21 | net/base/load_timing_info_test_util.cc | 63 |
| net/base/load_timing_internal_info.cc | 16 | net/base/logging_network_change_observer.cc | 143 |
| net/base/lookup_string_in_fixed_set.cc | 241 | net/base/lookup_string_in_fixed_set_fuzzer.cc | 21 |
| net/base/lookup_string_in_fixed_set_unittest.cc | 269 | net/base/mime_sniffer.cc | 837 |
| net/base/mime_sniffer_fuzzer.cc | 53 | net/base/mime_sniffer_perftest.cc | 107 |
| net/base/mime_sniffer_unittest.cc | 628 | net/base/mime_util.cc | 1036 |
| net/base/mime_util_unittest.cc | 710 | net/base/mock_network_change_notifier.cc | 130 |
| net/base/mock_proxy_delegate.cc | 13 | net/base/net_errors.cc | 146 |
| net/base/net_errors_posix.cc | 133 | net/base/net_errors_unittest.cc | 90 |
| net/base/net_errors_win.cc | 127 | net/base/net_platform_api_util.cc | 28 |
| net/base/net_platform_api_util_unittest.cc | 78 | net/base/net_string_util_icu.cc | 71 |
| net/base/net_string_util_icu_alternatives_android.cc | 145 | net/base/net_string_util_unittest.cc | 46 |
| net/base/network_activity_monitor.cc | 34 | net/base/network_activity_monitor_unittest.cc | 67 |
| net/base/network_anonymization_key.cc | 316 | net/base/network_anonymization_key_unittest.cc | 628 |
| net/base/network_change_notifier.cc | 1138 | net/base/network_change_notifier_apple_unittest.cc | 433 |
| net/base/network_change_notifier_fuchsia.cc | 169 | net/base/network_change_notifier_fuchsia_unittest.cc | 710 |
| net/base/network_change_notifier_linux.cc | 181 | net/base/network_change_notifier_linux_unittest.cc | 58 |
| net/base/network_change_notifier_passive.cc | 128 | net/base/network_change_notifier_passive_unittest.cc | 153 |
| net/base/network_change_notifier_unittest.cc | 298 | net/base/network_change_notifier_win.cc | 514 |
| net/base/network_change_notifier_win_unittest.cc | 1109 | net/base/network_config_watcher_apple.cc | 183 |
| net/base/network_cost_change_notifier_win.cc | 258 | net/base/network_cost_change_notifier_win_unittest.cc | 237 |
| net/base/network_delegate.cc | 247 | net/base/network_delegate_impl.cc | 120 |
| net/base/network_delegate_unittest.cc | 125 | net/base/network_handle.cc | 41 |
| net/base/network_interfaces.cc | 64 | net/base/network_interfaces_fuchsia.cc | 200 |
| net/base/network_interfaces_getifaddrs.cc | 301 | net/base/network_interfaces_getifaddrs_android.cc | 267 |
| net/base/network_interfaces_getifaddrs_unittest.cc | 318 | net/base/network_interfaces_linux.cc | 288 |
| net/base/network_interfaces_linux_unittest.cc | 191 | net/base/network_interfaces_posix.cc | 63 |
| net/base/network_interfaces_unittest.cc | 84 | net/base/network_interfaces_win.cc | 338 |
| net/base/network_interfaces_win_unittest.cc | 343 | net/base/network_isolation_key.cc | 203 |
| net/base/network_isolation_key_unittest.cc | 429 | net/base/network_isolation_partition.cc | 31 |
| net/base/network_notification_thread_mac.cc | 54 | net/base/parse_number.cc | 150 |
| net/base/parse_number_unittest.cc | 250 | net/base/parse_url_hostname_to_address_fuzzer.cc | 32 |
| net/base/pickle_base_types_unittest.cc | 38 | net/base/pickle_fuzzer.cc | 36 |
| net/base/pickle_unittest.cc | 340 | net/base/platform_mime_util_fuchsia.cc | 33 |
| net/base/platform_mime_util_linux.cc | 66 | net/base/platform_mime_util_win.cc | 58 |
| net/base/port_util.cc | 303 | net/base/port_util_unittest.cc | 130 |
| net/base/prioritized_dispatcher.cc | 148 | net/base/prioritized_dispatcher_unittest.cc | 550 |
| net/base/prioritized_task_runner.cc | 105 | net/base/prioritized_task_runner_unittest.cc | 385 |
| net/base/priority_queue_unittest.cc | 264 | net/base/privacy_mode.cc | 25 |
| net/base/proxy_chain.cc | 265 | net/base/proxy_chain_unittest.cc | 847 |
| net/base/proxy_delegate.cc | 20 | net/base/proxy_server.cc | 178 |
| net/base/proxy_server_unittest.cc | 237 | net/base/proxy_string_util.cc | 312 |
| net/base/proxy_string_util_unittest.cc | 488 | net/base/reconnect_notifier.cc | 96 |
| net/base/request_priority.cc | 31 | net/base/scheme_host_port_matcher.cc | 111 |
| net/base/scheme_host_port_matcher_rule.cc | 262 | net/base/scheme_host_port_matcher_rule_unittest.cc | 495 |
| net/base/scheme_host_port_matcher_unittest.cc | 71 | net/base/schemeful_site.cc | 289 |
| net/base/schemeful_site_unittest.cc | 584 | net/base/sockaddr_storage.cc | 55 |
| net/base/sockaddr_util_posix.cc | 66 | net/base/sockaddr_util_posix_unittest.cc | 111 |
| net/base/test_completion_callback.cc | 61 | net/base/test_completion_callback_unittest.cc | 141 |
| net/base/test_proxy_delegate.cc | 220 | net/base/transport_info.cc | 90 |
| net/base/unescape_url_component_fuzzer.cc | 22 | net/base/upload_bytes_element_reader.cc | 65 |
| net/base/upload_bytes_element_reader_unittest.cc | 99 | net/base/upload_data_stream.cc | 202 |
| net/base/upload_element_reader.cc | 13 | net/base/upload_file_element_reader.cc | 335 |
| net/base/upload_file_element_reader_unittest.cc | 328 | net/base/url_search_params.cc | 63 |
| net/base/url_search_params_unittest.cc | 151 | net/base/url_search_params_view.cc | 141 |
| net/base/url_search_params_view_unittest.cc | 260 | net/base/url_unescape_iterator.cc | 133 |
| net/base/url_unescape_iterator_unittest.cc | 378 | net/base/url_util.cc | 603 |
| net/base/url_util_unittest.cc | 1034 | net/base/winsock_init.cc | 48 |
| net/base/winsock_util.cc | 21 | | |
| **Total (341 files)** | **87003** | | |

| Class | Count |
|---|---|
| 1. for-loops total / stride-1 / strided | 548 / 160 / 1 |
| 2. geometric/shift loop updates | 22 |
| 3. bit-slice (shift-then-mask / mask-then-shift) | 6 / 0 = **6** |
| 4. monotone mask `|=` | 29 |
| 5. two-sided clamp (ternary / if-pair) | 0 / 0 = **0** (macro-call info: 660) |
| 6. narrowing casts | 5 |
| 7. switches (total/contig/sparse/sparse-dup/symbolic) | 85 / 3 / 2 / 0 / 80 |
| 8. lockstep (dual-incr / ptr-bound) | 2 / 9 = **11** |
| 9. zigzag/byteswap (enc / dec / byteswap-shiftor) | 0 / 0 / 1 = **1** |
| countable loops (for+while) | 626 |
| value-shaping sites (2+3+4+5+6+9) | 63 |
| **ratio, value-shaping / countable loops** | **0.10** |
| ratio, value-shaping / **for-loops only** | **0.11** |

### C++-idiom note (why these raw counts should not be compared directly to the C rows)

- **Class 5 (clamp), informational macro-call count = 660**, dramatically
  higher than every C codebase in the sample (max elsewhere: SQLite's 67).
  This is **not** evidence Chromium clamps more — the `CLAMP_MACRO_CALL_RE`
  regex (`\b(MIN|MAX|CLAMP|LIMIT)\s*\(`) is case-insensitive by design
  (to catch C's `MIN()`/`MAX()` macro-name conventions), which means it also
  matches C++'s lowercase `std::min(`, `std::max(`, `std::clamp(` call sites
  wherever they appear as bare `min(`/`max(`/`clamp(` after a `using`
  declaration or ADL — a call idiom essentially absent from the C sample
  (which spells clamping via macros, not function templates). The 660 count
  is a mix of genuine clamp-adjacent calls and an unknown amount of
  unrelated lowercase-`min`/`max` noise; not usable as a cross-language
  comparison point without manual review.
- **Class 6 (narrowing cast) = 5**, the lowest in the entire sample relative
  to LoC (87003 lines). The regex only matches C-style casts
  (`(uint8_t)`/`(uint16_t)`/`(int8_t)`/`(int16_t)`/`(char)`); Chromium's
  style guide mandates `static_cast<uint8_t>(...)` for narrowing conversions,
  a syntax the class-6 regex does not match at all. This under-counts
  narrowing-cast sites in C++ code by construction — a structural blind spot
  specific to this language, not a finding that Chromium narrows less.
- **Class 1 "other/unclassified update" = 374 of 548 for-loops (68%)**, far
  higher than any C codebase (next highest: curl at 32%). Chromium's
  for-loops are dominated by C++ range-based/iterator idioms
  (`for (const auto& x : container)`, `for (auto it = begin(); it != end();
  ++it)`) whose update clause (`++it`) parses as `stride1` when it matches,
  but whose *init*/*cond* shape and iterator-typed increment target fall
  outside what `classify_for_update` expects from C index variables in many
  cases — consistent with the class 1 docstring's own caveat that it targets
  scalar-index loops. Read the low bit-slice/mask/clamp counts (class
  2/3/4/6 all near zero relative to LoC) together with this: **Chromium's
  `base`/`net/base` loop and value-shaping vocabulary is largely not the
  vocabulary this census's regex suite is built to measure** — containers,
  iterators, and header-only checked-math templates replace the raw
  shift/mask/cast idioms the C sample is full of. This is the paper's own
  point in miniature: the syntactic shapes cataloged are a C-specific
  vocabulary, and this C++ codebase is exactly the kind of evidence that
  the vocabulary doesn't just "also happen to work" in C++ — it mostly
  doesn't apply.

---

## Domain read (counts only, no speculation beyond them)

- **Crypto is value-fold-heavy; general infrastructure code is not.** OpenSSL
  crypto (1.01/1.58) and linux crypto/ (0.78/1.19) both clear or approach 1×
  under at least one denominator, with the highest raw bit-slice counts in
  the sample (OpenSSL 342, linux crypto/ 168) — consistent with crypto
  primitives (block ciphers, hash compression functions, big-number
  arithmetic) being built from shift/mask/rotate value transforms. SQLite
  (0.27/0.38) and musl (0.28/0.43) — a query engine and a general libc — sit
  at the bottom of the ratio table; their loop-heavy tree-walk/VM-dispatch
  and one-function-per-file string/stdio code do not carry the same
  bit-manipulation density.
- **Linux kernel lib/ differs sharply from linux net/ipv4/, and both differ
  from crypto/.** lib/'s curated data-structure files have the highest
  monotone-`|=` density relative to for-loops in the Linux slices (80 `|=`
  against 131 for-loops) but a lower bit-slice count (21) than crypto/ (168);
  net/ipv4/ inverts this — very high `|=` (344, the highest raw count in the
  whole sample) but low bit-slice (7) and by far the most switches (207,
  driven by protocol/socket-option dispatch), reflecting flag-accumulation
  (socket/route flags) rather than bit-field extraction as its dominant
  value-shaping idiom. crypto/ is the only Linux slice with a non-trivial
  strided for-loop count (11) and reaches parity or above under either
  denominator, unlike lib/ and net/ipv4/.
- **Sparse-vs-contiguous switches remain codebase-dependent, not
  symbolic-name-dependent**, confirming the four-codebase finding on a much
  larger switch population: across the 8 new C codebases, 43 of 512 switches
  are numerically sparse, 60 contiguous, and 789 remain
  symbolic-unclassified (unresolved by the numeric-only classifier) — curl
  alone contributes 291 of those unclassified switches (mostly protocol
  state-machine and cURL-option dispatch), and linux net/ipv4/ contributes
  190 (socket-option and protocol-family symbolic dispatch). The manual
  spot-check discipline from the original four codebases (resolve a sample
  by reading the defining header) was not repeated exhaustively here given
  the ~5x larger switch population; this is flagged as unclosed manual work,
  not silently assumed sparse or contiguous.
- **musl's zero bit-slice count (class 3) across 6675 lines of
  string/stdlib/stdio is a genuine null result**, matching the earlier
  finding that FreeRTOS-Kernel's lib/list/queue/scheduler slice also scored
  zero on class 3: string/memory primitives and generic-libc code
  (`memcpy`, `strcmp`, `qsort`, `printf`-family dispatch) do not, in this
  sample, express themselves as shift-then-mask bit-slice extraction — that
  idiom is concentrated in the protocol/crypto codebases (nanopb, OpenSSL,
  linux crypto/, curl, lwIP) and largely absent from general-purpose libc
  and query-engine code (musl, SQLite both near-zero: 0 and 64 respectively,
  the latter driven mostly by SQLite's own varint/UTF-8 encoding helpers,
  not by libc-style code).
- **SQLite has the highest raw lockstep-pointer count in the entire sample
  (158)**, more than 4x the next highest (linux net/ipv4/ and OpenSSL, both
  in the 15–26 range) — consistent with SQLite's B-tree/VDBE/tokenizer code
  walking parallel cursor/pointer pairs extensively, and with its being by
  far the largest single dataset (207986 LoC, more than the other 11 C
  codebases combined at their next-largest, curl at 100403).

## Known-weak classes (regex judged too weak to trust as an absolute count)

1. **Class 1, "strided" sub-count (`+= c`/`-= c`, c>1) — genuinely 0 in all
   four codebases, verified independently** (a direct scan for any `for(...)`
   header containing `+=` or `-=` anywhere in its clauses, across all four
   codebases, also returned 0 — this is not a parsing bug). The classic
   spelling `for (i = 0; i < n; i += 4)` simply does not occur in this
   sample; all unit- and multi-step iteration is expressed via `++`/`--`
   with the stride folded into an index multiply inside the body, or via
   pointer walking, or via `while` loops with explicit length counters. This
   is a real, reportable null result about how real code spells strides —
   not evidence the pattern-1 fold doesn't apply (index-multiply and
   pointer-stride forms are outside this regex's scope by design, see class
   8's separate, narrower detector).

2. **Class 5, two-sided clamps — 0/0/0/0 across all four codebases, judged
   NOT trustworthy as an absolute frequency measure.** zlib alone has 7
   `MIN`/`MAX`/`CLAMP`/`LIMIT` macro-call sites (counted informationally,
   not in the class total), meaning where zlib clamps values it does so
   through a macro/function call, a shape the if/ternary-only regex is not
   designed to match (the task's own class definition is if/ternary
   bounding, not macro calls). What was done: the macro-call count is
   reported as a separate, explicit "informational, not totalled" line per
   codebase rather than folded into class 5's total, so the 0s are not
   silently read as "no clamping in this code" — they mean specifically
   "no if/ternary-shaped clamp found," which is a narrower and weaker claim.

3. **Class 9, zigzag sub-counts — 0/0 in all four codebases, including
   nanopb, which is confirmed by direct source reading to implement
   wire-format zigzag encode/decode** (`pb_encode_svarint`/
   `pb_decode_svarint` in `pb_encode.c`/`pb_decode.c`). Both are spelled as a
   branch (`value < 0 ? ~((value & mask) << 1) : value << 1` /
   `value & 1 ? ~(value>>1) : value>>1`), not the single-expression XOR idiom
   `(x << 1) ^ (x >> k)` the regex matches. This is a confirmed, specific
   regex miss on the one codebase most likely to exercise this class — class
   9's zigzag sub-count should be read as a lower bound on the XOR-spelled
   idiom only, not as evidence zigzag encoding is rare in this sample (it is
   present, just spelled differently). What was done: stated here plainly
   rather than widening the regex mid-census (which would break the "one
   fixed script, syntactic occurrence" reproducibility contract) — a wider
   detector (matching both the XOR and the branch forms) is a candidate
   follow-up for the script, not made here.

4. **Class 7, symbolic-switch classification — resolved by hand for 10 of
   20 symbolic switches** (all 8 in nanopb, all 3 in libcsp, 2 of 5 in zlib,
   2 of 4 in FreeRTOS-Kernel), by reading the defining header/enum for each.
   The automated numeric-only classifier cannot resolve macro/enum case
   labels, so it is not "too weak" so much as structurally unable to do this
   part of the job without a symbol table; the manual step is the stated,
   necessary complement (per the task's own instruction: "count switches +
   manually classify the top few; state method"). The finding is codebase-
   dependent and not predictable from symbolic-ness alone: nanopb's
   symbolic switches are uniformly sparse (bit-packed protocol fields);
   libcsp's are uniformly contiguous (plain sequential enums); zlib and
   FreeRTOS are mixed. A blind "if symbolic then sparse" heuristic would
   have been wrong for 2 of 4 codebases.

5. **Class 8, lockstep/pointer-bound — a documented naming-convention
   dependency**, not exercised as a false-negative here since the 0 results
   in nanopb/libcsp were independently confirmed genuine (no pointer-named
   or `end`-bound comparisons exist in those files at all — an abstraction
   choice, not a miss), but the detector would silently miss a pointer-bound
   loop using different naming (`stop`, `limit`, `finish`, or a bare
   letter other than `p`/`q`) in codebases that do use such loops (zlib's 6
   and FreeRTOS's 4 hits both come through the `end`-substring path). Not
   independently verified as complete on zlib/FreeRTOS; treat class 8 counts
   there as a lower bound.


6. **Class 5 (clamp) informational macro-call regex is language-ambiguous
   (case-insensitive `MIN|MAX|CLAMP|LIMIT`) — confirmed to misfire on C++.**
   Chromium's informational macro-call count (660, see the C++ context
   section) is inflated by matching lowercase `std::min(`/`std::max(`/
   `std::clamp(` call sites, an idiom essentially absent from the C sample.
   Not fixed (would change the regex mid-census, breaking reproducibility
   for the existing 12 C rows); flagged as C++-specific noise, informational
   count only, never folded into any codebase's totalled class-5 count.

7. **Class 7 (sparse-state switch), manual spot-check not repeated at scale
   for the 8 new C codebases.** The original four codebases' symbolic
   switches (20 total) were each individually resolved by reading the
   defining header/enum (see per-codebase spot-checks above). The 8 new
   codebases add 769 more symbolic-unclassified switches (curl 291, linux
   net/ipv4/ 190, sqlite 138, openssl 70, linux crypto/ 19, lwip 19, musl 19,
   linux lib/ 23) — none of these were individually resolved by hand; doing
   so at this scale is future work, stated here rather than silently
   assumed sparse or contiguous. The 43-sparse/60-contiguous/789-symbolic
   split for the new codebases should be read as strictly a numeric-literal
   classification, with the "true" sparse/contiguous split for the symbolic
   population unknown.

8. **musl clone URL: the task-suggested GitHub mirror
   (`github.com/bminor/musl`) does not exist** — `git clone` returned
   "Repository not found." The official `git.musl-libc.org/git/musl` was
   used instead (see Codebase 9 above) and pinned normally. Reported as a
   genuine finding about the suggested mirror, not silently worked around.

## Other structural blind spots (apply project-wide, not codebase-specific)

- No macro expansion: a `for` loop or bit operation hidden behind a
  project macro (e.g. `FOR_EACH(x, list)`) is invisible to every class.
- No preprocessor conditional resolution: code inside `#ifdef` branches
  that would not compile for a given target is still counted (e.g. zlib's
  `#ifndef NO_GZCOMPRESS`-gated cases).
- Bit-slice regexes require a single paren level; `((x + off) >> k) & m`
  is missed.
- `find_switches` does not exclude nested switch bodies from an outer
  switch's case list (observed once, in zlib's `inflate.c:505` — see
  codebase 3 above); a documented, not corrected, limitation.
- `find_while_loops` matches a `do { ... } while(cond);` trailing
  condition as if it were a second loop header (inflates the `while_total`
  denominator by roughly the number of `do/while` loops present; not
  separately counted in this census).

- **`find_switches`'s nested-switch blind spot (documented for zlib's
  `inflate.c:505`) is structural, not a one-off** — any codebase with a
  `switch` nested inside another `switch`'s case body will have the inner
  switch's case labels folded into the outer switch's reported case list.
  Not independently re-audited across the 8 new codebases (SQLite's VDBE
  opcode dispatch and curl's protocol state machines are both switch-heavy
  and plausible candidates); flagged as unclosed, not assumed absent.
- **musl's one-function-per-file style produces many single-digit-LoC
  files** (`strcmp.c` is 7 lines) where a single syntactic match can swing a
  file's per-file ratio arbitrarily — an aggregation-level statistic
  (musl's 212-file, 6675-LoC totals) is far more stable than any per-file
  number from this codebase would be; no per-file ratios are reported here
  for exactly this reason.

## Exact pinned commits (summary)

| Codebase | Upstream | Commit sha |
|---|---|---|
| nanopb | `https://github.com/nanopb/nanopb.git` | `4e73df5a72e470a8195c3efdaf1d0e45e22c3af7` |
| libcsp | `https://github.com/libcsp/libcsp.git` | `57c5c4857f30dd083bb373fbc79a65c6ae9f1a62` |
| zlib | `https://github.com/madler/zlib.git` | `e3dc0a85b7032e98380dec011bc8f2c2ee0d8fca` |
| FreeRTOS-Kernel | `https://github.com/FreeRTOS/FreeRTOS-Kernel.git` | `ce221a8bb468e462ca6b435cef66a9636e00baf4` |
| Linux kernel (lib/, crypto/, net/ipv4/) | `https://github.com/torvalds/linux.git` (local checkout's own `origin` is a local mirror path, see Codebase 5 note) | `8934827db5403eae57d4537114a9ff88b0a8460f` |
| OpenSSL | `https://github.com/openssl/openssl.git` | `2924476b5591e691e904c4baf57894c526c4b8de` |
| SQLite | `https://github.com/sqlite/sqlite.git` | `912706d94a5b9dc20fffc335ab4be0606bd2d4ab` |
| lwIP | `https://github.com/lwip-tcpip/lwip.git` | `3d896ba0a37ff3ce73270ca5e230707fe47f60e3` |
| musl | `https://git.musl-libc.org/git/musl` | `f21a96538f78fa8e2040831b4209b35f2fb581da` |
| curl | `https://github.com/curl/curl.git` | `9b29495863c967e2768ea1c517f3ad28a50a9a1b` |
| Chromium (C++ context, not in the C aggregate) | `https://github.com/chromium/chromium` | `32a630c4fe397978f938a2dd10b4c3ea271c6a98` |

All eleven are public repositories (the Linux kernel checkout's own `origin`
remote is a local mirror path rather than a direct GitHub URL, but the
commit sha is independently checkable against the canonical public upstream
URLs listed). No private codebase's name, path, or content appears anywhere
in this document or was read while producing it.
