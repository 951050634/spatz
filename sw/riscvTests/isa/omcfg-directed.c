// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#include <online_merge_omcfg.h>
#include <snrt.h>
#include <spatz_cluster_peripheral.h>
#include <stdint.h>
#include <printf.h>

typedef struct {
  float state_a_m;
  float state_a_l;
  float state_b_m;
  float state_b_l;
  float tile_m;
  float tile_l;
  float tile_l_reconfigured;
  float weight_old;
  float weight_tile;
} omcfg_buffers_t;

static const uint32_t cfg_mmio_offsets[9] = {
    SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_A_M_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_A_L_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_B_M_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_ISA_STATE_B_L_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_M_TILE_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_OLD_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_DST_WEIGHT_TILE_REG_OFFSET,
    SPATZ_CLUSTER_PERIPHERAL_MERGE_N_REG_OFFSET,
};

static volatile uint32_t *cluster_reg(uint32_t offset) {
  return (volatile uint32_t *)(snrt_cluster_memory().end + offset);
}

static uint32_t tcdm_offset(const void *pointer) {
  return (uint32_t)((uintptr_t)pointer -
                    (uintptr_t)snrt_cluster_memory().start);
}

static uint32_t float_bits(float value) {
  union {
    float f;
    uint32_t u;
  } converted;
  converted.f = value;
  return converted.u;
}

static void memory_fence(void) {
  __asm__ volatile("fence rw, rw" ::: "memory");
}

// These three forms make the frozen rs1 extraction directly visible in the
// disassembly and in the adapter's structured simulation messages.
static __attribute__((noinline)) void omcfg_id0_x0(void) {
  __asm__ volatile(".insn i 0x5b, 1, x0, x0, 0" ::: "memory");
}

static __attribute__((noinline)) void omcfg_id1_a0(uint32_t value) {
  __asm__ volatile("mv a0, %0\n\t"
                   ".insn i 0x5b, 1, x0, a0, 1"
                   :
                   : "r"(value)
                   : "a0", "memory");
}

static __attribute__((noinline)) void omcfg_id2_x31(uint32_t value) {
  __asm__ volatile("mv t6, %0\n\t"
                   ".insn i 0x5b, 1, x0, t6, 2"
                   :
                   : "r"(value)
                   : "t6", "memory");
}

static __attribute__((noinline)) void omcfg_reserved_x31(uint32_t value) {
  __asm__ volatile("mv t6, %0\n\t"
                   ".insn i 0x5b, 1, x0, t6, 10"
                   :
                   : "r"(value)
                   : "t6", "memory");
}

static int expect_u32(const char *test, const char *item, uint32_t actual,
                      uint32_t expected) {
  if (actual == expected) {
    return 0;
  }
  printf("PHASE8B_%s FAILURE %s actual=0x%08x expected=0x%08x\n", test,
         item, actual, expected);
  return 1;
}

static int expect_cfg_values(const char *test, const uint32_t expected[9]) {
  int failures = 0;
  for (uint32_t cfg_id = 0; cfg_id < 9; ++cfg_id) {
    failures += expect_u32(test, "configuration register",
                           *cluster_reg(cfg_mmio_offsets[cfg_id]),
                           expected[cfg_id]);
  }
  return failures;
}

