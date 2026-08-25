// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0.
// SPDX-License-Identifier: Apache-2.0

// Minimal Phase 4 device path. This benchmark intentionally keeps the INT8
// kernels scalar; the experiment is an integration path, not a GEMM
// accelerator implementation.

#include <benchmark.h>
#include <math.h>
#include <snrt.h>
#include <spatz_cluster_peripheral.h>
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>

#include "phase4_case_data.h"
#include "rvv_update.h"
#include <online_merge_mode.h>

#undef PRINTF
#define PRINTF(...) printf(__VA_ARGS__)

#ifndef SNRT_TCDM_SIZE
#define SNRT_TCDM_SIZE (128u * 1024u)
#endif

enum {
  PHASE4_STACK_LOG2 = 13,
  PHASE4_ALLOC_ALIGN = 256,
  PHASE4_MAX_POLLS = 1000000,
};

const uint32_t snrt_stack_size = PHASE4_STACK_LOG2;
extern const uint32_t _snrt_team_size;

typedef struct {
  float *x;
  int8_t *xq;
  int32_t *aq;
  int32_t *ak;
  int32_t *av;
  int8_t *qq;
  int8_t *kq;
  int8_t *vq;
  int32_t *score_i32;
  float *score;
  float *m_old;
  float *l_old;
  float *p_old;
  float *m_tile;
  float *l_tile;
  float *p_tile;
  float *m_out;
  float *l_out;
  float *p_out;
  float *old_weight;
  float *tile_weight;
  float *pv;
  float *output;
  uint32_t data_bytes;
  uint32_t allocation_bytes;
  uint32_t runtime_reserved_bytes;
  uint32_t memory_footprint_bytes;
} phase4_buffers_t;

typedef struct {
  float mae;
  float stable_relative_error;
  float cosine_similarity;
} phase4_metrics_t;

typedef enum {
  PHASE4_WAIT_OK = 0,
  PHASE4_WAIT_ERROR = 1,
  PHASE4_WAIT_TIMEOUT = 2,
} phase4_wait_t;

typedef struct {
  uint64_t x_maxabs_scale;
  uint64_t x_quant;
  uint64_t q_linear;
  uint64_t k_linear;
  uint64_t v_linear;
  uint64_t q_requant;
  uint64_t k_requant;
  uint64_t v_requant;
  uint64_t qkt;
  uint64_t score_rescale;
  uint64_t smu_scalar_window;
  uint64_t smu_probability_update;
  uint64_t smu_setup_orchestration;
  uint64_t smu_total;
  uint64_t pv;
  uint64_t output_rescale;
  uint64_t total;
} phase4_cycles_t;

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

static float absf(float value) { return value < 0.0f ? -value : value; }

// The current Spatz FPU configuration used by the available simulator does
// not implement fdiv.s/fdiv.d. Keep dynamic scale propagation in software
// with an integer-seed Newton reciprocal instead of emitting a divide.
static float reciprocal_f32(float value) {
  union {
    uint32_t u;
    float f;
  } converted;
  converted.f = value;
  if (value == 0.0f) {
    return 0.0f;
  }
  uint32_t exponent = (converted.u >> 23) & 0xffu;
  uint32_t mantissa = (converted.u & 0x7fffffu) | 0x3f800000u;
  float normalized = bits_float(mantissa);
  float estimate = 1.5f - 0.5f * normalized;
  estimate = estimate * (2.0f - normalized * estimate);
  estimate = estimate * (2.0f - normalized * estimate);
  estimate = estimate * (2.0f - normalized * estimate);
  int32_t exponent_unbiased = (int32_t)exponent - 127;
  uint32_t reciprocal_exponent =
      (uint32_t)(127 - exponent_unbiased) << 23;
  return estimate * bits_float(reciprocal_exponent);
}

