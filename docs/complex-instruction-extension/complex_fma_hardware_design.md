# 专用 Complex FMA 硬件单元设计方案

## 1. 设计目标

在 Spatz VFU 中添加专用的 Complex FMA 硬件单元，实现单周期复数乘加运算。

**约束**：
- 保持 conservative serialization fence（不修改）
- 复用现有 FPU infrastructure
- 最小化硬件开销

**预期收益**：
- 从 4条串行 FMA → 1个复数 FMA 单元
- 预期性能提升：2-3x（即使有 fence）
- 当前 12% → 目标 30-40%

---

## 2. 硬件架构设计

### 2.1 Complex FMA 数学定义

**输入**：
- `a = a.real + i*a.imag` (复数)
- `b = b.real + i*b.imag` (复数)
- `c = c.real + i*c.imag` (累加器，复数)

**输出**：
- `result = c + a * b`

**展开**：
```
result.real = c.real + (a.real * b.real - a.imag * b.imag)
result.imag = c.imag + (a.real * b.imag + a.imag * b.real)
```

**硬件需求**：
- 4个 FP 乘法器
- 4个 FP 加减器
- 6个输入端口
- 2个输出端口

---

### 2.2 模块层次结构

```
spatz_vfu
  ├── spatz_fpu_sequencer (修改)
  │   └── 识别 VFCMADD，生成复数 FMA 请求
  │
  └── fpnew_top (集成点)
      └── fpnew_complex_fma (新增模块)
          ├── 4x fpnew_fma (复用现有 FMA 单元)
          └── Complex datapath 控制逻辑
```

---

## 3. 详细设计

### 3.1 新增模块：fpnew_complex_fma.sv

**位置**：`hw/ip/fpnew/src/fpnew_complex_fma.sv`

**接口设计**：
```systemverilog
module fpnew_complex_fma #(
  parameter fpnew_pkg::fp_format_e   FpFormat    = fpnew_pkg::FP64,
  parameter int unsigned             NumPipeRegs = 0,
  parameter fpnew_pkg::pipe_config_t PipeConfig  = fpnew_pkg::BEFORE
) (
  input  logic                     clk_i,
  input  logic                     rst_ni,
  
  // Operands (6 inputs: a, b, c with real/imag parts)
  input  logic [63:0]              operand_a_real_i,
  input  logic [63:0]              operand_a_imag_i,
  input  logic [63:0]              operand_b_real_i,
  input  logic [63:0]              operand_b_imag_i,
  input  logic [63:0]              operand_c_real_i,
  input  logic [63:0]              operand_c_imag_i,
  
  // Control
  input  fpnew_pkg::roundmode_e    rnd_mode_i,
  input  logic                     op_valid_i,
  output logic                     op_ready_o,
  
  // Results (2 outputs: real/imag)
  output logic [63:0]              result_real_o,
  output logic [63:0]              result_imag_o,
  output fpnew_pkg::status_t       status_o,
  output logic                     result_valid_o,
  input  logic                     result_ready_i,
  
  // Side channels
  output logic [TagWidth-1:0]      result_tag_o,
  output logic                     busy_o
);
```

---

### 3.2 内部 Datapath 架构

**方案 A：时分复用（推荐，面积优化）**

使用 2个 FMA 单元，4个时钟周期完成：

```
Cycle 0: prod_rr = a.real * b.real
         prod_ii = a.imag * b.imag
         
Cycle 1: prod_ri = a.real * b.imag
         prod_ir = a.imag * b.real
         
Cycle 2: result.real = c.real + prod_rr - prod_ii
         
Cycle 3: result.imag = c.imag + prod_ri + prod_ir
```

**硬件资源**：
- 2个 FMA 单元（复用现有 fpnew_fma）
- 小型 FSM（4状态）
- 4个 64-bit 寄存器（暂存中间结果）

**面积增加**：~10-15%

---

**方案 B：全并行（性能优化）**

使用 4个 FMA 单元，2个时钟周期完成：

```
Cycle 0: 
  FMA0: prod_rr = a.real * b.real
  FMA1: prod_ii = a.imag * b.imag
  FMA2: prod_ri = a.real * b.imag
  FMA3: prod_ir = a.imag * b.real
  
Cycle 1:
  FMA0: result.real = c.real + prod_rr - prod_ii
  FMA1: result.imag = c.imag + prod_ri + prod_ir
```

**硬件资源**：
- 4个 FMA 单元
- 简单控制逻辑

**面积增加**：~25-30%

---

**推荐**：方案 A（时分复用）
- 面积增加可控
- 即使 4 cycle latency，相比当前 4条串行 FMA 仍有提升
- 与 fence 机制兼容

---

### 3.3 实现伪代码（方案 A）

