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
| 2 | Fair B1/B2-R/B3 baselines and RVV disassembly gate | P0 | complete | Stage 2b clean anchors |
| 3 | Anchors, RVV tails, mandatory size matrices | P0 | in_progress | anchors complete; tails/matrices pending |
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

### Stage 2b checkpoint: clean committed anchor evidence

- Objective: establish formal, clean-commit B1/B2-R/B3 anchor evidence after
  the Stage 2a implementation gate.
- External evidence:
  `/home/wxt/work-online-merge-stage2-clean-20260715-103300` (approximately
  1.7 GiB, retained outside Git because the simulator emits large `.dasm`
  traces).
- UTC measurement window: `2026-07-15T02:33:01+00:00` through
  `2026-07-15T03:29:07+00:00`.
- Run identity: commit
  `ded4a6720334d5473dcef0ab889dfe601968e07e`, `git_dirty=false`; CFG
  `hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson`, SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`;
  simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
- Tool identity: LLVM/Clang/objdump 14.0.6, Verilator 5.034, Python 3.12.3,
  and CMake 3.28.3.
- Inputs: seed 1, `main`, three measured repeats after one unmeasured warm-up
  for each implementation at `(N,D)=(1,1),(8,32),(16,64)`.  The exact
  per-command argv, timeout, return code, and timestamp are in
  `commands.json`; the top-level runner used the retained `cases.json`.
- Result: exactly 27 records (`3 cases * 3 implementations * 3 repeats`).
  Every target and host status is `pass`, every simulator command returned
  zero, every correctness and derived metric is finite, `failures.json` is
  empty, and each parsed 64-bit cycle value equals its target `cycles_hi/lo`
  reconstruction.  No Illegal Instruction, timeout, correctness failure, or
  failure marker was found.
- Measured cycles (median/min/max):

  | N | D | Implementation | Median | Min | Max |
  | ---: | ---: | --- | ---: | ---: | ---: |
  | 1 | 1 | B1 | 2480 | 2354 | 2481 |
  | 1 | 1 | B2-R | 1973 | 1934 | 1990 |
  | 1 | 1 | B3 | 1113 | 1113 | 1162 |
  | 8 | 32 | B1 | 99840 | 99740 | 99940 |
  | 8 | 32 | B2-R | 13155 | 12937 | 13304 |
  | 8 | 32 | B3 | 3268 | 3265 | 3279 |
  | 16 | 64 | B1 | 370559 | 369758 | 371684 |
  | 16 | 64 | B2-R | 25406 | 25291 | 25550 |
  | 16 | 64 | B3 | 9565 | 9556 | 9664 |

- Top-level evidence SHA256:
  - `cases.json`:
    `792bf71a5ecb3eb2266eba78520aa76057e9d3a77b3115196e9f8a1ff07d0f94`;
  - `runner.log`:
    `fee9823a7dc776f283e8237773cf0042459fe7215ebc0440cd201c5ed23e9dea`;
  - `run_manifest.json`:
    `edd7e9b5357c7d754cace42902e845e7f465f8d2c6da4356f250b5dcaeec609f`;
  - `records.json`:
    `71d8bf77fe949b11979ef761925144dc470b17a25dcee2fe24979a1351ba3a1d`;
  - `records.csv`:
    `ee971a4fa76420f71a56feb840ef5c1819023b5a36816cab79f0623844de3059`;
  - `summary.json`:
    `c5cf7226725da45596b8b673bab0b5aa237f3ed95b59f104e940ce184d92a8c6`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `commands.json`:
    `6f9852925bc059fd6c926bdd40ada7f9cd35e3adafc435fdcbe771a41f54880f`;
  - `artifact_manifest.json`:
    `8d8e3c245f46d42729d903a778dd272876db616724672e7229161e00bf242f7b`.
- Per-case ELF, simulator-log, and RVV-snippet SHA256 respectively:
  - `(1,1)`:
    `d85a702f69a6a258b4ae769013c16754bd265ca72e12c5b98feb37f6ddaacbc0`,
    `6174698b5896a76677118605facdc1aba79480a81e7b9b931bef4e7315eacdd5`,
    `0569f0f89bad011819932d99f55155818b33de27d83a40e639ccd6c0ad3e5b76`;
  - `(8,32)`:
    `8953e074f748b4e6a885d2f5103eb06947203393742f482ba6a0a5abeaf40407`,
    `db31aa5a43ecd713fae0f64fcff28c538ee1fe32988f126d4d30f6a2d127ded4`,
    `28790a32ff033c575ae9afdfd9d3eb0efdde41002b1679474f6187186973a808`;
  - `(16,64)`:
    `d3675aaa946fb6bfb4e506ef24e0d360784fd92f3e27a1008cef84b187af1ef5`,
    `abc3b631ef8069d2d27dd49bd2b6f5ccd48a54fb16239cb08a64915fd5db7a47`,
    `a8986ee68f72dd350da6e6bd1b7d6d7a68070f59f2a3700e685ec9c007deea57`.
- Validation:
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s`
    ` util/online_softmax_merge/tests -v`: 20 tests passed;
  - `cmake --build hw/system/spatz_cluster/sw/build --target`
    ` test-spatzBenchmarks-online-softmax-merge --parallel 8`: passed;
  - `llvm-objdump -d --no-show-raw-insn --mattr=+v <elf>` proves the required
    VLA RVV instructions and strip-mining back-edge in every retained ELF;
  - `check_output` contains no scalar `fdiv.s`, and the raw
    `snrt_stack_size` object value is 13 (8 KiB/core);
  - all 29 artifact-manifest entries were independently rehashed successfully;
  - record/status/finiteness/cycle reconstruction and failure-marker gates
    passed; `git diff --check` passed; `ruff` was unavailable and remains
    `skipped_unavailable`.
