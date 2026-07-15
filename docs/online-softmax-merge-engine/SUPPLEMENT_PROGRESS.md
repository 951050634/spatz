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
| 3 | Anchors, RVV tails, mandatory size matrices | P0 | in_progress | fixed-D closed; fresh-build smoke next |
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

### Stage 3b checkpoint: unsuccessful RVV completion diagnostics

- Objective: determine whether the `D=15` B2-R failure was caused by scalar
  return before completion or by the selected vector register groups.  These
  were dirty, single-case diagnostics from commit
  `7b3180242206d5dcfd6cc085ef11c9afaad1ba7a`; they are retained as failures,
  not formal timing evidence.
- Fixed input/provenance: `(N,D,seed,kind,repeats)=(1,15,1,main,3)`, CFG hash
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`;
  CMake 3.28.3, target clang/LLVM 14.0.6, Python 3.12.3, Verilator 5.034, and
  simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
- CSR dependency diagnostic: added a post-loop `csrr vl` followed by a scalar
  dependency.  Evidence is
  `/home/wxt/work-online-merge-stage3-tail-fence-diagnostic-20260715-041550`,
  UTC `2026-07-15T04:15:50+00:00` to `04:21:01+00:00`;
  `run_manifest.json` SHA256
  `90df178a4354eab76850ee3b0e4ff056ee8839ba0befdae89fc2047dca8714a4`
  and `artifact_manifest.json` SHA256
  `d35b894654bca6b4db2baec51f7aa82c81c04e4169efd4d44fd1e777f945e9b8`.
- Register-group diagnostic: changed the LMUL=8 groups from `v8/v16` to the
  known faxpy-style `v0/v8` groups while retaining the CSR dependency.
  Evidence is
  `/home/wxt/work-online-merge-stage3-tail-reggroup-diagnostic-20260715-042755`,
  UTC `2026-07-15T04:27:55+00:00` to `04:33:07+00:00`;
  `run_manifest.json` SHA256
  `e4d05c23190edd299633cdacb5929d69859ab570bb9ba01070da67cc8a597611`
  and `artifact_manifest.json` SHA256
  `aa77d3d57a2caa05abdc232906286f10a8ad0c3911107f288ab927742332f378`.
- Ordered-readback diagnostic: restored `v8/v16`, then loaded the final output
  word through the vector LSU and consumed it with `vmv.x.s` before return.
  Evidence is
  `/home/wxt/work-online-merge-stage3-tail-readback-diagnostic-20260715-043431`,
  UTC `2026-07-15T04:34:31+00:00` to `04:39:45+00:00`;
  `run_manifest.json` SHA256
  `adfb11902a743149cc8b8a1eb807df926f6696312aa15f2e2bd6b9359e8d29aa`
  and `artifact_manifest.json` SHA256
  `917b29f265cd2a94d36baadbdf99d3007befc2dde6ee9348f1bf16d3de18639f`.
- Preserved result: every diagnostic retained nine records.  B1 and B3 passed;
  B2-R failed all three repeats, each with first failure `O[0][9]`, expected
  bits `1060333124`, actual bits `1065266780`.  Each runner exited 1 and kept
  the simulator return 255 as `tool_error` alongside `correctness_fail` target
  records.  The three identical `failures.json` files have SHA256
  `087e8b4948f6d413a911b494a875450dfef461f7f0ab606562b32fa505df5b2f`.
- Validation: all 11 entries in each artifact manifest were independently
  rehashed successfully.  The three experimental source variants were
  removed after being disproved; no stronger disassembly gate was added.
- Decision: neither CSR consumption, register selection, nor a final-word LSU
  readback fixes the failure.  The next bounded diagnostic reduces LMUL/chunk
  length because short `D=7` vectors passed while the recurring bad upper
  lanes resemble earlier source elements.

### Stage 3c checkpoint: bounded-AVL RVV compatibility fix

- Objective: restore B2-R correctness for the retained shape-sensitive
  `D=15`/`D=31` failures without weakening VLA semantics or moving any
  workaround overhead outside the measured window.
- Bounded diagnostics used commit
  `e5d03284aa0ba422786ba6274efa4f6006fab17b` with `git_dirty=true`, CFG
  SHA256 `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  the fixed simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`,
  CMake 3.28.3, target LLVM/Clang 14.0.6, Python 3.12.3, and Verilator
  5.034.  Each diagnostic used the runner command below, with the shown
  external directory and `D` substituted:

  ```bash
  repo=/home/wxt/work-online-merge-supplement
  PYTHONDONTWRITEBYTECODE=1 python3 \
    util/online_softmax_merge/run_experiments.py \
    --repo-root "$repo" \
    --source-dir "$repo/hw/system/spatz_cluster/sw" \
    --build-dir "$repo/hw/system/spatz_cluster/sw/build" \
    --simulator /home/wxt/spatz/hw/system/spatz_cluster/bin/spatz_cluster.vlt \
    --cfg "$repo/hw/system/spatz_cluster/cfg/spatz_cluster.default.dram.hjson" \
    --work-dir <external-directory> --case 1,<D>,1,main,1800 \
    --repeats 3 --jobs 8
  ```

- Reducing only LMUL from `e32,m8` to `e32,m4` did not reduce the actual
  `VL` for `D=15` on the fixed 512-bit VLEN configuration and did not fix the
  failure.  Evidence:
  `/home/wxt/work-online-merge-stage3-tail-lmul4-diagnostic-20260715-050014`,
  UTC `2026-07-15T05:00:26+00:00` to `05:05:40+00:00`.  B1/B3 passed;
  B2-R failed all three repeats at `O[0][9]` with the same expected bits
  `1060333124` and actual bits `1065266780`.  `run_manifest.json` SHA256 is
  `27f7a2233eba6539a62aac2bb655667dc0f07907bac4332470407078f93b41f4`
  and `artifact_manifest.json` SHA256 is
  `39f087791e102994f6bd0c293e3e2856d39e1309b8cc0ead350ef2a04588238b`.
- Bounding each `e32,m8` AVL request to at most eight elements retained a
  generic VLA strip-mining loop and fixed both retained failing shapes.  The
  loop/configuration cost remains inside every B2-R measurement:
  - `D=15` evidence:
    `/home/wxt/work-online-merge-stage3-tail-cap8-diagnostic-20260715-050647`,
    UTC `2026-07-15T05:07:30+00:00` to `05:12:32+00:00`; all nine records
    passed, `run_manifest.json` SHA256
    `8a3985765e373566bce9dd0c7628b902446fb8be1ac72e8557ca857baf8d8625`,
    and `artifact_manifest.json` SHA256
    `343bad67296a701d97156095b3bbaef765fada12d655da31853acffb925f4c34`;
  - `D=31` evidence:
    `/home/wxt/work-online-merge-stage3-tail-cap8-d31-diagnostic-20260715-051424`,
    UTC `2026-07-15T05:14:24+00:00` to `05:19:18+00:00`; all nine records
    passed, `run_manifest.json` SHA256
    `f3c89e4fa2c8806375072d10dd08a3b9025565694a03419deeaa5db0e6f9157e`,
    `artifact_manifest.json` SHA256
    `9d9af1dac975486bc4ac89502484378a9126989cd50424320858c47299a13f48`,
    and runner log SHA256
    `79bf9b81d18921d86f1f1b2ca4449d72d991a163ec4bc670c3507b31d83e5665`.
- Validation: all 11 entries in each of the three artifact manifests were
  independently rehashed successfully.  The implementation unit suite passed
  21 tests.  The target build passed, and the actual target symbol contains
  two `vle32.v` instructions, `vfmul.vf`, `vfmacc.vf`, `vse32.v`, bounded-AVL
  selection, and a local strip-mining back-edge.  The strengthened gate now
  rejects a missing second load or missing back-edge.  `git diff --check`
  passed.
- Decision and limitation: retain the AVL cap as an explicitly documented
  compatibility workaround for this fixed RTL/Verilator environment; the
  evidence establishes a workaround, not an RTL root cause.  Diagnostic cycle
  values are not formal performance evidence.  Stage 3 remains open until the
  complete clean-commit tail set and both mandatory scale matrices pass.

### Stage 3d checkpoint: clean full RVV tail gate

- Objective: execute the complete correctness-only RVV tail set from the
  committed bounded-AVL implementation before accepting any scale result.
- Exact input was `(N,seed,kind,repeats)=(1,1,main,3)` with
  `D={1,7,15,17,31,33,63,65,127}` and a 1,800-second timeout per case.  The
  Stage 3c runner command was used with one `--case 1,<D>,1,main,1800`
  argument for each listed `D`.
- Clean evidence:
  `/home/wxt/work-online-merge-stage3-tail-full-clean-20260715-052827`, UTC
  `2026-07-15T05:28:27+00:00` to `06:17:36+00:00`, commit
  `c9b5ecb2a36bace2a5b62cbdb5156aa6242544cc`, `git_dirty=false`, fixed CFG
  and simulator identities from Stage 3c.  The runner returned zero and all
  36 configure/build/disassembly/simulator commands returned zero.
- Result: all 81 B1/B2-R/B3 records passed; `failures.json` is empty.  Every
  enriched cycle count was matched to the raw target `cycles_hi/lo` fields,
  all derived metrics are finite, maximum absolute and relative error are
  both `1.9073486328125e-06`, and maximum RMSE is
  `1.1614586872361443e-06`.  This closes the RVV correctness gate, including
  the previously failing `D=15` and `D=31` shapes.
- Validation: all 83 artifact-manifest entries independently rehashed
  successfully.  Top-level SHA256 values are:
  - `run_manifest.json`:
    `5fbc95c37552ac5ef95bea3766f220710ccb692643e81ddb2c7fc42284d402a1`;
  - `records.json`:
    `15cbc1c5ad041cf95cfba73c4833536387e3f3ace816e28d66e46f07417e7a02`;
  - `records.csv`:
    `3633d4aa1091e35370bd46c9541c0bc9dbb9acb108c114e0611eac13f593cff7`;
  - `summary.json`:
    `636aa334fb730725109235c52a4bf0c2a6f017ad80c8ed72d7e9a2236187e387`;
  - `commands.json`:
    `bfb63e9b7dba2d3882e6ef3cdbf92cda90b832c2c6660732a14afd0242801ff3`;
  - `artifact_manifest.json`:
    `9bab5c7b999fbcedae2040ad3a18ea861ffef294c7b26f73f12ee88d21a83cd1`;
  - external runner log:
    `1d454ba4d771a57b83fc3a1342086d2508a9ace34d097f06d6d7b31264745fd0`.
- Limitation: these tail points are correctness evidence, not the mandatory
  performance matrices.  Stage 3 remains open until both fixed-`D` and
  fixed-`N` matrices preserve all statuses and pass the same validation.
- Git sync note: the first clean-worktree `git fetch origin` attempt at
  `2026-07-15T14:24:11+08:00` failed with `gnutls_handshake() failed: The TLS connection was
  non-properly terminated`.  Local checkpoint `b769d23dc325f71018527a9420042afa905058be` is retained; no
  reset, merge, or force-push was used, and a periodic retry is required.


### Stage 3e checkpoint: controlled fixed-D long-run checkpoint

- Objective: satisfy the bounded checkpoint protocol without changing any
  benchmark, RTL, runner, CFG, or build input while the inherited six-case
  fixed-`D=64` clean run remains active.
- External run:
  `/home/wxt/work-online-merge-stage3-matrix-d64-clean-20260715-062750`,
  started at `2026-07-15T06:27:50+00:00` from commit
  `28b5eaec194e2dda302a36c0a03e4e7a1f34129b`, with
  `git_dirty=false`.  The requested cases are
  `N={1,2,4,8,16,32}`, seed 1, `main`, and three measured repeats of
  B1/B2-R/B3.
- At `2026-07-15T07:12:03+00:00`, the runner and active `N=8` simulator were
  deliberately paused with `SIGSTOP`.  The completed `N={1,2,4}` subset has
  27/27 passing records, no failures, and 12/12 zero-return commands.  The
  active `N=8` case is explicitly unclaimed until it completes; no partial
  trace or cycle value is treated as a result.
- Completed-subset validation independently reconstructed all target
  `cycles_hi/lo` values, checked finite derived metrics, confirmed exact
  three-case coverage, and rehashed all 29 indexed artifacts.  Its external
  report SHA256 is
  `6f328063e4bd53fca722228b2fecd7645d92c4866ee3899e7891390b6148cecd`.
  The pause/provenance record SHA256 is
  `ee6d8de7d04af7b80ef90fd83feb681eaa1620107e5edd270c8dde360abbb783`.
- Resume gate: the worktree must be clean after this documentation-only
  checkpoint and Git synchronization, and the benchmark/RTL/runner/CFG trees
  must have no source-relevant diff from the recorded run commit.  The run
  remains in progress and all later statuses, including failures or timeouts,
  must be preserved.

### Stage 3f checkpoint: preserve fixed-D timeout and active N=16 case

- Objective: preserve the first mandatory-matrix timeout exactly as observed
  and perform the next bounded Git checkpoint without claiming the active
  case.
- The inherited fixed-`D=64` run remains at
  `/home/wxt/work-online-merge-stage3-matrix-d64-clean-20260715-062750`.
  Its clean run provenance is unchanged: commit
  `28b5eaec194e2dda302a36c0a03e4e7a1f34129b`, `git_dirty=false`, seed 1,
  `main`, and three repeats.
- The `N=8` simulator reached its 1,800-second host wall-clock timeout at
  `2026-07-15T07:34:17+00:00`.  This status is retained rather than deleted or
  relabelled.  The log contains five complete target-pass records: all three
  B1 repeats and B2-R repeats 0 and 1.  The runner correctly marks those five
  final statuses as `timeout`, adds one synthetic B3 timeout record, and keeps
  the two validation failures `incomplete_repeat_set` and
  `missing_implementation`.  The earlier controlled pause counted against the
  wall-clock timeout, so this case must be rerun in a separate clean batch
  with a larger timeout before it can provide complete performance evidence.
- At `2026-07-15T07:37:24+00:00`, the runner and direct-child active `N=16`
  simulator were paused with `SIGSTOP`.  Persisted evidence then comprised
  33 records: 27 passes for `N={1,2,4}` and six explicit timeouts for `N=8`.
  The `N=16` partial execution is unclaimed.
- Checkpoint validation reconstructed all 32 raw target cycle values from
  `cycles_hi/lo`, checked every non-null metric for finiteness, confirmed the
  exact persisted record/status sets and timeout metadata, found no
  source-relevant diff from the run commit, and independently rehashed all 38
  current artifact-manifest entries.  The external validation report is
  `checkpoint-20260715T073724Z-validation.json`, SHA256
  `0cf578f5a2fca1a2b29046b2ca00608e428151b35c9224fd0df8166d7d95b050`.
  The pause/provenance record is `checkpoint-20260715T073724Z.json`, SHA256
  `65eded469ad341438bc407ae86488216ece109b5bfd8d6c0136550127725a931`.
- Resume gate remains documentation-only synchronization from a clean
  worktree plus a zero source-relevant diff from the recorded run commit.
  Any later timeout caused or shortened by pause wall time must likewise be
  retained, followed by a separate clean rerun rather than reinterpretation.

### Stage 3g checkpoint: clean N=8 retry, initial N=16, and retained diagnostics

- Objective: preserve the next bounded checkpoint while three simulators remain
  active, validate only fully persisted cases, and record all unsuccessful
  independent-build attempts and the ELF-inspection incident without
  reinterpreting any status.
- At `2026-07-15T08:24:05+00:00`, the direct-child simulators were stopped
  before their Python runners for these active partial cases:
  initial fixed-`D` `N=32`, formal retry `N=16`, and formal retry `N=32`.
  They remain explicitly unclaimed.  The external pause record is
  `/home/wxt/work-online-merge-stage3-checkpoint-20260715T082405Z/pause.json`,
  SHA256
  `c7357d439740b01306fc3040ac83339992c8708cc72cc6b342888eb794fdb9cc`.
- The initial six-case batch at
  `/home/wxt/work-online-merge-stage3-matrix-d64-clean-20260715-062750`
  completed `N=16` successfully at `2026-07-15T08:16:28+00:00`.
  Its nine records pass with median cycles B1 `371610`, B2-R `27532`, and
  B3 `9556`.  Persisted initial-batch state is now 42 records: 36 passes for
  `N={1,2,4,16}` and the six previously retained `N=8` timeouts.  Both
  timeout validation failures remain present.  The active `N=32` case has no
  result record and is not treated as evidence.
- The clean, independently built `N=8,D=64` retry completed at
  `2026-07-15T08:18:42+00:00` under
  `/home/wxt/work-online-merge-stage3-matrix-d64-n8-formal-clean-20260715-080002`.
  Provenance is commit `ceaa1f8b4ad802edd85f746bed025b09135c3c09`,
  `git_dirty=false`, with the fixed CFG-derived CMake cache values.  All nine
  B1/B2-R/B3 records pass, all four commands return zero, and there are no
  failures.  Median cycles are B1 `183136`, B2-R `14086`, and B3 `5351`.
  Independent validation reconstructed every 64-bit cycle count, checked
  exact repeat coverage and finite metrics, rechecked the RVV disassembly
  gate, and rehashed all 11 artifact-manifest entries plus bootstrap,
  top-level result, and runner-log sidecars.
- Four unsuccessful clean-build diagnostics are retained rather than removed:
  - `/home/wxt/work-online-merge-stage3-matrix-d64-n8-retry-clean-20260715-074512`:
    three `tool_error` records after a fresh cache selected host `/bin/clang`
    and rejected the RISC-V ABI/options;
  - `/home/wxt/work-online-merge-stage3-matrix-d64-n8-retry2-clean-20260715-074833`:
    bootstrap return code 1 because `BUILD_TESTS` was omitted and the online
    merge target did not exist;
  - `/home/wxt/work-online-merge-stage3-matrix-d64-n8-retry3-clean-20260715-075153`
    and
    `/home/wxt/work-online-merge-stage3-matrix-d64-n16-retry-clean-20260715-075357`:
    bootstrap/build succeeded, but omitted CFG-derived runtime cache values
    produced three `tool_error` records per run and target
    `online-softmax-merge FAILURE allocation`, simulator return code 255.
  The checkpoint validation report indexes and hashes every retained file in
  all four roots.
- Required independent-build cache inputs are now established as
  `BUILD_TESTS=ON`, `ELEN=64`, DRAM origin/size
  `2147483648/2147483648`, two cluster cores, four FPUs per core, TCDM
  start/size `1048576/131072`, standalone platform source, the default DRAM
  CFG, and the repository LLVM/GCC paths.  The formal `N=8` bootstrap records
  and validates those exact inputs.
- At `2026-07-15T08:04:05+00:00`, a diagnostic
  `llvm-objcopy --dump-section` invocation omitted a separate output ELF and
  rewrote the initial and formal `N=8` ELF containers in place.  The incident
  record is
  `/home/wxt/work-online-merge-elf-inspection-incident-20260715-080405/incident.json`,
  SHA256
  `0accf9f72e701d3b4d660ab8f70ec105ada52286881c8b30bc249d12ff946f81`.
  Both rewritten copies are preserved.  The formal ELF was restored from the
  exact same external build and revalidated at its indexed hash
  `a45f95d793b42589bad54fde7573fed31a8b2a168f1ea21ed38be4644789275a`.
  The initial ELF remains the one expected manifest mismatch, with current
  rewritten hash
  `0c4ce562e4e9e794274730e6ad0cc7cfc5a5bb3242d5a74a197b5401d008ebb9`;
  after the initial runner exits it must be rebuilt in the original shared
  build path, match required hash
  `c919d31ae76a159cdaadb9cb75a3ad567bceb1270fa0adc14a38c3350542e70c`,
  restored, and the complete initial manifest rehashed.  No claim is made
  that the in-place rewrite was harmless, and the section-comparison
  diagnostic is invalidated.
- Independent checkpoint report:
  `/home/wxt/work-online-merge-stage3-checkpoint-20260715T082405Z/validation.json`,
  SHA256
  `d5a0c9941edc59fb746b70c1819df7679cd38ff6c0e13fc664a875168181087e`.
  It confirms exact persisted status sets, 41 raw initial markers, nine raw
  formal markers, finite non-null metrics, command return codes, clean formal
  provenance, and no benchmark/RTL/runner/CFG diff from the initial run
  commit.  The sole initial manifest mismatch is the explicitly recorded ELF
  incident above.
- Resume gate: commit and synchronize this documentation-only checkpoint from
  a clean worktree, verify source-relevant inputs remain unchanged, then
  continue the stopped simulators first and runners second.  All later pass,
  timeout, tool-error, or incomplete statuses must be retained unchanged.

### Stage 3h checkpoint: independently built N=16 pass and two active N=32 cases

- Objective: preserve the next bounded checkpoint after the independently built
  fixed-`D=64`, `N=16` retry completed, while retaining both active `N=32`
  cases without claiming partial output.
- Clean evidence:
  `/home/wxt/work-online-merge-stage3-matrix-d64-n16-formal-clean-20260715-080049`,
  UTC `2026-07-15T08:00:49+00:00` to `08:57:00+00:00`, commit
  `ceaa1f8b4ad802edd85f746bed025b09135c3c09`, `git_dirty=false`, seed 1,
  `main`, three repeats, and a 10,800-second simulator timeout.  Its fresh
  CMake bootstrap used the fixed CFG-derived cache values recorded in Stage
  3g and returned zero.
- Result: all nine B1/B2-R/B3 records passed, all four
  configure/build/disassembly/simulator commands returned zero, and
  `failures.json` is empty.  Median cycles are B1 `371610`, B2-R `27532`, and
  B3 `9556`; the respective min/max ranges are `371057..371875`,
  `27476..27635`, and `9547..9646`.
- Independent validation reconstructed all nine 64-bit cycle counts and
  correctness metrics from raw `OM_RESULT` fields, checked the exact repeat
  set, finite metrics, correctness limits, B3 busy observation, the RVV
  disassembly gate, summary statistics, bootstrap inputs, and all four command
  statuses.  All 11 artifact-manifest entries were independently rehashed and
  matched.  Key SHA256 values are:
  - `run_manifest.json`:
    `88452d022248ea28ad0b82b49d90c1b328ff4a8a2d2c5d083547d3ec865072cc`;
  - `records.json`:
    `8054235d4f681c760324a0d8f662fe80c1cd7c8c74db447db0f622bfac4af82a`;
  - `records.csv`:
    `c7217c6ddfe0edc3923d3b65b5df838ca4e51b2bf537ef539db41fac1dd6a1d8`;
  - `summary.json`:
    `dcc7f0a2072a821597faf7ebac557d2b26de60b1a924627cfc562d7ec34e4ca3`;
  - `commands.json`:
    `2e703027e68cb0950cbd5c11efe934b00a049c44c51097f54a82db4e113b6310`;
  - `artifact_manifest.json`:
    `027a2f37fcb116cc5846407eb21bcca01ec5ca813f191fa555894cfc9e8f63d2`;
  - external runner log:
    `1875f44acad6cdb3441536b153a040f157fa62e809e6b93c2214b6ecc7b938ca`.
- At `2026-07-15T09:07:45+00:00`, the direct-child simulators were stopped
  before their Python runners for the initial fixed-`D` `N=32` case and the
  independently built `N=32` retry.  All four processes were verified in the
  stopped state.  Neither case has a persisted result record and both remain
  explicitly unclaimed.  The pause record is
  `/home/wxt/work-online-merge-stage3-checkpoint-20260715T090745Z/pause.json`,
  SHA256
  `5e0de6fb08ed84a88a40566c20cbd9bfbc98be8950fc3edfa0bfc49a4890f0c1`.
- The initial batch remains at 42 records: 36 passes and the six retained
  `N=8` timeouts.  The known initial-`N=8` ELF manifest mismatch remains
  unchanged and restoration is still deferred until that runner exits.
- Checkpoint validation report:
  `/home/wxt/work-online-merge-stage3-checkpoint-20260715T090745Z/validation.json`,
  SHA256
  `70ba4289a8a96d915da2a7b11f8a76aaae33ed8e6aabbf58597f4e7bb026e04b`.
  The validation script SHA256 is
  `84d8075cde1fcd628a23d70247a556dd029a9bfc6cd9e6fa3dc964872cdb2f91`.
- Resume gate: validate this documentation-only diff, commit and synchronize
  from a clean worktree, verify source-relevant inputs remain unchanged, then
  continue each stopped simulator before its runner.  Any later pass, timeout,
  tool error, or incomplete status must be retained without reinterpretation.

### Stage 3i checkpoint: final inherited timeout and exact ELF restoration

- Objective: close the inherited six-case runner without deleting its final
  timeout, restore the incident-affected retained ELF exactly, and validate the
  complete artifact set before changing experiment code.
- The initial fixed-`D=64` batch at
  `/home/wxt/work-online-merge-stage3-matrix-d64-clean-20260715-062750`
  completed with runner return code 1.  Its `N=32` simulator reached the
  3,600-second host wall-clock timeout at
  `2026-07-15T09:19:58+00:00` without emitting an `OM_RESULT` marker.  The
  retained result therefore contains one synthetic timeout record for each of
  B1, B2-R, and B3, all with `repeat=-1` and null cycle/correctness metrics.
  This timeout was not relabelled or replaced.
- Final inherited-batch state is 45 records: 36 passes for
  `N={1,2,4,16}`, six retained `N=8` timeouts, and three retained `N=32`
  timeouts.  The 24 recorded commands comprise 22 zero-return passes and two
  host timeouts whose recorded subprocess return code is zero.  The only two
  validation failures remain the `N=8` `incomplete_repeat_set` and
  `missing_implementation` records.  The runner's nonzero result is preserved
  as an incomplete mandatory matrix, not interpreted as a performance result.
- After that runner exited, the original shared build path was reconfigured
  for `N=8,D=64,seed=1,main,repeats=3` and rebuilt.  The resulting target hash
  was exactly the required
  `c919d31ae76a159cdaadb9cb75a3ad567bceb1270fa0adc14a38c3350542e70c`.
  It was copied to a temporary sibling, verified, and atomically renamed over
  the incident-affected retained ELF.  No `objcopy` command was used.  The
  restoration record is
  `/home/wxt/work-online-merge-elf-restoration-20260715T092707Z/restoration.json`,
  SHA256
  `67864137bb028f1d73bf5e3edd9c105501531b1108ea600471c32b38eff759bf`.
- Independent final validation reconstructed all 41 raw target markers,
  checked the exact 45-record status/key set, all non-null metrics, both
  retained failure kinds, all 24 command statuses, all 18 summary rows, and
  the RVV disassembly gate for all six cases.  After restoration, every one of
  the complete 56 artifact-manifest entries rehashed successfully.  The
  report is
  `/home/wxt/work-online-merge-stage3-initial-final-validation-20260715T092915Z/validation.json`,
  SHA256
  `37f48a508dfda3b8eeb1c10714e943889f47b188bfe33b463c1092b66d2a10bd`;
  its validation script SHA256 is
  `185fe18254785ecfb4d336a10d3bef296dfc0a15d89f8175c20ae289379420d8`.
- The first independent-validation attempt is retained at the same root as
  `validation_attempt1.json`, SHA256
  `29cca48c364df38ae0630c2ff63af3e86204bbef9dc46c39bf9fcda968d86d16`.
  It failed only because the validation script incorrectly expected summary
  statistics to include timeout records that retain target cycles; the runner
  intentionally summarizes final pass records only.  The corrected validator
  preserves the timeout cycles in `records.json` while confirming their
  exclusion from `summary.json`.
- Final top-level SHA256 values for the inherited batch are:
  - `run_manifest.json`:
    `d2a7772970d60b72d81066d0c5c26eeae21391479efcf098163abc78b700f69a`;
  - `records.json`:
    `2250247ab85af717448dedb61894622f8da99b837ff1ee86780fed13311f4f8c`;
  - `records.csv`:
    `e616227594ca7c3620c573d7ff124f4496f7b37379dc607e40e0efe255d0acb1`;
  - `summary.json`:
    `bd171796b3b74a69d3294b05cd2d6143fe6fadd4fc8b717f9a5b3315893a7aa2`;
  - `commands.json`:
    `9ddaad386c145a05a7da265fc830255709fb65bff8c64da5df088148c3b0bb54`;
  - `failures.json`:
    `20b4d7a7e6680169e53c01e5fd06f8cc8701f85dbbfcd988631ce6cd690a87ce`;
  - `artifact_manifest.json`:
    `1f92cd38f954b1076653863ebdbda6156b95d70d24b2a6462a7f2e28ec9047c3`;
  - external runner log:
    `0c766fedf995d58306c335828c5d62e132d0e02dda29d47845e8dd128c28114a`.
- The Stage 3h synchronization first failed at `git fetch origin` with
  `gnutls_handshake() failed: The TLS connection was non-properly terminated`.
  The local checkpoint was retained; a retry at
  `2026-07-15T09:16:19+00:00` succeeded, followed by a clean rebase and push at
  `09:18:51+00:00`.  The external sync record SHA256 is
  `c65778ba2ccc19ad5866a829f2ed4b337b0a741ae857ab5a2d57eb3e2c8bc732`;
  no force-push or merge commit was used.
- At `2026-07-15T09:33:39+00:00`, the remaining independently built `N=32`
  simulator was stopped before its runner and remains explicitly unclaimed.
  The pause record is
  `/home/wxt/work-online-merge-stage3-checkpoint-20260715T093339Z/pause.json`,
  SHA256
  `afd5bc1f6e8a435fe648b285067ec2330da17d854adf25e2125737325848174a`.
- Resume gate: validate this documentation-only diff, commit and synchronize
  from a clean worktree, then continue the stopped simulator before its runner.
  The fixed-`D` matrix remains open pending the independently built `N=32`
  result; the inherited `N=8` and `N=32` timeouts remain permanent evidence.

### Stage 3j checkpoint: independently built N=32 pass and fixed-D closure

- Objective: finish and independently validate the last clean fixed-`D=64`
  anchor before changing the experiment runner or benchmark sources.
- The formal `N=32,D=64,seed=1,main` run completed at
  `2026-07-15T09:46:24+00:00` under
  `/home/wxt/work-online-merge-stage3-matrix-d64-n32-formal-clean-20260715-080837`;
  its independent build directory is
  `/home/wxt/work-online-merge-build-stage3-d64-n32-formal-20260715-080837`.
  Provenance is commit `ceaa1f8b4ad802edd85f746bed025b09135c3c09`,
  `git_dirty=false`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`.
  The measured simulator window was
  `2026-07-15T08:08:41+00:00..09:46:24+00:00`, with a 21,600-second host
  cap, one excluded warm-up, and three retained measured repeats.
