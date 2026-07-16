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
| 3 | Anchors, RVV tails, mandatory size matrices | P0 | complete | Stage 3n closes both mandatory fixed matrices |
| 4 | Break-even table and fitted scale model | P0 | complete | Stage 4e formal fit and direct 16-point table |
| 5 | Full-SMU FSM cycle breakdown and A0/A2 | P0 | complete | Stage 5b exact three-point formal closure |
| 6 | C0/C1/C2/C3 concurrency and 16 bank phases | P0 | in_progress | Stage 6e bounded clean timeout diagnosed; tuned simulator validation pending |
| 7 | Yosys Slang generic-resource proxy | P0 | complete | Stage 7c clean capture and deterministic analysis closure |
| 8 | Representative RTL VCD toggle proxy | P0 | in_progress | Stage 8c three clean captures pass; formal analysis pending |
| 9 | Target `expf` B0/B2-F | P1 | pending | pending |
| 10 | Scalar-only A1 | P1 | pending | pending |
| 11 | Trace gating / low-perturbation counter | P1 | in_progress | Stage 8a probe-gated VCD implementation passes dirty smoke |
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

### Stage 3l checkpoint: clean committed fresh-build smoke

- Objective: establish formal passing evidence that a unique external build can
  be configured from the 14 recorded definitions without inherited cache
  state, before starting the dimension and break-even matrices.
- The Stage 3k implementation was committed as
  `ef859f48fa5f4474895b6993f37d77b6adb86bd0` and synchronized successfully.
  The sync record is
  `/home/wxt/work-online-merge-stage3k-sync-20260715T101207Z/sync.json`,
  SHA256
  `4716519239b9a41e643f24d12127328b598e7cd2c770b02e71aca7c4cd09a0e6`.
- Formal run evidence is retained under
  `/home/wxt/work-online-merge-cmake-define-clean-smoke-20260715T101634Z`;
  its unique build directory is
  `/home/wxt/work-online-merge-build-cmake-define-clean-smoke-20260715T101634Z`.
  Provenance is commit `ef859f48fa5f4474895b6993f37d77b6adb86bd0`,
  `git_dirty=false`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  The command window was
  `2026-07-15T10:16:34+00:00..2026-07-15T10:21:32+00:00` with an
  1,800-second simulator timeout.
- Fresh configure, target build, RVV objdump gate, and simulator all returned
  zero.  The exact 14 definitions occur after the five case definitions in the
  configure argv, their ordered manifest entries match, and all 19 values were
  independently recovered from the fresh `CMakeCache.txt`.  Runner return code
  is zero, `failures.json` is empty, and all nine B1/B2-R/B3 records pass.
- Cycle min/median/max values are B1 `2254/2530/2573`, B2-R
  `1909/1966/2084`, and B3 `1115/1124/1140`.  The largest absolute and relative
  error are both `0.0000012516975402832031`; largest RMSE is
  `0.0000007226679118264997`.  Every output is finite.  This is a plumbing
  anchor, not a replacement for the mandatory matrix points.
- Independent validation reconstructed all cycles and correctness metrics from
  the nine raw `OM_RESULT` markers, compared CSV and JSON semantically,
  reproduced all three summary rows, reran the RVV objdump gate on the exact
  ELF, rechecked the fresh cache and command order, and rehashed all 11
  artifact-manifest entries with their provenance fields.  The final report is
  `/home/wxt/work-online-merge-cmake-define-clean-final-validation-20260715T102657Z/validation.json`,
  SHA256
  `2d521c7818c194e182e064744612411f25ea5467078d8ce5d6b29150b5f32af5`;
  validator SHA256 is
  `199f4ab3a6e118749213786754cf9ff862af5bb05c9e05ffe1be8d418a4786b8`,
  and the independent objdump log SHA256 is
  `85f44ac5e501528de22aaacebf6450f49b51f9850bdaa2d4b9d7b12d44e35b93`.
- A failed validator-only attempt is deliberately retained at
  `/home/wxt/work-online-merge-cmake-define-clean-validation-20260715T102548Z`.
  All substantive checks passed, but it compared the stored function snippet
  against a rerun snippet containing one extra trailing blank line.  It did not
  alter run artifacts.  Its report SHA256 is
  `9dcf6e13d1df1ddd6a59a8e21b57006f92ac61bf49a723e630fd343beb3452a4`
  and validator SHA256 is
  `49396cae3f06fd2817cdd130e7a7d10e07011e7f46a368fc13f49e5c46ab9751`.
- Formal top-level SHA256 values are:
  - `run_manifest.json`:
    `f9cf3dbd928575ada341c7cefdd899360f8d05f655238480c6ad65953c709145`;
  - `records.json`:
    `65c54ff1b7133f2767d4742db6c544c0f68f135e629710abd16f655baa261273`;
  - `records.csv`:
    `093cb2768008ebaf68e83b890418c9e6a64e1286c7de6390590a3f4cebf3a663`;
  - `summary.json`:
    `7225b0909ad71c533e7115ceb8e006ae18fe866a72e6fc6d7d95c77e3d43f46d`;
  - `commands.json`:
    `aaa2a3975ae0ffa45ec665c2a54bf4b780f7bde98866ebe3f08d2e5436d56fcd`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `7c70c7f59fa9b0d143348d9934d0e1f5e776b4814d8c7a6aa4fb96269100cc8b`;
  - external runner log:
    `79d363ee581f0e4688d42e24ef44f48eada034e911ec2ce2e23b833690c21153`;
  - external runner return-code file:
    `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- Tool identities include CMake `3.28.3`, target Clang/objdump `14.0.6`,
  Verilator `5.034`, and Python `3.12.3`.  The checkpoint-level revalidation
  log, including all 26 unit tests and referenced-hash checks, is
  `/home/wxt/work-online-merge-stage3l-checkpoint-validation-20260715T102849Z/validation.log`,
  SHA256
  `7d01dc955a1c40af3ced09158398ff4e611d3f3f7574138f2acaa015afb6e9d8`.
  The next executable P0 item is the fixed-`N=8`,
  `D={1,8,16,32,64,128}` dimension matrix, followed by the break-even matrix.

### Stage 3m checkpoint: clean fixed-N small-D matrix batch

- Objective: collect and independently validate the small-dimension portion of
  the mandatory fixed-`N=8` matrix with a unique external build and the 14
  explicit fresh-cache definitions established in Stage 3k.
- Formal evidence is retained under
  `/home/wxt/work-online-merge-stage3-n8-d-small-clean-20260715T103315Z`;
  its build directory is
  `/home/wxt/work-online-merge-build-stage3-n8-d-small-clean-20260715T103315Z`.
  Provenance is commit `892c44ddb11f7cf87a139a46eed865b01039d7c7`,
  `git_dirty=false`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  The command window was
  `2026-07-15T10:33:15+00:00..2026-07-15T11:09:07+00:00`.
- Inputs are `N=8`, `D={1,8,16,32}`, seed 1, `main`, and three measured
  repeats after each implementation's unmeasured warm-up.  Per-case simulator
  timeouts are 1,800, 1,800, 2,700, and 3,600 seconds respectively.  All 16
  configure/build/objdump/simulator commands return zero; all 36 B1/B2-R/B3
  records pass and are finite; `failures.json` is empty; the runner return code
  is zero.
- Measured cycles (min/median/max) are:

  | D | B1 | B2-R | B3 |
  | ---: | ---: | ---: | ---: |
  | 1 | 15624/15896/15997 | 12857/13080/13127 | 1290/1290/1320 |
  | 8 | 34411/35166/35399 | 12837/12885/13101 | 1732/1732/1751 |
  | 16 | 55988/56049/56525 | 12754/13078/13263 | 2281/2281/2302 |
  | 32 | 99772/99794/100169 | 13455/13547/13761 | 3254/3263/3328 |

- Across all 36 records, the largest absolute error is
  `0.0012054443359375`, largest relative error is
  `0.00014736815617622854`, and largest RMSE is
  `0.00010590818264455575`.  These are correctness diagnostics under the
  RTL-aligned approximation, not physical-quality or energy claims.
- Independent validation reconstructed all 36 records from raw `OM_RESULT`
  fields, compared CSV and JSON semantically, reproduced all 12 summary rows,
  verified the exact case manifest and configure argv, checked all 19 final
  cache values, reran all four RVV disassembly gates, and rehashed all 38
  artifact-manifest entries.  The passing report is
  `/home/wxt/work-online-merge-stage3-n8-d-small-final-validation-20260715T111505Z/validation.json`,
  SHA256
  `54f007a0321aaf1650753ba7821858e9ec6e5f0c25dfce156c4b91fb3f97921e`;
  validator SHA256 is
  `b4339a2bcb58834204382d02b52955b3da063ff1df4e731dd2b4402072477758`.
  The validator log SHA256 is
  `4762d03207059f01ba806e3c6897cc143248f23ea52133a68d480d66264b5295`.
- Independent RVV rerun-log SHA256 values for `D=1,8,16,32` are respectively
  `56bb8e09527c64bad604e4ab05c6803304340307eb8bb5e58fe8178d9a6559ac`,
  `f056aa1f401ae21ce728aef713969348be15eff32db896a9706130a416cdd5fe`,
  `70eedd3933de008c1c6c36cddaf1ce3c1787bd189723e40e3d89c2d53a90b924`,
  and `c3fde0ecb0f00b699edf554efacc4eb53fb7cf0a7b3b8e097205717abdb1b3dc`.
- A failed validator-only attempt is deliberately retained at
  `/home/wxt/work-online-merge-stage3-n8-d-small-validation-20260715T111103Z`.
  All substantive checks and RVV reruns completed, but JSON serialization
  rejected tuple keys in the report-only `raw_sources` dictionary.  It did not
  modify run artifacts.  Its validator and log SHA256 values are
  `90cecacb06730b1150a27f81c6e19e098569e9631e7a63fe2fcd9544f2c084a2`
  and `10d0e440515b47652b401d62bad3a3871435b9ae634d6633ac44a8f6fadf18ea`.
- Formal top-level SHA256 values are:
  - `run_manifest.json`:
    `b029deeb02e863f2e5b0b74129e4c68400e218322b27147277807b4b3a36da16`;
  - `records.json`:
    `ec24a04a347df0fed86842591e51ad89271769214f5026d21c8f18d30ed4fc2e`;
  - `records.csv`:
    `7468577204fd8056241cbeaae15fbd9a57c14b8ca8b7858cc91e69010a3e3329`;
  - `summary.json`:
    `2997ec6cd388318547b6a139eb80be32e4a46e14c3efff8f54fb4eafa6aa851e`;
  - `commands.json`:
    `2bb29e1f7681c943e229805f44ed569de21884e75c057297f67fafb6c6d3f68a`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `8f96f24770e611ae48e8ac7495d96110bb2008b9ca69391a216fedfac8a552bc`;
  - external runner log:
    `901f3095d8fe15d5f32cfb34094a264db85baa8c05e3eef81db424a6c79b0dde`;
  - external runner return-code file:
    `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- Checkpoint validation reran all 26 runner unit tests, `git diff --check`,
  all referenced-hash checks, provenance and case coverage checks, and the
  independent-report gates.  Its report is
  `/home/wxt/work-online-merge-stage3m-checkpoint-validation-20260715T112110Z/validation.json`,
  SHA256
  `89987cc4ae42bbfe54ce5c822b34c3d54359cd693a55560da7518b2c41cdb3aa`;
  validator SHA256 is
  `2c205d7aca3d5cc12fb306ab9a75564f58d7b4d4e3d0446b0937b5745539130b`,
  and log SHA256 is
  `90bb1e9e45059d6534f05173c82cdaf801c7efec08826f0f66056bec60d0b467`.
- Tool identities include CMake `3.28.3`, target Clang/objdump `14.0.6`,
  Verilator `5.034`, and Python `3.12.3`.  The already validated fixed-`D=64`
  point supplies `N=8,D=64`; the remaining fixed-`N=8` mandatory point is
  `D=128`, which must use a separate fresh build and remain distinct from any
  timeout or failed diagnostic.

### Stage 3n checkpoint: fixed-N D=128 point and matrix closure

- Objective: execute the last mandatory fixed-`N=8` point and close the full
  `D={1,8,16,32,64,128}` matrix without replacing any earlier failed or
  timeout diagnostic.
- Formal `N=8,D=128,seed=1,main,repeats=3` evidence is retained under
  `/home/wxt/work-online-merge-stage3-n8-d128-clean-20260715T112512Z`;
  its unique external build is
  `/home/wxt/work-online-merge-build-stage3-n8-d128-clean-20260715T112512Z`.
  Provenance is commit `a80be50b1fca6bbd1e4b02a174c4a55b51ec2f5a`,
  `git_dirty=false`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  The exact command window was
  `2026-07-15T11:25:12+00:00..2026-07-15T11:56:37+00:00`, with a
  5,400-second simulator timeout.
- Fresh configure, target build, RVV objdump gate, and simulator all returned
  zero.  All nine B1/B2-R/B3 records pass and are finite, `failures.json` is
  empty, and the runner return code is zero.  Cycle min/median/max values are
  B1 `356471/356978/357049`, B2-R `15017/15194/15199`, and B3
  `9410/9419/9457`.  The largest absolute error is
  `0.0007348060607910156`, largest relative error is
  `0.00012778052198633453`, and largest RMSE is
  `0.00003153156172533741`.
- The large raw hart-0 trace remains outside Git at
  `/home/wxt/work-online-merge-stage3-n8-d128-clean-20260715T112512Z/N8_D128_S1_main_R3/logs/trace_hart_00000.dasm`;
  it is 1,133,010,045 bytes with SHA256
  `6824484f0cbaa7820585de78f1fd4b7d9a4b394d1f4b621be31b42f148c16afa`.
  No trace, build product, ELF, or simulator log is committed.
- Independent single-point validation reconstructed all nine raw results,
  compared CSV and JSON semantically, reproduced the three summary rows,
  checked the exact 19 cache values and four command argv/status records,
  reran the RVV gate, and rehashed all 11 artifact-manifest entries.  Its
  report is
  `/home/wxt/work-online-merge-stage3-n8-d128-final-validation-20260715T112825Z/validation.json`,
  SHA256
  `2eaaa6925a9f182efa8e443f9948b0042b336997b33047527ff98c67ccca6324`;
  validator SHA256 is
  `d946c7ddc645899502513efa813ab86ec2fe1350f36ae59a1a791eff19581f2b`,
  validator-log SHA256 is
  `dd5600f8754458caba89b8ae668be0937c0b60baa670557550e6382a24d4cb0b`,
  and the independent RVV rerun-log SHA256 is
  `17ee1f94e7b7432cfe5a32b1ef210584e515dec926ea7fc7c09817c1918e1caa`.
