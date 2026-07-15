// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#include <benchmark.h>
#include <perf_cnt.h>
#include <snrt.h>
#include <spatz_cluster_peripheral.h>
#include <stdint.h>
#include <stdio.h>

#include "concurrency_workloads.h"
#include "online_merge_case_data.h"

#undef PRINTF
#define PRINTF(...) printf(__VA_ARGS__)

#define ONLINE_MERGE_TOL 1.0e-3f
#define ONLINE_MERGE_MAX_REPEATS 16u
#define ONLINE_MERGE_ALLOC_ALIGN 256u
#define ONLINE_MERGE_STREAM_ELEMENTS 2049u
#define ONLINE_MERGE_STREAM_AVL_CAP 8u
#define ONLINE_MERGE_PHASE_COUNT 16u
#define ONLINE_MERGE_PHASE_STEP_BYTES 8u
#define ONLINE_MERGE_PHASE_PERIOD_BYTES 128u
#define ONLINE_MERGE_POLL_BACKOFF_ITERATIONS 64u
#define ONLINE_MERGE_MAX_STATUS_READS 4096u
#define ONLINE_MERGE_REGISTER_CALIBRATION_STEPS 3u
#define ONLINE_MERGE_REGISTER_MAX_ITERATIONS 10000000u

const uint32_t snrt_stack_size = 13u;

_Static_assert(ONLINE_MERGE_CASE_REPEATS >= 3u,
               "concurrency experiment requires at least three repeats");
_Static_assert(ONLINE_MERGE_CASE_REPEATS <= ONLINE_MERGE_MAX_REPEATS,
               "concurrency repeat count exceeds supported maximum");
_Static_assert(ONLINE_MERGE_STREAM_ELEMENTS % ONLINE_MERGE_STREAM_AVL_CAP != 0u,
               "stream workload must exercise an RVV tail");

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
} merge_buffers_t;

typedef struct {
  uint8_t *raw;
  uint32_t raw_bytes;
  uint32_t elements;
  uint32_t array_bytes;
  uint32_t source_destination_spacing;
} stream_workspace_t;

typedef struct {
  uint32_t passed;
  uint32_t checked;
  uint32_t mismatches;
  float max_abs;
  uint32_t failure_index;
  uint32_t expected_bits;
  uint32_t actual_bits;
} correctness_t;

typedef struct {
  uint64_t total_cycles;
  uint64_t core_cycles;
  uint32_t tcdm_accessed;
  uint32_t tcdm_congested;
  uint32_t status_after_core;
  uint32_t status_reads;
  uint32_t busy_status_reads;
  uint32_t poll_backoff_calls;
  uint32_t poll_checksum;
  uint32_t core_checksum;
  int32_t smu_invocation;
  correctness_t merge_correctness;
  correctness_t core_correctness;
  const char *status;
} concurrency_sample_t;

typedef enum {
  CORE_WORK_NONE = 0,
  CORE_WORK_REGISTER = 1,
  CORE_WORK_STREAM = 2,
} core_work_t;

typedef enum {
  WAIT_OK = 0,
  WAIT_ERROR = 1,
  WAIT_TIMEOUT = 2,
} wait_result_t;

static uint32_t next_smu_invocation;
static uint32_t all_passed = 1u;

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

static uint32_t float_is_finite(float value) {
  return ((float_bits(value) >> 23) & 0xffu) != 0xffu;
}

static uint64_t align_up_u64(uint64_t value, uint64_t alignment) {
  return (value + alignment - 1u) & ~(alignment - 1u);
}

