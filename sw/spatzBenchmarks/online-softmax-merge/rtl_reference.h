// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include <stdint.h>

void online_merge_rtl_reference(
    const float *m_old, const float *l_old, const float *o_old,
    const float *m_tile, const float *l_tile, const float *o_tile,
    float *m_out, float *l_out, float *o_out, uint32_t n, uint32_t d,
    uint32_t stride_bytes);
