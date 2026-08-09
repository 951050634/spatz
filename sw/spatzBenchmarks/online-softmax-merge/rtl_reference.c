// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#include "rtl_reference.h"

#include "rvv_update.h"

#include <stdint.h>

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

static const uint32_t recip_lut_q1_23[257] = {
    0x800000u, 0x7f8080u, 0x7f01fcu, 0x7e8473u,
    0x7e07e0u, 0x7d8c43u, 0x7d1196u, 0x7c97d9u,
    0x7c1f08u, 0x7ba720u, 0x7b301fu, 0x7aba02u,
    0x7a44c7u, 0x79d06bu, 0x795cebu, 0x78ea46u,
    0x787878u, 0x780780u, 0x77975cu, 0x772807u,
    0x76b982u, 0x764bc9u, 0x75ded9u, 0x7572b2u,
    0x750750u, 0x749cb3u, 0x7432d6u, 0x73c9b9u,
    0x73615au, 0x72f9b6u, 0x7292ccu, 0x722c99u,
    0x71c71cu, 0x716253u, 0x70fe3cu, 0x709ad5u,
    0x70381cu, 0x6fd610u, 0x6f74aeu, 0x6f13f6u,
    0x6eb3e4u, 0x6e5479u, 0x6df5b1u, 0x6d978cu,
    0x6d3a07u, 0x6cdd21u, 0x6c80d9u, 0x6c252du,
    0x6bca1bu, 0x6b6fa2u, 0x6b15c0u, 0x6abc75u,
    0x6a63beu, 0x6a0b99u, 0x69b407u, 0x695d04u,
    0x690690u, 0x68b0aau, 0x685b50u, 0x680680u,
    0x67b23au, 0x675e7cu, 0x670b45u, 0x66b894u,
    0x666666u, 0x6614bcu, 0x65c394u, 0x6572ecu,
    0x6522c4u, 0x64d31au, 0x6483edu, 0x64353cu,
    0x63e706u, 0x63994au, 0x634c06u, 0x62ff3au,
    0x62b2e4u, 0x626704u, 0x621b98u, 0x61d09fu,
    0x618618u, 0x613c03u, 0x60f25eu, 0x60a928u,
    0x606060u, 0x601806u, 0x5fd018u, 0x5f8895u,
    0x5f417du, 0x5efaceu, 0x5eb488u, 0x5e6eaau,
    0x5e2932u, 0x5de420u, 0x5d9f74u, 0x5d5b2bu,
    0x5d1746u, 0x5cd3c3u, 0x5c90a2u, 0x5c4de2u,
    0x5c0b81u, 0x5bc980u, 0x5b87deu, 0x5b4699u,
    0x5b05b0u, 0x5ac524u, 0x5a84f3u, 0x5a451du,
    0x5a05a0u, 0x59c67du, 0x5987b2u, 0x59493eu,
    0x590b21u, 0x58cd5bu, 0x588feau, 0x5852ceu,
    0x581606u, 0x57d991u, 0x579d6fu, 0x57619fu,
    0x572621u, 0x56eaf3u, 0x56b016u, 0x567588u,
    0x563b49u, 0x560158u, 0x55c7b5u, 0x558e5fu,
    0x555555u, 0x551c98u, 0x54e425u, 0x54abfdu,
    0x547420u, 0x543c8cu, 0x540540u, 0x53ce3eu,
    0x539783u, 0x53610fu, 0x532ae2u, 0x52f4fbu,
    0x52bf5bu, 0x5289ffu, 0x5254e8u, 0x522015u,
    0x51eb85u, 0x51b739u, 0x51832fu, 0x514f68u,
    0x511be2u, 0x50e89du, 0x50b599u, 0x5082d5u,
    0x505050u, 0x501e0bu, 0x4fec05u, 0x4fba3du,
    0x4f88b3u, 0x4f5766u, 0x4f2657u, 0x4ef583u,
    0x4ec4ecu, 0x4e9491u, 0x4e6471u, 0x4e348bu,
    0x4e04e0u, 0x4dd56fu, 0x4da638u, 0x4d7739u,
    0x4d4874u, 0x4d19e7u, 0x4ceb91u, 0x4cbd74u,
    0x4c8f8du, 0x4c61ddu, 0x4c3464u, 0x4c0721u,
    0x4bda13u, 0x4bad3bu, 0x4b8097u, 0x4b5428u,
    0x4b27edu, 0x4afbe6u, 0x4ad013u, 0x4aa472u,
    0x4a7905u, 0x4a4dc9u, 0x4a22c0u, 0x49f7e9u,
    0x49cd43u, 0x49a2ceu, 0x49788au, 0x494e76u,
    0x492492u, 0x48fadeu, 0x48d15au, 0x48a805u,
    0x487edeu, 0x4855e6u, 0x482d1cu, 0x480480u,
    0x47dc12u, 0x47b3d1u, 0x478bbdu, 0x4763d6u,
    0x473c1bu, 0x47148cu, 0x46ed29u, 0x46c5f2u,
    0x469ee6u, 0x467804u, 0x46514eu, 0x462ac2u,
    0x460460u, 0x45de28u, 0x45b81au, 0x459235u,
    0x456c79u, 0x4546e7u, 0x45217cu, 0x44fc3au,
    0x44d720u, 0x44b22eu, 0x448d64u, 0x4468c0u,
    0x444444u, 0x441fefu, 0x43fbc0u, 0x43d7b8u,
    0x43b3d6u, 0x439019u, 0x436c83u, 0x434911u,
    0x4325c5u, 0x43029eu, 0x42df9cu, 0x42bcbeu,
    0x429a04u, 0x42776fu, 0x4254fdu, 0x4232afu,
    0x421084u, 0x41ee7du, 0x41cc98u, 0x41aad6u,
    0x418937u, 0x4167bbu, 0x414660u, 0x412527u,
    0x410410u, 0x40e31bu, 0x40c247u, 0x40a194u,
    0x408102u, 0x406091u, 0x404040u, 0x402010u,
    0x400000u
};

