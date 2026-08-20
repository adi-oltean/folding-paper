/* equiv_case2.c -- experiment E0, case 2: nanopb ZigZag core of pb_encode_svarint.
 *
 * Role of this file: MECHANICAL VERIFIER.  The twin is UNTRUSTED input from
 * research/ai-driven-folding.md.  The real function is 64-bit, so the input space (2^64) is
 * out of reach for enumeration.  Following the memo's stated verifier level, this program
 * runs:
 *
 *   L1  8-bit  analog, exhaustive          -- COMPLETE PROOF at that width (2^8 inputs)
 *   L2  16-bit analog, exhaustive          -- COMPLETE PROOF at that width (2^16 inputs)
 *   L3  32-bit analog, exhaustive          -- COMPLETE PROOF at that width (2^32 inputs)
 *   L4  64-bit boundary set                -- evidence only (hand-chosen corner inputs)
 *   L5  64-bit deterministic LCG sample    -- evidence only (sampling, NOT a proof)
 *
 * L1-L3 are the "same expression shapes at narrow types": every operator of the source is
 * reproduced at the analog width, including the `((T)-1) >> 1` mask, the `<< 1`, the `~`,
 * and the signed/unsigned conversions.  Nothing is 64-bit-specific about the shape.
 *
 * Build: gcc -O2 -Wall -Wextra -std=c99 -o out/equiv_case2 equiv_case2.c
 * Exit:  0 if every level agrees, 1 on the first mismatch found at any level.
 */

#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>

/* ---------------------------------------------------------------------------------------
 * f_orig -- the original, at 64 bits.
 *
 * Source (read-only, copied exactly):
 *   nanopb: pb_encode.c:625-635
 *
 *       bool checkreturn pb_encode_svarint(pb_ostream_t *stream, pb_int64_t value)
 *       {
 *           pb_uint64_t zigzagged;
 *           pb_uint64_t mask = ((pb_uint64_t)-1) >> 1; // Satisfy clang -fsanitize=integer
 *           if (value < 0)
 *               zigzagged = ~(((pb_uint64_t)value & mask) << 1);
 *           else
 *               zigzagged = (pb_uint64_t)value << 1;
 *
 *           return pb_encode_varint(stream, zigzagged);
 *       }
 *
 * Standalone-ization: only the zigzag computation is extracted (per the experiment's scope);
 * the stream I/O tail `return pb_encode_varint(stream, zigzagged);` is replaced by
 * `return zigzagged;`, and pb_int64_t / pb_uint64_t are int64_t / uint64_t (their default
 * typedefs in pb.h when PB_WITHOUT_64BIT is not defined).  The four lines that compute
 * `zigzagged` are byte-for-byte the upstream ones.
 * ------------------------------------------------------------------------------------- */
static uint64_t zz_orig64(int64_t value)
{
	uint64_t zigzagged;
	uint64_t mask = ((uint64_t)-1) >> 1; /* Satisfy clang -fsanitize=integer */
	if (value < 0)
		zigzagged = ~(((uint64_t)value & mask) << 1);
	else
		zigzagged = (uint64_t)value << 1;

	return zigzagged;
}

/* ---------------------------------------------------------------------------------------
 * f_twin -- UNTRUSTED proposal, copied verbatim from the memo
 * (research/ai-driven-folding.md, "Case 2 ... Proposed twin"):
 *
 *       if (value < 0) zigzagged = 2*(pb_uint64_t)(-(value + 1)) + 1;
 *       else           zigzagged = 2*(pb_uint64_t)value;
 * ------------------------------------------------------------------------------------- */
static uint64_t zz_twin64(int64_t value)
{
	uint64_t zigzagged;
	if (value < 0) zigzagged = 2*(uint64_t)(-(value + 1)) + 1;
	else           zigzagged = 2*(uint64_t)value;
	return zigzagged;
}

/* ---- 8-bit analog: identical expression shapes at int8_t / uint8_t -------------------- */
static uint8_t zz_orig8(int8_t value)
{
	uint8_t zigzagged;
	uint8_t mask = (uint8_t)(((uint8_t)-1) >> 1);
	if (value < 0)
		zigzagged = (uint8_t)~(uint8_t)(((uint8_t)value & mask) << 1);
	else
		zigzagged = (uint8_t)((uint8_t)value << 1);
	return zigzagged;
}