static uintptr_t align_up_ptr(uintptr_t value, uintptr_t alignment) {
  return (value + alignment - 1u) & ~(alignment - 1u);
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

static int allocate_buffers(merge_buffers_t *merge,
                            stream_workspace_t *stream) {
  uint64_t n = ONLINE_MERGE_CASE_N;
  uint64_t d = ONLINE_MERGE_CASE_D;
  uint64_t vectors = n * d;
  uint64_t footprint = n * (32ull + 16ull * d);
  uint64_t merge_allocation =
      align_up_u64(footprint, ONLINE_MERGE_ALLOC_ALIGN);
  uint64_t array_bytes = ONLINE_MERGE_STREAM_ELEMENTS * sizeof(float);
  uint64_t spacing = align_up_u64(array_bytes,
                                  ONLINE_MERGE_PHASE_PERIOD_BYTES);
  uint64_t stream_allocation = ONLINE_MERGE_ALLOC_ALIGN + spacing +
                               array_bytes;
  uint64_t limit = ((uint64_t)SNRT_TCDM_SIZE * 7u) / 10u;

  merge->n = (uint32_t)n;
  merge->d = (uint32_t)d;
  if (d > UINT32_MAX / sizeof(float) || vectors > UINT32_MAX ||
      footprint > UINT32_MAX || merge_allocation > UINT32_MAX ||
      stream_allocation > UINT32_MAX ||
      merge_allocation + stream_allocation > limit) {
    return 1;
  }
  merge->stride = (uint32_t)(d * sizeof(float));
  merge->footprint_bytes = (uint32_t)footprint;
  merge->allocation_bytes = (uint32_t)merge_allocation;

  float *storage = (float *)snrt_l1alloc(merge->allocation_bytes);
  if (storage == 0) {
    return -1;
  }
  float *cursor = storage;
  uint32_t vector_count = (uint32_t)vectors;
  take_floats(&cursor, &merge->m_old, merge->n);
  take_floats(&cursor, &merge->l_old, merge->n);
  take_floats(&cursor, &merge->o_old, vector_count);
  take_floats(&cursor, &merge->m_tile, merge->n);
  take_floats(&cursor, &merge->l_tile, merge->n);
  take_floats(&cursor, &merge->o_tile, vector_count);
  take_floats(&cursor, &merge->m_out, merge->n);
  take_floats(&cursor, &merge->l_out, merge->n);
  take_floats(&cursor, &merge->o_out, vector_count);
  take_floats(&cursor, &merge->m_ref, merge->n);
  take_floats(&cursor, &merge->l_ref, merge->n);
  take_floats(&cursor, &merge->o_ref, vector_count);

  stream->raw_bytes = (uint32_t)stream_allocation;
  stream->raw = (uint8_t *)snrt_l1alloc(stream->raw_bytes);
  if (stream->raw == 0) {
    return -1;
  }
  stream->elements = ONLINE_MERGE_STREAM_ELEMENTS;
  stream->array_bytes = (uint32_t)array_bytes;
  stream->source_destination_spacing = (uint32_t)spacing;
  return 0;
}

static void copy_bits(float *destination, const uint32_t *source,
                      uint32_t count) {
  for (uint32_t index = 0; index < count; index++) {
    destination[index] = bits_float(source[index]);
  }
}

static void load_case(merge_buffers_t *merge) {
  uint32_t vectors = merge->n * merge->d;
  copy_bits(merge->m_old, online_merge_m_old_bits, merge->n);
  copy_bits(merge->l_old, online_merge_l_old_bits, merge->n);
  copy_bits(merge->o_old, online_merge_o_old_bits, vectors);
  copy_bits(merge->m_tile, online_merge_m_tile_bits, merge->n);
  copy_bits(merge->l_tile, online_merge_l_tile_bits, merge->n);
  copy_bits(merge->o_tile, online_merge_o_tile_bits, vectors);
  copy_bits(merge->m_ref, online_merge_golden_m_bits, merge->n);
  copy_bits(merge->l_ref, online_merge_golden_l_bits, merge->n);
  copy_bits(merge->o_ref, online_merge_golden_o_bits, vectors);
}

static void clear_merge_output(merge_buffers_t *merge) {
  uint32_t vectors = merge->n * merge->d;
  for (uint32_t index = 0; index < merge->n; index++) {
    merge->m_out[index] = 0.0f;
    merge->l_out[index] = 0.0f;
  }
  for (uint32_t index = 0; index < vectors; index++) {
    merge->o_out[index] = 0.0f;
  }
}

static float *stream_source(const merge_buffers_t *merge,
                            const stream_workspace_t *stream,
                            uint32_t phase_bytes) {
  uintptr_t aligned = align_up_ptr((uintptr_t)stream->raw,
                                   ONLINE_MERGE_PHASE_PERIOD_BYTES);
  uintptr_t smu_base = (uintptr_t)merge->o_old;
  uint32_t current = (uint32_t)((aligned - smu_base) & 0x78u);
  uint32_t adjustment = (phase_bytes - current) & 0x78u;
  return (float *)(aligned + adjustment);
}

static float *stream_destination(const stream_workspace_t *stream,
                                 float *source) {
  return (float *)((uint8_t *)source +
                   stream->source_destination_spacing);
}

static uint32_t relative_phase_bytes(const void *core_pointer,
                                     const void *smu_pointer) {
  return (uint32_t)(((uintptr_t)core_pointer - (uintptr_t)smu_pointer) &
                    0x78u);
}

static uint32_t bank_phase(const void *pointer) {
  return (uint32_t)(((uintptr_t)pointer >> 3) & 0xfu);
}

static float stream_value(uint32_t index) {
  int32_t centered = (int32_t)(index % 97u) - 48;
  return (float)centered * 0.125f;
}

static void initialize_stream(const stream_workspace_t *stream,
                              float *source, float *destination) {
  for (uint32_t index = 0; index < stream->elements; index++) {
    source[index] = stream_value(index);
    destination[index] = bits_float(0x7fc00000u);
  }
}

static correctness_t correctness_init(void) {
  correctness_t result = {
      .passed = 1u,
  };
  return result;
}

static void record_correctness(correctness_t *result, uint32_t index,
                               float actual, float expected,
                               uint32_t require_bit_equal) {
  result->checked++;
  float absolute = absf(actual - expected);
  if (float_is_finite(absolute) && absolute > result->max_abs) {
    result->max_abs = absolute;
  }
  uint32_t mismatch = 0u;
  if (!float_is_finite(actual) || !float_is_finite(expected)) {
    mismatch = 1u;
  } else if (require_bit_equal) {
    mismatch = float_bits(actual) != float_bits(expected);
  } else {
    float scale = absf(expected) > 1.0f ? absf(expected) : 1.0f;
    mismatch = absolute > ONLINE_MERGE_TOL * scale;
  }
  if (!mismatch) {
    return;
  }
  result->mismatches++;
  result->passed = 0u;
  if (result->mismatches == 1u) {
    result->failure_index = index;
    result->expected_bits = float_bits(expected);
    result->actual_bits = float_bits(actual);
  }
}

static correctness_t check_merge_output(const merge_buffers_t *merge) {
  correctness_t result = correctness_init();
  uint32_t flat_index = 0u;
  for (uint32_t row = 0; row < merge->n; row++) {
    record_correctness(&result, flat_index++, merge->m_out[row],
                       merge->m_ref[row], 0u);
    record_correctness(&result, flat_index++, merge->l_out[row],
                       merge->l_ref[row], 0u);
    uint32_t base = row * merge->d;
    for (uint32_t col = 0; col < merge->d; col++) {
      record_correctness(&result, flat_index++, merge->o_out[base + col],
                         merge->o_ref[base + col], 0u);
    }
  }
  return result;
}

static correctness_t check_stream_output(const stream_workspace_t *stream,
                                         const float *source,
                                         const float *destination) {
  correctness_t result = correctness_init();
  for (uint32_t index = 0; index < stream->elements; index++) {
    record_correctness(&result, index, destination[index], source[index], 1u);
  }
  return result;
}

static void smu_start(const merge_buffers_t *merge) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_OLD_REG_OFFSET) =
      tcdm_offset(merge->m_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_OLD_REG_OFFSET) =
      tcdm_offset(merge->l_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_OLD_REG_OFFSET) =
      tcdm_offset(merge->o_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_TILE_REG_OFFSET) =
      tcdm_offset(merge->m_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET) =
      tcdm_offset(merge->l_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_TILE_REG_OFFSET) =
      tcdm_offset(merge->o_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_M_REG_OFFSET) =
      tcdm_offset(merge->m_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_L_REG_OFFSET) =
      tcdm_offset(merge->l_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_O_REG_OFFSET) =
      tcdm_offset(merge->o_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET) = merge->n;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_D_REG_OFFSET) = merge->d;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STRIDE_REG_OFFSET) =
      merge->stride;
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

