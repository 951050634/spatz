## Material Passport
Origin Skill: academic-research-suite/experiment-agent
Mode: run
Date: 2026-10-29 Asia/Shanghai
Verification Status: see validation.md and experiment_manifest.json

Source B: /home/wxt/work-online-merge-supplement
Remote: https://github.com/951050634/spatz.git
B branch: exp/online-softmax-supplement
B HEAD: d624d589b00de2b9c6dfbcd43b67209f5088f9c5
GitHub branch tip at deployment: e8dc802bf35fa0a4bfc6bf7d1cc1ddfdb1d23afd
GitHub default HEAD at deployment: a541d3cfb658b8490ef04c1e53b60a103da3723f
GitHub experiment branch is behind B; missing RTL includes FP16 leading-zero
normalization and exposed cluster SMU synthesis parameters. ECS cloned GitHub
and fetched a private B-generated Git bundle. No source was pushed publicly.
B worktree had pre-existing paper/AGENTS changes; none were deployed.
Top-level git submodule status is empty; hardware dependencies use Bender 0.29.1.

C: smu-ecs; Ubuntu 24.04.5; 8 vCPUs; 30 GiB RAM; 99 GiB disk (~83 GiB initially free).
Task root C: /home/smu/smu-native-isa-20261029
Branch C: experiment/native-isa-20261029; software adaptation commits are local only.
Formal source is worktree ablation at commit 779621b7ab78d55e89466d8e258265f258b7473a.
Functional RTL is unchanged; simulation-only vector traffic/stall counters were added
inside translate_off. All formal paths use this same instrumented simulator.
Default DRAM cluster; 128 KiB TCDM,
16 banks, 2 cores, 4 FPUs/core, VLEN=512. SmuScalarOnly=0 preserves both
mode-2 Full and mode-3 Scalar implementations for the ablation on one simulator.
This is functional default-cluster evaluation, not a new area measurement.

Tools copied from B: Verilator 5.034; PULP LLVM 14.0.6
(b494f2d8dde88723026db8ec16ac6c7ee1e140ca); existing PULP riscv32 GCC
7.1.1 newlib/libgcc support; existing libfesvr.a and headers; Bender 0.29.1.
CMake 3.28.3 was copied from B, with its modules and required shared libraries.
C uses native GCC/G++ 13 for the Verilator model. Exact versions/hashes are in logs.
Python dependencies installed into a user directory because sudo/venv were unavailable.
Official PyPI was slow; switched to the Aliyun mirror. Pre-generated input headers
were produced on B with NumPy 1.26.4, matching B's installed historical environment.
All headers retain seed 1, identical Q/K/V for paired paths; tile-size changes only
change PHASE5_TILE_KEYS, not the input tensors. Headers are archived for reproduction.

Build repairs: copied ignored bootdata.cc, bootdata_bootrom.cc, link.ld and
memories.json from B's generated default cluster files. Kept checked-in boot ROM
and wrapper with make -o, avoiding timestamp-triggered regeneration. Exported
VERILATOR_ROOT to resolve the migrated tool's original compiled-in B prefix.
Bender dependencies copied from B. Bender.local path overrides and a runtime
lockfile resolve these exact checkout contents offline; original Bender.lock is
saved. Final delivery includes source/dependency content hashes and build commands.

Measurement contract: original benchmark timers unchanged. Recurrence/control
includes software recurrence or complete OMERGE issue/execute/response/status
consumption (or MMIO register programming/start/polling for matched control).
Inclusive merge additionally includes the common unchanged RVV update and state
swap. Native Core includes score/local-tile-state/merge/output-copy work, after
resident Q/K/V, excluding host projections and input allocation/loading.
Once-per-workload OMCFG/INIT is measured separately as workload_setup; historical
raw timers exclude it. CSVs preserve the raw timers and explicitly add setup to
recurrence, merge and core totals in separate columns, with setup-inclusive
speedups. These additions are accounting sums, not new contiguous timed windows.
Config-state diagnostic MMIO reads, activity-bracket MMIO markers, validation,
output hashes and output dumps remain outside the raw Native Core timer.
The ISA main path performs no MMIO SMU configuration/start/poll operations;
existing hardware observers verify this dynamically. Runtime config selector
retains unused MMIO configuration code in the ELF, as in Phase 8C.