static int run_directed(void) {
  int failures = 0;
  int t2_failures = 0;
  int t4_failures = 0;
  uint32_t expected_cfg[9] = {0};
  omcfg_buffers_t *buffers =
      (omcfg_buffers_t *)snrt_l1alloc(sizeof(omcfg_buffers_t));
  if (buffers == 0) {
    printf("PHASE8B_SETUP FAILURE allocation\n");
    return 1;
  }

  buffers->state_a_m = 1.0f;
  buffers->state_a_l = 2.0f;
  buffers->state_b_m = -31.0f;
  buffers->state_b_l = 37.0f;
  buffers->tile_m = 1.0f;
  buffers->tile_l = 3.0f;
  buffers->tile_l_reconfigured = 1.0f;
  buffers->weight_old = -41.0f;
  buffers->weight_tile = -43.0f;
  memory_fence();

  // T1/T2: x0, caller-saved a0, and the highest GPR x31 carry values for
  // three distinct cfg_ids.  MMIO reads observe the canonical shared bank.
  omcfg_id0_x0();
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[1] = tcdm_offset(&buffers->state_a_l);
  omcfg_id1_a0(expected_cfg[1]);
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[2] = tcdm_offset(&buffers->state_b_m);
  omcfg_id2_x31(expected_cfg[2]);
  t2_failures += expect_cfg_values("T2", expected_cfg);
  printf("PHASE8B_T1 %s\n", t2_failures == 0 ? "PASS" : "FAILURE");

  // T3/T4: the partial mask is 0x007.  INIT must leave cfg_valid low, and
  // OMERGE must return an error without touching state or advancing selector.
  omerge_cfg_write(OMERGE_CFG_CTRL, OMERGE_CFG_CTRL_INIT);
  uint32_t status = omerge_run();
  t4_failures += expect_u32("T4", "invalid OMERGE status", status, 1u);
  t4_failures += expect_u32("T4", "state A L unchanged",
                            float_bits(buffers->state_a_l), float_bits(2.0f));
  t4_failures += expect_u32("T4", "state B L unchanged",
                            float_bits(buffers->state_b_l), float_bits(37.0f));

  // Complete the nine required fields.  Field zero is deliberately rewritten
  // after its x0 decode check; each normal write leaves the context dirty.
  expected_cfg[0] = tcdm_offset(&buffers->state_a_m);
  omerge_cfg_write(OMERGE_CFG_STATE_A_M_ADDR, expected_cfg[0]);
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[3] = tcdm_offset(&buffers->state_b_l);
  omerge_cfg_write(OMERGE_CFG_STATE_B_L_ADDR, expected_cfg[3]);
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[4] = tcdm_offset(&buffers->tile_m);
  omerge_cfg_write(OMERGE_CFG_TILE_M_ADDR, expected_cfg[4]);
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[5] = tcdm_offset(&buffers->tile_l);
  omerge_cfg_write(OMERGE_CFG_TILE_L_ADDR, expected_cfg[5]);
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[6] = tcdm_offset(&buffers->weight_old);
  omerge_cfg_write(OMERGE_CFG_WEIGHT_OLD_ADDR, expected_cfg[6]);
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[7] = tcdm_offset(&buffers->weight_tile);
  omerge_cfg_write(OMERGE_CFG_WEIGHT_TILE_ADDR, expected_cfg[7]);
  t2_failures += expect_cfg_values("T2", expected_cfg);

  expected_cfg[8] = 1u;
  omerge_cfg_write(OMERGE_CFG_N, expected_cfg[8]);
  t2_failures += expect_cfg_values("T2", expected_cfg);
  failures += t2_failures + t4_failures;
  printf("PHASE8B_T2 %s\n", t2_failures == 0 ? "PASS" : "FAILURE");
  printf("PHASE8B_T3 %s\n", t4_failures == 0 ? "PASS" : "FAILURE");
  printf("PHASE8B_T4 %s\n", t4_failures == 0 ? "PASS" : "FAILURE");
  omerge_cfg_write(OMERGE_CFG_CTRL, OMERGE_CFG_CTRL_INIT);
  printf("PHASE8B_T5 %s\n", failures == 0 ? "PASS" : "FAILURE");

  // T6/T7: equal maxima make the scalar recurrence exact for this one-row
  // setup.  The first merge consumes A and writes B; the second consumes B
  // and writes A, proving the selector toggles in hardware and back again.
  memory_fence();
  status = omerge_run();
  failures += expect_u32("T6", "first OMERGE status", status, 0u);
  failures += expect_u32("T6", "B max", float_bits(buffers->state_b_m),
                         float_bits(1.0f));
  failures += expect_u32("T6", "B normalization",
                         float_bits(buffers->state_b_l), float_bits(5.0f));
  printf("PHASE8B_T6 %s\n", failures == 0 ? "PASS" : "FAILURE");

  status = omerge_run();
  failures += expect_u32("T7", "second OMERGE status", status, 0u);
  failures += expect_u32("T7", "A max", float_bits(buffers->state_a_m),
                         float_bits(1.0f));
  failures += expect_u32("T7", "A normalization",
                         float_bits(buffers->state_a_l), float_bits(8.0f));
  printf("PHASE8B_T7 %s\n", failures == 0 ? "PASS" : "FAILURE");

  // A reserved cfg_id changes no configuration register.  Its deterministic
  // invalidation makes the next OMERGE fail until a complete INIT is repeated.
  omcfg_reserved_x31(0xa5a55a5au);
  failures += expect_cfg_values("RESERVED", expected_cfg);
  status = omerge_run();
  failures += expect_u32("RESERVED", "post-reserved status", status, 1u);
  omerge_cfg_write(OMERGE_CFG_CTRL, OMERGE_CFG_CTRL_INIT);
  printf("PHASE8B_RESERVED %s\n",
         failures == 0 ? "PASS" : "FAILURE");

  // T8: modifying a committed normal field invalidates the context.  Failed
  // OMERGE cannot advance selector.  Re-INIT resets selector to A -> B.
  expected_cfg[5] = tcdm_offset(&buffers->tile_l_reconfigured);
  omerge_cfg_write(OMERGE_CFG_TILE_L_ADDR, expected_cfg[5]);
  failures += expect_cfg_values("T8", expected_cfg);
  status = omerge_run();
  failures += expect_u32("T8", "dirty OMERGE status", status, 1u);
  failures += expect_u32("T8", "dirty merge leaves B unchanged",
                         float_bits(buffers->state_b_l), float_bits(5.0f));

  omerge_cfg_write(OMERGE_CFG_CTRL, OMERGE_CFG_CTRL_INIT);
  status = omerge_run();
  failures += expect_u32("T8", "reinitialized OMERGE status", status, 0u);
  failures += expect_u32("T8", "selector reset produces A to B",
                         float_bits(buffers->state_b_l), float_bits(9.0f));
  printf("PHASE8B_T8 %s\n", failures == 0 ? "PASS" : "FAILURE");

  // The legacy MMIO path still targets the same storage and validity state.
  // A field write dirties the OMERGE context; CLEAR_DONE is its minimal INIT
  // equivalent and also resets the selector to A.
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_SRC_L_TILE_REG_OFFSET) =
      tcdm_offset(&buffers->tile_l);
  memory_fence();
  status = omerge_run();
  failures += expect_u32("MMIO_SHARED", "dirty MMIO OMERGE status", status,
                         1u);
  *cluster_reg(SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_REG_OFFSET) =
      1u << SPATZ_CLUSTER_PERIPHERAL_MERGE_CTRL_CLEAR_DONE_BIT;
  memory_fence();
  status = omerge_run();
  failures += expect_u32("MMIO_SHARED", "MMIO INIT OMERGE status", status,
                         0u);
  failures += expect_u32("MMIO_SHARED", "MMIO selector reset A to B",
                         float_bits(buffers->state_b_l), float_bits(11.0f));
  printf("PHASE8B_MMIO_SHARED %s\n",
         failures == 0 ? "PASS" : "FAILURE");

  return failures;
}

int main(void) {
  if (snrt_cluster_core_idx() != 0) {
    snrt_cluster_hw_barrier();
    return 0;
  }

  int failures = run_directed();
  printf("PHASE8B_RESULT %s failures=%d\n",
         failures == 0 ? "SUCCESS" : "FAILURE", failures);
  snrt_cluster_hw_barrier();
  return failures;
}