- Formal `D=128` top-level SHA256 values are:
  - `run_manifest.json`:
    `f4c54daabdec2a79634646db3d79e944daba9828c55e6cdd2f333737867a719b`;
  - `records.json`:
    `c5ef980e1539eda0d7d5079db4e37e0bfd8ac89190ddc328fa261fb2c301b341`;
  - `records.csv`:
    `93d5f2c7332ec2b23c86bb4b9af331042ca66b6652b1eed61222dd22d07d080c`;
  - `summary.json`:
    `47f9f437e084c3d2eba9cd7d6febf449264e4454f94cd43f733ff79f60a20512`;
  - `commands.json`:
    `4609bad97c9135c4eaa4c4b08943c9118dd1389f27a1293765f1c8c8e815b3ce`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `ff71a5961c3302e30ef2bf2d24536e1a9e6b8a78fa5f32667f2d59df5ab441f4`;
  - external runner log:
    `2f6e74821e7288b93f7035e79fc06df46a62a287eb557c9911cf14a238f668da`;
  - external runner return-code file:
    `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- The complete fixed-`N=8` matrix contains exactly 54 unique passing records.
  Measured cycle min/median/max values are:

  | D | B1 | B2-R | B3 |
  | ---: | ---: | ---: | ---: |
  | 1 | 15624/15896/15997 | 12857/13080/13127 | 1290/1290/1320 |
  | 8 | 34411/35166/35399 | 12837/12885/13101 | 1732/1732/1751 |
  | 16 | 55988/56049/56525 | 12754/13078/13263 | 2281/2281/2302 |
  | 32 | 99772/99794/100169 | 13455/13547/13761 | 3254/3263/3328 |
  | 64 | 182936/183136/183196 | 13847/14086/14317 | 5339/5351/5361 |
  | 128 | 356471/356978/357049 | 15017/15194/15199 | 9410/9419/9457 |

- The closure validator independently rehashed all 60 indexed artifacts from
  the small-D, D=64, and D=128 roots; verified all three prior independent
  reports at their fixed hashes; confirmed exact case/repeat/status coverage;
  and checked the real compact allocation at every point.  Rounded allocation
  ratios range from `0.00390625` at `D=1` to `0.126953125` at `D=128`, so all
  points satisfy both `N*D <= 2048` and the 70% TCDM gate.  A Git path diff
  also proves that benchmark and integration inputs did not change between the
  older validated D=64 commit and the D=128 commit; intervening changes are
  runner/tests/documentation only.
- The passing closure report is
  `/home/wxt/work-online-merge-stage3-fixed-n8-closure-validation-20260715T115938Z/validation.json`,
  SHA256
  `866682c5650a8d3289beb80fe5685ba41a24314d54a3013d6f95dd1c542a2f14`;
  validator SHA256 is
  `f30d3e3250d955d19696a91ded572be630d20d5d0c2936fdff5fc135705c2018`,
  and log SHA256 is
  `fca7eccef867562fdb716c3b32d8231e226b72e993e683a7c615285dead24353`.
  Tool identities remain CMake `3.28.3`, target Clang/objdump `14.0.6`,
  Verilator `5.034`, and Python `3.12.3`.
- Checkpoint validation reran all 26 runner unit tests, `git diff --check`,
  fixed-hash evidence checks, single-point validation gates, and exact closure
  coverage.  Its report is
  `/home/wxt/work-online-merge-stage3n-checkpoint-validation-20260715T120205Z/validation.json`,
  SHA256
  `095fde754fbde9e81d31841cbe7c7c775360eec3d1a797fda22207204847081e`;
  validator SHA256 is
  `6eeb29ef84cd40d902e76affe4ab8a1cd47e3435b2e9c33128b0df757a730635`,
  and log SHA256 is
  `6008fd028fe97bc3b602a61e807ad2749817782d00c6bd2f92a76975c5e36c59`.
- Both mandatory fixed matrices are now complete.  The next P0 stage is the
  remaining break-even cases `N={1,2,4}`, `D={1,8,16,32}`, followed by the
  measured break-even table and fitted B2-R/B3 scale model.

### Stage 4a checkpoint: clean break-even N=1 batch

- Objective: collect and independently validate the `N=1`,
  `D={1,8,16,32}` row of the required break-even matrix using a unique
  external build and the established 14 explicit fresh-cache definitions.
- A rejected preflight is deliberately retained.  The case file
  `/home/wxt/work-online-merge-stage4-break-even-n1-clean-20260715T120624Z.cases.json`
  used lowercase `n`/`d`; its SHA256 is
  `cad6f86f3f7cfcb6d0c6d80f164c627c7502af859e9cbabcd98d96ea2b0cb407`.
  The runner rejected entry 0 before creating a result directory with
  `missing required field(s): N, D`; the log and return-code-file SHA256 values
  are `91101c8849a4f94ee17ee3a312495a055aeaa8f7fd0abf6aaaa6aad46ad88235`
  and `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`
  respectively, and the recorded return code is 1.  This failed request is not
  relabelled as experiment evidence.
- Formal evidence is retained under
  `/home/wxt/work-online-merge-stage4-break-even-n1-clean-20260715T120725Z`;
  its unique build directory is
  `/home/wxt/work-online-merge-build-stage4-break-even-n1-clean-20260715T120725Z`.
  The corrected uppercase-key case file has SHA256
  `a0291fe97ad2f6b9b9afa3ea47a0a9dc2d9ba9c482bcdaf49225e77e4bb22245`.
  Provenance is commit `0dea6d2a50798e1606104dc31ebcac0b116e0fb9`,
  `git_dirty=false`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  The command window was
  `2026-07-15T12:07:26+00:00..2026-07-15T12:40:37+00:00`.
- Inputs are `N=1`, `D={1,8,16,32}`, seed 1, `main`, and three measured
  repeats after each implementation's unmeasured warm-up.  Every simulator
  timeout is 1,800 seconds.  All 16 configure/build/objdump/simulator commands
  returned zero; all 36 B1/B2-R/B3 records pass and are finite;
  `failures.json` is empty; the runner return code is zero.
- Measured cycles (min/median/max) are:

  | D | B1 | B2-R | B3 |
  | ---: | ---: | ---: | ---: |
  | 1 | 2254/2530/2573 | 1909/1966/2084 | 1115/1124/1140 |
  | 8 | 4773/4918/4983 | 1918/1968/1976 | 1118/1121/1133 |
  | 16 | 7444/7467/7587 | 1952/1995/2111 | 1191/1203/1217 |
  | 32 | 12523/12778/12874 | 1954/1977/2086 | 1377/1388/1391 |

- The largest absolute and relative errors are both
  `0.0000019073486328125`; the largest RMSE is
  `0.0000011879880087372511`.  Allocator-rounded working sets are 256, 256,
  512, and 768 bytes for increasing `D`, or at most `0.005859375` of the
  128 KiB TCDM.  Every record has `tcdm_congested=0`.  The retained CSV/JSON
  records also include cycles per element, elements per cycle, TCDM accesses,
  congestion ratio, and speedup versus B2-R.  These are measured simulator
  counters and correctness diagnostics, not physical PPA or energy claims.
- Independent validation reconstructed all 36 records from raw `OM_RESULT`
  fields, compared CSV and JSON semantically, reproduced all 12 summary rows,
  checked the exact uppercase case file and normalized manifest, preserved and
  rehashed the failed lowercase-key preflight, verified all 19 final cache
  values and 16 command records, reran all four RVV disassembly gates, and
  rehashed all 38 artifact-manifest entries.  The passing report is
  `/home/wxt/work-online-merge-stage4-break-even-n1-final-validation-20260715T122556Z/validation.json`,
  SHA256
  `9979b6fb0346af5e8f9f0e0fee81b50f818e23d6f5de37ba522b181ba4b50a27`;
  validator SHA256 is
  `4f411dd798084ba45399750686854b7d9b1bc3c8e613d2a56fbe2aecaac3c586`,
  and validator-log SHA256 is
  `516476eff3c38cbe2772548e04d53a2a103589855fca46bd6fa92e9d41eed512`.
  Independent RVV rerun-log SHA256 values for `D=1,8,16,32` are respectively
  `45c116326b3b4cc0046b498f826403d16bc7f1c4bac6d0a9d8d56d0b0f8dabdb`,
  `2b17ba73f004ac41aadfb17229c44e44c9438357fe289bf2c30735df7acb84b5`,
  `dee21f0dd7b0ec2e3aac65c55a5f7f76e845768d139e35cf15cc7fb94d583e86`,
  and `8dcb806fdef923308fb678d157fa1c9587e3760e288254fee6de8e0c25d616ac`.
- Large hart-0 instruction traces remain outside Git:
  - `N1_D1_S1_main_R3/logs/trace_hart_00000.dasm`: 144,460,946 bytes,
    SHA256
    `f68ab8846ea0427f5b31fc52ccfcb631f12bc294f492558a56835134e97c94a0`;
  - `N1_D8_S1_main_R3/logs/trace_hart_00000.dasm`: 151,964,955 bytes,
    SHA256
    `e63b16a3de7159929f8ff6e6438375dc13cb8dc2595232bf3175526ad54e492e`;
  - `N1_D16_S1_main_R3/logs/trace_hart_00000.dasm`: 159,639,275 bytes,
    SHA256
    `dd456fa4c3755d1d09334fb968dc25cbf30c84008d1f33cd8be22348ea6878ef`;
  - `N1_D32_S1_main_R3/logs/trace_hart_00000.dasm`: 174,751,522 bytes,
    SHA256
    `296f94499648b659873bdcc8b9834f133bd44ec7735ffb9be77981ce4da012bc`.
  Paths are relative to the formal result root above.  No trace, build product,
  ELF, or simulator log is committed.
- Formal top-level SHA256 values are:
  - `run_manifest.json`:
    `a327fc8c08e4edd34e667e7df614b64b99cee91733b76becbc040a224b258daa`;
  - `records.json`:
    `fe99bb6f83dbf466bd2f248dd8abb0628a472920b8e1728d9f5496b0c6f1afc8`;
  - `records.csv`:
    `dfd7c59df599f9fa40677497766436c5e26938ab1e1115f6aa47b9ce6238ab10`;
  - `summary.json`:
    `7ee5fa4b4c7f1964016593c97405ef29596426c7da941cc891bf067a6c656d8e`;
  - `commands.json`:
    `b14c3d0cb5777d7395035c491ed130b805167fb365f48eb05450cf3a1aab183e`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `68654caf2669a8cf7b3105e5781c4caea55b8e08346546cc1fedb6554ce9223b`;
  - external runner log:
    `1f41c89508ef44cf9dd542837a2654872f265059591737f5aab100fa347a2a3d`;
  - external runner return-code file:
    `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- A first checkpoint-validator-only attempt is retained at
  `/home/wxt/work-online-merge-stage4a-checkpoint-validation-20260715T124659Z`.
  All evidence checks and all 26 unit tests passed, but Python bytecode from
  the test import created the task-owned untracked directory
  `sw/spatzBenchmarks/online-softmax-merge/__pycache__/`, so the strict
  only-progress-file status check failed.  The cache was inspected and
  removed directly without `git clean`; no result artifact was modified.
  The failed report, validator, and log SHA256 values are respectively
  `5f64b5b17a9a0ab5cc31a8da85747b1ec8bbcb106e30b5416259aa3cd1fac4d1`,
  `3177204fd48dde19523d1c3096baef99818a325aedb882aed0ed06a5e77c9586`,
  and `9b078cd2c467dc5209e4c7fbc004cfe06684cdd0c496e00a7b68427665938a23`.
- Final checkpoint validation used `PYTHONDONTWRITEBYTECODE=1`, reran all 26
  unit tests, `git diff --check`, every fixed-hash evidence check, and the
  strict single-modified-file status gate.  Its report is
  `/home/wxt/work-online-merge-stage4a-checkpoint-final-validation-20260715T124809Z/validation.json`,
  SHA256
  `3ddc7ac2a1b769ea565d55225767aa28a697525bb3e22e1294404273a27eb9d3`;
  validator SHA256 is
  `3177204fd48dde19523d1c3096baef99818a325aedb882aed0ed06a5e77c9586`,
  and log SHA256 is
  `911a5921fd2d6ce71330c2a8760b9380beb24012a2b592ac7becfcf8ab572577`.
- Tool identities remain CMake `3.28.3`, target Clang/objdump `14.0.6`,
  Verilator `5.034`, and Python `3.12.3`.  Stage 4 remains in progress: the
  next executable batches are the independent `N=2` and `N=4` rows, followed
  by the measured break-even table and separately labelled fitted predictions,
  residuals, and R² for B2-R and B3.

### Stage 4b checkpoint: clean break-even N=2 batch

- Objective: collect and independently validate the `N=2`,
  `D={1,8,16,32}` row of the required break-even matrix using a unique
  external build and the established 14 explicit fresh-cache definitions.
- Formal evidence is retained under
  `/home/wxt/work-online-merge-stage4-break-even-n2-clean-20260715T125242Z`;
  its unique external build is
  `/home/wxt/work-online-merge-build-stage4-break-even-n2-clean-20260715T125242Z`.
  The exact uppercase case file is
  `/home/wxt/work-online-merge-stage4-break-even-n2-clean-20260715T125242Z.cases.json`,
  SHA256
  `33d2922054bd63c18078b912a13135cfdd00d283040517af344652b912815506`.
  Provenance is commit `074d6110e5820377366149b695974769e8a8b085`,
  `git_dirty=false`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  The exact command window was
  `2026-07-15T12:52:43+00:00..2026-07-15T13:28:40+00:00`, with a
  1,800-second per-case simulator timeout.
- Fresh configure, target build, RVV objdump gate, and simulator commands all
  returned zero for all four cases.  All 36 B1/B2-R/B3 records pass and are
  finite, all 16 command records pass, `failures.json` is empty, and the
  runner return code is zero.  Cycle min/median/max values are:
  - `D=1`: B1 `4168/4217/4460`, B2-R `3346/3387/3606`, and B3
    `1097/1106/1152`;
  - `D=8`: B1 `8992/9119/9371`, B2-R `3282/3426/3572`, and B3
    `1219/1228/1268`;
  - `D=16`: B1 `14513/14764/14817`, B2-R `3374/3455/3642`, and B3
    `1342/1351/1389`;
  - `D=32`: B1 `24781/24999/25059`, B2-R `3420/3504/3518`, and B3
    `1604/1610/1612`.
  Median B3 speedups versus B2-R are respectively `3.0624`, `2.7899`,
  `2.5574`, and `2.1764`; these are direct same-case cycle ratios, not model
  predictions or physical-performance claims.
- The largest absolute error is `9.900331497192383e-05`, largest relative
  error is `9.900331497192383e-05`, and largest RMSE is
  `1.2030378454469542e-05`.  Footprints are 96, 320, 576, and 1,088 bytes;
  allocator-rounded working sets are 256, 512, 768, and 1,280 bytes, or at
  most `0.009765625` of the 128 KiB TCDM.  B1 and B2-R have no congested
  accesses.  B3 records have at most one congested access; the maximum
  measured congestion ratio is `0.0030211480362537764`.  The retained
  CSV/JSON records also contain cycles per element, elements per cycle, TCDM
  accesses, and congestion ratio.  These are simulator counters and
  correctness diagnostics, not physical PPA or energy evidence.
