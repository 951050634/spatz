# CFMA Step 13 V1 Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the current CFMA work as a correct v1 implementation by keeping the existing four-phase FPU path as the functional `vfcmacc` path, keeping the incomplete dedicated CFMA write-back path disabled, documenting the Step 13 architecture decision, and rerunning the software/RTL verification closure.

**Architecture:** The v1 behavior source is the already verified four-phase FPU CFMA path in `spatz_vfu.sv`. The Step 12 dedicated write-back prototype remains compiled but disabled with `CfmaDedicatedWritebackEn = 1'b0`; Step 13 records that dedicated hardware cannot become the default path until it has dynamic FP format support, packed e16/e32 lane semantics, correct complex arithmetic, status flags, mask/tail byte enables, response timing, and arbitration verification.

**Tech Stack:** SystemVerilog RTL, Spatz VFU, fpnew, RVV ISA tests, CMake software build, Verilator RTL simulation, project docs under `docs/complex-instruction-extension/`.

---

## Goal Tool Objective

Use this as the long-running goal objective when ready:

```text
Execute docs/superpowers/plans/2026-07-06-cfma-step13-v1-stabilization.md end-to-end: stabilize CFMA Step 12/13 as a v1 four-phase FPU implementation, keep the incomplete dedicated CFMA write-back path disabled, update architecture and progress docs, run sw.vlt, RTL build, and vfcmacc/vfmacc/vfnmsac regressions, then prepare a clean commit summary without claiming dedicated hardware correctness or benchmark speedup.
```

Do not mark the goal complete until all verification commands in Task 5 have been run in the same goal run and their results are recorded.

## File Map

- Modify: `hw/ip/spatz/src/spatz_vfu.sv`
  - Owns VFU FPU operation routing, existing four-phase CFMA execution, and the disabled Step 12 dedicated write-back prototype.
- Modify: `docs/complex-instruction-extension/complex_fma_hardware_design.md`
  - Owns the 18-step hardware implementation plan and Step 12/13 acceptance status.
- Modify: `docs/complex-instruction-extension/PHASE_RESULTS.md`
  - Owns auditable phase evidence, verification commands, and residual risks.
- Modify: `docs/complex-instruction-extension/GIT_NOTES.md`
  - Owns commit intent, command history, and Git operation records.
- Modify: `docs/complex-instruction-extension/RESUME_INFO.md`
  - Owns the next-session recovery state.
- Optional create: `docs/complex-instruction-extension/step13_architecture_decision.md`
  - Use this only if the Step 13 decision grows too large for `complex_fma_hardware_design.md`.

## Task 1: Preflight Current State

**Files:**
- Read: `hw/ip/spatz/src/spatz_vfu.sv`
- Read: `docs/complex-instruction-extension/RESUME_INFO.md`
- Read: `docs/complex-instruction-extension/PHASE_RESULTS.md`
- Read: `docs/complex-instruction-extension/GIT_NOTES.md`

- [x] **Step 1: Capture current Git state**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected:

```text
## feature/cfma-instruction-extension
 M docs/complex-instruction-extension/GIT_NOTES.md
 M docs/complex-instruction-extension/PHASE_RESULTS.md
 M docs/complex-instruction-extension/RESUME_INFO.md
 M docs/complex-instruction-extension/complex_fma_hardware_design.md
 M hw/ip/spatz/src/spatz_vfu.sv
```

- [x] **Step 2: Confirm the dedicated write-back path is guarded**

Run:

```bash
rg -n "CfmaDedicatedWritebackEn|cfma_result_ready|cfma_result_valid && !cfma_wb_pending_q|cfma_wb_we \\?" hw/ip/spatz/src/spatz_vfu.sv
```

Expected checks:

```text
localparam bit CfmaDedicatedWritebackEn = 1'b0;
assign cfma_result_ready = CfmaDedicatedWritebackEn ? !cfma_wb_pending_q : 1'b1;
if (CfmaDedicatedWritebackEn && cfma_result_valid && !cfma_wb_pending_q) begin
```

