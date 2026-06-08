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

状态：未开始

目标：

- 补齐 mask、tail 和 vstart 行为。

证据：

- 尚无。

## Node 5c：特殊数值、Rounding 与 FFLAGS

状态：未开始

目标：

- 覆盖 zero sign、NaN/Inf、rounding mode 和 `fflags`。

证据：

- 尚无。

## Node 5d：Serialization Fence 与 Hazard Regression

状态：未开始

目标：

- 验证 conservative serialization fence 覆盖隐式 imag group hazards。
- 完成 v1 ISA 行为验收。

证据：

- 尚无。

## Node 6：Benchmark A/B 与性能报告

状态：未开始

目标：

- 在 `dp-cdotp` 中加入 old/new 路径。
- 量化 instruction count、cycle 和 frontend/offload pressure。

证据：

- 尚无。

## Node 7：Mnemonic 与工具链整理

状态：未开始

目标：

- 把临时 `.insn` 或固定编码 wrapper 替换为正式 mnemonic。
- 明确 assembler、objdump 和 LLVM 支持边界。

证据：

- 尚无。

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
