# Spatz 复数指令扩展工程规划

## 1. 背景与目标

当前复数 kernel 已经在仓库中存在，例如 `dp-cdotp`、`dp-caxpy`、
`dp-cmatmul` 和 FFT。它们通常使用 `vlseg2e*.v` 加载复数向量，
再用多条实数向量 FMA 指令完成复数运算。

以当前复数点积为例，一次复数乘加需要四条指令：

```asm
vfmacc.vv  v16, v0, v8     # acc.real += x.real * y.real
vfnmsac.vv v16, v4, v12    # acc.real -= x.imag * y.imag
vfmacc.vv  v20, v0, v12    # acc.imag += x.real * y.imag
vfmacc.vv  v20, v4, v8     # acc.imag += x.imag * y.real
```

本工作的目标是新增一条 Spatz-specific 复数浮点向量指令，将上述
四条指令在软件可见层面折叠成一条架构指令，从而降低指令数、
前端发射压力和复数 kernel 的调度复杂度。

推荐第一条指令命名为：

```asm
vfcmacc.vv vd, vs1, vs2
```

其语义为：

```c
vd.real += vs1.real * vs2.real - vs1.imag * vs2.imag;
vd.imag += vs1.real * vs2.imag + vs1.imag * vs2.real;
```

## 2. v1 默认边界

第一版建议采用低风险实现路径，目标是先获得正确、可测试、可量化的
完整闭环。

默认设计选择：

- v1 只实现 vector-vector 形式：`vfcmacc.vv`。
- v1 沿用当前 Spatz 向量浮点 offload 路径。
- v1 沿用当前复数 benchmark 的 segmented register layout。
- v1 内部可以用多拍 micro-op 复用现有 FPU 数据通路。
- v1 不强依赖完整 LLVM 指令选择支持；早期可用 `.insn` bring-up。
- v1 验收前应支持 masked case；早期 v1a 可以先只支持 `vm=1`。
- v2 再评估 `vfcmacc.vf`、conjugate 变体和专用复数 datapath。

不建议第一版直接追求单周期或完全融合的复数 FMA 数据通路。先用
既有 FPU 跑通语义，可以显著降低 RTL、scoreboard、异常标志和
数值舍入风险。

## 3. 指令语义

### 3.1 寄存器布局

`vfcmacc.vv` 使用当前复数 kernel 已经采用的分段布局。实部和虚部
不通过额外字段编码，而是由 base register 和 LMUL 推导。

```text
vs1_base         = vs1.real
vs1_base + LMUL  = vs1.imag

vs2_base         = vs2.real
vs2_base + LMUL  = vs2.imag

vd_base          = acc.real
vd_base + LMUL   = acc.imag
```

这与当前 `vlseg2e*.v` 的使用方式一致：

```asm
vlseg2e64.v v0, (x)   # LMUL=4 时，v0-v3 为 real，v4-v7 为 imag
vlseg2e64.v v8, (y)   # LMUL=4 时，v8-v11 为 real，v12-v15 为 imag
```

v1 建议强制 paired register group 约束，不支持任意 real/imag
寄存器组合。这样可以避免修改指令格式，也可以减少 decoder 接口扩展。

### 3.2 支持的数据类型

v1 应覆盖现有复数 benchmark 使用的浮点 element width：

```text
e16: half precision complex MAC
e32: single precision complex MAC
e64: double precision complex MAC
```

实现时可按以下顺序 bring-up：

```text
e32 -> e64 -> e16
```

如果当前配置不支持对应 FPU 格式，或 `vtype.vsew` 不合法，应将该
指令视为 illegal instruction。

### 3.3 Mask 与 Tail 语义

最终 v1 应保持与 RVV 浮点算术一致的行为：

- `vm=1`：所有 active element 参与计算。
- `vm=0`：只有 mask-active element 更新实部和虚部 accumulator。
- masked-off element 遵循当前 Spatz/RVV 的写回策略。
- tail element 遵循当前 `vtype` 中的 tail policy。

早期原型可以先只接受 `vm=1`，但最终 v1 验收必须包含 masked
测试，否则复数指令会与现有 RVV 编程模型不一致。