- All nine B1/B2-R/B3 records pass, all four configure/build/objdump/simulator
  commands return zero, and `failures.json` is empty.  Cycle
  min/median/max values are B1 `729981/730218/730593`, B2-R
  `53247/53520/53640`, and B3 `18141/18159/18159`.  The largest observed
  absolute error is `0.0008955001831054688`, largest relative error is
  `0.00016185392734602858`, largest RMSE is
  `0.00002819735176430857`, and every record has zero nonfinite outputs.
  B3 records retain `75..76` congested accesses and assert `saw_busy`; the
  software baselines do not assert it.
- The mandatory fixed-`D=64`, `N={1,2,4,8,16,32}` anchor matrix now has a
  clean passing result for every point.  Median B1/B2-R/B3 cycles by `N` are:
  `1: 23704/2048/1603`, `2: 46111/3683/2112`,
  `4: 92976/7246/3174`, `8: 183136/14086/5351`,
  `16: 371610/27532/9556`, and `32: 730218/53520/18159`.
  The inherited `N=8` and `N=32` timeout records remain unchanged in their
  original batch; the clean retries are separate evidence and do not replace
  or relabel those failures.
- Independent validation reconstructed all nine 64-bit cycle counts and
  correctness metrics from raw `OM_RESULT` fields, checked exact repeat and
  command coverage, compared CSV and JSON semantically, reproduced all three
  summary rows, reran the RVV disassembly gate, checked the fixed CFG-derived
  bootstrap inputs and self-hashes, and independently rehashed all 11
  artifact-manifest entries.  It also verified that the previously accepted
  N=16 and inherited-batch validations remain byte-identical and passing.
  The final report is
  `/home/wxt/work-online-merge-stage3-n32-final-validation-20260715T095001Z/validation_final.json`,
  SHA256
  `b337655da4a3b9f44dcbda05a92801007bb0e49ad4d541c6b46c3015a9d439d3`;
  validator SHA256 is
  `586ac2ceba96619088820d74efc094afb4bdf6c48841fcbe17cc646ed7af437b`.
