// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#include <benchmark.h>
#include <debug.h>
#include <perf_cnt.h>
#include <snrt.h>
#include <spatz_cluster_peripheral.h>
#include <stdint.h>
#include <stdio.h>

#undef PRINTF
#define PRINTF(...) printf(__VA_ARGS__)

#define MAX_N 16
#define MAX_D 64
#define TOL 1.0e-3f

typedef struct {
  float m_old[MAX_N];
  float l_old[MAX_N];
  float o_old[MAX_N][MAX_D];
  float m_tile[MAX_N];
  float l_tile[MAX_N];
  float o_tile[MAX_N][MAX_D];
  float m_out[MAX_N];
  float l_out[MAX_N];
  float o_out[MAX_N][MAX_D];
  float o_old_packed[MAX_N * MAX_D];
  float o_tile_packed[MAX_N * MAX_D];
  float o_out_packed[MAX_N * MAX_D];
  float m_ref[MAX_N];
  float l_ref[MAX_N];
  float o_ref[MAX_N][MAX_D];
} smu_buffers_t;

static smu_buffers_t *buf;

static volatile uint32_t *cluster_reg(uint32_t off) {
  return (volatile uint32_t *)(snrt_cluster_memory().end + off);
}

static uint32_t tcdm_off(const void *ptr) {
  return (uint32_t)((uintptr_t)ptr - (uintptr_t)snrt_cluster_memory().start);
}

static float absf(float x) { return x < 0.0f ? -x : x; }

static const uint32_t exp_lut_q1_23[257] = {
    0x800000, 0x7c0fd6, 0x783eb0, 0x748b9b, 0x70f5a9, 0x6d7bf5,
    0x6a1da0, 0x66d9d4, 0x63afbe, 0x609e96, 0x5da595, 0x5ac3fe,
    0x57f918, 0x554432, 0x52a49c, 0x5019b1, 0x4da2cc, 0x4b3f50,
    0x48eea5, 0x46b035, 0x448372, 0x4267d0, 0x405cc9, 0x3e61d9,
    0x3c7682, 0x3a9a49, 0x38ccb6, 0x370d57, 0x355bbc, 0x33b778,
    0x322022, 0x309554, 0x2f16ac, 0x2da3ca, 0x2c3c51, 0x2adfe8,
    0x298e36, 0x2846e9, 0x2709ad, 0x25d634, 0x24ac30, 0x238b58,
    0x227363, 0x21640b, 0x205d0c, 0x1f5e25, 0x1e6715, 0x1d779f,
    0x1c8f87, 0x1bae94, 0x1ad48c, 0x1a0139, 0x193467, 0x186de2,
    0x17ad78, 0x16f2fb, 0x163e39, 0x158f08, 0x14e53b, 0x1440a7,
    0x13a123, 0x130687, 0x1270ae, 0x11df70, 0x1152ab, 0x10ca3a,
    0x1045fc, 0x0fc5cf, 0x0f4994, 0x0ed12c, 0x0e5c78, 0x0deb5b,
    0x0d7db9, 0x0d1376, 0x0cac79, 0x0c48a6, 0x0be7e6, 0x0b8a20,
    0x0b2f3c, 0x0ad725, 0x0a81c3, 0x0a2f02, 0x09decc, 0x09910e,
    0x0945b5, 0x08fcad, 0x08b5e4, 0x087149, 0x082eca, 0x07ee57,
    0x07afdf, 0x077354, 0x0738a5, 0x06ffc4, 0x06c8a4, 0x069336,
    0x065f6c, 0x062d3b, 0x05fc94, 0x05cd6d, 0x059fba, 0x05736e,
    0x05487f, 0x051ee3, 0x04f68e, 0x04cf76, 0x04a993, 0x0484da,
    0x046142, 0x043ec3, 0x041d53, 0x03fceb, 0x03dd82, 0x03bf10,
    0x03a18e, 0x0384f5, 0x03693d, 0x034e5f, 0x033455, 0x031b18,
    0x0302a1, 0x02eaeb, 0x02d3f0, 0x02bdab, 0x02a814, 0x029328,
    0x027ee0, 0x026b38, 0x02582b, 0x0245b4, 0x0233ce, 0x022275,
    0x0211a5, 0x02015a, 0x01f18e, 0x01e23f, 0x01d369, 0x01c508,
    0x01b717, 0x01a995, 0x019c7d, 0x018fcc, 0x01837f, 0x017793,
    0x016c05, 0x0160d2, 0x0155f7, 0x014b72, 0x01413f, 0x01375d,
    0x012dc8, 0x01247f, 0x011b80, 0x0112c7, 0x010a53, 0x010221,
    0x00fa30, 0x00f27d, 0x00eb07, 0x00e3cc, 0x00dcca, 0x00d5ff,
    0x00cf6a, 0x00c908, 0x00c2d8, 0x00bcda, 0x00b70a, 0x00b169,
    0x00abf3, 0x00a6a9, 0x00a188, 0x009c90, 0x0097bf, 0x009314,
    0x008e8d, 0x008a2b, 0x0085ea, 0x0081cc, 0x007dcd, 0x0079ee,
    0x00762e, 0x00728b, 0x006f05, 0x006b9b, 0x00684b, 0x006516,
    0x0061f9, 0x005ef6, 0x005c0a, 0x005935, 0x005676, 0x0053cd,
    0x005139, 0x004eba, 0x004c4d, 0x0049f4, 0x0047ae, 0x004579,
    0x004356, 0x004144, 0x003f42, 0x003d50, 0x003b6d, 0x003999,
    0x0037d3, 0x00361b, 0x003471, 0x0032d4, 0x003144, 0x002fc0,
    0x002e48, 0x002cdb, 0x002b7a, 0x002a23, 0x0028d8, 0x002796,
    0x00265e, 0x002530, 0x00240b, 0x0022ef, 0x0021dc, 0x0020d1,
    0x001fcf, 0x001ed4, 0x001de1, 0x001cf6, 0x001c12, 0x001b35,
    0x001a5f, 0x00198f, 0x0018c6, 0x001802, 0x001745, 0x00168e,
    0x0015dc, 0x001530, 0x001489, 0x0013e8, 0x00134b, 0x0012b3,
    0x001220, 0x001191, 0x001107, 0x001080, 0x000ffe, 0x000f80,
    0x000f06, 0x000e90, 0x000e1d, 0x000dae, 0x000d42, 0x000cda,
    0x000c75, 0x000c13, 0x000bb4, 0x000b57, 0x000afe};