- Independent validation reconstructed all 36 records from raw `OM_RESULT`
  fields, compared CSV and JSON semantically, reproduced all 12 summary rows,
  checked the exact case file and normalized manifest, verified all 19 final
  cache values and 16 command records, reran all four RVV disassembly gates,
  and rehashed all 38 artifact-manifest entries.  The passing report is
  `/home/wxt/work-online-merge-stage4-break-even-n2-final-validation-20260715T125321Z/validation.json`,
  SHA256
  `bc393bb4b7b1e0359bf5c5b7415056cc4d8bafa7be6fe25411195404089295d0`;
  validator SHA256 is
  `840c5e6cf50daff03fa137c37f1ce2af978cbcbb5bbce8f42e547a0e689a5eef`,
  validator-log SHA256 is
  `382bb50a3f35633f7556b9166666970e273255e4a6e5fde5ca2259d2e0512b99`,
  and validator return-code-file SHA256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
  Independent RVV rerun-log SHA256 values for `D=1,8,16,32` are respectively
  `d656c40b68d25f571c6346361add9688e08a1149b01773fa5d5766b041adac72`,
  `5678101adc0f97c7013e452c2396b3c80e666af8c5efb636b24476c09860c61d`,
  `8d43819d0ab32e811c08bb796bf3190cc013e18b95f4b797f6dcef5031443ad4`,
  and `10ad23581e925bf220d07ac9d7fb3aa9a48bc9bb85a5233b9bc20b0ae3606e12`.
- Large hart-0 instruction traces remain outside Git:
  - `N2_D1_S1_main_R3/logs/trace_hart_00000.dasm`: 150,211,672 bytes,
    SHA256
    `5fc5cf351570a8acc5d292991e5fba13a1d7407b13e0119c4e0c1cad09d2ac93`;
  - `N2_D8_S1_main_R3/logs/trace_hart_00000.dasm`: 164,140,496 bytes,
    SHA256
    `efa98b0eaaae8ff74ec0b8dfddb55d90299a8fa38bff6a4c88bd446adf63fdb3`;
  - `N2_D16_S1_main_R3/logs/trace_hart_00000.dasm`: 179,180,041 bytes,
    SHA256
    `4f7449ab5dc43fb9fc268d59f3cd84f83ed1632cdbc45f6ea8871a12bb44e339`;
  - `N2_D32_S1_main_R3/logs/trace_hart_00000.dasm`: 209,842,699 bytes,
    SHA256
    `a628f5b0b7fa1eedb2558b05618eec7c7f1613be0c92ca599a55f36c5d2ebc85`.
  Paths are relative to the formal result root above.  No trace, build product,
  ELF, or simulator log is committed.
- Formal top-level SHA256 values are:
  - `run_manifest.json`:
    `6869f5d4507a098f05d379b597462304f22434739c13ef550b7660d0ccab22fc`;
  - `records.json`:
    `03b6178fda9fefb53ba939ea14c2f3b224a82e18ff22bd4844c2462ab844fb7d`;
  - `records.csv`:
    `660921bc8d2fafd0c7447dba8732a0741bc5718c1db1615ed332e8d0192cdd82`;
  - `summary.json`:
    `7f62e1cb86ea6fe1006ba13c0b0e793f54f6ae887ce2fe6002d8546c78b38a49`;
  - `commands.json`:
    `ae8e927383b835028ae9de49db16a8b08bee3574515d6bfe72b85690a07dbe31`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `286825db19aeec57ae624ab561cf6a37fd0011246d4227b837d099f2c5e476cc`;
  - external runner log:
    `3dd6cb3f55e5a6d5568edae665b630e2306e4aac5be41c53a38711cf48f98386`;
  - external runner return-code file:
    `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- Tool identities remain CMake `3.28.3`, target Clang/objdump `14.0.6`,
  Verilator `5.034`, and Python `3.12.3`.  Stage 4 remains in progress: the
  next executable batch is the independent `N=4` row, after which the already
  validated `N=8` small-D evidence will close the 16 direct break-even points
  for the measured table and the separately labelled B2-R/B3 fitted models,
  residuals, and R².
- A first checkpoint-validator-only attempt is retained at
  `/home/wxt/work-online-merge-stage4b-checkpoint-validation-20260715T133600Z`.
  All evidence, status, and 26 unit-test checks passed, but
  `git diff --check` correctly rejected a newly added blank line at EOF.  The
  progress file was corrected without changing any result artifact.  The
  failed report, validator, log, and return-code-file SHA256 values are
  respectively
  `4ba1dcb61029302f96d08eefed99e28e2865fe6bd3273e18b956425e3bdb2702`,
  `26795d5c20409034ad6c62096aa73ba2d20c2c91b9e1b49b1cef83fdb3a01ed6`,
  `ff45a82b8758db25a9ab0dd2eceb464b7fb20e764d6a0a15cdfc29837b529691`,
  and `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`.
- Final checkpoint validation used `PYTHONDONTWRITEBYTECODE=1`, reran all 26
  unit tests, `git diff --check`, every fixed-hash evidence check, provenance
  and case-coverage checks, the independent-report gate, and the strict
  single-modified-file status gate.  Its report is
  `/home/wxt/work-online-merge-stage4b-checkpoint-final-validation-20260715T133900Z/validation.json`,
  SHA256
  `ef6bd004a955d74edc9995d3fd839cdf0af0ea5167a28f8a856f79b93d48bc83`;
  validator SHA256 is
  `994d71dbec8a5b4cb91bcc13ce06f43ba1f439ca891338043c9838bcd1cf8015`,
  validator-log SHA256 is
  `2c0288051172381ec7b3650fd67bb20b22f6c1cab1396b69574ddcea7d93cc8c`,
  and return-code-file SHA256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.

### Stage 4c checkpoint: clean break-even N=4 batch

- Objective: collect and independently validate the `N=4`,
  `D={1,8,16,32}` row of the required break-even matrix using a unique
  external build and the established 14 explicit fresh-cache definitions.
  Together with the previously validated `N=1`, `N=2`, and `N=8` rows, this
  closes all 16 directly measured break-even coordinates without model
  interpolation.
- Formal evidence is retained under
  `/home/wxt/work-online-merge-stage4-break-even-n4-clean-20260715T134404Z`;
  its unique external build is
  `/home/wxt/work-online-merge-build-stage4-break-even-n4-clean-20260715T134404Z`.
  The exact uppercase case file is
  `/home/wxt/work-online-merge-stage4-break-even-n4-clean-20260715T134404Z.cases.json`,
  SHA256
  `681bb6fa1e81b184eb08017274e9fcfd643f9be4da2e376fd8063e7904d529f4`.
  Provenance is commit `2a406d8c83cf02969a5b0df39423933919c0792a`,
  `git_dirty=false`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and simulator SHA256
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  The exact command window was
  `2026-07-15T13:44:04+00:00..2026-07-15T14:28:51+00:00`, with a
  1,800-second per-case simulator timeout.
- Fresh configure, target build, RVV objdump gate, and simulator commands all
  returned zero for all four cases.  All 36 B1/B2-R/B3 records pass and are
  finite, all 16 command records pass, `failures.json` is empty, and the
  runner return code is zero.  Cycle min/median/max values are:
  - `D=1`: B1 `8014/8210/8407`, B2-R `6666/6739/6773`, and B3
    `1191/1194/1211`;
  - `D=8`: B1 `17556/17900/18015`, B2-R `6590/6772/6849`, and B3
    `1436/1436/1441`;
  - `D=16`: B1 `28703/28880/28975`, B2-R `6753/6812/6891`, and B3
    `1646/1655/1676`;
  - `D=32`: B1 `50049/50206/50268`, B2-R `6778/6867/7044`, and B3
    `2136/2136/2189`.
  Median B3 speedups versus B2-R are respectively `5.6441`, `4.7159`,
  `4.1160`, and `3.2149`; these are direct same-case cycle ratios, not model
  predictions or physical-performance claims.
- The largest absolute error is `0.00012874603271484375`, largest relative
  error is `9.900331497192383e-05`, and largest RMSE is
  `2.7177340590186426e-05`.  Footprints are 192, 640, 1,152, and 2,176 bytes;
  allocator-rounded working sets are 256, 768, 1,280, and 2,304 bytes, or at
  most `0.017578125` of the 128 KiB TCDM.  B1 and B2-R have no congested
  accesses.  B3 has at most five congested accesses and a maximum measured
  congestion ratio of `0.005482456140350877`.  The retained CSV/JSON records
  also contain cycles per element, elements per cycle, TCDM accesses, and
  congestion ratio.  These are simulator counters and correctness
  diagnostics, not physical PPA or energy evidence.
- Independent validation reconstructed all 36 records from raw `OM_RESULT`
  fields, compared CSV and JSON semantically, reproduced all 12 summary rows,
  checked the exact case file and normalized manifest, verified all 19 final
  cache values and 16 command records, reran all four RVV disassembly gates,
  and rehashed all 38 artifact-manifest entries.  The passing report is
  `/home/wxt/work-online-merge-stage4-break-even-n4-final-validation-20260715T134500Z/validation.json`,
  SHA256
  `1b29de593397d948f257c53685d2f6040ea900c54844e2a6eed6b9c1bda09f5f`;
  validator SHA256 is
  `8ccda36a2b4e53cf7156d1217c4055df72a7c9108e649f567fb9d4b060e03302`,
  validator-log SHA256 is
  `bb910ff5df6e3b533bd5299e8f4d921fb83d824f6361f401bc57f6c850cba439`,
  and validator return-code-file SHA256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
  Independent RVV rerun-log SHA256 values for `D=1,8,16,32` are respectively
  `c2048dfed59d0a1a02c68c9deb1771b17d14facb77157ac2460002c0ed83548c`,
  `8eb3d0988e0ebeb942accf2afebfae78d914731a4ad4c10333c336e19868c0ee`,
  `a79cb2b6819b55950c6695ee2005c64a7cfcccc0ecfe6cb3569c6d963803893c`,
  and `9f37ed4fd497fc01085a226e1bf008af461116f3a6f574e4dcdac64cf2462603`.
- Large hart-0 instruction traces remain outside Git:
  - `N4_D1_S1_main_R3/logs/trace_hart_00000.dasm`: 163,345,878 bytes,
    SHA256
    `a3a6e6c801429e7514606871c029ba041b462b6ec2953fbe565c11272127595c`;
  - `N4_D8_S1_main_R3/logs/trace_hart_00000.dasm`: 189,533,986 bytes,
    SHA256
    `148d4f7c0b7d3e05463bf26a6b1e513105a05541cd431e9ff1ed7fae726cbf3e`;
  - `N4_D16_S1_main_R3/logs/trace_hart_00000.dasm`: 220,243,603 bytes,
    SHA256
    `2b270f84b7d22fd65ab16d04c3d36a7bc1f669fd3ee0e4dc7153bf28a8c03ef6`;
  - `N4_D32_S1_main_R3/logs/trace_hart_00000.dasm`: 279,876,986 bytes,
    SHA256
    `5dab98f91a5b399f01ea1bb456d3c6be1ed61f51228e8d715895ac715d55e226`.
  Paths are relative to the formal result root above.  No trace, build product,
  ELF, or simulator log is committed.
- Formal top-level SHA256 values are:
  - `run_manifest.json`:
    `da0fafe47aa5711aee3a31ccaf87ca0eedffb15c5c85be689e9e29015a0ff510`;
  - `records.json`:
    `70d2629549d0bf1bb0c11efb13aa8628bffcff8e9a2b5127a9789228b4aa3807`;
  - `records.csv`:
    `bb919b90448bcb12645758ff5d0525b31e2c427b94d2687e3e2ef24a0b3e729c`;
  - `summary.json`:
    `b04aaf873635ff4b84f96bcdca974f87c418f23b6decb0c6195798393a354783`;
  - `commands.json`:
    `1b7b95e402ea46f247440cfeb2b5bde75208becaf6d1658a1ba6c63f816b082f`;
  - `failures.json`:
    `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
  - `artifact_manifest.json`:
    `57a32b9e0321dc35730e82522448cb39ba0ecc6adae09728020fd40ae45082ef`;
  - external runner log:
    `e324125e469b5cbdd0f3a45b9dc2c27e5dc941f635863f6bf234393e16be33a0`;
  - external runner return-code file:
    `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- An independently regenerated compact evidence summary is retained at
  `/home/wxt/work-online-merge-stage4-break-even-n4-evidence-summary-20260715T143200Z/evidence_summary.json`,
  SHA256
  `6a4544c6f40fc6c3d8cd468d26386cc6fd27fc15f63b24ad9ea83be1948334f6`.
  Its collector SHA256 is
  `280b96c877499ef9124f91e6e0b61164654102b2168d16527bd1abc82f34469d`.
- Tool identities remain CMake `3.28.3`, target Clang/objdump `14.0.6`,
  Verilator `5.034`, and Python `3.12.3`.  Stage 4 remains in progress only
  for the separately labelled B2-R/B3 fitted models, all residuals, `R²`, and
  the consolidated 16-point directly measured break-even table.  No unmeasured
  coordinate will be presented as direct evidence.

- Stage 4c checkpoint validation used `PYTHONDONTWRITEBYTECODE=1`, reran all
  26 unit tests, `git diff --check`, every fixed-hash evidence check,
  provenance and exact case-coverage checks, the independent report and
  compact-summary gates, and the strict single-modified-file status gate.  Its
  report is
  `/home/wxt/work-online-merge-stage4c-checkpoint-validation-20260715T143600Z/validation.json`,
  SHA256
  `84d73801ae60da57bdb4079f1fd66bd7980f3fa38f12645b9db453aa0c8255ef`;
  validator SHA256 is
  `4ea7ccd7b1c70a2358bae9a58fd17bc14fc88347ce7fc7f2df70c8cc7d090e07`,
  validator-log SHA256 is
  `f8b4e56d9572e03b2589117aba6eaccc0258857d218f1bca4407c7b61a907fc6`,
  and return-code-file SHA256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.


### Stage 4d checkpoint: deterministic scaling analyzer implementation

- Objective: implement the separately labelled B2-R/B3 scale-model fit,
  residual table, and consolidated directly measured break-even analysis before
  running it against the complete clean evidence set.
- The analyzer is
  `util/online_softmax_merge/analyze_scaling.py`, SHA256
  `76c54419cf63c95d5f44865a1389c0a19c3e1139d814be40fd6eaa6adcc1a7d5`.
  It uses standard-library exact rational least squares for
  `C(N,D) = C0 + Cs*N + Cv*N*D + Cstall`, fits B2-R and B3 independently,
  emits exact and decimal parameters, every fitted value and signed residual,
  SSE/SST and `R²`, and reports cycles/element, elements/cycle, congestion, and
  speedup versus B2-R.  Here `Cstall` is explicitly a fitted residual, not a
  physical stall counter.
- The directly measured break-even table uses only retained medians and the
  definition `C_smu(N,D) <= C_rvv(N,D)`.  Model fits and measured decisions
  remain separate; missing cells remain missing and cannot be populated by an
  extrapolation.  The analyzer requires a complete requested grid before
  accepting formal output.
- Input controls reject duplicate roots, conflicting duplicate records, dirty
  input provenance, inconsistent CFG or simulator identities, and missing
  measurement/validation metadata.  Equivalent repeats may differ only in
  their source root and Git commit provenance.  All non-pass records and all
  `failures.json` entries are copied into the analysis rather than filtered
  out.  Outputs are deterministic `analysis.json`, `model_residuals.csv`,
  `break_even.csv`, and `artifact_manifest.json` under a fresh external
  `work-online-merge-*` directory.
- The external reviewed source is
  `/home/wxt/work-online-merge-stage4-analysis-review-20260715T141000Z/`
  `analyze_scaling.py`, with the same SHA256 as the repository analyzer.  Its
  enhanced diagnostic smoke is
  `/home/wxt/work-online-merge-stage4-analysis-review-smoke-20260715T141500Z`.
  Before the N=4 batch was added, that smoke accepted all provenance gates,
  fit 19 unique coordinates per model, retained 180 pass and nine timeout raw
  records, retained nine non-pass records and two failure entries, and
  identified six equivalent B2-R/B3 duplicate repeat records.  Diagnostic
  `R²` values were `0.9997413491369759` for B2-R and
  `0.9999730794879631` for B3.  These are implementation smoke values, not the
  final complete-model evidence.  Its top-level SHA256 values are:
  - `analysis.json`:
    `7cc83f5dfd55af3ed3abbc30f4b02415415ba4ee1b599a1023601e847c320a02`;
  - `model_residuals.csv`:
    `f367497b6b1c3968071d4a4177d17cf025fe4d29cdd66c52db47a609b0e9c30c`;
  - `break_even.csv`:
    `af52bca8375400df574b9ff814dfe6c52d15de22edfbd6e7e3896016bf67fcbe`;
  - `artifact_manifest.json`:
    `b85bf4129e687d2f55e6210d21112a7ae1a343e09191db6105eef3bee1f164e1`.
- The initial repository test invocation correctly preserved an integration
  failure: the copied test searched its own `tests/` directory rather than the
  analyzer's parent directory and raised
  `ModuleNotFoundError: No module named 'analyze_scaling'`.  Evidence is
  `/home/wxt/work-online-merge-stage4-analysis-import-failure-20260715T144400Z/`
  `test.log`, SHA256
  `9ede141e36716941df2cfdadf08d05a146787a4c8f4ae9945d35cb6aa3734187`;
  return-code-file SHA256 is
  `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865`.
  The module path was then made repository-relative without hard-coded
  workspace paths.
- Validation at commit base
  `4f968841fd7738ffb757270888c0d625537fc23a` covered exact synthetic-model
  recovery, nonzero residuals and `R²`, direct minimum-D selection,
  provenance-only deduplication, conflicting-evidence rejection, retained
  non-pass/failure evidence, duplicate-root rejection, deterministic outputs,
  and external output-directory enforcement.  The analyzer-specific 9/9 tests
  and the full 35/35 discovery both passed with bytecode disabled.  Logs are in
  `/home/wxt/work-online-merge-stage4-analysis-tests-20260715T145559Z`; the
  analyzer-test log SHA256 is
  `f4384cf68cf890c1c46094f0f88a78e8e6025d0cde85f68cad67ab0309cb496c`,
  the full-discovery log SHA256 is
  `dfbfec029bb12d5ff9fda92226623cfb964d5003e486e31a5cdaf3cc7b4c6b1f`,
  and both return-code files have SHA256
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
  The UTC validation window was
  `2026-07-15T14:55:59Z..2026-07-15T14:55:59Z`; Python was 3.12.3.
- The clean Stage 4c synchronization immediately preceding this implementation
  is retained at
  `/home/wxt/work-online-merge-stage4c-sync-20260715T143847Z/sync.json`,
  SHA256
  `063f997202bea1a8748cbf66d4c14f582f37bd1634a117b4446dd57a228532c3`.
  Fetch, pull with rebase, and push all returned zero and left synchronized
  HEAD `4f968841fd7738ffb757270888c0d625537fc23a` clean.
- The Stage 4d checkpoint validator rechecked the exact four-file status,
  analyzer/reviewed-source identity, executable mode, Python syntax, 9/9
  analyzer tests, 35/35 full tests, CLI help, tracked and untracked diff
  whitespace, README protocol, retained import failure, and all reviewed-smoke
  hashes.  Its passing report is
  `/home/wxt/work-online-merge-stage4d-checkpoint-validation-20260715T151019Z/`
  `validation.json`, SHA256
  `b0659e11a8a78da5c279918fa27e6bb7218819c03fe080a56d7b4786f183f457`;
  validator SHA256 is
  `c2f8af733ddc7b0605bdd06f997ca4e9680df04984fdec4d0fac58c88146b55a`,
  validator-log SHA256 is
  `145ca887f0ff16a524cc85f73797774e9ce046a4780d1b6642918060b363d338`,
  and return-code-file SHA256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- This checkpoint implements and tests the analyzer only.  The formal complete
  23-coordinate-per-model fit and 16-point break-even consolidation must run
  from the clean committed analyzer checkpoint and will be indexed separately.


### Stage 4e checkpoint: formal scale model and break-even closure

- Objective: run the committed analyzer on every clean mandatory-matrix and
  break-even evidence root, retain inherited timeout/failure evidence, publish
  the independently refitted B2-R/B3 models, and close the directly measured
  16-point break-even table.
- Before the formal run, Stage 4d synchronization retained one transient push
  failure.  Fetch and pull with rebase returned zero, but the first push failed
  with `gnutls_handshake() failed: The TLS connection was non-properly
  terminated`.  The local checkpoint remained clean and ahead by one; no
  force-push or merge was used.  Failure metadata is
  `/home/wxt/work-online-merge-stage4d-sync-20260715T151245Z/sync.json`,
  SHA256
  `445ae6068d630c2da290c831a439210bd7a81bb78bbedbe693e381b4f49acbcd`;
  failed push-log SHA256 is
  `420fc1a2233169e32370cab0bae57b75558322d10a38803d6baf79dbd69dfdb4`.
  A periodic retry succeeded and synchronized commit
  `821d36b777c90db8394be2d59e1b3de9a51702d3`; retry metadata is
  `/home/wxt/work-online-merge-stage4d-push-retry-20260715T151348Z/retry.json`,
  SHA256
  `214ba2b98236667c0b894e9ab89d4c9349d2c9675b9dd047bc12d4b0088ad0ed`;
  successful push-log SHA256 is
  `1094a81ffb4f7863cb50c7c76884c19927e61c315b88b4b6a7c2d5de4c092db2`.
- Formal analysis ran from that clean synchronized commit and used exactly the
  following nine roots:
  - `/home/wxt/work-online-merge-stage3-matrix-d64-clean-20260715-062750`;
  - `/home/wxt/work-online-merge-stage3-matrix-d64-n8-formal-clean-20260715-080002`;
  - `/home/wxt/work-online-merge-stage3-matrix-d64-n16-formal-clean-20260715-080049`;
  - `/home/wxt/work-online-merge-stage3-matrix-d64-n32-formal-clean-20260715-080837`;
  - `/home/wxt/work-online-merge-stage3-n8-d-small-clean-20260715T103315Z`;
  - `/home/wxt/work-online-merge-stage3-n8-d128-clean-20260715T112512Z`;
  - `/home/wxt/work-online-merge-stage4-break-even-n1-clean-20260715T120725Z`;
  - `/home/wxt/work-online-merge-stage4-break-even-n2-clean-20260715T125242Z`;
  - `/home/wxt/work-online-merge-stage4-break-even-n4-clean-20260715T134404Z`.
- The formal result is
  `/home/wxt/work-online-merge-stage4-scaling-formal-20260715T151558Z`.
  Analysis command metadata is
  `/home/wxt/work-online-merge-stage4-scaling-formal-command-20260715T151558Z/`
  `run.json`, SHA256
  `e17a9a483d38b037b153c4c3b18e5210a39482d4a47317cacdf1b5329550291f`.
  The analysis window was
  `2026-07-15T15:15:58Z..2026-07-15T15:15:58Z`; the underlying measurement
  roots span `2026-07-15T06:27:50+00:00..2026-07-15T14:28:51+00:00`.
  CFG SHA256 is
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`;
  simulator SHA256 is
  `25a56d98474895d16d7de81f73d9cf8a06ba8eb650af5f9b58a012d15022e69a`.
  Tools remain Python 3.12.3, CMake 3.28.3, target Clang/objdump 14.0.6,
  Verilator 5.034, and analyzer SHA256
  `76c54419cf63c95d5f44865a1389c0a19c3e1139d814be40fd6eaa6adcc1a7d5`.