### 3.4 数值语义

v1 推荐定义为等价于当前四条指令按程序顺序执行：

```asm
vfmacc.vv  acc_r, x_r, y_r
vfnmsac.vv acc_r, x_i, y_i
vfmacc.vv  acc_i, x_r, y_i
vfmacc.vv  acc_i, x_i, y_r
```

这个定义有两个好处：

- 可以直接用现有 kernel 作为 reference model。
- 可以避免 v1 因完全融合 FMA 产生不同舍入结果而难以验证。

如果 v2 引入专用复数 FMA datapath，并采用不同融合或舍入模型，
必须在 ISA 文档和测试 reference 中明确说明。

## 4. 候选指令集与优先级

`vfcmacc.vv` 是第一优先级，但它不是唯一有价值的复数指令。下面列出
建议纳入规划评审的候选指令。v1 不应一次性实现全部指令，但需要提前
保留 encoding、命名和语义空间，避免后续扩展互相冲突。

### 4.1 普通复数乘加：`vfcmacc.vv`

优先级：最高，作为 v1 主线。

语义：

```c
acc.real += x.real * y.real - x.imag * y.imag;
acc.imag += x.real * y.imag + x.imag * y.real;
```

适用场景：

- 复数点积。
- 复数矩阵乘。
- 频域逐点乘加。
- 复数 FIR/IIR 类 kernel。

实现理由：

- 能直接替换当前四条 `vfmacc/vfnmsac` 序列。
- 与现有 `dp-cdotp`、`dp-cmatmul` benchmark 对应关系最清楚。
- 可用现有四指令实现作为 reference model。

v1 应只把这条指令作为必须完成项。

### 4.2 共轭复数乘加：`vfconjmac.vv`

优先级：高，建议作为 v1 之后的第一条扩展。

语义：

```c
acc.real += x.real * y.real + x.imag * y.imag;
acc.imag += x.real * y.imag - x.imag * y.real;
```

该语义对应：

```c
acc += conj(x) * y;
```

适用场景：

- 复数内积。
- 相关运算。
- 通信中的 I/Q 信号处理。
- FFT 和频域算法中的共轭对称计算。

实现理由：

- 很多复数点积实际需要 conjugate form。
- 与 `vfcmacc.vv` 使用相同寄存器布局和 operand 数量。
- 内部 micro-op 只需要改变符号组合，硬件增量相对可控。

风险：

- 需要在 ISA 文档中明确共轭的是 `vs1` 还是 `vs2`。
- 如果后续支持多个 conjugate 变体，命名必须保持一致。

推荐约定：

```text
vfconjmac.vv vd, vs1, vs2  # acc += conj(vs1) * vs2
```

### 4.3 复数乘法：`vfcmul.vv`

优先级：中高，建议作为第二阶段扩展。

语义：

```c
dst.real = x.real * y.real - x.imag * y.imag;
dst.imag = x.real * y.imag + x.imag * y.real;
```

适用场景：

- FFT butterfly 中的 twiddle multiply。
- 频域滤波。
- 复数逐点乘。
- 不需要 accumulator 的复数变换。

实现理由：

- 与 `vfcmacc.vv` 共享大部分 operand 读取和计算逻辑。
- 区别在于 `vd` 不作为 accumulator source。
- 可作为 `vfcmacc.vv` 跑通后的自然扩展。

风险：

- 需要确认目的寄存器 real/imag group 的写回和 scoreboard 行为。
- 如果 v1 micro-op 依赖 `vd_is_src`，需要为 non-accumulate 路径补旁路。

### 4.4 复数标量乘加：`vfcmacc.vf`

优先级：中，价值高但编码和 operand 供给更复杂。

语义：

```c
acc += complex_scalar * complex_vector;
```

展开为：

```c
acc.real += a.real * x.real - a.imag * x.imag;
acc.imag += a.real * x.imag + a.imag * x.real;
```

适用场景：

- 复数 AXPY：`y = a * x + y`。
- 标量 broadcast 系数的复数矩阵或卷积 kernel。
- FFT 中部分 twiddle 重用场景。

实现价值：

