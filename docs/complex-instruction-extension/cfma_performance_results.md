# CFMA Performance and Benchmark Evidence

**Date**: 2026-07-06  
**Branch**: `feature/cfma-instruction-extension`  
**Scope**: v1 evidence only

## Scope

This document records the evidence available for the current v1 implementation. The v1
`vfcmacc` path uses the verified four-phase FPU reuse implementation in
`hw/ip/spatz/src/spatz_vfu.sv`. The dedicated CFMA hardware write-back prototype remains
compiled but disabled by `CfmaDedicatedWritebackEn = 1'b0`.

The results below must not be read as proof of dedicated CFMA hardware correctness or
speedup.

## Commands

```bash
git diff --check
```

Result: PASS, exit 0, no output.

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
```

Result: PASS, exit 0. The simulator target was already up to date. Output included the
known Bender `description` warning and then:

```text
make: 'bin/spatz_cluster.vlt' is up to date.
```

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt
```

Result: PASS, exit 0. The software tree was rebuilt, CMake registered
`vfcmacc_illegal` and `vfcmacc`, and the build completed. Output still contains existing
runtime/benchmark warnings, including `dp-cmatmul` inline-function warnings.

```bash
cd hw/system/spatz_cluster/sw/build &&
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

Result: PASS, exit 0. 3/3 tests passed.

```text
vfmacc:  27.18 s
vfcmacc: 137.46 s
vfnmsac: 21.69 s
Total:   186.35 s
```

```bash
cd hw/system/spatz_cluster/sw/build &&
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'spatzBenchmarks-rtl-spatzBenchmarks-rtl-(dp-cdotp_old_M128|dp-cdotp_vfcmacc_M128|dp-caxpy_M256|dp-caxpy_vfcmacc_M256)$' --output-on-failure
```

Result: INTERRUPTED, exit 130, after the `dp-cdotp_old_M128` RTL run exceeded 17 minutes
without completing. The completed sub-results before interruption were:

```text
dp-caxpy_M256:         PASS, 1.59 s
dp-caxpy_vfcmacc_M256: PASS, 1.51 s
dp-cdotp_old_M128:     did not complete within the observed 17-minute window
dp-cdotp_vfcmacc_M128: not reached in this run
```

CTest temporary evidence:

- `hw/system/spatz_cluster/sw/build/Testing/Temporary/LastTest.log.tmp` records the two
  passing `dp-caxpy` probe tests.
- The long-running process was
  `bin/spatz_cluster.vlt sw/build/spatzBenchmarks/test-spatzBenchmarks-dp-cdotp_old_M128`.

## Results

| Target | Result | Time | Claim Supported |
| --- | --- | ---: | --- |
| `riscvTests-rtl-vfmacc` | PASS | 27.18 s | Non-CFMA FMA regression still passes |
| `riscvTests-rtl-vfcmacc` | PASS | 137.46 s | v1 `vfcmacc` ISA behavior still passes |
| `riscvTests-rtl-vfnmsac` | PASS | 21.69 s | Neighbor FMA regression still passes |
| `dp-caxpy_M256` | PASS | 1.59 s | Small baseline benchmark can run to completion |
| `dp-caxpy_vfcmacc_M256` | PASS | 1.51 s | Small vfcmacc benchmark can run to completion |
| `dp-cdotp_old_M128` | Incomplete | >17 min | Benchmark closure remains blocked |
| `dp-cdotp_vfcmacc_M128` | Not reached | n/a | No claim |

## Claims Not Made

- Dedicated CFMA hardware correctness is not claimed.
- Full benchmark correctness is not claimed.
- Speedup is not claimed.
- Step 12 dedicated write-back completion is not claimed.
- The old Step 17 target of `>2x` speedup is not satisfied by this evidence.

## Next Work

Recommended next goal:

```text
Option A: keep v1 four-phase FPU path and clean up or remove the unused dedicated prototype.
```

Alternative future goal:

```text
Option B: reopen dedicated CFMA hardware only after an independent `fpnew_complex_fma`
reference/testbench exists and the path supports dynamic FP formats, packed e16/e32 lanes,
complete complex arithmetic/status flags, mask/tail byte enables, response timing, and
write-back arbitration.
```