- All eight formal acceptance gates passed.  The analyzer retained 225 raw
  records with status counts `pass=216` and `timeout=9`, retained all nine
  non-pass records and both failure entries, and identified six equivalent
  duplicate B2-R/B3 repeat records without conflicts.  After exact
  deduplication, each model has the same 23 unique seed-1/main coordinates and
  three contiguous repeats per coordinate.  The inherited timeouts and failure
  entries remain part of the evidence and were not used as passing fit points.
- Exact rational least-squares parameters, with decimal cycle interpretations,
  are:

  | Model | `C0` | `Cs` per row | `Cv` per element | `R²` |
  | --- | ---: | ---: | ---: | ---: |
  | B2-R | 483.353185 | 1538.126851 | 2.056380 | 0.9997383363 |
  | B3 | 1058.654226 | 22.029195 | 7.994777 | 0.9999669373 |

  The exact numerators and denominators, SSE, SST, every fitted value, and all
  46 signed `Cstall` residuals are in `analysis.json` and
  `model_residuals.csv`.  These terms distinguish fixed startup, scalar
  per-row, and vector per-element costs; they are simulator-cycle fit terms,
  not physical latency, power, or energy quantities.
- The largest absolute B2-R residual is 394.877647 cycles at `(N,D)=(32,64)`;
  every B2-R fitted point has median `tcdm_congested=0`, so this deviation
  cannot be attributed to measured TCDM congestion.  The largest absolute B3
  residual is 51.483707 cycles at `(1,32)`.  B3's largest median congestion is
  76 accesses with ratio `0.007769372316499694` at `(32,64)`; residual signs
  do not vary monotonically with congestion, for example `(16,64)` has
  residual `-41.773` cycles while `(32,64)` has `+22.108` cycles.  Therefore
  the high `R²` values support a useful compact fit but not a claim of strict
  linearity or a causal congestion model.  `Cstall` remains explicitly a
  signed residual rather than a directly measured stall counter.
- The direct measured break-even table is complete.  Each cell below is
  `B2-R median cycles / B3 median cycles`; all cells satisfy
  `C_smu(N,D) <= C_rvv(N,D)`:

  | `N` | `D=1` | `D=8` | `D=16` | `D=32` | minimum measured `D` |
  | ---: | ---: | ---: | ---: | ---: | ---: |
  | 1 | 1966 / 1124 | 1968 / 1121 | 1995 / 1203 | 1977 / 1388 | 1 |
  | 2 | 3387 / 1106 | 3426 / 1228 | 3455 / 1351 | 3504 / 1610 | 1 |
  | 4 | 6739 / 1194 | 6772 / 1436 | 6812 / 1655 | 6867 / 2136 | 1 |
  | 8 | 13080 / 1290 | 12885 / 1732 | 13078 / 2281 | 13547 / 3263 | 1 |

  Direct speedup ranges from `1.4243515850144093` at `(1,32)` to
  `10.13953488372093` at `(8,1)`.  This table makes no monotonicity claim and
  no claim about unmeasured `D`; model predictions are not mixed into the 16
  measured rows.  The retained records and residual CSV also report
  cycles/element, elements/cycle, TCDM accessed/congested/ratio, and speedup
  for every fitted coordinate.
- Formal top-level SHA256 values are:
  - `analysis.json`:
    `451f3402cfc0aae61437c359edeea0df22ba095ddb53439b8d2a223547fedcb5`;
  - `model_residuals.csv`:
    `b3b2cf0911c96d2ded302cad5d567e6b14dfe0780b94553a33d68689c996b3fe`;
  - `break_even.csv`:
    `106fd1a0decd6430a8584400bed301ff323b279ecfbd25fe83d40cec65fd984c`;
  - `artifact_manifest.json`:
    `fecbee0ac896fbaa645dedb9e3e7353a179830329008220e94c7cca590f28d43`.
- Independent validation did not import the repository analyzer.  It rehashed
  every input manifest/record/failure file, reconstructed all status and
  failure projections, independently deduplicated the six equivalent repeats,
  rebuilt the exact 23-coordinate medians and rational normal-equation fits,
  matched all model parameters/residuals and both CSV files, verified the
  direct 16-cell table and clean provenance, and reran the committed analyzer
  to a fresh directory.  The deterministic rerun at
  `/home/wxt/work-online-merge-stage4-scaling-determinism-20260715T152231Z`
  produced byte-identical files and the same four SHA256 values.  The passing
  report is
  `/home/wxt/work-online-merge-stage4-scaling-validation-20260715T152231Z/`
  `validation.json`, SHA256
  `d724a6df9de521d9dabb5ed77206f68741f790a01a30f78d0e1ad5ad104ff4b3`;
  validator SHA256 is
  `f0511d7acbe5f9c9d7831a50c57f8cc1f20ff662692c93022b2ff4b9441d3426`,
  validator-log SHA256 is
  `0839e82e60d9559495fdaa4a727924f9eeed345e163da29fa14678cda4e13038`,
  and return-code-file SHA256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- The Stage 4e checkpoint validator rechecked the exact single-file status,
  all formal and independent-validation hashes, acceptance/status/failure and
  duplicate counts, both 23-point models, all 46 residual rows, all 16 direct
  break-even rows, the progress-index values, 35/35 unit tests, and
  `git diff --check`.  Its passing report is
  `/home/wxt/work-online-merge-stage4e-checkpoint-validation-20260715T154055Z/`
  `validation.json`, SHA256
  `65879b9a64fc22720aae5c5b21f3851c5ee90ad4a0731c1afce8fb4c6187f3d8`;
  validator SHA256 is
  `77277ca608e5eaab04864126db938f25b29b0901b850015b12a65fbf1ffe9ce8`,
  unit-test-log SHA256 is
  `6b87034c8400f1aff10372010a5b608604c231f28ef337746a01cbfb6fbf0b48`,
  validator-log SHA256 is
  `81c17617dc4ecd2b02a57800d75bac3506b73eddc6c85cbef72cb7e6f65a43f3`,
  and return-code-file SHA256 is
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- Stage 4 acceptance is complete: both mandatory matrices have retained status
  records, capacity/timeout/failure evidence remains preserved, the directly
  measured break-even table and exact fitted parameters/residuals/`R²` are
  published, the model separates fixed, per-row, and per-element terms, and
  all capacity claims continue to use the compact allocator-rounded footprint.
  The next P0 stage is the Full-SMU FSM cycle decomposition and A0/A2.

- Synchronization of the Stage 4e checkpoint itself also retained one transient
  push failure after successful fetch and pull with rebase.  The clean local
  commit `c91200cdc6e95ecf25fb80255485a5781459375c` remained ahead by one; no
  force-push or merge was used.  Failure metadata is
  `/home/wxt/work-online-merge-stage4e-sync-20260715T154341Z/sync.json`, SHA256
  `0f3e94a19a1bead532de3b7a11e93be56720d5880b438ec2f02b226887a7549a`;
  failed push-log SHA256 is
  `420fc1a2233169e32370cab0bae57b75558322d10a38803d6baf79dbd69dfdb4`.
  A periodic retry synchronized the same commit; retry metadata is
  `/home/wxt/work-online-merge-stage4e-push-retry-20260715T154450Z/retry.json`,
  SHA256
  `e3d861fe10f75c2765dfeb8b0ed3d209cebbaf8b27f743cc459ca13285e8bac0`,
  and successful push-log SHA256 is
  `55514b06b50b2c1024eeea4c1df52b1ab7eaa480603ff7c399d5587952d507fe`.


### Stage 5a checkpoint: Full-SMU FSM observer and analyzer

- Objective: add the non-functional observation and deterministic analysis
  support required by specification section 4 before taking formal A0/A2
  measurements at `(1,1)`, `(8,32)`, and `(16,64)`.