- 当前 `dp-caxpy` 也需要四条向量浮点乘加。
- 对复数标量系数频繁复用的 kernel，能减少指令数和调度压力。

主要风险：

- 标准 RVV `.vf` 形式通常只携带一个 FP scalar operand。
- 复数 scalar 需要 `a.real` 和 `a.imag` 两个标量值。
- 需要决定 scalar 复数布局，例如相邻 FP register 或 packed scalar。
- Snitch scalar FP operand 读取和 Spatz request 字段可能需要扩展。

因此不建议放入 v1 主线。可以在 `vfcmacc.vv` 稳定后单独评审。

### 4.5 FFT Butterfly 指令

优先级：后期评估，高收益但高侵入。

典型语义：

```c
t = w * b;
u = a + t;
v = a - t;
```

适用场景：

- FFT radix-2 butterfly。
- 固定形态的频域 transform kernel。

潜在收益：

- 一条指令覆盖 twiddle multiply、add 和 sub。
- 可能显著降低 FFT kernel 的指令数和中间寄存器压力。

主要风险：

- 需要更多源和目的寄存器组。
- VRF 读写端口压力明显高于 `vfcmacc.vv`。
- scoreboard、写回和异常处理更复杂。
- 指令语义更接近专用 kernel acceleration，通用性低于复数 MAC。

除非项目目标明确聚焦 FFT，否则不建议在早期实现。

### 4.6 复数旋转和乘以 j

优先级：低到中，低成本辅助指令。

典型语义：

```c
dst.real = -x.imag;
dst.imag =  x.real;
```

也就是：

```c
dst = j * x;
```

适用场景：

- FFT 中特殊 twiddle 值。
- I/Q 数据处理。
- 复数符号变换和象限旋转。

实现特点：

- 不需要 FPU 乘法。
- 主要是 swap 和 sign flip。
- 单条收益依赖 workload，通用优先级低于复数 MAC 和复数乘法。

### 4.7 推荐扩展顺序

建议按以下顺序推进：

```text
1. vfcmacc.vv      普通复数乘加，v1 主线
2. vfconjmac.vv    共轭复数乘加，复数内积和通信常用
3. vfcmul.vv       复数乘法，适合 FFT 和频域逐点乘
4. vfcmacc.vf      复数标量乘加，适合 caxpy，但编码更复杂
5. FFT butterfly   高收益但高侵入，后期专项评估
6. vfcjmul/vfcrot  低成本旋转或乘以 j，按 workload 决定
```

如果需要定义一套最小复数扩展指令集，建议先收敛到三条：

```text
vfcmacc.vv
vfconjmac.vv
vfcmul.vv
```

这三条共享同一套 real/imag paired register group 规则，容易形成一致
的 decoder、scoreboard、benchmark 和测试框架。

## 5. Encoding 策略

### 5.1 推荐路径

仓库中已有 `vfwdotp` / `VSDOTP` 作为非标准向量浮点扩展样例。
复数指令建议沿用同一条链路：

- 在 `sw/toolchain/riscv-opcodes/opcodes-rvv` 中新增 encoding。
- 运行 `make update_opcodes` 生成 `riscv_instr.sv`。
- 在 Snitch 和 Spatz decoder 中使用生成的 `riscv_instr::VFCMACC_VV`。
- RTL 原型稳定后，再补 LLVM TableGen mnemonic 支持。

候选 mnemonic：

```text
vfcmacc.vv
```

后续可能扩展：

```text
vfcmacc.vf     # 复数标量系数乘以复数向量
vfconjmac.vv   # 可选 conjugate 形式
vfcnmacc.vv    # 可选 negated 或 conjugate-negated 形式
```

### 5.2 Encoding 决策检查项

正式选定 bit pattern 前，应完成以下检查：

- 检查 `opcodes-rvv` 中所有 `31..26` function value，避免冲突。
- 检查已有项目扩展，尤其是 `vfwdotp`。
- 决定使用 RVV OPFVV custom slot，还是单独 custom opcode。
- 确认 encoding 能被 `riscv-opcodes` 表达并生成 SystemVerilog。
- 确认 Snitch decode 能无歧义识别该指令。

