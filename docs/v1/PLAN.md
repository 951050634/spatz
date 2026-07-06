# Spatz 复数指令扩展工程规划

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` when implementing this plan. Execute one node at
> a time. Do not combine opcode, decoder, VFU, benchmark, and toolchain work in
> one large change.

**Goal:** 在 Spatz 上新增一条非标准复数浮点向量乘加指令
`vfcmacc.vv`，把现有复数 kernel 中四条向量 FMA 指令折叠为一条软件可见
架构指令，并建立可审计、可回归、可量化的工程闭环。

**Architecture:** v1 使用 32-bit RVV OPFVV 风格编码、paired vector
register layout 和现有 Snitch-to-Spatz offload 路径。执行侧优先用多拍
micro-op 复用现有 FPU/VRF 通路，保证数值行为 bit-identical 于当前四指令
序列；v2 之后才评估专用 complex-FMA datapath。

**Tech Stack:** SystemVerilog、Spatz/Snitch RTL、`riscv_instr.sv` opcode
生成链路、C/inline assembly ISA tests、CMake/CTest、Verilator。

---

## 1. 工程边界与默认决策

### 1.1 v1 必须完成的内容

v1 只实现一条 vector-vector 形式：

```asm
vfcmacc.vv vd, vs1, vs2
```

语义为：

```c
vd.real += vs1.real * vs2.real - vs1.imag * vs2.imag;
vd.imag += vs1.real * vs2.imag + vs1.imag * vs2.real;
```

v1 必须满足以下边界：

- 只支持 `.vv`，不实现 `.vf`。
- 只支持 paired register group，不支持任意 real/imag register 编码。
- 优先支持 `e32`，随后支持 `e64`，最后支持 `e16`。
- 最终 v1 必须支持 mask；早期 `v1a` 可只支持 `vm=1`，但不能作为 v1
  验收。
- 内部执行必须 bit-identical 于当前四指令 reference sequence。
- 每条架构指令只产生一次 architectural completion。
- 四个内部浮点操作的 `fflags` 必须 bitwise OR 后一次性暴露。
- v1 性能主张只限定为降低 instruction count、fetch/decode/offload 压力和
  issue queue 压力；不得承诺原始 FPU 吞吐提升。

### 1.2 v1 明确不做的内容

以下内容不得混入 v1 主线：

- `vfcmacc.vf` 或任何复数标量形式。
- conjugate、negated、butterfly、rotation 等变体。
- LLVM 自动指令选择和完整 register allocator 支持。
- 专用 complex-FMA datapath。
- Gem5、Spike 或故障注入工具的强制集成。
- 修改外部协处理器接口，例如 CORE-V X-IF；本项目使用现有 Snitch/Spatz
  offload 路径。

### 1.3 后续扩展优先级

后续扩展按以下顺序单独立项：

```text
v1.5  vfcjmacc.vv   acc += conj(vs1) * vs2
v2    vfcmul.vv     dst = vs1 * vs2
v3    vfcmacc.vf    acc += complex_scalar * complex_vector
v4    FFT butterfly 或 rotation 类专项指令
```

共轭形式命名为 `vfcjmacc.vv`，不使用较长的 `vfconjmac.vv`。`j` 表示复数
共轭相关的虚部符号变化，命名更接近 RISC-V 助记符的简短风格。

## 2. 工作树、记录与 Git 规范

### 2.1 工作树要求

本工程在隔离工作树中进行：

```text
/home/wxt/spatz-cfma
branch: feature/cfma-instruction-extension
```

该工作树当前基于不含 online softmax merge accelerator 主线改动的分支，避免
加速器 RTL、benchmark 和论文数据污染本工程上下文。

根目录必须保留并追踪 `.codexignore`，内容从 `/home/wxt/spatz/.codexignore`
复制，用于避免 toolchain、build output、仿真波形和二进制产物污染 Codex
上下文。

### 2.2 阶段记录文件

本目录必须维护三类文档：

```text
docs/v1/PLAN.md
docs/v1/PHASE_RESULTS.md
docs/v1/GIT_NOTES.md
```

每完成一个 node，必须更新 `PHASE_RESULTS.md`：

- 状态：`未开始`、`进行中`、`已完成`、`阻塞`、`部分完成`。
- 目标：本 node 的唯一目标。
- 修改范围：实际 touched files。
- 验收标准：逐条打勾或说明未满足原因。
- 证据：命令、时间、退出码、关键输出摘要。
- 风险：遗留风险和下一步处理。

每完成一个 node，必须更新 `GIT_NOTES.md`：

- 本轮分支和 `git status --short --branch`。
- 本轮计划提交名。
- `git diff --stat` 摘要。
- 验证命令和结果。
- 实际 commit hash。
- 如远端操作失败，仅记录失败，不把修复网络作为本工程内容。

### 2.3 Git 操作规则

每个 node 结束时必须独立提交，禁止把多个复杂 node 合成一个提交。

推荐提交序列：

```text
[cfma] Record complex instruction planning baseline
[cfma] Add complex register layout reference checks
[cfma] Add vfcmacc opcode pattern
[cfma] Decode vfcmacc in Snitch and Spatz
[cfma] Add vfcmacc e32 micro-op execution
[cfma] Add vfcmacc e64 and e16 behavior
[cfma] Cover vfcmacc mask and tail behavior
[cfma] Cover vfcmacc numerical corner cases
[cfma] Complete vfcmacc ISA behavior
[cfma] Add vfcmacc benchmark path
[cfma] Add vfcmacc mnemonic support
[cfma] Record complex datapath v2 decision
```

每次提交前至少运行：

```sh
git status --short --branch
git diff --check
```

涉及 RTL 的 node 还必须运行：

```sh
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
```

涉及软件或 benchmark 的 node 还必须运行：

```sh
make -C hw/system/spatz_cluster sw.vlt
```

涉及测试新增或行为变化的 node 还必须从 `hw/system/spatz_cluster/sw/build`
运行目标 CTest。

允许进行长时间编译工作以验证指令集修改的合理性。涉及 RTL、opcode、decode、
benchmark 或 ISA 行为的修改，不得因为 `make -C hw/system/spatz_cluster
bin/spatz_cluster.vlt`、`make -C hw/system/spatz_cluster sw.vlt` 或目标 CTest
耗时较长而跳过验证。长时间验证运行时必须记录：

- 命令、工作目录和必要环境变量。
- 开始时间、结束时间和总耗时。
- 退出码。
- 关键输出摘要，包括 error、fatal warning、timeout、CTest 失败项或成功计数。
- 若失败或超时，记录为该 node 的风险或 blocker，不得把对应功能标记为已完成。

### 2.4 Goal 一次性执行默认决策

后续如果使用 goal 功能连续执行本计划，以下决策为默认实现要求。执行 agent
不得在这些点重新二选一，除非遇到无法继续的硬 blocker，并把 blocker 记录到
`PHASE_RESULTS.md` 与 `GIT_NOTES.md`。

- Opcode 生成唯一默认入口是：

  ```sh
  make update_opcodes
  ```

  该命令负责按 pinned version 拉取 `sw/toolchain/riscv-opcodes` 并重新生成
  `hw/ip/snitch/src/riscv_instr.sv`。不得用 `make all` 作为 Node 2 默认路径，
  因为它会触发完整 toolchain 构建。若 `make update_opcodes` 因网络或上游
  源缺失失败，Node 2 标为 `阻塞`，不得切换到手工 patch binary 或提交仅手改
  generated file 的结果。

- v1 scoreboard 采用 conservative serialization fence，不扩展
  `spatz_req_t` 去显式携带六个 real/imag register groups。默认实现方式是：
  `vfcmacc.vv` 只在所有既有非 `CON` offload 指令完成后发射；一旦
  `VFCMADD` 发射，在该指令完成响应前阻止新的 VFU/VLSU/VSLDU 指令发射。该
  fence 是 v1 对隐式 imag group RAW/WAR/WAW hazard 的架构保护。

- v1 VFU 复用现有 VRF/FPU 多拍通路，不新增 VRF 物理端口，不新增专用
  complex-FMA datapath。若 kill/flush/debug 能在 partial writeback 后暴露
  中间架构状态，Node 4 必须阻塞；不得用“当前测试没暴露”替代精准状态说明。

- 软件 bring-up 默认使用固定寄存器 inline assembly wrapper 与 `.insn` 或固定
  编码宏。正式 `vfcmacc.vv` mnemonic 支持只在 Node 7 处理，不阻塞 Node 4-6
  的 RTL/benchmark 验收。

- Benchmark 默认在 `dp-cdotp` 上新增 old/new 两套 CTest 目标，使用
  `SPATZ_USE_VFCMACC=0/1` 选择路径。验收使用 `M128`、`M1024` 和 `M4096` 规模。

## 3. ISA 与数值语义

### 3.1 编码策略

自定义指令必须保持 32-bit 指令宽度，不引入 48-bit 或 64-bit 变长指令。
优先复用 RVV OPFVV 路径和现有 vector floating-point decode 结构，而不是
新增完全独立的 major opcode。这样可以复用 Snitch/Spatz 已有的向量 offload、
`vm`、`vtype`、`vd/vs1/vs2` 字段和 VFU 调度逻辑。

当前分支只追踪了 toolchain 版本文件，未展开 `sw/toolchain/riscv-opcodes`
源码目录。Node 2 必须通过 `make update_opcodes` 展开 pinned opcode source 并
重新生成 `hw/ip/snitch/src/riscv_instr.sv`。正式选定 encoding 前必须先确认实际
opcode 源路径：

```sh
find sw \( -path '*riscv-opcodes*' -o -name 'opcodes-rvv' \) -print
rg -n "VFWDOTP|vfwdotp|VFMACC_VV" hw/ip/snitch/src/riscv_instr.sv hw/ip/spatz/src
```

如果 `riscv-opcodes` 源码尚未展开，执行 `make update_opcodes`。长期方案必须
更新 opcode 源并重新生成 `hw/ip/snitch/src/riscv_instr.sv`；不得只手改生成文件
作为最终交付。

encoding 决策必须记录：

- `vfcmacc.vv` 的完整 bit pattern。
- 与 `VFMACC_VV`、`VFNMSAC_VV`、`VFWDOTP_VV`、`VFWDOTP_VF` 是否冲突。
- `funct6`、`funct3`、`vm`、`vd`、`vs1`、`vs2` 字段解释。
- objdump/assembler 是否能显示 mnemonic；若不能，记录 `.insn` bring-up
  格式。

### 3.2 寄存器布局

`vfcmacc.vv` 使用 paired register group。每个复数向量由一个 real group 和
紧随其后的 imag group 组成：

```text
vs1.real = vs1_base
vs1.imag = vs1_base + LMUL

