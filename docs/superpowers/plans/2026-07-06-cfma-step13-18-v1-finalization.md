# CFMA Step 13-18 V1 Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the CFMA documentation and verification closure through Step 18 using the current v1 four-phase FPU implementation, without enabling or claiming correctness/performance for the incomplete dedicated CFMA hardware path.

**Architecture:** The current authoritative architecture decision is that v1 `vfcmacc` behavior remains implemented by the verified four-phase FPU reuse path in `spatz_vfu.sv`. The dedicated `fpnew_complex_fma` write-back prototype remains compiled but disabled by `CfmaDedicatedWritebackEn = 1'b0`; Step 13-18 closure must therefore rewrite the remaining old dedicated-hardware steps as v1 closure evidence and v2/deferred work, not as completed dedicated hardware.

**Tech Stack:** SystemVerilog RTL, Spatz VFU, CMake/CTest, Verilator, Markdown docs under `docs/complex-instruction-extension/`.

---

## Non-Negotiable Scope

- Do not enable `CfmaDedicatedWritebackEn`.
- Do not add a default `USE_CFMA_HARDWARE` path.
- Do not claim dedicated CFMA hardware correctness.
- Do not claim benchmark correctness unless fresh benchmark RTL tests pass in this run.
- Do not claim speedup; v1 uses the four-phase FPU path and any performance data is observational.
- If a benchmark fails or times out, record it as an unresolved Step 17 blocker instead of marking benchmark/performance complete.

## File Map

- Modify: `docs/complex-instruction-extension/complex_fma_hardware_design.md`
  - Normalize Step 13-18 statuses to v1 closure and dedicated-hardware deferral.
- Modify: `docs/complex-instruction-extension/PHASE_RESULTS.md`
  - Record fresh Step 13-18 closure evidence and any benchmark blockers.
- Modify: `docs/complex-instruction-extension/GIT_NOTES.md`
  - Record command history and commit intent.
- Modify: `docs/complex-instruction-extension/RESUME_INFO.md`
  - Update recovery state after Step 13-18 closure.
- Create: `docs/complex-instruction-extension/cfma_performance_results.md`
  - Record what performance/benchmark evidence was actually gathered and what is not claimed.
- Create: `docs/complex-instruction-extension/IMPLEMENTATION_SUMMARY.md`
  - Summarize v1 implementation, verification, residual risks, and next work.
- No planned RTL source changes.

## Task 1: Preflight Current State

- [x] **Step 1: Confirm clean starting point**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected: branch `feature/cfma-instruction-extension` and no unstaged source edits except this new plan while it is being created.

- [x] **Step 2: Confirm dedicated path remains disabled**

Run:

```bash
rg -n "CfmaDedicatedWritebackEn|cfma_result_ready|CfmaDedicatedWritebackEn && cfma_result_valid" hw/ip/spatz/src/spatz_vfu.sv
```

Expected: `localparam bit CfmaDedicatedWritebackEn = 1'b0`, `cfma_result_ready` is guarded, and result capture is inside `if (CfmaDedicatedWritebackEn && ...)`.

- [x] **Step 3: Confirm relevant CTest targets exist**

Run:

```bash
cd hw/system/spatz_cluster/sw/build && ctest -N -R 'vfcmacc|dp-cdotp|dp-caxpy' | sed -n '1,220p'
```

Expected: `riscvTests-rtl-...vfcmacc`, `dp-cdotp_*`, and `dp-caxpy_*` targets are listed if `sw/build` exists. If missing, run `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt` before continuing.

## Task 2: Normalize Step 13-18 Documentation

- [x] **Step 1: Update `complex_fma_hardware_design.md` statuses**

Edit the Step 13-18 sections so they explicitly state:

```markdown
- Step 13 v1 decision: keep the four-phase FPU path as the functional implementation; do not enable dedicated hardware by default.
- Step 14 v1 dependency policy: retain the conservative serialization/fence behavior already covered by ISA regressions; detailed dedicated-hardware scoreboard optimization is deferred.
- Step 15 build closure: record fresh `git diff --check`, RTL build, software build, and targeted RTL CTest results from this run.
- Step 16 functional closure: use ISA RTL regression and any benchmark CTest that passes in this run as evidence; if benchmark CTest fails, record it as not complete.
- Step 17 performance closure: create `cfma_performance_results.md`; do not claim speedup unless fresh benchmark data proves it.
- Step 18 final docs: create/update summary docs and record residual v2/dedicated-hardware work.
```

- [x] **Step 2: Ensure old dedicated-hardware acceptance claims are not presented as current truth**

Run:

```bash
rg -n "USE_CFMA_HARDWARE|加速比达到|所有 benchmark 运行完成|dedicated hardware path 启用后|硬件路径.*已验证" docs/complex-instruction-extension/complex_fma_hardware_design.md
```

Expected: any matches are either historical/original-target text or are explicitly marked deferred/not claimed.