static float sqrt_f32_no_div(float value) {
  if (value == 0.0f) {
    return 0.0f;
  }
  union {
    uint32_t u;
    float f;
  } converted;
  converted.f = value;
  float estimate = bits_float((converted.u >> 1) + 0x1fc00000u);
  estimate = 0.5f * (estimate + value * reciprocal_f32(estimate));
  estimate = 0.5f * (estimate + value * reciprocal_f32(estimate));
  estimate = 0.5f * (estimate + value * reciprocal_f32(estimate));
  return estimate;
}

static uint64_t align_up_u64(uint64_t value, uint64_t alignment) {
  return (value + alignment - 1u) & ~(alignment - 1u);
}

static void *take_bytes(uint8_t **cursor, uint32_t bytes) {
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

static int32_t round_even_f32(float value) {
  float magnitude = value < 0.0f ? -value : value;
  int32_t base = (int32_t)magnitude;
  float fraction = magnitude - (float)base;
  if (fraction > 0.5f ||
      (fraction == 0.5f && ((uint32_t)base & 1u) != 0u)) {
    base++;
  }
  return value < 0.0f ? -base : base;
}

static int32_t max_abs_i32(const int32_t *values, uint32_t count) {
  uint32_t maximum = 0u;
  for (uint32_t index = 0; index < count; index++) {
    int64_t value = values[index];
    uint32_t magnitude = (uint32_t)(value < 0 ? -value : value);
    if (magnitude > maximum) {
      maximum = magnitude;
    }
  }
  return (int32_t)maximum;
}

static float max_abs_f32(const float *values, uint32_t count) {
  float maximum = 0.0f;
  for (uint32_t index = 0; index < count; index++) {
    float magnitude = absf(values[index]);
    if (magnitude > maximum) {
      maximum = magnitude;
    }
  }
  return maximum;
}

static int8_t clamp_i8(int32_t value) {
  if (value > 127) {
    return 127;
  }
  if (value < -127) {
    return -127;
  }
  return (int8_t)value;
}

static int allocate_buffers(phase4_buffers_t *buffers, uint32_t n,
                            uint32_t d) {
  uint64_t nd = (uint64_t)n * d;
  uint64_t nn = (uint64_t)n * n;
  uint64_t bytes = 0u;
  // Every old/tile/out probability row is separately 8-byte aligned. No
  // vector buffer partially overlaps another buffer.
#define P4_BYTES(count, type) ((uint64_t)(count) * sizeof(type))
  bytes += P4_BYTES(nd, float);
  bytes += P4_BYTES(nd, int8_t);
  bytes += P4_BYTES(nd, int32_t) * 3u;
  bytes += P4_BYTES(nd, int8_t) * 3u;
  bytes += P4_BYTES(nn, int32_t);
  bytes += P4_BYTES(nn, float);
  bytes += P4_BYTES(n, float) * 6u;
  bytes += P4_BYTES(nn, float) * 3u;
  bytes += P4_BYTES(n, float) * 2u;
  bytes += P4_BYTES(nd, float) * 2u;
#undef P4_BYTES

  uint64_t runtime_reserved = (uint64_t)_snrt_team_size +
                               (uint64_t)snrt_cluster_core_num() *
                                   ((1ull << PHASE4_STACK_LOG2) + 8ull);
  uint64_t allocation = align_up_u64(bytes, PHASE4_ALLOC_ALIGN);
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
#define P4_BYTES(count, type) ((uint64_t)(count) * sizeof(type))
#define P4_TAKE(field, type, count) \
  buffers->field = (type *)take_bytes(&cursor, (uint32_t)P4_BYTES(count, type))
  P4_TAKE(x, float, nd);
  P4_TAKE(xq, int8_t, nd);
  P4_TAKE(aq, int32_t, nd);
  P4_TAKE(ak, int32_t, nd);
  P4_TAKE(av, int32_t, nd);
  P4_TAKE(qq, int8_t, nd);
  P4_TAKE(kq, int8_t, nd);
  P4_TAKE(vq, int8_t, nd);
  P4_TAKE(score_i32, int32_t, nn);
  P4_TAKE(score, float, nn);
  P4_TAKE(m_old, float, n);
  P4_TAKE(l_old, float, n);
  P4_TAKE(p_old, float, nn);
  P4_TAKE(m_tile, float, n);
  P4_TAKE(l_tile, float, n);
  P4_TAKE(p_tile, float, nn);
  P4_TAKE(m_out, float, n);
  P4_TAKE(l_out, float, n);
  P4_TAKE(p_out, float, nn);
  P4_TAKE(old_weight, float, n);
  P4_TAKE(tile_weight, float, n);
  P4_TAKE(pv, float, nd);
  P4_TAKE(output, float, nd);
#undef P4_TAKE
#undef P4_BYTES
  buffers->data_bytes = (uint32_t)(cursor - storage);
  buffers->allocation_bytes = (uint32_t)allocation;
  buffers->runtime_reserved_bytes = (uint32_t)runtime_reserved;
  buffers->memory_footprint_bytes = (uint32_t)footprint;
  return 0;
}

static void load_input(phase4_buffers_t *buffers, uint32_t count) {
  for (uint32_t index = 0; index < count; index++) {
    buffers->x[index] = bits_float(phase4_x_bits[index]);
  }
}

static void quantize_input(const float *input, int8_t *output, uint32_t count,
                           float scale) {
  float inverse = reciprocal_f32(scale);
  for (uint32_t index = 0; index < count; index++) {
    output[index] = clamp_i8(round_even_f32(input[index] * inverse));
  }
}

static void linear_i8(const int8_t *input, const int8_t *weight,
                      int32_t *output, uint32_t n, uint32_t d) {
  for (uint32_t row = 0; row < n; row++) {
    for (uint32_t col = 0; col < d; col++) {
      int32_t sum = 0;
      for (uint32_t inner = 0; inner < d; inner++) {
        sum += (int32_t)input[row * d + inner] *
               (int32_t)weight[inner * d + col];
      }
      output[row * d + col] = sum;
    }
  }
}

static float requant_i32(const int32_t *input, int8_t *output,
                         uint32_t count, float base_scale,
                         uint32_t *maximum_out) {
  int32_t maximum = max_abs_i32(input, count);
  *maximum_out = (uint32_t)maximum;
  if (maximum == 0) {
    for (uint32_t index = 0; index < count; index++) {
      output[index] = 0;
    }
    return base_scale;
  }
  float scale = base_scale * ((float)maximum * 0.007874015748031496f);
  float inverse = reciprocal_f32((float)maximum) * 127.0f;
  for (uint32_t index = 0; index < count; index++) {
    output[index] = clamp_i8(round_even_f32((float)input[index] * inverse));
  }
  return scale;
}

static void score_i8_key_major(const int8_t *query, const int8_t *key,
                               int32_t *score, uint32_t n, uint32_t d) {
  for (uint32_t key_row = 0; key_row < n; key_row++) {
    for (uint32_t query_row = 0; query_row < n; query_row++) {
      int32_t sum = 0;
      for (uint32_t inner = 0; inner < d; inner++) {
        sum += (int32_t)query[query_row * d + inner] *
               (int32_t)key[key_row * d + inner];
      }
      score[key_row * n + query_row] = sum;
    }
  }
}

static void rescale_score(const int32_t *input, float *output, uint32_t count,
                          float scale) {
  for (uint32_t index = 0; index < count; index++) {
    output[index] = (float)input[index] * scale;
  }
}

static void smu_clear_done(void) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT;
}