static uint32_t status_bit(uint32_t status, uint32_t bit) {
  return (status >> bit) & 1u;
}

static wait_result_t wait_sparse(uint32_t initial_status,
                                 concurrency_sample_t *sample) {
  uint32_t status = initial_status;
  for (;;) {
    if (status_bit(status,
                   SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_BUSY_BIT)) {
      sample->busy_status_reads++;
    }
    if (status_bit(status,
                   SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_ERROR_BIT)) {
      return WAIT_ERROR;
    }
    if (status_bit(status,
                   SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_DONE_BIT)) {
      return WAIT_OK;
    }
    if (sample->status_reads >= ONLINE_MERGE_MAX_STATUS_READS) {
      return WAIT_TIMEOUT;
    }
    sample->poll_checksum ^=
        online_merge_register_workload(
            ONLINE_MERGE_POLL_BACKOFF_ITERATIONS,
            sample->status_reads ^ sample->poll_checksum);
    sample->poll_backoff_calls++;
    status = smu_status();
    sample->status_reads++;
  }
}

static void start_tcdm_counters(void) {
  snrt_reset_perf_counter(SNRT_PERF_CNT0);
  snrt_reset_perf_counter(SNRT_PERF_CNT1);
  snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_TCDM_ACCESSED,
                          0);
  snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_TCDM_CONGESTED,
                          0);
}

