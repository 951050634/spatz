# FPnew Package Structure and FPU Architecture

本文档记录 Spatz 中 fpnew 包的结构、FPU 架构和相关接口定义，作为实现 Complex FMA 硬件单元的基础参考。

**文档创建日期**: 2026-06-13  
**相关实施步骤**: 步骤 1 - 定位 FPU 相关基础设施

---

## 1. fpnew 包的位置

### 1.1 源代码位置

fpnew 作为外部依赖通过 Bender 包管理器引入：

```
.bender/git/checkouts/fpnew-d958174726140127/
├── src/
│   ├── fpnew_pkg.sv              # 核心包定义
│   ├── fpnew_fma.sv              # FMA 单元实现
│   ├── fpnew_fma_multi.sv        # Multi-format FMA
│   ├── fpnew_top.sv              # FPU 顶层模块
│   ├── fpnew_cast_multi.sv       # 类型转换
│   ├── fpnew_divsqrt_multi.sv    # 除法/平方根
│   ├── fpnew_sdotp_multi.sv      # SDOTP 运算
│   ├── fpnew_noncomp.sv          # 非计算类操作
│   └── ...
```

### 1.2 在 Spatz 中的使用

fpnew 在 Spatz VFU 中通过以下方式引入：

**文件**: `hw/ip/spatz/src/spatz_vfu.sv`

```systemverilog
module spatz_vfu
  import spatz_pkg::*;
  import rvv_pkg::*;
  import cf_math_pkg::idx_width;
  import fpnew_pkg::*; #(
    /// FPU configuration.
    parameter fpu_implementation_t FPUImplementation = fpu_implementation_t'(0)
  ) (
    // ...
  );
```

---

## 2. fpnew_pkg 中的关键定义

### 2.1 操作码枚举 (operation_e)

**文件**: `.bender/git/checkouts/fpnew-d958174726140127/src/fpnew_pkg.sv`  
**位置**: 第 125-131 行

```systemverilog
typedef enum logic [OP_BITS-1:0] {
  FMADD, FNMSUB, ADD, MUL,     // ADDMUL operation group
  DIV, SQRT,                   // DIVSQRT operation group
  SGNJ, MINMAX, CMP, CLASSIFY, // NONCOMP operation group
  F2F, F2I, I2F, CPKAB, CPKCD, // CONV operation group
  SDOTP, EXVSUM, VSUM          // DOTP operation group
} operation_e;
```

**已有操作码列表**:
- `FMADD` - Fused Multiply-Add (a*b + c)
- `FNMSUB` - Fused Negative Multiply-Subtract
- `ADD` - 加法
- `MUL` - 乘法
- `DIV` - 除法
- `SQRT` - 平方根
- `SGNJ` - Sign injection
- `MINMAX` - 最小/最大值
- `CMP` - 比较
- `CLASSIFY` - 分类
- `F2F` - 浮点格式转换
- `F2I` - 浮点到整数转换
- `I2F` - 整数到浮点转换
- `CPKAB`, `CPKCD` - Cast-and-pack
- `SDOTP` - Sum of dot products
- `EXVSUM` - Extended vector sum
- `VSUM` - Vector sum

**注意**: 当前 `OP_BITS = 5`，支持最多 32 种操作。

### 2.2 操作组 (opgroup_e)

```systemverilog
typedef enum logic [2:0] {
  ADDMUL, DIVSQRT, NONCOMP, CONV, DOTP
} opgroup_e;
```

每个操作属于一个操作组，用于路由到不同的硬件单元。

### 2.3 浮点格式 (fp_format_e)

```systemverilog
typedef enum logic [FP_FORMAT_BITS-1:0] {
  FP32    = 'd0,  // IEEE binary32 (single)
  FP64    = 'd1,  // IEEE binary64 (double)
  FP16    = 'd2,  // IEEE binary16 (half)
  FP8     = 'd3,  // custom binary8
  FP16ALT = 'd4,  // custom binary16alt
  FP8ALT  = 'd5   // custom binary8alt
} fp_format_e;
```

