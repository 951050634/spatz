# 复数指令扩展阶段成果记录

本文件用于按 node 记录进展、证据和风险。每个 node 完成后必须更新本文件，
再进行对应 git commit。

## Node 0：工作树、基线与文档框架

状态：已完成

目标：

- 在隔离工作树中建立可审计工程入口。
- 同步并追踪根目录 `.codexignore`。
- 重构 `PLAN.md`，并建立后续阶段记录模板。

验收标准：

- 当前工作树为 `/home/wxt/spatz-cfma`。
- 当前分支为 `feature/cfma-instruction-extension`。
- `.codexignore` 已从 `/home/wxt/spatz/.codexignore` 复制到当前工作树。
- `PLAN.md` 已包含分阶段实施、测试标准、结果标准和 git 操作要求。
- 未引入 online softmax merge accelerator 相关源码改动。

证据：

- 2026-06-08 运行 `git worktree list --porcelain`，确认存在
  `/home/wxt/spatz-cfma`，分支为 `feature/cfma-instruction-extension`。
- 2026-06-08 运行 `git status --short --branch`，当前工作树初始状态仅显示
  `docs/complex-instruction-extension/` 未追踪。
- 2026-06-08 已将 `/home/wxt/spatz/.codexignore` 复制为
  `/home/wxt/spatz-cfma/.codexignore`。
- 2026-06-08 运行 `cmp -s /home/wxt/spatz/.codexignore
/home/wxt/spatz-cfma/.codexignore`，退出码为 0，确认两份文件一致。
- 2026-06-08 运行 `git diff --check`，退出码为 0，未发现 whitespace
  error。
- 2026-06-08 运行 `make -C hw/system/spatz_cluster help`，退出码为 0，并成功
  打印 Spatz cluster Makefile targets；命令同时提示当前工作树缺少
  `install/bender/bender`，该提示不影响 help 目标打印。

备注：

- 本 node 只更新文档和 `.codexignore`，未引入 online softmax merge
  accelerator 相关源码改动。

## Node 1：Register Layout Reference 与 Encoding 决策

状态：已完成

目标：

- 生成 `LMUL={1,2,4,8}` 的 register layout 合法表。
- 冻结 v1 legal/illegal policy。
- 决定 `vfcmacc.vv` encoding。

修改范围：

- `docs/complex-instruction-extension/register_layout.md`
- `docs/complex-instruction-extension/scripts/cfma_register_layout.py`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`
- `docs/complex-instruction-extension/README.md`

验收标准：

- [x] `LMUL=1/2/4/8` 的所有 base `v0..v31` 都有记录。
- [x] `m8` 默认策略已明确为 illegal。原因：单个 complex operand 已消耗
      32 个 vector registers，无法满足 v1 的 non-overlap destination/source
      policy。
- [x] encoding 与现有 `VFWDOTP`、`VFMACC`、`VFNMSAC` 无冲突。脚本检查
      `VFMACC_VV`、`VFNMSAC_VV`、`VFWDOTP_VV`、`VFWDOTP_VF` 均不 overlap。
- [x] 最终 bit pattern 和合法性策略已记录。

最终 encoding：

```text
VFCMACC_VV = 32'b111010???????????001?????1010111
funct6     = 111010
vm         = instr[25]
vs2        = instr[24:20]
vs1        = instr[19:15]
funct3     = 001 (OPFVV)
vd         = instr[11:7]
opcode     = 1010111 (OP-V)
```

bring-up `.insn` 格式：

```asm
.insn r 0x57, 0x1, 0x75, vd, vs1, vs2  # vm=1
```

证据：

- 2026-06-08 01:55:09 CST 运行
  `python3 docs/complex-instruction-extension/scripts/cfma_register_layout.py`，
  退出码为 0；输出覆盖 `m1/m2/m4/m8` 的 `v0..v31` 共 128 行，并报告
  `Encoding VFCMACC_VV=32'b111010???????????001?????1010111 has no checked
overlap.`。
- 2026-06-08 运行
  `python3 docs/complex-instruction-extension/scripts/cfma_register_layout.py
