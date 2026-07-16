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
#include "rtl_reference.h"

#undef PRINTF
#define PRINTF(...) printf(__VA_ARGS__)

#define ONLINE_MERGE_TOL 1.0e-3f
#define ONLINE_MERGE_MAX_REPEATS 16u
#define ONLINE_MERGE_MAX_POLLS 1000000u
#define ONLINE_MERGE_ALLOC_ALIGN 256u

#ifndef ONLINE_MERGE_TRACE_PROXY
#define ONLINE_MERGE_TRACE_PROXY 0
#endif

#define ONLINE_MERGE_IMPLEMENTATION_B1 1u
#define ONLINE_MERGE_IMPLEMENTATION_B2_R 2u
#define ONLINE_MERGE_IMPLEMENTATION_B3 3u

// The three implementations' measured samples and correctness state make
// main's frame larger than the runtime's 1 KiB default.  Reserve 8 KiB per
// core so the stacks remain disjoint while the nonzero core waits at barrier.
const uint32_t snrt_stack_size = 13u;

_Static_assert(ONLINE_MERGE_CASE_REPEATS >= 3u,
               "online merge requires at least three measured repeats");
_Static_assert(ONLINE_MERGE_CASE_REPEATS <= ONLINE_MERGE_MAX_REPEATS,
               "online merge repeat count exceeds local sample storage");

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
  uint32_t n;
  uint32_t d;
  uint32_t stride;
  uint32_t footprint_bytes;
  uint32_t allocation_bytes;
} online_merge_buffers_t;

typedef struct {
  uint64_t cycles;
  uint32_t tcdm_accessed;
  uint32_t tcdm_congested;
  int saw_busy;
  const char *status;
} online_merge_sample_t;

typedef struct {
  float max_abs;
  float max_rel_numerator;
  float max_rel_denominator;
  float sum_sq;
  uint32_t checked;
  uint32_t bit_equal;
  uint32_t nonfinite;
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
  uint64_t row_bytes = 32ull + 16ull * (uint64_t)d;
  uint64_t limit = ((uint64_t)SNRT_TCDM_SIZE * 7u) / 10u;

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
  if (stride_bytes > UINT32_MAX || vector_count > UINT32_MAX ||
      footprint_bytes > UINT32_MAX || allocation_bytes > UINT32_MAX) {
    return 1;
  }
  buffers->stride = (uint32_t)stride_bytes;
  buffers->footprint_bytes = (uint32_t)footprint_bytes;
  buffers->allocation_bytes = (uint32_t)allocation_bytes;
  if (allocation_bytes > limit) {
    return 1;
  }

  float *storage = (float *)snrt_l1alloc(buffers->allocation_bytes);
  if (storage == 0) {
    return -1;
  }
  float *cursor = storage;
  uint32_t vectors = (uint32_t)vector_count;
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

static void clear_output(online_merge_buffers_t *buffers) {
  uint32_t vectors = buffers->n * buffers->d;
  for (uint32_t i = 0; i < buffers->n; i++) {
    buffers->m_out[i] = 0.0f;
    buffers->l_out[i] = 0.0f;
  }
  for (uint32_t i = 0; i < vectors; i++) {
    buffers->o_out[i] = 0.0f;
  }
}

static void smu_start(const online_merge_buffers_t *buffers) {
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
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_START_BIT;
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

static void start_tcdm_counters(void) {
  snrt_reset_perf_counter(SNRT_PERF_CNT0);
  snrt_reset_perf_counter(SNRT_PERF_CNT1);
  snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_TCDM_ACCESSED,
                          0);
  snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_TCDM_CONGESTED,
                          0);
}

static void stop_tcdm_counters(online_merge_sample_t *sample) {
  snrt_stop_perf_counter(SNRT_PERF_CNT0);
  snrt_stop_perf_counter(SNRT_PERF_CNT1);
  sample->tcdm_accessed = snrt_get_perf_counter(SNRT_PERF_CNT0);
  sample->tcdm_congested = snrt_get_perf_counter(SNRT_PERF_CNT1);
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
  }
}

