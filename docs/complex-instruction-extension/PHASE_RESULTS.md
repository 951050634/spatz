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

状态：未开始

目标：

- 生成 `LMUL={1,2,4,8}` 的 register layout 合法表。
- 冻结 v1 legal/illegal policy。
- 决定 `vfcmacc.vv` encoding。

证据：

- 尚无。

## Node 2：Opcode 生成与 Snitch 识别

状态：未开始

目标：

- 让 `riscv_instr::VFCMACC_VV` 成为可引用的指令 pattern。
- Snitch 能在 RVV/RVF 可用时 offload 该指令。

证据：

- 尚无。

## Node 3：Spatz Decode、配置开关与非法路径

状态：未开始

目标：

- 新增 `RVV_EXT_XVFCOMPLEX` 配置开关。
- 新增内部 op `VFCMADD`。
- `vfcmacc.vv` 解码为合法 Spatz VFU request。
- 非法 layout 不进入执行。

证据：

- 尚无。

## Node 4：v1a Unmasked e32 多拍执行

状态：未开始

目标：

- 实现 `vfcmacc.vv` 的最小可执行路径。
- 只要求 `e32`、`vm=1`、合法 non-overlap layout。

证据：

- 尚无。

## Node 5a：e64/e16 Format 支持

状态：未开始

目标：

- 补齐 e64 和 e16。

证据：

- 尚无。

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
