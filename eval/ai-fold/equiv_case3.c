/* equiv_case3.c -- experiment E0, case 3: kernel _find_first_bit.
 *
 * Role of this file: MECHANICAL VERIFIER.  The twin is UNTRUSTED input from
 * research/ai-driven-folding.md.  Two exhaustive configurations are run:
 *
 *   C1  one 16-bit word : all 2^16 bitmap contents  x  all sizes 0..16
 *       -> 65536 * 17 = 1114112 inputs.  COMPLETE PROOF for that configuration.
 *   C2  two 8-bit words : all 2^8 x 2^8 content pairs x all sizes 0..16
 *       -> 65536 * 17 = 1114112 inputs.  COMPLETE PROOF for that configuration.
 *
 * "Configuration" = (word width, number of words, range of sizes).  Neither configuration
 * is a proof for BITS_PER_LONG = 64 with unbounded word counts; they are complete proofs of
 * the two-level-scan / flat-scan coupling at the widths named, which is where the shape
 * lives.  The production path would be an SMT per-edge VC with the coupling relation as
 * witness (not built in E0).
 *
 * Build: gcc -O2 -Wall -Wextra -std=c99 -o out/equiv_case3 equiv_case3.c
 * Exit:  0 if both configurations agree, 1 on the first mismatch.
 */

#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>

/* ---------------------------------------------------------------------------------------
 * f_orig -- the original two-level word/bit scan.
 *
 * Source (read-only):
 *   linux: lib/find_bit.c:100-103
 *
 *       unsigned long _find_first_bit(const unsigned long *addr, unsigned long size)
 *       {
 *               return FIND_FIRST_BIT(addr[idx], /-* nop *-/, size);
 *       }
 *
 * expanding the FIND_FIRST_BIT macro, which is defined in the SAME FILE at
 *   linux: lib/find_bit.c:29-42
 *
 *       #define FIND_FIRST_BIT(FETCH, MUNGE, size)                                  \
 *       ({                                                                          \
 *               unsigned long idx, val, sz = (size);                                \
 *                                                                                   \
 *               for (idx = 0; idx * BITS_PER_LONG < sz; idx++) {                    \
 *                       val = (FETCH);                                              \
 *                       if (val) {                                                  \
 *                               sz = min(idx * BITS_PER_LONG + __ffs(MUNGE(val)), sz); \
 *                               break;                                              \
 *                       }                                                           \
 *               }                                                                   \
 *                                                                                   \
 *               sz;                                                                 \
 *       })
 *
 * (Note: the macro lives in lib/find_bit.c itself, not in a header -- the per-arch
 * overrides that suppress this generic definition are the `#ifndef find_first_bit` guards
 * around line 96 and the arch `include/asm-generic/bitops/find.h` declarations.)
 *
 * Standalone-ization, and ONLY this:
 *   - BITS_PER_LONG -> the analog word width (16 or 8), so the shape can be enumerated;
 *   - MUNGE is the nop, so MUNGE(val) is val;
 *   - `min(a, b)` -> `((a) < (b) ? (a) : (b))`, the kernel's min() semantics for two
 *     unsigned long operands;
 *   - the statement-expression wrapper becomes a function body with `return sz;`;
 *   - __ffs() is the standalone loop below (see comment there).
 * The control structure -- word loop, early `break`, the `min` clamp -- is unchanged.
 * ------------------------------------------------------------------------------------- */

/* __ffs(word): index of the least significant set bit.  In the kernel this is an arch
 * bit-scan intrinsic (asm-generic/bitops/__ffs.h) and is UNDEFINED for 0; the caller here,
 * as in the kernel, only reaches it under `if (val)`.  A loop is used so this file needs no
 * builtins and so the twin cannot be accused of racing a compiler intrinsic. */
static unsigned long ffs_lsb(unsigned long val)
{
	unsigned long i = 0;
	while (((val >> i) & 1UL) == 0UL)
		i++;
	return i;
}

#define MIN_UL(a, b) (((a) < (b)) ? (a) : (b))

static unsigned long ffb_orig16(const uint16_t *addr, unsigned long size)
{
	unsigned long idx, val, sz = size;

	for (idx = 0; idx * 16UL < sz; idx++) {
		val = addr[idx];
		if (val) {
			sz = MIN_UL(idx * 16UL + ffs_lsb(val), sz);
			break;
		}
	}

	return sz;
}

