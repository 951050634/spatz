// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#include <benchmark.h>
#include <perf_cnt.h>
#include <snrt.h>
#include <spatz_cluster_peripheral.h>
#include <stdint.h>
#include <stdio.h>

#include "online_merge_case_data.h"
#include <online_merge_mode.h>
#include "rtl_reference.h"
#include "rvv_update.h"

#undef PRINTF
#define PRINTF(...) printf(__VA_ARGS__)

#if defined(ONLINE_MERGE_IMPLEMENTATION_SELECT) && \
    ONLINE_MERGE_IMPLEMENTATION_SELECT == 6
#define ONLINE_MERGE_TOL 1.5e-2f
#else
#define ONLINE_MERGE_TOL 1.0e-3f
#endif
#define ONLINE_MERGE_MAX_REPEATS 16u
#define ONLINE_MERGE_MAX_POLLS 1000000u
#define ONLINE_MERGE_ALLOC_ALIGN 256u

#ifndef ONLINE_MERGE_TRACE_PROXY
#define ONLINE_MERGE_TRACE_PROXY 0
#endif

#ifndef ONLINE_MERGE_IMPLEMENTATION_SELECT
#define ONLINE_MERGE_IMPLEMENTATION_SELECT 0
#endif

#ifndef ONLINE_MERGE_COUNTER_PROFILE
#define ONLINE_MERGE_COUNTER_PROFILE 0
#endif

#ifndef ONLINE_MERGE_STACK_LOG2
#define ONLINE_MERGE_STACK_LOG2 13
#endif

#define ONLINE_MERGE_IMPLEMENTATION_B1 1u
#define ONLINE_MERGE_IMPLEMENTATION_B2_R 2u
#define ONLINE_MERGE_IMPLEMENTATION_B3 3u
#define ONLINE_MERGE_IMPLEMENTATION_A1 4u
#define ONLINE_MERGE_IMPLEMENTATION_MODE_COMPARE 5u
#define ONLINE_MERGE_IMPLEMENTATION_A1_MIXED 6u

#define ONLINE_MERGE_COUNTER_MEMORY 0
#define ONLINE_MERGE_COUNTER_INSTRUCTIONS 1

// The four implementations' measured samples and correctness state make
// main's frame larger than the runtime's 1 KiB default.  Reserve 8 KiB per
// core so the stacks remain disjoint while the nonzero core waits at barrier.
const uint32_t snrt_stack_size = ONLINE_MERGE_STACK_LOG2;
extern const uint32_t _snrt_team_size;

#if ONLINE_MERGE_IMPLEMENTATION_SELECT == 0
_Static_assert(ONLINE_MERGE_CASE_REPEATS >= 3u,
               "all-in-one online merge requires at least three repeats");
#else
_Static_assert(ONLINE_MERGE_CASE_REPEATS == 1u,
               "single-implementation target requires one measured sample");
#endif
_Static_assert(ONLINE_MERGE_CASE_REPEATS <= ONLINE_MERGE_MAX_REPEATS,
               "online merge repeat count exceeds local sample storage");
_Static_assert(ONLINE_MERGE_IMPLEMENTATION_SELECT <=
                   ONLINE_MERGE_IMPLEMENTATION_A1_MIXED,
               "invalid online merge implementation selector");
_Static_assert(ONLINE_MERGE_COUNTER_PROFILE == ONLINE_MERGE_COUNTER_MEMORY ||
                   ONLINE_MERGE_COUNTER_PROFILE ==
                       ONLINE_MERGE_COUNTER_INSTRUCTIONS,
               "invalid online merge counter profile");
_Static_assert(ONLINE_MERGE_STACK_LOG2 > 0 &&
                   ONLINE_MERGE_STACK_LOG2 < 31,
               "invalid online merge stack size exponent");

#ifndef SNRT_TCDM_SIZE
#define SNRT_TCDM_SIZE (128u * 1024u)
#endif

typedef struct {
  float *m_old;
  float *l_old;
  float *o_old;
  float *m_tile;
  float *l_tile;
  float *o_tile;
  float *m_out;
  float *l_out;
  float *o_out;
  float *m_ref;
  float *l_ref;
  float *o_ref;
  float *old_weight;
  float *tile_weight;
  uint32_t n;
  uint32_t d;
  uint32_t stride;
  uint32_t footprint_bytes;
  uint32_t allocation_bytes;
  uint32_t runtime_reserved_bytes;
  uint32_t memory_footprint_bytes;
} online_merge_buffers_t;

typedef struct {
  uint64_t cycles;
  uint64_t smu_scalar_cycles;
  uint64_t rvv_vector_cycles;
  uint32_t tcdm_accessed;
  uint32_t tcdm_congested;
  uint32_t retired_instructions;
  uint32_t retired_accelerator_instructions;
  int saw_busy;
  const char *status;
} online_merge_sample_t;

typedef struct {
  float max_abs;
  float max_rel_numerator;
  float max_rel_denominator;
  float sum_abs;
  float sum_sq;
  float sum_ref_sq;
  uint32_t checked;
  uint32_t bit_equal;
  uint32_t nonfinite;
  uint32_t nan_count;
  uint32_t pos_inf_count;
  uint32_t neg_inf_count;
  int passed;
  int has_failure;
  uint32_t component;
  uint32_t row;
  uint32_t col;
  uint32_t expected_bits;
  uint32_t actual_bits;
} online_merge_metrics_t;

typedef enum {
  ONLINE_MERGE_WAIT_OK = 0,
  ONLINE_MERGE_WAIT_ERROR = 1,
  ONLINE_MERGE_WAIT_TIMEOUT = 2,
} online_merge_wait_t;

static volatile uint32_t *cluster_reg(uint32_t offset) {
  return (volatile uint32_t *)(snrt_cluster_memory().end + offset);
}

static uint32_t float_bits(float value) {
  union {
    float f;
    uint32_t u;
  } converted;
  converted.f = value;
  return converted.u;
}

static float bits_float(uint32_t value) {
  union {
    uint32_t u;
    float f;
  } converted;
  converted.u = value;
  return converted.f;
}

static float absf(float value) { return value < 0.0f ? -value : value; }

