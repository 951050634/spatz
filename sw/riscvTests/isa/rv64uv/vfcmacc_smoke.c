// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

#include <stdint.h>

#define VFCMACC_VV_VM1(vd, vs1, vs2)                                           \
  asm volatile(".insn r 0x57, 0x1, 0x75, " vd ", " vs1 ", " vs2)

void vfcmacc_smoke(void) {
  asm volatile("vsetivli zero, 1, e32, m1, ta, ma");
  VFCMACC_VV_VM1("v8", "v0", "v2");
}

int main(void) {
  vfcmacc_smoke();
  return 0;
}