static unsigned long ffb_orig8(const uint8_t *addr, unsigned long size)
{
	unsigned long idx, val, sz = size;

	for (idx = 0; idx * 8UL < sz; idx++) {
		val = addr[idx];
		if (val) {
			sz = MIN_UL(idx * 8UL + ffs_lsb(val), sz);
			break;
		}
	}

	return sz;
}

/* ---------------------------------------------------------------------------------------
 * f_twin -- UNTRUSTED proposal, from the memo
 * (research/ai-driven-folding.md, "Case 3 ... Proposed twin"):
 *
 *       flat single-index scan
 *       for (k = 0; k < size; k++) if (bit k set) return k; return size;
 *
 * "bit k set" is spelled out with the word/bit split the caller's storage forces; the twin's
 * point is that the RETURNED value is the loop's single affine induction variable, not a
 * composition `word*BITS + bitpos`.
 * ------------------------------------------------------------------------------------- */
static unsigned long ffb_twin16(const uint16_t *addr, unsigned long size)
{
	unsigned long k;

	for (k = 0; k < size; k++)
		if ((addr[k / 16UL] >> (k % 16UL)) & 1u)
			return k;

	return size;
}

static unsigned long ffb_twin8(const uint8_t *addr, unsigned long size)
{
	unsigned long k;

	for (k = 0; k < size; k++)
		if ((addr[k / 8UL] >> (k % 8UL)) & 1u)
			return k;

	return size;
}

int main(void)
{
	uint64_t n1 = 0, n2 = 0;
	uint32_t w;
	unsigned long size;
	unsigned p, q;

	/* ---- C1: one 16-bit word, all contents x sizes 0..16 ---- */
	for (w = 0; w < 65536u; w++) {
		uint16_t bm[1];
		bm[0] = (uint16_t)w;
		for (size = 0; size <= 16UL; size++) {
			unsigned long a = ffb_orig16(bm, size);
			unsigned long b = ffb_twin16(bm, size);
			n1++;
			if (a != b) {
				printf("MISMATCH: case3 config=1word16 bitmap=0x%04x size=%lu"
				       " f_orig=%lu f_twin=%lu\n",
				       (unsigned)bm[0], size, a, b);
				printf("RESULT case=3 config=1word16 status=REJECT"
				       " first_bitmap=0x%04x first_size=%lu orig=%lu twin=%lu\n",
				       (unsigned)bm[0], size, a, b);
				return 1;
			}
		}
	}
	printf("EQUIV: case3/1word16 %" PRIu64 " inputs checked, 0 mismatches\n", n1);
	printf("RESULT case=3 config=1word16 status=EQUIV n=%" PRIu64
	       " mismatches=0 level=complete-proof-for-config\n", n1);

	/* ---- C2: two 8-bit words, all content pairs x sizes 0..16 ---- */
	for (p = 0; p < 256u; p++) {
		for (q = 0; q < 256u; q++) {
			uint8_t bm[2];
			bm[0] = (uint8_t)p;
			bm[1] = (uint8_t)q;
			for (size = 0; size <= 16UL; size++) {
				unsigned long a = ffb_orig8(bm, size);
				unsigned long b = ffb_twin8(bm, size);
				n2++;
				if (a != b) {
					printf("MISMATCH: case3 config=2word8 bitmap=[0x%02x,0x%02x]"
					       " size=%lu f_orig=%lu f_twin=%lu\n",
					       (unsigned)bm[0], (unsigned)bm[1], size, a, b);
					printf("RESULT case=3 config=2word8 status=REJECT"
					       " first_bitmap=0x%02x%02x first_size=%lu"
					       " orig=%lu twin=%lu\n",
					       (unsigned)bm[1], (unsigned)bm[0], size, a, b);
					return 1;
				}
			}
		}
	}
	printf("EQUIV: case3/2word8 %" PRIu64 " inputs checked, 0 mismatches\n", n2);
	printf("RESULT case=3 config=2word8 status=EQUIV n=%" PRIu64
	       " mismatches=0 level=complete-proof-for-config\n", n2);

	printf("EQUIV: case3 %" PRIu64 " inputs checked, 0 mismatches\n", n1 + n2);
	printf("RESULT case=3 status=EQUIV n=%" PRIu64 " mismatches=0"
	       " level=complete-proof-for-two-configs\n", n1 + n2);
	return 0;
}