- `hw/ip/online_merge/src/online_merge_update_engine.sv` now contains a
  simulation-only observer inside `translate_off/on`; it changes no port or
  functional signal and its counters do not feed functional RTL.  Source
  SHA256 is
  `58417827163f6351e52003c08ee8cd6fbbf6b75ace609aecf93d951aadb28439`.
  It emits one `OM_FSM` JSON record at each `DONE` or `ERROR`: invocation zero
  is the benchmark warm-up and invocations `1..R` map to measured repeats
  `0..R-1`.  Each record retains `N`, `D`, terminal state, the five state
  counts, and their busy-cycle sum.
- The five mutually exclusive busy-state groups are `LOAD_SCALAR`,
  `COMPUTE_SCALAR`, `COMPUTE_WEIGHT`, `STORE_SCALAR`, and `UPDATE_VECTOR`.
  Scalar share is the sum of the first four states, vector share is
  `UPDATE_VECTOR`, and the non-overlapping command/setup/wait/error remainder
  is `A2_end_to_end_cycles - busy_cycles`.  Completion polling overlaps SMU
  busy execution and is therefore not added to the FSM-state totals.
- `util/online_softmax_merge/analyze_fsm.py`, SHA256
  `cf5ac0414744e0c541a1cd33af1cda8824fe430ba1797f7d74c31f5795dcc18d`,
  loads runner manifests, records, failures, commands, and simulator logs.  It
  requires clean and consistent commit/CFG/simulator/window provenance,
  correctness, repeat order, exact RTL enum/state expression, contiguous
  invocations, `DONE` terminals, exact state sums, and
  `busy_cycles <= A2_end_to_end_cycles`.  Complete non-pass records and every
  `failures.json` entry remain in the report.  Its deterministic external
  outputs are `analysis.json`, `fsm_observations.csv`, `fsm_breakdown.csv`,
  `ablation_a0_a2.csv`, and `artifact_manifest.json`.
- The README documents the observer/runner/analyzer commands, measurement
  mapping, overlap rule, reconciliation gates, output schemas, and the
  non-physical interpretation.  Eleven focused analyzer tests bring the
  complete suite to 46 tests.
- Final implementation validation ran during
  `2026-07-15T17:35:56Z..2026-07-15T17:35:57Z` at
  `/home/wxt/work-online-merge-stage5a-final-validation-20260715T173556Z`.
  All 46 unit tests, `py_compile`, Python/SystemVerilog line-length checks, and
  `git diff --check` passed.  `result.json` SHA256 is
  `ac5715cd29ee220eb683aef8f879c4838c12569dd9ef46252586c9968d762a7c`;
  unit-test-log SHA256 is
  `8916dacbb25a30cf06a3f0333c4d63d8569de2a171d951fdbcd9bd05506f6c81`.
  An earlier validation at
  `/home/wxt/work-online-merge-stage5a-validation-20260715T172940Z`
  correctly failed its SystemVerilog 100-column gate; the three pre-existing
  expressions were subsequently wrapped without functional change and that
  failed attempt remains preserved.