static void stop_tcdm_counters(concurrency_sample_t *sample) {
  snrt_stop_perf_counter(SNRT_PERF_CNT0);
  snrt_stop_perf_counter(SNRT_PERF_CNT1);
  sample->tcdm_accessed = snrt_get_perf_counter(SNRT_PERF_CNT0);
  sample->tcdm_congested = snrt_get_perf_counter(SNRT_PERF_CNT1);
}

static const char *wait_status(wait_result_t result) {
  if (result == WAIT_TIMEOUT) {
    return "timeout";
  }
  if (result == WAIT_ERROR) {
    return "tool_error";
  }
  return "pass";
}

static uint32_t stream_bytes(const stream_workspace_t *stream) {
  return 2u * stream->array_bytes;
}

static uint32_t register_seed(int32_t repeat) {
  return 0x6d2b79f5u ^ (uint32_t)repeat;
}

static void print_sample(const char *scenario, int32_t repeat,
                         const merge_buffers_t *merge,
                         const stream_workspace_t *stream,
                         const float *source, const float *destination,
                         uint32_t phase_bytes, uint32_t register_iterations,
                         core_work_t core_work,
                         const concurrency_sample_t *sample) {
  uint32_t total_hi = (uint32_t)(sample->total_cycles >> 32);
  uint32_t total_lo = (uint32_t)sample->total_cycles;
  uint32_t core_hi = (uint32_t)(sample->core_cycles >> 32);
  uint32_t core_lo = (uint32_t)sample->core_cycles;
  uint32_t has_stream = core_work == CORE_WORK_STREAM;
  uint32_t has_register = core_work == CORE_WORK_REGISTER;
  uint32_t relative_phase =
      has_stream ? relative_phase_bytes(source, merge->o_old) : UINT32_MAX;
  uint32_t destination_phase =
      has_stream ? relative_phase_bytes(destination, merge->o_old)
                 : UINT32_MAX;

  PRINTF("OM_CONCURRENCY {");
  PRINTF("\"schema_version\":1,\"scenario\":\"%s\",", scenario);
  PRINTF("\"repeat\":%d,\"N\":%u,\"D\":%u,", repeat, merge->n,
         merge->d);
  PRINTF("\"phase_bytes\":%u,\"relative_phase_bytes\":%u,",
         phase_bytes, relative_phase);
  PRINTF("\"destination_relative_phase_bytes\":%u,",
         destination_phase);
  PRINTF("\"smu_bank_phase\":%u,", bank_phase(merge->o_old));
  PRINTF("\"core_source_bank_phase\":%u,",
         has_stream ? bank_phase(source) : UINT32_MAX);
  PRINTF("\"core_destination_bank_phase\":%u,",
         has_stream ? bank_phase(destination) : UINT32_MAX);
  PRINTF("\"smu_invocation\":%d,", sample->smu_invocation);
  PRINTF("\"total_cycles_hi\":%u,\"total_cycles_lo\":%u,", total_hi,
         total_lo);
  PRINTF("\"core_cycles_hi\":%u,\"core_cycles_lo\":%u,", core_hi,
         core_lo);
  PRINTF("\"tcdm_accessed\":%u,\"tcdm_congested\":%u,",
         sample->tcdm_accessed, sample->tcdm_congested);
  PRINTF("\"status_after_core\":%u,\"status_reads\":%u,",
         sample->status_after_core, sample->status_reads);
  PRINTF("\"busy_status_reads\":%u,\"poll_backoff_calls\":%u,",
         sample->busy_status_reads, sample->poll_backoff_calls);
  PRINTF("\"poll_backoff_iterations\":%u,",
         ONLINE_MERGE_POLL_BACKOFF_ITERATIONS);
  PRINTF("\"poll_checksum\":%u,\"core_checksum\":%u,",
         sample->poll_checksum, sample->core_checksum);
  PRINTF("\"status_reads_during_core\":0,");
  PRINTF("\"counter_reads_inside_window\":0,");
  PRINTF("\"register_iterations\":%u,", has_register
                                                    ? register_iterations
                                                    : 0u);
  PRINTF("\"core_elements\":%u,", has_stream ? stream->elements : 0u);
  PRINTF("\"core_bytes\":%u,", has_stream ? stream_bytes(stream) : 0u);
  PRINTF("\"stream_array_bytes\":%u,",
         has_stream ? stream->array_bytes : 0u);
  PRINTF("\"stream_tail_elements\":%u,",
         has_stream ? stream->elements % ONLINE_MERGE_STREAM_AVL_CAP : 0u);
  PRINTF("\"merge_checked\":%u,\"merge_mismatches\":%u,",
         sample->merge_correctness.checked,
         sample->merge_correctness.mismatches);
  PRINTF("\"merge_max_abs_bits\":%u,",
         float_bits(sample->merge_correctness.max_abs));
  PRINTF("\"core_checked\":%u,\"core_mismatches\":%u,",
         sample->core_correctness.checked,
         sample->core_correctness.mismatches);
  PRINTF("\"failure_index\":%u,",
         sample->merge_correctness.mismatches
             ? sample->merge_correctness.failure_index
             : sample->core_correctness.failure_index);
  PRINTF("\"expected_bits\":%u,",
         sample->merge_correctness.mismatches
             ? sample->merge_correctness.expected_bits
             : sample->core_correctness.expected_bits);
  PRINTF("\"actual_bits\":%u,",
         sample->merge_correctness.mismatches
             ? sample->merge_correctness.actual_bits
             : sample->core_correctness.actual_bits);
  PRINTF("\"status\":\"%s\"}\n", sample->status);
}

