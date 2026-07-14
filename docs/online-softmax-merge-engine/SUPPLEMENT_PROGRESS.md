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
| 2 | Fair B1/B2-R/B3 baselines and RVV disassembly gate | P0 | pending | pending |
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
