// Copyright 2026 ETH Zurich and University of Bologna.
// SPDX-License-Identifier: Apache-2.0

#include "vector_macros.h"
#include <stdint.h>

// Test: v16 and v20 accumulation in loop, then reduction
int main() {
    volatile double test_buf[2] = {-999.0, -999.0};
    const unsigned int one = 1;
    const unsigned int vl_val = 4;

    // Simulate dp-cdotp: accumulate over multiple iterations
    asm volatile("vsetvli zero, %0, e64, m4, ta, ma" ::"r"(vl_val));
    asm volatile("vmv.v.i v16, 0");  // Real accumulator = 0
    asm volatile("vmv.v.i v20, 0");  // Imag accumulator = 0

    // Iteration 1: add 1.0 to real, 2.0 to imag
    double val1_r = 1.0, val1_i = 2.0;
    asm volatile("vfmv.v.f v0, %0" ::"f"(val1_r));
    asm volatile("vfmv.v.f v4, %0" ::"f"(val1_i));
    asm volatile("vfadd.vv v16, v16, v0");
    asm volatile("vfadd.vv v20, v20, v4");

    // Iteration 2: add 3.0 to real, 4.0 to imag
    double val2_r = 3.0, val2_i = 4.0;
    asm volatile("vfmv.v.f v0, %0" ::"f"(val2_r));
    asm volatile("vfmv.v.f v4, %0" ::"f"(val2_i));
    asm volatile("vfadd.vv v16, v16, v0");
    asm volatile("vfadd.vv v20, v20, v4");

    // Now v16 should be [4.0, 4.0, 4.0, 4.0]
    // And v20 should be [6.0, 6.0, 6.0, 6.0]

    // Reduce
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");  // Should get 16.0
    asm volatile("vfredusum.vs v20, v20, v24");  // Should get 24.0

    // Extract
    asm volatile("vsetvli zero, %0, e64, m4, ta, ma" ::"r"(one));
    asm volatile("vse64.v v16, (%0)" ::"r"(&test_buf[0]) : "memory");
    asm volatile("vse64.v v20, (%0)" ::"r"(&test_buf[1]) : "memory");

    int pass = (test_buf[0] == 16.0) && (test_buf[1] == 24.0);

    return pass ? 0 : -1;
}