static uint64_t align_up_u64(uint64_t value, uint64_t alignment) {
  return (value + alignment - 1u) & ~(alignment - 1u);
}

static int float_is_finite(float value) {
  return ((float_bits(value) >> 23) & 0xffu) != 0xffu;
}

static uint32_t tcdm_offset(const void *pointer) {
  return (uint32_t)((uintptr_t)pointer -
                    (uintptr_t)snrt_cluster_memory().start);
}

static void take_floats(float **cursor, float **destination,
                        uint32_t count) {
  *destination = *cursor;
  *cursor += count;
}

static int allocate_buffers(online_merge_buffers_t *buffers, uint32_t n,
                            uint32_t d) {
  uint64_t vector_count = (uint64_t)n * (uint64_t)d;
  uint64_t stride_bytes = (uint64_t)d * sizeof(float);
  uint64_t row_bytes = 40ull + 16ull * (uint64_t)d;
  uint64_t limit = ((uint64_t)SNRT_TCDM_SIZE * 8u) / 10u;
  uint64_t runtime_reserved = (uint64_t)_snrt_team_size +
                              (uint64_t)snrt_cluster_core_num() *
                                  ((1ull << ONLINE_MERGE_STACK_LOG2) + 8ull);

  buffers->n = n;
  buffers->d = d;
  if (n != 0u && row_bytes > UINT64_MAX / (uint64_t)n) {
    return 1;
  }
  uint64_t footprint_bytes = (uint64_t)n * row_bytes;
  if (footprint_bytes > UINT64_MAX - (ONLINE_MERGE_ALLOC_ALIGN - 1u)) {
    return 1;
  }
  uint64_t allocation_bytes =
      align_up_u64(footprint_bytes, ONLINE_MERGE_ALLOC_ALIGN);
  uint64_t memory_footprint_bytes = allocation_bytes + runtime_reserved;
  if (stride_bytes > UINT32_MAX || vector_count > UINT32_MAX ||
      footprint_bytes > UINT32_MAX || allocation_bytes > UINT32_MAX ||
      runtime_reserved > UINT32_MAX ||
      memory_footprint_bytes > UINT32_MAX) {
    return 1;
  }
  buffers->stride = (uint32_t)stride_bytes;
  buffers->footprint_bytes = (uint32_t)footprint_bytes;
  buffers->allocation_bytes = (uint32_t)allocation_bytes;
  buffers->runtime_reserved_bytes = (uint32_t)runtime_reserved;
  buffers->memory_footprint_bytes = (uint32_t)memory_footprint_bytes;
  if (memory_footprint_bytes > limit) {
    return 1;
  }

  float *storage = (float *)snrt_l1alloc(buffers->allocation_bytes);
  if (storage == 0) {
    return -1;
  }
  float *cursor = storage;
  uint32_t vectors = (uint32_t)vector_count;
  if ((vectors & 1u) == 0u) {
    take_floats(&cursor, &buffers->m_old, n);
    take_floats(&cursor, &buffers->l_old, n);
    take_floats(&cursor, &buffers->o_old, vectors);
    take_floats(&cursor, &buffers->m_tile, n);
    take_floats(&cursor, &buffers->l_tile, n);
    take_floats(&cursor, &buffers->o_tile, vectors);
    take_floats(&cursor, &buffers->m_out, n);
    take_floats(&cursor, &buffers->l_out, n);
    take_floats(&cursor, &buffers->o_out, vectors);
    take_floats(&cursor, &buffers->m_ref, n);
    take_floats(&cursor, &buffers->l_ref, n);
    take_floats(&cursor, &buffers->o_ref, vectors);
    take_floats(&cursor, &buffers->old_weight, n);
    take_floats(&cursor, &buffers->tile_weight, n);
  } else {
    // Odd vector arrays toggle the 64-bit beat phase.  Interleave one odd-N
    // scalar array between vector arrays so every vector base starts on the
    // same beat phase without adding padding or changing the footprint.
    take_floats(&cursor, &buffers->m_old, n);
    take_floats(&cursor, &buffers->l_old, n);
    take_floats(&cursor, &buffers->o_old, vectors);
    take_floats(&cursor, &buffers->m_tile, n);
    take_floats(&cursor, &buffers->o_tile, vectors);
    take_floats(&cursor, &buffers->l_tile, n);
    take_floats(&cursor, &buffers->o_out, vectors);
    take_floats(&cursor, &buffers->m_out, n);
    take_floats(&cursor, &buffers->o_ref, vectors);
    take_floats(&cursor, &buffers->l_out, n);
    take_floats(&cursor, &buffers->m_ref, n);
    take_floats(&cursor, &buffers->l_ref, n);
    take_floats(&cursor, &buffers->old_weight, n);
    take_floats(&cursor, &buffers->tile_weight, n);
  }
  return 0;
}

static void copy_bits(float *destination, const uint32_t *source,
                      uint32_t count) {
  for (uint32_t i = 0; i < count; i++) {
    destination[i] = bits_float(source[i]);
  }
}

static void load_case(online_merge_buffers_t *buffers) {
  uint32_t vectors = buffers->n * buffers->d;
  copy_bits(buffers->m_old, online_merge_m_old_bits, buffers->n);
  copy_bits(buffers->l_old, online_merge_l_old_bits, buffers->n);
  copy_bits(buffers->o_old, online_merge_o_old_bits, vectors);
  copy_bits(buffers->m_tile, online_merge_m_tile_bits, buffers->n);
  copy_bits(buffers->l_tile, online_merge_l_tile_bits, buffers->n);
  copy_bits(buffers->o_tile, online_merge_o_tile_bits, vectors);
  copy_bits(buffers->m_ref, online_merge_golden_m_bits, buffers->n);
  copy_bits(buffers->l_ref, online_merge_golden_l_bits, buffers->n);
  copy_bits(buffers->o_ref, online_merge_golden_o_bits, vectors);
}

static void load_mode_compare_vector(online_merge_buffers_t *buffers) {
  buffers->m_old[0] = bits_float(0x3f800000u);
  buffers->l_old[0] = bits_float(0x3f800000u);
  buffers->o_old[0] = bits_float(0x3f800000u);
  buffers->m_tile[0] = bits_float(0x00000000u);
  buffers->l_tile[0] = bits_float(0x3f800000u);
  buffers->o_tile[0] = bits_float(0x40400000u);
}

