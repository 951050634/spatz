// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

#include "vector_macros.h"
#include <stdint.h>

#define VFCMACC_VV_VM1(vd, vs1, vs2)                                           \
  asm volatile(".insn r 0x57, 0x1, 0x75, " vd ", " vs1 ", " vs2               \
               ::: "memory")

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

int main(void) {
  INIT_CHECK();

  TEST_CASE1();
  TEST_CASE2();
  TEST_CASE3();
  TEST_CASE4();

  EXIT_CHECK();
}