- A detached external integration build reused the complete offline Bender
  database at `/home/wxt/spatz/.bender` and passed the Verilator `verilate`
  target during `2026-07-15T17:36:39Z..2026-07-15T17:38:48Z`.  Context is
  `/home/wxt/work-online-merge-stage5a-vlt-final-20260715T173639Z/context.txt`,
  SHA256
  `d5807bc39f49241d7a97d7a5ad2cc8aa8c5e50f957ca5ba14f58caf125eca442`;
  log SHA256 is
  `82e81e5b383dfec7febccd7a1df5cb7d7bc51d671830ffcc6b9171d2464ed0e0`.
  Tools were Bender 0.29.1, Verilator 5.034, and
  `/home/wxt/spatz/.venv/bin/python`; CFG SHA256 remained
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`.
  The generated archive is external at
  `/home/wxt/work-online-merge-stage5a-vlt-offline-retry4-20260715T172648Z/`
  `build/Vtestharness__ALL.a`, SHA256
  `53c6a72e8b99cf2ab41b2d84ec3cbae51965135752c51a319a17d4ca9a34be5b`.
  This target did not yet link `spatz_cluster.vlt` and is not formal
  measurement evidence.
- All unsuccessful integration attempts remain external diagnostic
  `tool_error` evidence, not measurements:
  - network dependency fetch failure/interruption:
    `/home/wxt/work-online-merge-stage5a-vlt-validation-20260715T164938Z`;
    log SHA256
    `bbc7c34e6708db2720cf8f24618fc76308aa267e7be36667651ec5d47467af7f`,
    failure-metadata SHA256
    `b850bac3667d0f27b61eafc9ef5a6b86d3b109cb79a1f0acf1ba35b9e5d7019e`;
  - missing generated `bootdata_bootrom.cc`:
    `/home/wxt/work-online-merge-stage5a-vlt-offline-20260715T171716Z`, log
    SHA256
    `9619d9fea36da05bc2c5811b52bbb345b25b3df9106b09909e60b1f107b72036`;
  - system Python missing `hjson` during cluster generation:
    `/home/wxt/work-online-merge-stage5a-generated-support-20260715T171934Z`,
    failure-metadata SHA256
    `a047d6d961b10ef7e76d8344a7b2a69e818c23b05a91d137b019e80d321e56b4`;
  - detached source missing the ignored `install` symlink:
    `/home/wxt/work-online-merge-stage5a-vlt-offline-retry-20260715T172313Z`,
    log SHA256
    `6605510ce900f68caadd3612ae2ebb0ffe33a7b581c52f8a8a963f6207d6da38`;
  - missing `sw/toolchain/riscv-opcodes/encoding.h`:
    `/home/wxt/work-online-merge-stage5a-vlt-offline-retry2-20260715T172500Z`,
    log SHA256
    `7b293815c822c610bf47446489bd0b1d09364b345369217d65d651702c3abb21`;
  - system Python missing `hjson` during boot-ROM generation:
    `/home/wxt/work-online-merge-stage5a-vlt-offline-retry3-20260715T172617Z`,
    log SHA256
    `2eca06a4239629bbb0ae0b07bf44098a430cb2ee98ab127629e163cbd7a99f9f`.
  Successful generated support using the project virtual environment is at
  `/home/wxt/work-online-merge-stage5a-generated-support-20260715T172216Z`.
- This checkpoint claims only implementation, unit/style validation, and a
  successful unlinked Verilator integration compile.  It claims no formal
  A0/A2 cycles, speedup, state shares, or TCDM numbers.  Formal acceptance
  remains pending until the exact clean checkpoint commit is used to link the
  simulator, run one warm-up plus at least three measured repeats at all three
  required coordinates, observe exactly four valid `OM_FSM` records per log,
  and independently reproduce every analyzer value and output hash.

### Stage 5b checkpoint: exact three-point FSM/A0-A2 closure

- Formal measurements and analysis use the clean detached source at exact
  commit `9d812be187fcf07359e80537031850c313ad5954`.  The linked simulator is
  `/home/wxt/work-online-merge-stage5b-vlt-exact-20260715T175424Z/source/`
  `hw/system/spatz_cluster/bin/spatz_cluster.vlt`, SHA256
  `73b9138e49f7d8b095250a0867d03063b9afb494bbf7e9ca300faf70a70e4cc8`.
  It was built during `2026-07-15T17:54:47Z..2026-07-15T17:57:05Z`
  with Bender 0.29.1, Verilator 5.034, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and the Stage 5a observer source SHA256 recorded above.
- Two pre-measurement `tool_error` attempts are retained rather than hidden.
  Lowercase case keys failed runner preflight before simulation; its index is
  `/home/wxt/work-online-merge-stage5b-formal-20260715T175943Z/evidence/`
  `preflight-tool-error-index-20260715T180803Z.json`, SHA256
  `d4b0f1edb71a606cbb77aacba9ae926ce389ab44445136b9cda427fceae937bd`.
  A malformed shell retry wrapper never invoked the runner; its record is
  `parallel-shell-tool-error-r1-20260715T180803Z.json`, SHA256
  `a300de17a22432421f6892f1d0d17c2ae7353a84ec1f6020ab20a5e6527a062b`.
  Neither attempt produced or influenced measurements.
- The corrected formal run spans
  `2026-07-15T18:10:03Z..2026-07-15T18:32:51Z` and has three clean roots:
  `/home/wxt/work-online-merge-stage5b-fsm-r2-20260715T180948Z-n1d1`,
  `...-n8d32`, and `...-n16d64`.  Their `run_manifest.json` SHA256 values are,
  respectively,
  `118b71aaf7c923715a97be8560a3f1023bfde693f00209e5cfa10d415ce6f019`,
  `fd97dc84c1036410513123d8b19d13e71c7651de42ca3b52c9596fd60bc0c6a4`,
  and `feb7e1024661fced81fabe42ff708fc8f76d2d390421d37fd7b0549088f8e911`.
  Every root has nine passing B1/B2-R/B3 records, no failure entry, and exactly
  four parseable `OM_FSM` records: one warm-up and three measured invocations.
- The medians below are exact measured Verilator cycles.  `Other` is the
  non-overlapping `A2 end-to-end - busy` remainder.  Scalar/vector percentages
  divide by busy cycles; `Other %` divides by A2 end-to-end cycles.  TCDM cells
  show `accessed/congested` and the exact ratio follows in parentheses.

  | `(N,D)` | A0 | A2 | A0/A2 | Scalar | Vector | Busy | Other |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
  | `(1,1)` | 1966 | 1124 | 1.749110 | 20 | 9 | 29 | 1095 |
  | `(8,32)` | 13547 | 3263 | 4.151701 | 160 | 2063 | 2223 | 1040 |
  | `(16,64)` | 27532 | 9556 | 2.881122 | 320 | 8214 | 8534 | 1022 |

  | `(N,D)` | Scalar % | Vector % | Other % | A0 TCDM | A2 TCDM |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | `(1,1)` | 68.9655 | 31.0345 | 97.4199 | `129/0` (0) | `321/0` (0) |
  | `(8,32)` | 7.1975 | 92.8025 | 31.8725 | `825/0` (0) | `1524/11` (0.007218) |
  | `(16,64)` | 3.7497 | 96.2503 | 10.6949 | `2337/0` (0) | `5036/38` (0.007546) |

  The scalar state medians `(load, compute-scalar, compute-weight, store)` are
  `(13,1,1,5)`, `(104,8,8,40)`, and `(208,16,16,80)`, respectively.  All A0
  and A2 correctness checks pass.  Maximum A2 absolute/relative errors are
  `1.25170e-6/1.25170e-6`, `6.03199e-4/1.47368e-4`, and
  `2.59399e-4/1.61854e-4` in coordinate order.
- Final deterministic analysis is at
  `/home/wxt/work-online-merge-stage5b-fsm-analysis-20260715T183542Z`.
  All 16 analyzer acceptance gates pass.  Output SHA256 values are:
  `analysis.json`
  `e964a64d8afd06df09d3859bc333726687bf5c0facee164da24b5e77111bae76`,
  `fsm_observations.csv`
  `7222a66a2874bb81d1ef4cd48aea9d4adf6c4889784f5e942b580896493076ad`,
  `fsm_breakdown.csv`
  `f4dd2ecebf81db5e2127029b647553c90f560fa08bf27dd38489adcd83dff1ac`,
  `ablation_a0_a2.csv`
  `ca8043fa7f835f6098de58751cc080524be14d8f1b2ce06ff43572461ccc8b6e`,
  and `artifact_manifest.json`
  `e10fc57340a950faf4dc195db36def4fe1f926957c1a231c16bc4160a2ca1027`.
  A fresh rerun at
  `/home/wxt/work-online-merge-stage5b-fsm-analysis-rerun-20260715T183542Z`
  produced byte-identical copies of all five files; the `cmp` evidence SHA256
  is `29c2fb60432f2e1d91c38678b454793bcac50506bcd3571a815ded351a6eab1b`.
- The independent verifier does not import the repository analyzer.  Its
  source SHA256 is
  `7600455578734fb1c28278d3ba60be419d1908b1d3ab10e812909f8798f4a847`.
  It independently parsed all observer lines, reconstructed state sums,
  medians, shares, speedups, congestion and correctness, checked every input
  and artifact-manifest hash, and matched every analyzer value.  All ten
  independent gates pass in
  `/home/wxt/work-online-merge-stage5b-independent-final-20260715T183604Z.json`,
  SHA256
  `066a199ee81bab1e6b075880fd65782451ab804d214cac13af53a527dadf9841`.
- Checkpoint validation at
  `/home/wxt/work-online-merge-stage5b-checkpoint-validation-20260715T183912Z`
  reran all 46 unit tests, analyzer `py_compile`, `git diff --check`, and status;
  all passed.  `result.json` SHA256 is
  `52f750733ae6096e7adfb2bcf3ecaf6364ba9c53e34f5e6431e1a025d17ee8b7`;
  validation-log SHA256 is
  `d8e8ead6ba85fa638180239a0bd13a432ca641f5d722a87c8f65edd56b1cd36f`.
- Completion polling overlaps SMU busy execution and is not added to state
  cycles.  These are functional-simulation cycle/counter results only; they
  are not physical area, timing, power, energy, or critical-path evidence.
  Stage 5 is complete; the next P0 stage is C0-C3 concurrency and all 16
  relative `addr[6:3]` bank phases.

### Stage 6a checkpoint: concurrency microbenchmark and low-polling schedule

- Objective: establish the target-side C0/C1/C2/C3 schedule required by
  specification section 8 before adding the formal host runner and analysis.
  Stage 6 is `in_progress`, not complete.
- The new
  `test-spatzBenchmarks-online-softmax-merge-concurrency` target uses the
  compact generated merge case and allocates one separate streaming workspace.
  For `R=3` it emits one `OM_CONCURRENCY_META` record and 148 structured
  `OM_CONCURRENCY` records: C0 SMU/register/stream baselines, C1 register-only
  overlap, C2 RVV-stream overlap, and paired standalone/concurrent C3 samples
  at all relative offsets `{0,8,...,120}` bytes.  There are 76 SMU invocations
  for exact pairing with the simulation-only `OM_FSM` observer.
- C1 is a runtime-calibrated, register-only integer loop.  Its target symbol
  has a loop back-edge and zero load/store instructions.  The polling fallback
  uses the same register-only body for 64 iterations between status reads; the
  first status read occurs only after the core workload.  Every record declares
  zero status reads during the core window and zero counter reads inside the
  measured window.
- C2/C3 use a fixed 2,049-element RVV e32,m8 copy with AVL capped at 8.  Each
  workload transfers 16,392 bytes, its 1-element tail is explicit, and source
  to destination spacing is the same 8,320 bytes at every phase.  Both source
  and destination actual relative `addr[6:3]` phases are checked against the
  requested phase.  SMU output is checked against the generated golden result,
  stream output is bit-exact, and register output is deterministic; terminal
  timeout/error/capacity/unsupported statuses remain structured records.
- Dirty compile evidence is
  `/home/wxt/work-online-merge-stage6a-compile-dirty-20260715T185530Z` with
  external build directory
  `/home/wxt/work-online-merge-stage6a-build-dirty-20260715T185530Z`.
  Configure and target compile/link returned zero.  `result.json` SHA256 is
  `9847490bfead5b84780a259f83ebc8fca6fc8564ac2540ffda38dbd3e52008b5`;
  build-log SHA256 is
  `3f4e10e5293b85540e20d4960ca9781263305639055931f438445f7b70029ae8`.
  The exact ELF SHA256 is
  `e7d06ef5c8d1f2ffd19aeaf8bd8e0623ee6f4448184e9f74d6b814b79b49c681`.
- Disassembly evidence is
  `/home/wxt/work-online-merge-stage6a-disassembly-20260715T185837Z`.
  `/usr/bin/riscv64-unknown-elf-objdump` proves the register loop has no
  load/store or spill and proves the stream symbol contains `vsetvli`,
  `vle32.v`, `vse32.v`, and a strip-mining back-edge; gate-file SHA256 is
  `769b850c2b3a03d02c6401ec2b05e70ea3cc8305ebc22db39bbfa93728e08ee7`.
  The first pinned LLVM objdump could not decode these vector opcodes and its
  failed gates are retained in the same directory rather than discarded.
- The exact-simulator smoke is retained at
  `/home/wxt/work-online-merge-stage6a-smoke-20260715T190019Z`, UTC window
  `2026-07-15T19:00:19Z` to `2026-07-15T19:15:20Z`.  It used simulator SHA256
  `73b9138e49f7d8b095250a0867d03063b9afb494bbf7e9ca300faf70a70e4cc8`
  from source commit `9d812be187fcf07359e80537031850c313ad5954`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  Verilator 5.034, and the exact ELF above.  The traced simulator reached the
  900-second host limit and remains return code 124/`timeout`, not a passing
  full-schedule result.  Before timeout it emitted one valid metadata record,
  nine parseable records (all correctness/status checks passing), and four
  complete `OM_FSM` records.  The four C0-SMU samples used exactly 13 sparse
  status reads each, or about 656 busy cycles per read.  Median C0 SMU and
  register cycles were 10,048 and 10,059, giving calibration ratio 1.001095.
  Completeness gates correctly reject the missing C1/C2/C3 schedule and PASS
  banner; validation JSON SHA256 is
  `eb21ff932226fa0662c593de7d1606ac3800f5133af8a61358425bbfa1106d6a`.
  The validator's first partial-evidence path exposed a `None` handling bug;
  that tool-error traceback is retained with SHA256
  `b5c67b23e2edc40aa52e213170ec683a5ec81bcaeb376f7c2597111f4c229569`
  before the validator was fixed and rerun.
- Smoke stdout/stderr SHA256 values are
  `411e5c0c483c40e72e57f65be4a404d496e843a9461fd8dcca4a069e030c1c87`
  and `38c65c68c47a77a22db4626675de1b0c7750accb811d9a0c9eb835fba8135545`.
  The large 539 MiB/248 KiB hart traces remain only under the external run
  directory; hart-0/hart-1 SHA256 values are
  `5e3292a2df2f78a8e6468b4b084217eb5a558b9b767ad2472f89377247348a6f`
  and `53fbbf28aa5a63867deb47aa63c566f80c212d824cacf19bff4b340684900731`.
- Source identities for this dirty pre-checkpoint smoke are parent commit
  `50903a5458c9812280621249673a3d350c6a8bcb`; `concurrency.c`,
  `concurrency_workloads.S`, and `concurrency_workloads.h` SHA256 values are
  `b4dba9dec2f1223c659fab299a13a9c7a313cf903f09abe05374b4e6fc83bcd7`,
  `e7e42f9cd2c1aa8efcbf3cb1c6a1ed314fdbcb61d516aba217894bce93462389`,
  and `e9cf9ae266e79a649d761f901ff6734042cad023959bf01e0217e148b3d6940c`.
- The first checkpoint-validation harness at
  `/home/wxt/work-online-merge-stage6a-checkpoint-validation-20260715T191835Z`
  had an incorrect static string assertion and lacked fail-fast propagation, so
  its misleading zero exit is retained as `tool_error`; validation-log SHA256 is
  `9863beae029700b7521f328344f155a3086aaafe04ad63cd6604b0684afaddda`.
  The corrected fail-fast rerun at
  `/home/wxt/work-online-merge-stage6a-checkpoint-validation-r2-20260715T191957Z`
  passed with return code zero; validation-log and context SHA256 values are
  `8363d352a654cb94ba838b5823a0ef50a6ec32e567ea52e9ad248c6603a9eb6b`
  and `4c4409678b55c88a0b7884645dc888040309273af218da5844586b6de5ba7493`.
- Remaining Stage 6 work: add the external-work-dir host runner, synthetic
  timeout/tool-error/capacity/unsupported retention tests, exact `OM_FSM`
  pairing, CSV/JSON analysis of `T_smu`, `T_core`, `T_concurrent`, unclamped
  overlap efficiency, both slowdowns, congestion, throughput, and best/worst/
  median phase, followed by a clean committed formal run.  The retained timeout
  shows that always-on per-instruction traces are not a practical formal-run
  configuration; any low-perturbation trace gate used next must be explicit and
  independently validated.  No physical PPA, power, energy, Fmax, or
  critical-path claim is made.

### Stage 6b checkpoint: concurrency host runner and retained terminal states

- Objective: make the Stage 6a target schedule reproducibly buildable,
  executable, disassembly-gated, validated, and preservable from one host
  command.  Stage 6 remains `in_progress`; metric analysis and a clean formal
  run are still pending.
- `util/online_softmax_merge/run_concurrency.py` defaults to the representative
  `(N,D,R)=(16,64,3)` point and requires a fresh external
  `work-online-merge-*` result directory.  Configure, build, disassembly, and
  simulator commands have separate timeouts.  Repeated CMake definitions,
  exact ELF copying/hashing, CFG and simulator identities, source Git context,
  tool versions, command windows, generated trace identities, and measurement
  semantics are retained in JSON manifests.
- The runner requires exactly 148 C0/C1/C2/C3 target records, 76 `OM_FSM`
  invocations, one metadata record, every `(scenario,phase,repeat)` key, all 16
  phases, an exact target/FSM invocation bijection, and the PASS banner.  It
  validates stream length/tail, allocation metadata, bank-phase arithmetic,
  correctness counts, sparse post-work polling, zero reads inside the core
  window, FSM state sums, and the `[0.8,1.2]` C0 register/SMU calibration gate.
  GNU/LLVM-aware disassembly gates prove the register loop has no memory or
  stack access and prove the stream loop has `vsetvli`, `vle32.v`, `vse32.v`,
  and a local back-edge.
- Every parsed partial target/FSM record is retained on timeout or error.
  Malformed numeric/JSON fields become structured validation failures rather
  than escaping as tracebacks.  Target-emitted whole-run `capacity_skip` and
  `unsupported` records use a dedicated terminal validator instead of
  accumulating false full-schedule failures.  Early setup/build/disassembly
  terminal states now also create matching `failures.json` entries, and an
  objdump wall-clock timeout remains `timeout` rather than being relabeled as
  a generic tool error.
- Structured outputs are `concurrency_records.{csv,json}`,
  `concurrency_metadata.json`, `fsm_records.{csv,json}`, `failures.json`,
  `commands.json`, `artifact_manifest.json`, and `run_manifest.json`.
  `util/online_softmax_merge/README.md` documents the controlled invocation,
  gates, outputs, and the non-physical scope of these runtime proxies.
- End-to-end synthetic CLI evidence is retained at
  `/home/wxt/work-online-merge-stage6b-cli-20260715T194941Z`.  The harness ran
  the real runner entry point through capacity, unsupported, missing-simulator
  tool error, and one-second simulator timeout paths.  Expected/observed exit
  codes were `0/0`, `0/0`, `1/1`, and `1/1`; each output manifest retained only
  the corresponding explicit status.  The timeout command window was
  `2026-07-15T19:49:41Z` to `2026-07-15T19:49:42Z`, retained malformed output,
  and produced seven validation failures plus a terminal timeout record.  This
  uses clearly labeled fake objdump/simulator scripts solely to validate host
  status plumbing; it is not performance evidence.
- The synthetic run used source parent
  `9e4c35d2623a83701b1547d3ab4712cbdf5c8779` with `git_dirty=true`, CFG SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  Python 3.12.3, CMake 3.28.3, Verilator 5.034, and the configured Clang 14.0.6.
  Harness, validation-summary, and complete checksum-index SHA256 values are
  `2b3eaa23a7ad9d0ac3153ccefb63da2605c3f680b53eaaf544cecfdc912ff8fe`,
  `6f0100f7002e4ea7b1b340b9f0ba409ba855ea5f382c80aaf68d3d6bc432b535`,
  and `8409de42999ecd64bf44a1b692eb51a1de7accb68ba2d81b3e8b76bff96d62cb`.
- The first checkpoint harness at
  `/home/wxt/work-online-merge-stage6b-validation-20260715T195258Z` is retained
  as `tool_error`: all 59 tests and Python compilation passed, but its new
  whole-progress-file 100-column gate rediscovered 13 pre-existing long lines
  and stopped before `git diff --check`.  Validation-log SHA256 is
  `20c240507a6e38f5713a2c5c1c44fda584ffb03eee2dcd254b754fad17a4e0d7`.
- Corrected checkpoint validation at
  `/home/wxt/work-online-merge-stage6b-validation-r2-20260715T195434Z`
  reran all 59 utility unit tests, compiled all four runner/analyzer Python
  modules, checked changed-file line lengths and `git diff --check`, and
  inspected status/diff.  Validation-log and context SHA256 values are
  `d2007e63553a6e3d26edae67d6ca7a7da19b4b3a1a3a0d0f4d6816dee6fb31c1` and
  `846ea7c8fcd66f0fb0fbbf3d871c31939f1c54fd4f2b0ef954145010f0a0e11c`.
- Next: implement deterministic concurrency analysis with exact per-invocation
  pairing, warm-up exclusion, raw unclamped overlap/slowdown metrics, C3 phase
  best/worst/median summaries, and full retention of negative/non-pass data.
  The prior exact traced smoke remains a reproducible 900-second timeout; no
  physical area, timing, power, energy, or critical-path claim is made.

### Stage 6c checkpoint: deterministic concurrency metrics analyzer

- Objective: complete the deterministic C0/C1/C2/C3 metric and bank-phase
  analysis layer while preserving the Stage 6 formal-run timeout as a blocker.
  The analyzer is complete, but Stage 6 measured performance evidence remains
  `in_progress` until a clean, reproducible simulator run finishes.
- `util/online_softmax_merge/analyze_concurrency.py`, source SHA256
  `9b55037b886cb0c0acd278f9571f171947034ae3dd9fdf331da6b8dc23921ffe`,
  consumes one or more complete Stage 6b roots in canonical order.  It rejects
  duplicate roots and strictly validates passing manifests, provenance,
  command success, metadata, schedule completeness, correctness, FSM sums,
  and the exact target/FSM invocation bijection.  Terminal non-pass roots,
  complete records, failures, commands, metadata, and artifact identities are
  retained rather than discarded.
- Baselines are selected without cross-repeat or cross-phase substitution:
  C1 uses same-repeat `C0_SMU` and `C0_REG`; C2 uses same-repeat `C0_SMU` and
  `C0_STREAM`; C3 uses same-repeat `C0_SMU` and same-phase/same-repeat
  `C3_CORE`.  For each observation it reports `T_smu`, `T_core`,
  `T_concurrent`, `T_smu_concurrent`, and `T_core_concurrent`, followed by
  `T_smu + T_core - T_concurrent`, raw overlap efficiency divided by
  `min(T_smu,T_core)`, both component slowdowns, TCDM congestion, core
  bytes/cycle, concurrent SMU elements/cycle, and standalone SMU
  elements/cycle.
- Every ratio has an exact numerator/denominator and a decimal rendering.
  Summary medians are computed directly from exact rational values rather than
  float round trips.  Negative overlap is retained without clamping.  Warm-up
  rows remain in the observation table but do not contribute to measured
  medians.  Component windows larger than their total windows are rejected.
- C3 summaries retain all 16 relative bank phases.  Best and worst minimize
  and maximize measured median `T_concurrent`.  The representative median is
  the observed phase closest to the median of the 16 phase medians; ties use
  lower `T_concurrent` and then the lower phase.  Output files are
  `analysis.json`, `concurrency_observations.csv`,
  `concurrency_summary.csv`, `bank_phase_summary.csv`,
  `retained_status_records.csv`, and `artifact_manifest.json`.
- Eleven focused analyzer tests bring the complete utility suite to 70 tests.
  They cover exact known metrics and medians, C3 baseline selection, negative
  overlap, warm-up exclusion, all phases and deterministic phase selection,
  repeat-count generalization, malformed/impossible records, missing or
  duplicate pairings, terminal-state retention, multiple-root ordering,
  byte-deterministic outputs, provenance failures, and controlled external
  output directories.  All 70 tests pass, and all five utility modules plus
  the new analyzer test compile with Python 3.12.3.
- Final synthetic CLI validation is retained at
  `/home/wxt/work-online-merge-stage6c-synthetic-r2-20260715T202622Z`.
  A fresh temporary Git repository at clean commit
  `e0cdee23b6a4cc088c4225ce5e4320d1c8214ee3` generated the full synthetic
  148-target/76-FSM schedule, ran the real analyzer twice, and compared all six
  outputs byte-for-byte.  It contains 72 observations, 54 measured rows, all
  16 phase summaries, and 67 deliberately negative-overlap observations.
  Synthetic `performance_evidence` is explicitly `false`.
- Final output SHA256 values are: `analysis.json`
  `fd40aa797b909ba1672be609540dd05f0823d5c771ff27a8656d94df7ce2da33`,
  `concurrency_observations.csv`
  `001692b67a1459ebf1dbfaa74d1e1822744e7d290610712fb717d3a652a46768`,
  `concurrency_summary.csv`
  `a4ede791c628322bb17319889a7f3fe8ee85bd4636e86c33e3be7ed0a0aaf542`,
  `bank_phase_summary.csv`
  `0af0cbff183262b473f6a4222074906becd333be2cfa1a48ec9c5b990833d51b`,
  `retained_status_records.csv`
  `8ff7fede6354f2a0ee3a8c9209e47d9d9a8c775bb648fa19dbac0594a9585e97`,
  and `artifact_manifest.json`
  `75a1cf1b1f5c70e42b4c2d8a05d8a30489918b3c5cbc6e47174255142d90233e`.
- An independent standard-library verifier imports no repository analyzer code.
  It reconstructs the full schedule and target/FSM pairing, all component
  windows and exact ratios, measured medians, every phase summary and selected
  phase, warm-up and negative-overlap handling, CSV values, input/output/tool
  hashes, and duplicate-run byte identity.  All 11 independent gates pass.
  Verifier-source SHA256 is
  `37a60b47bd483c89ba1e44108fcbf5b1c25fed85a2f0dbe3cf3cc5facbaf7cd4`;
  verification-result SHA256 is
  `db7dc53305c97e6b1a45a622a30e1b1e07918681c6a68eff4c4406de5dabe164`;
  byte-comparison-log SHA256 is
  `41e8ef5909ac60d57befecade4f00a84dd31df57397b1712ce516d5cfd22a1ce`;
  and the verified checksum-index SHA256 is
  `ad0511c4a5377c29f0741dcda121ec183e7345490645574ca37166321b088d51`.
- The earlier successful synthetic evidence at
  `/home/wxt/work-online-merge-stage6c-synthetic-20260715T202056Z` is retained
  but superseded because it predates exact median numerator/denominator
  columns in the summary CSV files.  Its `analysis.json` and
  `artifact_manifest.json` SHA256 values are
  `738d9ae05010d0dcbb2c405716c174f11b01802dc37fa6d350e92493191213f3`
  and `a1f4bf30873e4385a0168f0c680f845fcb18b7de9e96a9e278f8813fe10fa9d5`.
- The first checkpoint-validation attempt at
  `/home/wxt/work-online-merge-stage6c-checkpoint-validation-20260715T203049Z`
  is retained as `tool_error`: all 70 tests, compilation, line-length, and
  diff checks completed, but the embedded result reporter had a parenthesis
  syntax error.  Failure-record and stderr SHA256 values are
  `7c8c7739ebf1d7a96fd0fab2f254d00688e861637b7e95787b4447990ce182a2`
  and `3f3b12d4a412a88dd185e6015bacee4a404b377dbf888865cf2cbb134d6de39d`.
- The second attempt at
  `/home/wxt/work-online-merge-stage6c-checkpoint-validation-r2-20260715T203223Z`
  passed every validation gate, but its outer checksum command used the wrong
  working directory and left an empty index.  It is retained as `tool_error`;
  failure-record and checksum-failure-note SHA256 values are
  `33babc2f25f5ea757b30ea2f22407e1e95755ee2b6acf5a99441a8d5861b8724`
  and `ee700f8e4afa876d4160175856a75755c213df6c52b330a89a51a1c3e5b50479`.
- Corrected checkpoint validation at
  `/home/wxt/work-online-merge-stage6c-checkpoint-validation-r3-20260715T203303Z`
  reran all 70 tests, compiled all five utility modules and the analyzer test,
  checked changed-file line lengths and `git diff --check`, retained the full
  diff/status context, and verified its checksum index.  Result, test-log,
  diff-context, checksum-index, and validator SHA256 values are
  `b1351e45c1c3860f9be72c9e657ece6bce301e6452ed9797a726ba98188c6346`,
  `1b2c62e36dc2ce505d8a135b0991e971830fbbcf2a5d8f76be55b3c1fb38d183`,
  `09615e4ac2171a8511506440dbc0804ae7a1c8b21a7ef106ffee7289c9d5ad3f`,
  `9e2872c6612684b49c693b35738f4015697cc55dfb405170365269e3ed7cfbeb`,
  and `e9f8131e9a5f1b64c319ff3b4fc15245ccd5a62ae8b77b6da500dea354154759`.
- The formal traced run remains the reproducible Stage 6a blocker at
  `/home/wxt/work-online-merge-stage6a-smoke-20260715T190019Z`: 900 seconds at
  `(N,D,R)=(16,64,3)` produced only 9 target and 4 FSM records while the
  always-on per-instruction DASM trace grew to 539 MiB.  No incomplete record
  is promoted to a pass.  A lower-trace simulator must be committed, explicit,
  hashed, reproducible, and compared with traced behavior; trace gating remains
  a P1 item after the remaining P0 proxy stages.
- These analyzer and synthetic-validation results are host-framework evidence,
  not measured concurrency performance.  They make no physical area, Fmax,
  frequency, power, energy, critical-path, or physical-efficiency claim.  Next
  P0 work is the engineering-grade Yosys Slang generic-resource proxy, while
  the formal Stage 6 run remains explicitly blocked by traced-simulator cost.

### Stage 6d checkpoint: low-perturbation simulator profile

- Objective: remove the reproducible Stage 6a per-instruction DASM bottleneck
  without removing the simulation-only `OM_FSM` busy-cycle observer or
  weakening the formal runner gates.  Stage 6 remains `in_progress` until the
  clean formal schedule and deterministic analysis complete.
- `SPATZ_DASM_TRACE=0` adds the compile-time `SPATZ_DISABLE_DASM` definition.
  It omits only the `spatz_cc` per-instruction string formatting and `.dasm`
  writer.  The online-merge observer remains present and emits one machine-
  readable `OM_SIM_CONFIG` record declaring the low-perturbation profile,
  `dasm_trace_enabled=false`, and `fsm_observer_enabled=true`.
- The concurrency runner now rejects missing, duplicated, malformed, default,
  DASM-enabled, or FSM-disabled simulator configuration records.  The exact
  accepted record is retained in `run_manifest.json`; any gate failure becomes
  a structured `tool_error` while preserving all partial target/FSM records.
- Dirty integration build is retained at
  `/home/wxt/work-online-merge-stage6d-low-trace-build-dirty-20260716T032333Z`.
  The exact external simulator is 18 MiB with SHA256
  `70c021ced118617eb9fe25da53e052d2f6327296af81a44d5e064a355551f419`;
  build-log SHA256 is
  `fbb5982f4838187fb2b7a1865a7b93b432abc0e61d9fd50f5c9833abcd937e64`.
  The generated Verilator file list contains `SPATZ_DISABLE_DASM`, the linked
  binary contains `OM_SIM_CONFIG` and `OM_FSM`, and an independent binary
  string gate confirms `trace_hart_%05x.dasm` is absent.
- This integration build used source parent
  `1a0ebc9b2c330879e2edd4b091c53590ccc069cc` with `git_dirty=true`, fixed CFG
  SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  Bender 0.29.1, Verilator 5.034, and Python 3.12.3.  The modified `spatz_cc`,
  online-merge observer, Makefile, and runner source SHA256 values are
  `cb9d152ace32f5210ff147b526b8f30b18f8758d8ea201fa0a03a78405b5c3a7`,
  `fe52fe2dbffcb3d800314972c3d4da863a6ab7633cd3675ebacb530ba7ef10d3`,
  `1a1468dbe6c628e9b0606c39b5dc5850c12ae5a6a6d0ae092ad8114a0b30105a`,
  and
  `277399fa1f77a5213f984c32eeda3eb29dadb0d55930bce25ebe4a31d71323d4`.
- Validation: all 93 utility tests pass, all utility Python modules compile,
  the external Verilator elaboration/link returns zero, changed-file style and
  `git diff --check` pass.  The Makefile-triggered `test/bootrom.elf` rebuild
  was known to originate in this validation and was restored exactly to HEAD;
  no unrelated path was changed.
- This dirty build proves implementation only and is not performance evidence.
  Next: create the atomic commit, rebuild the same profile from that clean
  commit, run all 148 target/76 FSM records, and execute the deterministic
  analyzer plus an independent reconstruction before Stage 6 completion.

### Stage 6e checkpoint: bounded clean timeout and runtime tuning gate

- The low-perturbation implementation was committed as `928ec7e`.  Its clean
  simulator build is retained at
  `/home/wxt/work-online-merge-stage6-formal-simulator-clean-20260716T033109Z`.
  The exact 17,998,528-byte binary SHA256 is
  `70c021ced118617eb9fe25da53e052d2f6327296af81a44d5e064a355551f419`;
  it contains the required `OM_SIM_CONFIG`/`OM_FSM` strings and excludes the
  DASM filename string.
- The clean formal attempt is retained at
  `/home/wxt/work-online-merge-stage6-formal-capture-clean-20260716T033500Z`.
  It ran under the runner's separate-process-group 3,600-second timeout and
  was terminated without leaving a simulator process.  It is preserved as a
  timeout, not promoted to passing evidence.
- At timeout the run had produced 29 of 148 scheduled target records and 16 of
  76 FSM records.  Every observed target workload and FSM invocation passed,
  but only phase zero and the phase-eight standalone-core warm-up had been
  reached.  The PASS banner was absent.  This proves the issue is insufficient
  whole-system Verilator throughput, not a completed target waiting for host
  exit; extrapolating the incomplete record rate would require several hours.
- The retained output also exposed an independent runner bug: non-stream C0/C1
  target records intentionally encode `phase_bytes=UINT32_MAX`, while the host
  validator and analyzer expected zero.  Expected schedule keys, raw-record
  validation, baseline lookup, and synthetic tests now use `UINT32_MAX` for
  non-stream records and zero only for C0-stream/C2.
- `util/Makefrag` now exposes opt-in `VLT_THREADS` and
  `VLT_MODEL_CFLAGS` knobs.  Both preserve the established build by default
  (`1` and empty).  A tuned binary such as four threads plus `-O3` must be
  explicitly recorded and compared with the single-thread profile before
  formal use; no speedup is assumed in advance.
- Validation: all 98 utility tests pass after the phase-sentinel repair.  Next:
  commit the repair/tuning gate, build a clean tuned simulator, run a short
  bounded throughput comparison, and choose between the tuned single capture
  and a versioned phase-sharded flow.  No additional hour-long run starts
  before that diagnostic gate passes.


### Stage 7a checkpoint: versioned Slang wrapper and capture runner

- Objective: replace the external-only Yosys prototype with a repository-owned,
  fixed-type Slang top, versioned pre/post-techmap pass sequence, controlled
  external runner, structured terminal records, timeouts, and complete input and
  raw-artifact provenance.  This checkpoint implements capture only; the
  deterministic resource parser and clean formal evidence are Stage 7b.
- The synthesis-only wrapper fixes the default cluster integration at 17 TCDM
  byte-address bits for 128 KiB, 64 data bits, eight strobe bits, and the exact
  four-bit packed user payload for two cores plus four outstanding Spatz loads.
  A minimal `reqrsp_pkg` preserves the exact four-bit AMO encoding without
  importing the unrelated AXI package graph.  The wrapper exposes independent
  `exp`, `reciprocal`, `vector`, and `full` tops.  The vector top repeats the
  exact `compute_vector_merge` expression, but all independent scope totals are
  explicitly non-additive because Yosys may optimize them differently.
- `generic_resource.ys` performs `proc/opt/memory_collect`, records `stat -json`
  and `stat -width`, and writes the raw pre-techmap netlist before
  `flatten/techmap/opt/clean`, then records equivalent post-techmap artifacts.
  It supplies no liberty, PDK, technology mapping, timing constraint, or power
  model.  Wrapper and pass-script SHA256 values in the final validation capture
  are `c4c1604ace7cbdac378171530668ee8910dd77249719903ec23baebfdc2597d7`
  and `ca81bc659aff8e5c082a0699da2853fea605bf89cf27b206597ac6751a692e60`.
- `run_resource_proxy.py` records `yosys -V`, probes `read_slang`, hashes the
  runner, wrapper, script, all four RTL inputs, and the fixed CFG reference,
  preserves every scope's log and raw pre/post files outside Git, validates
  structured `stat` output, and incrementally writes run/input/scope/failure/
  command/artifact manifests.  A dirty run is retained but cannot set
  `resource_proxy_evidence=true`; selecting fewer than all acceptance-required
  `exp`, `reciprocal`, and `full` scopes also cannot produce evidence.  Timeout,
  nonzero-tool, missing-output, duplicate-scope, unsafe-path, and existing-root
  cases have explicit tests.  The shared command helper now closes its timeout
  pipe after preserving all remaining output, eliminating the observed resource
  leak without changing target-record semantics.
- The first integrated runner attempt is retained at
  `/home/wxt/work-online-merge-stage7a-runner-smoke-20260715T205832Z` as
  `tool_error`: Yosys treats double quotes passed inside a `read_slang` command
  as literal filename bytes, so all four scopes failed before producing raw
  outputs.  The runner was corrected to accept only unambiguous Yosys path
  tokens and pass them without embedded quotes.  Failure-manifest, command-log,
  and first-scope-log SHA256 values are
  `121b38d37f8e56fdc112df91812ae761368fed5638656613db0393fc196bdc4e`,
  `1d6ca6850b9b566918789ce2dfcac30d31db5952a505af0c6f4d581de50f5c21`,
  and `5206e9fd06889360b131d5cf37aad85d56eb8a8cd4797122c952d0c649dc02d1`.
  No failed scope was promoted to a pass.
- Corrected dirty smoke at
  `/home/wxt/work-online-merge-stage7a-runner-smoke-r2-20260715T205909Z`
  synthesized all four scopes in about 28 seconds.  It is validation-only
  because source commit `d07d516da56f639f24ff8974cee4a1a33c9af007` was dirty.
  Its run-manifest, scope-results, and artifact-manifest SHA256 values are
  `af92eb2e771dd2c2a929890f8fc572219e75a23f214d257e6b156226e3829d3a`,
  `e2eb7dd8fcbdb03ffe3b57d86238b9118bbaa585a794b8f555ab5b3faf9b3304`,
  and `a4c591bf6be54b547254f138fd637d5db08bc5a81156a8068a0a44401ba9cc04`.
- Final checkpoint validation at
  `/home/wxt/work-online-merge-stage7a-checkpoint-validation-20260715T210432Z`
  ran all 80 utility tests, compiled the changed Python modules, checked Python,
  Markdown, Yosys-script, and SystemVerilog line limits, ran real
  `Yosys 0.66+4 (git sha1 8125af88d, clang++ 18.1.8 -fPIC -O3)` synthesis for
  all four scopes, independently rehashed every input and raw artifact without
  importing runner code, verified top/stat/command/pass-order/claim gates, and
  passed `git diff --check` plus a self-verified checksum index.  Validation,
  independent-verifier, checksum-index, unit-test-log, and capture-artifact-
  manifest SHA256 values are
  `813500d06329f7c4058848c778feba1e9c7379f610ea9a565500d84c8690fc2f`,
  `644057d82e1442c31a94cb9bfafffda117bf06d93c14bfb350d7601eae76c7d8`,
  `bf2969677e217319fd684fa30591eba27e35b2d860fff6954de6ead5a651a980`,
  `33228e9bc6b8ec9814d3225fe8c0e23f27c6fe38128d921978f410eae56f72f1`,
  and `76d0a92634f73d98715108381f3cbffabf9543d8923bdd59ae1a12900392e162`.
- The validation-only top totals were pre/post 38/4,235 cells for `exp`,
  24/4,629 for `reciprocal`, 156/33,070 for `vector`, and 938/94,713 for
  `full`.  These numbers are retained only as version-specific generic-logic
  smoke proxies.  The artifact manifest records every raw netlist/stat path,
  size, SHA256, source commit, CFG reference SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  tool version, and synthesis scope; the largest full post-techmap JSON is
  61,340,728 bytes with SHA256
  `1bd7558b08624d0971cefd245c3178a2bedb37e599e0af3a9c883d13ec01ef52`.
  None of these raw generated files is tracked by Git.
- No ASIC area, frequency/Fmax, critical path, timing closure, power, energy,
  or physical-efficiency claim is made.  P2 remains `blocked_external` on the
  PDK, liberty/LEF, PVT, clock/IO/load/floorplan/routing constraints, and
  physical synthesis/P&R/timing/power tools listed in the fixed context.  Next
  work is Stage 7b's deterministic per-resource/per-source parser, clean
  committed `exp`/`reciprocal`/`full` capture, independent verification, and
  explicit structured `blocked_external` PPA record.

### Stage 7b checkpoint: deterministic parser and clean capture

- Objective: add the deterministic resource parser required by specification
  section 6 and obtain a clean committed capture before formal analysis.
- Clean capture is retained at
  `/home/wxt/work-online-merge-stage7b-resource-clean-20260716T014550Z`, UTC
  window `2026-07-16T01:45:50Z..2026-07-16T01:46:22Z`, commit
  `679331001c59ac7466bbc0039ffe4ce1a87ff3c0`, `git_dirty=false`, CFG reference
  SHA256
  `120fa0c30199e54e6e9b5c60d8da40913eae8526640992cc5d4f130bef159775`,
  and Yosys `0.66+4` with the Slang plugin.  All four independent scopes pass,
  `failures.json` is empty, and `resource_proxy_evidence=true`.
- Clean capture pre/post cell totals are exp `38/4235`, reciprocal `24/4629`,
  vector `156/33070`, and full `938/94713`.  The full pre-techmap netlist has
  ten `$mul` cells and 620 register bits; no memory/ROM/LUT-like cell is
  inferred.  These are version-specific generic logic proxies only.
- `analyze_resource_proxy.py` validates capture, input, and artifact hashes,
  Yosys stat sums, required scopes, and current source identities.  It emits
  complete pre/post cell types, major operator groups, multiplier width rows,
  register bits, memory-like inference, module rows, deterministic CSV/JSON,
  and an artifact manifest.
- Independent scopes are explicitly non-additive.  Because no separate
  scalar/FSM/control synthesis top exists, that decomposition is retained as
  `unsupported`; the analyzer does not manufacture it by subtracting
  independently optimized scopes.
- Physical PPA remains an explicit `blocked_external` record.  Missing inputs
  are the target PDK, liberty/LEF, defined PVT and clock/IO/load constraints,
  floorplan/routing constraints, and physical synthesis/P&R/timing/power
  tools.  No area, Fmax, critical-path, mW, pJ, or physical-efficiency value is
  generated.
- Validation before this checkpoint: all 85 utility tests pass, all utility
  modules and tests compile under Python 3.12.3, changed Python/Markdown lines
  meet repository limits, and `git diff --check` passes.  A direct parse of the
  clean capture passes every substantive gate; only
  `analysis_git_clean=false` while this atomic implementation is uncommitted.
- Git synchronization note: `git fetch origin` and `git pull --rebase` showed
  the branch up to date on 2026-07-16, but the following push retry failed at
  the HTTPS TLS handshake.  The local checkpoint is retained; no force-push,
  merge commit, reset, stash, or clean was used.  Synchronization must be
  retried after this atomic commit.
- Remaining Stage 7 gate: commit this analyzer from a clean worktree, run it on
  the retained clean capture, independently rehash its outputs, and record the
  formal analysis identity before marking Stage 7 complete.

### Stage 7c checkpoint: formal generic-resource proxy closure

- Objective: run the committed analyzer from a clean checkout, independently
  validate every output and input artifact, and close the current-environment
  acceptance boundary for specification section 6.
- Analyzer implementation commit
  `b8be96a3114db37a7552ecdbb7d651fa72cbcc0e` was fetched, checked with
  `git pull --rebase`, and pushed successfully before measurement.  The formal
  analysis is retained at
  `/home/wxt/work-online-merge-stage7b-resource-analysis-clean-20260716T015813Z`.
- Every acceptance gate passes: clean capture and analysis provenance, required
  exp/reciprocal/full scopes, all requested scopes, empty capture failures,
  passing commands, current source-input hashes, all 30 captured artifact
  hashes, and indexed pre/post stat and netlist files.
- Formal generic-resource table:

  | Scope | Pre cells | Post generic cells | `$mul` | Register bits | Memory-like cells |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | exp | 38 | 4235 | 1 | 0 | 0 |
  | reciprocal | 24 | 4629 | 1 | 0 | 0 |
  | vector | 156 | 33070 | 2 | 0 | 0 |
  | full | 938 | 94713 | 10 | 620 | 0 |

  The independent scopes remain non-additive.  Multiplier widths and complete
  pre/post cell-type rows are retained in the external structured outputs.
- Formal output SHA256 values are:
  - `analysis.json`:
    `f0176d2a59cd517f82eba894a38f0d89c19e76b4c10abeb7b953ef6c423e81aa`;
  - `resource_summary.csv`:
    `e54bb260b16c119681b2fe73e4ac93a6b6eb95302734d469e2d3aa985168da08`;
  - `multiplier_widths.csv`:
    `7203eee4a0c29217bcdafc40dfa5223bf368a7404d5e813d1f93e594939beea4`;
  - `cell_types.csv`:
    `72528b94e52dd3559e96315be5cb97a13e8a928834c12f4998c063261fc53983`;
  - `module_resources.csv`:
    `cbaefdbbcaf00a5327d800253bb78d59357bf36ba8b3cb65a4df47b9ed330399`;
  - `artifact_manifest.json`:
    `a78514d28551d5395ceede5239eed2458b1497dd6798e8e917c6c7ebac9f4d4d`.
- An independent standard-library verifier imported no analyzer code.  It
  rehashed all 30 capture artifacts and all five manifest-indexed analysis
  outputs, checked all gates and proxy/PPA booleans, reproduced the four scope
  totals, confirmed 14 multiplier rows including ten full-SMU rows, and
  confirmed the structured `blocked_external` physical-PPA record.
- Validation command:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s`
  ` util/online_softmax_merge/tests -v` passed all 85 tests before the formal
  run; the analyzer command and independent verifier both returned zero, and
  `git diff --check` passed.