static void smu_start(float *m_old, float *l_old, float *p_old,
                      float *m_tile, float *l_tile, float *p_tile,
                      float *m_out, float *l_out, float *p_out,
                      float *old_weight, float *tile_weight, uint32_t n,
                      uint32_t d, uint32_t stride) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_OLD_REG_OFFSET) =
      tcdm_offset(m_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_OLD_REG_OFFSET) =
      tcdm_offset(l_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_OLD_REG_OFFSET) =
      tcdm_offset(p_old);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_TILE_REG_OFFSET) =
      tcdm_offset(m_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET) =
      tcdm_offset(l_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_TILE_REG_OFFSET) =
      tcdm_offset(p_tile);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_M_REG_OFFSET) =
      tcdm_offset(m_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_L_REG_OFFSET) =
      tcdm_offset(l_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_O_REG_OFFSET) =
      tcdm_offset(p_out);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET) = n;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_D_REG_OFFSET) = d;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STRIDE_REG_OFFSET) = stride;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_MODE_REG_OFFSET) =
      (uint32_t)ONLINE_MERGE_MODE_MIXED_SCALAR;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_OLD_REG_OFFSET) =
      tcdm_offset(old_weight);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_TILE_REG_OFFSET) =
      tcdm_offset(tile_weight);
  smu_clear_done();
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_START_BIT;
}