- Known limitation: these are same-CFG Verilator cycle/runtime proxies.  They
  are not physical PPA, frequency, power, energy, or critical-path evidence;
  Stage 3 must still complete the RVV tails and mandatory size matrices.

### Stage 3a checkpoint: retained RVV tail failure

- Objective: exercise the first nontrivial VLA/tail dimensions at `N=1`,
  seed 1, `main`, with one warm-up and three measured repeats per
  implementation.
- External evidence:
  `/home/wxt/work-online-merge-stage3-tail-a-clean-20260715-114400`
  (approximately 636 MiB, retained outside Git).
- UTC window: `2026-07-15T03:45:29+00:00` through
  `2026-07-15T04:05:56+00:00`.
- Run identity: commit
  `ea1eaeca2c5db5bf8868f0f8752491f62039977f`, `git_dirty=false`; the CFG,
  simulator, and tool identities are unchanged from Stage 2b.
- Inputs: `D={7,15,17,31}`; the retained `cases.json` and `commands.json`
  contain every exact case, command, timeout, return code, and timestamp.
- Preserved result: 36 records were retained.  B1 and B3 passed every repeat;
  B2-R passed all repeats at `D=7` and `D=17`, failed all three repeats at
  `D=15`, and failed repeat 1 at `D=31`.  The runner exited 1 and retained two
  first-failure records:
  - `D=15`, repeat 0, `O[0][9]`: expected bits `1060333124`, actual bits
    `1065266780`;
  - `D=31`, repeat 1, `O[0][17]`: expected bits `3176287040`, actual bits
    `3205216679`.
- The failing simulator commands returned 255 and are retained as
  `tool_error` commands; the corresponding target/result records remain
  `correctness_fail`.  Passing cases returned zero.  No failure, command, or
  repeat was removed or relabelled as a pass.
- Top-level evidence SHA256:
  - `cases.json`:
    `70dd44a34aeecddd2068c4e6288866a86fc2a3bf4c3c5b1179c1e27edfd81894`;
  - `runner.log`:
    `85d9d7b10f398c6387a9285ce2f8aed82b235711c140b967cda0b6b44d517179`;
  - `run_manifest.json`:
    `20634357be1e2c9a266435648e62a278faeb72cf384a38d1773474dd172fbe88`;
  - `records.json`:
    `5c2fe9c17b65a424fed3d646ed65f3abbe2875037abc3476c87a3699bef46840`;
  - `records.csv`:
    `0218889101d45b99648a9d10827e35220c6fca9e7a3a1a9313ce8673322781fd`;
  - `summary.json`:
    `3549c849fdba191f4da33e563af4ed32334daeaf3896bc591bf28dc1ee5395d8`;
  - `failures.json`:
    `9f74e4d19af99bea139faec83129a429654f44de7bc811c83a1fa3c2ddf00c99`;
  - `commands.json`:
    `9b9f1341da330b36534880a35efff2eadf53f4019b9171b8925f32f3b83c7fef`;
  - `artifact_manifest.json`:
    `1c226142d99f055e4936ad5344b68571100098cf3806e0bd1db8bc2625359609`.
- Validation: all 38 artifact-manifest entries rehashed successfully; all
  records and derived metrics are finite; every parsed cycle count matches the
  raw target `cycles_hi/lo`; `failures.json` exactly identifies the two failed
  workloads above.
- Gate decision: Stage 3 is not accepted.  The intermittent/shape-sensitive
  B2-R output-completion/correctness failure must be diagnosed and fixed before
  remaining tails or performance matrices.  These failed B2-R cycle values
  are diagnostic only and must not be used as performance evidence.