static void set_mode_compare_reference(online_merge_buffers_t *buffers,
                                        online_merge_mode_t mode) {
  buffers->m_ref[0] = bits_float(0x3f800000u);
  if (mode == ONLINE_MERGE_MODE_LEGACY_SCALAR) {
    buffers->l_ref[0] = bits_float(0x3faf16acu);
    buffers->o_ref[0] = bits_float(0x3fc4d968u);
  } else {
    buffers->l_ref[0] = bits_float(0x3fafd400u);
    buffers->o_ref[0] = bits_float(0x3fc5a000u);
  }
}

static void clear_output(online_merge_buffers_t *buffers) {
  uint32_t vectors = buffers->n * buffers->d;
  for (uint32_t i = 0; i < buffers->n; i++) {
    buffers->m_out[i] = 0.0f;
    buffers->l_out[i] = 0.0f;
    buffers->old_weight[i] = 0.0f;
    buffers->tile_weight[i] = 0.0f;
  }
  for (uint32_t i = 0; i < vectors; i++) {
    buffers->o_out[i] = 0.0f;
  }
}

static void online_merge_start_mode(const online_merge_buffers_t *buffers,
                                    online_merge_mode_t mode) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_OLD_REG_OFFSET) =
      tcdm_offset(buffers->m_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_OLD_REG_OFFSET) =
      tcdm_offset(buffers->l_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_OLD_REG_OFFSET) =
      tcdm_offset(buffers->o_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_TILE_REG_OFFSET) =
      tcdm_offset(buffers->m_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET) =
      tcdm_offset(buffers->l_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_TILE_REG_OFFSET) =
      tcdm_offset(buffers->o_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_M_REG_OFFSET) =
      tcdm_offset(buffers->m_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_L_REG_OFFSET) =
      tcdm_offset(buffers->l_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_O_REG_OFFSET) =
      tcdm_offset(buffers->o_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET) = buffers->n;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_D_REG_OFFSET) = buffers->d;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STRIDE_REG_OFFSET) =
      buffers->stride;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_MODE_REG_OFFSET) =
      (uint32_t)mode;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_OLD_REG_OFFSET) =
      tcdm_offset(buffers->old_weight);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_TILE_REG_OFFSET) =
      tcdm_offset(buffers->tile_weight);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_START_BIT;
}

// Compatibility entry point for the original callers.  New code should use
// the typed mode-aware entry point above so mode 3 is explicit at the call
// site while the register ordering remains unchanged.
static void smu_start(const online_merge_buffers_t *buffers, uint32_t mode) {
  online_merge_start_mode(buffers, (online_merge_mode_t)mode);
}

static uint32_t smu_status(void) {
  return *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_REG_OFFSET);
}

static void smu_clear_done(void) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT;
}

static online_merge_wait_t smu_wait(int *saw_busy) {
  *saw_busy = 0;
  for (uint32_t poll = 0; poll < ONLINE_MERGE_MAX_POLLS; poll++) {
    uint32_t status = smu_status();
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_BUSY_BIT) & 1u) {
      *saw_busy = 1;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_ERROR_BIT) & 1u) {
      return ONLINE_MERGE_WAIT_ERROR;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_DONE_BIT) & 1u) {
      return ONLINE_MERGE_WAIT_OK;
    }
  }
  return ONLINE_MERGE_WAIT_TIMEOUT;
}

static void start_perf_counters(void) {
  snrt_reset_perf_counter(SNRT_PERF_CNT0);
  snrt_reset_perf_counter(SNRT_PERF_CNT1);
#if ONLINE_MERGE_COUNTER_PROFILE == ONLINE_MERGE_COUNTER_MEMORY
  snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_TCDM_ACCESSED,
                          0);
  snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_TCDM_CONGESTED,
                          0);
#else
  snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_RETIRED_INSTR,
                          0);
  snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_RETIRED_ACC, 0);
#endif
}

static void stop_perf_counters(online_merge_sample_t *sample) {
  snrt_stop_perf_counter(SNRT_PERF_CNT0);
  snrt_stop_perf_counter(SNRT_PERF_CNT1);
#if ONLINE_MERGE_COUNTER_PROFILE == ONLINE_MERGE_COUNTER_MEMORY
  sample->tcdm_accessed = snrt_get_perf_counter(SNRT_PERF_CNT0);
  sample->tcdm_congested = snrt_get_perf_counter(SNRT_PERF_CNT1);
#else
  sample->retired_instructions = snrt_get_perf_counter(SNRT_PERF_CNT0);
  sample->retired_accelerator_instructions =
      snrt_get_perf_counter(SNRT_PERF_CNT1);
#endif
}

// Visible no-op markers let an offline DASM audit delimit the measurement
// envelope without adding printf calls to the hot loop.  Target cycle timing
// remains bounded by benchmark_get_cycle64() inside each run function.
__attribute__((noinline, used)) void online_merge_trace_begin(
    uint32_t implementation, uint32_t repeat) {
  asm volatile("" : : "r"(implementation), "r"(repeat) : "memory");
}

__attribute__((noinline, used)) void online_merge_trace_end(
    uint32_t implementation, uint32_t repeat) {
  asm volatile("" : : "r"(implementation), "r"(repeat) : "memory");
}

static int trace_marker_enabled(uint32_t implementation, uint32_t repeat) {
#if ONLINE_MERGE_TRACE_PROXY
  return repeat == 0u &&
         (implementation == ONLINE_MERGE_IMPLEMENTATION_B2_R ||
          implementation == ONLINE_MERGE_IMPLEMENTATION_B3);
#else
  (void)implementation;
  (void)repeat;
  return 1;
#endif
}

static void trace_marker_start(uint32_t implementation, uint32_t repeat) {
  if (trace_marker_enabled(implementation, repeat)) {
    start_kernel();
    online_merge_trace_begin(implementation, repeat);
  }
}

static void trace_marker_stop(uint32_t implementation, uint32_t repeat) {
  if (trace_marker_enabled(implementation, repeat)) {
    online_merge_trace_end(implementation, repeat);
    stop_kernel();
  }
}

