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

void online_merge_b2_r(
    const float *m_old, const float *l_old, const float *o_old,
    const float *m_tile, const float *l_tile, const float *o_tile,
    float *m_out, float *l_out, float *o_out, uint32_t n, uint32_t d,
    uint32_t stride_bytes);

// Existing LUT-backed scalar recurrence exposed for the native online
// attention integration.  This intentionally does not update O: callers use
// the same RVV update as the SMU path after consuming these weights.
void online_merge_b2_r_scalar(
    const float *m_old, const float *l_old, const float *m_tile,
    const float *l_tile, float *m_out, float *l_out, float *old_weight,
    float *tile_weight, uint32_t n);

// Reuse the frozen Phase 1 exp/reciprocal approximations when constructing a
// local online state.  The wrappers only expose existing LUT semantics; they
// do not add a new approximation or datapath.
float online_merge_exp_approx_f32(float value);
float online_merge_recip_approx_f32(float value);