- Completion boundary: Stage 7 delivers only the specified Yosys/Slang generic
  resource and logic-complexity proxies.  It reports no ASIC area, Fmax,
  critical path, physical power, energy, or efficiency.  P2 remains
  `blocked_external` on the exact technology and signoff inputs in the fixed
  context.

### Stage 8a checkpoint: probe-gated VCD implementation and smoke

- Objective: make representative RTL VCD capture practical without tracing
  benchmark initialization, correctness checking, printing, B1, warm-ups, or
  all measured repeats.
- The Verilator top now exposes the existing `cluster_probe`, and the C++
  harness accepts `SNITCH_TRACE_GATE=1`.  It dumps while the probe is high and
  once on the falling edge, and emits an indexed start/end record for every
  window.  With gating disabled, existing whole-run trace behavior is
  unchanged.
- `ONLINE_MERGE_TRACE_PROXY=1` is an explicit CMake definition.  It marks only
  B2-R repeat zero and B3 repeat zero; the benchmark still executes and checks
  the required three measured repeats of B1/B2-R/B3.  This supplies identical
  input/case and marker semantics for the RVV and SMU activity windows while
  keeping the VCD bounded.
- `VLT_BIN` allows the trace-capable simulator executable to remain in an
  external `work-online-merge-*` directory instead of overwriting the existing
  `bin` symlink.  All Verilated objects used by this smoke likewise remained
  under an external `VLT_BUILDDIR`.