static void record_failure(online_merge_metrics_t *metrics,
                           uint32_t component, uint32_t row, uint32_t col,
                           float actual, float expected) {
  metrics->passed = 0;
  if (metrics->has_failure) {
    return;
  }
  metrics->has_failure = 1;
  metrics->component = component;
  metrics->row = row;
  metrics->col = col;
  metrics->expected_bits = float_bits(expected);
  metrics->actual_bits = float_bits(actual);
}

static void record_value(online_merge_metrics_t *metrics, uint32_t component,
                         uint32_t row, uint32_t col, float actual,
                         float expected) {
  metrics->checked++;
  if (float_bits(actual) == float_bits(expected)) {
    metrics->bit_equal++;
  }
  if (!float_is_finite(actual) || !float_is_finite(expected)) {
    metrics->nonfinite++;
    uint32_t actual_bits = float_bits(actual);
    uint32_t actual_exponent = (actual_bits >> 23) & 0xffu;
    uint32_t actual_fraction = actual_bits & 0x7fffffu;
    if (actual_exponent == 0xffu) {
      if (actual_fraction != 0u) {
        metrics->nan_count++;
      } else if ((actual_bits >> 31) != 0u) {
        metrics->neg_inf_count++;
      } else {
        metrics->pos_inf_count++;
      }
    }
    record_failure(metrics, component, row, col, actual, expected);
    return;
  }

  float absolute = absf(actual - expected);
  float scale = absf(expected) > 1.0f ? absf(expected) : 1.0f;
  if (!float_is_finite(absolute)) {
    metrics->nonfinite++;
    record_failure(metrics, component, row, col, actual, expected);
    return;
  }
  if (absolute > metrics->max_abs) {
    metrics->max_abs = absolute;
  }
  if (absolute * metrics->max_rel_denominator >
      metrics->max_rel_numerator * scale) {
    metrics->max_rel_numerator = absolute;
    metrics->max_rel_denominator = scale;
  }
  metrics->sum_abs += absolute;
  metrics->sum_sq += absolute * absolute;
  metrics->sum_ref_sq += expected * expected;
  if (!float_is_finite(metrics->sum_abs) ||
      !float_is_finite(metrics->sum_sq) ||
      !float_is_finite(metrics->sum_ref_sq)) {
    metrics->nonfinite++;
    record_failure(metrics, component, row, col, actual, expected);
    return;
  }
  if (absolute > ONLINE_MERGE_TOL * scale) {
    record_failure(metrics, component, row, col, actual, expected);
  }
}

static online_merge_metrics_t check_output(
    const online_merge_buffers_t *buffers) {
  online_merge_metrics_t metrics = {
      .max_rel_denominator = 1.0f,
      .passed = 1,
  };
  for (uint32_t row = 0; row < buffers->n; row++) {
    record_value(&metrics, 0, row, 0, buffers->m_out[row],
                 buffers->m_ref[row]);
    record_value(&metrics, 1, row, 0, buffers->l_out[row],
                 buffers->l_ref[row]);
    uint32_t base = row * buffers->d;
    for (uint32_t col = 0; col < buffers->d; col++) {
      record_value(&metrics, 2, row, col, buffers->o_out[base + col],
                   buffers->o_ref[base + col]);
    }
  }
  return metrics;
}

static void require_exact_value(online_merge_metrics_t *metrics,
                                uint32_t component, uint32_t row,
                                uint32_t col, float actual, float expected) {
  if (float_bits(actual) != float_bits(expected)) {
    record_failure(metrics, component, row, col, actual, expected);
  }
}

static void check_mode_compare_exact(
    const online_merge_buffers_t *buffers, online_merge_metrics_t *metrics,
    online_merge_mode_t mode) {
  uint32_t expected_l_bits = mode == ONLINE_MERGE_MODE_LEGACY_SCALAR
                                 ? 0x3faf16acu
                                 : 0x3fafd400u;
  uint32_t expected_o_bits = mode == ONLINE_MERGE_MODE_LEGACY_SCALAR
                                 ? 0x3fc4d968u
                                 : 0x3fc5a000u;
  uint32_t expected_old_weight_bits =
      mode == ONLINE_MERGE_MODE_LEGACY_SCALAR ? 0x3f3b26b8u : 0x3f3a6000u;
  uint32_t expected_tile_weight_bits =
      mode == ONLINE_MERGE_MODE_LEGACY_SCALAR ? 0x3e89b2bbu : 0x3e8b4000u;

  record_value(metrics, 0, 0, 0, buffers->m_out[0],
               bits_float(0x3f800000u));
  require_exact_value(metrics, 0, 0, 0, buffers->m_out[0],
                      bits_float(0x3f800000u));
  record_value(metrics, 1, 0, 0, buffers->l_out[0],
               bits_float(expected_l_bits));
  require_exact_value(metrics, 1, 0, 0, buffers->l_out[0],
                      bits_float(expected_l_bits));
  record_value(metrics, 2, 0, 0, buffers->o_out[0],
               bits_float(expected_o_bits));
  require_exact_value(metrics, 2, 0, 0, buffers->o_out[0],
                      bits_float(expected_o_bits));
  record_value(metrics, 3, 0, 0, buffers->old_weight[0],
               bits_float(expected_old_weight_bits));
  require_exact_value(metrics, 3, 0, 0, buffers->old_weight[0],
                      bits_float(expected_old_weight_bits));
  record_value(metrics, 4, 0, 0, buffers->tile_weight[0],
               bits_float(expected_tile_weight_bits));
  require_exact_value(metrics, 4, 0, 0, buffers->tile_weight[0],
                      bits_float(expected_tile_weight_bits));
}

