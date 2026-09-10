// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0.
// SPDX-License-Identifier: Apache-2.0

// Minimal native online-attention integration.  Q/K/V are already resident
// before the core timer starts.  A four-key tile is reduced to (m, l, O), and
// only that state is carried into the next tile; no N x N probability matrix
// is allocated or materialized.

#include <benchmark.h>
#include <snrt.h>
#include <spatz_cluster_peripheral.h>
#include <stdint.h>
#include <stdio.h>

#include "phase5_case_data.h"
#include "rtl_reference.h"
#include "rvv_update.h"
#include <online_merge_mode.h>
#include <online_merge_omcfg.h>

#undef PRINTF
#define PRINTF(...) printf(__VA_ARGS__)

#ifndef PHASE5_IMPLEMENTATION
#define PHASE5_IMPLEMENTATION 0
#endif

#define PHASE5_SOFTWARE 0
#define PHASE5_SMU 1
#define PHASE5_ISA 2
#define PHASE5_MAX_POLLS 1000000u
#define PHASE5_STACK_LOG2 13
#define PHASE5_ALLOC_ALIGN 256u
#define PHASE5_OUTPUT_BUFFER_BYTES 16384u
#define PHASE5_OUTPUT_CHUNK_WORDS 256u

#define PHASE8C_CONFIG_MMIO 1
#define PHASE8C_CONFIG_OMCFG 2

#ifndef PHASE8C_CONFIG_PATH
#define PHASE8C_CONFIG_PATH PHASE8C_CONFIG_MMIO
#endif

// Keep both configuration mechanisms in an identical text image.  The two
// matched targets differ only in this initialized runtime selector word.
static volatile uint32_t phase8c_config_path = PHASE8C_CONFIG_PATH;

#ifndef PHASE5_DUMP_OUTPUT
#define PHASE5_DUMP_OUTPUT 0
#endif

const uint32_t snrt_stack_size = PHASE5_STACK_LOG2;
extern const uint32_t _snrt_team_size;
extern uintptr_t volatile tohost;
extern uintptr_t volatile fromhost;

static volatile uint64_t phase5_output_syscall[8];
static char phase5_output_buffer[PHASE5_OUTPUT_BUFFER_BYTES];

_Static_assert(PHASE5_IMPLEMENTATION == PHASE5_SOFTWARE ||
                   PHASE5_IMPLEMENTATION == PHASE5_SMU ||
                   PHASE5_IMPLEMENTATION == PHASE5_ISA,
               "invalid Phase 5 implementation selector");
_Static_assert(PHASE8C_CONFIG_PATH == PHASE8C_CONFIG_MMIO ||
                   PHASE8C_CONFIG_PATH == PHASE8C_CONFIG_OMCFG,
               "invalid Phase 8C configuration path selector");
_Static_assert(PHASE5_TILE_KEYS > 0u, "Phase 5 tile must be non-empty");
_Static_assert(PHASE5_CASE_N % PHASE5_TILE_KEYS == 0u,
               "Phase 5 anchor must have complete four-key tiles");

#ifndef SNRT_TCDM_SIZE
#define SNRT_TCDM_SIZE (128u * 1024u)
#endif

typedef struct {
  float *q;
  float *k;
  float *v;
  float *score_tile;
  float *m_old;
  float *l_old;
  float *o_old;
  float *m_tile;
  float *l_tile;
  float *o_tile;
  float *m_out;
  float *l_out;
  float *o_out;
  float *old_weight;
  float *tile_weight;
  float *output;
  uint32_t data_bytes;
  uint32_t allocation_bytes;
  uint32_t runtime_reserved_bytes;
  uint32_t memory_footprint_bytes;
} phase5_buffers_t;

typedef struct {
  uint64_t score_cycles;
  uint64_t local_state_cycles;
  uint64_t recurrence_cycles;
  uint64_t rvv_update_cycles;
  uint64_t merge_window_cycles;
  uint64_t merge_orchestration_cycles;
  uint64_t core_residual_cycles;
  uint64_t output_copy_cycles;
  uint64_t total_cycles;
  uint64_t workload_setup_cycles;
  uint64_t smu_setup_cycles;
  uint64_t smu_wait_cycles;
  int64_t smu_breakdown_delta_cycles;
  uint32_t smu_breakdown_exact;
  uint32_t software_recurrence_calls;
  uint32_t smu_commands;
  uint32_t smu_done;
  uint32_t smu_errors;
  uint32_t smu_timeouts;
  uint32_t smu_saw_busy;
  uint32_t output_nonfinite;
  uint32_t output_hash;
  float output_mae;
  float output_stable_relative_error;
  float output_cosine;
} phase5_cycles_t;