```systemverilog
// State machine
typedef enum logic [1:0] {
  IDLE,
  MULTIPLY_PHASE1,  // 计算 prod_rr, prod_ii
  MULTIPLY_PHASE2,  // 计算 prod_ri, prod_ir
  ADD_PHASE         // 计算最终结果
} state_e;

state_e state_q, state_d;

// 中间结果寄存器
logic [63:0] prod_rr_q, prod_ii_q, prod_ri_q, prod_ir_q;

// 实例化 2个 FMA 单元
fpnew_fma #(
  .FpFormat(FP64)
) i_fma_0 (
  .operand_a_i(fma0_op_a),
  .operand_b_i(fma0_op_b),
  .operand_c_i(fma0_op_c),
  .result_o(fma0_result),
  // ...
);

fpnew_fma #(
  .FpFormat(FP64)
) i_fma_1 (
  .operand_a_i(fma1_op_a),
  .operand_b_i(fma1_op_b),
  .operand_c_i(fma1_op_c),
  .result_o(fma1_result),
  // ...
);

// 控制逻辑
always_comb begin
  state_d = state_q;
  
  case (state_q)
    IDLE: begin
      if (op_valid_i) begin
        // FMA0: a.real * b.real
        fma0_op_a = operand_a_real_i;
        fma0_op_b = operand_b_real_i;
        fma0_op_c = '0;  // 纯乘法
        
        // FMA1: a.imag * b.imag
        fma1_op_a = operand_a_imag_i;
        fma1_op_b = operand_b_imag_i;
        fma1_op_c = '0;
        
        state_d = MULTIPLY_PHASE1;
      end
    end
    
    MULTIPLY_PHASE1: begin
      // 保存结果
      prod_rr_d = fma0_result;
      prod_ii_d = fma1_result;
      
      // FMA0: a.real * b.imag
      fma0_op_a = operand_a_real_i;
      fma0_op_b = operand_b_imag_i;
      fma0_op_c = '0;
      
      // FMA1: a.imag * b.real
      fma1_op_a = operand_a_imag_i;
      fma1_op_b = operand_b_real_i;
      fma1_op_c = '0;
      
      state_d = MULTIPLY_PHASE2;
    end
    
    MULTIPLY_PHASE2: begin
      // 保存结果
      prod_ri_d = fma0_result;
      prod_ir_d = fma1_result;
      
      // FMA0: c.real + prod_rr - prod_ii
      fma0_op_a = prod_rr_q;
      fma0_op_b = prod_ii_q;
      fma0_op_c = operand_c_real_i;
      fma0_op = FNMSUB;  // c + a - b
      
      // FMA1: c.imag + prod_ri + prod_ir
      // 需要两步：先 prod_ri + prod_ir，再 + c.imag
      // 或者使用额外的加法器
      
      state_d = ADD_PHASE;
    end
    
    ADD_PHASE: begin
      result_real_o = fma0_result;
      result_imag_o = fma1_result;
      result_valid_o = 1'b1;
      
      if (result_ready_i) begin
        state_d = IDLE;
      end
    end
  endcase
end
```

**注意**：实际实现需要处理：
- Pipeline stages
- Rounding mode 传播
- Exception flags 合并
- Back-pressure 处理

---

## 4. 集成到 Spatz VFU

### 4.1 修改 fpnew_pkg.sv

**位置**：`hw/ip/fpnew/src/fpnew_pkg.sv`

```systemverilog
typedef enum logic [3:0] {
  // 现有操作
  FMADD  = 4'h0,
  FNMSUB = 4'h1,
  ADD    = 4'h2,
  // ...
  
  // 新增：复数 FMA
  CFMA   = 4'hC  // Complex FMA
} fpnew_operation_e;
```

---

### 4.2 修改 spatz_fpu_sequencer.sv

**位置**：`hw/ip/spatz/src/spatz_fpu_sequencer.sv`

```systemverilog
// 检测 VFCMADD 操作
if (spatz_req_i.op == VFCMADD) begin
  // 生成复数 FMA 请求
  fpu_req_o.op = fpnew_pkg::CFMA;
  
  // 设置操作数地址
  fpu_req_o.operand_a_real = vs1;        // vs1.real
  fpu_req_o.operand_a_imag = vs1 + LMUL; // vs1.imag
  fpu_req_o.operand_b_real = vs2;        // vs2.real
  fpu_req_o.operand_b_imag = vs2 + LMUL; // vs2.imag
  fpu_req_o.operand_c_real = vd;         // vd.real (accumulator)
  fpu_req_o.operand_c_imag = vd + LMUL;  // vd.imag (accumulator)
  
  // 设置目标寄存器（需要写回 real 和 imag）
  fpu_req_o.dest_real = vd;
  fpu_req_o.dest_imag = vd + LMUL;
  fpu_req_o.is_complex = 1'b1;  // 标记为复数操作
end
```

---

### 4.3 修改 spatz_vfu.sv

**位置**：`hw/ip/spatz/src/spatz_vfu.sv`

