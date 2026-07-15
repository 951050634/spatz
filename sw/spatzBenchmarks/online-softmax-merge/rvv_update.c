// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#include "rvv_update.h"

// Keep this as a visible target symbol so the experiment runner can prove that
// the measured B2-R path contains the required VLA RVV load/multiply/FMA/store
// sequence.  LMUL=8 exposes up to 128 FP32 lanes on the 512-bit Spatz VLEN;
// vsetvli still strip-mines every D, including tails and larger rows.
__attribute__((noinline)) void online_merge_rvv_update(
    const float *old_row, const float *tile_row, float *out_row, uint32_t d,
    float old_weight, float tile_weight) {
  uint32_t remaining = d;
  while (remaining != 0u) {
    uint32_t vl;
    asm volatile(
        "vsetvli %0, %1, e32, m8, ta, ma\n"
        "vle32.v v8, (%2)\n"
        "vle32.v v16, (%3)\n"
        "vfmul.vf v8, v8, %4\n"
        "vfmacc.vf v8, %5, v16\n"
        "vse32.v v8, (%6)\n"
        : "=&r"(vl)
        : "r"(remaining), "r"(old_row), "r"(tile_row), "f"(old_weight),
          "f"(tile_weight), "r"(out_row)
        : "memory");
    old_row += vl;
    tile_row += vl;
    out_row += vl;
    remaining -= vl;
  }
}
