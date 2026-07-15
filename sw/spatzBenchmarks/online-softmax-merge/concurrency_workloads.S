# Copyright 2026 ETH Zurich and University of Bologna.
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

    .text
    .align 2
    .globl online_merge_register_workload
    .type online_merge_register_workload, @function
online_merge_register_workload:
    mv        t0, a1
    xori      t1, a1, 0x135
    addi      t2, a1, 17
    xori      t3, a1, 0x2a5
    addi      t4, a1, 31
    xori      t5, a1, 0x35a
    beqz      a0, .Lregister_done
.Lregister_loop:
    add       t0, t0, t1
    xor       t2, t2, t0
    add       t3, t3, t2
    xor       t4, t4, t3
    add       t5, t5, t4
    xor       t1, t1, t5
    add       t0, t0, t3
    xor       t2, t2, t4
    addi      a0, a0, -1
    bnez      a0, .Lregister_loop
.Lregister_done:
    xor       t0, t0, t2
    xor       t0, t0, t4
    mv        a0, t0
    ret
    .size online_merge_register_workload, .-online_merge_register_workload

    .align 2
    .globl online_merge_concurrency_stream
    .type online_merge_concurrency_stream, @function
online_merge_concurrency_stream:
    beqz      a2, .Lstream_done
.Lstream_loop:
    li        t0, 8
    bgeu      t0, a2, .Lstream_tail
    mv        t1, t0
    j         .Lstream_vl
.Lstream_tail:
    mv        t1, a2
.Lstream_vl:
    vsetvli   t2, t1, e32, m8, ta, ma
    vle32.v   v8, (a0)
    vse32.v   v8, (a1)
    slli      t3, t2, 2
    add       a0, a0, t3
    add       a1, a1, t3
    sub       a2, a2, t2
    bnez      a2, .Lstream_loop
.Lstream_done:
    ret
    .size online_merge_concurrency_stream, .-online_merge_concurrency_stream