static uint32_t float_bits(float value) {
  union {
    float f;
    uint32_t u;
  } v;
  v.f = value;
  return v.u;
}

static float bits_float(uint32_t value) {
  union {
    uint32_t u;
    float f;
  } v;
  v.u = value;
  return v.f;
}

static uint64_t fp32_abs_to_uq16_32_bits(uint32_t bits) {
  if ((bits & 0x7fffffffu) == 0) {
    return 0;
  }
  uint64_t significand = (uint64_t)(0x800000u | (bits & 0x7fffffu));
  int32_t shift = (int32_t)((bits >> 23) & 0xffu) + 32 - 150;
  if (shift >= 0) {
    return (significand << (uint32_t)shift) & 0x0000ffffffffffffull;
  }
  return significand >> (uint32_t)(-shift);
}

static int64_t fp32_to_sq16_32(float value) {
  uint32_t bits = float_bits(value);
  uint64_t mag = fp32_abs_to_uq16_32_bits(bits);
  return (bits >> 31) ? -(int64_t)mag : (int64_t)mag;
}

static uint32_t uq16_32_to_fp32_bits(uint64_t value) {
  if (value == 0) {
    return 0;
  }

  uint32_t msb = 0;
  for (uint32_t i = 0; i < 48; i++) {
    if ((value >> i) & 1ull) {
      msb = i;
    }
  }

  uint32_t exponent = msb - 32 + 127;
  uint64_t norm = (msb >= 23) ? (value >> (msb - 23)) : (value << (23 - msb));
  return (exponent << 23) | ((uint32_t)norm & 0x7fffffu);
}

static float sq16_32_to_fp32(int64_t value) {
  if (value < 0) {
    return bits_float(0x80000000u | uq16_32_to_fp32_bits((uint64_t)(-value)));
  }
  return bits_float(uq16_32_to_fp32_bits((uint64_t)value));
}

static uint32_t fp32_abs_to_exp_pos_q8_bits(uint32_t bits) {
  if (((bits >> 23) & 0xffu) == 0) {
    return 0;
  }
  uint64_t significand = (uint64_t)(0x800000u | (bits & 0x7fffffu));
  int32_t shift = (int32_t)((bits >> 23) & 0xffu) - 127 + 13;
  if (shift < 0) {
    return 0;
  }
  if (shift >= 17) {
    return 65536;
  }
  return (uint32_t)((significand << (uint32_t)shift) >> 23);
}

static uint32_t merge_exp_q1_23(float x) {
  uint32_t bits = float_bits(x);
  uint32_t abs_bits = bits & 0x7fffffffu;
  if (((bits >> 23) & 0xffu) == 0xffu) {
    return 0;
  }
  if (abs_bits == 0) {
    return 0x800000u;
  }
  if ((bits >> 31) == 0) {
    return 0x800000u;
  }
  if (abs_bits > 0x41000000u) {
    return 0;
  }

  uint32_t pos_q8 = fp32_abs_to_exp_pos_q8_bits(bits);
  uint32_t idx = pos_q8 >> 8;
  uint32_t frac = pos_q8 & 0xffu;
  uint32_t lo = exp_lut_q1_23[idx];
  uint32_t hi = (idx == 256) ? exp_lut_q1_23[256] : exp_lut_q1_23[idx + 1];
  uint32_t step = ((lo - hi) * frac) >> 8;
  return lo - step;
}

static uint32_t recip_lut_q1_23(uint32_t idx) {
  return (uint32_t)(((uint64_t)0x800000u * 256u + (256u + idx) / 2u) /
                    (256u + idx));
}

static uint32_t merge_recip_q1_23(float x, int32_t *scale_exp) {
  uint32_t bits = float_bits(x);
  uint32_t idx = (bits >> 15) & 0xffu;
  uint32_t frac = bits & 0x7fffu;
  uint32_t lo = recip_lut_q1_23(idx);
  uint32_t hi = (idx == 256) ? recip_lut_q1_23(256) : recip_lut_q1_23(idx + 1);
  uint32_t step = ((lo - hi) * frac) >> 15;
  *scale_exp = 127 - (int32_t)((bits >> 23) & 0xffu);
  return lo - step;
}