typedef enum {
  PHASE5_WAIT_OK = 0,
  PHASE5_WAIT_ERROR = 1,
  PHASE5_WAIT_TIMEOUT = 2,
} phase5_wait_t;

static volatile uint32_t *cluster_reg(uint32_t offset) {
  return (volatile uint32_t *)(snrt_cluster_memory().end + offset);
}

static float bits_float(uint32_t value) {
  union {
    uint32_t u;
    float f;
  } converted;
  converted.u = value;
  return converted.f;
}

static uint32_t float_bits(float value) {
  union {
    uint32_t u;
    float f;
  } converted;
  converted.f = value;
  return converted.u;
}

static uint64_t align_up_u64(uint64_t value, uint64_t alignment) {
  return (value + alignment - 1u) & ~(alignment - 1u);
}

static void *take_bytes(uint8_t **cursor, uint64_t bytes) {
  uintptr_t address = (uintptr_t)*cursor;
  address = (uintptr_t)align_up_u64(address, sizeof(uint64_t));
  void *result = (void *)address;
  *cursor = (uint8_t *)(address + bytes);
  return result;
}

static uint32_t tcdm_offset(const void *pointer) {
  return (uint32_t)((uintptr_t)pointer -
                    (uintptr_t)snrt_cluster_memory().start);
}

static int allocate_buffers(phase5_buffers_t *buffers, uint32_t n,
                            uint32_t d) {
  uint64_t nd = (uint64_t)n * d;
  uint64_t tile_values = (uint64_t)n * PHASE5_TILE_KEYS;
  uint64_t bytes = 0u;
#define P5_ADD(count, type)                                                   \
  bytes = align_up_u64(bytes, sizeof(uint64_t)) +                             \
          (uint64_t)(count) * sizeof(type)
#define P5_FLOAT(count) P5_ADD(count, float)
  P5_FLOAT(nd);
  P5_FLOAT(nd);
  P5_FLOAT(nd);
  P5_FLOAT(tile_values);
  P5_FLOAT(n);
  P5_FLOAT(n);
  P5_FLOAT(nd);
  P5_FLOAT(n);
  P5_FLOAT(n);
  P5_FLOAT(nd);
  P5_FLOAT(n);
  P5_FLOAT(n);
  P5_FLOAT(nd);
  P5_FLOAT(n);
  P5_FLOAT(n);
  P5_FLOAT(nd);
#undef P5_FLOAT
#undef P5_ADD

  uint64_t runtime_reserved = (uint64_t)_snrt_team_size +
                               (uint64_t)snrt_cluster_core_num() *
                                   ((1ull << PHASE5_STACK_LOG2) + 8ull);
  uint64_t allocation = align_up_u64(bytes, PHASE5_ALLOC_ALIGN);
  uint64_t footprint = allocation + runtime_reserved;
  uint64_t limit = ((uint64_t)SNRT_TCDM_SIZE * 8u) / 10u;
  if (bytes > UINT32_MAX || allocation > UINT32_MAX ||
      runtime_reserved > UINT32_MAX || footprint > UINT32_MAX ||
      footprint > limit) {
    return 1;
  }

  uint8_t *storage = (uint8_t *)snrt_l1alloc((uint32_t)allocation);
  if (storage == 0) {
    return -1;
  }
  uint8_t *cursor = storage;
#define P5_TAKE(field, count)                                                  \
  buffers->field = (float *)take_bytes(&cursor, (uint64_t)(count) * sizeof(float))
  P5_TAKE(q, nd);
  P5_TAKE(k, nd);
  P5_TAKE(v, nd);
  P5_TAKE(score_tile, tile_values);
  P5_TAKE(m_old, n);
  P5_TAKE(l_old, n);
  P5_TAKE(o_old, nd);
  P5_TAKE(m_tile, n);
  P5_TAKE(l_tile, n);
  P5_TAKE(o_tile, nd);
  P5_TAKE(m_out, n);
  P5_TAKE(l_out, n);
  P5_TAKE(o_out, nd);
  P5_TAKE(old_weight, n);
  P5_TAKE(tile_weight, n);
  P5_TAKE(output, nd);
#undef P5_TAKE
  buffers->data_bytes = (uint32_t)(cursor - storage);
  buffers->allocation_bytes = (uint32_t)allocation;
  buffers->runtime_reserved_bytes = (uint32_t)runtime_reserved;
  buffers->memory_footprint_bytes = (uint32_t)footprint;
  return 0;
}