**Spatz 默认使用 FP64** (双精度)。

### 2.4 舍入模式 (roundmode_e)

```systemverilog
typedef enum logic [2:0] {
  RNE = 3'b000,  // Round to Nearest, ties to Even
  RTZ = 3'b001,  // Round towards Zero
  RDN = 3'b010,  // Round Down (towards -∞)
  RUP = 3'b011,  // Round Up (towards +∞)
  RMM = 3'b100,  // Round to Nearest, ties to Max Magnitude
  ROD = 3'b101,  // Round to Odd (non-standard)
  RSR = 3'b110,  // Stochastic Rounding (non-standard)
  DYN = 3'b111   // Dynamic (use fcsr)
} roundmode_e;
```

### 2.5 状态标志 (status_t)

```systemverilog
typedef struct packed {
  logic NV; // Invalid
  logic DZ; // Divide by zero
  logic OF; // Overflow
  logic UF; // Underflow
  logic NX; // Inexact
} status_t;
```

---

## 3. fpnew_fma 模块接口

**文件**: `.bender/git/checkouts/fpnew-d958174726140127/src/fpnew_fma.sv`  
**位置**: 第 18-54 行

### 3.1 模块声明

```systemverilog
module fpnew_fma #(
  parameter fpnew_pkg::fp_format_e   FpFormat    = fpnew_pkg::fp_format_e'(0),
  parameter int unsigned             NumPipeRegs = 0,
  parameter fpnew_pkg::pipe_config_t PipeConfig  = fpnew_pkg::BEFORE,
  parameter type                     TagType     = logic,
  parameter type                     AuxType     = logic,

  localparam int unsigned WIDTH = fpnew_pkg::fp_width(FpFormat)
) (
  input logic                      clk_i,
  input logic                      rst_ni,
  
  // Input signals
  input logic [2:0][WIDTH-1:0]     operands_i,   // 3 operands (a, b, c)
  input logic [2:0]                is_boxed_i,   // NaN boxing check
  input fpnew_pkg::roundmode_e     rnd_mode_i,
  input fpnew_pkg::operation_e     op_i,         // FMADD or FNMSUB
  input logic                      op_mod_i,     // Operation modifier
  input TagType                    tag_i,
  input logic                      mask_i,
  input AuxType                    aux_i,
  
  // Input Handshake
  input  logic                     in_valid_i,
  output logic                     in_ready_o,
  input  logic                     flush_i,
  
  // Output signals
  output logic [WIDTH-1:0]         result_o,
  output fpnew_pkg::status_t       status_o,
  output logic                     extension_bit_o,
  output TagType                   tag_o,
  output logic                     mask_o,
  output AuxType                   aux_o,
  
  // Output handshake
  output logic                     out_valid_o,
  input  logic                     out_ready_i,
  
  // Indication of valid data in flight
  output logic                     busy_o
);
```

### 3.2 接口说明

**参数**:
- `FpFormat`: 浮点格式 (FP32, FP64, etc.)
- `NumPipeRegs`: 流水线寄存器数量
- `PipeConfig`: 流水线配置 (BEFORE, AFTER, INSIDE, DISTRIBUTED)
- `TagType`: 标签类型 (用于追踪操作)
- `AuxType`: 辅助信息类型

**输入**:
- `operands_i`: 3 个操作数 [a, b, c]，宽度由 FpFormat 决定
- `rnd_mode_i`: 舍入模式
- `op_i`: 操作类型 (FMADD 或 FNMSUB)
- `op_mod_i`: 操作修饰符

**输出**:
- `result_o`: 计算结果
- `status_o`: 异常状态标志
- `busy_o`: 模块忙碌指示

**握手信号**:
- 输入: `in_valid_i` / `in_ready_o`
- 输出: `out_valid_o` / `out_ready_i`

---

## 4. fpnew_top 在 Spatz VFU 中的实例化