- [x] **Step 3: Inspect the current diff before editing**

Run:

```bash
git diff -- hw/ip/spatz/src/spatz_vfu.sv docs/complex-instruction-extension/RESUME_INFO.md docs/complex-instruction-extension/PHASE_RESULTS.md docs/complex-instruction-extension/GIT_NOTES.md docs/complex-instruction-extension/complex_fma_hardware_design.md
```

Expected: only the dedicated write-back guard/prototype and status documentation are modified.

## Task 2: Lock Step 13 Architecture Decision

**Files:**
- Modify: `docs/complex-instruction-extension/complex_fma_hardware_design.md`
- Modify: `docs/complex-instruction-extension/PHASE_RESULTS.md`
- Modify: `docs/complex-instruction-extension/RESUME_INFO.md`

- [x] **Step 1: Ensure Step 12 is not marked complete**

Run:

```bash
rg -n "步骤 12|Step 12|dedicated hardware path|不能标记完成|默认禁用|CfmaDedicatedWritebackEn" docs/complex-instruction-extension/complex_fma_hardware_design.md docs/complex-instruction-extension/PHASE_RESULTS.md docs/complex-instruction-extension/RESUME_INFO.md
```

Expected: each file states that Step 12 is in progress, the dedicated write-back prototype is disabled, and dedicated hardware correctness is not claimed.

- [x] **Step 2: Add or keep this Step 13 decision text**

In `docs/complex-instruction-extension/complex_fma_hardware_design.md`, under Step 13, ensure this exact decision is present or equivalently recorded:

```markdown
**当前建议（2026-07-06）**：先做架构决策，不要直接默认启用
`USE_CFMA_HARDWARE`。当前已知可工作的 v1 功能路径是四阶段 FPU 复用实现；专用硬件
路径必须先补齐动态 FP format、packed lane、complex arithmetic、status flags、
mask/tail 和写回时序验证后才能作为默认路径。
```

- [x] **Step 3: Record the two allowed future paths**

In `docs/complex-instruction-extension/RESUME_INFO.md`, keep the next-step recommendation as:

```markdown
1. 不要继续把当前 Step 12 草稿推进为完成态；它只应作为 disabled prototype
   保留，避免破坏已通过的 ISA 行为。
2. 做 Step 13 控制架构决策：
   - v1 保守路线：明确保留现有四阶段 FPU 路径作为功能实现，删除或继续 guard
     未完成的专用写回路径。
   - 专用硬件路线：重新设计完整 dedicated CFMA path，包括动态 FP format、
     packed e16/e32 lanes、正确 complex arithmetic、status flags、mask/tail byte
     enable、response timing 和 VRF 写回仲裁。
3. 若选择专用硬件路线，先补 `fpnew_complex_fma` 的独立 reference/testbench，
   再重新打开 `CfmaDedicatedWritebackEn`，不能直接启用当前草稿。
```

## Task 3: Make RTL Guard Intent Unambiguous

**Files:**
- Modify: `hw/ip/spatz/src/spatz_vfu.sv`

- [x] **Step 1: Confirm the guard is local and default-disabled**

Run:

```bash
sed -n '1390,1575p' hw/ip/spatz/src/spatz_vfu.sv
```

Expected: `CfmaDedicatedWritebackEn` is declared in the FPU generate block, set to `1'b0`, and used to guard both `cfma_result_ready` backpressure and result capture.

- [x] **Step 2: If the explanatory comment is missing, add it**

Use `apply_patch` so the localparam area reads:

```systemverilog
    // Dedicated CFMA result write-back is intentionally disabled for v1.
    // The existing four-phase FPU path is the verified architectural path.
    // Re-enable only after the dedicated unit supports dynamic FP formats,
    // packed e16/e32 lanes, complete complex arithmetic/status flags, and
    // mask/tail write-back semantics.
    localparam bit CfmaDedicatedWritebackEn = 1'b0;
```