static phase4_wait_t smu_wait(int *saw_busy) {
  *saw_busy = 0;
  for (uint32_t poll = 0; poll < PHASE4_MAX_POLLS; poll++) {
    uint32_t status =
        *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_REG_OFFSET);
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_BUSY_BIT) & 1u) {
      *saw_busy = 1;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_ERROR_BIT) & 1u) {
      return PHASE4_WAIT_ERROR;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_DONE_BIT) & 1u) {
      return PHASE4_WAIT_OK;
    }
  }
  return PHASE4_WAIT_TIMEOUT;
}

static void fill_one_hot(float *tile, uint32_t n, uint32_t key) {
  for (uint32_t query = 0; query < n; query++) {
    for (uint32_t column = 0; column < n; column++) {
      tile[query * n + column] = column == key ? 1.0f : 0.0f;
    }
  }
}

static void probability_update(const float *old_probability,
                               const float *tile_probability,
                               float *out_probability, const float *old_weight,
                               const float *tile_weight, uint32_t n) {
  for (uint32_t query = 0; query < n; query++) {
    online_merge_rvv_update(
        &old_probability[query * n], &tile_probability[query * n],
        &out_probability[query * n], n, old_weight[query], tile_weight[query]);
  }
}

static phase4_metrics_t metric_bits(const float *actual,
                                    const uint32_t *reference_bits,
                                    uint32_t count) {
  double sum_abs = 0.0;
  double sum_ref_abs = 0.0;
  double dot = 0.0;
  double actual_sq = 0.0;
  double reference_sq = 0.0;
  for (uint32_t index = 0; index < count; index++) {
    double lhs = (double)actual[index];
    double rhs = (double)bits_float(reference_bits[index]);
    double difference = lhs - rhs;
    sum_abs += difference < 0.0 ? -difference : difference;
    sum_ref_abs += rhs < 0.0 ? -rhs : rhs;
    dot += lhs * rhs;
    actual_sq += lhs * lhs;
    reference_sq += rhs * rhs;
  }
  phase4_metrics_t result;
  result.mae = (float)sum_abs * reciprocal_f32((float)count);
  result.stable_relative_error =
      (float)sum_abs * reciprocal_f32(
          (float)(sum_ref_abs > 1.0e-12 ? sum_ref_abs : 1.0e-12));
  if (actual_sq == 0.0 || reference_sq == 0.0) {
    result.cosine_similarity = actual_sq == reference_sq ? 1.0f : 0.0f;
  } else {
    float denominator = sqrt_f32_no_div((float)actual_sq) *
                        sqrt_f32_no_div((float)reference_sq);
    result.cosine_similarity = (float)dot * reciprocal_f32(denominator);
  }
  return result;
}