--write-md docs/complex-instruction-extension/register_layout.md`，退出码为 0，
  用脚本重新生成 `register_layout.md`。
- 2026-06-08 运行 `python3 --version`，输出 `Python 3.12.3`。

风险：

- Node 1 只冻结 plan 指定的 layout 和 encoding 决策，不修改 opcode source 或
  generated `riscv_instr.sv`。Node 2 必须通过 `make update_opcodes` 展开并更新
  pinned `riscv-opcodes` source 后重新生成正式 pattern。

## Node 2：Opcode 生成与 Snitch 识别

状态：已完成

目标：

- 让 `riscv_instr::VFCMACC_VV` 成为可引用的指令 pattern。
- Snitch 能在 RVV/RVF 可用时 offload 该指令。

修改范围：

- `Makefile`
- `sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch`
- `hw/ip/snitch/src/riscv_instr.sv`
- `hw/ip/snitch/src/snitch.sv`
- `sw/riscvTests/CMakeLists.txt`
- `sw/riscvTests/isa/rv64uv/vfcmacc_smoke.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] `riscv_instr.sv` 包含 `VFCMACC_VV`。
- [x] `VFCMACC_VV` 来自 tracked opcode patch，并通过 `make update_opcodes`
      应用到 pinned `sw/toolchain/riscv-opcodes/opcodes-rvv` 后重新生成，不是只手改
      generated file。
- [x] Snitch decode 将 `VFCMACC_VV` 放入 RVV/RVF vector FP offload 分支，
      未加入 integer source 或 scalar FP source 读取路径。
- [x] 禁用 RVV/RVF 时沿用现有 offload gating，保持 illegal instruction 行为。
- [x] 现有 `VFWDOTP` decode 未修改。

最终 opcode source：

```text
vfcmacc.vv     31..26=0x3a vm vs2 vs1 14..12=0x1 vd 6..0=0x57
```

生成结果：

```text
VFCMACC_VV = 32'b111010???????????001?????1010111
```

证据：

- 2026-06-08 02:14 CST 运行 `make update_opcodes`，退出码为 0；命令使用
  tracked `sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch` 更新 pinned
  `sw/toolchain/riscv-opcodes` source，并重新生成
  `hw/ip/snitch/src/riscv_instr.sv`。
- 2026-06-08 02:22 CST 再次运行 `make update_opcodes`，退出码为 0；输出
  `Opcode patch already applied`，并只执行 `inst.sverilog` 生成路径。
- 2026-06-08 运行 `rg -n "VFCMACC_VV|vfcmacc.vv|vfcmacc_smoke"
hw/ip/snitch/src/riscv_instr.sv hw/ip/snitch/src/snitch.sv
sw/toolchain/riscv-opcodes/opcodes-rvv sw/riscvTests/CMakeLists.txt
sw/riscvTests/isa/rv64uv/vfcmacc_smoke.c`，确认 opcode source、generated
  pattern、Snitch offload case 和 compile-only smoke test 均存在。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster
bin/spatz_cluster.vlt`，退出码为 0；Verilator 报告成功生成
  `bin/spatz_cluster.vlt`。输出包含既有 testbench/external IP latch warnings，
  无 fatal error。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，
  退出码为 0；CMake/Make 完成软件构建，新增 `vfcmacc_smoke` 作为
  compile-only executable 被覆盖。输出包含既有 runtime/benchmark warnings 和
  DWARF address range table diagnostic，但目标完成。

风险：

- Node 2 只完成 opcode pattern、Snitch 识别和 compile-only smoke。Spatz decode、
  illegal layout 和 VFU 执行从 Node 3/4 开始实现。
- 本地使用 ignored `install` 与 `.venv` 环境入口满足 pinned toolchain 和 Python
  dependencies；这些环境支撑不进入提交。
- `sw/toolchain/riscv-opcodes` 是 ignored nested git checkout，父仓库不能直接
  提交其中单个源文件；本 node 通过 tracked patch 保留 opcode source 变更，并由
  `make update_opcodes` 自动应用。
- `hw/system/spatz_cluster/src/generated/testharness.sv` 与
  `hw/system/spatz_cluster/test/bootrom.elf` 在工作树中已有生成差异，本 node 不
  stage、不提交这些与 opcode/Snitch 无关的 tracked 产物。

## Node 3：Spatz Decode、配置开关与非法路径

状态：已完成

目标：

- 新增 `RVV_EXT_XVFCOMPLEX` 配置开关。
- 新增内部 op `VFCMADD`。
- `vfcmacc.vv` 解码为合法 Spatz VFU request。
- 非法 layout 不进入执行。
- 为 `VFCMADD` 建立 conservative serialization fence，不扩展 multi-imag group
  scoreboard request。

修改范围：

- `hw/ip/snitch/src/snitch.sv`
- `hw/ip/spatz/src/spatz_pkg.sv.tpl`
- `hw/ip/spatz/src/generated/spatz_pkg.sv`
- `hw/ip/spatz/src/spatz_decoder.sv`
- `hw/ip/spatz/src/spatz_controller.sv`
- `sw/riscvTests/CMakeLists.txt`
- `sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] 扩展开关关闭时 `vfcmacc.vv` illegal：decoder 与 controller 均检查
      `RVV_EXT_XVFCOMPLEX`。本 node 未新增独立 disabled-config 仿真目标，风险见下。