static uint64_t q1_23_mul_uq16_32(uint64_t lhs, uint32_t rhs) {
  uint64_t lhs_lo = lhs & 0xffffffull;
  uint64_t lhs_hi = (lhs >> 24) & 0xffffffull;
  uint64_t shifted = (lhs_hi * (uint64_t)rhs) << 1;
  shifted += (lhs_lo * (uint64_t)rhs) >> 23;
  return shifted & 0x0000ffffffffffffull;
}

static uint64_t q1_23_scaled_mul_uq16_32(uint64_t lhs, uint32_t rhs,
                                         int32_t scale_exp) {
  uint64_t scaled = q1_23_mul_uq16_32(lhs, rhs);
  if (scale_exp > 0) {
    return (scaled << (uint32_t)scale_exp) & 0x0000ffffffffffffull;
  }
  return scaled >> (uint32_t)(-scale_exp);
}

static int64_t sq16_32_mul_weight(int64_t value, uint64_t weight) {
  uint64_t mag = (value < 0) ? (uint64_t)(-value) : (uint64_t)value;
  uint64_t mag_lo = mag & 0xffffffffull;
  uint64_t mag_hi = (mag >> 32) & 0xffffull;
  uint64_t weight_lo = weight & 0xffffffffull;
  uint64_t weight_hi = (weight >> 32) & 0xffffull;
  uint64_t scaled = (mag_lo * weight_lo) >> 32;
  scaled += mag_hi * weight_lo;
  scaled += weight_hi * mag_lo;
  scaled += (mag_hi * weight_hi) << 32;
  scaled &= 0x0000ffffffffffffull;
  return (value < 0) ? -(int64_t)scaled : (int64_t)scaled;
}

static int fp_close(float got, float exp) {
  float diff = absf(got - exp);
  float scale = absf(exp) > 1.0f ? absf(exp) : 1.0f;
  return diff <= (TOL * scale);
}

static void smu_start_offsets(uint32_t m_old, uint32_t l_old, uint32_t o_old,
                              uint32_t m_tile, uint32_t l_tile, uint32_t o_tile,
                              uint32_t m_out, uint32_t l_out, uint32_t o_out,
                              uint32_t n, uint32_t d, uint32_t stride) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_OLD_REG_OFFSET) = m_old;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_OLD_REG_OFFSET) = l_old;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_OLD_REG_OFFSET) = o_old;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_TILE_REG_OFFSET) = m_tile;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET) = l_tile;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_O_TILE_REG_OFFSET) = o_tile;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_M_REG_OFFSET) = m_out;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_L_REG_OFFSET) = l_out;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_O_REG_OFFSET) = o_out;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET) = n;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_D_REG_OFFSET) = d;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STRIDE_REG_OFFSET) = stride;
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      (1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      (1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_START_BIT);
}

void smu_start(float *m_old, float *l_old, float *o_old, float *m_tile,
               float *l_tile, float *o_tile, float *m_out, float *l_out,
               float *o_out, uint32_t n, uint32_t d, uint32_t stride) {
  smu_start_offsets(tcdm_off(m_old), tcdm_off(l_old), tcdm_off(o_old),
                    tcdm_off(m_tile), tcdm_off(l_tile), tcdm_off(o_tile),
                    tcdm_off(m_out), tcdm_off(l_out), tcdm_off(o_out), n, d,
                    stride);
}

int smu_done(void) {
  return (*cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_REG_OFFSET) >>
          SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_DONE_BIT) & 1u;
}

static uint32_t smu_status(void) {
  return *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_REG_OFFSET);
}

int smu_error(void) {
  return (smu_status() >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_ERROR_BIT) & 1u;
}

static int smu_busy(void) {
  return (smu_status() >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_BUSY_BIT) & 1u;
}

static void smu_clear_done(void) {
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      (1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT);
}

static int smu_wait_observe_busy(int *saw_busy) {
  const uint32_t max_polls = 100000u;
  *saw_busy = 0;
  for (uint32_t i = 0; i < max_polls; i++) {
    uint32_t status = smu_status();
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_BUSY_BIT) & 1u) {
      *saw_busy = 1;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_DONE_BIT) & 1u) {
      return 0;
    }
    if ((status >> SPATZ_CLUSTER_PERIPHERAL_MERGE_STATUS_ERROR_BIT) & 1u) {
      return -1;
    }
  }
  PRINTF("SMU timeout, status=0x%x\n", smu_status());
  return -1;
}

int smu_wait(void) {
  int saw_busy;
  return smu_wait_observe_busy(&saw_busy);
}