static phase4_metrics_t metric_i8_scaled(const int8_t *actual, float scale,
                                         const uint32_t *reference_bits,
                                         uint32_t count) {
  double sum_abs = 0.0;
  double sum_ref_abs = 0.0;
  double dot = 0.0;
  double actual_sq = 0.0;
  double reference_sq = 0.0;
  for (uint32_t index = 0; index < count; index++) {
    double lhs = (double)actual[index] * (double)scale;
    double rhs = (double)bits_float(reference_bits[index]);
    double difference = lhs - rhs;
    sum_abs += difference < 0.0 ? -difference : difference;
    sum_ref_abs += rhs < 0.0 ? -rhs : rhs;
    dot += lhs * rhs;
    actual_sq += lhs * lhs;
    reference_sq += rhs * rhs;
  }
  phase4_metrics_t result;
  result.mae = (float)sum_abs * reciprocal_f32((float)count);
  result.stable_relative_error =
      (float)sum_abs * reciprocal_f32(
          (float)(sum_ref_abs > 1.0e-12 ? sum_ref_abs : 1.0e-12));
  if (actual_sq == 0.0 || reference_sq == 0.0) {
    result.cosine_similarity = actual_sq == reference_sq ? 1.0f : 0.0f;
  } else {
    float denominator = sqrt_f32_no_div((float)actual_sq) *
                        sqrt_f32_no_div((float)reference_sq);
    result.cosine_similarity = (float)dot * reciprocal_f32(denominator);
  }
  return result;
}

static uint32_t saturation_count(const int8_t *values, uint32_t count) {
  uint32_t saturated = 0;
  for (uint32_t index = 0; index < count; index++) {
    saturated += values[index] == -127 || values[index] == 127;
  }
  return saturated;
}

static void print_metric(const phase4_metrics_t *metric) {
  // The target printf formatter's %g path uses a software dtoa routine that
  // emits unsupported fdiv.d instructions. Match existing experiment output
  // convention and expose IEEE-754 bits; host parsers decode these fields.
  PRINTF("{\"mae_bits\":%u,\"stable_relative_error_bits\":%u,"
         "\"cosine_similarity_bits\":%u}",
         float_bits(metric->mae), float_bits(metric->stable_relative_error),
         float_bits(metric->cosine_similarity));
}