- [x] `base % LMUL != 0` illegal。
- [x] `base + 2*LMUL - 1 >= 32` illegal。
- [x] v1 policy 下 `LMUL=m8` illegal。
- [x] `vd` pair overlap source pair illegal。
- [x] `VFCMADD` 发射前等待旧 VFU/VLSU/VSLDU 指令完成；`VFCMADD` 完成前阻止新的
      VFU/VLSU/VSLDU 指令发射。实现为 controller 中的 conservative
      `cfma_fence_stall` 和 `cfma_running_q`。
- [x] 现有 vector floating-point decode 无回归：RTL/software build 均通过，
      Node 3 只新增 `VFCMACC_VV` 到既有 FP vector decode 列表。

证据：

- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster
bin/spatz_cluster.vlt`，退出码为 0；最终重跑输出
  `make: 'bin/spatz_cluster.vlt' is up to date.`，此前同一 Node 3 RTL 改动已完成
  Verilator C++ rebuild 并链接生成 `bin/spatz_cluster.vlt`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，
  退出码为 0；CMake/Make 完成软件构建并注册 `vfcmacc_illegal`。输出包含既有
  runtime/benchmark warnings 和 DWARF address range table diagnostic，但目标完成。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R vfcmacc_illegal --output-on-failure`，退出码为 0；结果为
  `1/1 Test #68 ... Passed`，`100% tests passed, 0 tests failed out of 1`。
- 2026-06-08 运行 `git diff --check`，退出码为 0，未发现 whitespace error。
- 中间失败与修正记录：
  - 初版非法 layout CTest 中 `.vv` 动态非法没有触发 trap；根因是 Snitch 未把
    Spatz issue response 的 `exception` 纳入异常路径，只打印 illegal 且没有设置
    `mcause`/redirect。修复为 `acc_issue_exception`，保留 q-channel valid 让 Spatz
    consume/discard，同时在 Snitch 中设置 illegal cause 并跳转异常入口。
  - 随后测试读到 cause 0/4；根因是测试 trap entry 调用 C handler 时只保存 `ra`，
    破坏了被中断点仍活跃的 caller-saved register。修复为 pure assembly trap entry，
    只使用并恢复 `t0..t3`。
  - `out-of-range m4` 起初使用 `vd=v24`，实际覆盖 `v24..v31`，是合法边界；测试改为
    `vd=v28`，覆盖越界 imag group。

风险：

- `vstart != 0` 当前按计划在 Node 3 定义为 illegal；Node 5b 必须重新评估并冻结最终
  v1 行为。
- 本 node 完成 decode、动态合法性、异常路径和 fence；`VFCMADD` VFU 执行仍未实现，
  由 Node 4 处理。
- `RVV_EXT_XVFCOMPLEX=0` 的 disabled-config 路径已有 RTL hook，但本 node 只通过默认
  配置仿真覆盖非法 layout，未新增单独 disabled-config build。
- Conservative fence 已实现，专门的 real/imag hazard regression 留到 Node 5d。

## Node 4：v1a Unmasked e32 多拍执行

状态：已完成（v1a，非完整 v1）

目标：

- 实现 `vfcmacc.vv` 的最小可执行路径。
- 只要求 `e32`、`vm=1`、合法 non-overlap layout。
- 建立四阶段 micro-op 执行、单次 architectural completion 和 `fflags` OR
  final-only 暴露机制。

修改范围：

- `hw/ip/spatz/src/spatz_vfu.sv`
- `sw/riscvTests/CMakeLists.txt`
- `sw/riscvTests/isa/rv64uv/vfcmacc_e32.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] `Cfma_RR -> Cfma_II -> Cfma_RI -> Cfma_IR` 四阶段状态推进存在，对应
  `MAC_RR/MAC_II/MAC_RI/MAC_IR`。
- [x] `e32`、`vm=1`、合法 non-overlap layout 的结果逐 bit 等同四指令 reference
  sequence。
- [x] 每条 `vfcmacc.vv` 只在 final phase 返回一次 VFU response。
- [x] back-to-back same accumulator pair 无 deadlock：`vfcmacc_e32` 覆盖连续两条
  `vfcmacc.vv v8, v0, v2` 写同一 `v8/v9` accumulator pair。
- [x] 四个内部 FPU operation 的 status 在 VFU 内局部 OR，并只在 final result
  response 那一拍对 Snitch 暴露。
- [x] 本阶段明确为 `v1a`，只覆盖 unmasked e32，不声称完整 v1。

证据：

- TDD red：2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R vfcmacc_e32 --output-on-failure`，退出码为 8；在 VFU 执行尚未实现时
  按预期失败，关键输出为 `real[0] Got 0, expected 1070386381`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，退出码为 0；
  CMake/Make 成功注册并构建 `vfcmacc_e32`。输出仍包含既有 runtime/benchmark
  warnings 和 DWARF address range table diagnostic。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`，
  退出码为 0；Verilator 5.034 重新生成并链接 `bin/spatz_cluster.vlt`。输出包含既有
  latch warnings，无 fatal error。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R vfcmacc_e32 --output-on-failure`，退出码为 0；结果为
  `1/1 Test #69 ... Passed`，覆盖单条 `vfcmacc.vv` 和 back-to-back same accumulator
  case。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc_e32|vfcmacc_illegal|vfmacc|vfnmsac" --output-on-failure`，
  退出码为 0；结果为 `100% tests passed, 0 tests failed out of 4`。
