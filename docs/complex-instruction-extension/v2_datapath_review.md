# vfcmacc.vv v2 Datapath Review

## Decision

Do not start a dedicated complex-FMA datapath yet.

The v1 ISA behavior is covered through RTL ISA regressions, but the v1
engineering loop is not ready to justify a v2 datapath because benchmark and
toolchain evidence are incomplete:

- Node 6 did not produce `dp-cdotp` old/new correctness, cycles, or M4096 data.
- Node 7 did not replace `.insn` with a formal mnemonic because the installed
  LLVM toolchain does not support `vfcmacc.vv`.
- v1 currently relies on a conservative serialization fence for implicit imag
  register hazards, so cycle data is required before deciding whether a new
  datapath or a more precise scoreboard is the right optimization.

## v1 Evidence Available

- Encoding and register layout are frozen:
  `32'b111010???????????001?????1010111`.
- Snitch and Spatz decode recognize `VFCMACC_VV` / `VFCMADD`.
- VFU executes `vfcmacc.vv` as a four-phase sequence:
  `Cfma_RR`, `Cfma_II`, `Cfma_RI`, `Cfma_IR`.
- ISA regressions cover e32/e64/e16, mask, tail, vstart illegal, fflags,
  NaN/Inf, signed zero, rounding mode, and serialization fence hazards.
- v1 uses fixed `.insn` bring-up and does not require binary patching.

## v1 Evidence Missing

- `dp-cdotp` old/new runtime correctness.
- `dp-cdotp` old/new cycle counts for M128 and M4096.
- Runtime frontend/offload stall counters.
- Direct evidence that instruction-count reduction translates into the expected
  frontend/offload pressure reduction for the benchmark.
- Assembler and objdump mnemonic support.

## v2 Questions

### Bit Identity

v2 must not silently reuse the v1 bitwise reference if it introduces a fused
complex-FMA datapath. A fused datapath may produce different rounding, NaN
payload, signed-zero, and `fflags` behavior.

Before v2 RTL starts, the project must choose one policy:

- preserve v1 bit-identical behavior by internally sequencing the same
  operations, or
- define a new fused numerical contract with explicit ULP/NaN/fflags rules.

### Datapath Location

No decision yet between extending fpnew and adding a local Spatz VFU block.

The current preference is no new datapath until benchmark evidence shows that
the v1 bottleneck is not only sequencing/fence overhead.

### Formats

Any v2 datapath must continue to account for e16/e32/e64 or explicitly split
format support into separate nodes. Dropping e16 or e64 would require new ISA
documentation and tests.

### Extensions

`vfcjmacc.vv` remains the first named follow-up extension, but it should not be
combined with the initial v2 datapath decision. It needs its own encoding,
reference model, and tests.

## Entry Criteria for Reopening v2

1. Node 6 benchmark blocker is resolved and old/new M128/M4096 data is recorded.
2. Node 7 mnemonic support is either implemented or explicitly deferred with a
   stable user-facing `.insn` policy.
3. v1 performance data shows one of:
   - frontend/offload pressure is the primary bottleneck and v1 instruction
     count reduction is insufficient, or
   - VFU sequencing/fence overhead dominates and a datapath/scoreboard change
     has a concrete expected benefit.
4. A v2 reference model and numerical policy are written before RTL changes.

## Current Outcome

Stop at v1 multi-phase execution. Do not add fpnew operations, VRF ports, or a
dedicated complex-FMA datapath in this branch.