static void load_case(phase5_buffers_t *buffers, uint32_t n, uint32_t d) {
  uint32_t count = n * d;
  for (uint32_t index = 0; index < count; index++) {
    buffers->q[index] = bits_float(phase5_q_bits[index]);
    buffers->k[index] = bits_float(phase5_k_bits[index]);
    buffers->v[index] = bits_float(phase5_v_bits[index]);
  }
}

static float score_scale(uint32_t d) {
  return d == 32u ? 0.1767766952966369f
                  : d == 64u ? 0.125f
                  : d == 128u ? 0.08838834764831843f : 1.0f;
}

static void compute_score_tile(const phase5_buffers_t *buffers,
                               uint32_t key_start, uint32_t n, uint32_t d) {
  float scale = score_scale(d);
  for (uint32_t query = 0; query < n; query++) {
    for (uint32_t offset = 0; offset < PHASE5_TILE_KEYS; offset++) {
      uint32_t key = key_start + offset;
      float sum = 0.0f;
      for (uint32_t inner = 0; inner < d; inner++) {
        sum += buffers->q[query * d + inner] *
               buffers->k[key * d + inner];
      }
      buffers->score_tile[query * PHASE5_TILE_KEYS + offset] = sum * scale;
    }
  }
}

static void build_local_state(const phase5_buffers_t *buffers,
                              uint32_t key_start, uint32_t n, uint32_t d) {
  for (uint32_t query = 0; query < n; query++) {
    const float *scores = &buffers->score_tile[query * PHASE5_TILE_KEYS];
    float maximum = scores[0];
    for (uint32_t offset = 1; offset < PHASE5_TILE_KEYS; offset++) {
      if (scores[offset] > maximum) {
        maximum = scores[offset];
      }
    }

    float sum = 0.0f;
    uint32_t output_base = query * d;
    for (uint32_t offset = 0; offset < PHASE5_TILE_KEYS; offset++) {
      float weight = online_merge_exp_approx_f32(scores[offset] - maximum);
      sum += weight;
      uint32_t value_base = (key_start + offset) * d;
      for (uint32_t column = 0; column < d; column++) {
        buffers->o_tile[output_base + column] +=
            weight * buffers->v[value_base + column];
      }
    }
    buffers->m_tile[query] = maximum;
    buffers->l_tile[query] = sum;
    float inverse = online_merge_recip_approx_f32(sum);
    for (uint32_t column = 0; column < d; column++) {
      buffers->o_tile[output_base + column] *= inverse;
    }
  }
}

static void clear_tile_output(const phase5_buffers_t *buffers, uint32_t n,
                              uint32_t d) {
  for (uint32_t index = 0; index < n * d; index++) {
    buffers->o_tile[index] = 0.0f;
  }
}

static void copy_initial_state(phase5_buffers_t *buffers, uint32_t n,
                               uint32_t d) {
  for (uint32_t row = 0; row < n; row++) {
    buffers->m_old[row] = buffers->m_tile[row];
    buffers->l_old[row] = buffers->l_tile[row];
  }
  for (uint32_t index = 0; index < n * d; index++) {
    buffers->o_old[index] = buffers->o_tile[index];
  }
}

static void rvv_output_update(const phase5_buffers_t *buffers, uint32_t n,
                              uint32_t d) {
  for (uint32_t row = 0; row < n; row++) {
    uint32_t base = row * d;
    online_merge_rvv_update(
        &buffers->o_old[base], &buffers->o_tile[base],
        &buffers->o_out[base], d, buffers->old_weight[row],
        buffers->tile_weight[row]);
  }
}

static void swap_running_state(phase5_buffers_t *buffers) {
  float *pointer = buffers->m_old;
  buffers->m_old = buffers->m_out;
  buffers->m_out = pointer;
  pointer = buffers->l_old;
  buffers->l_old = buffers->l_out;
  buffers->l_out = pointer;
  pointer = buffers->o_old;
  buffers->o_old = buffers->o_out;
  buffers->o_out = pointer;
}

static void smu_clear_done(void) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT;
}

static inline void phase8c_cfg_write(uint32_t cfg_id, uint32_t mmio_offset,
                                     uint32_t value) {
  if (phase8c_config_path == PHASE8C_CONFIG_OMCFG) {
    omerge_cfg_write(cfg_id, value);
  } else {
    *cluster_reg(mmio_offset) = value;
  }
}

static inline void phase8c_cfg_init(void) {
  if (phase8c_config_path == PHASE8C_CONFIG_OMCFG) {
    omerge_cfg_write(OMERGE_CFG_CTRL, OMERGE_CFG_CTRL_INIT);
  } else {
    smu_clear_done();
  }
}