static void print_meta(const merge_buffers_t *merge,
                       const stream_workspace_t *stream,
                       uint32_t register_iterations,
                       uint64_t register_target_cycles,
                       uint64_t backoff_cycles) {
  PRINTF("OM_CONCURRENCY_META {");
  PRINTF("\"schema_version\":1,\"N\":%u,\"D\":%u,", merge->n,
         merge->d);
  PRINTF("\"repeats\":%u,\"phase_count\":%u,",
         ONLINE_MERGE_CASE_REPEATS, ONLINE_MERGE_PHASE_COUNT);
  PRINTF("\"phase_step_bytes\":%u,\"phase_period_bytes\":%u,",
         ONLINE_MERGE_PHASE_STEP_BYTES, ONLINE_MERGE_PHASE_PERIOD_BYTES);
  PRINTF("\"smu_phase_base_offset\":%u,", tcdm_offset(merge->o_old));
  PRINTF("\"stream_elements\":%u,\"stream_array_bytes\":%u,",
         stream->elements, stream->array_bytes);
  PRINTF("\"stream_bytes_per_workload\":%u,", stream_bytes(stream));
  PRINTF("\"stream_source_destination_spacing\":%u,",
         stream->source_destination_spacing);
  PRINTF("\"stream_avl_cap\":%u,\"stream_tail_elements\":%u,",
         ONLINE_MERGE_STREAM_AVL_CAP,
         stream->elements % ONLINE_MERGE_STREAM_AVL_CAP);
  PRINTF("\"register_iterations\":%u,", register_iterations);
  PRINTF("\"register_target_cycles_hi\":%u,",
         (uint32_t)(register_target_cycles >> 32));
  PRINTF("\"register_target_cycles_lo\":%u,",
         (uint32_t)register_target_cycles);
  PRINTF("\"poll_backoff_iterations\":%u,",
         ONLINE_MERGE_POLL_BACKOFF_ITERATIONS);
  PRINTF("\"poll_backoff_cycles_hi\":%u,",
         (uint32_t)(backoff_cycles >> 32));
  PRINTF("\"poll_backoff_cycles_lo\":%u,", (uint32_t)backoff_cycles);
  PRINTF("\"max_status_reads\":%u,", ONLINE_MERGE_MAX_STATUS_READS);
  PRINTF("\"merge_footprint_bytes\":%u,", merge->footprint_bytes);
  PRINTF("\"merge_allocation_bytes\":%u,", merge->allocation_bytes);
  PRINTF("\"stream_allocation_bytes\":%u,", stream->raw_bytes);
  PRINTF("\"tcdm_capacity_bytes\":%u}\n", (uint32_t)SNRT_TCDM_SIZE);
}