Node 0 完成前，应把最终选择的 encoding 追加记录到本文档。

## 6. 涉及组件与修改点

### 6.1 Opcode 生成

涉及文件：

```text
sw/toolchain/riscv-opcodes/opcodes-rvv
Makefile
hw/ip/snitch/src/riscv_instr.sv
```

任务：

- 新增 `vfcmacc.vv` encoding。
- 运行 `make update_opcodes`。
- 检查生成的 `riscv_instr::VFCMACC_VV` pattern。

验收标准：

- `riscv_instr.sv` 包含新指令 localparam。
- 除新增 pattern 外，现有生成内容没有非预期变化。

### 6.2 Snitch 前端译码

涉及文件：

```text
hw/ip/snitch/src/snitch.sv
hw/ip/spatz/src/spatz_fpu_sequencer.sv
```

任务：

- 将 `VFCMACC_VV` 加入向量浮点 offload case。
- 仅在 RVV 和所需浮点扩展可用时视为合法。
- `.vv` 形式不应请求整数或标量 FP 源操作数。
- 如果后续增加 `.vf`，需要正确标记 scalar FP source register。

验收标准：

- Snitch 将 `vfcmacc.vv` 送往 Spatz，而不是报 illegal。
- 无 FPU 或无 RVV 配置下，非法指令行为保持清晰。
- 现有向量浮点指令 decode 行为不变。

### 6.3 Spatz 内部 op 定义

涉及文件：

```text
hw/ip/spatz/src/spatz_pkg.sv.tpl
hw/ip/spatz/src/generated/spatz_pkg.sv
```

任务：

- 新增内部 operation，例如 `VFCMADD`。
- 保证该 op 落在 `spatz_vfu.sv` 识别的 FPU operation 范围中。
- 优先修改模板，再通过正常生成流程更新 generated 文件。

验收标准：

- decoder 和 VFU 均能引用新 op。
- 模板和 generated package 内容一致。

### 6.4 Spatz Decoder

涉及文件：

```text
hw/ip/spatz/src/spatz_decoder.sv
```

任务：

- 将 `riscv_instr::VFCMACC_VV` 加入 vector floating-point 列表。
- 使用现有 OPFVV 字段解析路径。
- 设置 `spatz_req.op = VFCMADD`。
- 设置 `spatz_req.vd_is_src = 1'b1`。
- 正确标记 `use_vs1`、`use_vs2` 和 `use_vd`。
- 明确如何推导 imag register group。

关键问题：

当前 `spatz_req_t` 只描述一个 `vs1`、一个 `vs2` 和一个 `vd`。
复数 MAC 逻辑上需要：

```text
vs1.real, vs1.imag
vs2.real, vs2.imag
vd.real,  vd.imag
```

v1 建议不扩展指令格式，而是在 RTL 内部按 `base + LMUL` 推导虚部
寄存器组。若需要支持任意 real/imag 寄存器组合，则必须扩展
`spatz_req_t`，并重新审视 scoreboard 和 VRF 端口。

验收标准：

- decoder 能为 `vfcmacc.vv` 生成合法 VFU request。
- 非法 register group 组合会被拒绝。
- 现有向量浮点 decode 不受影响。

### 6.5 VFU 调度与 VRF 读写

涉及文件：

```text
hw/ip/spatz/src/spatz_vfu.sv
hw/ip/spatz/src/spatz.sv
hw/ip/spatz/src/spatz_controller.sv
hw/ip/spatz/src/spatz_vrf.sv
```

任务：

- 将 `VFCMADD` 纳入 FPU 指令集合。
- 设计如何读取 real/imag operand group。
- 设计如何读取和写回 real/imag accumulator group。
- 保证 scoreboard 覆盖两个 destination group。

核心风险：

现有 VFU 路径主要围绕一个 `vs1`、一个 `vs2` 和一个 `vd` source。
复数 MAC 需要更多逻辑操作数。如果直接增加并行 VRF 读端口，风险和
面积都会上升。v1 更稳妥的方式是把一条架构指令拆成短 micro-op
序列，多拍复用现有 VRF 读写路径。

验收标准：