static const char *phase8c_config_path_name(void) {
  return phase8c_config_path == PHASE8C_CONFIG_OMCFG ? "omcfg" : "mmio";
}

static void smu_start(const phase5_buffers_t *buffers, uint32_t n,
                      uint32_t d) {
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
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET) = n;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_D_REG_OFFSET) = d;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STRIDE_REG_OFFSET) =
      d * sizeof(float);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_MODE_REG_OFFSET) =
      (uint32_t)ONLINE_MERGE_MODE_MIXED_SCALAR;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_OLD_REG_OFFSET) =
      tcdm_offset(buffers->old_weight);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_TILE_REG_OFFSET) =
      tcdm_offset(buffers->tile_weight);
  smu_clear_done();
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_START_BIT;
}

// Configure the physical A/B m/l state buffers once for the instruction path.
// The software O pointer remains outside the adapter and is updated by the
// existing RVV routine after every successful completion.
static void smu_isa_setup(const phase5_buffers_t *buffers, uint32_t n,
                          uint32_t d) {
  (void)d;
  phase8c_cfg_write(
      OMERGE_CFG_STATE_A_M_ADDR,
      SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_A_M_REG_OFFSET,
      tcdm_offset(buffers->m_old));
  phase8c_cfg_write(
      OMERGE_CFG_STATE_A_L_ADDR,
      SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_A_L_REG_OFFSET,
      tcdm_offset(buffers->l_old));
  phase8c_cfg_write(
      OMERGE_CFG_STATE_B_M_ADDR,
      SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_B_M_REG_OFFSET,
      tcdm_offset(buffers->m_out));
  phase8c_cfg_write(
      OMERGE_CFG_STATE_B_L_ADDR,
      SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_B_L_REG_OFFSET,
      tcdm_offset(buffers->l_out));
  phase8c_cfg_write(OMERGE_CFG_TILE_M_ADDR,
                    SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_TILE_REG_OFFSET,
                    tcdm_offset(buffers->m_tile));
  phase8c_cfg_write(OMERGE_CFG_TILE_L_ADDR,
                    SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET,
                    tcdm_offset(buffers->l_tile));
  phase8c_cfg_write(
      OMERGE_CFG_WEIGHT_OLD_ADDR,
      SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_OLD_REG_OFFSET,
      tcdm_offset(buffers->old_weight));
  phase8c_cfg_write(
      OMERGE_CFG_WEIGHT_TILE_ADDR,
      SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_TILE_REG_OFFSET,
      tcdm_offset(buffers->tile_weight));
  phase8c_cfg_write(OMERGE_CFG_N,
                    SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET, n);
  phase8c_cfg_init();
}

static void print_phase8c_config_state(uint32_t workload_d) {
  PRINTF("PHASE8C_CONFIG_STATE {\"path\":\"%s\","
         "\"A_M\":%u,\"A_L\":%u,\"B_M\":%u,\"B_L\":%u,"
         "\"TILE_M\":%u,\"TILE_L\":%u,\"WEIGHT_OLD\":%u,"
         "\"WEIGHT_TILE\":%u,\"N\":%u,\"workload_D\":%u}\n",
         phase8c_config_path_name(),
         *cluster_reg(
             SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_A_M_REG_OFFSET),
         *cluster_reg(
             SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_A_L_REG_OFFSET),
         *cluster_reg(
             SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_B_M_REG_OFFSET),
         *cluster_reg(
             SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_B_L_REG_OFFSET),
         *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_TILE_REG_OFFSET),
         *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET),
         *cluster_reg(
             SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_OLD_REG_OFFSET),
         *cluster_reg(
             SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_TILE_REG_OFFSET),
         *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET), workload_d);
}

static inline uint32_t omerge(void) {
  uint32_t status;
  __asm__ volatile(
      ".insn r 0x5b, 0, 3, %0, x0, x0"
      : "=r"(status)
      :
      : "memory");
  return status;
}

static phase5_wait_t smu_wait(int *saw_busy) {
  *saw_busy = 0;
  for (uint32_t poll = 0; poll < PHASE5_MAX_POLLS; poll++) {
    uint32_t status =
        *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_REG_OFFSET);
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_BUSY_BIT) & 1u) {
      *saw_busy = 1;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_ERROR_BIT) & 1u) {
      return PHASE5_WAIT_ERROR;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_DONE_BIT) & 1u) {
      return PHASE5_WAIT_OK;
    }
  }
  return PHASE5_WAIT_TIMEOUT;
}