static void run_b1(online_merge_buffers_t *buffers,
                   online_merge_sample_t *samples,
                   online_merge_metrics_t *metrics) {
  clear_output(buffers);
  online_merge_rtl_reference(
      buffers->m_old, buffers->l_old, buffers->o_old, buffers->m_tile,
      buffers->l_tile, buffers->o_tile, buffers->m_out, buffers->l_out,
      buffers->o_out, buffers->n, buffers->d, buffers->stride);

  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    clear_output(buffers);
    start_perf_counters();
    trace_marker_start(ONLINE_MERGE_IMPLEMENTATION_B1, repeat);
    uint64_t start = benchmark_get_cycle64();
    online_merge_rtl_reference(
        buffers->m_old, buffers->l_old, buffers->o_old, buffers->m_tile,
        buffers->l_tile, buffers->o_tile, buffers->m_out, buffers->l_out,
        buffers->o_out, buffers->n, buffers->d, buffers->stride);
    uint64_t end = benchmark_get_cycle64();
    trace_marker_stop(ONLINE_MERGE_IMPLEMENTATION_B1, repeat);
    samples[repeat].cycles = end - start;
    samples[repeat].saw_busy = 0;
    samples[repeat].status = "pass";
    stop_perf_counters(&samples[repeat]);
    metrics[repeat] = check_output(buffers);
  }
}

static void run_b2_r(online_merge_buffers_t *buffers,
                     online_merge_sample_t *samples,
                     online_merge_metrics_t *metrics) {
  clear_output(buffers);
  online_merge_b2_r(
      buffers->m_old, buffers->l_old, buffers->o_old, buffers->m_tile,
      buffers->l_tile, buffers->o_tile, buffers->m_out, buffers->l_out,
      buffers->o_out, buffers->n, buffers->d, buffers->stride);

  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    clear_output(buffers);
    start_perf_counters();
    trace_marker_start(ONLINE_MERGE_IMPLEMENTATION_B2_R, repeat);
    uint64_t start = benchmark_get_cycle64();
    online_merge_b2_r(
        buffers->m_old, buffers->l_old, buffers->o_old, buffers->m_tile,
        buffers->l_tile, buffers->o_tile, buffers->m_out, buffers->l_out,
        buffers->o_out, buffers->n, buffers->d, buffers->stride);
    uint64_t end = benchmark_get_cycle64();
    trace_marker_stop(ONLINE_MERGE_IMPLEMENTATION_B2_R, repeat);
    samples[repeat].cycles = end - start;
    samples[repeat].saw_busy = 0;
    samples[repeat].status = "pass";
    stop_perf_counters(&samples[repeat]);
    metrics[repeat] = check_output(buffers);
  }
}

static void run_rvv_weighted_update(online_merge_buffers_t *buffers) {
  for (uint32_t row = 0; row < buffers->n; row++) {
    uint32_t base = row * buffers->d;
    online_merge_rvv_update(
        &buffers->o_old[base], &buffers->o_tile[base],
        &buffers->o_out[base], buffers->d, buffers->old_weight[row],
        buffers->tile_weight[row]);
  }
}

static const char *wait_status(online_merge_wait_t wait_result) {
  if (wait_result == ONLINE_MERGE_WAIT_TIMEOUT) {
    return "timeout";
  }
  if (wait_result == ONLINE_MERGE_WAIT_ERROR) {
    return "tool_error";
  }
  return "pass";
}

static int run_a1_mode(online_merge_buffers_t *buffers,
                       online_merge_sample_t *samples,
                       online_merge_metrics_t *metrics,
                       online_merge_mode_t mode,
                       uint32_t implementation) {
  clear_output(buffers);
  online_merge_start_mode(buffers, mode);
  int warmup_busy;
  online_merge_wait_t warmup = smu_wait(&warmup_busy);
  if (warmup == ONLINE_MERGE_WAIT_OK) {
    run_rvv_weighted_update(buffers);
  }
  smu_clear_done();
  if (warmup != ONLINE_MERGE_WAIT_OK) {
    samples[0].status = wait_status(warmup);
    samples[0].saw_busy = warmup_busy;
    return -1;
  }

  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    clear_output(buffers);
    start_perf_counters();
    trace_marker_start(implementation, repeat);
    uint64_t start = benchmark_get_cycle64();
    online_merge_start_mode(buffers, mode);
    int saw_busy;
    online_merge_wait_t wait_result = smu_wait(&saw_busy);
    uint64_t scalar_end = benchmark_get_cycle64();
    if (wait_result == ONLINE_MERGE_WAIT_OK) {
      run_rvv_weighted_update(buffers);
    }
    uint64_t end = benchmark_get_cycle64();
    trace_marker_stop(implementation, repeat);
    samples[repeat].cycles = end - start;
    samples[repeat].smu_scalar_cycles = scalar_end - start;
    samples[repeat].rvv_vector_cycles = end - scalar_end;
    samples[repeat].saw_busy = saw_busy;
    samples[repeat].status = wait_status(wait_result);
    stop_perf_counters(&samples[repeat]);
    smu_clear_done();
    if (wait_result != ONLINE_MERGE_WAIT_OK) {
      return (int)repeat + 1;
    }
    metrics[repeat] = check_output(buffers);
  }
  return 0;
}

// Preserve the historical A1 entry point and default mode exactly.
static int run_a1(online_merge_buffers_t *buffers,
                  online_merge_sample_t *samples,
                  online_merge_metrics_t *metrics) {
  return run_a1_mode(buffers, samples, metrics,
                     ONLINE_MERGE_MODE_LEGACY_SCALAR,
                     ONLINE_MERGE_IMPLEMENTATION_A1);
}

static int run_a1_mixed(online_merge_buffers_t *buffers,
                        online_merge_sample_t *samples,
                        online_merge_metrics_t *metrics) {
  return run_a1_mode(buffers, samples, metrics,
                     ONLINE_MERGE_MODE_MIXED_SCALAR,
                     ONLINE_MERGE_IMPLEMENTATION_A1_MIXED);
}