static void trace_marker_stop(uint32_t implementation, uint32_t repeat) {
  if (trace_marker_enabled(implementation, repeat)) {
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
  metrics->sum_sq += absolute * absolute;
  if (!float_is_finite(metrics->sum_sq)) {
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
    start_tcdm_counters();
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
    stop_tcdm_counters(&samples[repeat]);
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
    start_tcdm_counters();
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
    stop_tcdm_counters(&samples[repeat]);
    metrics[repeat] = check_output(buffers);
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

static int run_b3(online_merge_buffers_t *buffers,
                  online_merge_sample_t *samples,
                  online_merge_metrics_t *metrics) {
  clear_output(buffers);
  smu_start(buffers);
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
    start_tcdm_counters();
    trace_marker_start(ONLINE_MERGE_IMPLEMENTATION_B3, repeat);
    uint64_t start = benchmark_get_cycle64();
    smu_start(buffers);
    int saw_busy;
    online_merge_wait_t wait_result = smu_wait(&saw_busy);
    uint64_t end = benchmark_get_cycle64();
    trace_marker_stop(ONLINE_MERGE_IMPLEMENTATION_B3, repeat);
    samples[repeat].cycles = end - start;
    samples[repeat].saw_busy = saw_busy;
    samples[repeat].status = wait_status(wait_result);
    stop_tcdm_counters(&samples[repeat]);
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
  return "O";
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
  PRINTF("\"tcdm_accessed\":%u,", sample->tcdm_accessed);
  PRINTF("\"tcdm_congested\":%u,", sample->tcdm_congested);
  PRINTF("\"max_abs_bits\":%u,", float_bits(metrics->max_abs));
  PRINTF("\"max_rel_numerator_bits\":%u,",
         float_bits(metrics->max_rel_numerator));
  PRINTF("\"max_rel_denominator_bits\":%u,",
         float_bits(metrics->max_rel_denominator));
  PRINTF("\"sum_sq_bits\":%u,", float_bits(metrics->sum_sq));
  PRINTF("\"checked\":%u,\"bit_equal\":%u,", metrics->checked,
         metrics->bit_equal);
  PRINTF("\"nonfinite\":%u,", metrics->nonfinite);
  PRINTF("\"status\":\"%s\",", status);
  PRINTF("\"saw_busy\":%u,", (uint32_t)sample->saw_busy);
  PRINTF("\"footprint_bytes\":%u,", buffers->footprint_bytes);
  PRINTF("\"allocation_bytes\":%u,", buffers->allocation_bytes);
  PRINTF("\"tcdm_capacity_bytes\":%u}\n", (uint32_t)SNRT_TCDM_SIZE);
}

static void print_terminal_status(const online_merge_buffers_t *buffers,
                                  const char *status) {
  const char *implementations[] = {"B1", "B2-R", "B3"};
  online_merge_sample_t sample = {
      .status = status,
  };
  online_merge_metrics_t metrics = {
      .max_rel_denominator = 1.0f,
      .passed = 1,
  };
  for (uint32_t i = 0; i < 3; i++) {
    print_result(implementations[i], -1, buffers, &sample, &metrics, status);
  }
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

  if (ONLINE_MERGE_CASE_UNSUPPORTED) {
    print_terminal_status(&buffers, "unsupported");
    PRINTF("online-softmax-merge PASS status=unsupported\n");
    snrt_cluster_hw_barrier();
    return 0;
  }

  online_merge_sample_t b1_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_sample_t b2_r_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_sample_t b3_samples[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t b1_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t b2_r_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};
  online_merge_metrics_t b3_metrics[ONLINE_MERGE_MAX_REPEATS] = {0};

  run_b1(&buffers, b1_samples, b1_metrics);
  run_b2_r(&buffers, b2_r_samples, b2_r_metrics);
  int b3_result = run_b3(&buffers, b3_samples, b3_metrics);

  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    print_result("B1", (int)repeat, &buffers, &b1_samples[repeat],
                 &b1_metrics[repeat], 0);
    print_result("B2-R", (int)repeat, &buffers, &b2_r_samples[repeat],
                 &b2_r_metrics[repeat], 0);
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
  print_first_failure("B3", &buffers, b3_metrics);

  int result = metrics_pass(b1_metrics) && metrics_pass(b2_r_metrics) &&
               b3_result == 0 && metrics_pass(b3_metrics);
  PRINTF("online-softmax-merge %s\n", result ? "PASS" : "FAILURE");
  snrt_cluster_hw_barrier();
  return result ? 0 : -1;
}