static void mark_sample_status(concurrency_sample_t *sample) {
  if (sample->status[0] == 'p' &&
      (!sample->merge_correctness.passed ||
       !sample->core_correctness.passed)) {
    sample->status = "correctness_fail";
  }
  if (sample->status[0] != 'p') {
    all_passed = 0u;
  }
}

static uint32_t execute_core_work(core_work_t core_work,
                                  uint32_t register_iterations,
                                  uint32_t register_seed,
                                  const stream_workspace_t *stream,
                                  const float *source, float *destination) {
  if (core_work == CORE_WORK_REGISTER) {
    return online_merge_register_workload(register_iterations, register_seed);
  }
  if (core_work == CORE_WORK_STREAM) {
    online_merge_concurrency_stream(source, destination, stream->elements);
  }
  return 0u;
}

static int run_smu_sample(const char *scenario, int32_t repeat,
                          merge_buffers_t *merge,
                          const stream_workspace_t *stream,
                          float *source, float *destination,
                          uint32_t phase_bytes,
                          uint32_t register_iterations,
                          uint32_t register_expected,
                          core_work_t core_work,
                          concurrency_sample_t *sample) {
  *sample = (concurrency_sample_t){
      .smu_invocation = (int32_t)next_smu_invocation++,
      .merge_correctness = correctness_init(),
      .core_correctness = correctness_init(),
      .status = "pass",
  };
  clear_merge_output(merge);
  start_tcdm_counters();
  start_kernel();
  uint64_t total_start = benchmark_get_cycle64();
  smu_start(merge);
  uint64_t core_start = benchmark_get_cycle64();
  sample->core_checksum = execute_core_work(
      core_work, register_iterations,
      register_seed(repeat), stream, source,
      destination);
  uint64_t core_end = benchmark_get_cycle64();
  sample->status_after_core = smu_status();
  sample->status_reads = 1u;
  wait_result_t wait = wait_sparse(sample->status_after_core, sample);
  uint64_t total_end = benchmark_get_cycle64();
  stop_kernel();
  sample->total_cycles = total_end - total_start;
  sample->core_cycles = core_end - core_start;
  sample->status = wait_status(wait);
  stop_tcdm_counters(sample);
  smu_clear_done();

  if (wait == WAIT_OK) {
    sample->merge_correctness = check_merge_output(merge);
  }
  if (core_work == CORE_WORK_STREAM) {
    sample->core_correctness =
        check_stream_output(stream, source, destination);
  } else if (core_work == CORE_WORK_REGISTER) {
    sample->core_correctness.checked = 1u;
    if (sample->core_checksum != register_expected) {
      sample->core_correctness.passed = 0u;
      sample->core_correctness.mismatches = 1u;
      sample->core_correctness.expected_bits = register_expected;
      sample->core_correctness.actual_bits = sample->core_checksum;
    }
  }
  mark_sample_status(sample);
  print_sample(scenario, repeat, merge, stream, source, destination,
               phase_bytes, register_iterations, core_work, sample);
  return wait == WAIT_OK ? 0 : 1;
}

static void run_core_sample(const char *scenario, int32_t repeat,
                            const merge_buffers_t *merge,
                            const stream_workspace_t *stream,
                            float *source, float *destination,
                            uint32_t phase_bytes,
                            uint32_t register_iterations,
                            uint32_t register_expected,
                            core_work_t core_work) {
  concurrency_sample_t sample = {
      .smu_invocation = -1,
      .merge_correctness = correctness_init(),
      .core_correctness = correctness_init(),
      .status = "pass",
  };
  start_tcdm_counters();
  start_kernel();
  uint64_t start = benchmark_get_cycle64();
  sample.core_checksum = execute_core_work(
      core_work, register_iterations,
      register_seed(repeat), stream, source,
      destination);
  uint64_t end = benchmark_get_cycle64();
  stop_kernel();
  sample.total_cycles = end - start;
  sample.core_cycles = sample.total_cycles;
  stop_tcdm_counters(&sample);

  if (core_work == CORE_WORK_STREAM) {
    sample.core_correctness =
        check_stream_output(stream, source, destination);
  } else {
    sample.core_correctness.checked = 1u;
    if (sample.core_checksum != register_expected) {
      sample.core_correctness.passed = 0u;
      sample.core_correctness.mismatches = 1u;
      sample.core_correctness.expected_bits = register_expected;
      sample.core_correctness.actual_bits = sample.core_checksum;
    }
  }
  mark_sample_status(&sample);
  print_sample(scenario, repeat, merge, stream, source, destination,
               phase_bytes, register_iterations, core_work, &sample);
}