- [x] **Step 3: Confirm no normal `vfcmacc` result can be overwritten by disabled dedicated write-back**

Run:

```bash
rg -n "assign vrf_we_o|assign vrf_wbe_o|assign vrf_wdata_o|vrf_waddr_o = cfma_wb_we|CfmaDedicatedWritebackEn && cfma_result_valid" hw/ip/spatz/src/spatz_vfu.sv
```

Expected:

```text
vrf_waddr_o = cfma_wb_we ? cfma_wb_addr : vrf_addr_t'(result_tag.vd_addr);
assign vrf_we_o    = cfma_wb_we ? 1'b1 : vreg_we;
assign vrf_wbe_o   = cfma_wb_we ? cfma_wb_be : vreg_wbe;
assign vrf_wdata_o = cfma_wb_we ? cfma_wb_data : vreg_wdata;
if (CfmaDedicatedWritebackEn && cfma_result_valid && !cfma_wb_pending_q) begin
```

Because `CfmaDedicatedWritebackEn` is `1'b0`, `cfma_wb_pending_q` is never newly set by the dedicated result path, so `cfma_wb_we` remains inactive in normal v1 operation.

## Task 4: Update Evidence Records

**Files:**
- Modify: `docs/complex-instruction-extension/PHASE_RESULTS.md`
- Modify: `docs/complex-instruction-extension/GIT_NOTES.md`
- Modify: `docs/complex-instruction-extension/RESUME_INFO.md`

- [x] **Step 1: Record the verification commands to be run**

In both `PHASE_RESULTS.md` and `GIT_NOTES.md`, ensure the Step 12/13 record includes these exact command names:

```text
git diff --check
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build &&
PATH="$PWD/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

- [x] **Step 2: Record the non-goals**

In the same records, ensure these non-goals are explicit:

```text
Do not claim dedicated CFMA hardware correctness.
Do not claim benchmark correctness.
Do not claim speedup.
Do not mark Step 12 complete.
```

Use Chinese wording consistent with surrounding docs.

## Task 5: Run Full Verification Closure

**Files:**
- Read: build logs from terminal output.
- Modify after running: `docs/complex-instruction-extension/PHASE_RESULTS.md`
- Modify after running: `docs/complex-instruction-extension/GIT_NOTES.md`

- [x] **Step 1: Run whitespace check**

Run:

```bash
git diff --check
```

Expected:

```text
```

The command should produce no output and exit 0.

- [x] **Step 2: Run RTL build**

Run:

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
```

Expected: exit 0. Accept either a fresh Verilator build or:

```text
make: 'bin/spatz_cluster.vlt' is up to date.
```

- [x] **Step 3: Run software build**

Run:

```bash
PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt
```

Expected: exit 0. The log should show CMake registering `vfcmacc_illegal` and `vfcmacc`, then completing software target compilation. Existing runtime/benchmark warnings and DWARF address range diagnostics may appear; record them as existing diagnostics, not failures, if the command exits 0.

- [x] **Step 4: Run targeted RTL regressions**

Run:

```bash
cd hw/system/spatz_cluster/sw/build &&
PATH="/home/wxt/spatz-cfma/.venv/bin:$PATH" ctest -R 'riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac)$' --output-on-failure
```

Expected:

```text
100% tests passed, 0 tests failed out of 3
```

Record the per-test times printed by this run. Do not reuse older timing numbers.

- [x] **Step 5: Update docs with fresh verification output**

Edit `PHASE_RESULTS.md` and `GIT_NOTES.md` so the Step 12/13 record contains the actual outputs from Steps 1-4:

```text
git diff --check: PASS, exit 0.
bin/spatz_cluster.vlt: PASS, exit 0, [fresh build or up-to-date summary].
sw.vlt: PASS, exit 0, CMake registered vfcmacc_illegal/vfcmacc targets.
ctest vfcmacc/vfmacc/vfnmsac: PASS, 3/3, [actual per-test times].
```