## Task 3: Add Performance and Implementation Summary Documents

- [x] **Step 1: Create `cfma_performance_results.md`**

Create a document with these sections:

```markdown
# CFMA Performance and Benchmark Evidence

## Scope

This document records v1 evidence only. The v1 implementation uses the four-phase FPU reuse path. The dedicated CFMA hardware write-back prototype remains disabled by `CfmaDedicatedWritebackEn = 1'b0`.

## Commands

List each fresh benchmark or regression command run in this session, with exit code and key output.

## Results

Record exact per-test CTest timing for passing targets. For failing or timed-out targets, record the target name, failure mode, and log location.

## Claims Not Made

- Dedicated CFMA hardware correctness is not claimed.
- Benchmark correctness is claimed only for targets that pass in this session.
- Speedup is not claimed unless fresh old/new benchmark data proves it.

## Next Work

Option A: keep v1 four-phase FPU path and remove/continue guarding unused dedicated prototype.
Option B: reopen dedicated CFMA hardware only after an independent `fpnew_complex_fma` reference/testbench exists.
```

- [x] **Step 2: Create `IMPLEMENTATION_SUMMARY.md`**

Create a document with these sections:

```markdown
# CFMA Implementation Summary

## Implemented v1 Scope

Summarize encoding, legal/illegal policy, e16/e32/e64 behavior, mask/tail, fflags, serialization fence, and current four-phase FPU execution path.

## Step 13-18 Closure

Summarize how each step is closed for v1 or deferred for dedicated hardware.

## Verification Evidence

List fresh commands and results from this run.

## Residual Risks

List dedicated-hardware gaps: dynamic FP format, packed e16/e32 lanes, complex arithmetic/status flags, mask/tail byte enables, response timing, write-back arbitration, benchmark closure, and speedup evidence.

## Recommended Next Goal

Recommend Option A: keep v1 four-phase FPU path and clean up unused dedicated prototype.
```

## Task 4: Run Verification Closure

- [x] **Step 1: Whitespace check**

Run:

```bash
git diff --check
```

Expected: no output, exit 0.

- [x] **Step 2: RTL build**

Run:

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
```

Expected: exit 0; record whether fresh build or up-to-date.

- [x] **Step 3: Software build**

Run:

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt
```

Expected: exit 0; CMake registers `vfcmacc_illegal` and `vfcmacc`.

- [x] **Step 4: ISA RTL regressions**

Run:

```bash
cd hw/system/spatz_cluster/sw/build &&
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

Expected: 3/3 pass; record per-test times.

- [x] **Step 5: Small benchmark probes**

Run a bounded set first:

```bash
cd hw/system/spatz_cluster/sw/build &&
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'spatzBenchmarks-rtl-spatzBenchmarks-rtl-(dp-cdotp_old_M128|dp-cdotp_vfcmacc_M128|dp-caxpy_M256|dp-caxpy_vfcmacc_M256)$' --output-on-failure
```

Expected: record actual pass/fail. If any fail, do not mark benchmark correctness complete; record blocker and continue docs closure honestly.

## Task 5: Update Evidence Records

- [x] **Step 1: Update `PHASE_RESULTS.md`**

Append a Step 13-18 closure section with:

- commands run,
- exit codes,
- per-test times,
- benchmark probe result,
- explicit non-claims.

- [x] **Step 2: Update `GIT_NOTES.md`**

Append commit intent and verification record for this finalization commit.

- [x] **Step 3: Update `RESUME_INFO.md`**

Record current state: v1 is finalized through documentation/verification closure if verification passed; dedicated hardware remains disabled/deferred; next recommended goal is Option A cleanup.

## Task 6: Final Review and Commit

- [x] **Step 1: Search for forbidden claims**

Run:

```bash
rg -n "Step 12.*已完成|步骤 12.*已完成|dedicated.*correctness|benchmark correctness|speedup|加速比达到|硬件路径.*已验证" docs/complex-instruction-extension docs/superpowers/plans/2026-07-06-cfma-step13-18-v1-finalization.md
```

Expected: matches are only non-claim/deferred statements, historical targets explicitly labeled as old targets, or this plan's guard text.

- [x] **Step 2: Final whitespace check**

Run:

```bash
git diff --check
```

Expected: no output, exit 0.

- [x] **Step 3: Commit**

Run:

```bash
git add docs/complex-instruction-extension docs/superpowers/plans/2026-07-06-cfma-step13-18-v1-finalization.md
git commit -m "[cfma] Finalize v1 CFMA closure docs"
```

Expected: commit succeeds. Do not push unless explicitly requested.

## Self-Review

- [x] The plan preserves the Step 13 v1 architecture decision.
- [x] The plan does not enable dedicated hardware.
- [x] The plan includes fresh build and RTL regression verification.
- [x] The plan records benchmark probes without overclaiming.
- [x] The plan creates final performance and implementation summary documents.