- 不引入新的 VRF 端口冲突。
- scoreboard 能阻止 real/imag destination group 的数据相关冒险。
- 整条复数指令只产生一次架构完成响应。
- 现有 VFU 指令回归仍然通过。

### 6.6 FPU 数据通路

涉及文件：

```text
hw/ip/spatz/src/spatz_vfu.sv
```

v1 推荐实现：

```text
acc.real = fma(x.real, y.real, acc.real)
acc.real = fnmsac_equivalent(x.imag, y.imag, acc.real)
acc.imag = fma(x.real, y.imag, acc.imag)
acc.imag = fma(x.imag, y.real, acc.imag)
```

该方式复用现有 FPU pipeline，数值行为接近当前四条指令序列。

v2 可选实现：

新增专用 complex-FMA datapath，同时接收实部和虚部操作数，并同时
产生实部和虚部结果。这样可以提高吞吐或降低延迟，但需要重新处理：

- 舍入语义。
- 浮点异常标志合并。
- pipeline latency。
- fpnew 集成方式。
- 面积和时序影响。

v1 验收标准：

- 结果与当前四条指令 reference 一致。
- e32、e64、e16 按支持顺序逐步通过。
- FPU status 和 exception 行为被保留或明确记录。

v2 验收标准：

- 数据通路时序符合配置的 FPU latency 模型，或配置 schema 已扩展。
- 舍入和异常语义有明确文档。
- 面积、周期和吞吐收益已经与 v1 对比。

### 6.7 软件工具链

涉及文件：

```text
sw/toolchain/llvm-project/llvm/lib/Target/RISCV/RISCVInstrInfoV.td
sw/toolchain/llvm-project/llvm/lib/Target/RISCV/RISCVInstrInfoVPseudos.td
sw/toolchain/riscv-isa-sim/riscv/encoding.h
sw/toolchain/riscv-isa-sim/riscv/opcodes.h
```

任务：

- 早期 bring-up 可使用 `.insn` 或生成的 assembler 支持。
- RTL 稳定后，在 LLVM TableGen 中加入 `vfcmacc.vv` mnemonic。
- 如果 Spike 流程需要运行该指令，应补 decode 和执行模型。
- 如果 Spike 不支持，应在测试流中明确标记 RTL-only。

验收标准：

- benchmark 能发出 `vfcmacc.vv` 或等价 `.insn`。
- 不需要手工 patch binary。
- 可选 objdump 支持能显示期望 mnemonic。

### 6.8 Benchmark 与测试

涉及文件：

```text
sw/spatzBenchmarks/dp-cdotp/kernel/cdotp.c
sw/spatzBenchmarks/dp-caxpy/kernel/caxpy.c
sw/spatzBenchmarks/dp-cmatmul/kernel/dp-cmatmul.c
sw/spatzBenchmarks/sp-fft/kernel/fft.c
sw/spatzBenchmarks/dp-fft/kernel/fft.c
sw/riscvTests/CMakeLists.txt
sw/riscvTests/isa/rv64uv/
```

测试策略：

- 新增最小 ISA-style `vfcmacc.vv` 测试。
- 分别覆盖 unmasked 和 masked case。
- 覆盖 e32、e64、e16。
- 覆盖 zero、negative zero、小有限值和 mixed sign。
- 添加 benchmark A/B 路径，对比旧四指令实现和新指令实现。

验收标准：

- Verilator 上新 ISA 测试通过。
- 至少 `dp-cdotp` 同时具备 old/new 两条路径。
- 新路径结果匹配选定数值语义下的 reference。
- benchmark 输出 instruction count 和 cycle 对比。

## 7. 阶段计划

### Node 0：基线与 encoding 决策

目标：

- 记录当前分支、dirty files 和构建入口状态。
- 选定并记录最终 `vfcmacc.vv` encoding。
- 冻结 v1 范围：只做 `.vv`，还是同时做 `.vf`。

建议命令：

```sh
git status --short --branch
make -C hw/system/spatz_cluster help
```

验收标准：

- 工作区状态已记录。
- encoding 已写入本文档。
- v1 scope 已明确。

### Node 1：Opcode 生成与前端识别