static void init_case(uint32_t n, uint32_t d, uint32_t case_id) {
  for (uint32_t i = 0; i < n; i++) {
    float base = (float)((int)i - 4) * 0.125f;
    if (case_id == 0) {
      buf->m_old[i] = 1.0f + base;
      buf->m_tile[i] = -0.5f + base;
    } else if (case_id == 1) {
      buf->m_old[i] = -0.75f + base;
      buf->m_tile[i] = 0.5f + base;
    } else {
      buf->m_old[i] = 0.25f + base;
      buf->m_tile[i] = 0.25f + base;
    }
    if (case_id == 0) {
      buf->l_old[i] = 0.75f + 0.0625f * (float)i;
      buf->l_tile[i] = 0.0f;
    } else if (case_id == 1) {
      buf->l_old[i] = 0.0f;
      buf->l_tile[i] = 0.5f + 0.03125f * (float)(i + 1);
    } else if (case_id == 3) {
      buf->l_old[i] = 0.001f * (float)(i + 1);
      buf->l_tile[i] = buf->l_old[i];
    } else if (case_id == 4) {
      buf->l_old[i] = 0.0015f * (float)(i + 1);
      buf->l_tile[i] = buf->l_old[i];
    } else {
      buf->l_old[i] = 0.75f + 0.0625f * (float)i;
      buf->l_tile[i] = buf->l_old[i];
    }
    buf->m_out[i] = 0.0f;
    buf->l_out[i] = 0.0f;
    buf->m_ref[i] = 0.0f;
    buf->l_ref[i] = 0.0f;
    for (uint32_t j = 0; j < d; j++) {
      buf->o_old[i][j] = 0.01f * (float)((int)(i * 7 + j * 3) - 19);
      if (case_id == 0 || case_id == 1) {
        buf->o_tile[i][j] = 0.02f * (float)((int)(i * 5 + j) - 11);
      } else {
        buf->o_tile[i][j] = buf->o_old[i][j];
      }
      buf->o_out[i][j] = 0.0f;
      buf->o_ref[i][j] = 0.0f;
    }
  }
}

static void ref_merge(uint32_t n, uint32_t d, uint32_t case_id) {
  (void)case_id;
  for (uint32_t i = 0; i < n; i++) {
    float m_new = buf->m_old[i] > buf->m_tile[i] ? buf->m_old[i] : buf->m_tile[i];
    int64_t old_exp_arg = fp32_to_sq16_32(buf->m_old[i]) - fp32_to_sq16_32(m_new);
    int64_t tile_exp_arg =
        fp32_to_sq16_32(buf->m_tile[i]) - fp32_to_sq16_32(m_new);
    uint32_t old_exp = merge_exp_q1_23(sq16_32_to_fp32(old_exp_arg));
    uint32_t tile_exp = merge_exp_q1_23(sq16_32_to_fp32(tile_exp_arg));
    uint64_t old_l = fp32_abs_to_uq16_32_bits(float_bits(buf->l_old[i]));
    uint64_t tile_l = fp32_abs_to_uq16_32_bits(float_bits(buf->l_tile[i]));
    uint64_t old_scaled_l = q1_23_mul_uq16_32(old_l, old_exp);
    uint64_t tile_scaled_l = q1_23_mul_uq16_32(tile_l, tile_exp);
    uint64_t l_new_fixed =
        (old_scaled_l + tile_scaled_l) & 0x0000ffffffffffffull;
    float l_new = bits_float(uq16_32_to_fp32_bits(l_new_fixed));
    int32_t recip_scale_exp;
    uint32_t recip_l = merge_recip_q1_23(l_new, &recip_scale_exp);
    uint64_t old_weight =
        q1_23_scaled_mul_uq16_32(old_scaled_l, recip_l, recip_scale_exp);
    uint64_t tile_weight =
        q1_23_scaled_mul_uq16_32(tile_scaled_l, recip_l, recip_scale_exp);
    buf->m_ref[i] = m_new;
    buf->l_ref[i] = l_new;
    for (uint32_t j = 0; j < d; j++) {
      int64_t old_term =
          sq16_32_mul_weight(fp32_to_sq16_32(buf->o_old[i][j]), old_weight);
      int64_t tile_term =
          sq16_32_mul_weight(fp32_to_sq16_32(buf->o_tile[i][j]), tile_weight);
      buf->o_ref[i][j] = sq16_32_to_fp32(old_term + tile_term);
    }
  }
}

static int check_case(uint32_t n, uint32_t d) {
  for (uint32_t i = 0; i < n; i++) {
    if (!fp_close(buf->m_out[i], buf->m_ref[i]) ||
        !fp_close(buf->l_out[i], buf->l_ref[i])) {
      PRINTF("Mismatch scalar row %u: m got 0x%x ref 0x%x, l got 0x%x ref 0x%x\n", i,
             *(uint32_t *)&buf->m_out[i], *(uint32_t *)&buf->m_ref[i],
             *(uint32_t *)&buf->l_out[i], *(uint32_t *)&buf->l_ref[i]);
      return -1;
    }
    for (uint32_t j = 0; j < d; j++) {
      if (!fp_close(buf->o_out[i][j], buf->o_ref[i][j])) {
        PRINTF("Mismatch O[%u][%u]: got 0x%x ref 0x%x, m_out=0x%x "
               "l_out=0x%x m_ref=0x%x l_ref=0x%x, m_old=0x%x "
               "m_tile=0x%x l_old=0x%x l_tile=0x%x o_old=0x%x "
               "o_tile=0x%x\n",
               i, j, *(uint32_t *)&buf->o_out[i][j],
               *(uint32_t *)&buf->o_ref[i][j], *(uint32_t *)&buf->m_out[i],
               *(uint32_t *)&buf->l_out[i], *(uint32_t *)&buf->m_ref[i],
               *(uint32_t *)&buf->l_ref[i], *(uint32_t *)&buf->m_old[i],
               *(uint32_t *)&buf->m_tile[i], *(uint32_t *)&buf->l_old[i],
               *(uint32_t *)&buf->l_tile[i], *(uint32_t *)&buf->o_old[i][j],
               *(uint32_t *)&buf->o_tile[i][j]);
        return -1;
      }
    }
  }
  return 0;
}