static uint64_t measure_register_cycles(uint32_t iterations,
                                        uint32_t seed,
                                        uint32_t *checksum) {
  uint64_t start = benchmark_get_cycle64();
  *checksum = online_merge_register_workload(iterations, seed);
  uint64_t end = benchmark_get_cycle64();
  return end - start;
}

static uint32_t calibrate_register_iterations(uint64_t target_cycles) {
  uint32_t iterations = 32u;
  uint32_t checksum = 0u;
  for (uint32_t step = 0; step < ONLINE_MERGE_REGISTER_CALIBRATION_STEPS;
       step++) {
    uint64_t measured = measure_register_cycles(
        iterations, 0x6d2b79f5u, &checksum);
    if (measured == 0u) {
      measured = 1u;
    }
    uint64_t scaled = ((uint64_t)iterations * target_cycles +
                       measured / 2u) /
                      measured;
    if (scaled == 0u) {
      scaled = 1u;
    }
    if (scaled > ONLINE_MERGE_REGISTER_MAX_ITERATIONS) {
      scaled = ONLINE_MERGE_REGISTER_MAX_ITERATIONS;
    }
    iterations = (uint32_t)scaled;
  }
  return iterations;
}

static void print_terminal(const merge_buffers_t *merge,
                           const stream_workspace_t *stream,
                           const char *status) {
  concurrency_sample_t sample = {
      .smu_invocation = -1,
      .merge_correctness = correctness_init(),
      .core_correctness = correctness_init(),
      .status = status,
  };
  print_sample("ALL", -1, merge, stream, 0, 0, UINT32_MAX, 0u,
               CORE_WORK_NONE, &sample);
}