目标：

- 生成 `riscv_instr::VFCMACC_VV`。
- Snitch 能识别并 offload 该指令。
- 添加一个 compile-only inline assembly smoke test。

验收标准：

- `make update_opcodes` 成功。
- Snitch RTL 编译能通过新增 decode 引用。
- 软件文件能 emit 该指令或等价 `.insn`。

### Node 2：Decoder 与内部 op

目标：

- 新增 `VFCMADD` 内部 operation。
- `vfcmacc.vv` 能被解码为 Spatz VFU request。
- 非法 register group 和不支持的 element width 被拒绝。

验收标准：

- decoder 相关编译或仿真通过。
- 现有向量浮点指令 decode 无回归。

### Node 3：v1 多拍执行

目标：

- 用现有 FPU path 实现 `VFCMADD` micro-op 序列。
- 正确读写 real/imag register group。
- 两个 accumulator group 更新完成后，再完成整条架构指令。

验收标准：

- 最小 unmasked e32 测试通过。
- 现有 VFU 测试仍通过。
- 不出现 scoreboard deadlock。

### Node 4：ISA 测试与复数 benchmark

目标：

- 添加 ISA-style 测试。
- 为 `dp-cdotp` 和一个矩阵或 AXPY kernel 添加 A/B 路径。
- 收集 instruction count 和 cycle 数据。

验收标准：

- 从 `sw/build` 运行 `ctest -R vfcmacc` 通过。
- `ctest -R dp-cdotp` 在 old/new 路径下均通过。
- benchmark 输出正确性和性能对比。

### Node 5：工具链 mnemonic 支持

目标：

- 在 LLVM TableGen 中加入 `vfcmacc.vv`。
- 将临时 `.insn` 替换为正式 mnemonic。
- 文档化 assembler/compiler 版本要求。

验收标准：

- benchmark 可以使用 `asm volatile("vfcmacc.vv ...")` 构建。
- 不需要 binary patch。
- objdump 支持时能显示预期 mnemonic。

### Node 6：v2 专用 datapath 评估

目标：

- 根据 v1 性能数据判断是否值得做专用 complex-FMA datapath。
- 评估新增 pipeline、异常标志、latency 配置和面积影响。
- 决定扩展 fpnew，还是在 Spatz VFU 内新增本地复数 FMA block。

验收标准：

- v1 已有完整性能数据。
- v2 开始 RTL 前已有面积、时序和收益评估说明。
- v2 舍入语义已达成一致。

## 8. 验证矩阵

| 范围 | 必要证据 |
| --- | --- |
| Opcode 生成 | `riscv_instr.sv` 包含 `VFCMACC_VV` |
| Snitch decode | RVV/RVF 可用时指令被 offload 到 Spatz |
| Spatz decode | decoder 生成 `VFCMADD` 且设置 `vd_is_src` |
| VFU 执行 | unmasked e32/e64 测试匹配 reference |
| Mask 行为 | masked 测试只更新 active 复数 element |
| 寄存器冒险 | overlapping 和 adjacent group 测试通过 |
| Benchmark | `dp-cdotp` A/B 正确性和 cycle 对比 |
| 回归 | 现有 vector floating-point 测试仍通过 |

## 9. 待决问题

- v1 是否只做 `vfcmacc.vv`，还是同步做 `vfcmacc.vf`？
- 是否需要 conjugate 形式，例如 `acc += conj(x) * y`？
- 是否强制 real/imag 采用 `base + LMUL` paired group？
- v2 是否必须 bit-identical 于当前四指令序列？
- 四个内部浮点操作产生的 exception flag 应如何合并和暴露？
- 是否需要为复数指令新增配置开关，便于不同 cluster 配置裁剪？

## 10. 推荐首版实施范围

推荐首版范围如下：

```text
只实现 vfcmacc.vv
先做 unmasked，v1 验收前补 masked
先做 e32，再做 e64，最后做 e16
只支持 paired register group
内部多拍复用现有 FPU 操作
先用 dp-cdotp 做 benchmark proof
```

这个范围能最快得到正确的端到端原型，同时保留后续专用 datapath 的
优化空间。
