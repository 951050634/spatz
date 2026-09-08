// Copyright 2026 ETH Zurich and University of Bologna.
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

#ifndef ONLINE_MERGE_OMCFG_H_
#define ONLINE_MERGE_OMCFG_H_

#include <stdint.h>

#define OMERGE_CFG_STATE_A_M_ADDR 0x000u
#define OMERGE_CFG_STATE_A_L_ADDR 0x001u
#define OMERGE_CFG_STATE_B_M_ADDR 0x002u
#define OMERGE_CFG_STATE_B_L_ADDR 0x003u
#define OMERGE_CFG_TILE_M_ADDR 0x004u
#define OMERGE_CFG_TILE_L_ADDR 0x005u
#define OMERGE_CFG_WEIGHT_OLD_ADDR 0x006u
#define OMERGE_CFG_WEIGHT_TILE_ADDR 0x007u
#define OMERGE_CFG_N 0x008u
#define OMERGE_CFG_CTRL 0x009u

#define OMERGE_CFG_CTRL_INIT 0x1u

// The immediate is part of the instruction word.  This internal macro is
// intentionally used only with numeric literals in the switch below.
#define OMERGE_CFG_EMIT_(cfg_id_, value_)                                    \
  __asm__ volatile(".insn i 0x5b, 1, x0, %0, " #cfg_id_                     \
                   :                                                         \
                   : "r"((uint32_t)(value_))                                 \
                   : "memory")

// Minimal v1 wrapper for the implemented namespace.  Unknown IDs are not
// emitted; directed reserved-ID checks can use an explicit .insn immediate.
static inline __attribute__((always_inline)) void omerge_cfg_write(
    uint32_t cfg_id, uint32_t value) {
  switch (cfg_id) {
    case OMERGE_CFG_STATE_A_M_ADDR:
      OMERGE_CFG_EMIT_(0, value);
      break;
    case OMERGE_CFG_STATE_A_L_ADDR:
      OMERGE_CFG_EMIT_(1, value);
      break;
    case OMERGE_CFG_STATE_B_M_ADDR:
      OMERGE_CFG_EMIT_(2, value);
      break;
    case OMERGE_CFG_STATE_B_L_ADDR:
      OMERGE_CFG_EMIT_(3, value);
      break;
    case OMERGE_CFG_TILE_M_ADDR:
      OMERGE_CFG_EMIT_(4, value);
      break;
    case OMERGE_CFG_TILE_L_ADDR:
      OMERGE_CFG_EMIT_(5, value);
      break;
    case OMERGE_CFG_WEIGHT_OLD_ADDR:
      OMERGE_CFG_EMIT_(6, value);
      break;
    case OMERGE_CFG_WEIGHT_TILE_ADDR:
      OMERGE_CFG_EMIT_(7, value);
      break;
    case OMERGE_CFG_N:
      OMERGE_CFG_EMIT_(8, value);
      break;
    case OMERGE_CFG_CTRL:
      OMERGE_CFG_EMIT_(9, value);
      break;
    default:
      break;
  }
}

static inline __attribute__((always_inline)) uint32_t omerge_run(void) {
  uint32_t status;
  __asm__ volatile(".insn r 0x5b, 0, 3, %0, x0, x0"
                   : "=r"(status)
                   :
                   : "memory");
  return status;
}

#undef OMERGE_CFG_EMIT_

#endif  // ONLINE_MERGE_OMCFG_H_
