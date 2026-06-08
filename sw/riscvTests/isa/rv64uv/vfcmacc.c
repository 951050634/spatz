// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

#include "float_macros.h"
#include "vector_macros.h"
#include <stdint.h>

#define VFCMACC_VV_VM1(vd, vs1, vs2)                                           \
  asm volatile(".insn r 0x57, 0x1, 0x75, " vd ", " vs1 ", " vs2               \
               ::: "memory")

#define VFCMACC_VV_VM0(vd, vs1, vs2)                                           \
  asm volatile(".insn r 0x57, 0x1, 0x74, " vd ", " vs1 ", " vs2               \
               ::: "memory")

#define VSET_POLICY(VLEN, VTYPE, LMUL, TAIL, MASK)                             \
  do {                                                                         \
    unsigned int vl;                                                           \
    asm volatile("vsetvli %[vl], %[A]," #VTYPE "," #LMUL "," #TAIL ","       \
                 #MASK "\n"                                                    \
                 : [vl] "+r"(vl)                                               \
                 : [A] "r"(VLEN));                                             \
  } while (0)

static void copy_sources_to_v4_v7(void) {
  asm volatile("vmv.v.v v4, v0\n"
               "vmv.v.v v5, v1\n"
               "vmv.v.v v6, v2\n"
               "vmv.v.v v7, v3\n"
               ::: "memory");
}