- Dirty implementation smoke used `(N,D,seed,repeats)=(1,1,1,3)`.  The target
  ELF SHA256 is
  `3e28aba96c07d7243ad21ef45309daea41732ba14776059becf31f886d1f0a20`;
  the trace-capable simulator SHA256 is
  `6773b6cffb3ee261450aa44648eecb3d6420dd0d601c1b2c23ae6ae78127f51f`.
  Its generated header reports `traceCapable=true` and a one-bit
  `cluster_probe_o` output.
- Smoke evidence is retained at
  `/home/wxt/work-online-merge-stage8-trace-smoke-dirty-20260716T023543Z`.
  Simulator return code is zero, all nine target records pass, all four FSM
  observations terminate in `DONE`, and the target prints its PASS banner.
  The exact two trace windows are:

  | Index | Implementation | Start time | End time | Marker span |
  | ---: | --- | ---: | ---: | ---: |
  | 0 | B2-R repeat 0 | 46152 | 50052 | 3900 half cycles |
  | 1 | B3 repeat 0 | 71954 | 74292 | 2338 half cycles |

  Target cycle records for those repeats are 1887 and 1115 respectively.  The
  marker span includes observable boundary instructions around the target's
  internal `mcycle` interval and is therefore retained separately.
- The gated VCD is 84,031,468 bytes with SHA256
  `674af544bdfb282a0356fcbe3efc5a31f382ec96ebbb4a96cac84cad04adeeff`.
  It and the 144 MiB hart trace remain outside Git.  Simulator stdout/stderr
  SHA256 values are
  `06015789af90803de1c5b836c9162ce3ccb7dbe629614362604a1f160d3e3f1c`
  and
  `a8a5319c8e4a69ab22b5ff63af55ab8a7f8f2ad88f9c0c5d842565ba7b65eaa9`.
- Preserved setup failures: two Bender HTTPS fetches failed with truncated TLS
  packets and a missing locked iDMA object; the exact locked object was then
  fetched from the read-only local `/home/wxt/spatz/.bender` cache and Bender
  completed with `--local`.  A subsequent build attempt failed because system
  Python lacked `hjson`; the existing project virtual environment reports
  hjson 3.1.0 and completed the build.  No failed attempt is promoted to
  measurement evidence.
- The first Make invocation rebuilt tracked `test/bootrom.elf` because the
  Makefile timestamp changed.  The worktree was clean at task start and this
  binary change was created by that invocation, so only that known generated
  change was restored to HEAD before continuing.  The validated simulator and
  all later artifacts remained external; no unrelated user change was touched.
- Validation: all 90 utility tests pass, all utility Python files compile,
  target CMake/build passes with the actual trace definition, RVV and stack
  symbols are present, Verilator trace elaboration and link pass, the two-window
  simulator smoke passes, and `git diff --check` passes.
- Remaining Stage 8 work: commit this atomic gate, add the capture/VCD parser,
  then run clean `(1,1)`, `(8,32)`, and `(16,64)` captures and report bit-toggle
  totals, toggle/cycle, toggle/element, and hierarchy breakdown.  These remain
  RTL activity proxies and cannot be converted to mW or pJ.

### Stage 8b checkpoint: controlled capture and streaming VCD analysis

- Objective: turn the Stage 8a implementation smoke into a bounded,
  provenance-gated capture and deterministic analysis flow before starting the
  three formal simulations.  Stage 8 remains `in_progress` until all mandatory
  clean captures and their independent verification complete.
- `run_toggle_proxy.py` defaults to `(1,1)`, `(8,32)`, and `(16,64)`, fixes
  seed one and three repeats, owns `ONLINE_MERGE_TRACE_PROXY=1`, and requires
  exactly nine passing target records plus two ordered B2-R/B3 repeat-zero
  windows per point.  It runs the trace-capable simulator without the
  unnecessary per-instruction `--trace` option, so the VCD is preserved while
  the 144 MiB DASM behavior seen in the dirty smoke is not requested.
- Configure, target build, disassembly, and simulation commands have explicit
  independent wall-clock limits.  The shared command helper accepts recorded
  environment overrides while retaining its separate-process-group `TERM`
  then `KILL` timeout handling.  Partial logs, VCD identity, terminal command
  status, and structured failures survive every timeout or tool error.
- Formal capture requires matching clean repository and simulator-source
  commits, a fresh external result root, the exact trace definition, complete
  mandatory coordinates, VCD headers, hashes for the CFG/simulator/ELFs/VCDs/
  logs, and no retained failure.  A partial or dirty capture can validate the
  implementation but cannot set `toggle_proxy_evidence=true`.
- `analyze_toggle_proxy.py` streams each external VCD and counts known `0/1`
  Hamming-distance bit changes once per unique VCD identifier.  The first
  value per signal in each gated window initializes state and is not counted;
  `x/z`-involving transitions are retained separately.  Identifier aliases
  are not double counted.
- The exhaustive hierarchy partition is SMU scalar/exp/reciprocal, SMU vector
  data path, SMU control/FSM, TCDM-facing request/response, core or RVV
  baseline, global clock/reset, and other cluster logic.  Deterministic outputs
  are `analysis.json`, `toggle_summary.csv`,
  `hierarchy_toggle_summary.csv`, `signal_toggle_summary.csv`, and a checksum
  index.
- Direct streaming validation against the retained 84,031,468-byte Stage 8a
  dirty VCD completed in 9.2 seconds under an external 120-second process
  timeout.  It parsed 81,639 unique identifiers and 1,620,684 declared bits.
  The B2-R and B3 windows produced 2,560,517 and 1,289,705 known bit toggles,
  respectively, with zero unknown transitions.  These values validate parser
  behavior only: the source was dirty, `(1,1)` was a smoke, and the result is
  not promoted to formal evidence.
- Validation: all 98 utility tests pass, every utility Python module compiles,
  changed-file 80-column checks and `git diff --check` pass.  The synthetic VCD
  tests cover exact window ordering, per-window initialization, known bit
  changes, unknown transitions, aliases, and hierarchy classification.
- Claim boundary: this is a zero-delay RTL activity proxy.  It models no
  glitches, cell-internal power, interconnect parasitics/load, clock tree,
  leakage, voltage, process, or physical power/energy.  It cannot produce mW,
  pJ, ASIC efficiency, or signoff claims.
- Remaining Stage 8 work: commit this runner/analyzer checkpoint, build or
  identify a clean trace-capable simulator at that commit, execute the three
  bounded captures, run deterministic analysis plus an independent
  reconstruction, and only then mark Stage 8 complete.

### Stage 8c checkpoint: three clean bounded captures

- A clean single-thread trace-capable, DASM-disabled simulator was built from
  `8f2de6826185015a3b7289f3d69a34de036876d2` at
  `/home/wxt/work-online-merge-stage8c-single-simulator-clean-20260716T144500Z`.
  The 51,391,760-byte binary SHA256 is
  `06185ec84ce7ba634dd1583b9c097986142916d0e813832978d3ca85057006fc`;
  its generated model declares `traceCapable=true` and `threads()=1`, contains
  `OM_SIM_CONFIG`/`OM_FSM`, and excludes the DASM filename string.
- The three mandatory points ran concurrently in independent external build
  and result roots, each with its own process-group timeout.  All configure,
  build, RVV disassembly, and simulator commands returned zero; every point
  has nine passing target records, exactly two ordered windows, and an empty
  `failures.json`.  All simulator commands ended naturally before their
  900/1,800/3,600-second bounds; no simulator process remained.
- Clean capture identities are:

  | `(N,D)` | Simulator UTC window | VCD bytes | VCD SHA256 |
  | --- | --- | ---: | --- |
  | `(1,1)` | `14:51:46`--`14:59:32` | 79,418,518 | `e22941328e8fda1b7549599f23d221b8947710edb14b18d75aff17bcbb99ce69` |
  | `(8,32)` | `14:51:46`--`15:07:17` | 282,877,039 | `c88651b4568c7a4ed8d11b3665145c400d64bea563a3b535beb15cea0a921a0a` |
  | `(16,64)` | `14:51:46`--`15:35:51` | 685,762,235 | `e6e8ee46da1451d7b5e6e44ff2a94b99f47127a2b3c7021c7be91f4235f28898` |

- Each independently bounded point root correctly records
  `toggle_proxy_evidence=false` because it is only a subset.  The analyzer now
  accepts repeated roots only when their clean union contains every mandatory
  coordinate exactly once and commit, CFG, simulator SHA256, CMake definitions,
  trace protocol, and claim boundary are identical.  Duplicate coordinates,
  failures, non-pass commands, dirty roots, and mixed simulator identities are
  rejected.
- A clean post-capture analysis commit is permitted only when the capture
  commit is its ancestor and the intervening paths are limited to the versioned
  toggle analyzer, its tests, README, and checkpoint progress.  Any RTL,
  target, runner, build, or configuration change rejects formal analysis.
- Validation: all 101 utility tests pass and all utility Python modules compile.
  Remaining Stage 8 work: commit the multi-root analyzer gate, run the three
  VCD parses, independently reconstruct totals and hashes, record the formal
  tables, and then close Stage 8.