static uint8_t zz_twin8(int8_t value)
{
	uint8_t zigzagged;
	if (value < 0) zigzagged = (uint8_t)(2u*(uint8_t)(-(value + 1)) + 1u);
	else           zigzagged = (uint8_t)(2u*(uint8_t)value);
	return zigzagged;
}

/* ---- 16-bit analog -------------------------------------------------------------------- */
static uint16_t zz_orig16(int16_t value)
{
	uint16_t zigzagged;
	uint16_t mask = (uint16_t)(((uint16_t)-1) >> 1);
	if (value < 0)
		zigzagged = (uint16_t)~(uint16_t)(((uint16_t)value & mask) << 1);
	else
		zigzagged = (uint16_t)((uint16_t)value << 1);
	return zigzagged;
}

static uint16_t zz_twin16(int16_t value)
{
	uint16_t zigzagged;
	if (value < 0) zigzagged = (uint16_t)(2u*(uint16_t)(-(value + 1)) + 1u);
	else           zigzagged = (uint16_t)(2u*(uint16_t)value);
	return zigzagged;
}

/* ---- 32-bit analog -------------------------------------------------------------------- */
static uint32_t zz_orig32(int32_t value)
{
	uint32_t zigzagged;
	uint32_t mask = ((uint32_t)-1) >> 1;
	if (value < 0)
		zigzagged = ~(((uint32_t)value & mask) << 1);
	else
		zigzagged = (uint32_t)value << 1;
	return zigzagged;
}

static uint32_t zz_twin32(int32_t value)
{
	uint32_t zigzagged;
	/* -(value + 1) is computed in int64_t so that value == INT32_MIN cannot overflow the
	 * 32-bit int the promotion would otherwise pick; the 64-bit source has no such issue
	 * because -(INT64_MIN + 1) == INT64_MAX is representable. */
	if (value < 0) zigzagged = 2u*(uint32_t)(-((int64_t)value + 1)) + 1u;
	else           zigzagged = 2u*(uint32_t)value;
	return zigzagged;
}

static uint64_t g_n = 0;
static uint64_t g_mism = 0;

#define REPORT_MISMATCH(suite, vfmt, v, ofmt, o, tfmt, t)                                  \
	do {                                                                               \
		printf("MISMATCH: case2 suite=%s value=" vfmt " f_orig=" ofmt                \
		       " f_twin=" tfmt "\n", (suite), (v), (o), (t));                        \
		printf("RESULT case=2 suite=%s status=REJECT\n", (suite));                   \
	} while (0)

