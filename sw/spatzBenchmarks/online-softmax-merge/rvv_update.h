// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <stdint.h>

void online_merge_rvv_update(const float *old_row, const float *tile_row,
                             float *out_row, uint32_t d, float old_weight,
                             float tile_weight);