static uint32_t count_nonfinite(const float *values, uint32_t count) {
  uint32_t result = 0u;
  for (uint32_t index = 0; index < count; index++) {
    uint32_t exponent = (float_bits(values[index]) >> 23) & 0xffu;
    result += exponent == 0xffu;
  }
  return result;
}

static float absf(float value) { return value < 0.0f ? -value : value; }

static float sqrt_no_div(float value) {
  if (value == 0.0f) {
    return 0.0f;
  }
  uint32_t bits = float_bits(value);
  float estimate = bits_float((bits >> 1) + 0x1fc00000u);
  for (uint32_t iteration = 0; iteration < 3u; iteration++) {
    estimate = 0.5f *
               (estimate + value * online_merge_recip_approx_f32(estimate));
  }
  return estimate;
}

static void output_metrics(const float *actual, uint32_t count,
                           float *mae, float *stable_relative_error,
                           float *cosine, uint32_t *hash) {
  float sum_abs = 0.0f;
  float sum_ref_abs = 0.0f;
  float dot = 0.0f;
  float actual_sq = 0.0f;
  float reference_sq = 0.0f;
  uint32_t digest = 2166136261u;
  for (uint32_t index = 0; index < count; index++) {
    float reference = bits_float(phase5_reference_output_bits[index]);
    float value = actual[index];
    float difference = absf(value - reference);
    sum_abs += difference;
    sum_ref_abs += absf(reference);
    dot += value * reference;
    actual_sq += value * value;
    reference_sq += reference * reference;
    digest ^= float_bits(value);
    digest *= 16777619u;
  }
  *mae = sum_abs * online_merge_recip_approx_f32((float)count);
  float denominator = sum_ref_abs > 1.0e-12f ? sum_ref_abs : 1.0e-12f;
  *stable_relative_error =
      sum_abs * online_merge_recip_approx_f32(denominator);
  if (actual_sq == 0.0f || reference_sq == 0.0f) {
    *cosine = actual_sq == reference_sq ? 1.0f : 0.0f;
  } else {
    *cosine = dot * online_merge_recip_approx_f32(
                        sqrt_no_div(actual_sq) * sqrt_no_div(reference_sq));
  }
  *hash = digest;
}