int main(void)
{
	int64_t i64;
	int32_t v32;
	uint64_t i;
	unsigned k;

	/* ---- L1: 8-bit exhaustive ---- */
	{
		uint64_t n = 0;
		for (i = 0; i < 256; i++) {
			int8_t v = (int8_t)(uint8_t)i;
			uint8_t a = zz_orig8(v), b = zz_twin8(v);
			n++;
			if (a != b) {
				REPORT_MISMATCH("8bit-exhaustive", "%d", (int)v,
						"0x%02x", (unsigned)a, "0x%02x", (unsigned)b);
				return 1;
			}
		}
		g_n += n;
		printf("EQUIV: case2/8bit-exhaustive %" PRIu64 " inputs checked, 0 mismatches\n", n);
		printf("RESULT case=2 suite=8bit-exhaustive status=EQUIV n=%" PRIu64
		       " mismatches=0 level=complete-proof-at-width-8\n", n);
	}

	/* ---- L2: 16-bit exhaustive ---- */
	{
		uint64_t n = 0;
		for (i = 0; i < 65536; i++) {
			int16_t v = (int16_t)(uint16_t)i;
			uint16_t a = zz_orig16(v), b = zz_twin16(v);
			n++;
			if (a != b) {
				REPORT_MISMATCH("16bit-exhaustive", "%d", (int)v,
						"0x%04x", (unsigned)a, "0x%04x", (unsigned)b);
				return 1;
			}
		}
		g_n += n;
		printf("EQUIV: case2/16bit-exhaustive %" PRIu64 " inputs checked, 0 mismatches\n", n);
		printf("RESULT case=2 suite=16bit-exhaustive status=EQUIV n=%" PRIu64
		       " mismatches=0 level=complete-proof-at-width-16\n", n);
	}

	/* ---- L3: 32-bit exhaustive ---- */
	{
		uint64_t n = 0;
		for (i = 0; i < (UINT64_C(1) << 32); i++) {
			uint32_t a, b;
			v32 = (int32_t)(uint32_t)i;
			a = zz_orig32(v32);
			b = zz_twin32(v32);
			n++;
			if (a != b) {
				REPORT_MISMATCH("32bit-exhaustive", "%" PRId32, v32,
						"0x%08" PRIx32, a, "0x%08" PRIx32, b);
				return 1;
			}
		}
		g_n += n;
		printf("EQUIV: case2/32bit-exhaustive %" PRIu64 " inputs checked, 0 mismatches\n", n);
		printf("RESULT case=2 suite=32bit-exhaustive status=EQUIV n=%" PRIu64
		       " mismatches=0 level=complete-proof-at-width-32\n", n);
	}

	/* ---- L4: 64-bit boundary set ---- */
	{
		static const int64_t bset[] = {
			INT64_MIN, INT64_MIN + 1, INT64_MIN + 2,
			-(INT64_C(1) << 62) - 1, -(INT64_C(1) << 62), -(INT64_C(1) << 62) + 1,
			-(INT64_C(1) << 32) - 1, -(INT64_C(1) << 32), -(INT64_C(1) << 32) + 1,
			-(INT64_C(1) << 31) - 1, -(INT64_C(1) << 31), -(INT64_C(1) << 31) + 1,
			-3, -2, -1, 0, 1, 2, 3,
			(INT64_C(1) << 31) - 1, (INT64_C(1) << 31), (INT64_C(1) << 31) + 1,
			(INT64_C(1) << 32) - 1, (INT64_C(1) << 32), (INT64_C(1) << 32) + 1,
			(INT64_C(1) << 62) - 1, (INT64_C(1) << 62), (INT64_C(1) << 62) + 1,
			INT64_MAX - 2, INT64_MAX - 1, INT64_MAX
		};
		uint64_t n = 0;
		for (k = 0; k < sizeof bset / sizeof bset[0]; k++) {
			uint64_t a = zz_orig64(bset[k]), b = zz_twin64(bset[k]);
			n++;
			if (a != b) {
				REPORT_MISMATCH("64bit-boundary", "%" PRId64, bset[k],
						"0x%016" PRIx64, a, "0x%016" PRIx64, b);
				return 1;
			}
		}
		g_n += n;
		printf("EQUIV: case2/64bit-boundary %" PRIu64 " inputs checked, 0 mismatches\n", n);
		printf("RESULT case=2 suite=64bit-boundary status=EQUIV n=%" PRIu64
		       " mismatches=0 level=evidence-only-boundary-set\n", n);
	}

	/* ---- L5: 64-bit deterministic sample (NOT a proof) ---- */
	{
		uint64_t st = UINT64_C(0x243F6A8885A308D3);   /* fixed seed: digits of pi */
		uint64_t n = 0;
		for (i = 0; i < UINT64_C(20000000); i++) {
			uint64_t a, b;
			st = st * UINT64_C(6364136223846793005) + UINT64_C(1442695040888963407);
			i64 = (int64_t)st;
			a = zz_orig64(i64);
			b = zz_twin64(i64);
			n++;
			if (a != b) {
				REPORT_MISMATCH("64bit-lcg-sample", "%" PRId64, i64,
						"0x%016" PRIx64, a, "0x%016" PRIx64, b);
				return 1;
			}
		}
		g_n += n;
		printf("EQUIV: case2/64bit-lcg-sample %" PRIu64 " inputs checked, 0 mismatches\n", n);
		printf("RESULT case=2 suite=64bit-lcg-sample status=EQUIV n=%" PRIu64
		       " mismatches=0 level=sampling-not-a-proof\n", n);
	}

	printf("EQUIV: case2 %" PRIu64 " inputs checked, %" PRIu64 " mismatches\n", g_n, g_mism);
	printf("RESULT case=2 status=EQUIV n=%" PRIu64 " mismatches=0"
	       " level=complete-proof-at-widths-8-16-32-plus-64bit-evidence\n", g_n);
	return 0;
}