- 2026-06-08 运行 `git diff --check`，退出码为 0，未发现 whitespace error。

风险：

- Node 4 只覆盖 `e32`、`vm=1`、合法 non-overlap paired layout；`e64/e16` 留给
  Node 5a。
- mask、tail 和最终 `vstart` 行为留给 Node 5b；当前 `vstart != 0` 仍沿用 Node 3
  illegal policy。
- `fflags` 的 VFU OR/final-only 暴露机制已实现，但 NaN/Inf、zero sign、rounding mode
  和 exact architectural `fflags` bit 对比仍由 Node 5c 验证。
- Conservative fence 的专门 real/imag hazard regression 留给 Node 5d；本 node 仅用
  back-to-back same accumulator e32 case覆盖最小 deadlock/错序风险。

## Node 5a：e64/e16 Format 支持

状态：已完成

目标：

- 在 v1a e32 基础上补齐 e64 和 e16。
- 保持每种 SEW 都 bit-identical 于四指令 reference sequence。

修改范围：

- `hw/ip/spatz/src/spatz_controller.sv`
- `sw/riscvTests/CMakeLists.txt`
- `sw/riscvTests/isa/rv64uv/vfcmacc.c`
- `sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] e32/e64/e16 unmasked case 均 bit-identical：`vfcmacc` regression 覆盖
      e32 single、e32 back-to-back、e64 和 e16，均与四指令 reference sequence
      逐 bit 对比。
- [x] e8、integer vtype 和 unsupported alternative FP formats illegal：e8 沿用
      `vfcmacc_illegal` 覆盖；integer vtype 不能匹配 OPFVV 浮点 decode；新增
      `fmode.src/dst != 0` 的 e16 alternative format trap 覆盖。
- [x] e64 只在 RVD/FPU 可用时合法：controller 仍保留
      `vtype.vsew == EW_64 && (!spatz_pkg::RVD || MAXEW != EW_64)` illegal gate。
- [x] e16 只在 half-precision FPU support 可用时合法：默认 RVD FPU features
      支持 FP16；v1 `VFCMADD` 现在拒绝 `FP16ALT`/alternative fmode。
- [x] e32 v1a 测试无回归：原 `vfcmacc_e32` 内容迁移为 `vfcmacc` 的
      `TEST_CASE1/2`，最终 `vfcmacc` CTest 通过。

证据：

- TDD red：2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure`，退出码为 8；
  `vfcmacc` behavior test 通过，但新增 alternative fmode illegal case 失败，
  关键输出为 `unsupported alternative fmode did not raise illegal instruction
trap.`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster
bin/spatz_cluster.vlt`，退出码为 0；Verilator 5.034 重新生成并链接
  `bin/spatz_cluster.vlt`。输出包含既有 latch warnings，无 fatal error。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，
  退出码为 0；CMake/Make 成功注册并构建统一 `vfcmacc` regression。输出仍包含
  既有 runtime/benchmark warnings 和 DWARF address range table diagnostic。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure`，退出码为 0；结果为
  `100% tests passed, 0 tests failed out of 2`。

风险：

- 本 node 覆盖 unmasked e32/e64/e16 和 alternative fmode legality；mask、tail 和
  `vstart` 行为仍留给 Node 5b。
- e64 的 disabled RVD 配置未新增独立 build；本 node 依赖 controller 中已有
  RVD/MAXEW legality gate，并在默认 RVD build 中覆盖 e64 正常路径。

## Node 5b：Mask、Tail 与 vstart 行为

状态：已完成

目标：

- 补齐 mask、tail 和 vstart 行为。

修改范围：