int main(void) {
  if (snrt_cluster_core_idx() != 0) {
    snrt_cluster_hw_barrier();
    return 0;
  }

  merge_buffers_t merge = {
      .n = ONLINE_MERGE_CASE_N,
      .d = ONLINE_MERGE_CASE_D,
  };
  stream_workspace_t stream = {0};
  int allocation = allocate_buffers(&merge, &stream);
  if (allocation == 1) {
    print_terminal(&merge, &stream, "capacity_skip");
    PRINTF("online-softmax-merge-concurrency PASS status=capacity_skip\n");
    snrt_cluster_hw_barrier();
    return 0;
  }
  if (allocation != 0) {
    print_terminal(&merge, &stream, "tool_error");
    PRINTF("online-softmax-merge-concurrency FAILURE allocation\n");
    snrt_cluster_hw_barrier();
    return -1;
  }
  load_case(&merge);
  if (ONLINE_MERGE_CASE_UNSUPPORTED) {
    print_terminal(&merge, &stream, "unsupported");
    PRINTF("online-softmax-merge-concurrency PASS status=unsupported\n");
    snrt_cluster_hw_barrier();
    return 0;
  }

  float *phase_zero_source = stream_source(&merge, &stream, 0u);
  float *phase_zero_destination =
      stream_destination(&stream, phase_zero_source);
  initialize_stream(&stream, phase_zero_source, phase_zero_destination);

  concurrency_sample_t c0_warmup;
  if (run_smu_sample("C0_SMU", -1, &merge, &stream, 0, 0, UINT32_MAX,
                     0u, 0u, CORE_WORK_NONE, &c0_warmup)) {
    goto finish;
  }
  uint32_t register_iterations =
      calibrate_register_iterations(c0_warmup.total_cycles);
  uint32_t register_expected = online_merge_register_workload(
      register_iterations, register_seed(-1));
  uint32_t backoff_checksum;
  uint64_t backoff_cycles = measure_register_cycles(
      ONLINE_MERGE_POLL_BACKOFF_ITERATIONS, 1u, &backoff_checksum);
  print_meta(&merge, &stream, register_iterations,
             c0_warmup.total_cycles, backoff_cycles);

  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    concurrency_sample_t sample;
    if (run_smu_sample("C0_SMU", (int32_t)repeat, &merge, &stream, 0, 0,
                       UINT32_MAX, 0u, 0u, CORE_WORK_NONE, &sample)) {
      goto finish;
    }
  }

  run_core_sample("C0_REG", -1, &merge, &stream, 0, 0, UINT32_MAX,
                  register_iterations, register_expected,
                  CORE_WORK_REGISTER);
  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    uint32_t expected = online_merge_register_workload(
        register_iterations, register_seed((int32_t)repeat));
    run_core_sample("C0_REG", (int32_t)repeat, &merge, &stream, 0, 0,
                    UINT32_MAX, register_iterations, expected,
                    CORE_WORK_REGISTER);
  }

  initialize_stream(&stream, phase_zero_source, phase_zero_destination);
  run_core_sample("C0_STREAM", -1, &merge, &stream, phase_zero_source,
                  phase_zero_destination, 0u, 0u, 0u, CORE_WORK_STREAM);
  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    run_core_sample("C0_STREAM", (int32_t)repeat, &merge, &stream,
                    phase_zero_source, phase_zero_destination, 0u, 0u, 0u,
                    CORE_WORK_STREAM);
  }

  {
    uint32_t expected = online_merge_register_workload(
        register_iterations, register_seed(-1));
    concurrency_sample_t sample;
    if (run_smu_sample("C1", -1, &merge, &stream, 0, 0, UINT32_MAX,
                       register_iterations, expected,
                       CORE_WORK_REGISTER, &sample)) {
      goto finish;
    }
  }
  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    uint32_t expected = online_merge_register_workload(
        register_iterations, register_seed((int32_t)repeat));
    concurrency_sample_t sample;
    if (run_smu_sample("C1", (int32_t)repeat, &merge, &stream, 0, 0,
                       UINT32_MAX, register_iterations, expected,
                       CORE_WORK_REGISTER, &sample)) {
      goto finish;
    }
  }

  initialize_stream(&stream, phase_zero_source, phase_zero_destination);
  {
    concurrency_sample_t sample;
    if (run_smu_sample("C2", -1, &merge, &stream, phase_zero_source,
                       phase_zero_destination, 0u, 0u, 0u,
                       CORE_WORK_STREAM, &sample)) {
      goto finish;
    }
  }
  for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS; repeat++) {
    concurrency_sample_t sample;
    if (run_smu_sample("C2", (int32_t)repeat, &merge, &stream,
                       phase_zero_source, phase_zero_destination, 0u, 0u, 0u,
                       CORE_WORK_STREAM, &sample)) {
      goto finish;
    }
  }

  for (uint32_t phase = 0; phase < ONLINE_MERGE_PHASE_COUNT; phase++) {
    uint32_t phase_bytes = phase * ONLINE_MERGE_PHASE_STEP_BYTES;
    float *source = stream_source(&merge, &stream, phase_bytes);
    float *destination = stream_destination(&stream, source);
    uint32_t actual = relative_phase_bytes(source, merge.o_old);
    uint32_t destination_actual =
        relative_phase_bytes(destination, merge.o_old);
    if (actual != phase_bytes || destination_actual != phase_bytes) {
      print_terminal(&merge, &stream, "tool_error");
      all_passed = 0u;
      goto finish;
    }
    initialize_stream(&stream, source, destination);
    run_core_sample("C3_CORE", -1, &merge, &stream, source, destination,
                    phase_bytes, 0u, 0u, CORE_WORK_STREAM);
    for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS;
         repeat++) {
      run_core_sample("C3_CORE", (int32_t)repeat, &merge, &stream, source,
                      destination, phase_bytes, 0u, 0u, CORE_WORK_STREAM);
    }
    {
      concurrency_sample_t sample;
      if (run_smu_sample("C3", -1, &merge, &stream, source, destination,
                         phase_bytes, 0u, 0u, CORE_WORK_STREAM, &sample)) {
        goto finish;
      }
    }
    for (uint32_t repeat = 0; repeat < ONLINE_MERGE_CASE_REPEATS;
         repeat++) {
      concurrency_sample_t sample;
      if (run_smu_sample("C3", (int32_t)repeat, &merge, &stream, source,
                         destination, phase_bytes, 0u, 0u,
                         CORE_WORK_STREAM, &sample)) {
        goto finish;
      }
    }
  }

finish:
  PRINTF("online-softmax-merge-concurrency %s\n",
         all_passed ? "PASS" : "FAILURE");
  snrt_cluster_hw_barrier();
  return all_passed ? 0 : -1;
}