static int run_attention(phase4_buffers_t *buffers, phase4_cycles_t *cycles) {
  const uint32_t n = PHASE4_CASE_N;
  const uint32_t d = PHASE4_CASE_D;
  const uint32_t nd = n * d;
  const uint32_t nn = n * n;
  const uint32_t stride = n * sizeof(float);
  float swq = bits_float(phase4_swq_bits[0]);
  float swk = bits_float(phase4_swk_bits[0]);
  float swv = bits_float(phase4_swv_bits[0]);
  float sx = 0.0f;
  float sq = 0.0f;
  float sk = 0.0f;
  float sv = 0.0f;
  float score_scale = 0.0f;
  uint32_t mq = 0;
  uint32_t mk = 0;
  uint32_t mv = 0;
  int smu_error_count = 0;
  int smu_timeout_count = 0;
  int smu_saw_busy = 0;
  uint32_t smu_commands = 0;
  uint64_t total_start;

  load_input(buffers, nd);
  total_start = benchmark_get_cycle64();
  uint64_t stage_start = benchmark_get_cycle64();
  sx = max_abs_f32(buffers->x, nd);
  sx = sx == 0.0f ? 1.0f : sx * 0.007874015748031496f;
  cycles->x_maxabs_scale = benchmark_get_cycle64() - stage_start;

  stage_start = benchmark_get_cycle64();
  quantize_input(buffers->x, buffers->xq, nd, sx);
  cycles->x_quant = benchmark_get_cycle64() - stage_start;

  stage_start = benchmark_get_cycle64();
  linear_i8(buffers->xq, phase4_wq_q, buffers->aq, n, d);
  cycles->q_linear = benchmark_get_cycle64() - stage_start;
  stage_start = benchmark_get_cycle64();
  linear_i8(buffers->xq, phase4_wk_q, buffers->ak, n, d);
  cycles->k_linear = benchmark_get_cycle64() - stage_start;
  stage_start = benchmark_get_cycle64();
  linear_i8(buffers->xq, phase4_wv_q, buffers->av, n, d);
  cycles->v_linear = benchmark_get_cycle64() - stage_start;

  stage_start = benchmark_get_cycle64();
  sq = requant_i32(buffers->aq, buffers->qq, nd, sx * swq, &mq);
  cycles->q_requant = benchmark_get_cycle64() - stage_start;
  stage_start = benchmark_get_cycle64();
  sk = requant_i32(buffers->ak, buffers->kq, nd, sx * swk, &mk);
  cycles->k_requant = benchmark_get_cycle64() - stage_start;
  stage_start = benchmark_get_cycle64();
  sv = requant_i32(buffers->av, buffers->vq, nd, sx * swv, &mv);
  cycles->v_requant = benchmark_get_cycle64() - stage_start;

  stage_start = benchmark_get_cycle64();
  score_i8_key_major(buffers->qq, buffers->kq, buffers->score_i32, n, d);
  cycles->qkt = benchmark_get_cycle64() - stage_start;

  stage_start = benchmark_get_cycle64();
  float inverse_sqrt_d = d == 32u
                             ? 0.1767766952966369f
                             : d == 64u ? 0.125f
                                        : reciprocal_f32(sqrt_f32_no_div((float)d));
  score_scale = sq * sk * inverse_sqrt_d;
  rescale_score(buffers->score_i32, buffers->score, nn, score_scale);
  cycles->score_rescale = benchmark_get_cycle64() - stage_start;

  // Explicit P construction: d=N, one-hot O tiles, and key-major score
  // storage. The vector update is timed separately from the accelerator
  // scalar window while both are also accumulated into smu_total.
  uint64_t smu_total_start = benchmark_get_cycle64();
  for (uint32_t query = 0; query < n; query++) {
    buffers->m_old[query] = buffers->score[query];
    buffers->l_old[query] = 1.0f;
    for (uint32_t key = 0; key < n; key++) {
      buffers->p_old[query * n + key] = key == 0 ? 1.0f : 0.0f;
    }
  }
  for (uint32_t key = 1; key < n; key++) {
    for (uint32_t query = 0; query < n; query++) {
      buffers->m_tile[query] = buffers->score[key * n + query];
      buffers->l_tile[query] = 1.0f;
    }
    fill_one_hot(buffers->p_tile, n, key);
    uint64_t scalar_start = benchmark_get_cycle64();
    smu_start(buffers->m_old, buffers->l_old, buffers->p_old,
              buffers->m_tile, buffers->l_tile, buffers->p_tile,
              buffers->m_out, buffers->l_out, buffers->p_out,
              buffers->old_weight, buffers->tile_weight, n, n, stride);
    int saw_busy = 0;
    phase4_wait_t wait_result = smu_wait(&saw_busy);
    uint64_t scalar_end = benchmark_get_cycle64();
    cycles->smu_scalar_window += scalar_end - scalar_start;
    smu_saw_busy |= saw_busy;
    smu_commands++;
    if (wait_result != PHASE4_WAIT_OK) {
      if (wait_result == PHASE4_WAIT_ERROR) {
        smu_error_count++;
      } else {
        smu_timeout_count++;
      }
      break;
    }
    uint64_t update_start = benchmark_get_cycle64();
    probability_update(buffers->p_old, buffers->p_tile, buffers->p_out,
                       buffers->old_weight, buffers->tile_weight, n);
    uint64_t update_end = benchmark_get_cycle64();
    cycles->smu_probability_update += update_end - update_start;
    float *float_swap = buffers->m_old;
    buffers->m_old = buffers->m_out;
    buffers->m_out = float_swap;
    float_swap = buffers->l_old;
    buffers->l_old = buffers->l_out;
    buffers->l_out = float_swap;
    float_swap = buffers->p_old;
    buffers->p_old = buffers->p_out;
    buffers->p_out = float_swap;
    smu_clear_done();
  }
  cycles->smu_total = benchmark_get_cycle64() - smu_total_start;
  uint64_t smu_subtotal =
      cycles->smu_scalar_window + cycles->smu_probability_update;
  cycles->smu_setup_orchestration =
      cycles->smu_total > smu_subtotal ? cycles->smu_total - smu_subtotal : 0u;

  stage_start = benchmark_get_cycle64();
  for (uint32_t query = 0; query < n; query++) {
    for (uint32_t column = 0; column < d; column++) {
      float sum = 0.0f;
      for (uint32_t key = 0; key < n; key++) {
        sum += buffers->p_old[query * n + key] *
               (float)buffers->vq[key * d + column];
      }
      buffers->pv[query * d + column] = sum;
    }
  }
  cycles->pv = benchmark_get_cycle64() - stage_start;

  stage_start = benchmark_get_cycle64();
  for (uint32_t index = 0; index < nd; index++) {
    buffers->output[index] = buffers->pv[index] * sv;
  }
  cycles->output_rescale = benchmark_get_cycle64() - stage_start;
  cycles->total = benchmark_get_cycle64() - total_start;

  phase4_metrics_t q_metric =
      metric_i8_scaled(buffers->qq, sq, phase4_q_ref_bits, nd);
  phase4_metrics_t k_metric =
      metric_i8_scaled(buffers->kq, sk, phase4_k_ref_bits, nd);
  phase4_metrics_t v_metric =
      metric_i8_scaled(buffers->vq, sv, phase4_v_ref_bits, nd);
  phase4_metrics_t score_metric =
      metric_bits(buffers->score, phase4_ref_score_key_major_bits, nn);
  phase4_metrics_t p_ref_metric =
      metric_bits(buffers->p_old, phase4_ref_prob_bits, nn);
  phase4_metrics_t p_mixed_metric =
      metric_bits(buffers->p_old, phase4_mixed_prob_bits, nn);
  phase4_metrics_t output_ref_metric =
      metric_bits(buffers->output, phase4_ref_output_bits, nd);
  phase4_metrics_t output_mixed_metric =
      metric_bits(buffers->output, phase4_mixed_output_bits, nd);
  uint32_t q_sat = saturation_count(buffers->qq, nd);
  uint32_t k_sat = saturation_count(buffers->kq, nd);
  uint32_t v_sat = saturation_count(buffers->vq, nd);
  const char *status = "pass";
  if (smu_error_count || smu_timeout_count) {
    status = "smu_error";
  } else if (smu_commands != n - 1u ||
             p_mixed_metric.cosine_similarity < 0.999f ||
             output_mixed_metric.cosine_similarity < 0.999f ||
             p_mixed_metric.stable_relative_error >= 0.01f ||
             output_mixed_metric.stable_relative_error >= 0.01f) {
    status = "integration_fail";
  }

  PRINTF("P4_RESULT {");
  PRINTF("\"status\":\"%s\",\"n\":%u,\"d\":%u,\"seed\":%u,",
         status, n, d, PHASE4_CASE_SEED);
  PRINTF("\"mode\":3,\"smu_d\":%u,\"stride\":%u,", n, stride);
  PRINTF("\"scales_bits\":{\"sX\":%u,\"sWQ\":%u,\"sWK\":%u,"
         "\"sWV\":%u,\"sQ\":%u,\"sK\":%u,\"sV\":%u,"
         "\"sScore\":%u},",
         float_bits(sx), float_bits(swq), float_bits(swk), float_bits(swv),
         float_bits(sq), float_bits(sk), float_bits(sv),
         float_bits(score_scale));
  PRINTF("\"maxabs_bits\":{\"X\":%u},\"maxabs\":{\"Q\":%u,"
         "\"K\":%u,\"V\":%u},",
         float_bits(sx * 127.0f), mq, mk, mv);
  PRINTF("\"linear\":{\"Q\":");
  print_metric(&q_metric);
  PRINTF(",\"K\":");
  print_metric(&k_metric);
  PRINTF(",\"V\":");
  print_metric(&v_metric);
  PRINTF(",\"saturation_count\":{\"Q\":%u,\"K\":%u,\"V\":%u}},",
         q_sat, k_sat, v_sat);
  PRINTF("\"score\":");
  print_metric(&score_metric);
  PRINTF(",\"probability\":{\"vs_ref\":");
  print_metric(&p_ref_metric);
  PRINTF(",\"integration_vs_host_mixed\":");
  print_metric(&p_mixed_metric);
  PRINTF("},\"output\":{\"vs_ref\":");
  print_metric(&output_ref_metric);
  PRINTF(",\"integration_vs_host_mixed\":");
  print_metric(&output_mixed_metric);
  PRINTF("},");
  PRINTF("\"smu\":{\"commands\":%u,\"done\":%u,\"error\":%u,"
         "\"timeout\":%u,\"saw_busy\":%u},",
         smu_commands,
         smu_commands - (uint32_t)(smu_error_count + smu_timeout_count),
         (uint32_t)smu_error_count, (uint32_t)smu_timeout_count,
         (uint32_t)smu_saw_busy);
  PRINTF("\"cycles\":{\"x_maxabs_scale\":%llu,\"x_quant\":%llu,"
         "\"q_linear\":%llu,\"k_linear\":%llu,\"v_linear\":%llu,"
         "\"q_requant\":%llu,\"k_requant\":%llu,\"v_requant\":%llu,"
         "\"qkt\":%llu,\"score_rescale\":%llu,"
         "\"smu_scalar_window\":%llu,\"smu_probability_update\":%llu,"
         "\"smu_setup_orchestration\":%llu,\"smu_total\":%llu,"
         "\"pv\":%llu,\"output_rescale\":%llu,"
         "\"total\":%llu},",
         (unsigned long long)cycles->x_maxabs_scale,
         (unsigned long long)cycles->x_quant,
         (unsigned long long)cycles->q_linear,
         (unsigned long long)cycles->k_linear,
         (unsigned long long)cycles->v_linear,
         (unsigned long long)cycles->q_requant,
         (unsigned long long)cycles->k_requant,
         (unsigned long long)cycles->v_requant,
         (unsigned long long)cycles->qkt,
         (unsigned long long)cycles->score_rescale,
         (unsigned long long)cycles->smu_scalar_window,
         (unsigned long long)cycles->smu_probability_update,
         (unsigned long long)cycles->smu_setup_orchestration,
         (unsigned long long)cycles->smu_total,
         (unsigned long long)cycles->pv,
         (unsigned long long)cycles->output_rescale,
         (unsigned long long)cycles->total);
  PRINTF("\"tcdm\":{\"data_bytes\":%u,\"allocation_bytes\":%u,"
         "\"runtime_reserved_bytes\":%u,\"memory_footprint_bytes\":%u,"
         "\"capacity_bytes\":%u}}\n",
         buffers->data_bytes, buffers->allocation_bytes,
         buffers->runtime_reserved_bytes, buffers->memory_footprint_bytes,
         (uint32_t)SNRT_TCDM_SIZE);
  return status[0] == 'p' ? 0 : -1;
}

int main(void) {
  if (snrt_cluster_core_idx() != 0) {
    snrt_cluster_hw_barrier();
    return 0;
  }
  phase4_buffers_t buffers = {0};
  int allocation = allocate_buffers(&buffers, PHASE4_CASE_N, PHASE4_CASE_D);
  if (allocation != 0) {
    PRINTF("P4_RESULT {\"status\":\"allocation_error\",\"n\":%u,"
           "\"d\":%u}\n", PHASE4_CASE_N, PHASE4_CASE_D);
    PRINTF("quantized-attention FAILURE allocation\n");
    snrt_cluster_hw_barrier();
    return -1;
  }
  phase4_cycles_t cycles = {0};
  int result = run_attention(&buffers, &cycles);
  PRINTF("quantized-attention %s\n", result == 0 ? "PASS" : "FAILURE");
  snrt_cluster_hw_barrier();
  return result;
}
