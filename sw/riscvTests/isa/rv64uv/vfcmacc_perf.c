// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

#include <stdint.h>
#include "printf.h"

#ifndef VFCMACC_PERF_ITERS
#define VFCMACC_PERF_ITERS 64u
#endif

#define VFCMACC_VV_VM1(vd, vs1, vs2)                                           \
  asm volatile(".insn r 0x57, 0x1, 0x75, " vd ", " vs1 ", " vs2 ::: "memory")

static inline uint32_t read_mhartid32(void) {
  uint32_t value;
  asm volatile("csrr %0, mhartid" : "=r"(value));
  return value;
}

static inline uint32_t read_mcycle32(void) {
  uint32_t value;
  asm volatile("csrr %0, mcycle" : "=r"(value));
  return value;
}


int main(void) {
  if (read_mhartid32() != 0) {
    return 0;
  }

  asm volatile("vsetivli zero, 1, e64, m1, ta, ma\n"
               "vmv.v.i v0, 0\n"
               "vmv.v.i v1, 0\n"
               "vmv.v.i v2, 0\n"
               "vmv.v.i v3, 0\n"
               "vmv.v.i v8, 0\n"
               "vmv.v.i v9, 0\n" ::: "memory");

  uint32_t start = read_mcycle32();
  for (uint32_t i = 0; i < VFCMACC_PERF_ITERS; i++) {
    VFCMACC_VV_VM1("v8", "v0", "v2");
  }
  uint32_t cycles = read_mcycle32() - start;



  printf("vfcmacc_perf iterations=%u vl=1 vsew=e64 cycles=%u cycles_per_insn_x100=%u\n",
         VFCMACC_PERF_ITERS, cycles,
         (cycles * 100u + (VFCMACC_PERF_ITERS / 2u)) / VFCMACC_PERF_ITERS);
  return 0;
}