static void init_packed_vectors(uint32_t n, uint32_t d) {
  for (uint32_t i = 0; i < n; i++) {
    for (uint32_t j = 0; j < d; j++) {
      uint32_t idx = i * d + j;
      buf->o_old_packed[idx] = buf->o_old[i][j];
      buf->o_tile_packed[idx] = buf->o_tile[i][j];
      buf->o_out_packed[idx] = 0.0f;
    }
  }
}

static int check_packed_case(uint32_t n, uint32_t d) {
  for (uint32_t i = 0; i < n; i++) {
    if (!fp_close(buf->m_out[i], buf->m_ref[i]) ||
        !fp_close(buf->l_out[i], buf->l_ref[i])) {
      PRINTF("Mismatch packed scalar row %u: m got 0x%x ref 0x%x, "
             "l got 0x%x ref 0x%x\n",
             i, *(uint32_t *)&buf->m_out[i], *(uint32_t *)&buf->m_ref[i],
             *(uint32_t *)&buf->l_out[i], *(uint32_t *)&buf->l_ref[i]);
      return -1;
    }
    for (uint32_t j = 0; j < d; j++) {
      uint32_t idx = i * d + j;
      if (!fp_close(buf->o_out_packed[idx], buf->o_ref[i][j])) {
        PRINTF("Mismatch packed O[%u][%u]: got 0x%x ref 0x%x\n", i, j,
               *(uint32_t *)&buf->o_out_packed[idx],
               *(uint32_t *)&buf->o_ref[i][j]);
        return -1;
      }
    }
  }
  return 0;
}

static void copy_output_to_state(uint32_t n, uint32_t d) {
  for (uint32_t i = 0; i < n; i++) {
    buf->m_old[i] = buf->m_out[i];
    buf->l_old[i] = buf->l_out[i];
    for (uint32_t j = 0; j < d; j++) {
      buf->o_old[i][j] = buf->o_out[i][j];
    }
  }
}

static void init_attention_state(uint32_t n, uint32_t d) {
  for (uint32_t i = 0; i < n; i++) {
    buf->m_old[i] = 0.0f;
    buf->l_old[i] = 0.0f;
    buf->m_out[i] = 0.0f;
    buf->l_out[i] = 0.0f;
    buf->m_ref[i] = 0.0f;
    buf->l_ref[i] = 0.0f;
    for (uint32_t j = 0; j < d; j++) {
      buf->o_old[i][j] = 0.0f;
      buf->o_out[i][j] = 0.0f;
      buf->o_ref[i][j] = 0.0f;
    }
  }
}

static void init_attention_tile(uint32_t n, uint32_t d, uint32_t block) {
  for (uint32_t i = 0; i < n; i++) {
    float row = (float)i;
    float blk = (float)block;
    int mode = (int)((i + block) & 3u);
    if (mode == 0) {
      buf->m_tile[i] = -0.50f + 0.125f * row + 0.1875f * blk;
      buf->l_tile[i] = 0.50f + 0.03125f * row + 0.015625f * blk;
    } else if (mode == 1) {
      buf->m_tile[i] = 0.75f - 0.0625f * row + 0.125f * blk;
      buf->l_tile[i] = 0.25f + 0.046875f * row + 0.03125f * blk;
    } else if (mode == 2) {
      buf->m_tile[i] = 0.125f + 0.0625f * row - 0.0625f * blk;
      buf->l_tile[i] = 1.00f + 0.015625f * row;
    } else {
      buf->m_tile[i] = -1.00f + 0.09375f * row + 0.25f * blk;
      buf->l_tile[i] = 0.001f * (row + 1.0f) * (blk + 1.0f);
    }
    for (uint32_t j = 0; j < d; j++) {
      int v = (int)(block * 19 + i * 11 + j * 5) % 53;
      buf->o_tile[i][j] = ((float)v - 26.0f) * 0.01171875f;
    }
  }
}

static int smu_wait_error(void) {
  const uint32_t max_polls = 1000000u;
  for (uint32_t i = 0; i < max_polls; i++) {
    if (smu_error()) {
      return smu_busy() ? -1 : 0;
    }
    if (smu_done()) {
      return -1;
    }
  }
  PRINTF("SMU error timeout, status=0x%x\n", smu_status());
  return -1;
}

static int run_invalid_case(const char *name, uint32_t n, uint32_t d,
                            uint32_t m_old_offset, uint32_t stride) {
  smu_start_offsets(m_old_offset, tcdm_off(buf->l_old),
                    tcdm_off(&buf->o_old[0][0]), tcdm_off(buf->m_tile),
                    tcdm_off(buf->l_tile), tcdm_off(&buf->o_tile[0][0]),
                    tcdm_off(buf->m_out), tcdm_off(buf->l_out),
                    tcdm_off(&buf->o_out[0][0]), n, d, stride);
  if (smu_wait_error() != 0) {
    PRINTF("SMU invalid-config case %s did not report clean error, status=0x%x\n",
           name, smu_status());
    return -1;
  }
  PRINTF("online-softmax-merge invalid %s status=0x%x\n", name, smu_status());
  smu_clear_done();
  return 0;
}