static int run_attention(phase5_buffers_t *buffers, phase5_cycles_t *cycles) {
  const uint32_t n = PHASE5_CASE_N;
  const uint32_t d = PHASE5_CASE_D;
  const uint32_t tile_count = n / PHASE5_TILE_KEYS;
  int failed = 0;

#if PHASE5_IMPLEMENTATION == PHASE5_ISA
  uint64_t setup_start = benchmark_get_cycle64();
  smu_isa_setup(buffers, n, d);
  cycles->workload_setup_cycles = benchmark_get_cycle64() - setup_start;
  print_phase8c_config_state(d);
#endif

  uint64_t core_start = benchmark_get_cycle64();
  for (uint32_t tile = 0; tile < tile_count; tile++) {
    uint32_t key_start = tile * PHASE5_TILE_KEYS;

    uint64_t stage_start = benchmark_get_cycle64();
    compute_score_tile(buffers, key_start, n, d);
    cycles->score_cycles += benchmark_get_cycle64() - stage_start;

    stage_start = benchmark_get_cycle64();
    clear_tile_output(buffers, n, d);
    build_local_state(buffers, key_start, n, d);
    cycles->local_state_cycles += benchmark_get_cycle64() - stage_start;

    if (tile == 0u) {
      copy_initial_state(buffers, n, d);
      continue;
    }

    uint64_t merge_start = benchmark_get_cycle64();
    uint64_t recurrence_cycles = 0u;
#if PHASE5_IMPLEMENTATION == PHASE5_SOFTWARE
    stage_start = benchmark_get_cycle64();
    online_merge_b2_r_scalar(
        buffers->m_old, buffers->l_old, buffers->m_tile, buffers->l_tile,
        buffers->m_out, buffers->l_out, buffers->old_weight,
        buffers->tile_weight, n);
    recurrence_cycles = benchmark_get_cycle64() - stage_start;
    cycles->recurrence_cycles += recurrence_cycles;
    cycles->software_recurrence_calls++;
#elif PHASE5_IMPLEMENTATION == PHASE5_SMU
    uint64_t recurrence_start = benchmark_get_cycle64();
    uint64_t setup_start = recurrence_start;
    smu_start(buffers, n, d);
    uint64_t setup_end = benchmark_get_cycle64();
    int saw_busy = 0;
    phase5_wait_t wait_result = smu_wait(&saw_busy);
    uint64_t recurrence_end = benchmark_get_cycle64();
    recurrence_cycles = recurrence_end - recurrence_start;
    cycles->recurrence_cycles += recurrence_cycles;
    cycles->smu_setup_cycles += setup_end - setup_start;
    cycles->smu_wait_cycles += recurrence_end - setup_end;
    cycles->smu_commands++;
    cycles->smu_saw_busy |= (uint32_t)saw_busy;
    if (wait_result == PHASE5_WAIT_OK) {
      cycles->smu_done++;
    } else if (wait_result == PHASE5_WAIT_ERROR) {
      cycles->smu_errors++;
      failed = 1;
    } else {
      cycles->smu_timeouts++;
      failed = 1;
    }
    if (failed) {
      break;
    }
#else
    uint64_t recurrence_start = benchmark_get_cycle64();
    uint32_t status = omerge();
    cycles->smu_commands++;
    if (status == 0u) {
      cycles->smu_done++;
    } else {
      cycles->smu_errors++;
      failed = 1;
    }
    // Consume the completion status before sampling the end of the
    // instruction window.  This keeps the ISA timing bucket inclusive of
    // issue, SMU execution, response commit, and status consumption.
    uint64_t recurrence_end = benchmark_get_cycle64();
    recurrence_cycles = recurrence_end - recurrence_start;
    cycles->recurrence_cycles += recurrence_cycles;
    if (failed) {
      break;
    }
#endif

    stage_start = benchmark_get_cycle64();
    rvv_output_update(buffers, n, d);
    uint64_t rvv_cycles = benchmark_get_cycle64() - stage_start;
    cycles->rvv_update_cycles += rvv_cycles;

    swap_running_state(buffers);
    uint64_t merge_window = benchmark_get_cycle64() - merge_start;
    cycles->merge_window_cycles += merge_window;
    uint64_t accounted = recurrence_cycles + rvv_cycles;
    if (merge_window >= accounted) {
      cycles->merge_orchestration_cycles += merge_window - accounted;
    }
  }

  if (!failed) {
    uint64_t stage_start = benchmark_get_cycle64();
    for (uint32_t index = 0; index < n * d; index++) {
      buffers->output[index] = buffers->o_old[index];
    }
    cycles->output_copy_cycles = benchmark_get_cycle64() - stage_start;
  }
  cycles->total_cycles = benchmark_get_cycle64() - core_start;

  // Validation and digest work are deliberately outside the native-core
  // timer.  The timed final stage is only the output copy above; diagnostics
  // must not be charged to orchestration in either matched path.
  if (!failed) {
    cycles->output_nonfinite = count_nonfinite(buffers->output, n * d);
    failed = cycles->output_nonfinite != 0u;
    output_metrics(buffers->output, n * d, &cycles->output_mae,
                   &cycles->output_stable_relative_error,
                   &cycles->output_cosine, &cycles->output_hash);
  }

  // The merge window is the exact outer window around recurrence, the common
  // RVV update, and swap.  Everything else left in the core interval is a
  // separate core residual; it must not inflate merge_total.
  uint64_t smu_breakdown_sum = cycles->smu_setup_cycles +
                               cycles->smu_wait_cycles;
#if PHASE5_IMPLEMENTATION == PHASE5_SMU
  if (cycles->recurrence_cycles >= smu_breakdown_sum) {
    cycles->smu_breakdown_delta_cycles =
        (int64_t)(cycles->recurrence_cycles - smu_breakdown_sum);
  } else {
    cycles->smu_breakdown_delta_cycles =
        -(int64_t)(smu_breakdown_sum - cycles->recurrence_cycles);
  }
  cycles->smu_breakdown_exact =
      cycles->smu_breakdown_delta_cycles == 0 ? 1u : 0u;
  if (!cycles->smu_breakdown_exact) {
    failed = 1;
  }
#else
  // There is no SMU window on the software control; keep the optional SMU
  // breakdown fields neutral so the collector can apply the invariant only
  // to the proposed path.
  cycles->smu_breakdown_delta_cycles = 0;
  cycles->smu_breakdown_exact = 1u;
#endif

  // Timer reads, first-tile state initialization, loop gaps, and any small
  // non-merge work are assigned to a core-wide residual bucket.
  uint64_t subtotal = cycles->score_cycles + cycles->local_state_cycles +
                      cycles->merge_window_cycles + cycles->output_copy_cycles;
  if (cycles->total_cycles > subtotal) {
    cycles->core_residual_cycles = cycles->total_cycles - subtotal;
  }
  return failed ? -1 : 0;
}