```systemverilog
// 实例化 fpnew_complex_fma
fpnew_complex_fma #(
  .FpFormat(fpnew_pkg::FP64),
  .NumPipeRegs(FPU_PIPE_STAGES)
) i_complex_fma (
  .clk_i,
  .rst_ni,
  .operand_a_real_i(vrf_operand_a_real),
  .operand_a_imag_i(vrf_operand_a_imag),
  .operand_b_real_i(vrf_operand_b_real),
  .operand_b_imag_i(vrf_operand_b_imag),
  .operand_c_real_i(vrf_operand_c_real),
  .operand_c_imag_i(vrf_operand_c_imag),
  .rnd_mode_i,
  .result_real_o(cfma_result_real),
  .result_imag_o(cfma_result_imag),
  .result_valid_o(cfma_valid),
  // ...
);

// 在 VRF writeback 逻辑中处理复数结果
always_comb begin
  if (fpu_op == CFMA && cfma_valid) begin
    // 写回 real 部分
    vrf_waddr_real = cfma_dest_real;
    vrf_wdata_real = cfma_result_real;
    vrf_we_real = 1'b1;
    
    // 写回 imag 部分
    vrf_waddr_imag = cfma_dest_imag;
    vrf_wdata_imag = cfma_result_imag;
    vrf_we_imag = 1'b1;
  end
end
```

---

## 5. VRF 带宽考虑

**挑战**：Complex FMA 需要同时读取 6个操作数，写回 2个结果。

**解决方案**：

### 方案 1：分拍读取（推荐）

```
Cycle 0: 读取 a.real, a.imag, b.real
Cycle 1: 读取 b.imag, c.real, c.imag
Cycle 2-5: 执行 Complex FMA (4 cycles)
Cycle 6: 写回 result.real
Cycle 7: 写回 result.imag
```

**优点**：无需修改 VRF 端口数量
**缺点**：额外 2 cycle overhead

### 方案 2：增加 VRF 读端口

修改 VRF 从 3读端口 → 6读端口

**优点**：无延迟
**缺点**：VRF 面积增加 ~30-40%，不推荐

---

**推荐**：方案 1（分拍读取）
- 总 latency: 2 (read) + 4 (compute) + 2 (write) = 8 cycles
- 相比当前 4条串行 FMA 仍有 2x+ 提升

---

## 6. 实施计划

### Phase 1: 模块设计与仿真 (2-3周)

1. 实现 `fpnew_complex_fma.sv` (1周)
   - 基本 datapath
   - FSM 控制逻辑
   - Rounding 和 exception 处理

2. 单元测试 (1周)
   - Testbench 验证
   - 边界情况：NaN, Inf, ±0
   - Rounding modes

3. 集成 fpnew_pkg.sv (2-3天)

### Phase 2: VFU 集成 (2-3周)

1. 修改 spatz_fpu_sequencer.sv (3-5天)
2. 修改 spatz_vfu.sv (1周)
3. VRF 读写逻辑调整 (3-5天)

### Phase 3: 系统验证 (2-3周)

1. ISA tests 回归 (3天)
2. 新增 complex FMA ISA tests (5天)
3. Benchmark 性能测试 (3天)
4. 功耗/面积综合分析 (1周)

**总工作量**：6-9周

---

## 7. 验收标准

### 功能正确性

1. ✅ 所有现有 ISA tests 通过（不回归）
2. ✅ 新增 complex FMA tests 通过：
   - 基本正确性
   - NaN/Inf 处理
   - Rounding modes (RNE, RTZ, RDN, RUP, RMM)
   - Subnormal 处理
3. ✅ dp-caxpy, dp-cdotp benchmarks bit-identical 结果

### 性能提升

| Benchmark | 当前 | 目标 | 提升 |
|-----------|------|------|------|
| dp-caxpy M4096 | 4.09秒 | <2.5秒 | >40% |
| dp-caxpy M1024 | 2.23秒 | <1.4秒 | >35% |
| dp-caxpy M256 | 3.33秒 | <2.1秒 | >35% |

### 硬件开销

1. ✅ 面积增加 <20%（相对 Spatz VFU）
2. ✅ 时序满足目标频率（无退化）
3. ✅ 功耗增加 <25%（complex workload）

---

## 8. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| VRF 带宽不足 | 性能受限 | 中 | 采用分拍读取方案 |
| Rounding 不一致 | 功能错误 | 低 | 参考 IEEE 754，详细测试 |
| 面积超标 | 硬件成本 | 中 | 时分复用，减少并行度 |
| 集成复杂度高 | 延期 | 中 | 分阶段实施，充分测试 |

---

## 9. 后续扩展

成功实施后，可添加：

1. **vfcjmacc.vv** - Conjugate multiply-accumulate
   ```
   result = c + conj(a) * b
   ```
   只需修改符号：`a.imag → -a.imag`

2. **vfcmul.vv** - Complex multiply (without accumulate)
   ```
   result = a * b
   ```
   `c` 输入设为 0

3. **fp32 支持** - 在同一硬件单元支持 `e32` element width

---

## 10. 参考资料

**现有实现**：
- `hw/ip/fpnew/src/fpnew_fma.sv` - 标量 FMA 实现
- `hw/ip/spatz/src/spatz_vfu.sv` - VFU 架构
- `hw/ip/spatz/src/spatz_fpu_sequencer.sv` - FPU 序列器

**相关文档**：
- `docs/complex-instruction-extension/PLAN.md` - 项目总体规划
- `docs/complex-instruction-extension/fence_explained.md` - Fence 机制