static int run_b3(online_merge_buffers_t *buffers,
                  online_merge_sample_t *samples,
                  online_merge_metrics_t *metrics) {
  clear_output(buffers);
  smu_start(buffers, ONLINE_MERGE_MODE_FULL);
  int warmup_busy;
  online_merge_wait_t warmup = smu_wait(&warmup_busy);
  smu_clear_done();
  if (warmup != ONLINE_MERGE_WAIT_OK) {
    samples[0].status = wait_status(warmup);
    samples[0].saw_busy = warmup_busy;
    return -1;
  }

  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    clear_output(buffers);
    start_perf_counters();
    trace_marker_start(ONLINE_MERGE_IMPLEMENTATION_B3, repeat);
    uint64_t start = benchmark_get_cycle64();
    smu_start(buffers, ONLINE_MERGE_MODE_FULL);
    int saw_busy;
    online_merge_wait_t wait_result = smu_wait(&saw_busy);
    uint64_t end = benchmark_get_cycle64();
    trace_marker_stop(ONLINE_MERGE_IMPLEMENTATION_B3, repeat);
    samples[repeat].cycles = end - start;
    samples[repeat].saw_busy = saw_busy;
    samples[repeat].status = wait_status(wait_result);
    stop_perf_counters(&samples[repeat]);
    smu_clear_done();
    if (wait_result != ONLINE_MERGE_WAIT_OK) {
      return (int)repeat + 1;
    }
    metrics[repeat] = check_output(buffers);
  }
  return 0;
}

static const char *component_name(uint32_t component) {
  if (component == 0) {
    return "m";
  }
  if (component == 1) {
    return "l";
  }
  if (component == 2) {
    return "O";
  }
  return component == 3 ? "weight_old" : "weight_tile";
}

static void print_failure(const char *implementation, int repeat,
                          const online_merge_buffers_t *buffers,
                          const online_merge_metrics_t *metrics) {
  if (!metrics->has_failure) {
    return;
  }
  uint32_t base = metrics->row * buffers->d + metrics->col;
  uint32_t old_o = metrics->component == 2
                       ? float_bits(buffers->o_old[base])
                       : 0u;
  uint32_t tile_o = metrics->component == 2
                        ? float_bits(buffers->o_tile[base])
                        : 0u;
  PRINTF("OM_FAILURE {");
  PRINTF("\"implementation\":\"%s\",", implementation);
  PRINTF("\"repeat\":%d,", repeat);
  PRINTF("\"component\":\"%s\",", component_name(metrics->component));
  PRINTF("\"row\":%u,\"col\":%u,", metrics->row, metrics->col);
  PRINTF("\"expected_bits\":%u,", metrics->expected_bits);
  PRINTF("\"actual_bits\":%u,", metrics->actual_bits);
  PRINTF("\"m_old_bits\":%u,", float_bits(buffers->m_old[metrics->row]));
  PRINTF("\"m_tile_bits\":%u,", float_bits(buffers->m_tile[metrics->row]));
  PRINTF("\"l_old_bits\":%u,", float_bits(buffers->l_old[metrics->row]));
  PRINTF("\"l_tile_bits\":%u,", float_bits(buffers->l_tile[metrics->row]));
  PRINTF("\"o_old_bits\":%u,\"o_tile_bits\":%u}\n", old_o, tile_o);
}

static void print_result(const char *implementation, int repeat,
                         const online_merge_buffers_t *buffers,
                         const online_merge_sample_t *sample,
                         const online_merge_metrics_t *metrics,
                         const char *forced_status) {
  const char *status = forced_status;
  if (status == 0) {
    status = sample->status != 0 ? sample->status : "tool_error";
    if (status[0] == 'p' && !metrics->passed) {
      status = "correctness_fail";
    }
  }
  uint32_t cycles_hi = (uint32_t)(sample->cycles >> 32);
  uint32_t cycles_lo = (uint32_t)sample->cycles;

  PRINTF("OM_RESULT {");
  PRINTF("\"implementation\":\"%s\",", implementation);
  PRINTF("\"N\":%u,\"D\":%u,", buffers->n, buffers->d);
  PRINTF("\"stride\":%u,\"seed\":%u,", buffers->stride,
         ONLINE_MERGE_CASE_SEED);
  PRINTF("\"case_kind\":\"%s\",", ONLINE_MERGE_CASE_KIND);
  PRINTF("\"case_class\":\"%s\",", ONLINE_MERGE_CASE_CLASS);
  PRINTF("\"repeat\":%d,", repeat);
  PRINTF("\"cycles_hi\":%u,\"cycles_lo\":%u,", cycles_hi, cycles_lo);
  PRINTF("\"smu_scalar_cycles\":%llu,",
         (unsigned long long)sample->smu_scalar_cycles);
  PRINTF("\"rvv_vector_cycles\":%llu,",
         (unsigned long long)sample->rvv_vector_cycles);
#if ONLINE_MERGE_COUNTER_PROFILE == ONLINE_MERGE_COUNTER_MEMORY
  PRINTF("\"counter_profile\":\"memory\",");
  PRINTF("\"tcdm_accessed\":%u,", sample->tcdm_accessed);
  PRINTF("\"tcdm_congested\":%u,", sample->tcdm_congested);
  PRINTF("\"retired_instructions\":null,");
  PRINTF("\"retired_accelerator_instructions\":null,");
#else
  PRINTF("\"counter_profile\":\"instructions\",");
  PRINTF("\"tcdm_accessed\":null,\"tcdm_congested\":null,");
  PRINTF("\"retired_instructions\":%u,",
         sample->retired_instructions);
  PRINTF("\"retired_accelerator_instructions\":%u,",
         sample->retired_accelerator_instructions);
#endif
  PRINTF("\"max_abs_bits\":%u,", float_bits(metrics->max_abs));
  PRINTF("\"max_rel_numerator_bits\":%u,",
         float_bits(metrics->max_rel_numerator));
  PRINTF("\"max_rel_denominator_bits\":%u,",
         float_bits(metrics->max_rel_denominator));
  PRINTF("\"sum_sq_bits\":%u,", float_bits(metrics->sum_sq));
  PRINTF("\"sum_abs_bits\":%u,", float_bits(metrics->sum_abs));
  PRINTF("\"sum_ref_sq_bits\":%u,", float_bits(metrics->sum_ref_sq));
  PRINTF("\"checked\":%u,\"bit_equal\":%u,", metrics->checked,
         metrics->bit_equal);
  PRINTF("\"nonfinite\":%u,", metrics->nonfinite);
  PRINTF("\"nan_count\":%u,", metrics->nan_count);
  PRINTF("\"pos_inf_count\":%u,", metrics->pos_inf_count);
  PRINTF("\"neg_inf_count\":%u,", metrics->neg_inf_count);
  PRINTF("\"status\":\"%s\",", status);
  PRINTF("\"saw_busy\":%u,", (uint32_t)sample->saw_busy);
  PRINTF("\"footprint_bytes\":%u,", buffers->footprint_bytes);
  PRINTF("\"allocation_bytes\":%u,", buffers->allocation_bytes);
  PRINTF("\"runtime_reserved_bytes\":%u,",
         buffers->runtime_reserved_bytes);
  PRINTF("\"memory_footprint_bytes\":%u,",
         buffers->memory_footprint_bytes);
  PRINTF("\"tcdm_capacity_bytes\":%u}\n", (uint32_t)SNRT_TCDM_SIZE);
}

