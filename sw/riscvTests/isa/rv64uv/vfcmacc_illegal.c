// Copyright 2026 ETH Zurich and University of Bologna.
// Solderpad Hardware License, Version 0.51, see LICENSE for details.
// SPDX-License-Identifier: SHL-0.51

#include "vector_macros.h"
#include <stdint.h>

#define CAUSE_ILLEGAL_INSTRUCTION 2u

#define VFCMACC_VV_VM1(vd, vs1, vs2)                                           \
  asm volatile(".insn r 0x57, 0x1, 0x75, " vd ", " vs1 ", " vs2               \
               ::: "memory")

#define VFCMACC_VF_RESERVED(vd, rs1, vs2)                                      \
  asm volatile(".insn r 0x57, 0x5, 0x75, " vd ", " rs1 ", " vs2              \
               ::: "memory")

volatile uint32_t trap_count;
volatile uint32_t trap_unexpected;

static inline uintptr_t read_mtvec(void) {
  uintptr_t value;
  asm volatile("csrr %0, mtvec" : "=r"(value));
  return value;
}

static inline void write_mtvec(uintptr_t value) {
  asm volatile("csrw mtvec, %0" ::"r"(value));
}

static inline uintptr_t read_fmode(void) {
  uintptr_t value;
  asm volatile("csrr %0, 0x800" : "=r"(value));
  return value;
}

static inline void write_fmode(uintptr_t value) {
  asm volatile("csrw 0x800, %0" ::"r"(value));
}

__attribute__((naked)) static void trap_entry(void) {
  asm volatile("addi sp, sp, -16\n"
               "sw t0, 0(sp)\n"
               "sw t1, 4(sp)\n"
               "sw t2, 8(sp)\n"
               "sw t3, 12(sp)\n"
               "csrr t0, mcause\n"
               "li t1, %[illegal_cause]\n"
               "beq t0, t1, 1f\n"
               "lui t2, %%hi(trap_unexpected)\n"
               "sw t0, %%lo(trap_unexpected)(t2)\n"
               "1:\n"
               "lui t2, %%hi(trap_count)\n"
               "lw t3, %%lo(trap_count)(t2)\n"
               "addi t3, t3, 1\n"
               "sw t3, %%lo(trap_count)(t2)\n"
               "csrr t0, mepc\n"
               "addi t0, t0, 4\n"
               "csrw mepc, t0\n"
               "lw t0, 0(sp)\n"
               "lw t1, 4(sp)\n"
               "lw t2, 8(sp)\n"
               "lw t3, 12(sp)\n"
               "addi sp, sp, 16\n"
               "mret\n"
               :
               : [illegal_cause] "i"(CAUSE_ILLEGAL_INSTRUCTION));
}

static void expect_illegal(const char *name, void (*emit)(void)) {
  uint32_t before = trap_count;
  emit();
  if (trap_unexpected != 0) {
    printf("%s raised unexpected trap cause %u.\n", name, trap_unexpected);
    num_failed++;
  } else if (trap_count != before + 1) {
    printf("%s did not raise illegal instruction trap.\n", name);
    num_failed++;
  } else {
    printf("%s trapped as illegal.\n", name);
  }
}

static void illegal_lmul_m8(void) {
  VSET(1, e32, m8);
  VFCMACC_VV_VM1("v0", "v8", "v16");
}

static void illegal_misaligned_m2_vd(void) {
  VSET(1, e32, m2);
  VFCMACC_VV_VM1("v1", "v8", "v12");
}

static void illegal_out_of_range_m4(void) {
  VSET(1, e32, m4);
  VFCMACC_VV_VM1("v28", "v0", "v8");
}

static void illegal_overlap_vd_vs1(void) {
  VSET(1, e32, m1);
  VFCMACC_VV_VM1("v8", "v8", "v10");
}

static void illegal_overlap_vd_vs2(void) {
  VSET(1, e32, m1);
  VFCMACC_VV_VM1("v8", "v10", "v8");
}

static void illegal_unsupported_e8(void) {
  VSET(1, e8, m1);
  VFCMACC_VV_VM1("v8", "v0", "v2");
}

static void illegal_alt_fmode_e16(void) {
  uintptr_t old_fmode = read_fmode();
  write_fmode(3);
  VSET(1, e16, m1);
  VFCMACC_VV_VM1("v8", "v0", "v2");
  write_fmode(old_fmode);
}

static void illegal_reserved_vf(void) {
  VSET(1, e32, m1);
  VFCMACC_VF_RESERVED("v8", "x0", "v2");
}

int main(void) {
  INIT_CHECK();

  uintptr_t old_mtvec = read_mtvec();
  trap_count = 0;
  trap_unexpected = 0;
  write_mtvec((uintptr_t)trap_entry);

  expect_illegal("m8", illegal_lmul_m8);
  expect_illegal("misaligned m2 vd", illegal_misaligned_m2_vd);
  expect_illegal("out-of-range m4 vd", illegal_out_of_range_m4);
  expect_illegal("vd/vs1 overlap", illegal_overlap_vd_vs1);
  expect_illegal("vd/vs2 overlap", illegal_overlap_vd_vs2);
  expect_illegal("unsupported e8", illegal_unsupported_e8);
  expect_illegal("unsupported alternative fmode", illegal_alt_fmode_e16);
  expect_illegal("reserved vf", illegal_reserved_vf);

  write_mtvec(old_mtvec);
  EXIT_CHECK();
}