static uint32_t merge_recip_q1_23(float x, int32_t *scale_exp) {
  uint32_t bits = float_bits(x);
  uint32_t idx = (bits >> 15) & 0xffu;
  uint32_t frac = bits & 0x7fffu;
  uint32_t lo = recip_lut_q1_23[idx];
  uint32_t hi = (idx == 256) ? recip_lut_q1_23[256] : recip_lut_q1_23[idx + 1];
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

typedef struct {
  float m_new;
  float l_new;
  uint64_t old_weight;
  uint64_t tile_weight;
} online_merge_rtl_row_weights_t;

static inline online_merge_rtl_row_weights_t online_merge_rtl_row_weights(
    float m_old, float l_old, float m_tile, float l_tile) {
  online_merge_rtl_row_weights_t weights;
  weights.m_new = m_old > m_tile ? m_old : m_tile;
  int64_t old_exp_arg =
      fp32_to_sq16_32(m_old) - fp32_to_sq16_32(weights.m_new);
  int64_t tile_exp_arg =
      fp32_to_sq16_32(m_tile) - fp32_to_sq16_32(weights.m_new);
  uint32_t old_exp = merge_exp_q1_23(sq16_32_to_fp32(old_exp_arg));
  uint32_t tile_exp = merge_exp_q1_23(sq16_32_to_fp32(tile_exp_arg));
  uint64_t old_l = fp32_abs_to_uq16_32_bits(float_bits(l_old));
  uint64_t tile_l = fp32_abs_to_uq16_32_bits(float_bits(l_tile));
  uint64_t old_scaled_l = q1_23_mul_uq16_32(old_l, old_exp);
  uint64_t tile_scaled_l = q1_23_mul_uq16_32(tile_l, tile_exp);
  uint64_t l_new_fixed =
      (old_scaled_l + tile_scaled_l) & 0x0000ffffffffffffull;
  weights.l_new = bits_float(uq16_32_to_fp32_bits(l_new_fixed));
  int32_t recip_scale_exp;
  uint32_t recip_l =
      merge_recip_q1_23(weights.l_new, &recip_scale_exp);
  weights.old_weight = q1_23_scaled_mul_uq16_32(
      old_scaled_l, recip_l, recip_scale_exp);
  weights.tile_weight = q1_23_scaled_mul_uq16_32(
      tile_scaled_l, recip_l, recip_scale_exp);
  return weights;
}

void online_merge_rtl_reference(
    const float *m_old, const float *l_old, const float *o_old,
    const float *m_tile, const float *l_tile, const float *o_tile,
    float *m_out, float *l_out, float *o_out, uint32_t n, uint32_t d,
    uint32_t stride_bytes) {
  for (uint32_t i = 0; i < n; i++) {
    const float *old_row =
        (const float *)((const uint8_t *)o_old + i * stride_bytes);
    const float *tile_row =
        (const float *)((const uint8_t *)o_tile + i * stride_bytes);
    float *out_row = (float *)((uint8_t *)o_out + i * stride_bytes);
    online_merge_rtl_row_weights_t weights = online_merge_rtl_row_weights(
        m_old[i], l_old[i], m_tile[i], l_tile[i]);

    m_out[i] = weights.m_new;
    l_out[i] = weights.l_new;
    for (uint32_t j = 0; j < d; j++) {
      int64_t old_term = sq16_32_mul_weight(
          fp32_to_sq16_32(old_row[j]), weights.old_weight);
      int64_t tile_term = sq16_32_mul_weight(
          fp32_to_sq16_32(tile_row[j]), weights.tile_weight);
      out_row[j] = sq16_32_to_fp32(old_term + tile_term);
    }
  }
}

void online_merge_b2_r(
    const float *m_old, const float *l_old, const float *o_old,
    const float *m_tile, const float *l_tile, const float *o_tile,
    float *m_out, float *l_out, float *o_out, uint32_t n, uint32_t d,
    uint32_t stride_bytes) {
  for (uint32_t i = 0; i < n; i++) {
    const float *old_row =
        (const float *)((const uint8_t *)o_old + i * stride_bytes);
    const float *tile_row =
        (const float *)((const uint8_t *)o_tile + i * stride_bytes);
    float *out_row = (float *)((uint8_t *)o_out + i * stride_bytes);
    online_merge_rtl_row_weights_t weights = online_merge_rtl_row_weights(
        m_old[i], l_old[i], m_tile[i], l_tile[i]);
    float old_weight =
        bits_float(uq16_32_to_fp32_bits(weights.old_weight));
    float tile_weight =
        bits_float(uq16_32_to_fp32_bits(weights.tile_weight));

    m_out[i] = weights.m_new;
    l_out[i] = weights.l_new;
    online_merge_rvv_update(old_row, tile_row, out_row, d, old_weight,
                            tile_weight);
  }
}