- `hw/ip/spatz/src/spatz_vfu.sv`
- `sw/riscvTests/isa/rv64uv/vfcmacc.c`
- `sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] `vm=0` masked `vfcmacc.vv` 覆盖 e32/e64/e16，active lanes 与四指令
      reference sequence bit-identical，masked-off accumulator lanes 保持原值。
- [x] tail-undisturbed short-`vl` 覆盖 e32/e64/e16，tail accumulator lanes 保持原值。
- [x] `vstart != 0` 最终 v1 policy 冻结为 illegal；`vfcmacc_illegal` 覆盖
      nonzero `vstart` trap。
- [x] VFU 写回只对 active bytes 置位 `vrf_wbe_o`；masked/tail inactive bytes 不
      写 VRF。
- [x] e32/e64/e16 unmasked regression 无回归，统一 `vfcmacc` CTest 通过。

证据：

- TDD red：2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure`，退出码为 8；
  `vfcmacc_illegal` 通过，`vfcmacc` 失败，关键输出为 masked/tail cases：
  `TC 5 real[0] FAILED`、`TC 6 real[12] FAILED`、`TC 7 real[0] FAILED`、
  `TC 8 real[5] FAILED`、`TC 9 real[0] FAILED`、`TC 10 real[11] FAILED`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`，
  退出码为 0；最终 fresh rerun 输出 `make: 'bin/spatz_cluster.vlt' is up to
  date.`，此前同一 Node 5b RTL 改动已完成 Verilator rebuild 并链接生成
  `bin/spatz_cluster.vlt`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，
  退出码为 0；CMake/Make 成功重建软件测试树。输出仍包含既有 runtime/benchmark
  warnings 和 DWARF address range table diagnostic。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc$|vfcmacc_illegal" --output-on-failure`，退出码为 0；结果为
  `100% tests passed, 0 tests failed out of 2`。
- 2026-06-08 运行 `git diff --check`，退出码为 0，未发现 whitespace error。
- 2026-06-08 运行 `git diff --cached --check`，退出码为 0，staged diff 未发现
  whitespace error。

风险：

- 本 node 将 `vstart != 0` 固定为 v1 illegal policy。支持 resumable
  `vfcmacc.vv` 需要额外 phase/vstart 状态，不纳入 v1。
- `VFCMADD` 通过 VRF byte-enable 保持 masked-off/tail lanes；inactive lane 的精确
  `fflags` 行为仍由 Node 5c 继续验证。
- 既有普通 VFU arithmetic mask 测试在仓库中仍有部分注释关闭；本 node 只为
  `VFCMADD` 补齐 v1 mask/tail 行为。

## Node 5c：特殊数值、Rounding 与 FFLAGS

状态：已完成

目标：

- 覆盖 zero sign、NaN/Inf、rounding mode 和 `fflags`。

修改范围：

- `sw/riscvTests/isa/rv64uv/vfcmacc.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] `+0.0/-0.0` result bits 与四指令 reference sequence bit-identical。
- [x] NaN、Inf、overflow 和 invalid-result bits 与四指令 reference sequence
      bit-identical。
- [x] RNE 与 RTZ rounding-mode cases 均与四指令 reference sequence bit-identical。
- [x] `fflags_final` 与四个 reference FMA/FNMSAC operations 的 architectural
      flags 一致，并在 `vfcmacc.vv` 后一次性可读。
- [x] masked `vfcmacc.vv` 的 `fflags` 与当前四条 masked FMA reference sequence
      一致。
- [x] 现有 `vfmacc`、`vfnmsac` 和 `vfwdotp` proxy regression 无回归。

证据：

- TDD red：2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc$" --output-on-failure`，退出码为 8；新增 TC13 初版错误地
  假设 masked-off signaling-NaN lanes 不应产生 flags，输出为
  `[TC 13] fflags FAILED. Got 0x10, expected 0x0.`。根据 v1 reference 必须等同
  当前四条 masked FMA sequence，测试修正为比较 `vfcmacc.vv` 与 reference flags。
