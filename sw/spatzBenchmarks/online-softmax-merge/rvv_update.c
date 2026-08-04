// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#include "rvv_update.h"

// Keep this as a visible target symbol so the experiment runner can prove that
// the measured B2-R path contains the required VLA RVV load/multiply/FMA/store
// sequence.  The fixed RTL/Verilator model corrupts selected upper lanes for
// some longer partial e32,m8 groups (reproduced at D=15 and D=31).  Cap each
// AVL request at eight as an empirically validated compatibility strip-mine;
// its loop overhead remains inside the measured B2-R window.
enum { ONLINE_MERGE_RVV_AVL_CAP = 8 };
__attribute__((noinline)) void online_merge_rvv_update(
    const float *old_row, const float *tile_row, float *out_row, uint32_t d,
    float old_weight, float tile_weight) {
  uint32_t remaining = d;
  // Spatz issues e32 vector memory operations over 64-bit TCDM beats.  The
  // fixed RTL rotates lanes when all three row pointers are four bytes off a
  // beat boundary, as happens on odd rows of an unpadded odd-D matrix.  Peel
  // elements scalarly until every pointer is beat-aligned.  The benchmark
  // allocator gives all vector buffers a common beat phase, so this needs at
  // most one peel and retains the declared logical stride; other callers with
  // mismatched phases safely fall back to scalar execution.
  while (remaining != 0u &&
         (((uintptr_t)old_row | (uintptr_t)tile_row | (uintptr_t)out_row) &
          (sizeof(uint64_t) - 1u)) != 0u) {
    *out_row = *old_row * old_weight + *tile_row * tile_weight;
    old_row++;
    tile_row++;
    out_row++;
    remaining--;
  }
  while (remaining != 0u) {
    uint32_t request = remaining;
    if (request > ONLINE_MERGE_RVV_AVL_CAP) {
      request = ONLINE_MERGE_RVV_AVL_CAP;
    }
    uint32_t vl;
    asm volatile(
        "vsetvli %0, %1, e32, m8, ta, ma\n"
        "vle32.v v8, (%2)\n"
        "vle32.v v16, (%3)\n"
        "vfmul.vf v8, v8, %4\n"
        "vfmacc.vf v8, %5, v16\n"
        "vse32.v v8, (%6)\n"
        : "=&r"(vl)
        : "r"(request), "r"(old_row), "r"(tile_row), "f"(old_weight),
          "f"(tile_weight), "r"(out_row)
        : "memory");
    old_row += vl;
    tile_row += vl;
    out_row += vl;
    remaining -= vl;
  }
}
