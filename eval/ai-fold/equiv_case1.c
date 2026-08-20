/* equiv_case1.c -- experiment E0, case 1: kernel csum_from32to16.
 *
 * Role of this file: MECHANICAL VERIFIER.  The twin below is UNTRUSTED input, copied
 * verbatim from research/ai-driven-folding.md (the proposing agent's memo).  This program
 * decides input-output equality by exhaustive enumeration of the complete input space
 * (2^32 values of `unsigned int`), which at this width is a PROOF, not a test.
 *
 * Build: gcc -O2 -Wall -Wextra -std=c99 -o out/equiv_case1 equiv_case1.c
 * Exit:  0 on EQUIV, 1 on the first mismatch (reported with inputs and both outputs).
 *
 * No wall-clock appears in the output; progress/size is reported by the loop counter only.
 */

#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>

/* ---------------------------------------------------------------------------------------
 * f_orig -- the original.
 *
 * Source (read-only, copied exactly):
 *   linux: include/net/checksum.h:142-146
 *
 *       static inline unsigned short csum_from32to16(unsigned int sum)
 *       {
 *               sum += (sum >> 16) | (sum << 16);
 *               return (unsigned short)(sum >> 16);
 *       }
 *
 * Standalone-ization: `static inline` -> `static`, and the name.  The body is byte-for-byte
 * the kernel's.  No kernel headers are needed: the function is closed over plain C.
 * ------------------------------------------------------------------------------------- */
static unsigned short f_orig(unsigned int sum)
{
	sum += (sum >> 16) | (sum << 16);
	return (unsigned short)(sum >> 16);
}

/* ---------------------------------------------------------------------------------------
 * f_twin -- UNTRUSTED proposal, copied verbatim from the memo
 * (research/ai-driven-folding.md, "Case 1 ... Proposed twin", including its comments).
 * The verifier does not repair it; if it is wrong, the mismatch is the result.
 * ------------------------------------------------------------------------------------- */
static unsigned short f_twin(unsigned int sum)
{
	unsigned int t = (sum & 0xffffu) + (sum >> 16);   /* <= 0x1FFFE */
	unsigned int r = (t   & 0xffffu) + (t   >> 16);   /* <= 0x10000; exact <= 0xFFFF */
	return (unsigned short)r;
}

int main(void)
{
	uint64_t i;
	uint64_t n = 0;
	uint64_t mism = 0;
	uint32_t first_x = 0;
	unsigned int first_a = 0, first_b = 0;

	/* Measured, not assumed: the concrete maxima of the twin's two intermediates.  These
	 * substantiate the memo's "<= 0x1FFFE" / "exact <= 0xFFFF" comments and expose the
	 * off-by-one between the exact bound and the interval bound 0x10000. */
	uint32_t max_t = 0, max_r = 0;

	for (i = 0; i < (UINT64_C(1) << 32); i++) {
		uint32_t x = (uint32_t)i;
		unsigned int a = f_orig(x);
		unsigned int b = f_twin(x);
		unsigned int t = (x & 0xffffu) + (x >> 16);
		unsigned int r = (t & 0xffffu) + (t >> 16);

		if (t > max_t) max_t = t;
		if (r > max_r) max_r = r;

		n++;
		if (a != b) {
			if (mism == 0) { first_x = x; first_a = a; first_b = b; }
			mism++;
		}
	}

	printf("MAXIMA case=1 max_t=0x%" PRIx32 " max_r=0x%" PRIx32 "\n", max_t, max_r);

	if (mism != 0) {
		printf("MISMATCH: case1 first input sum=0x%08" PRIx32
		       " f_orig=0x%04x f_twin=0x%04x\n", first_x, first_a, first_b);
		printf("RESULT case=1 status=REJECT n=%" PRIu64 " mismatches=%" PRIu64
		       " first_input=0x%08" PRIx32 " orig=0x%04x twin=0x%04x\n",
		       n, mism, first_x, first_a, first_b);
		return 1;
	}

	printf("EQUIV: case1 %" PRIu64 " inputs checked, 0 mismatches\n", n);
	printf("RESULT case=1 status=EQUIV n=%" PRIu64 " mismatches=0 level=full-2^32-exhaustive\n",
	       n);
	return 0;
}