Capacity: actual benchmark uses seven N*D FP32 matrices, one N*B score tile,
eight N-element scalar arrays, 256-byte allocation rounding and runtime reserve.
With the current 16,512-byte reserve, footprint is
align256(28*N*D + 4*N*B + 32*N) + 16512.
Limit remains the existing 80% of 131,072 bytes (104,857 bytes); no allocator,
TCDM, baseline, vector strip-mining cap (AVL<=8) or timing window was relaxed.
N16/D256/B4 and N32/D128/B8 exceed even physical capacity with runtime reserve;
they are BLOCKED, not measured. All other requested points fit the existing limit.

Formal main paths: Software Recurrence+RVV vs OMCFG/INIT+OMERGE Scalar SMU+RVV.
Matched MMIO controls use full per-tile mode-3 setup/start/polling, not the historical
Phase 8C MMIO-config-plus-OMERGE hybrid. Full SMU uses mode 2 via MMIO because the
implemented OMERGE adapter fixes mode=3; compare Full against matched mode-3 MMIO
Scalar+RVV and report control/scope separately from the main ISA dataset.

Dimension scope: the existing PHASE5_D is both Q/K dot-product dimension and V/output dimension. No separate dk parameter exists. This run preserves that implementation and labels D scaling as a joint head/output sweep. It cannot isolate the effect of dv at fixed dk. This limitation was surfaced to the user while baseline, sequence and tile runs continued.

Normalization epoch: ONLINE_MERGE_MIXED_RECIPROCAL is enabled for every formal
software, ISA, MMIO and Full run, matching historical Phase 5 Native
experiments/phase5_native_online_attention/formal/manifest.json and paper
implementation choice. Both -DSPATZ_DISABLE_DASM and
-DONLINE_MERGE_MIXED_RECIPROCAL are explicitly supplied as DEFS. Build output is
bin/spatz_cluster.recip.vlt, separate work-vlt-recip to avoid stale objects.
Initial default iterative-division diagnostics were stopped and archived under
../history-division-diagnostic; none of their cycles enter this formal dataset.
Full-mode rvv_output_update is an empty timer pair, not an actual RVV workload.

Generated opcode encoding.h was copied from B into the formal worktree after an
initial missing-header build failure; original failure logs are retained.

ISA timing correction: source commit 9b8adb6b adds a dependent ADD immediately
after OMERGE inside the same asm block. Old N16/D64 LLVM scheduling placed the
cycle read before the status-dependent branch, measuring only issue time
(48 cycles for three calls) and charging engine wait to orchestration. All final
ISA rows use the dependent status read; four earlier ISA points are rerun. Old
records are diagnosis only. The existing three timer definitions and RVV code
remain unchanged. The 13 non-ISA PT_LOAD executable images are byte-identical
before/after this source-only change, verified in
non_isa_loaded_image_equivalence.json; their measurements remain reusable.
RTL model source remains 779621b7 and its simulator hash is unchanged.

Final source commit: 9b8adb6befae3eb45de50cb97229d1a69bfc9f5d
Simulator SHA256: c6ba3633fa7d8ebed9e451f0889f9cb5b9c3d0e6e43e6d165ad32d4afb3ea9b0
Observed run status totals: {"BLOCKED": 4, "FAILED": 1, "ISA_EVIDENCE_FAILED": 2, "PASS": 17}

Update: preserved original results and ZIP. Existing source 9b8adb6befae3eb45de50cb97229d1a69bfc9f5d and simulator c6ba3633fa7d8ebed9e451f0889f9cb5b9c3d0e6e43e6d165ad32d4afb3ea9b0 reused. Two ISA cases were rebuilt and rerun; N32/B4 was recovered from an intact physical execution. Final valid configurations: 9, including 8 requested sweep points.