static void print_cycles(const phase5_cycles_t *cycles) {
  PRINTF("\"cycles\":{");
  PRINTF("\"score_compute\":%llu,",
         (unsigned long long)cycles->score_cycles);
  PRINTF("\"tile_local_state\":%llu,",
         (unsigned long long)cycles->local_state_cycles);
#if PHASE5_IMPLEMENTATION == PHASE5_SOFTWARE
  PRINTF("\"software_recurrence\":%llu,",
         (unsigned long long)cycles->recurrence_cycles);
#else
  PRINTF("\"smu_recurrence\":%llu,",
         (unsigned long long)cycles->recurrence_cycles);
#endif
  PRINTF("\"rvv_output_update\":%llu,",
         (unsigned long long)cycles->rvv_update_cycles);
  PRINTF("\"merge_window\":%llu,\"merge_orchestration\":%llu,",
         (unsigned long long)cycles->merge_window_cycles,
         (unsigned long long)cycles->merge_orchestration_cycles);
  PRINTF("\"core_residual\":%llu,\"output_copy\":%llu,"
         "\"merge_total\":%llu,\"total\":%llu,",
         (unsigned long long)cycles->core_residual_cycles,
         (unsigned long long)cycles->output_copy_cycles,
         (unsigned long long)cycles->merge_window_cycles,
         (unsigned long long)cycles->total_cycles);
  PRINTF("\"workload_setup\":%llu,\"smu_setup\":%llu,\"smu_wait\":%llu,"
         "\"smu_breakdown_sum\":%llu,\"smu_breakdown_delta\":%lld,"
         "\"smu_breakdown_exact\":%u,",
         (unsigned long long)cycles->workload_setup_cycles,
         (unsigned long long)cycles->smu_setup_cycles,
         (unsigned long long)cycles->smu_wait_cycles,
         (unsigned long long)(cycles->smu_setup_cycles +
                              cycles->smu_wait_cycles),
         (long long)cycles->smu_breakdown_delta_cycles,
         cycles->smu_breakdown_exact);
  PRINTF("\"software_recurrence_calls\":%u,\"smu_commands\":%u}",
         cycles->software_recurrence_calls, cycles->smu_commands);
}

static void print_output(const phase5_buffers_t *buffers, uint32_t n,
                         uint32_t d) {
  const uint32_t count = n * d;
  // Keep each host write small enough for the simulator transport.  The
  // diagnostic is outside the timed core; chunking does not change the
  // archived bit sequence and avoids a large single syscall for larger D.
#define P5_APPEND_LITERAL(value)                                              \
  do {                                                                         \
    const char *literal = (value);                                            \
    while (*literal != '\0') {                                                \
      phase5_output_buffer[length++] = *literal++;                             \
    }                                                                          \
  } while (0)
#define P5_APPEND_U32(value)                                                   \
  do {                                                                         \
    uint32_t number = (value);                                                 \
    char reversed[10];                                                         \
    uint32_t digits = 0u;                                                      \
    do {                                                                       \
      reversed[digits++] = (char)('0' + number % 10u);                         \
      number /= 10u;                                                           \
    } while (number != 0u);                                                    \
    while (digits != 0u) {                                                     \
      phase5_output_buffer[length++] = reversed[--digits];                     \
    }                                                                          \
  } while (0)
  for (uint32_t offset = 0u; offset < count;
       offset += PHASE5_OUTPUT_CHUNK_WORDS) {
    uint32_t length = 0u;
    uint32_t chunk_count = count - offset;
    if (chunk_count > PHASE5_OUTPUT_CHUNK_WORDS) {
      chunk_count = PHASE5_OUTPUT_CHUNK_WORDS;
    }
    P5_APPEND_LITERAL("PHASE5_OUTPUT_CHUNK {\"n\":");
    P5_APPEND_U32(n);
    P5_APPEND_LITERAL(",\"d\":");
    P5_APPEND_U32(d);
    P5_APPEND_LITERAL(",\"offset\":");
    P5_APPEND_U32(offset);
    P5_APPEND_LITERAL(",\"bits\":[");
    for (uint32_t index = 0u; index < chunk_count; index++) {
      if (index != 0u) {
        phase5_output_buffer[length++] = ',';
      }
      P5_APPEND_U32(float_bits(buffers->output[offset + index]));
    }
    P5_APPEND_LITERAL("]}\n");
    phase5_output_syscall[0] = 64u;  // sys_write
    phase5_output_syscall[1] = 1u;   // stdout
    phase5_output_syscall[2] = (uintptr_t)phase5_output_buffer;
    phase5_output_syscall[3] = length;
    tohost = (uintptr_t)phase5_output_syscall;
    while (fromhost == 0u) {
    }
    fromhost = 0u;
  }
#undef P5_APPEND_U32
#undef P5_APPEND_LITERAL
}