## Task 6: Final Review Before Commit

**Files:**
- Review: all modified files.

- [x] **Step 1: Run status and summary**

Run:

```bash
git status --short --branch
git diff --stat
```

Expected modified files:

```text
docs/complex-instruction-extension/GIT_NOTES.md
docs/complex-instruction-extension/PHASE_RESULTS.md
docs/complex-instruction-extension/RESUME_INFO.md
docs/complex-instruction-extension/complex_fma_hardware_design.md
hw/ip/spatz/src/spatz_vfu.sv
```

If this plan file is created in the same goal run, include:

```text
docs/superpowers/plans/2026-07-06-cfma-step13-v1-stabilization.md
```

- [x] **Step 2: Search for forbidden success claims**

Run:

```bash
rg -n "Step 12.*已完成|步骤 12.*已完成|dedicated.*correctness|speedup|加速比|benchmark correctness|硬件路径.*已验证" docs/complex-instruction-extension docs/superpowers/plans/2026-07-06-cfma-step13-v1-stabilization.md
```

Expected: no current-progress statement claims Step 12 completion, dedicated hardware correctness, benchmark correctness, or speedup. Historical records may mention benchmark targets or speedup goals; do not edit unrelated history unless it is presented as current status.

- [x] **Step 3: Run final whitespace check**

Run:

```bash
git diff --check
```

Expected: exit 0 with no output.

## Task 7: Commit Preparation

**Files:**
- Stage only the files intentionally changed by this plan.

- [x] **Step 1: Stage the current stabilization work**

Run:

```bash
git add hw/ip/spatz/src/spatz_vfu.sv \
  docs/complex-instruction-extension/RESUME_INFO.md \
  docs/complex-instruction-extension/PHASE_RESULTS.md \
  docs/complex-instruction-extension/GIT_NOTES.md \
  docs/complex-instruction-extension/complex_fma_hardware_design.md \
  docs/superpowers/plans/2026-07-06-cfma-step13-v1-stabilization.md
```

- [x] **Step 2: Inspect staged diff**

Run:

```bash
git diff --cached --stat
git diff --cached -- hw/ip/spatz/src/spatz_vfu.sv | sed -n '1,220p'
```

Expected: staged RTL diff only guards/disables the dedicated write-back prototype and does not remove the verified four-phase FPU path.

- [x] **Step 3: Commit**

Run:

```bash
git commit -m "[cfma] Guard incomplete dedicated CFMA writeback path"
```

Expected: commit succeeds. After commit, run:

```bash
git status --short --branch
git log --oneline -3
```

Expected: the new commit appears at the top. Do not push unless explicitly requested.

## Task 8: Post-Commit Next-Step Note

**Files:**
- Modify only if continuing beyond this stabilization commit: `docs/complex-instruction-extension/RESUME_INFO.md`

- [x] **Step 1: Decide the next goal**

Choose one next goal and record it in the final response:

```text
Option A: Keep v1 four-phase FPU path and clean up unused dedicated prototype.
Option B: Reopen dedicated CFMA hardware path with an independent fpnew_complex_fma reference/testbench first.
```

Recommended next goal after this plan:

```text
Option A: Keep v1 four-phase FPU path and clean up unused dedicated prototype.
```

Reason: current tests already validate the four-phase FPU path; the dedicated path has multiple known semantic gaps and should not be expanded inside the same stabilization commit.

## Self-Review Checklist

- [x] The plan keeps Step 12 out of completed status.
- [x] The plan verifies `sw.vlt`, RTL build, and targeted RTL regressions.
- [x] The plan does not claim dedicated hardware correctness.
- [x] The plan does not claim benchmark correctness or speedup.
- [x] The plan gives an exact goal objective for long-running goal execution.
- [x] The plan leaves push/remote operations out unless the user explicitly requests them.
