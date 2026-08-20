/* equiv_case_neg.c -- experiment E0, NEGATIVE CONTROL (the mutant analog).
 *
 * The point of the AI-driven-folding architecture is that the proposer is entirely
 * untrusted and a non-equivalent proposal must be REJECTED by the mechanical checker, with
 * the analysis left unchanged (fail-safe).  A verifier that only ever says EQUIV proves
 * nothing about that claim, so this file feeds it a deliberately wrong proposal.
 *
 * "Proposal N" is case 1's twin with a plausible-looking off-by-one: the SECOND fold is
 * dropped.  It looks right -- the single fold is the textbook one-complement fold, the
 * comment even claims the bound -- and it is right on the overwhelming majority of inputs.
 * It is wrong exactly on the carry-out inputs.
 *
 * Build: gcc -O2 -Wall -Wextra -std=c99 -o out/equiv_case_neg equiv_case_neg.c
 * Exit:  1 (rejection) is the EXPECTED, PASSING outcome for this file; 0 would mean the
 *        verifier failed to catch a known-wrong proposal, which is itself a defect.
 */

#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>

/* Original: linux: include/net/checksum.h:142-146 */
static unsigned short f_orig(unsigned int sum)
{
	sum += (sum >> 16) | (sum << 16);
	return (unsigned short)(sum >> 16);
}

/* Proposal N -- WRONG BY CONSTRUCTION.  Case 1's twin with the second fold removed. */
static unsigned short f_twin_N(unsigned int sum)
{
	unsigned int t = (sum & 0xffffu) + (sum >> 16);   /* <= 0x1FFFE */
	return (unsigned short)t;                         /* claims: already folded.  it is not */
}

int main(void)
{
	uint64_t i;
	uint64_t n = 0;
	uint64_t mism = 0;
	uint32_t first_x = 0;
	unsigned int first_a = 0, first_b = 0;

	for (i = 0; i < (UINT64_C(1) << 32); i++) {
		uint32_t x = (uint32_t)i;
		unsigned int a = f_orig(x);
		unsigned int b = f_twin_N(x);
		n++;
		if (a != b) {
			if (mism == 0) { first_x = x; first_a = a; first_b = b; }
			mism++;
		}
	}

	if (mism == 0) {
		printf("EQUIV: case-neg %" PRIu64 " inputs checked, 0 mismatches\n", n);
		printf("RESULT case=neg status=UNEXPECTED-EQUIV n=%" PRIu64 " mismatches=0\n", n);
		return 0;   /* a failure of the experiment, not a success */
	}

	printf("MISMATCH: case-neg first input sum=0x%08" PRIx32
	       " f_orig=0x%04x f_twin_N=0x%04x\n", first_x, first_a, first_b);
	printf("REJECTED: proposal N rejected after scanning %" PRIu64 " inputs; %" PRIu64
	       " of them are mismatches\n", n, mism);
	printf("RESULT case=neg status=REJECT n=%" PRIu64 " mismatches=%" PRIu64
	       " first_input=0x%08" PRIx32 " orig=0x%04x twin=0x%04x\n",
	       n, mism, first_x, first_a, first_b);
	return 1;
}