int main(void) {
  if (snrt_cluster_core_idx() != 0) {
    snrt_cluster_hw_barrier();
    return 0;
  }

  phase5_buffers_t buffers = {0};
  int allocation = allocate_buffers(&buffers, PHASE5_CASE_N, PHASE5_CASE_D);
  if (allocation != 0) {
    PRINTF("PHASE5_RESULT {\"status\":\"allocation_error\","
           "\"implementation\":\"%s\",\"n\":%u,\"d\":%u}\n",
#if PHASE5_IMPLEMENTATION == PHASE5_SOFTWARE
           "software",
#elif PHASE5_IMPLEMENTATION == PHASE5_ISA
           "omerge",
#else
           "smu",
#endif
           PHASE5_CASE_N, PHASE5_CASE_D);
    snrt_cluster_hw_barrier();
    return -1;
  }

  load_case(&buffers, PHASE5_CASE_N, PHASE5_CASE_D);
  phase5_cycles_t cycles = {0};
  int result = run_attention(&buffers, &cycles);

#if PHASE5_IMPLEMENTATION == PHASE5_SOFTWARE
  const char *implementation = "software";
#elif PHASE5_IMPLEMENTATION == PHASE5_ISA
  const char *implementation = "omerge";
#else
  const char *implementation = "smu";
#endif
  const char *status = result == 0 ? "pass" :
      (cycles.smu_errors != 0u ? "smu_error" :
       cycles.smu_timeouts != 0u ? "timeout" : "correctness_fail");
  PRINTF("PHASE5_RESULT {\"status\":\"%s\",\"implementation\":\"%s\","
         "\"n\":%u,\"d\":%u,\"seed\":%u,\"tile_keys\":%u,"
         "\"tile_count\":%u,\"merge_count\":%u,",
         status, implementation, PHASE5_CASE_N, PHASE5_CASE_D,
         PHASE5_CASE_SEED, PHASE5_TILE_KEYS,
         PHASE5_CASE_N / PHASE5_TILE_KEYS,
         PHASE5_CASE_N / PHASE5_TILE_KEYS - 1u);
  PRINTF("\"smu\":{\"commands\":%u,\"done\":%u,\"errors\":%u,"
         "\"timeouts\":%u,\"saw_busy\":%u},",
         cycles.smu_commands, cycles.smu_done, cycles.smu_errors,
         cycles.smu_timeouts, cycles.smu_saw_busy);
#if PHASE5_IMPLEMENTATION == PHASE5_ISA
  PRINTF("\"configuration\":{\"path\":\"%s\",\"field_writes\":9,"
         "\"mmio_writes\":%u,\"omcfg_instructions\":%u,"
         "\"init_count\":1},",
         phase8c_config_path_name(),
         phase8c_config_path == PHASE8C_CONFIG_MMIO ? 9u : 0u,
         phase8c_config_path == PHASE8C_CONFIG_OMCFG ? 10u : 0u);
#endif
  print_cycles(&cycles);
  PRINTF(",\"output_nonfinite\":%u,\"output_hash\":%u,"
         "\"output_metrics\":{\"mae_bits\":%u,"
         "\"stable_relative_error_bits\":%u,"
         "\"cosine_similarity_bits\":%u},\"tcdm\":{\"data_bytes\":%u,"
         "\"allocation_bytes\":%u,\"runtime_reserved_bytes\":%u,"
         "\"memory_footprint_bytes\":%u,\"capacity_bytes\":%u}}\n",
         cycles.output_nonfinite, cycles.output_hash,
         float_bits(cycles.output_mae),
         float_bits(cycles.output_stable_relative_error),
         float_bits(cycles.output_cosine), buffers.data_bytes,
         buffers.allocation_bytes, buffers.runtime_reserved_bytes,
         buffers.memory_footprint_bytes, (uint32_t)SNRT_TCDM_SIZE);
#if PHASE5_DUMP_OUTPUT
  if (result == 0) {
    print_output(&buffers, PHASE5_CASE_N, PHASE5_CASE_D);
  }
#endif
  PRINTF("native-online-attention %s\n", result == 0 ? "PASS" : "FAILURE");
  snrt_cluster_hw_barrier();
  return result;
}