- A failed validator-only attempt is deliberately retained in the same
  directory.  It incorrectly imposed earlier observed N=16 accuracy maxima,
  treated Python CSV formatting as canonical JSON formatting, and expected a
  shell-only `runner_rc` line inside the `tee` output.  It did not modify any
  run artifact.  Its report SHA256 is
  `3aa32090228096be369fcaad365bbacb15f037758f83d400d678e45343a1a229`
  and validator SHA256 is
  `c586817a988533febad6190fab3e26aacb4e9d2bab82b3c6a4648a4abdf83e42`.
- Final N=32 top-level SHA256 values are:
  - `run_manifest.json`:
    `08fe331d437d00f8c132ec9c33c4e98ca967bfbf8238130a50aaa3a870e72c7a`;
  - `records.json`:
    `97cb16fd6750350313129d2332f0b95c65279a40a4eececdeb96e4965fe7f64d`;
  - `records.csv`:
    `c3b7ef7072dd0fac8837c52c8879bdb435036f08777e51bbb15be952ba227be4`;
  - `summary.json`:
    `f8b3c4c561b108dcd5e1f2ad65c468b49cb0bd898de720af643d73c7de9a6678`;
  - `commands.json`:
    `279c0966cfa1dedc519d8b4e95df2a3c5321c9252a72d69d4daff9f9bba2c582`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `96f12f0d9d2b99c72906527fb47d6768341a33e1021be7af28f775db22444dbb`;
  - external runner log:
    `83743d77039d748bc7d498951e41985b58e946b3824ab827c5c4c32d0e3340fe`.