static int run_invalid_cases(void) {
  uint32_t m_old = tcdm_off(buf->m_old);
  int rc = 0;
  rc |= run_invalid_case("n-zero", 0, 1, m_old, MAX_D * sizeof(float));
  rc |= run_invalid_case("d-zero", 1, 0, m_old, MAX_D * sizeof(float));
  rc |= run_invalid_case("misaligned-address", 1, 1, m_old + 1,
                         MAX_D * sizeof(float));
  rc |= run_invalid_case("misaligned-stride", 1, 1, m_old, 2);
  return rc;
}

static int run_unsupported_case(const char *name, float m_old, float m_tile,
                                float l_old, float l_tile) {
  init_case(1, 1, 2);
  buf->m_old[0] = m_old;
  buf->m_tile[0] = m_tile;
  buf->l_old[0] = l_old;
  buf->l_tile[0] = l_tile;
  smu_start(buf->m_old, buf->l_old, &buf->o_old[0][0], buf->m_tile, buf->l_tile,
            &buf->o_tile[0][0], buf->m_out, buf->l_out, &buf->o_out[0][0], 1, 1,
            MAX_D * sizeof(float));
  if (smu_wait_error() != 0) {
    PRINTF("SMU unsupported case %s did not report error, status=0x%x\n", name,
           smu_status());
    return -1;
  }
  PRINTF("online-softmax-merge unsupported %s status=0x%x\n", name, smu_status());
  smu_clear_done();
  return 0;
}

static int run_unsupported_cases(void) {
  int rc = 0;
  rc |= run_unsupported_case("both-zero-l", 0.0f, 0.0f, 0.0f, 0.0f);
  return rc;
}

static void init_full_reference_probe_case(uint32_t n, uint32_t d) {
  for (uint32_t i = 0; i < n; i++) {
    float row = (float)i;
    switch (i & 3u) {
    case 0:
      buf->m_old[i] = 1.25f + 0.125f * row;
      buf->m_tile[i] = buf->m_old[i] - 0.75f;
      buf->l_old[i] = 0.75f + 0.03125f * row;
      buf->l_tile[i] = 0.25f + 0.015625f * row;
      break;
    case 1:
      buf->m_old[i] = -0.25f + 0.0625f * row;
      buf->m_tile[i] = buf->m_old[i] + 0.75f;
      buf->l_old[i] = 0.50f + 0.03125f * row;
      buf->l_tile[i] = 1.25f + 0.015625f * row;
      break;
    case 2:
      buf->m_old[i] = 0.125f + 0.0625f * row;
      buf->m_tile[i] = buf->m_old[i];
      buf->l_old[i] = 0.25f + 0.03125f * row;
      buf->l_tile[i] = 0.75f + 0.015625f * row;
      break;
    default:
      buf->m_old[i] = -1.0f + 0.0625f * row;
      buf->m_tile[i] = buf->m_old[i] + 0.75f;
      buf->l_old[i] = 0.001f * (row + 1.0f);
      buf->l_tile[i] = 0.003f * (row + 1.0f);
      break;
    }
    buf->m_out[i] = 0.0f;
    buf->l_out[i] = 0.0f;
    for (uint32_t j = 0; j < d; j++) {
      buf->o_old[i][j] = 0.01f * (float)((int)(i * 11 + j * 5) - 17);
      buf->o_tile[i][j] = 0.02f * (float)((int)(i * 7 + j * 3) - 23);
      buf->o_out[i][j] = 0.0f;
    }
  }
}

static int run_full_reference_probe_case(const char *name, uint32_t n,
                                         uint32_t d) {
  init_full_reference_probe_case(n, d);
  ref_merge(n, d, 5);

  uint32_t cpu_start = benchmark_get_cycle();
  ref_merge(n, d, 5);
  uint32_t cpu_cycles = benchmark_get_cycle() - cpu_start;
  snrt_reset_perf_counter(SNRT_PERF_CNT0);
  snrt_reset_perf_counter(SNRT_PERF_CNT1);
  snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_TCDM_ACCESSED, 0);
  snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_TCDM_CONGESTED, 0);
  uint32_t engine_start = benchmark_get_cycle();
  smu_start(buf->m_old, buf->l_old, &buf->o_old[0][0], buf->m_tile, buf->l_tile,
            &buf->o_tile[0][0], buf->m_out, buf->l_out, &buf->o_out[0][0], n, d,
            MAX_D * sizeof(float));
  int saw_busy;
  int wait_rc = smu_wait_observe_busy(&saw_busy);
  uint32_t engine_cycles = benchmark_get_cycle() - engine_start;
  snrt_stop_perf_counter(SNRT_PERF_CNT0);
  snrt_stop_perf_counter(SNRT_PERF_CNT1);
  uint32_t tcdm_accessed = snrt_get_perf_counter(SNRT_PERF_CNT0);
  uint32_t tcdm_congested = snrt_get_perf_counter(SNRT_PERF_CNT1);

  if (wait_rc != 0 || smu_error()) {
    PRINTF("SMU full-reference probe %s failed, status=0x%x\n", name,
           smu_status());
    return -1;
  }
  if (check_case(n, d) != 0) {
    return -1;
  }
  PRINTF("online-softmax-merge full-ref-probe %s N=%u D=%u status=0x%x "
         "cpu=%u engine=%u tcdm_accessed=%u tcdm_congested=%u ref_l0=0x%x "
         "ref_o00=0x%x\n",
         name, n, d, smu_status(), cpu_cycles, engine_cycles, tcdm_accessed,
         tcdm_congested, *(uint32_t *)&buf->l_ref[0],
         *(uint32_t *)&buf->o_ref[0][0]);
  smu_clear_done();
  return 0;
}