static void load_odd_lane_mask(void) {
  VLOAD_8(v0, 0xaa, 0xaa, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
}

static void save_accumulator_to_v24_v25(void) {
  asm volatile("vmv.v.v v24, v8\n"
               "vmv.v.v v25, v9\n"
               ::: "memory");
}

static unsigned int read_fflags(void) {
  unsigned int flags;
  asm volatile("frflags %0" : "=r"(flags));
  return flags;
}

static void clear_fflags(void) { asm volatile("fsflags %0" ::"r"(0)); }

static void check_fflags(uint32_t casenum, unsigned int expected) {
  unsigned int got = read_fflags();
  if (got != expected) {
    printf("[TC %u] fflags FAILED. Got 0x%x, expected 0x%x.\n", casenum, got,
           expected);
    num_failed++;
    return;
  }

  printf("[TC %u] fflags PASSED.\n", casenum);
}

static void compare_v8_v9_active_else_orig(uint32_t casenum,
                                           uint32_t active_mask,
                                           uint32_t active_limit) {
  VSTORE_U32(v8);
  uint32_t got_real[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_real[i] = Ru32[i];
  }

  VSTORE_U32(v16);
  uint32_t ref_real[16];
  for (unsigned int i = 0; i < 16; i++) {
    ref_real[i] = Ru32[i];
  }

  VSTORE_U32(v24);
  for (unsigned int i = 0; i < 16; i++) {
    uint32_t expected = (i < active_limit && ((active_mask >> i) & 1u))
                            ? ref_real[i]
                            : Ru32[i];
    if (got_real[i] != expected) {
      printf("[TC %u] real[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_real[i], expected);
      num_failed++;
      return;
    }
  }

  VSTORE_U32(v9);
  uint32_t got_imag[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_imag[i] = Ru32[i];
  }

  VSTORE_U32(v17);
  uint32_t ref_imag[16];
  for (unsigned int i = 0; i < 16; i++) {
    ref_imag[i] = Ru32[i];
  }

  VSTORE_U32(v25);
  for (unsigned int i = 0; i < 16; i++) {
    uint32_t expected = (i < active_limit && ((active_mask >> i) & 1u))
                            ? ref_imag[i]
                            : Ru32[i];
    if (got_imag[i] != expected) {
      printf("[TC %u] imag[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_imag[i], expected);
      num_failed++;
      return;
    }
  }

  printf("[TC %u] PASSED.\n", casenum);
}

static void compare_e16_v8_v9_active_else_orig(uint32_t casenum,
                                               uint32_t active_mask,
                                               uint32_t active_limit) {
  VSTORE_U16(v8);
  uint16_t got_real[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_real[i] = Ru16[i];
  }

  VSTORE_U16(v16);
  uint16_t ref_real[16];
  for (unsigned int i = 0; i < 16; i++) {
    ref_real[i] = Ru16[i];
  }

  VSTORE_U16(v24);
  for (unsigned int i = 0; i < 16; i++) {
    uint16_t expected = (i < active_limit && ((active_mask >> i) & 1u))
                            ? ref_real[i]
                            : Ru16[i];
    if (got_real[i] != expected) {
      printf("[TC %u] real[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_real[i], expected);
      num_failed++;
      return;
    }
  }

  VSTORE_U16(v9);
  uint16_t got_imag[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_imag[i] = Ru16[i];
  }

  VSTORE_U16(v17);
  uint16_t ref_imag[16];
  for (unsigned int i = 0; i < 16; i++) {
    ref_imag[i] = Ru16[i];
  }

  VSTORE_U16(v25);
  for (unsigned int i = 0; i < 16; i++) {
    uint16_t expected = (i < active_limit && ((active_mask >> i) & 1u))
                            ? ref_imag[i]
                            : Ru16[i];
    if (got_imag[i] != expected) {
      printf("[TC %u] imag[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_imag[i], expected);
      num_failed++;
      return;
    }
  }

  printf("[TC %u] PASSED.\n", casenum);
}

#if ELEN == 64
static void compare_e64_v8_v9_active_else_orig(uint32_t casenum,
                                               uint32_t active_mask,
                                               uint32_t active_limit) {
  VSTORE_U64(v8);
  uint64_t got_real[8];
  for (unsigned int i = 0; i < 8; i++) {
    got_real[i] = Ru64[i];
  }

  VSTORE_U64(v16);
  uint64_t ref_real[8];
  for (unsigned int i = 0; i < 8; i++) {
    ref_real[i] = Ru64[i];
  }

  VSTORE_U64(v24);
  for (unsigned int i = 0; i < 8; i++) {
    uint64_t expected = (i < active_limit && ((active_mask >> i) & 1u))
                            ? ref_real[i]
                            : Ru64[i];
    if (got_real[i] != expected) {
      printf("[TC %u] real[%u] FAILED. Got %lu, expected %lu.\n", casenum, i,
             got_real[i], expected);
      num_failed++;
      return;
    }
  }

  VSTORE_U64(v9);
  uint64_t got_imag[8];
  for (unsigned int i = 0; i < 8; i++) {
    got_imag[i] = Ru64[i];
  }

  VSTORE_U64(v17);
  uint64_t ref_imag[8];
  for (unsigned int i = 0; i < 8; i++) {
    ref_imag[i] = Ru64[i];
  }

  VSTORE_U64(v25);
  for (unsigned int i = 0; i < 8; i++) {
    uint64_t expected = (i < active_limit && ((active_mask >> i) & 1u))
                            ? ref_imag[i]
                            : Ru64[i];
    if (got_imag[i] != expected) {
      printf("[TC %u] imag[%u] FAILED. Got %lu, expected %lu.\n", casenum, i,
             got_imag[i], expected);
      num_failed++;
      return;
    }
  }

  printf("[TC %u] PASSED.\n", casenum);
}
#endif

static void compare_v8_v9_against_v16_v17(uint32_t casenum) {
  VSTORE_U32(v8);
  uint32_t got_real[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_real[i] = Ru32[i];
  }

  VSTORE_U32(v16);
  for (unsigned int i = 0; i < 16; i++) {
    if (got_real[i] != Ru32[i]) {
      printf("[TC %u] real[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_real[i], Ru32[i]);
      num_failed++;
      return;
    }
  }

  VSTORE_U32(v9);
  uint32_t got_imag[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_imag[i] = Ru32[i];
  }

  VSTORE_U32(v17);
  for (unsigned int i = 0; i < 16; i++) {
    if (got_imag[i] != Ru32[i]) {
      printf("[TC %u] imag[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_imag[i], Ru32[i]);
      num_failed++;
      return;
    }
  }

  printf("[TC %u] PASSED.\n", casenum);
}

static void compare_v10_v11_against_v20_v21(uint32_t casenum) {
  VSTORE_U32(v10);
  uint32_t got_real[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_real[i] = Ru32[i];
  }

  VSTORE_U32(v20);
  for (unsigned int i = 0; i < 16; i++) {
    if (got_real[i] != Ru32[i]) {
      printf("[TC %u] real-read[%u] FAILED. Got %u, expected %u.\n", casenum,
             i, got_real[i], Ru32[i]);
      num_failed++;
      return;
    }
  }

  VSTORE_U32(v11);
  uint32_t got_imag[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_imag[i] = Ru32[i];
  }

  VSTORE_U32(v21);
  for (unsigned int i = 0; i < 16; i++) {
    if (got_imag[i] != Ru32[i]) {
      printf("[TC %u] imag-read[%u] FAILED. Got %u, expected %u.\n", casenum,
             i, got_imag[i], Ru32[i]);
      num_failed++;
      return;
    }
  }

  printf("[TC %u] PASSED.\n", casenum);
}

static void compare_e16_v8_v9_against_v16_v17(uint32_t casenum) {
  VSTORE_U16(v8);
  uint16_t got_real[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_real[i] = Ru16[i];
  }

  VSTORE_U16(v16);
  for (unsigned int i = 0; i < 16; i++) {
    if (got_real[i] != Ru16[i]) {
      printf("[TC %u] real[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_real[i], Ru16[i]);
      num_failed++;
      return;
    }
  }

  VSTORE_U16(v9);
  uint16_t got_imag[16];
  for (unsigned int i = 0; i < 16; i++) {
    got_imag[i] = Ru16[i];
  }

  VSTORE_U16(v17);
  for (unsigned int i = 0; i < 16; i++) {
    if (got_imag[i] != Ru16[i]) {
      printf("[TC %u] imag[%u] FAILED. Got %u, expected %u.\n", casenum, i,
             got_imag[i], Ru16[i]);
      num_failed++;
      return;
    }
  }

  printf("[TC %u] PASSED.\n", casenum);
}

static void compare_e64_v8_v9_against_v16_v17(uint32_t casenum) {
  VSTORE_U64(v8);
  uint64_t got_real[8];
  for (unsigned int i = 0; i < 8; i++) {
    got_real[i] = Ru64[i];
  }

  VSTORE_U64(v16);
  for (unsigned int i = 0; i < 8; i++) {
    if (got_real[i] != Ru64[i]) {
      printf("[TC %u] real[%u] FAILED. Got %lu, expected %lu.\n", casenum, i,
             got_real[i], Ru64[i]);
      num_failed++;
      return;
    }
  }

  VSTORE_U64(v9);
  uint64_t got_imag[8];
  for (unsigned int i = 0; i < 8; i++) {
    got_imag[i] = Ru64[i];
  }

  VSTORE_U64(v17);
  for (unsigned int i = 0; i < 8; i++) {
    if (got_imag[i] != Ru64[i]) {
      printf("[TC %u] imag[%u] FAILED. Got %lu, expected %lu.\n", casenum, i,
             got_imag[i], Ru64[i]);
      num_failed++;
      return;
    }
  }

  printf("[TC %u] PASSED.\n", casenum);
}

static void load_e32_fixture(void) {
  VSET(16, e32, m1);

  VLOAD_32(v0, 0x3f800000, 0xbf000000, 0x40000000, 0xc0400000, 0x3e800000,
           0xbf800000, 0x00000000, 0x80000000, 0x3f400000, 0xbf200000,
           0x3f99999a, 0xbf99999a, 0x40400000, 0xc0800000, 0x3dcccccd,
           0xbdcccccd);
  VLOAD_32(v1, 0x40000000, 0x3f800000, 0xbf800000, 0x3f000000, 0xc0000000,
           0x3e800000, 0x80000000, 0x00000000, 0xbf400000, 0x3f200000,
           0xbf000000, 0x3f000000, 0x3fc00000, 0xbfc00000, 0x3e4ccccd,
           0xbe4ccccd);
  VLOAD_32(v2, 0x3f000000, 0x3f400000, 0xbf400000, 0xbf800000, 0x40000000,
           0xc0000000, 0x3f800000, 0xbf800000, 0x3e800000, 0xbe800000,
           0x3fa00000, 0xbfa00000, 0x3f666666, 0xbf666666, 0x3dcccccd,
           0xbdcccccd);
  VLOAD_32(v3, 0xbf000000, 0x3f000000, 0x3f800000, 0xbf400000, 0x3e800000,
           0xbe800000, 0x00000000, 0x80000000, 0x3fc00000, 0xbfc00000,
           0x3e99999a, 0xbe99999a, 0xbfa00000, 0x3fa00000, 0xbe4ccccd,
           0x3e4ccccd);
  VLOAD_32(v8, 0x3dcccccd, 0xbdcccccd, 0x3e4ccccd, 0xbe4ccccd, 0x3f000000,
           0xbf000000, 0x00000000, 0x80000000, 0x3f800000, 0xbf800000,
           0x40000000, 0xc0000000, 0x40400000, 0xc0400000, 0x3f19999a,
           0xbf19999a);
  VLOAD_32(v9, 0xbe4ccccd, 0x3e4ccccd, 0xbf000000, 0x3f000000, 0x3dcccccd,
           0xbdcccccd, 0x80000000, 0x00000000, 0x3f000000, 0xbf000000,
           0x3f800000, 0xbf800000, 0xc0000000, 0x40000000, 0x3e99999a,
           0xbe99999a);
  VLOAD_32(v16, 0x3dcccccd, 0xbdcccccd, 0x3e4ccccd, 0xbe4ccccd, 0x3f000000,
           0xbf000000, 0x00000000, 0x80000000, 0x3f800000, 0xbf800000,
           0x40000000, 0xc0000000, 0x40400000, 0xc0400000, 0x3f19999a,
           0xbf19999a);
  VLOAD_32(v17, 0xbe4ccccd, 0x3e4ccccd, 0xbf000000, 0x3f000000, 0x3dcccccd,
           0xbdcccccd, 0x80000000, 0x00000000, 0x3f000000, 0xbf000000,
           0x3f800000, 0xbf800000, 0xc0000000, 0x40000000, 0x3e99999a,
           0xbe99999a);
}

static void load_e32_special_fixture(void) {
  VSET(16, e32, m1);

  VLOAD_32(v0, 0x00000000, 0x80000000, pInff, pInff, pMaxf, 0x3f800000,
           0x3f800000, sNaNf, 0x3f800000, 0xbf800000, 0x3f800000, 0x3f800000,
           0x3eaaaaab, 0x3eaaaaab, 0x00000000, 0x80000000);
  VLOAD_32(v1, 0x00000000, 0x80000000, pInff, pInff, pMaxf, 0x3f800000,
           0x3f800000, 0x3f800000, sNaNf, 0xbf800000, 0x3f800000, 0x3f800000,
           0x3eaaaaab, 0x3eaaaaab, 0x80000000, 0x00000000);
  VLOAD_32(v2, 0x3f800000, 0x3f800000, 0x3f800000, mInff, pMaxf, sNaNf,
           0x3f800000, 0x3f800000, 0x3f800000, 0x3f800000, 0x3eaaaaab,
           0x3eaaaaab, 0x3eaaaaab, 0x3eaaaaab, 0x3f800000, 0x3f800000);
  VLOAD_32(v3, 0x3f800000, 0x3f800000, 0x3f800000, pInff, pMaxf, 0x3f800000,
           sNaNf, 0x3f800000, 0x3f800000, 0x3f800000, 0x3eaaaaab, 0x3eaaaaab,
           0x3eaaaaab, 0x3eaaaaab, 0x3f800000, 0x3f800000);
  VLOAD_32(v8, 0x00000000, 0x00000000, 0x00000000, 0x00000000, pMaxf,
           0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000,
           0x3eaaaaab, 0x3eaaaaab, 0x00000000, 0x00000000, 0x80000000,
           0x80000000);
  VLOAD_32(v9, 0x00000000, 0x00000000, 0x00000000, 0x00000000, pMaxf,
           0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000,
           0x3eaaaaab, 0x3eaaaaab, 0x00000000, 0x00000000, 0x80000000,
           0x80000000);
  VLOAD_32(v16, 0x00000000, 0x00000000, 0x00000000, 0x00000000, pMaxf,
           0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000,
           0x3eaaaaab, 0x3eaaaaab, 0x00000000, 0x00000000, 0x80000000,
           0x80000000);
  VLOAD_32(v17, 0x00000000, 0x00000000, 0x00000000, 0x00000000, pMaxf,
           0x00000000, 0x00000000, 0x00000000, 0x00000000, 0x00000000,
           0x3eaaaaab, 0x3eaaaaab, 0x00000000, 0x00000000, 0x80000000,
           0x80000000);
}

static void run_e32_reference_v16_v17(void) {
  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");
}

static void load_e16_fixture(void) {
  VSET(16, e16, m1);

  VLOAD_16(v0, 0x3c00, 0xbc00, 0x4000, 0xc000, 0x3800, 0xb800, 0x3400, 0xb400,
           0x3e00, 0xbe00, 0x4200, 0xc200, 0x0000, 0x8000, 0x3555, 0xb555);
  VLOAD_16(v1, 0x4000, 0x3c00, 0xbc00, 0x3800, 0xc000, 0x3400, 0x8000, 0x0000,
           0xbe00, 0x3e00, 0xbc00, 0x3c00, 0x3a00, 0xba00, 0x3155, 0xb155);
  VLOAD_16(v2, 0x3800, 0x3a00, 0xba00, 0xbc00, 0x4000, 0xc000, 0x3c00, 0xbc00,
           0x3400, 0xb400, 0x3d00, 0xbd00, 0x399a, 0xb99a, 0x2e66, 0xae66);
  VLOAD_16(v3, 0xb800, 0x3800, 0x3c00, 0xba00, 0x3400, 0xb400, 0x0000, 0x8000,
           0x3e00, 0xbe00, 0x3666, 0xb666, 0xbd00, 0x3d00, 0xb155, 0x3155);
  VLOAD_16(v8, 0x2e66, 0xae66, 0x3155, 0xb155, 0x3800, 0xb800, 0x0000, 0x8000,
           0x3c00, 0xbc00, 0x4000, 0xc000, 0x4200, 0xc200, 0x3666, 0xb666);
  VLOAD_16(v9, 0xb155, 0x3155, 0xb800, 0x3800, 0x2e66, 0xae66, 0x8000, 0x0000,
           0x3800, 0xb800, 0x3c00, 0xbc00, 0xc000, 0x4000, 0x3555, 0xb555);
  VLOAD_16(v16, 0x2e66, 0xae66, 0x3155, 0xb155, 0x3800, 0xb800, 0x0000, 0x8000,
           0x3c00, 0xbc00, 0x4000, 0xc000, 0x4200, 0xc200, 0x3666, 0xb666);
  VLOAD_16(v17, 0xb155, 0x3155, 0xb800, 0x3800, 0x2e66, 0xae66, 0x8000, 0x0000,
           0x3800, 0xb800, 0x3c00, 0xbc00, 0xc000, 0x4000, 0x3555, 0xb555);
}

#if ELEN == 64
static void load_e64_fixture(void) {
  VSET(16, e64, m1);

  VLOAD_64(v0, 0x3ff0000000000000, 0xbfe0000000000000, 0x4000000000000000,
           0xc008000000000000, 0x3fd0000000000000, 0xbff0000000000000,
           0x0000000000000000, 0x8000000000000000, 0x3ff8000000000000,
           0xbff8000000000000, 0x4008000000000000, 0xc010000000000000,
           0x3fc999999999999a, 0xbfc999999999999a, 0x3fb999999999999a,
           0xbfb999999999999a);
  VLOAD_64(v1, 0x4000000000000000, 0x3ff0000000000000, 0xbff0000000000000,
           0x3fe0000000000000, 0xc000000000000000, 0x3fd0000000000000,
           0x8000000000000000, 0x0000000000000000, 0xbff8000000000000,
           0x3ff8000000000000, 0xbff0000000000000, 0x3ff0000000000000,
           0x3ff4000000000000, 0xbff4000000000000, 0x3fa999999999999a,
           0xbfa999999999999a);
  VLOAD_64(v2, 0x3fe0000000000000, 0x3ff8000000000000, 0xbff8000000000000,
           0xbff0000000000000, 0x4000000000000000, 0xc000000000000000,
           0x3ff0000000000000, 0xbff0000000000000, 0x3fd0000000000000,
           0xbfd0000000000000, 0x3ff4000000000000, 0xbff4000000000000,
           0x3feb333333333333, 0xbfeb333333333333, 0x3f9999999999999a,
           0xbf9999999999999a);
  VLOAD_64(v3, 0xbfe0000000000000, 0x3fe0000000000000, 0x3ff0000000000000,
           0xbff8000000000000, 0x3fd0000000000000, 0xbfd0000000000000,
           0x0000000000000000, 0x8000000000000000, 0x3ff4000000000000,
           0xbff4000000000000, 0x3fd3333333333333, 0xbfd3333333333333,
           0xbff4000000000000, 0x3ff4000000000000, 0xbfa999999999999a,
           0x3fa999999999999a);
  VLOAD_64(v8, 0x3f9999999999999a, 0xbf9999999999999a, 0x3fa999999999999a,
           0xbfa999999999999a, 0x3fe0000000000000, 0xbfe0000000000000,
           0x0000000000000000, 0x8000000000000000, 0x3ff0000000000000,
           0xbff0000000000000, 0x4000000000000000, 0xc000000000000000,
           0x4008000000000000, 0xc008000000000000, 0x3fe3333333333333,
           0xbfe3333333333333);
  VLOAD_64(v9, 0xbfa999999999999a, 0x3fa999999999999a, 0xbfe0000000000000,
           0x3fe0000000000000, 0x3f9999999999999a, 0xbf9999999999999a,
           0x8000000000000000, 0x0000000000000000, 0x3fe0000000000000,
           0xbfe0000000000000, 0x3ff0000000000000, 0xbff0000000000000,
           0xc000000000000000, 0x4000000000000000, 0x3fd3333333333333,
           0xbfd3333333333333);
  VLOAD_64(v16, 0x3f9999999999999a, 0xbf9999999999999a, 0x3fa999999999999a,
           0xbfa999999999999a, 0x3fe0000000000000, 0xbfe0000000000000,
           0x0000000000000000, 0x8000000000000000, 0x3ff0000000000000,
           0xbff0000000000000, 0x4000000000000000, 0xc000000000000000,
           0x4008000000000000, 0xc008000000000000, 0x3fe3333333333333,
           0xbfe3333333333333);
  VLOAD_64(v17, 0xbfa999999999999a, 0x3fa999999999999a, 0xbfe0000000000000,
           0x3fe0000000000000, 0x3f9999999999999a, 0xbf9999999999999a,
           0x8000000000000000, 0x0000000000000000, 0x3fe0000000000000,
           0xbfe0000000000000, 0x3ff0000000000000, 0xbff0000000000000,
           0xc000000000000000, 0x4000000000000000, 0x3fd3333333333333,
           0xbfd3333333333333);
}
#endif

void TEST_CASE1(void) {
  load_e32_fixture();

  VFCMACC_VV_VM1("v8", "v0", "v2");

  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");

  compare_v8_v9_against_v16_v17(1);
}

void TEST_CASE2(void) {
  load_e32_fixture();

  VFCMACC_VV_VM1("v8", "v0", "v2");
  VFCMACC_VV_VM1("v8", "v0", "v2");

  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               "vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");

  compare_v8_v9_against_v16_v17(2);
}

void TEST_CASE3(void) {
#if ELEN == 64
  load_e64_fixture();

  VFCMACC_VV_VM1("v8", "v0", "v2");

  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");

  compare_e64_v8_v9_against_v16_v17(3);
#else
  printf("[TC 3] SKIPPED: e64 requires ELEN=64.\n");
#endif
}

void TEST_CASE4(void) {
  load_e16_fixture();

  VFCMACC_VV_VM1("v8", "v0", "v2");

  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");

  compare_e16_v8_v9_against_v16_v17(4);
}

void TEST_CASE5(void) {
  load_e32_fixture();
  copy_sources_to_v4_v7();
  save_accumulator_to_v24_v25();
  load_odd_lane_mask();
  VSET_POLICY(16, e32, m1, tu, mu);

  VFCMACC_VV_VM0("v8", "v4", "v6");

  VSET(16, e32, m1);
  asm volatile("vfmacc.vv v16, v4, v6\n"
               "vfnmsac.vv v16, v5, v7\n"
               "vfmacc.vv v17, v4, v7\n"
               "vfmacc.vv v17, v5, v6\n"
               ::: "memory");

  compare_v8_v9_active_else_orig(5, 0xaaaa, 16);
}

void TEST_CASE6(void) {
  load_e32_fixture();
  save_accumulator_to_v24_v25();
  VSET_POLICY(12, e32, m1, tu, ma);

  VFCMACC_VV_VM1("v8", "v0", "v2");

  VSET(16, e32, m1);
  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");

  compare_v8_v9_active_else_orig(6, 0xffff, 12);
}

void TEST_CASE7(void) {
#if ELEN == 64
  load_e64_fixture();
  copy_sources_to_v4_v7();
  save_accumulator_to_v24_v25();
  load_odd_lane_mask();
  VSET_POLICY(16, e64, m1, tu, mu);

  VFCMACC_VV_VM0("v8", "v4", "v6");

  VSET(16, e64, m1);
  asm volatile("vfmacc.vv v16, v4, v6\n"
               "vfnmsac.vv v16, v5, v7\n"
               "vfmacc.vv v17, v4, v7\n"
               "vfmacc.vv v17, v5, v6\n"
               ::: "memory");

  compare_e64_v8_v9_active_else_orig(7, 0xaa, 8);
#else
  printf("[TC 7] SKIPPED: e64 requires ELEN=64.\n");
#endif
}

void TEST_CASE8(void) {
#if ELEN == 64
  load_e64_fixture();
  save_accumulator_to_v24_v25();
  VSET_POLICY(5, e64, m1, tu, ma);

  VFCMACC_VV_VM1("v8", "v0", "v2");

  VSET(16, e64, m1);
  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");

  compare_e64_v8_v9_active_else_orig(8, 0xff, 5);
#else
  printf("[TC 8] SKIPPED: e64 requires ELEN=64.\n");
#endif
}

void TEST_CASE9(void) {
  load_e16_fixture();
  copy_sources_to_v4_v7();
  save_accumulator_to_v24_v25();
  load_odd_lane_mask();
  VSET_POLICY(16, e16, m1, tu, mu);

  VFCMACC_VV_VM0("v8", "v4", "v6");

  VSET(16, e16, m1);
  asm volatile("vfmacc.vv v16, v4, v6\n"
               "vfnmsac.vv v16, v5, v7\n"
               "vfmacc.vv v17, v4, v7\n"
               "vfmacc.vv v17, v5, v6\n"
               ::: "memory");

  compare_e16_v8_v9_active_else_orig(9, 0xaaaa, 16);
}

void TEST_CASE10(void) {
  load_e16_fixture();
  save_accumulator_to_v24_v25();
  VSET_POLICY(11, e16, m1, tu, ma);

  VFCMACC_VV_VM1("v8", "v0", "v2");

  VSET(16, e16, m1);
  asm volatile("vfmacc.vv v16, v0, v2\n"
               "vfnmsac.vv v16, v1, v3\n"
               "vfmacc.vv v17, v0, v3\n"
               "vfmacc.vv v17, v1, v2\n"
               ::: "memory");

  compare_e16_v8_v9_active_else_orig(10, 0xffff, 11);
}

void TEST_CASE11(void) {
  load_e32_special_fixture();

  clear_fflags();
  VFCMACC_VV_VM1("v8", "v0", "v2");
  unsigned int got_fflags = read_fflags();

  clear_fflags();
  run_e32_reference_v16_v17();
  unsigned int ref_fflags = read_fflags();

  compare_v8_v9_against_v16_v17(11);
  check_fflags(11, ref_fflags);
  if (got_fflags != ref_fflags) {
    printf("[TC 11] vfcmacc fflags snapshot FAILED. Got 0x%x, expected 0x%x.\n",
           got_fflags, ref_fflags);
    num_failed++;
    return;
  }
}

void TEST_CASE12(void) {
  load_e32_special_fixture();
  CHANGE_RM(RM_RTZ);

  clear_fflags();
  VFCMACC_VV_VM1("v8", "v0", "v2");
  unsigned int got_fflags = read_fflags();

  clear_fflags();
  run_e32_reference_v16_v17();
  unsigned int ref_fflags = read_fflags();
  CHANGE_RM(RM_RNE);

  compare_v8_v9_against_v16_v17(12);
  check_fflags(12, ref_fflags);
  if (got_fflags != ref_fflags) {
    printf("[TC 12] vfcmacc RTZ fflags snapshot FAILED. Got 0x%x, expected 0x%x.\n",
           got_fflags, ref_fflags);
    num_failed++;
    return;
  }
}

void TEST_CASE13(void) {
  VSET(16, e32, m1);
  VLOAD_32(v0, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000,
           sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf,
           0x3f800000, sNaNf, 0x3f800000);
  VLOAD_32(v1, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000,
           sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf,
           0x3f800000, sNaNf, 0x3f800000);
  VLOAD_32(v2, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000,
           sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf,
           0x3f800000, sNaNf, 0x3f800000);
  VLOAD_32(v3, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000,
           sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf, 0x3f800000, sNaNf,
           0x3f800000, sNaNf, 0x3f800000);
  copy_sources_to_v4_v7();
  VLOAD_32(v8, 0x00000000, 0x3f800000, 0x00000000, 0x3f800000, 0x00000000,
           0x3f800000, 0x00000000, 0x3f800000, 0x00000000, 0x3f800000,
           0x00000000, 0x3f800000, 0x00000000, 0x3f800000, 0x00000000,
           0x3f800000);
  VLOAD_32(v9, 0x00000000, 0x3f800000, 0x00000000, 0x3f800000, 0x00000000,
           0x3f800000, 0x00000000, 0x3f800000, 0x00000000, 0x3f800000,
           0x00000000, 0x3f800000, 0x00000000, 0x3f800000, 0x00000000,
           0x3f800000);
  asm volatile("vmv.v.v v16, v8\n"
               "vmv.v.v v17, v9\n"
               ::: "memory");
  save_accumulator_to_v24_v25();
  load_odd_lane_mask();
  VSET_POLICY(16, e32, m1, tu, mu);

  clear_fflags();
  VFCMACC_VV_VM0("v8", "v4", "v6");
  unsigned int got_fflags = read_fflags();

  clear_fflags();
  asm volatile("vfmacc.vv v16, v4, v6, v0.t\n"
               "vfnmsac.vv v16, v5, v7, v0.t\n"
               "vfmacc.vv v17, v4, v7, v0.t\n"
               "vfmacc.vv v17, v5, v6, v0.t\n"
               ::: "memory");
  unsigned int ref_fflags = read_fflags();
  compare_v8_v9_active_else_orig(13, 0xaaaa, 16);
  check_fflags(13, ref_fflags);
  if (got_fflags != ref_fflags) {
    printf("[TC 13] masked fflags snapshot FAILED. Got 0x%x, expected 0x%x.\n",
           got_fflags, ref_fflags);
    num_failed++;
    return;
  }
}

void TEST_CASE14(void) {
  load_e32_fixture();

  asm volatile(".insn r 0x57, 0x1, 0x75, v8, v0, v2\n"
               "vfadd.vv v10, v8, v0\n"
               "vfadd.vv v11, v9, v1\n"
               ::: "memory");

  run_e32_reference_v16_v17();
  asm volatile("vfadd.vv v20, v16, v0\n"
               "vfadd.vv v21, v17, v1\n"
               ::: "memory");

  compare_v10_v11_against_v20_v21(14);
}

void TEST_CASE15(void) {
  load_e32_fixture();

  asm volatile("vfadd.vv v1, v1, v0\n"
               ".insn r 0x57, 0x1, 0x75, v8, v0, v2\n"
               ::: "memory");

  run_e32_reference_v16_v17();
  compare_v8_v9_against_v16_v17(15);
}

void TEST_CASE16(void) {
  load_e32_fixture();

  asm volatile("vfadd.vv v3, v3, v2\n"
               ".insn r 0x57, 0x1, 0x75, v8, v0, v2\n"
               ::: "memory");

  run_e32_reference_v16_v17();
  compare_v8_v9_against_v16_v17(16);
}

void TEST_CASE17(void) {
  load_e32_fixture();

  asm volatile(".insn r 0x57, 0x1, 0x75, v8, v0, v2\n"
               ".insn r 0x57, 0x1, 0x75, v8, v0, v2\n"
               ".insn r 0x57, 0x1, 0x75, v8, v0, v2\n"
               ::: "memory");

  run_e32_reference_v16_v17();
  run_e32_reference_v16_v17();
  run_e32_reference_v16_v17();

  compare_v8_v9_against_v16_v17(17);
}

void TEST_CASE18(void) {
  static const uint32_t vs1_imag_data[16] = {
      0x3f000000, 0xbf400000, 0x3fc00000, 0xbfc00000,
      0x3e800000, 0xbe800000, 0x40000000, 0xc0000000,
      0x3f800000, 0xbf800000, 0x3dcccccd, 0xbdcccccd,
      0x40400000, 0xc0400000, 0x3e4ccccd, 0xbe4ccccd};
  static const uint32_t vs2_imag_data[16] = {
      0xbf000000, 0x3f400000, 0xbfc00000, 0x3fc00000,
      0xbe800000, 0x3e800000, 0xc0000000, 0x40000000,
      0xbf800000, 0x3f800000, 0xbdcccccd, 0x3dcccccd,
      0xc0400000, 0x40400000, 0xbe4ccccd, 0x3e4ccccd};
  uint32_t *vs1_imag = (uint32_t *)snrt_l1alloc(sizeof(vs1_imag_data));
  uint32_t *vs2_imag = (uint32_t *)snrt_l1alloc(sizeof(vs2_imag_data));
  memcpy(vs1_imag, vs1_imag_data, sizeof(vs1_imag_data));
  memcpy(vs2_imag, vs2_imag_data, sizeof(vs2_imag_data));

  load_e32_fixture();

  asm volatile("vle32.v v1, (%[vs1_imag])\n"
               "vle32.v v3, (%[vs2_imag])\n"
               ".insn r 0x57, 0x1, 0x75, v8, v0, v2\n"
               :
               : [vs1_imag] "r"(vs1_imag), [vs2_imag] "r"(vs2_imag)
               : "memory");

  run_e32_reference_v16_v17();
  compare_v8_v9_against_v16_v17(18);
}

int main(void) {
  INIT_CHECK();

  TEST_CASE1();
  TEST_CASE2();
  TEST_CASE3();
  TEST_CASE4();
  TEST_CASE5();
  TEST_CASE6();
  TEST_CASE7();
  TEST_CASE8();
  TEST_CASE9();
  TEST_CASE10();
  TEST_CASE11();
  TEST_CASE12();
  TEST_CASE13();
  TEST_CASE14();
  TEST_CASE15();
  TEST_CASE16();
  TEST_CASE17();
  TEST_CASE18();

  EXIT_CHECK();
}