- 修正测试 oracle 后，2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc$" --output-on-failure`，退出码为 0；结果为
  `100% tests passed, 0 tests failed out of 1`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster bin/spatz_cluster.vlt`，
  退出码为 0；fresh rerun 输出 `make: 'bin/spatz_cluster.vlt' is up to date.`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，
  退出码为 0；CMake/Make 成功重建软件测试树。输出仍包含既有 runtime/benchmark
  warnings 和 DWARF address range table diagnostic。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfcmacc$" --output-on-failure`，退出码为 0；结果为
  `100% tests passed, 0 tests failed out of 1`。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfmacc|vfnmsac|vfwdotp" --output-on-failure`，退出码为 0；当前 build
  只注册 `vfmacc` 与 `vfnmsac` 两个匹配目标，结果为
  `100% tests passed, 0 tests failed out of 2`。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "sdotp-(hp|bp)-fmatmul_M64_N64_K64" --output-on-failure`，退出码为 0；
  这两个 benchmark kernels 使用 `vfwdotp.vf`，作为当前 build 的 `vfwdotp`
  proxy regression，结果为 `100% tests passed, 0 tests failed out of 2`。
- 2026-06-08 运行 `ctest -N -R "vfwdotp|dotp"`，退出码为 0；列出的目标包含
  sdotp/dotp benchmarks，但没有独立名为 `vfwdotp` 的 ISA CTest。
- 2026-06-08 运行 `git diff --check`，退出码为 0，未发现 whitespace error。

风险：

- Node 5c 只新增数值和 `fflags` coverage；未修改 RTL。现有 `VFCMADD`
  `fflags` OR/final-only 机制满足这些 cases。
- sNaN masked-off lane flags 按计划的 bit-identical reference 处理：与当前四条
  masked FMA sequence 一致，而不是按“inactive lane 不产生 flags”的替代语义。
- `vfwdotp` 当前没有独立 CTest 名称；本 node 使用包含 `vfwdotp.vf` 的 sdotp
  benchmark 作为 proxy regression。

## Node 5d：Serialization Fence 与 Hazard Regression

状态：已完成

目标：

- 验证 conservative serialization fence 覆盖隐式 imag group hazards。
- 完成 v1 ISA 行为验收。

修改范围：

- `sw/riscvTests/isa/rv64uv/vfcmacc.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] `vfcmacc.vv` 后紧跟读取 `vd.real/vd.imag` 的普通 vector 指令无 stale read。
- [x] 普通 vector 指令写 `vs1.imag` 或 `vs2.imag` 后紧跟 `vfcmacc.vv` 无 stale read。
- [x] VLSU 写 `vs1.imag` 与 `vs2.imag` 后紧跟 `vfcmacc.vv` 无 stale read。
- [x] back-to-back `vfcmacc.vv` 写同一 accumulator pair 无 deadlock、无错序完成。
- [x] 非法 overlap case 不进入执行状态，由 `vfcmacc_illegal` 覆盖。
- [x] v1 ISA 行为已覆盖 e32/e64/e16、mask/tail、vstart illegal、fflags、
      NaN/zero sign 和 serialization fence；本 node 后不再标为 v1a。

证据：

- TDD red：2026-06-08 临时将 `spatz_controller.sv` 中
  `cfma_fence_stall` 置为 `1'b0` 后重新运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster
