// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <stdint.h>

uint32_t online_merge_register_workload(uint32_t iterations, uint32_t seed);
void online_merge_concurrency_stream(const float *source, float *destination,
                                     uint32_t elements);