- Tool identities recorded by the run include CMake `3.28.3`, target Clang
  `14.0.6`, Verilator `5.034`, and simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  The next atomic stage is runner support for repeated, conflict-checked
  `--cmake-define KEY=VALUE`, followed by the fixed-`N=8` dimension matrix.

### Stage 3k checkpoint: reproducible fresh-build CMake definitions

- Objective: remove inherited CMake-cache state from later matrix runs by
  making every non-case configure input explicit, ordered, and auditable.
- The runner now accepts repeated `--cmake-define KEY=VALUE` options, appends
  them after the five runner-owned case definitions in every configure argv,
  and records ordered `key`, `value`, and exact `-D` argument entries in
  `run_manifest.json`.  Keys must match `[A-Za-z_][A-Za-z0-9_]*`; empty or
  non-printable values, typed-key syntax, duplicate keys, and the five
  runner-owned `ONLINE_MERGE_*` keys are rejected before a result directory is
  created.  Additional `=` characters in values remain unchanged.
- `util/online_softmax_merge/README.md` records the 14 fixed definitions needed
  to bootstrap a fresh external build for
  `spatz_cluster.default.dram.hjson`: toolchain paths, `BUILD_TESTS`, `ELEN`,
  DRAM origin/size, hart/core/FPU counts, TCDM address/size, platform source,
  and cluster CFG name.