bin/spatz_cluster.vlt`，退出码为 0；随后从 `hw/system/spatz_cluster/sw/build`
  运行 `ctest -R "vfcmacc$" --output-on-failure`，退出码为 8，输出
  `ERROR: ... vfcmacc.c failed 6 tests!`。失败集中在既有 masked/tail cases，
  证明 conservative fence 对 `VFCMADD` 多拍执行和后续发射隔离是必要条件。
- 2026-06-08 恢复 `cfma_fence_stall` 后运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster
bin/spatz_cluster.vlt`，退出码为 0；Verilator 重新生成并链接
  `bin/spatz_cluster.vlt`。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，
  退出码为 0；软件测试树重建完成。输出仍包含既有 runtime/benchmark warnings
  和 DWARF address range table diagnostic。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R vfcmacc --output-on-failure`，退出码为 0；结果为
  `100% tests passed, 0 tests failed out of 2`，覆盖 `vfcmacc_illegal` 和新增
  hazard cases TC14-TC18。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "vfmacc|vfnmsac|vfwdotp" --output-on-failure`，退出码为 0；当前 build
  只注册 `vfmacc` 与 `vfnmsac` 两个匹配目标，结果为
  `100% tests passed, 0 tests failed out of 2`。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -N -R "vfwdotp|dotp"`，退出码为 0；列出的目标包含 sdotp/dotp benchmarks，
  但没有独立名为 `vfwdotp` 的 ISA CTest。
- 2026-06-08 从 `hw/system/spatz_cluster/sw/build` 运行
  `ctest -R "sdotp-(hp|bp)-fmatmul_M64_N64_K64" --output-on-failure`，
  退出码为 0；包含 `vfwdotp.vf` 的 sdotp proxy regression 结果为
  `100% tests passed, 0 tests failed out of 2`。
- 2026-06-08 运行 `git diff --check`，退出码为 0，未发现 whitespace error。

风险：

- Node 5d 未修改 RTL；现有 controller conservative serialization fence 满足新增
  hazards。更精细的 imag group scoreboard 仍是 v2 之后的性能/复杂度评估项。
- `vfwdotp` 当前没有独立 ISA CTest 名称，继续使用 sdotp benchmark 作为 proxy
  regression。

## Node 6：Benchmark A/B 与性能报告

状态：阻塞（代码和构建已完成，RTL benchmark 未收敛）

目标：

- 在 `dp-cdotp` 中加入 old/new 路径。
- 量化 instruction count、cycle 和 frontend/offload pressure。

修改范围：

- `sw/spatzBenchmarks/CMakeLists.txt`
- `sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c`
- `sw/spatzBenchmarks/dp-cdotp/main.c`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [x] old path 与 new path 均可构建。
- [x] `sw/spatzBenchmarks/CMakeLists.txt` 注册
      `dp-cdotp_old_M128`、`dp-cdotp_vfcmacc_M128`、
      `dp-cdotp_old_M4096` 和 `dp-cdotp_vfcmacc_M4096`，使用
      `SPATZ_USE_VFCMACC=0/1` 区分路径。
- [ ] 默认验收 `M128` 与 `M4096` old/new 均通过：阻塞在 RTL benchmark
      运行收敛，`dp-cdotp_old_M128` 在 600 秒上限内超时；未继续宣称 M4096
      通过。
- [ ] 输出 old/new cycles：未取得，原因同上。
- [x] 输出 instruction count proxy：程序输出格式已加入
      `inner_loop_insn_proxy` 和 `complex_mac_insn_proxy`；old path 为
      `7/4`，new path 为 `4/1`，表示 inner loop 静态指令数与 complex MAC
      指令数 proxy。
- [ ] frontend/offload stall counters：当前 runtime 未提供可直接读取 counter；
      本 node 仅保留静态 proxy，真实 cycle/offload 数据被 RTL benchmark
      收敛 blocker 阻塞。

证据：

- TDD red / blocker reproduction：2026-06-08 从
  `hw/system/spatz_cluster/sw/build` 运行
  `ctest -V -R "dp-cdotp_old_M128$"`，`dp-cdotp` 第一版全量驻留路径在
  13 分钟后仍未返回；`spatzBenchmarks/logs/trace_hart_00000.dasm` 与
  `trace_hart_00001.dasm` 停在 745/530 行且 mtime 不再更新。手动停止该次
  CTest，作为 Node 6 benchmark blocker 证据。
- 2026-06-08 运行 `timeout 600s ctest -V -R "dp-cdotp_ver2_M128$"`，
  退出码为 124；分块版参考也未在 600 秒内收敛，trace 停在 767/559 行且
  mtime 不再更新，说明当前问题不是新增 `SPATZ_USE_VFCMACC` 路径独有。
- 根据既有 `dp_cdotp_dp_cmatmul_v1_排查与验证记录.md` 中关于第一版
  `dp-cdotp` 全量驻留风险的记录，2026-06-08 将 `dp-cdotp/main.c` 改成
  `CDOTP_TILE_ELEMS=1024` 的分块 DMA/分块累加主流程，old/new A/B 共享同一
  数据搬运框架。
- 2026-06-08 运行
  `PATH="$PWD/.venv/bin:$PATH" make -C hw/system/spatz_cluster sw.vlt`，
  退出码为 0；CMake/Make 完成软件构建并注册/链接
  `dp-cdotp_old_M128`、`dp-cdotp_vfcmacc_M128`、`dp-cdotp_old_M4096` 和
  `dp-cdotp_vfcmacc_M4096`。输出仍包含既有 runtime/benchmark warnings 和
  DWARF address range table diagnostic。
- 2026-06-08 运行 `ctest -N -R
  "dp-cdotp_(old|vfcmacc)_M(128|4096)$"`，退出码为 0；列出 4 个 Node 6
  old/new 目标。
- 修复后再次运行 `timeout 600s ctest -V -R "dp-cdotp_old_M128$"`，
  退出码为 124；trace 停在 766/559 行且 mtime 不再更新。M128 old path
  仍无法给出 correctness/cycle 结果，Node 6 因 benchmark RTL 运行收敛问题
  标为阻塞。
- 对照运行 `timeout 180s ctest -R "vfcmacc$" --output-on-failure`，退出码为
  0；`vfcmacc` ISA regression 用时 117.31 秒并通过，说明当前 simulator
  基础路径仍可执行并退出，blocker 限定在 benchmark 类目标。

风险：

- Node 6 尚未取得 old/new cycles、correctness 或 M4096 结果；不得使用本 node
  声称 `vfcmacc.vv` benchmark speedup。
- `dp-cdotp_vfcmacc` new path 已编译链接，但没有 RTL runtime pass 证据。
- 分块 DMA 主流程解决 M4096 全量驻留的已知 TCDM 风险，但未解决当前 RTL
  benchmark 停滞；后续需要用波形或 RTL trace 定位 benchmark 在
  vector reduction/result writeback/barrier 附近等待的根因。

## Node 7：Mnemonic 与工具链整理

状态：阻塞（工具链 source 未展开，installed LLVM 不支持 mnemonic）

目标：

- 把临时 `.insn` 或固定编码 wrapper 替换为正式 mnemonic。
- 明确 assembler、objdump 和 LLVM 支持边界。

修改范围：

- `docs/complex-instruction-extension/toolchain_mnemonic_status.md`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- [ ] inline asm 可写 `vfcmacc.vv` mnemonic：阻塞。当前 installed LLVM 14.0.6
      assembler 报 `unrecognized instruction mnemonic`。
- [x] benchmark 不需要 binary patch：当前 benchmark 使用固定 `.insn` wrapper，
      不手工 patch binary。
- [ ] objdump 能显示 `vfcmacc.vv`：阻塞。`.insn` 可汇编成
      `57 18 80 ea`，但 `llvm-objdump` 显示 `<unknown>`。
- [x] LLVM 自动 SelectionDAG lowering 仍不纳入本 node；已记录为 v1 之外的
      follow-up。

证据：

- 2026-06-08 运行 `find sw/toolchain -maxdepth 2 -type d`，确认当前只展开
  `sw/toolchain/riscv-opcodes`；`sw/toolchain/llvm-project` 与
  `sw/toolchain/riscv-gnu-toolchain` source tree 不存在。
- 2026-06-08 运行 `rg -n "vfcmacc|VFCMACC|vfwdotp|VFWDOTP"
  sw/toolchain sw/toolchain-patches install/llvm install/riscv-gcc -S`，只在
  `sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch` 与
  `sw/toolchain/riscv-opcodes/opcodes-rvv` 中找到 `vfcmacc`；installed toolchain
  中未找到 mnemonic 支持痕迹。
- 2026-06-08 运行 installed clang mnemonic assembly smoke：
  `printf "... vfcmacc.vv v16, v0, v8" | install/llvm/bin/clang -x assembler ...`，
  退出码为 1；关键错误为 `unrecognized instruction mnemonic`。
- 2026-06-08 运行 fixed `.insn` assembly smoke：
  `printf "... .insn r 0x57, 0x1, 0x75, v16, v0, v8" |
  install/llvm/bin/clang -x assembler ...`，退出码为 0；随后
  `llvm-objdump -d` 显示 `57 18 80 ea   <unknown>`。
- 2026-06-08 运行 `install/llvm/bin/clang --version`，输出 LLVM 14.0.6，
  revision 为 `pulp-platform/llvm-project b494f2d8...`。
- 2026-06-08 新增
  `docs/complex-instruction-extension/toolchain_mnemonic_status.md`，记录当前
  assembler/objdump 状态和后续解锁路径。

风险：

- Node 7 未能把 `.insn` 替换为正式 mnemonic；v1 软件路径仍依赖固定编码
  wrapper。
- 正式 mnemonic support 需要展开并 patch pinned LLVM/binutils source，或安装
  已包含 `vfcmacc.vv` 的预构建工具链；不得把完整 `make all/toolchain` 构建混入
  本 node 默认修复路径。

## Node 8：v2 Datapath 评审门

状态：未开始

目标：

- 基于 v1 真实数据决定是否启动专用 complex-FMA datapath。

证据：

- 尚无。

## 2026-06-08 Plan hardening：Goal 一次性执行补强

状态：已完成

目标：

- 将 `PLAN.md` 从方向性计划补强为 goal 可连续执行规格。
- 冻结 opcode 生成、scoreboard hazard、VFU 原子性和 benchmark 默认决策。
- 拆分原 Node 5，降低长跑执行时的中途决策风险。

修改范围：

- `docs/complex-instruction-extension/PLAN.md`
- `docs/complex-instruction-extension/PHASE_RESULTS.md`
- `docs/complex-instruction-extension/GIT_NOTES.md`

验收标准：

- `PLAN.md` 明确 `make update_opcodes` 是 Node 2 唯一默认 opcode 入口。
- `PLAN.md` 明确 v1 使用 conservative serialization fence，不扩展 multi-imag
  scoreboard request。
- `PLAN.md` 明确 Node 6 benchmark 默认验收 `dp-cdotp` old/new `M128/M4096`。
- 原 Node 5 拆分为 Node 5a、5b、5c、5d。

证据：

- 2026-06-08 运行 `git diff --check`，退出码为 0，未发现 whitespace error。

风险：

- 本次只修改文档，不执行 RTL、opcode 或 benchmark 实现。
