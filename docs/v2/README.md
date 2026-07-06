# CFMA v2 Dedicated Datapath Plan

**Date**: 2026-07-07  
**Base**: CFMA v1 four-phase FPU reuse implementation  
**Branch**: `feature/cfma-v2-datapath`

## 1. Goal

v2 aims to turn `vfcmacc.vv` from a software-visible instruction that internally reuses the
existing four-phase FPU sequence into a real dedicated complex-FMA datapath. The target is to
compute one complex multiply-accumulate operation with explicit real/imag operands and write
back both real and imaginary accumulator groups through a verified hardware path.

The v2 goal is not merely to keep the v1 instruction encoding alive. It must prove that the
new datapath is functionally correct, safely integrated into Spatz VFU control, and capable of
supporting future performance claims.

## 2. v1 Baseline to Preserve

v1 remains the architectural correctness baseline:

```text
vd.real += vs1.real * vs2.real - vs1.imag * vs2.imag
vd.imag += vs1.real * vs2.imag + vs1.imag * vs2.real
```

v1 implementation details to preserve unless explicitly superseded:

- `vfcmacc.vv` custom encoding and decode behavior.
- paired register group layout:
  - `vs1.real = vs1`, `vs1.imag = vs1 + LMUL`;
  - `vs2.real = vs2`, `vs2.imag = vs2 + LMUL`;
  - `vd.real = vd`, `vd.imag = vd + LMUL`.
- legal LMUL policy for v1 (`m1/m2/m4`, `m8` illegal).
- `vstart != 0` rejected for v1 unless v2 explicitly designs resumable partial progress.
- mask/tail semantics for active elements.
- fflags accumulation semantics.
- conservative hazard correctness for implicit real/imag register dependencies.

## 3. Non-Goals for the First v2 Slice

The first v2 slice should avoid mixing too many objectives. It should not initially include:

- new ISA variants such as `vfcmacc.vf`, conjugate MAC, rotation, or butterfly operations;
- LLVM auto-vectorization or full register allocator support;
- area/power optimization beyond basic synthesis/build sanity;
- changing the public `vfcmacc.vv` encoding;
- removing the v1 four-phase FPU fallback before the dedicated path has independent proof.

## 4. Datapath Architecture Target

The dedicated path should conceptually perform:

```text
real_out = c.real + a.real * b.real - a.imag * b.imag
imag_out = c.imag + a.real * b.imag + a.imag * b.real
```

where:

```text
a = vs1
b = vs2
c = vd accumulator
```

Required operand groups per vector word:

```text
a.real, a.imag, b.real, b.imag, c.real, c.imag
```

Required result groups per vector word:

```text
result.real -> vd
result.imag -> vd + LMUL
```

Recommended initial microarchitecture:

1. split VRF reads over two cycles to avoid increasing VRF read port count;
2. latch all six operands into a dedicated CFMA request bundle;
3. feed a standalone `fpnew_complex_fma` reference-compatible block;
4. capture `{real, imag, status, tag}` result;
5. write back real and imag over two write beats with correct byte enables;
6. keep v1 four-phase path available behind a parameter or local guard until v2 is proven.

## 5. Implementation Phases

### Phase 0: Restore a Clean Baseline

- Start from the v1 archive commit.
- Confirm `docs/v1/IMPLEMENTATION_SUMMARY.md` describes the current v1 closure.
- Confirm the dedicated writeback guard is still disabled by default before v2 work starts.
- Run baseline checks before touching RTL.

Exit criteria:

- Git status clean.
- v1 ISA regression still passes or any failure is documented as pre-existing.

### Phase 1: Build an Independent Reference/Testbench for `fpnew_complex_fma`

Before enabling the datapath in Spatz, create standalone evidence for the complex arithmetic
unit.

Required coverage:

- e16/e32/e64 format selection;
- normal finite values;
- signed zero behavior;
- NaN/Inf propagation policy;
- rounding modes;
- fflags generation and accumulation;
- randomized comparison against a software/reference model.

Exit criteria:

- The complex FMA block has a reference-driven testbench.
- Failures identify operand tuple, format, rounding mode, expected value, actual value, and flags.

### Phase 2: Define the Spatz VFU Dedicated Request/Response Contract

Specify how one `vfcmacc.vv` vector word becomes one dedicated CFMA request.

Design decisions to freeze:

- request valid/ready timing;
- whether the dedicated unit is single-issue, pipelined, or multi-cycle blocking;
- how backpressure is applied to the existing VFU issue path;
- how tags carry `vd`, `vd+LMUL`, `vsew`, `vl`, mask/tail information, and element index;
- how exceptions/status flags are held until architectural completion.

Exit criteria:

- A written timing table exists for request, result, and writeback.
- The v1 fallback path remains selectable.

### Phase 3: Implement Six-Operand VRF Read Sequencing

Use the existing three-read-port VRF interface by splitting reads:

```text
Cycle R0: read a.real, a.imag, b.real
Cycle R1: read b.imag, c.real, c.imag
```

Required behavior:

- LMUL offset calculation uses the same paired layout as v1.
- Mask data is captured before result byte-enable computation.
- Reads do not expose partial architectural state.
- Illegal layout checks remain before datapath execution.

Exit criteria:

- RTL build passes.
- A directed trace/test can show the six operands captured from the expected register groups.

### Phase 4: Connect Dedicated Compute Path Without Enabling Writeback by Default

Integrate the dedicated compute block and result capture while keeping architectural writeback
guarded until Phase 5 is proven.

Required behavior:

- dynamic FP format selection matches `vsew`;
- status flags are returned with the result;
- result tags retain enough information for real/imag writeback;
- fallback four-phase path remains functional.

Exit criteria:

- RTL build passes with the dedicated compute block instantiated.
- Standalone CFMA block tests still pass.
- v1 fallback regression still passes.

### Phase 5: Implement and Verify Split Real/Imag Writeback

Enable the dedicated writeback FSM only under a controlled parameter or test configuration.

Required behavior:

- write `result.real` to `vd`;
- write `result.imag` to `vd + LMUL`;
- apply mask/tail byte enables correctly for e16/e32/e64;
- arbitrate safely with ordinary FPU writeback;
- avoid marking the architectural instruction complete before both write beats finish.

Exit criteria:

- Dedicated-mode `vfcmacc` ISA regression passes.
- Neighbor FPU regressions such as `vfmacc` and `vfnmsac` still pass.
- Tests cover masked-off lanes and tail lanes for both real and imaginary destination groups.

### Phase 6: Replace v1 Default Only After Correctness Closure

Only after Phases 1-5 pass should v2 make the dedicated datapath the default `vfcmacc.vv`
implementation.

Required behavior:

- the default build uses the dedicated path;
- fallback path remains available for debug until final cleanup;
- documentation states whether v2 is bit-identical to v1 or intentionally fused with different
  rounding behavior.

Exit criteria:

- `vfcmacc` ISA regression passes in default mode.
- v1 fallback comparison exists for representative e16/e32/e64 cases.
- Any non-bit-identical rounding/fflags behavior is documented and accepted.

### Phase 7: Benchmark and Performance Closure

After correctness, measure performance against:

1. no complex instruction baseline;
2. v1 four-phase `vfcmacc.vv`;
3. v2 dedicated datapath `vfcmacc.vv`.

Required benchmark evidence:

- `dp-cdotp` old/new correctness at small sizes first;
- cycle counts;
- instruction-count proxy;
- frontend/offload stall counters if available;
- explanation for any slowdown or timeout.

Exit criteria:

- Performance table records all three variants.
- Speedup claims are made only from completed benchmark runs.

## 6. Expected Efficiency Targets

These are targets, not current evidence:

| Variant | Expected Role | Target Relative Efficiency |
| --- | --- | ---: |
| No complex instruction | baseline | 1.0x |
| v1 four-phase `vfcmacc.vv` | instruction/front-end pressure reduction | about 1.0-1.2x cycle speedup, 4x software instruction reduction |
| v2 dedicated datapath | real compute datapath acceleration | conservative 2x+, ideal 3-4x |

A v2 branch must not claim these numbers as results until benchmark evidence exists.

## 7. Verification Matrix

Minimum checks before any v2 completion claim:

```bash
git diff --check
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

Dedicated-mode completion additionally requires dedicated CFMA unit tests and benchmark evidence.

## 8. First Concrete Next Step

Start v2 with Phase 1, not by enabling the existing guarded writeback prototype. The first
implementation task should be:

```text
Build an independent `fpnew_complex_fma` reference/testbench and freeze its arithmetic,
rounding, and flag behavior before routing it as the default Spatz `vfcmacc.vv` datapath.
```