**文件**: `hw/ip/spatz/src/spatz_vfu.sv`  
**位置**: 第 1306-1382 行

### 4.1 生成块结构

```systemverilog
for (genvar fpu = 0; unsigned'(fpu) < N_FPU; fpu++) begin : gen_fpnew
  // FPU pipeline stage
  elen_t fpu_operand1_q, fpu_operand2_q, fpu_operand3_q;
  operation_e fpu_op_q;
  fp_format_e fpu_src_fmt_q, fpu_dst_fmt_q;
  int_format_e fpu_int_fmt_q;
  logic fpu_op_mode_q;
  logic fpu_vectorial_op_q;
  roundmode_e rm_q;
  vfu_tag_t input_tag_q;
  logic fpu_in_valid_q;
  
  // FPU instantiation
  fpnew_top #(
    .Features                   (FPUFeatures           ),
    .Implementation             (FPUImplementation     ),
    .TagType                    (vfu_tag_t             ),
    .StochasticRndImplementation(fpnew_pkg::DEFAULT_RSR)
  ) i_fpu (
    .clk_i         (clk_i                                                  ),
    .rst_ni        (rst_ni                                                 ),
    .operands_i    ({fpu_operand3_q, fpu_operand2_q, fpu_operand1_q}       ),
    .in_valid_i    (fpu_in_valid_q                                         ),
    .in_ready_o    (fpu_in_ready_d                                         ),
    .op_i          (fpu_op_q                                               ),
    .src_fmt_i     (fpu_src_fmt_q                                          ),
    .dst_fmt_i     (fpu_dst_fmt_q                                          ),
    .int_fmt_i     (fpu_int_fmt_q                                          ),
    .vectorial_op_i(fpu_vectorial_op_q                                     ),
    .op_mod_i      (fpu_op_mode_q                                          ),
    .rnd_mode_i    (rm_q                                                   ),
    .result_o      (fpu_result[fpu*ELEN +: ELEN]                           ),
    .out_valid_o   (int_fpu_result_valid                                   ),
    .out_ready_i   (result_ready                                           ),
    .status_o      (fpu_status_d[fpu]                                      ),
    .tag_o         (tag                                                    )
  );
end : gen_fpnew
```

### 4.2 关键特性

1. **多 FPU 实例**: Spatz 可配置多个 FPU (默认 `N_FPU = 4`)
2. **流水线化**: 操作数在进入 FPU 前先锁存到 `_q` 寄存器
3. **握手机制**: 使用 valid/ready 握手控制数据流
4. **标签追踪**: 使用 `vfu_tag_t` 追踪每个操作，包含 vsew 信息

---

## 5. 操作数路由逻辑

**文件**: `hw/ip/spatz/src/spatz_vfu.sv`  
**位置**: 第 1314-1317 行

```systemverilog
elen_t fpu_operand1, fpu_operand2, fpu_operand3;
assign fpu_operand1 = spatz_req.op_arith.switch_rs1_rd 
                      ? wide_operand3[fpu*ELEN +: ELEN] 
                      : wide_operand1[fpu*ELEN +: ELEN];
assign fpu_operand2 = wide_operand2[fpu*ELEN +: ELEN];
assign fpu_operand3 = (fpu_op == fpnew_pkg::ADD || spatz_req.op_arith.switch_rs1_rd) 
                      ? wide_operand1[fpu*ELEN +: ELEN] 
                      : wide_operand3[fpu*ELEN +: ELEN];
```

**注意**: 
- 操作数从 VRF 宽向量 (`wide_operand1/2/3`) 中提取
- 支持操作数交换 (`switch_rs1_rd`)
- 每个 FPU 处理 ELEN (64-bit) 宽度的数据

---

## 6. 操作码映射

**文件**: `hw/ip/spatz/src/spatz_vfu.sv`  
**位置**: 约 200-400 行 (gen_decoder 块)

Spatz 将 RISC-V 向量指令映射到 fpnew 操作码：

