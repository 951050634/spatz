// Copyright 2026 ETH Zurich and University of Bologna.
// SPDX-License-Identifier: Apache-2.0

#include "vector_macros.h"
#include <stdint.h>

// Minimal test case: verify v20 reduction + vse64.v extraction
int main() {
    volatile double test_real[4] = {-999.0, -999.0, -999.0, -999.0};
    volatile double test_imag[4] = {-999.0, -999.0, -999.0, -999.0};
    const unsigned int one = 1;
    const unsigned int four = 4;

    // Initialize v16 and v20 with known values
    asm volatile("vsetvli zero, %0, e64, m4, ta, ma" ::"r"(four));

    // Set v16 (real) to [1.0, 1.0, 1.0, 1.0]
    double val_real = 1.0;
    asm volatile("vfmv.v.f v16, %0" ::"f"(val_real));

    // Set v20 (imag) to [2.0, 2.0, 2.0, 2.0]
    double val_imag = 2.0;
    asm volatile("vfmv.v.f v20, %0" ::"f"(val_imag));

    // Reduce: should get 4.0 and 8.0
    asm volatile("vmv.s.x v24, zero");
    asm volatile("vfredusum.vs v16, v16, v24");
    asm volatile("vfredusum.vs v20, v20, v24");

    // Extract with vse64.v (vl=1, m4)
    asm volatile("vsetvli zero, %0, e64, m4, ta, ma" ::"r"(one));
    asm volatile("vse64.v v16, (%0)" ::"r"(&test_real[0]) : "memory");
    asm volatile("vse64.v v20, (%0)" ::"r"(&test_imag[0]) : "memory");

    int pass = (test_real[0] == 4.0) && (test_imag[0] == 8.0);

    if (pass) {
        return 0;
    } else {
        return -1;
    }
}