static int run_case(uint32_t n, uint32_t d, uint32_t case_id, int require_busy) {
  init_case(n, d, case_id);
  PRINTF("online-softmax-merge begin N=%u D=%u case=%u\n", n, d, case_id);
  uint32_t cpu_start = benchmark_get_cycle();
  ref_merge(n, d, case_id);
  uint32_t cpu_cycles = benchmark_get_cycle() - cpu_start;

  snrt_reset_perf_counter(SNRT_PERF_CNT0);
  snrt_reset_perf_counter(SNRT_PERF_CNT1);
  snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_TCDM_ACCESSED, 0);
  snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_TCDM_CONGESTED, 0);
  uint32_t engine_start = benchmark_get_cycle();
  smu_start(buf->m_old, buf->l_old, &buf->o_old[0][0], buf->m_tile, buf->l_tile,
            &buf->o_tile[0][0], buf->m_out, buf->l_out, &buf->o_out[0][0], n, d,
            MAX_D * sizeof(float));
  int saw_busy;
  int wait_rc = smu_wait_observe_busy(&saw_busy);
  uint32_t engine_cycles = benchmark_get_cycle() - engine_start;
  snrt_stop_perf_counter(SNRT_PERF_CNT0);
  snrt_stop_perf_counter(SNRT_PERF_CNT1);
  uint32_t tcdm_accessed = snrt_get_perf_counter(SNRT_PERF_CNT0);
  uint32_t tcdm_congested = snrt_get_perf_counter(SNRT_PERF_CNT1);

  if (wait_rc != 0 || smu_error()) {
    PRINTF("SMU error for N=%u D=%u case=%u\n", n, d, case_id);
    return -1;
  }
  if (require_busy && !saw_busy) {
    PRINTF("SMU busy was not observed for N=%u D=%u case=%u\n", n, d,
           case_id);
    return -1;
  }
  if (check_case(n, d) != 0) {
    return -1;
  }

  PRINTF("online-softmax-merge N=%u D=%u case=%u cpu=%u engine=%u "
         "tcdm_accessed=%u tcdm_congested=%u\n",
         n, d, case_id, cpu_cycles, engine_cycles, tcdm_accessed,
         tcdm_congested);
  return 0;
}

static int run_full_mixed_case(uint32_t n, uint32_t d, int require_busy) {
  init_full_reference_probe_case(n, d);
  PRINTF("online-softmax-merge begin full-mixed N=%u D=%u\n", n, d);
  uint32_t cpu_start = benchmark_get_cycle();
  ref_merge(n, d, 5);
  uint32_t cpu_cycles = benchmark_get_cycle() - cpu_start;

  snrt_reset_perf_counter(SNRT_PERF_CNT0);
  snrt_reset_perf_counter(SNRT_PERF_CNT1);
  snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_TCDM_ACCESSED, 0);
  snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_TCDM_CONGESTED, 0);
  uint32_t engine_start = benchmark_get_cycle();
  smu_start(buf->m_old, buf->l_old, &buf->o_old[0][0], buf->m_tile, buf->l_tile,
            &buf->o_tile[0][0], buf->m_out, buf->l_out, &buf->o_out[0][0], n, d,
            MAX_D * sizeof(float));
  int saw_busy;
  int wait_rc = smu_wait_observe_busy(&saw_busy);
  uint32_t engine_cycles = benchmark_get_cycle() - engine_start;
  snrt_stop_perf_counter(SNRT_PERF_CNT0);
  snrt_stop_perf_counter(SNRT_PERF_CNT1);
  uint32_t tcdm_accessed = snrt_get_perf_counter(SNRT_PERF_CNT0);
  uint32_t tcdm_congested = snrt_get_perf_counter(SNRT_PERF_CNT1);

  if (wait_rc != 0 || smu_error()) {
    PRINTF("SMU error for full-mixed N=%u D=%u status=0x%x\n", n, d,
           smu_status());
    return -1;
  }
  if (require_busy && !saw_busy) {
    PRINTF("SMU busy was not observed for full-mixed N=%u D=%u\n", n, d);
    return -1;
  }
  if (check_case(n, d) != 0) {
    return -1;
  }
  PRINTF("online-softmax-merge full-mixed N=%u D=%u cpu=%u engine=%u "
         "tcdm_accessed=%u tcdm_congested=%u\n",
         n, d, cpu_cycles, engine_cycles, tcdm_accessed, tcdm_congested);
  smu_clear_done();
  return 0;
}

