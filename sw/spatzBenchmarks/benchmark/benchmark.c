// Copyright 2020 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.

// SPDX-License-Identifier: Apache-2.0
#include "benchmark.h"
#include "encoding.h"
#include "spatz_cluster_peripheral.h"
#include "team.h"

extern __thread struct snrt_team *_snrt_team_current;

size_t benchmark_get_cycle() { return read_csr(mcycle); }

uint64_t benchmark_get_cycle64() {
#if __riscv_xlen == 32
  uint32_t high_before;
  uint32_t low;
  uint32_t high_after;
  do {
    high_before = read_csr(mcycleh);
    low = read_csr(mcycle);
    high_after = read_csr(mcycleh);
  } while (high_before != high_after);
  return ((uint64_t)high_before << 32) | low;
#else
  return read_csr(mcycle);
#endif
}

void start_kernel() {
  uint32_t *bench =
      (uint32_t *)(_snrt_team_current->root->cluster_mem.end +
                   SPATZ_CLUSTER_PERIPHERAL_SPATZ_STATUS_REG_OFFSET);
  *bench = 1;
}

void stop_kernel() {
  uint32_t *bench =
      (uint32_t *)(_snrt_team_current->root->cluster_mem.end +
                   SPATZ_CLUSTER_PERIPHERAL_SPATZ_STATUS_REG_OFFSET);
  *bench = 0;
}