| RISC-V 指令 | Spatz 内部操作 | fpnew 操作码 |
|------------|--------------|-------------|
| VFADD      | VFADD        | ADD         |
| VFMUL      | VFMUL        | MUL         |
| VFMADD     | VFMADD       | FMADD       |
| VFMSUB     | VFMSUB       | FMADD (op_mod=1) |
| VFNMADD    | VFNMADD      | FNMSUB      |
| VFCMACC    | VFCMACC      | FMADD (4-phase) |

**VFCMACC 的特殊处理**:
- 当前通过 4-phase 串行执行实现
- 每个 phase 执行一次 FMADD
- 由 `cfma_phase_q` 状态机控制

---

## 7. 为 Complex FMA 预留的扩展点

### 7.1 操作码扩展

在 `fpnew_pkg.sv` 的 `operation_e` 枚举中添加新操作：

```systemverilog
typedef enum logic [OP_BITS-1:0] {
  // 现有操作...
  SDOTP, EXVSUM, VSUM,         // DOTP operation group
  
  // 新增: Complex FMA
  CFMA = 5'd18                 // 或下一个可用值
} operation_e;
```

**可用编码**: 当前使用到 `VSUM` (约 17)，`5'd18` 可用。

### 7.2 新模块集成点

建议创建独立模块 `fpnew_complex_fma.sv`，与 `fpnew_fma.sv` 并列：

```
.bender/git/checkouts/fpnew-*/src/
├── fpnew_fma.sv              # 标量 FMA
├── fpnew_complex_fma.sv      # 新增: Complex FMA (本地)
└── fpnew_top.sv              # 顶层 (需修改路由逻辑)
```

**或者**在 Spatz 本地创建：

```
hw/ip/spatz/src/
├── spatz_vfu.sv
├── spatz_fpu_sequencer.sv
└── fpnew_complex_fma.sv      # 新增: Complex FMA (推荐)
```

### 7.3 在 spatz_vfu.sv 中的实例化位置

在 `gen_fpnew` 生成块后添加：

```systemverilog
end : gen_fpnew

// 新增: Complex FMA unit
if (ENABLE_CFMA) begin : gen_cfma
  fpnew_complex_fma #(
    .FpFormat(fpnew_pkg::FP64),
    .NumPipeRegs(0)
  ) i_complex_fma (
    // 连接接口
  );
end : gen_cfma
```

---

## 8. 总结

### 8.1 关键文件路径

1. **fpnew_pkg.sv**:  
   `.bender/git/checkouts/fpnew-d958174726140127/src/fpnew_pkg.sv`
   - 定义 `operation_e` (需扩展)
   - 定义 `roundmode_e`, `status_t`

2. **fpnew_fma.sv**:  
   `.bender/git/checkouts/fpnew-d958174726140127/src/fpnew_fma.sv`
   - 标量 FMA 实现 (可复用)

3. **spatz_vfu.sv**:  
   `hw/ip/spatz/src/spatz_vfu.sv`
   - FPU 实例化 (第 1306 行)
   - 操作数路由 (第 1314 行)
   - 操作码解码 (约 200-400 行)

4. **spatz_fpu_sequencer.sv**:  
   `hw/ip/spatz/src/spatz_fpu_sequencer.sv`
   - 当前 CFMA 4-phase 逻辑所在

### 8.2 验收标准确认

- ✅ fpnew_structure.md 文件存在
- ✅ 文档中包含至少 3 个关键文件路径:
  1. `.bender/git/checkouts/fpnew-d958174726140127/src/fpnew_pkg.sv`
  2. `.bender/git/checkouts/fpnew-d958174726140127/src/fpnew_fma.sv`
  3. `hw/ip/spatz/src/spatz_vfu.sv`
- ✅ 记录了现有 operation_e 的所有枚举值 (18 个操作)
- ✅ 记录了 FPU 接口信号定义

### 8.3 下一步行动

**步骤 2**: 扩展 fpnew_pkg 添加 CFMA 操作码

---

**文档版本**: v1.0  
**最后更新**: 2026-06-13