static int run_attention_like_case(uint32_t n, uint32_t d, uint32_t blocks) {
  init_attention_state(n, d);
  uint32_t cpu_total = 0;
  uint32_t engine_total = 0;
  uint32_t tcdm_accessed_total = 0;
  uint32_t tcdm_congested_total = 0;
  int saw_busy_any = 0;

  for (uint32_t b = 0; b < blocks; b++) {
    init_attention_tile(n, d, b);

    uint32_t cpu_start = benchmark_get_cycle();
    ref_merge(n, d, 6);
    cpu_total += benchmark_get_cycle() - cpu_start;
    float ref_m[MAX_N];
    float ref_l[MAX_N];
    float ref_o[MAX_N][MAX_D];
    for (uint32_t i = 0; i < n; i++) {
      ref_m[i] = buf->m_ref[i];
      ref_l[i] = buf->l_ref[i];
      for (uint32_t j = 0; j < d; j++) {
        ref_o[i][j] = buf->o_ref[i][j];
      }
    }

    snrt_reset_perf_counter(SNRT_PERF_CNT0);
    snrt_reset_perf_counter(SNRT_PERF_CNT1);
    snrt_start_perf_counter(SNRT_PERF_CNT0, SNRT_PERF_CNT_TCDM_ACCESSED, 0);
    snrt_start_perf_counter(SNRT_PERF_CNT1, SNRT_PERF_CNT_TCDM_CONGESTED, 0);
    uint32_t engine_start = benchmark_get_cycle();
    smu_start(buf->m_old, buf->l_old, &buf->o_old[0][0], buf->m_tile,
              buf->l_tile, &buf->o_tile[0][0], buf->m_out, buf->l_out,
              &buf->o_out[0][0], n, d, MAX_D * sizeof(float));
    int saw_busy;
    int wait_rc = smu_wait_observe_busy(&saw_busy);
    engine_total += benchmark_get_cycle() - engine_start;
    saw_busy_any |= saw_busy;
    snrt_stop_perf_counter(SNRT_PERF_CNT0);
    snrt_stop_perf_counter(SNRT_PERF_CNT1);
    tcdm_accessed_total += snrt_get_perf_counter(SNRT_PERF_CNT0);
    tcdm_congested_total += snrt_get_perf_counter(SNRT_PERF_CNT1);

    if (wait_rc != 0 || smu_error()) {
      PRINTF("SMU error for attention-like N=%u D=%u block=%u status=0x%x\n",
             n, d, b, smu_status());
      return -1;
    }

    for (uint32_t i = 0; i < n; i++) {
      buf->m_ref[i] = ref_m[i];
      buf->l_ref[i] = ref_l[i];
      for (uint32_t j = 0; j < d; j++) {
        buf->o_ref[i][j] = ref_o[i][j];
      }
    }
    if (check_case(n, d) != 0) {
      return -1;
    }
    copy_output_to_state(n, d);
    smu_clear_done();
  }

  uint32_t state_bytes = blocks * n * (2u + d) * sizeof(float);
  PRINTF("online-softmax-merge attention-like rows=%u blocks=%u D=%u cpu=%u "
         "engine=%u tcdm_accessed=%u tcdm_congested=%u state_bytes=%u "
         "saw_busy=%u\n",
         n, blocks, d, cpu_total, engine_total, tcdm_accessed_total,
         tcdm_congested_total, state_bytes, saw_busy_any);
  return 0;
}

static int run_stride_zero_case(uint32_t n, uint32_t d, uint32_t case_id) {
  init_case(n, d, case_id);
  init_packed_vectors(n, d);
  ref_merge(n, d, case_id);

  smu_start(buf->m_old, buf->l_old, buf->o_old_packed, buf->m_tile,
            buf->l_tile, buf->o_tile_packed, buf->m_out, buf->l_out,
            buf->o_out_packed, n, d, 0);
  int saw_busy;
  if (smu_wait_observe_busy(&saw_busy) != 0 || smu_error()) {
    PRINTF("SMU error for stride-zero N=%u D=%u case=%u status=0x%x\n", n, d,
           case_id, smu_status());
    return -1;
  }
  if (!saw_busy) {
    PRINTF("SMU busy was not observed for stride-zero N=%u D=%u case=%u\n",
           n, d, case_id);
    return -1;
  }
  if (check_packed_case(n, d) != 0) {
    return -1;
  }

  PRINTF("online-softmax-merge stride-zero N=%u D=%u case=%u status=0x%x\n", n,
         d, case_id, smu_status());
  smu_clear_done();
  return 0;
}

int main(void) {
  if (snrt_cluster_core_idx() != 0) {
    snrt_cluster_hw_barrier();
    return 0;
  }

  buf = (smu_buffers_t *)snrt_l1alloc(sizeof(smu_buffers_t));
  if (buf == 0) {
    PRINTF("Failed to allocate SMU buffers\n");
    return -1;
  }

  int rc = 0;
  rc |= run_case(1, 1, 0, 0);
  rc |= run_case(4, 8, 1, 0);
  rc |= run_case(8, 16, 2, 0);
  rc |= run_case(16, 64, 2, 1);
  rc |= run_case(4, 8, 3, 0);
  rc |= run_stride_zero_case(4, 8, 2);
  rc |= run_full_mixed_case(1, 1, 0);
  rc |= run_full_mixed_case(4, 8, 0);
  rc |= run_full_mixed_case(8, 16, 0);
  rc |= run_full_mixed_case(8, 32, 0);
  rc |= run_full_mixed_case(16, 64, 1);
  rc |= run_attention_like_case(8, 32, 4);
  rc |= run_invalid_cases();
  rc |= run_unsupported_cases();
  rc |= run_full_reference_probe_case("generic-mixed", 4, 8);

  if (rc == 0) {
    PRINTF("online-softmax-merge PASS\n");
  }

  snrt_cluster_hw_barrier();
  return rc;
}
