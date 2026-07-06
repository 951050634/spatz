# CFMA Implementation Summary

**Date**: 2026-07-06  
**Branch**: `feature/cfma-instruction-extension`  
**Latest closure commit**: record with `git log --oneline -1`

## Implemented v1 Scope

The current v1 implementation adds and verifies `vfcmacc.vv` as a Spatz custom vector
complex FMA instruction using the existing four-phase FPU reuse path. The v1 scope covers:

- fixed custom encoding and decode integration;
- register layout and legal/illegal policy for paired real/imag register groups;
- e16/e32/e64 ISA behavior covered by `vfcmacc` RTL regression;
- mask/tail behavior covered by the v1 ISA test;
- `vstart != 0` rejected by v1 policy;
- fflags accumulation covered by the v1 ISA test;
- conservative serialization/fence behavior for implicit real/imag register dependencies;
- inline-assembly based software use while installed LLVM mnemonic support remains incomplete.

## Dedicated Hardware Status

A dedicated `fpnew_complex_fma` integration/prototype exists in the RTL, including a split
VRF write-back FSM draft. It is intentionally disabled for v1:

```systemverilog
localparam bit CfmaDedicatedWritebackEn = 1'b0;
```

This disabled path is not the functional source of v1 `vfcmacc` results. It must not be
enabled as the default implementation until it has independent reference/testbench coverage
and fixes the known gaps listed below.

## Step 13-18 Closure

| Step | v1 Closure Status | Evidence / Decision |
| --- | --- | --- |
| Step 13 | Closed as architecture decision | Keep four-phase FPU path for v1; do not enable dedicated hardware by default. |
| Step 14 | Closed for v1 | Retain conservative serialization/fence behavior already covered by ISA regressions; dedicated scoreboard optimization deferred. |
| Step 15 | Closed for current v1 sources | `git diff --check`, RTL build, and `sw.vlt` completed successfully on 2026-07-06. |
| Step 16 | Closed for ISA RTL behavior | `vfmacc/vfcmacc/vfnmsac` RTL regressions passed 3/3 on 2026-07-06. |
| Step 17 | Not closed for full benchmarks/performance | `dp-caxpy_M256` and `dp-caxpy_vfcmacc_M256` passed, but `dp-cdotp_old_M128` did not complete within the observed 17-minute window. No speedup claim. |
| Step 18 | Closed for documentation handoff | This summary and `cfma_performance_results.md` record the final v1 state and residual risks. |

## Verification Evidence

Fresh commands run on 2026-07-06:

```text
git diff --check: PASS, exit 0.
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS, exit 0, target up to date.
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt: PASS, exit 0, CMake registered vfcmacc_illegal/vfcmacc.
ctest riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac): PASS, 3/3, total 186.35 s.
benchmark probe ctest: INTERRUPTED, exit 130, after dp-cdotp_old_M128 exceeded 17 minutes.
```

Detailed benchmark evidence is in `cfma_performance_results.md`.

## Residual Risks

Dedicated hardware remains deferred because it lacks proof for:

- dynamic FP format selection;
- packed e16/e32 lane semantics;
- complete complex arithmetic/status flag semantics;
- mask/tail byte enable behavior;
- response timing and backpressure;
- VRF write-back arbitration under enabled dedicated mode;
- benchmark correctness and speedup evidence.

The `dp-cdotp` RTL benchmark path remains a performance/timeout investigation item and
must not be used as proof of benchmark correctness or speedup.

## Recommended Next Goal

Use Option A:

```text
Keep v1 four-phase FPU path and clean up or remove the unused dedicated prototype.
```

Do not pursue Option B until an independent `fpnew_complex_fma` reference/testbench exists.