vs2.real = vs2_base
vs2.imag = vs2_base + LMUL

vd.real  = vd_base
vd.imag  = vd_base + LMUL
```

当 `LMUL=4` 时，当前 `dp-cdotp` kernel 的布局是：

```asm
vlseg2e64.v v0, (x)   # v0-v3: X.real, v4-v7: X.imag
vlseg2e64.v v8, (y)   # v8-v11: Y.real, v12-v15: Y.imag
v16-v19               # acc.real
v20-v23               # acc.imag
```

v1 默认合法性规则：

- `LMUL` 只接受 `m1`、`m2`、`m4`；`m8` 默认 illegal，除非 Node 1 显式
  证明 scoreboard、VRF 访问和加载路径可控。
- `base % LMUL == 0`，否则 illegal instruction。
- `base + 2 * LMUL - 1 < 32`，否则 illegal instruction。
- `vd` pair 不得与 `vs1` pair 或 `vs2` pair 重叠；v1 用 illegal
  instruction 拒绝，避免多拍 micro-op 写回破坏后续源操作数读取。
- `vs1` pair 与 `vs2` pair 可以相同；必须按普通源操作数读取处理。
- `vd`、`vs1`、`vs2` 均必须满足当前 RVV register group 对齐约束。

Node 1 必须生成一张 `LMUL={1,2,4,8}` 的合法/非法 base table。该表是
decoder 和测试用例的来源，不允许 RTL 与测试各自解释。

### 3.3 数据类型与配置开关

v1 支持顺序：

```text
e32 -> e64 -> e16
```

合法性要求：

- `e32` 需要 RVV + RVF + Spatz FPU。
- `e64` 需要 RVV + RVD + Spatz FPU。
- `e16` 需要 RVV + half-precision FPU support。
- `e8`、integer `vtype`、unsupported alternative FP formats 均为 illegal。

新增 RTL 配置开关必须使用非标准扩展命名，推荐：

```text
RVV_EXT_XVFCOMPLEX
```

不要使用看起来像标准扩展的 `Z*` 名称，除非该扩展已进入标准化流程。该开关应
位于 `hw/ip/spatz/src/spatz_pkg.sv.tpl`，并通过正常生成流程同步到
`hw/ip/spatz/src/generated/spatz_pkg.sv`。

### 3.4 Mask、tail 与 `vstart`

最终 v1 必须与现有 RVV 浮点算术保持一致：

- `vm=1`：所有 active elements 更新 real/imag accumulator。
- `vm=0`：只更新 mask-active elements。
- masked-off elements 遵循当前 Spatz/RVV 写回策略。
- tail elements 遵循当前 `vtype` 的 tail policy。
- `vstart != 0` 必须与现有 VFU 处理方式一致；若无法保证，Node 3 必须把
  `vstart != 0` 定义为 illegal 或明确记录为阻塞项。

早期 `v1a` 可以先只接受 `vm=1`，但必须在 `PHASE_RESULTS.md` 中标为
部分完成，不能合并为 v1 完成。

### 3.5 数值、舍入和异常

v1 定义为与以下四条指令按程序顺序执行 bit-identical：

```asm
vfmacc.vv  acc_r, x_r, y_r
vfnmsac.vv acc_r, x_i, y_i
vfmacc.vv  acc_i, x_r, y_i
vfmacc.vv  acc_i, x_i, y_r
```

bit-identical 的范围包括：

- finite values。
- `+0.0` 与 `-0.0`。
- NaN payload 传播行为，以现有 FPU reference sequence 为准。
- rounding mode。
- `fflags`。

四个内部 FPU operation 的 `fflags` 必须按位 OR：

```text
fflags_final = fflags_rr | fflags_ii | fflags_ri | fflags_ir
```

只在整条 `vfcmacc.vv` 完成时提交一次。

v2 如采用真正 fused complex-FMA datapath，可允许与 v1 不 bit-identical，但
必须在新的 ISA 文档、reference model 和测试阈值中单独定义，不得复用 v1 的
bitwise reference。

## 4. 微架构方案

### 4.1 现有可复用链路

当前分支已有 `vfwdotp`/`VSDOTP` 的非标准 RVV 浮点扩展示例，可作为
`vfcmacc.vv` 的主要参考：

```text
hw/ip/snitch/src/riscv_instr.sv
hw/ip/snitch/src/snitch.sv
hw/ip/spatz/src/spatz_fpu_sequencer.sv
hw/ip/spatz/src/spatz_pkg.sv.tpl
hw/ip/spatz/src/generated/spatz_pkg.sv
hw/ip/spatz/src/spatz_decoder.sv
hw/ip/spatz/src/spatz_vfu.sv
```

已知参考点：

- `riscv_instr::VFWDOTP_VV` 和 `VFWDOTP_VF` 已存在。
- Snitch 在 RVV/RVF 可用时把 `VFWDOTP_VV` offload 到 Spatz。
- Spatz decoder 把 `VFWDOTP_*` 映射到内部 `VSDOTP`。
- `spatz_vfu.sv` 将 `VSDOTP` 送到 `fpnew_pkg::SDOTP`。

`vfcmacc.vv` 应沿用该链路，但不要照搬 `.vf` 支持。

### 4.2 Snitch 前端

Snitch 修改目标：

- 识别 `riscv_instr::VFCMACC_VV`。
- 仅在 `RVV && RVF` 时 offload。
- 不读取整数 source register。
- 不读取 scalar FP source register。
- 在扩展关闭、FPU 不存在或指令非法时保持 illegal instruction 行为。

建议文件：

```text
hw/ip/snitch/src/riscv_instr.sv
hw/ip/snitch/src/snitch.sv
hw/ip/spatz/src/spatz_fpu_sequencer.sv
```

### 4.3 Spatz Decoder

Spatz decoder 修改目标：

- 新增内部 op，例如 `VFCMADD`。
- `vfcmacc.vv` 设置 `spatz_req.op = VFCMADD`。
- 设置 `use_vs1=1`、`use_vs2=1`、`use_vd=1`、`vd_is_src=1`。
- 保留 `vm`、`vtype`、rounding mode 和 FP format mode。
- 在 decoder 或进入 VFU 前完成 paired group 合法性检查。

建议文件：

```text
hw/ip/spatz/src/spatz_pkg.sv.tpl
hw/ip/spatz/src/generated/spatz_pkg.sv
hw/ip/spatz/src/spatz_decoder.sv
```

### 4.4 VFU 多拍执行

v1 推荐内部状态机：

```text
IDLE
MAC_RR   # acc.real += x.real * y.real
MAC_II   # acc.real -= x.imag * y.imag
MAC_RI   # acc.imag += x.real * y.imag
MAC_IR   # acc.imag += x.imag * y.real
DONE
```

关键约束：

- 不增加 VRF 物理读写端口。
- 每拍只发射当前 FPU/VRF 通路可承受的操作。
- `MAC_RR` 和 `MAC_II` 更新 `vd.real` group。
- `MAC_RI` 和 `MAC_IR` 更新 `vd.imag` group。
- sequence 执行期间不得响应外部 interrupt/debug/flush 造成部分架构状态可见。
- 如果前端 kill 发生在第一拍 FPU 写回前，可以取消；一旦有任意 partial
  writeback，必须 drain 到 `DONE` 并只提交一次完成响应，或在 Node 3 明确实现
  shadow accumulator 避免 partial write。
- `fflags` 使用局部寄存器累积，`DONE` 时一次性提交。
- 若现有 VFU 无法干净表达该原子性，Node 3 必须停止并记录 blocker，不能用
  “仿真暂时没出错”代替架构语义。

建议文件：

```text
hw/ip/spatz/src/spatz_vfu.sv
hw/ip/spatz/src/spatz_controller.sv
hw/ip/spatz/src/spatz_vrf.sv
hw/ip/spatz/src/spatz.sv
```

### 4.5 Serialization Fence 与相关冒险

`vfcmacc.vv` 在架构上读写六个隐式 register groups：

```text
read:  vs1.real, vs1.imag, vs2.real, vs2.imag, vd.real, vd.imag
write: vd.real, vd.imag
```

现有 scoreboard request 结构只描述 `vs1`、`vs2` 和 `vd` 三个 group。v1 不扩展
scoreboard/request，而是使用 2.4 中定义的 conservative serialization fence：
发射 `vfcmacc.vv` 前等待旧非 `CON` offload 完成，`VFCMADD` 完成前阻止新的
VFU/VLSU/VSLDU 指令发射。

不得只依赖 real group scoreboard 而移除 serialization fence。该问题必须在
Node 3/5d 的测试中覆盖：

- back-to-back `vfcmacc.vv` 写同一 accumulator pair。
- `vfcmacc.vv` 后紧跟读取 `vd.imag` 的普通 vector 指令。
- 普通 vector 指令写 `vs1.imag` 后紧跟 `vfcmacc.vv`。
- 非法 overlap case 不应进入执行状态。

## 5. 软件、工具链与 benchmark 策略

### 5.1 Bring-up 方式

早期 bring-up 允许使用 `.insn` 或临时 inline assembly wrapper，但必须满足：

- 不手工 patch binary。
- wrapper 固定寄存器布局并写明 clobber。
- benchmark 能在 `make -C hw/system/spatz_cluster sw.vlt` 中构建。

RTL 稳定后再进入正式 mnemonic 支持：

- GNU assembler / riscv-opcodes 支持 `vfcmacc.vv`。
- objdump 能显示预期 mnemonic，或文档记录当前 objdump limitation。
- LLVM TableGen 支持仅作为后续 node，不阻塞 v1 RTL 验收。

### 5.2 LLVM 风险边界

LLVM register allocator 很难自然表达“base + LMUL 隐式 imag group”的多个
寄存器绑定。v1 不要求自动 SelectionDAG 匹配，也不要求 C 代码自动 lowering。

v1 软件接口使用以下保守策略之一：

- 固定寄存器 inline assembly wrapper，并用 clobber list 保护 real/imag pairs。
- 或 TableGen pseudo instruction + 自定义 register class，例如 `VRM2Pair`，
  但该工作单独进入工具链 node。

不得在 RTL v1 尚未稳定前投入完整 LLVM 自动化。工具链 node 的验收目标是
mnemonic 可用，不是自动优化高级 C 代码。

### 5.3 Benchmark 接入

第一目标 benchmark 是 `dp-cdotp`，因为当前 kernel 已经清晰包含四指令复数
MAC reference sequence。

建议文件：

```text
sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c
sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.h
sw/spatzBenchmarks/dp-cdotp/main.c
sw/spatzBenchmarks/CMakeLists.txt
```

benchmark 必须保留 old/new A/B 路径：

```text
old: vfmacc + vfnmsac + vfmacc + vfmacc
new: vfcmacc.vv
```

推荐通过 compile definition 控制：

```text
SPATZ_USE_VFCMACC=0
SPATZ_USE_VFCMACC=1
```

报告至少包含：

- correctness result。
- old cycles。
- new cycles。
- dynamic vector instruction count proxy。
- frontend/offload stall counters，如果当前 runtime 可读。
- TCDM counters 保持记录，但 v1 不以 TCDM 改善作为主要收益。

## 6. 测试与结果标准

### 6.1 Reference 标准

v1 reference 必须是当前四指令序列，而不是 C 语言 `complex` 表达式。C
表达式可能被编译器融合、重排或采用不同中间精度，不能作为 bit-identical
golden。

ISA test 中应提供 helper：

```c
ref_vfcmacc_sequence(acc_r, acc_i, x_r, x_i, y_r, y_i)
```

该 helper 必须用现有 RVV 指令执行 reference sequence，并与 `vfcmacc.vv`
输出做逐 bit 比较。

### 6.2 必测功能矩阵

| 范围 | v1 验收标准 |
| --- | --- |
| Encoding | `riscv_instr::VFCMACC_VV` 存在，bit pattern 无冲突 |
| Snitch decode | RVV/RVF 可用时 offload，禁用时 illegal |
| Spatz decode | 生成 `VFCMADD`，`vd_is_src=1`，保留 `vm/vtype/rm` |
| Register layout | `LMUL=1/2/4` 合法表通过，`m8` 默认 illegal |
| Register bounds | `base + 2*LMUL - 1 >= 32` 必须 illegal |
| Alignment | `base % LMUL != 0` 必须 illegal |
| Overlap | v1 拒绝 `vd` pair 与 source pair 重叠 |
| e32 | unmasked、masked、tail、mixed sign bitwise pass |
| e64 | unmasked、masked、tail、mixed sign bitwise pass |
| e16 | unmasked、masked、tail、mixed sign bitwise pass |
| Zero sign | `+0.0/-0.0` 与 reference sequence bit-identical |
| NaN/Inf | result bits 和 `fflags` 与 reference sequence 一致 |
| FFLAGS | 四个内部 operation 的 flag OR 后一次性提交 |
| Atomicity | back-to-back、kill/flush/debug policy 有 RTL 证据或明确 blocker |
| Scoreboard | real/imag hazard tests 无 deadlock、无 stale read |
| Benchmark | `dp-cdotp` old/new 均通过，输出 cycles 和 instruction proxy |
| Regression | 现有 `vfmacc`、`vfnmsac`、`dp-cdotp`、`dp-cmatmul` 不回归 |

### 6.3 必测非法指令矩阵

必须新增非法指令测试，覆盖：

```text
unsupported extension switch: RVV_EXT_XVFCOMPLEX=0
unsupported SEW: e8 或 integer vtype
unsupported LMUL: m8 under v1 policy
misaligned base: base % LMUL != 0
out-of-range imag group: base + 2*LMUL - 1 >= 32
destination/source pair overlap under v1 policy
reserved vfcmacc.vf encoding if accidentally emitted
```

非法测试标准：

- 指令不得进入 VFU 执行状态。
- 不得修改任何 vector register。
- trap/illegal 行为与现有非法 RVV 指令一致。

### 6.4 结果精度标准

v1 ISA tests：

```text
bitwise equality required
```

v1 benchmark：

```text
old/new path must match the same existing benchmark tolerance
```

若 benchmark 只比较最终 reduction 标量，必须额外保留至少一个 ISA-style test
逐 element 比较 vector accumulator real/imag pair，避免 reduction 掩盖局部错误。

v2 fused datapath 如启动，必须单独定义：

```text
max_abs_error
max_rel_error
ULP threshold
NaN/Inf policy
fflags policy
```

### 6.5 性能结果标准

v1 不以 FPU throughput speedup 作为硬性验收。v1 必须报告：

- inner loop 中复数 MAC 指令数从 4 条降到 1 条。
- old/new cycle count。
- old/new instruction count proxy。
- frontend/offload stall counters，如可用。
- 是否存在额外 micro-op sequencing overhead。

v1 性能判定：

- correctness 是硬门槛。
- instruction count reduction 是硬门槛。
- cycle speedup 是观察项，不是硬门槛。
- 如果 long-running `dp-cdotp` new path 比 old path 慢超过 10%，必须在
  `PHASE_RESULTS.md` 记录原因，并在进入 v2 前决定是优化 sequencer 还是停止。

v2 进入条件：

- v1 已完成 e32/e64/e16、mask、fflags、scoreboard 和 benchmark。
- v1 数据显示 frontend/offload pressure 是主要瓶颈，或专用 datapath 有明确
  cycle/PPA 收益假设。
- v2 reference model 已独立冻结。

## 7. 分阶段实施计划

### Node 0：工作树、基线与文档框架

目标：

- 在隔离工作树中建立可审计工程入口。
- 同步并追踪 `.codexignore`。
- 建立 `PLAN.md`、`PHASE_RESULTS.md`、`GIT_NOTES.md`。

建议命令：

```sh
git status --short --branch
git worktree list --porcelain
make -C hw/system/spatz_cluster help
```

验收标准：

- 当前工作树为 `/home/wxt/spatz-cfma`。
- 当前分支为 `feature/cfma-instruction-extension`。
- `.codexignore` 已复制并被 git 追踪。
- `PHASE_RESULTS.md` 和 `GIT_NOTES.md` 已记录初始状态。
- 未引入 online softmax merge accelerator 相关源码改动。

提交：

```sh
git add .codexignore docs/v1
git commit -m "[cfma] Record complex instruction planning baseline"
```

### Node 1：Register Layout Reference 与 Encoding 决策

目标：

- 生成 `LMUL={1,2,4,8}` 的 register layout 合法表。
- 冻结 v1 legal/illegal policy。
- 决定 `vfcmacc.vv` encoding。

建议新增文件：

```text
docs/v1/register_layout.md
docs/v1/scripts/cfma_register_layout.py
```

脚本输出必须包含：

```text
LMUL
base
real group range
imag group range
alignment result
range result
v1 legality
illegal reason
```

验收标准：

- `LMUL=1/2/4/8` 的所有 base `v0..v31` 都有记录。
- `m8` 默认策略已明确为 illegal 或明确启用并有理由。
- encoding 与现有 `VFWDOTP`、`VFMACC`、`VFNMSAC` 无冲突。
- `PHASE_RESULTS.md` 记录最终 bit pattern 和合法性策略。

验证：

```sh
python3 docs/v1/scripts/cfma_register_layout.py
git diff --check
```

提交：

```sh
git add docs/v1
git commit -m "[cfma] Add complex register layout reference checks"
```

### Node 2：Opcode 生成与 Snitch 识别

目标：

- 让 `riscv_instr::VFCMACC_VV` 成为可引用的指令 pattern。
- Snitch 能在 RVV/RVF 可用时 offload 该指令。

建议修改文件。Node 2 的第一步固定运行 `make update_opcodes`。该命令会按
`sw/toolchain/riscv-opcodes.version` 展开 pinned opcode source；运行成功后确认
实际采用哪种源码布局，并只修改实际存在的那个源文件：

```text
sw/toolchain/riscv-opcodes/opcodes-rvv
sw/toolchain/riscv-opcodes/extensions/rv_v
hw/ip/snitch/src/riscv_instr.sv
hw/ip/snitch/src/snitch.sv
hw/ip/spatz/src/spatz_fpu_sequencer.sv
```

流程：

- 若 opcode source 不存在，运行 `make update_opcodes` 展开 pinned source。
- 若 `make update_opcodes` 因网络、权限或上游仓库失败而无法展开 source，停止
  Node 2，记录为 `阻塞`。
- 修改 opcode source。
- 再次运行 `make update_opcodes` 重新生成 `hw/ip/snitch/src/riscv_instr.sv`。
- 在 Snitch decode 中加入 `VFCMACC_VV`。
- 加入 compile-only inline assembly smoke test，先不要求执行。

验收标准：

- `riscv_instr.sv` 包含 `VFCMACC_VV`。
- `VFCMACC_VV` 来自 opcode source 重新生成，不是只手改 generated file。
- Snitch decode 不请求 integer/scalar FP operands。
- 禁用 RVV/RVF 时该指令 illegal。
- 现有 `VFWDOTP` decode 不变。

验证：

```sh
make update_opcodes
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
git diff --check
```

提交：

```sh
git add sw/toolchain hw/ip/snitch/src hw/ip/spatz/src docs/v1
git commit -m "[cfma] Add vfcmacc opcode pattern"
```

### Node 3：Spatz Decode、配置开关与非法路径

目标：

- 新增 `RVV_EXT_XVFCOMPLEX` 配置开关。
- 新增内部 op `VFCMADD`。
- `vfcmacc.vv` 解码为合法 Spatz VFU request。
- 非法 layout 不进入执行。
- 为 `VFCMADD` 建立 conservative serialization fence，不扩展多 imag group
  scoreboard request。

建议修改文件：

```text
hw/ip/spatz/src/spatz_pkg.sv.tpl
hw/ip/spatz/src/generated/spatz_pkg.sv
hw/ip/spatz/src/spatz_decoder.sv
sw/riscvTests/CMakeLists.txt
sw/riscvTests/isa/rv64uv/vfcmacc_illegal.c
```

验收标准：

- 扩展开关关闭时 `vfcmacc.vv` illegal。
- `base % LMUL != 0` illegal。
- `base + 2*LMUL - 1 >= 32` illegal。
- v1 policy 下 `LMUL=m8` illegal。
- `vd` pair overlap source pair illegal。
- `VFCMADD` 发射前等待旧 VFU/VLSU/VSLDU 指令完成；`VFCMADD` 完成前阻止新的
  VFU/VLSU/VSLDU 指令发射。
- 现有 vector floating-point decode 无回归。

验证：

```sh
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc_illegal --output-on-failure
git diff --check
```

提交：

```sh
git add hw/ip/spatz/src sw/riscvTests docs/v1
git commit -m "[cfma] Decode vfcmacc in Spatz"
```

### Node 4：v1a Unmasked e32 多拍执行

目标：

- 实现 `vfcmacc.vv` 的最小可执行路径。
- 只要求 `e32`、`vm=1`、合法 non-overlap layout。
- 建立 micro-op 状态机和 `fflags` OR 机制。

建议修改文件：

```text
hw/ip/spatz/src/spatz_vfu.sv
hw/ip/spatz/src/spatz_controller.sv
sw/riscvTests/isa/rv64uv/vfcmacc.c
```

验收标准：

- `IDLE -> MAC_RR -> MAC_II -> MAC_RI -> MAC_IR -> DONE` 状态机存在。
- e32 unmasked result bit-identical 于四指令 reference。
- 每条 `vfcmacc.vv` 只完成一次。
- back-to-back same accumulator pair 无 deadlock。
- `fflags` OR 后一次性提交。
- `PHASE_RESULTS.md` 明确标记该阶段是 `v1a`，不是完整 v1。

验证：

```sh
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc --output-on-failure
cd hw/system/spatz_cluster/sw/build && ctest -R "vfmacc|vfnmsac" --output-on-failure
git diff --check
```

提交：

```sh
git add hw/ip/spatz/src sw/riscvTests docs/v1
git commit -m "[cfma] Add vfcmacc e32 micro-op execution"
```

### Node 5a：e64/e16 Format 支持

目标：

- 在 v1a e32 基础上补齐 e64 和 e16。
- 保持每种 SEW 都 bit-identical 于四指令 reference sequence。

建议修改文件：

```text
hw/ip/spatz/src/spatz_vfu.sv
sw/riscvTests/isa/rv64uv/vfcmacc.c
docs/v1/PHASE_RESULTS.md
```

验收标准：

- e32/e64/e16 unmasked case 均 bit-identical。
- e8、integer vtype 和 unsupported alternative FP formats illegal。
- e64 只在 RVD/FPU 可用时合法；e16 只在 half-precision FPU support 可用时合法。
- e32 v1a 测试无回归。

验证：

```sh
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc --output-on-failure
git diff --check
```

提交：

```sh
git add hw/ip/spatz/src sw/riscvTests docs/v1
git commit -m "[cfma] Add vfcmacc e64 and e16 behavior"
```

### Node 5b：Mask、Tail 与 vstart 行为

目标：

- 补齐 `vm=0` mask 行为。
- 确认 tail policy 与当前 Spatz/RVV 浮点算术一致。
- 冻结 `vstart != 0` 行为。

建议修改文件：

```text
hw/ip/spatz/src/spatz_vfu.sv
hw/ip/spatz/src/spatz_decoder.sv
sw/riscvTests/isa/rv64uv/vfcmacc.c
docs/v1/PHASE_RESULTS.md
```

验收标准：

- masked case 只更新 mask-active complex elements。
- masked-off elements 与现有 Spatz/RVV 浮点写回策略一致。
- tail elements 与当前 `vtype` tail policy 一致。
- 若现有 VFU 无法保证 `vstart != 0` 的四拍复数语义，decoder 必须把
  `VFCMADD` with `vstart != 0` 定义为 illegal，并在 `PHASE_RESULTS.md` 记录。

验证：

```sh
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc --output-on-failure
git diff --check
```

提交：

```sh
git add hw/ip/spatz/src sw/riscvTests docs/v1
git commit -m "[cfma] Cover vfcmacc mask and tail behavior"
```

### Node 5c：特殊数值、Rounding 与 FFLAGS

目标：

- 覆盖 `+0.0/-0.0`、NaN、Inf、rounding mode 和 `fflags`。
- 证明 `fflags_final = fflags_rr | fflags_ii | fflags_ri | fflags_ir` 只提交一次。

建议修改文件：

```text
hw/ip/spatz/src/spatz_vfu.sv
sw/riscvTests/isa/rv64uv/vfcmacc.c
docs/v1/PHASE_RESULTS.md
```

验收标准：

- `+0.0/-0.0` result bits 与 reference sequence bit-identical。
- NaN payload、Inf 和 invalid/overflow/underflow/inexact/div-by-zero flags 与 reference
  sequence 一致。
- 不因四个内部 FPU operation 产生四次 architectural `fflags` 提交。
- 现有 `vfmacc`、`vfnmsac`、`vfwdotp` 测试无回归。

验证：

```sh
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc --output-on-failure
cd hw/system/spatz_cluster/sw/build && ctest -R "vfmacc|vfnmsac|vfwdotp" --output-on-failure
git diff --check
```

提交：

```sh
git add hw/ip/spatz/src sw/riscvTests docs/v1
git commit -m "[cfma] Cover vfcmacc numerical corner cases"
```

### Node 5d：Serialization Fence 与 Hazard Regression

目标：

- 验证 v1 conservative serialization fence 覆盖隐式 imag group hazards。
- 完成 v1 ISA 行为验收。

建议修改文件：

```text
hw/ip/spatz/src/spatz_controller.sv
hw/ip/spatz/src/spatz_vfu.sv
sw/riscvTests/isa/rv64uv/vfcmacc.c
docs/v1/PHASE_RESULTS.md
```

验收标准：

- `vfcmacc.vv` 后紧跟读取 `vd.real/vd.imag` 的普通 vector 指令无 stale read。
- 普通 vector 指令写 `vs1.imag` 或 `vs2.imag` 后紧跟 `vfcmacc.vv` 无 stale read。
- back-to-back `vfcmacc.vv` 写同一 accumulator pair 无 deadlock、无错序完成。
- 非法 overlap case 不进入执行状态。
- `PHASE_RESULTS.md` 标记完整 v1 ISA 行为完成，不能再标为 v1a。

验证：

```sh
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build && ctest -R vfcmacc --output-on-failure
cd hw/system/spatz_cluster/sw/build && ctest -R "vfmacc|vfnmsac|vfwdotp" --output-on-failure
git diff --check
```

提交：

```sh
git add hw/ip/spatz/src sw/riscvTests docs/v1
git commit -m "[cfma] Complete vfcmacc ISA behavior"
```

### Node 6：Mnemonic 与工具链整理

目标：

- 把临时 `.insn` 或固定编码 wrapper 替换为正式 mnemonic。
- 明确 assembler、objdump 和 LLVM 支持边界。

建议修改文件。Node 7 开始前必须先确认 pinned toolchain 已展开，并只修改实际
存在的路径：

```text
sw/toolchain/riscv-opcodes/opcodes-rvv
sw/toolchain/riscv-opcodes/extensions/rv_v
sw/toolchain/riscv-gnu-toolchain/riscv-binutils/include/opcode/riscv-opc.h
sw/toolchain/riscv-gnu-toolchain/riscv-binutils/opcodes/riscv-opc.c
sw/toolchain/llvm-project/llvm/lib/Target/RISCV/RISCVInstrInfoV.td
sw/toolchain/llvm-project/llvm/lib/Target/RISCV/RISCVInstrInfoVPseudos.td
sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c
docs/v1/PHASE_RESULTS.md
```

验收标准：

- inline asm 可写 `vfcmacc.vv` mnemonic。
- benchmark 不需要 binary patch。
- objdump 能显示 `vfcmacc.vv`；若当前工具链不支持，必须记录原因和补救路径。
- LLVM 自动 SelectionDAG lowering 仍不是本 node 的必做项。

验证：

```sh
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build && ctest -R "vfcmacc|dp-cdotp" --output-on-failure
git diff --check
```

提交：

```sh
git add sw/toolchain sw/spatzBenchmarks docs/v1
git commit -m "[cfma] Add vfcmacc mnemonic support"
```

### Node 7：v2 Datapath 评审门

目标：

- 基于 v1 真实数据决定是否启动专用 complex-FMA datapath。

必须输入：

- v1 ISA tests 全部通过。
- `dp-cdotp` A/B 性能报告。
- frontend/offload stall 或 instruction pressure 证据。
- `fflags`、rounding 和 NaN/Inf 现状总结。

v2 决策项：

- 是否允许非 bit-identical fused result。
- 是否扩展 fpnew，还是在 Spatz VFU 内新增本地 block。
- 是否继续支持 e16/e32/e64。
- 是否加入 `vfcjmacc.vv`。
- 预期 latency、throughput、面积和时序风险。

验收标准：

- v2 只有在评审记录完成后才能动 RTL。
- 若收益不足，明确停止在 v1，不做专用 datapath。

提交：

```sh
git add docs/v1
git commit -m "[cfma] Record complex datapath v2 decision"
```

## 8. 风险清单

| 风险 | 处理方式 |
| --- | --- |
| 隐式 imag group 越界 | Node 1 表格冻结规则，Node 3 illegal tests 覆盖 |
| LLVM 难以分配 paired registers | v1 使用 inline asm wrapper；LLVM pseudo 单独 node |
| micro-op partial write 破坏精准状态 | Node 4 使用 serialization fence 保护；若 kill/flush/debug 会暴露中间状态则阻塞 |
| `fflags` 多次提交 | 局部 OR 累积，只在 DONE 提交 |
| v1 无 FPU 吞吐收益 | 性能目标改为 frontend/offload pressure，cycle speedup 只报告 |
| mask/tail 被 v1a 遗漏 | v1a 只可标部分完成，Node 5b 后才可声称 mask/tail 完成 |
| 隐式 imag group hazard | Node 3 建立 serialization fence，Node 5d 必测 imag hazards |
| opcode 源路径缺失 | Node 2 使用 `make update_opcodes` 展开 pinned source，长期不手改生成文件 |
| v2 fused result 不同 | v2 单独 reference model，不复用 v1 bitwise 标准 |

## 9. 当前推荐首版范围

首版只做以下内容：

```text
vfcmacc.vv only
LMUL=m1/m2/m4 only
paired register group only
non-overlapping destination/source pairs only
e32 -> e64 -> e16
v1a unmasked e32 first
v1 final includes mask/tail/fflags/hazard tests
inline asm bring-up first
dp-cdotp proof first
```

该范围能最小化 RTL 风险，同时形成完整 ISA、decoder、VFU、software、
benchmark 和记录闭环。任何超出该范围的优化都必须在独立 node 中重新评审。
