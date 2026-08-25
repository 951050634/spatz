// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <stdint.h>

// Values written to SPATZ_CLUSTER_PERIPHERAL_MERGE_MODE before START.  The
// update engine latches this field at START; software must not change it
// while STATUS.BUSY is set.
typedef enum {
  ONLINE_MERGE_MODE_LEGACY_FULL = 0u,
  ONLINE_MERGE_MODE_LEGACY_SCALAR = 1u,
  ONLINE_MERGE_MODE_MIXED_FULL = 2u,
  ONLINE_MERGE_MODE_MIXED_SCALAR = 3u,
} online_merge_mode_t;

// Keep the original names used by existing benchmark callers source
// compatible.  Their values and legacy meanings are unchanged.
#define ONLINE_MERGE_MODE_FULL ((uint32_t)ONLINE_MERGE_MODE_LEGACY_FULL)
#define ONLINE_MERGE_MODE_SCALAR_ONLY \
  ((uint32_t)ONLINE_MERGE_MODE_LEGACY_SCALAR)

static inline int online_merge_mode_valid(uint32_t mode) {
  return mode <= (uint32_t)ONLINE_MERGE_MODE_MIXED_SCALAR;
}