- Implementation validation:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s`
  ` util/online_softmax_merge/tests -v` passes all 26 tests.  The added tests
  cover order, embedded `=`, manifest encoding, invalid/typed keys,
  non-printable and empty values, duplicate and reserved keys, exact configure
  ordering, and repeated CLI parsing.  `git diff --check` also passes.  The
  retained validation log is
  `/home/wxt/work-online-merge-stage3k-implementation-validation-20260715T101019Z/validation.log`,
  SHA256
  `f4551245c9b1a82227825c8a319d46d5a312e8c468e5a4275b828c124d217f29`.
- Dirty fresh-build diagnostic evidence is retained under
  `/home/wxt/work-online-merge-cmake-define-dirty-diagnostic-20260715-100056`;
  its independent build is
  `/home/wxt/work-online-merge-build-cmake-define-dirty-diagnostic-20260715-100056`.
  It used commit `13331927aa047d5b2ced8316f33fa553316d095c`,
  `git_dirty=true`, `(N,D,seed,kind,repeats)=(1,1,1,main,3)`, and an intentional
  one-second simulator timeout.  Fresh configure, target build, and RVV
  objdump gate returned zero; the simulator timeout and three synthetic
  `timeout` records are retained, and runner return code 1 is expected.  This
  diagnostic proves plumbing only and is not passing benchmark or performance
  evidence.
- Independent validation found all 14 definitions in exact argv order, checked
  their exact `CMakeCache.txt` values, matched the ordered manifest entries,
  rehashed all 11 artifact-manifest entries, confirmed the RVV gate artifact,
  and proved that reserved, duplicate, and typed-key probes fail before work
  directory creation.  Its report is
  `/home/wxt/work-online-merge-cmake-define-dirty-validation-20260715T100219Z/validation.json`,
  SHA256
  `552682669c64435a9fc5e9d19bbcdd76e7ffb63e202ac667596ea9d2a1938403`;
  validator SHA256 is
  `e3784989473f8da658072a743fbb00ea1d2d337f285b3048bdf30cdbae491bc8`.
- Diagnostic top-level SHA256 values are:
  - `run_manifest.json`:
    `d0e46758d3e248b3402e07b8fff72b8bc4dea5280057675fee57360acba62304`;
  - `records.json`:
    `1ffe53f05e2800d477d9cb9be8ea6d3ce26a404aa9de7071f26ab70218c36015`;
  - `records.csv`:
    `5c63364f84fd03c9a3a570010ee13c6264f76040c2d2075436ec541fc07fc70f`;
  - `summary.json`:
    `6c0c4878041cf94d3595bb1d6c55e47ca6e3fec27a13942bc5d906dc86288457`;
  - `commands.json`:
    `010f7b84a31b73f29342579cc7293598c509600b47a6f73614b909225d9bae37`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `6891d95d4c63ce2b02cb8fa23ab69f3d993c344850eb325011177b81c64271fd`;
  - external runner log:
    `1fdb675bf7e4f449852c433b79ab0ac45793ccf0a804f7e428dcf4b4ed2b4c54`.
- Remaining gate: commit and synchronize this implementation from a clean
  worktree, then run a clean committed fresh-build smoke with a realistic
  timeout.  Only that later run may establish formal passing evidence before
  the fixed-`N=8` dimension matrix.