static void print_terminal_status(const online_merge_buffers_t *buffers,
                                  const char *status) {
  online_merge_sample_t sample = {
      .status = status,
  };
  online_merge_metrics_t metrics = {
      .max_rel_denominator = 1.0f,
      .passed = 1,
  };
#if ONLINE_MERGE_IMPLEMENTATION_SELECT == 0
  const char *implementations[] = {"B1", "B2-R", "A1", "B3"};
  for (uint32_t i = 0; i < 4; i++) {
    print_result(implementations[i], -1, buffers, &sample, &metrics, status);
  }
#else
  const char *implementation =
      ONLINE_MERGE_IMPLEMENTATION_SELECT == ONLINE_MERGE_IMPLEMENTATION_B1
          ? "B1"
      : ONLINE_MERGE_IMPLEMENTATION_SELECT ==
                ONLINE_MERGE_IMPLEMENTATION_B2_R
          ? "B2-R"
      : ONLINE_MERGE_IMPLEMENTATION_SELECT == ONLINE_MERGE_IMPLEMENTATION_A1
          ? "A1"
      : ONLINE_MERGE_IMPLEMENTATION_SELECT ==
                ONLINE_MERGE_IMPLEMENTATION_A1_MIXED
          ? "A1-mixed"
      : ONLINE_MERGE_IMPLEMENTATION_SELECT ==
                ONLINE_MERGE_IMPLEMENTATION_MODE_COMPARE
          ? "A1/mode-compare"
          : "B3";
  print_result(implementation, -1, buffers, &sample, &metrics, status);
#endif
}

static int metrics_pass(const online_merge_metrics_t *metrics) {
  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    if (!metrics[repeat].passed) {
      return 0;
    }
  }
  return 1;
}

static void print_first_failure(const char *implementation,
                                const online_merge_buffers_t *buffers,
                                const online_merge_metrics_t *metrics) {
  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    if (metrics[repeat].has_failure) {
      print_failure(implementation, (int)repeat, buffers, &metrics[repeat]);
      return;
    }
  }
}

int main(void) {
  if (snrt_cluster_core_idx() != 0) {
    snrt_cluster_hw_barrier();
    return 0;
  }

  online_merge_buffers_t buffers = {
      .n = ONLINE_MERGE_CASE_N,
      .d = ONLINE_MERGE_CASE_D,
  };
  int allocation =
      allocate_buffers(&buffers, ONLINE_MERGE_CASE_N, ONLINE_MERGE_CASE_D);
  if (allocation == 1) {
    print_terminal_status(&buffers, "capacity_skip");
    PRINTF("online-softmax-merge PASS status=capacity_skip\n");
    snrt_cluster_hw_barrier();
    return 0;
  }
  if (allocation != 0) {
    print_terminal_status(&buffers, "tool_error");
    PRINTF("online-softmax-merge FAILURE allocation\n");
    snrt_cluster_hw_barrier();
    return -1;
  }
  load_case(&buffers);

#if ONLINE_MERGE_IMPLEMENTATION_SELECT == \
    ONLINE_MERGE_IMPLEMENTATION_MODE_COMPARE
  // Selector 5 intentionally uses one allocated row/vector even when this
  // target shares a paper-build case header with larger N/D.  The allocation
  // above has already reserved the full generated case, so narrowing the
  // runtime view cannot expose an out-of-bounds access.
  buffers.n = 1u;
  buffers.d = 1u;
  buffers.stride = sizeof(float);
  load_mode_compare_vector(&buffers);
  set_mode_compare_reference(&buffers, ONLINE_MERGE_MODE_LEGACY_SCALAR);
#endif

  if (ONLINE_MERGE_CASE_UNSUPPORTED) {
    print_terminal_status(&buffers, "unsupported");
    PRINTF("online-softmax-merge PASS status=unsupported\n");
    snrt_cluster_hw_barrier();
    return 0;
  }

#if ONLINE_MERGE_IMPLEMENTATION_SELECT != 0
  if (ONLINE_MERGE_IMPLEMENTATION_SELECT ==
      ONLINE_MERGE_IMPLEMENTATION_MODE_COMPARE) {
    online_merge_sample_t legacy_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
    online_merge_sample_t mixed_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
    online_merge_metrics_t legacy_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};
    online_merge_metrics_t mixed_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};

    // Both launches consume the same frozen scalar-interface vector.  Only
    // the output/state buffers are cleared between launches, so this is a
    // direct software-visible mode comparison rather than two generated
    // cases.
    load_mode_compare_vector(&buffers);
    set_mode_compare_reference(&buffers, ONLINE_MERGE_MODE_LEGACY_SCALAR);
    int legacy_result =
        run_a1_mode(&buffers, legacy_samples, legacy_metrics,
                    ONLINE_MERGE_MODE_LEGACY_SCALAR,
                    ONLINE_MERGE_IMPLEMENTATION_A1);
    if (legacy_result == 0) {
      check_mode_compare_exact(&buffers, &legacy_metrics[0],
                               ONLINE_MERGE_MODE_LEGACY_SCALAR);
    }

    set_mode_compare_reference(&buffers, ONLINE_MERGE_MODE_MIXED_SCALAR);
    int mixed_result = run_a1_mode(
        &buffers, mixed_samples, mixed_metrics,
        ONLINE_MERGE_MODE_MIXED_SCALAR,
        ONLINE_MERGE_IMPLEMENTATION_MODE_COMPARE);
    if (mixed_result == 0) {
      check_mode_compare_exact(&buffers, &mixed_metrics[0],
                               ONLINE_MERGE_MODE_MIXED_SCALAR);
    }

    if (legacy_result == 0) {
      print_result("A1", 0, &buffers, &legacy_samples[0],
                   &legacy_metrics[0], 0);
    } else {
      const char *status = legacy_samples[0].status != 0
                               ? legacy_samples[0].status
                               : "tool_error";
      print_result("A1", legacy_result < 0 ? -1 : 0, &buffers,
                   &legacy_samples[0], &legacy_metrics[0], status);
    }
    if (mixed_result == 0) {
      print_result("A1-mixed", 0, &buffers, &mixed_samples[0],
                   &mixed_metrics[0], 0);
    } else {
      const char *status = mixed_samples[0].status != 0
                               ? mixed_samples[0].status
                               : "tool_error";
      print_result("A1-mixed", mixed_result < 0 ? -1 : 0, &buffers,
                   &mixed_samples[0], &mixed_metrics[0], status);
    }
    print_first_failure("A1", &buffers, legacy_metrics);
    print_first_failure("A1-mixed", &buffers, mixed_metrics);

    int result = legacy_result == 0 && mixed_result == 0 &&
                 metrics_pass(legacy_metrics) && metrics_pass(mixed_metrics);
    PRINTF("online-softmax-merge %s\n", result ? "PASS" : "FAILURE");
    snrt_cluster_hw_barrier();
    return result ? 0 : -1;
  }

  online_merge_sample_t samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t metrics[ONLINE_MERGE_MAX_REPEATS] = {0};
  const char *implementation;
  int run_result = 0;

  if (ONLINE_MERGE_IMPLEMENTATION_SELECT == ONLINE_MERGE_IMPLEMENTATION_B1) {
    implementation = "B1";
    run_b1(&buffers, samples, metrics);
  } else if (ONLINE_MERGE_IMPLEMENTATION_SELECT ==
             ONLINE_MERGE_IMPLEMENTATION_B2_R) {
    implementation = "B2-R";
    run_b2_r(&buffers, samples, metrics);
  } else if (ONLINE_MERGE_IMPLEMENTATION_SELECT ==
             ONLINE_MERGE_IMPLEMENTATION_A1) {
    implementation = "A1";
    run_result = run_a1(&buffers, samples, metrics);
  } else if (ONLINE_MERGE_IMPLEMENTATION_SELECT ==
             ONLINE_MERGE_IMPLEMENTATION_A1_MIXED) {
    implementation = "A1-mixed";
    run_result = run_a1_mixed(&buffers, samples, metrics);
  } else {
    implementation = "B3";
    run_result = run_b3(&buffers, samples, metrics);
  }

  if (run_result == 0) {
    print_result(implementation, 0, &buffers, &samples[0], &metrics[0], 0);
  } else {
    const char *status = samples[0].status != 0 ? samples[0].status
                                                : "tool_error";
    print_result(implementation, run_result < 0 ? -1 : 0, &buffers,
                 &samples[0], &metrics[0], status);
  }
  print_first_failure(implementation, &buffers, metrics);
  int result = run_result == 0 && metrics_pass(metrics);
  PRINTF("online-softmax-merge %s\n", result ? "PASS" : "FAILURE");
  snrt_cluster_hw_barrier();
  return result ? 0 : -1;
