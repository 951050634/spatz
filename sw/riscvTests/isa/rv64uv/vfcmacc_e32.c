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

int main(void) {
  INIT_CHECK();

  TEST_CASE1();
  TEST_CASE2();

  EXIT_CHECK();
}
