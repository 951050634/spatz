# Online Softmax Merge Engine Supplement Progress

This file is the small, version-controlled progress index for the experiments
specified by `需要补充的若干实验内容.md`.  Detailed raw artifacts must remain
outside Git under a `work-online-merge-*` directory and are referenced from
small manifests only.

## Fixed context

- Specification baseline: 2026-07-15
- Starting commit: `136da62cf3c8fed3ad7088b825661d71bd2b0b20`
- Working branch: `exp/online-softmax-supplement`
- Main CFG: `hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson`
- Main CFG SHA256:
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`
- Physical PPA/energy status: `blocked_external`
- Missing external inputs: target PDK, liberty/LEF, defined PVT/IO/clock
  constraints, and signoff synthesis/P&R/timing/power tools.
- Required next action for P2: provide the above inputs and a fixed physical
  flow; generic resources and RTL toggles must remain explicitly labelled as
  proxies.

## Stage index

| Order | Stage | Priority | Status | Checkpoint / evidence |
| ---: | --- | --- | --- | --- |
| 0 | Isolate worktree and import governing specification | setup | complete | this checkpoint |
| 1 | Benchmark/result framework | P0 | complete | pre-commit smoke below |
| 2 | Fair B1/B2-R/B3 baselines and RVV disassembly gate | P0 | implementation_complete | clean committed anchors pending |
| 3 | Anchors, RVV tails, mandatory size matrices | P0 | pending | pending |
| 4 | Break-even table and fitted scale model | P0 | pending | pending |
| 5 | Full-SMU FSM cycle breakdown and A0/A2 | P0 | pending | pending |
| 6 | C0/C1/C2/C3 concurrency and 16 bank phases | P0 | pending | pending |
| 7 | Yosys Slang generic-resource proxy | P0 | pending | pending |
| 8 | Representative RTL VCD toggle proxy | P0 | pending | pending |
| 9 | Target `expf` B0/B2-F | P1 | pending | pending |
| 10 | Scalar-only A1 | P1 | pending | pending |
| 11 | Trace gating / low-perturbation counter | P1 | pending | pending |
| 12 | Capacity probes and expanded numerical coverage | P1 | pending | pending |
| 13 | ASIC PPA and physical energy | P2 | blocked_external | see fixed context |

## Checkpoint log

### Setup checkpoint

- Objective: preserve unrelated user changes and establish an isolated,
  auditable experiment branch.
- Input: the untracked governing specification from the original worktree.
- Validation: `git status --short --branch`; inspect copied file and CFG hash.
- Result: dedicated worktree `/home/wxt/work-online-merge-supplement` on
  `exp/online-softmax-supplement`; no stash/reset/clean/overwrite was used.
- Known limitation: no experiment implementation or measurement is claimed by
  this checkpoint.

### Stage 1 checkpoint: reproducible benchmark framework

- Objective: implement compact per-case buffers, the common timing and
  correctness protocol, structured CSV/JSON records, host capacity checks,
  command timeouts, and external artifact indexing.
- Input case: `(N,D,seed,kind,repeats) = (1,1,1,main,5)` with one unmeasured
  warm-up for each of B1 and B3.
- Implementation validation:
  - `python3 -m unittest discover -s util/online_softmax_merge/tests -v`:
    18 tests passed;
  - `cmake --build hw/system/spatz_cluster/sw/build --target`
    ` test-spatzBenchmarks-online-softmax-merge --parallel 8`: passed;
  - `check_output` disassembly contains no scalar `fdiv.s`;
  - `snrt_stack_size` is present with value 12 (4 KiB per core);
  - `git diff --check`: passed; `ruff` was unavailable and recorded as
    skipped.
- Preserved failure diagnostic:
  `/home/wxt/work-online-merge-stage1-smoke-20260715-023944`, UTC window
  `2026-07-14T18:39:45+00:00` to `18:49:45+00:00`.  The simulator timed out
  after 600 seconds following complete target-side output.  Hart traces showed
  the approximately 2.8 KiB `main` frame exceeded the runtime's default 1 KiB
  per-core stack, overwrote core 1's saved return address, and caused a return
  to PC zero.  This run remains `timeout` and is not performance evidence.
- Stack-fix smoke:
  `/home/wxt/work-online-merge-stage1-smoke-stackfix-20260715-025453`, UTC
  window `2026-07-14T18:54:53+00:00` to `18:59:42+00:00`.  It produced exactly
  ten finite records, B1/B3 repeats 0 through 4, all `pass`, no failures, and a
  simulator return code of zero.  B1 cycles were 2243/2348/2310/2265/2243;
  B3 cycles were 1095/1063/1063/1063/1063.  These are dirty pre-commit smoke
  values, not formal published performance results.
- Capacity smoke:
  `/home/wxt/work-online-merge-stage1-capacity-smoke-20260715-031133` retained
  one synthetic B1 and B3 record for `(N,D)=(1,5732)`, both marked
  `capacity_skip` with `case_class=capacity`; no simulator command ran.
- Clean committed evidence:
  `/home/wxt/work-online-merge-stage1-clean-20260715-031637`, UTC window
  `2026-07-14T19:16:37+00:00` to `19:21:23+00:00`, commit
  `7a290229abd959de549d60f3dd28972aaa156935`, `git_dirty=false`.  The run
  retained exactly ten records: B1/B3 repeats 0 through 4, all target and host
  statuses `pass`, finite correctness metrics, empty `failures.json`, and a
  simulator return code of zero.  The recorded 64-bit cycles match the target
  `cycles_hi/lo` fields.  B1 cycles are 2243/2348/2310/2265/2243 and B3 cycles
  are 1095/1063/1063/1063/1063.  No Illegal Instruction, host timeout, or
  failure marker is present in the simulator log.
- Clean evidence artifact identity:
  - exact ELF SHA256:
    `878b39541108d7b726cc1dfb24fd8b21cb0a626bff2324836a5217b938f70d7c`;
  - simulator log SHA256:
    `2ed6ced86138637367a3790442d10efd5afbed35ac30eef52f1b7667a2719ea7`;
  - RTL metadata SHA256:
    `ebe6e7c01a12c6fa5e43b36cd781144cc8bfa04e3b761d05c70123253887ae33`;
  - hart 0/1 trace SHA256:
    `9af2b9bfb0c552b5d2f813113fb0f2b6293690eb1c0f476651d06efbc4d556a0`
    and
    `099a4e9ccb76362cd0ea9731a11c64dd7b4f2c2ee45fe979ca36f3237bc0af6f`.
- Stack-fix artifact identity:
  - exact ELF SHA256:
    `878b39541108d7b726cc1dfb24fd8b21cb0a626bff2324836a5217b938f70d7c`;
  - simulator log SHA256:
    `2ed6ced86138637367a3790442d10efd5afbed35ac30eef52f1b7667a2719ea7`;
  - hart 0 trace SHA256:
    `9af2b9bfb0c552b5d2f813113fb0f2b6293690eb1c0f476651d06efbc4d556a0`;
  - hart 1 trace SHA256:
    `099a4e9ccb76362cd0ea9731a11c64dd7b4f2c2ee45fe979ca36f3237bc0af6f`.
- Fixed identities: Git commit at run time
  `82333d594cf187577a1cf38102b6b78450366d70` with `git_dirty=true`; CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`;
  simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`;
  Verilator 5.034; clang 14.0.6, RV32 target.
- Known limitations: only the framework smoke is claimed.  Fair B1/B2-R/B3
  baseline evidence starts in Stage 2.  A clean committed rerun will be added
  as a separate evidence checkpoint.

### Stage 2a checkpoint: B2-R implementation and RVV gate

- Objective: add the required same-semantics B2-R baseline by reusing the
  RTL-aligned scalar weight path and moving the `O[D]` update to a VLA RVV
  load/multiply/FMA/store kernel; reject measurements unless target
  disassembly proves that kernel is present.
- Input case: diagnostic `(N,D,seed,kind,repeats) = (1,1,1,main,3)`, with one
  unmeasured warm-up for B1, B2-R, and B3.
- Implementation validation:
  - `python3 -m unittest discover -s util/online_softmax_merge/tests -v`:
    20 tests passed, including positive and negative RVV disassembly gates;
  - `cmake --build hw/system/spatz_cluster/sw/build --target`
    ` test-spatzBenchmarks-online-softmax-merge --parallel 8`: passed;
  - the saved `online_merge_rvv_update` target symbol contains `vsetvli`, two
    `vle32.v`, `vfmul.vf`, `vfmacc.vf`, and `vse32.v`, with a strip-mining
    back-edge;
  - `check_output` disassembly contains no scalar `fdiv.s`;
  - `snrt_stack_size` is present with value 13 (8 KiB per core);
  - `git diff --check`: passed; `ruff` was unavailable and recorded as
    skipped.
- Dirty pre-commit diagnostic:
  `/home/wxt/work-online-merge-stage2-precommit-20260715-100842`, UTC window
  `2026-07-15T02:08:42+00:00` to `02:13:23+00:00`.  It retained exactly nine
  finite records, B1/B2-R/B3 repeats 0 through 2, all target and host statuses
  `pass`, an empty `failures.json`, and a zero simulator return code.  Median
  cycles were B1 2480, B2-R 1973, and B3 1113.  Because `git_dirty=true`, these
  values are validation-only and are not formal performance evidence.
- Diagnostic artifact identity:
  - exact ELF SHA256:
    `557ff13d45751efe30cb3356e9752ef6cb0ac1b79b31b4f3a41a4cbad198f95c`;
  - simulator log SHA256:
    `6174698b5896a76677118605facdc1aba79480a81e7b9b931bef4e7315eacdd5`;
  - RVV disassembly snippet SHA256:
    `0569f0f89bad011819932d99f55155818b33de27d83a40e639ccd6c0ad3e5b76`;
  - full objdump/gate log SHA256:
    `df33ddfd4940a1fa56cfcd1ccaf4f571c42c30622150ca5f445b43d4a01700d9`.
- Fixed identities: run-time Git commit
  `a494087a3aba5bb74e98f3d26763f55938877bf8` with `git_dirty=true`; CFG
  SHA256 `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`;
  simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`;
  LLVM/Clang/objdump 14.0.6; Verilator 5.034; Python 3.12.3.
- Known limitations: this checkpoint proves implementation and smoke
  correctness only.  Stage 2 remains incomplete until clean committed anchor
  evidence is retained; RVV tail and the mandatory scale matrices belong to
  Stage 3.