#else
  online_merge_sample_t b1_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_sample_t b2_r_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_sample_t a1_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_sample_t b3_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t b1_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t b2_r_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t a1_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t b3_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};

  run_b1(&buffers, b1_samples, b1_metrics);
  run_b2_r(&buffers, b2_r_samples, b2_r_metrics);
  int a1_result = run_a1(&buffers, a1_samples, a1_metrics);
  int b3_result = run_b3(&buffers, b3_samples, b3_metrics);

  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    print_result("B1", (int)repeat, &buffers, &b1_samples[repeat],
                 &b1_metrics[repeat], 0);
    print_result("B2-R", (int)repeat, &buffers, &b2_r_samples[repeat],
                 &b2_r_metrics[repeat], 0);
  }
  if (a1_result == 0) {
    for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
      print_result("A1", (int)repeat, &buffers, &a1_samples[repeat],
                   &a1_metrics[repeat], 0);
    }
  } else if (a1_result < 0) {
    const char *status = a1_samples[0].status != 0
                             ? a1_samples[0].status
                             : "tool_error";
    print_result("A1", -1, &buffers, &a1_samples[0], &a1_metrics[0], status);
  } else {
    uint32_t failed_repeat = (uint32_t)(a1_result - 1);
    for (uint32_t repeat = 0; repeat <= failed_repeat; repeat++) {
      print_result("A1", (int)repeat, &buffers, &a1_samples[repeat],
                   &a1_metrics[repeat], 0);
    }
  }
  if (b3_result == 0) {
    for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
      print_result("B3", (int)repeat, &buffers, &b3_samples[repeat],
                   &b3_metrics[repeat], 0);
    }
  } else if (b3_result < 0) {
    const char *status = b3_samples[0].status != 0
                             ? b3_samples[0].status
                             : "tool_error";
    print_result("B3", -1, &buffers, &b3_samples[0], &b3_metrics[0], status);
  } else {
    uint32_t failed_repeat = (uint32_t)(b3_result - 1);
    for (uint32_t repeat = 0; repeat <= failed_repeat; repeat++) {
      print_result("B3", (int)repeat, &buffers, &b3_samples[repeat],
                   &b3_metrics[repeat], 0);
    }
  }

  print_first_failure("B1", &buffers, b1_metrics);
  print_first_failure("B2-R", &buffers, b2_r_metrics);
  print_first_failure("A1", &buffers, a1_metrics);
  print_first_failure("B3", &buffers, b3_metrics);

  int result = metrics_pass(b1_metrics) && metrics_pass(b2_r_metrics) &&
               a1_result == 0 && metrics_pass(a1_metrics) && b3_result == 0 &&
               metrics_pass(b3_metrics);
  PRINTF("online-softmax-merge %s\n", result ? "PASS" : "FAILURE");
  snrt_cluster_hw_barrier();
  return result ? 0 : -1;
#endif
}
