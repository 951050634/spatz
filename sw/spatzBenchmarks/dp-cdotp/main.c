// Copyright 2022 ETH Zurich and University of Bologna.
// SPDX-License-Identifier: Apache-2.0
// Input/output logic consistent with dp-faxpy / dp-fdotp

#include <benchmark.h>
#include <debug.h>
#include <snrt.h>
#include <stdio.h>

#include DATAHEADER
#include "kernel/cdotp.c"

#define CDOTP_TILE_ELEMS 1024

#ifndef SPATZ_CDOTP_KERNEL_NAME
#define SPATZ_CDOTP_KERNEL_NAME "old"
#endif

#ifndef SPATZ_CDOTP_INNER_LOOP_INSN_PROXY
#define SPATZ_CDOTP_INNER_LOOP_INSN_PROXY 7
#endif

#ifndef SPATZ_CDOTP_ACCUM_INSN_PROXY
#define SPATZ_CDOTP_ACCUM_INSN_PROXY 4
#endif

cdouble *x;
cdouble *y;
cdouble *result;

static inline int cp_check(const cdouble calc, const cdouble ref) {
  const double threshold = 0.0001;
  double dr = calc.real - ref.real, di = calc.imag - ref.imag;
  if (dr < 0) dr = -dr;
  if (di < 0) di = -di;
  return (dr > threshold) || (di > threshold);
}

int main() {
  const unsigned int num_cores = snrt_cluster_core_num();
  const unsigned int cid = snrt_cluster_core_idx();

  unsigned int timer = (unsigned int)-1;

  const unsigned int dim = cdotp_n;

  if (cid == 0) {
    x = (cdouble *)snrt_l1alloc(CDOTP_TILE_ELEMS * sizeof(cdouble));
    y = (cdouble *)snrt_l1alloc(CDOTP_TILE_ELEMS * sizeof(cdouble));
    result = (cdouble *)snrt_l1alloc(num_cores * sizeof(cdouble));
  }

  snrt_cluster_hw_barrier();

  if (cid == 0)
    start_kernel();

  if (cid == 0)
    timer = benchmark_get_cycle();

  cdouble acc = {0.0, 0.0};

  for (unsigned int offset = 0; offset < dim; offset += CDOTP_TILE_ELEMS) {
    unsigned int tile_elems = dim - offset;
    if (tile_elems > CDOTP_TILE_ELEMS)
      tile_elems = CDOTP_TILE_ELEMS;

    if (cid == 0) {
      snrt_dma_start_1d(x, cdotp_x + offset,
                        tile_elems * sizeof(cdouble));
      snrt_dma_start_1d(y, cdotp_y + offset,
                        tile_elems * sizeof(cdouble));
      snrt_dma_wait_all();
    }

    snrt_cluster_hw_barrier();

    unsigned int start = (tile_elems * cid) / num_cores;
    unsigned int end = (tile_elems * (cid + 1)) / num_cores;
#if SPATZ_CDOTP_SCALAR_DIAG
    start = 0;
    end = (cid == 0) ? tile_elems : 0;
#endif
    if (end > start) {
      cdouble tile_acc = cdotp_v64b(x + start, y + start, end - start);
      acc.real += tile_acc.real;
      acc.imag += tile_acc.imag;
    }

    snrt_cluster_hw_barrier();
  }

  result[cid] = acc;

  snrt_cluster_hw_barrier();

  if (cid == 0) {
    cdouble sum = result[0];
    for (unsigned int i = 1; i < num_cores; ++i) {
      sum.real += result[i].real;
      sum.imag += result[i].imag;
    }
    result[0] = sum;
  }

  snrt_cluster_hw_barrier();

  if (cid == 0)
    stop_kernel();

  if (cid == 0)
    timer = benchmark_get_cycle() - timer;

  if (cid == 0) {
    long unsigned int performance = 1000 * 2 * 2 * dim / timer;
    PRINTF("dp-cdotp %s M%d: cycles=%u, inner_loop_insn_proxy=%u, "
           "complex_mac_insn_proxy=%u, performance=%ld OP/1000cycle.\n",
           SPATZ_CDOTP_KERNEL_NAME, dim, timer,
           SPATZ_CDOTP_INNER_LOOP_INSN_PROXY, SPATZ_CDOTP_ACCUM_INSN_PROXY,
           performance);
  }

  if (cid == 0) {
    if (cp_check(result[0], cdotp_result)) {
      PRINTF("Error: Result = (%f, %f), Golden = (%f, %f)\n",
             (float)result[0].real, (float)result[0].imag,
             (float)cdotp_result.real, (float)cdotp_result.imag);
      return -1;
    }
    PRINTF("Verification: SUCCESS\n");
  }

  snrt_cluster_hw_barrier();
  return 0;
}
