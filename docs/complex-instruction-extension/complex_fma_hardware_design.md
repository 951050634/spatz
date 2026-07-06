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

## 6. 详细实施步骤（可量化、可验收）

**说明**：每个步骤都有明确的输入、输出和验收标准，完成后需进行 git commit。

---

### 步骤 1：定位 FPU 相关基础设施

**目标**：找到 fpnew 包和 FMA 单元的位置，理解现有 FPU 架构

**具体任务**：
1. 在 hw/ 目录下搜索 "fpnew_pkg" 关键字，找到包定义文件的完整路径
2. 找到现有 fpnew_fma 模块的位置（如果存在独立文件）
3. 查看 spatz_vfu.sv 中 FPU 实例化代码（约 1306 行附近的 gen_fpnew）
4. 读取 fpnew_pkg 中的 operation_e 枚举定义，确认现有操作码
5. 创建文档：`docs/complex-instruction-extension/fpnew_structure.md`
   记录：
   - fpnew_pkg.sv 的路径
   - 现有 FPU 模块的实例化方式
   - operation_e 中已有的操作码列表
   - FPU 接口信号定义（operand_a/b/c, result, valid/ready）

**验收标准**：
- ✓ fpnew_structure.md 文件存在
- ✓ 文档中包含至少 3 个关键文件路径
- ✓ 记录了现有 operation_e 的所有枚举值

**Git 操作**：
```bash
git add docs/complex-instruction-extension/fpnew_structure.md
git commit -m "[cfma] Document fpnew package structure and FPU architecture"
```

---

### 步骤 2：扩展 fpnew_pkg 添加 CFMA 操作码

**目标**：在 fpnew 包中添加 Complex FMA 操作类型定义

**具体任务**：
1. 打开步骤 1 中找到的 fpnew_pkg.sv 文件
2. 定位 operation_e 枚举类型定义
3. 在枚举末尾添加新操作：`CFMA = 4'hC` （或下一个可用的编码）
4. 添加注释说明：`// Complex FMA: result = c + a * b (complex arithmetic)`
5. 验证语法：运行 `verilator --lint-only fpnew_pkg.sv`

**验收标准**：
- ✓ fpnew_pkg.sv 中 operation_e 包含 CFMA
- ✓ CFMA 有明确的数值编码（不与现有冲突）
- ✓ 有注释说明其功能
- ✓ 文件通过 lint 检查（无语法错误）

**Git 操作**：
```bash
git add <fpnew_pkg.sv的路径>
git commit -m "[cfma] Add CFMA operation code to fpnew_pkg"
```

---

### 步骤 3：创建 fpnew_complex_fma 模块接口定义

**目标**：创建模块骨架，定义所有输入输出端口

**具体任务**：
1. 确定模块文件位置（与现有 fpnew 模块同目录，或 `hw/ip/spatz/src/`）
2. 创建文件 `fpnew_complex_fma.sv`
3. 编写模块声明，包含：
   - 参数：`FpFormat` (默认 FP64), `NumPipeRegs` (默认 0), `PipeConfig`
   - 输入端口：`clk_i`, `rst_ni`
   - 操作数输入：`operand_a_real_i`, `operand_a_imag_i`, `operand_b_real_i`, `operand_b_imag_i`, `operand_c_real_i`, `operand_c_imag_i` (6个，各64位)
   - 控制输入：`rnd_mode_i`, `op_valid_i`
   - 控制输出：`op_ready_o`, `busy_o`
   - 结果输出：`result_real_o`, `result_imag_o` (各64位), `status_o`, `result_valid_o`
   - 结果输入：`result_ready_i`
4. 在 module 内部添加占位注释：
   ```systemverilog
   // TODO: State machine (4 states)
   // TODO: Intermediate registers (4x 64-bit)
   // TODO: FMA unit instantiation (2x)
   // TODO: Control logic
   ```
5. 添加临时实现：`assign op_ready_o = 1'b0;` (防止编译错误)

**验收标准**：
- ✓ fpnew_complex_fma.sv 文件存在
- ✓ 模块有 6 个操作数输入端口（各 64-bit）
- ✓ 模块有 2 个结果输出端口（各 64-bit）
- ✓ 包含 valid/ready 握手信号
- ✓ 文件可以通过 SystemVerilog 语法检查
- ✓ 文件大小 > 1KB（确保不是空文件）

**Git 操作**：
```bash
git add hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Create fpnew_complex_fma module skeleton with interface definition"
```

---

### 步骤 4：实现 fpnew_complex_fma 状态机

**目标**：实现 4 状态 FSM 控制 Complex FMA 的执行流程

**具体任务**：
1. 在 fpnew_complex_fma.sv 中定义状态枚举：
   ```systemverilog
   typedef enum logic [1:0] {
     IDLE         = 2'b00,
     MULTIPLY_PH1 = 2'b01,  // 计算 prod_rr, prod_ii
     MULTIPLY_PH2 = 2'b10,  // 计算 prod_ri, prod_ir
     ADD_PHASE    = 2'b11   // 计算最终结果
   } cfma_state_e;
   ```
2. 声明状态寄存器：`cfma_state_e state_q, state_d;`
3. 实现状态转移逻辑（always_comb）：
   - IDLE → MULTIPLY_PH1: 当 op_valid_i 为高
   - MULTIPLY_PH1 → MULTIPLY_PH2: 自动转移
   - MULTIPLY_PH2 → ADD_PHASE: 自动转移
   - ADD_PHASE → IDLE: 当 result_ready_i 为高
4. 实现状态寄存器更新（always_ff）
5. 实现 `op_ready_o` 信号：仅在 IDLE 状态为高
6. 实现 `result_valid_o` 信号：仅在 ADD_PHASE 状态为高
7. 实现 `busy_o` 信号：在非 IDLE 状态为高

**验收标准**：
- ✓ 定义了 4 个状态的枚举类型
- ✓ 有 always_comb 实现状态转移逻辑
- ✓ 有 always_ff 实现状态寄存器
- ✓ op_ready_o 仅在 IDLE 为 1
- ✓ result_valid_o 仅在 ADD_PHASE 为 1
- ✓ 代码通过 lint 检查

**Git 操作**：
```bash
git add hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Implement 4-state FSM for complex FMA control flow"
```

---

### 步骤 5：添加中间结果寄存器

**目标**：添加 4 个寄存器暂存乘法中间结果

**具体任务**：
1. 声明 4 个中间结果寄存器（各 64-bit）：
   ```systemverilog
   logic [63:0] prod_rr_q, prod_rr_d;
   logic [63:0] prod_ii_q, prod_ii_d;
   logic [63:0] prod_ri_q, prod_ri_d;
   logic [63:0] prod_ir_q, prod_ir_d;
   ```
2. 实现寄存器更新逻辑（always_ff）：在时钟上升沿更新 _q 从 _d
3. 在状态机中添加赋值逻辑：
   - MULTIPLY_PH1 状态：prod_rr_d 和 prod_ii_d 从 FMA 结果获取
   - MULTIPLY_PH2 状态：prod_ri_d 和 prod_ir_d 从 FMA 结果获取
4. 添加 reset 逻辑：当 rst_ni 为低时清零所有寄存器
5. 添加注释说明每个寄存器的用途

**验收标准**：
- ✓ 声明了 4 对寄存器（_q 和 _d）
- ✓ 有 always_ff 块更新寄存器
- ✓ 有 reset 逻辑
- ✓ 每个寄存器有注释说明
- ✓ 代码通过 lint 检查

**Git 操作**：
```bash
git add hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Add intermediate result registers for complex FMA datapath"
```

---

### 步骤 6：实例化 2 个 FMA 单元（仅接口连接）

**目标**：复用现有 fpnew_fma 模块，连接基本接口

**具体任务**：
1. 在 spatz_vfu.sv 中查找现有 fpnew FMA 的实例化代码（参考）
2. 在 fpnew_complex_fma.sv 中声明 FMA 单元的接口信号：
   ```systemverilog
   // FMA0 signals
   logic [63:0] fma0_operand_a, fma0_operand_b, fma0_operand_c;
   logic [63:0] fma0_result;
   logic fma0_valid, fma0_ready;
   // FMA1 signals
   logic [63:0] fma1_operand_a, fma1_operand_b, fma1_operand_c;
   logic [63:0] fma1_result;
   logic fma1_valid, fma1_ready;
   ```
3. 实例化 2 个 fpnew_fma 模块（或使用 Spatz 中的 FPU 实例方式）：如果没有独立的 fpnew_fma，则实例化 Spatz 使用的 FPU 类型
4. 连接时钟和复位信号
5. 连接 rounding mode：都使用 rnd_mode_i
6. 暂时将操作数连接到 '0（后续步骤会实现 mux）
7. 添加 localparam 定义 FMA 操作类型

**验收标准**：
- ✓ 实例化了 2 个 FMA 单元（或等效的 FPU）
- ✓ 时钟、复位、rounding mode 已连接
- ✓ 所有端口都有连接（即使是临时的 '0）
- ✓ 没有悬空的输出信号
- ✓ 代码通过 elaboration 检查

**Git 操作**：
```bash
git add hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Instantiate two FMA units with basic interface connections"
```

---

### 步骤 7：实现操作数 Multiplexer

**目标**：根据状态机选择正确的操作数输入到 FMA 单元

**具体任务**：
1. 实现 FMA0 操作数选择逻辑（always_comb）：
   ```systemverilog
   case (state_q)
     IDLE, MULTIPLY_PH1:
       fma0_operand_a = operand_a_real_i;
       fma0_operand_b = operand_b_real_i;
       fma0_operand_c = 64'h0;  // 纯乘法
     MULTIPLY_PH2:
       fma0_operand_a = operand_a_real_i;
       fma0_operand_b = operand_b_imag_i;
       fma0_operand_c = 64'h0;
     ADD_PHASE:
       fma0_operand_a = prod_rr_q;
       fma0_operand_b = prod_ii_q;
       fma0_operand_c = operand_c_real_i;
   endcase
   ```
2. 实现 FMA1 操作数选择逻辑（always_comb）：
   ```systemverilog
   case (state_q)
     IDLE, MULTIPLY_PH1:
       fma1_operand_a = operand_a_imag_i;
       fma1_operand_b = operand_b_imag_i;
       fma1_operand_c = 64'h0;
     MULTIPLY_PH2:
       fma1_operand_a = operand_a_imag_i;
       fma1_operand_b = operand_b_real_i;
       fma1_operand_c = 64'h0;
     ADD_PHASE:
       fma1_operand_a = prod_ri_q;
       fma1_operand_b = prod_ir_q;
       fma1_operand_c = operand_c_imag_i;
   endcase
   ```
3. 为 ADD_PHASE 配置 FMA 操作类型（FNMSUB for real, FMADD for imag）
4. 添加注释说明每个状态的计算含义

**验收标准**：
- ✓ FMA0 和 FMA1 各有一个 case 语句
- ✓ 每个状态都有明确的操作数赋值
- ✓ MULTIPLY 阶段 operand_c 为 0（纯乘法）
- ✓ ADD_PHASE 使用中间结果和累加器
- ✓ 有注释说明计算逻辑
- ✓ 代码通过 lint 检查

**Git 操作**：
```bash
git add hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Implement operand multiplexer for FMA units"
```

---

### 步骤 8：实现结果路由和输出

**目标**：将 FMA 结果正确路由到输出或中间寄存器

**具体任务**：
1. 在状态机逻辑中添加中间结果捕获：
   - MULTIPLY_PH1: 捕获 `fma0_result → prod_rr_d`, `fma1_result → prod_ii_d`
   - MULTIPLY_PH2: 捕获 `fma0_result → prod_ri_d`, `fma1_result → prod_ir_d`
2. 实现最终结果输出：
   - ADD_PHASE: `result_real_o = fma0_result`, `result_imag_o = fma1_result`
3. 处理 FMA valid/ready 握手：
   - 在 MULTIPLY 和 ADD 状态：`fma0/1_valid = 1'b1`
   - 在 IDLE 状态：`fma0/1_valid = 1'b0`
4. 连接 status 信号（合并两个 FMA 的 status）
5. 添加 pipeline 考虑：如果 FMA 有多周期延迟，需要添加计数器

**验收标准**：
- ✓ 每个状态都有明确的结果去向
- ✓ result_real_o 和 result_imag_o 在正确的状态被赋值
- ✓ FMA valid 信号根据状态正确控制
- ✓ status_o 合并了两个 FMA 的状态
- ✓ 代码逻辑完整，无悬空赋值

**Git 操作**：
```bash
git add hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Implement result routing and output logic"
```

---

### 步骤 9：独立编译验证 fpnew_complex_fma 模块

**目标**：验证模块本身语法正确，接口完整

**具体任务**：
1. 创建简单的 testbench wrapper（可选，如果需要）
2. 运行 Verilator lint 检查：
   ```bash
   verilator --lint-only -Wall fpnew_complex_fma.sv
   ```
3. 检查并修复所有 warning 和 error
4. 验证接口完整性：
   - 所有输入端口都有使用
   - 所有输出端口都有驱动
   - 没有组合环路
5. 记录模块的关键参数：
   - 面积估算：2 FMA + 4 registers + FSM
   - 延迟：4 cycles (计算) + overhead
   - 吞吐率：1 complex result / 8 cycles

**验收标准**：
- ✓ `verilator --lint-only` 通过（0 error）
- ✓ warning 数量 < 5（或有合理解释）
- ✓ 所有端口有明确的驱动源或接收者
- ✓ 无未使用的信号声明
- ✓ 模块接口符合设计文档 3.1 节规范

**Git 操作**：
```bash
git add hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Complete fpnew_complex_fma module implementation and pass lint check"
```

---

### 步骤 10：在 spatz_vfu.sv 中添加 CFMA 模块实例化

**目标**：将 fpnew_complex_fma 集成到 VFU 中

**具体任务**：
1. 在 spatz_vfu.sv 的 FPU 生成块（gen_fpnew，约 1306 行）附近找到合适位置
2. 添加条件编译或参数检查：仅在支持 CFMA 时实例化
3. 声明 CFMA 模块的接口信号：
   ```systemverilog
   logic cfma_op_valid, cfma_op_ready;
   logic [63:0] cfma_operand_a_real, cfma_operand_a_imag;
   logic [63:0] cfma_operand_b_real, cfma_operand_b_imag;
   logic [63:0] cfma_operand_c_real, cfma_operand_c_imag;
   logic [63:0] cfma_result_real, cfma_result_imag;
   logic cfma_result_valid, cfma_result_ready;
   logic cfma_busy;
   ```
4. 实例化 fpnew_complex_fma 模块：
   ```systemverilog
   fpnew_complex_fma #(
     .FpFormat(fpnew_pkg::FP64),
     .NumPipeRegs(0)
   ) i_complex_fma (
     .clk_i,
     .rst_ni,
     .operand_a_real_i(cfma_operand_a_real),
     // ... 连接所有端口
   );
   ```
5. 暂时不连接操作数（下一步实现），先用 '0 占位
6. 检查编译：`cd hw/system/spatz_cluster && make bin/spatz_cluster.vlt`

**验收标准**：
- ✓ spatz_vfu.sv 中添加了 fpnew_complex_fma 实例
- ✓ 所有端口都有连接（即使是临时的）
- ✓ 实例化使用了正确的参数（FP64）
- ✓ 编译能够通过 elaboration 阶段
- ✓ 没有引入新的 lint error

**Git 操作**：
```bash
git add hw/ip/spatz/src/spatz_vfu.sv
git commit -m "[cfma] Instantiate fpnew_complex_fma module in spatz_vfu"
```

---

### 步骤 11：实现 CFMA 操作数路由（VRF 读取逻辑）

**当前状态（2026-07-06）**：已由提交
`0de3f7f [cfma] Implement split VRF read logic for 6 complex FMA operands` 完成。
以下内容保留为设计依据和审计记录。

**目标**：从 VRF 读取 6 个操作数，分拍路由到 CFMA 模块

**具体任务**：
1. 在 spatz_vfu.sv 的操作数读取逻辑中（vreg_addr_proc，约 520 行）定位合适位置
2. 为 CFMA 添加特殊处理：当 `cfma_insn` 为真时
3. 实现分拍读取状态机：
   ```systemverilog
   typedef enum logic [1:0] {
     CFMA_READ_IDLE,
     CFMA_READ_PHASE1,  // 读 a.real, a.imag, b.real
     CFMA_READ_PHASE2   // 读 b.imag, c.real, c.imag
   } cfma_read_state_e;
   ```
4. 在 PHASE1：
   - `vrf_raddr_o[0] = vs2` (a.real)
   - `vrf_raddr_o[1] = vs2 + LMUL` (a.imag)
   - `vrf_raddr_o[2] = vs1` (b.real)
   - 锁存这 3 个操作数
5. 在 PHASE2：
   - `vrf_raddr_o[0] = vs1 + LMUL` (b.imag)
   - `vrf_raddr_o[1] = vd` (c.real)
   - `vrf_raddr_o[2] = vd + LMUL` (c.imag)
   - 锁存这 3 个操作数
6. 将锁存的 6 个操作数连接到 `cfma_operand_*_i` 信号
7. 控制 `cfma_op_valid`：在所有 6 个操作数就绪后拉高

**验收标准**：
- ✓ 实现了 CFMA 专用的读取状态机
- ✓ 分 2 拍读取 6 个操作数
- ✓ 操作数地址计算考虑了 LMUL 偏移
- ✓ 有锁存寄存器保存 PHASE1 的操作数
- ✓ cfma_op_valid 的控制逻辑正确
- ✓ 编译通过

**Git 操作**：
```bash
git add hw/ip/spatz/src/spatz_vfu.sv
git commit -m "[cfma] Implement split VRF read logic for 6 complex FMA operands"
```

---

### 步骤 12：实现 CFMA 结果写回逻辑

**当前状态（2026-07-06）**：进行中，不能标记完成。工作区已有未提交草稿，在
`hw/ip/spatz/src/spatz_vfu.sv` 中新增两拍写回 FSM、`cfma_wb_*` 信号和 VRF 写回
mux 接入；但专用写回路径通过 `CfmaDedicatedWritebackEn = 1'b0` 默认禁用。
默认功能路径仍是已验证的现有四阶段 FPU CFMA 路径。

**禁用原因**：启用 dedicated CFMA result write-back 会覆盖既有正确结果并导致
`vfcmacc` RTL regression 出错。当前专用硬件路径还缺少动态 FP format、packed
e16/e32 lane 语义、完整 complex arithmetic/status flags，以及经过验证的
mask/tail byte enable 和 response timing。

**本轮验证结论**：在专用写回默认禁用后，`git diff --check`、Spatz cluster
Verilator build，以及 `vfcmacc/vfmacc/vfnmsac` RTL regression 均通过。该证据只证明
guard 后没有破坏既有功能路径，不证明 dedicated hardware path 可启用。

**目标**：将 CFMA 的 2 个结果分拍写回 VRF

**具体任务**：
1. 在 spatz_vfu.sv 的写回逻辑中（约 result_tag 相关，900 行附近）定位合适位置
2. 添加 CFMA 写回状态机：
   ```systemverilog
   typedef enum logic {
     CFMA_WRITE_REAL,
     CFMA_WRITE_IMAG
   } cfma_write_state_e;
   ```
3. 在 WRITE_REAL 状态：
   - `vrf_waddr_o = vd`
   - `vrf_wdata_o = cfma_result_real`
   - `vrf_we_o = cfma_result_valid`
   - 下一状态 → WRITE_IMAG
4. 在 WRITE_IMAG 状态：
   - `vrf_waddr_o = vd + LMUL`
   - `vrf_wdata_o = cfma_result_imag`
   - `vrf_we_o = cfma_result_valid`
   - 下一状态 → WRITE_REAL（等待下一个元素）
5. 连接 `cfma_result_ready`：当写回完成时拉高
6. 处理 byte enable：根据 vsew 设置正确的写使能位
7. 考虑与普通 FPU 结果的仲裁（mux）

**验收标准**：
- [x] 实现了 CFMA 专用的写回状态机草稿。
- [x] 分 2 拍写回 2 个结果的 FSM 草稿存在。
- [x] 写地址草稿包含 LMUL 偏移计算。
- [x] VRF 写回 mux 草稿可编译。
- [ ] byte enable 逻辑已在 dedicated path 启用模式下验证。
- [ ] 与现有写回逻辑在 dedicated path 启用模式下正确仲裁。
- [ ] dedicated hardware path 启用后 `vfcmacc` ISA regression 通过。

**Git 操作**：
```bash
git add hw/ip/spatz/src/spatz_vfu.sv
git commit -m "[cfma] Implement split VRF write logic for complex FMA results"
```

---

### 步骤 13：更新 CFMA phase 控制逻辑

**当前建议（2026-07-06）**：先做架构决策，不要直接默认启用
`USE_CFMA_HARDWARE`。当前已知可工作的 v1 功能路径是四阶段 FPU 复用实现；专用硬件
路径必须先补齐动态 FP format、packed lane、complex arithmetic、status flags、
mask/tail 和写回时序验证后才能作为默认路径。

**目标**：修改现有的 4-phase 串行逻辑，改用专用硬件单元

**具体任务**：
1. 找到现有 cfma_phase_q 的控制逻辑（约 382-398 行）
2. 添加编译选项或参数：`USE_CFMA_HARDWARE` (默认启用)
3. 在 `USE_CFMA_HARDWARE` 启用时：
   - 跳过 cfma_phase 状态机
   - 直接调用 cfma 硬件单元
   - cfma_phase_q 保持在 Cfma_RR（或废弃）
4. 在 `USE_CFMA_HARDWARE` 禁用时：
   - 保留原有的 4-phase 串行逻辑（向后兼容）
5. 更新 cfma_insn 的处理：
   - 检测到 VFCMADD 时，路由到 cfma 硬件单元
   - 不再进入 4-phase 循环
6. 更新 `cfma_wait_result_q` 逻辑：
   - 等待 cfma 硬件单元完成（通过 cfma_busy）
7. 清理不再需要的 cfma_status 累积逻辑

**验收标准**：
- ✓ 添加了 USE_CFMA_HARDWARE 编译选项
- ✓ 新逻辑正确绕过 4-phase 循环
- ✓ 保留了向后兼容模式
- ✓ cfma_wait_result 逻辑更新为监控硬件单元
- ✓ 没有破坏非 CFMA 指令的执行
- ✓ 编译通过

**Git 操作**：
```bash
git add hw/ip/spatz/src/spatz_vfu.sv
git commit -m "[cfma] Update control logic to use dedicated CFMA hardware unit"
```

---

### 步骤 14：处理 CFMA 的 fence 和依赖关系

**目标**：确保 CFMA 与其他指令的正确同步

**具体任务**：
1. 阅读 `docs/complex-instruction-extension/fence_explained.md`
2. 确认 CFMA 硬件单元是否需要 fence：
   - 如果内部处理所有依赖：可以减少或消除 fence
   - 如果与 VRF 有 RAW/WAW 冲突：需要保留 fence
3. 更新 fence 逻辑（如果需要）：
   - 在 CFMA 操作前：等待前序写操作完成
   - 在 CFMA 操作后：阻塞后序读操作，直到写回完成
4. 检查 scoreboard 更新：
   - CFMA 读取时，标记 vs1, vs2, vd 为 busy
   - CFMA 写回完成后，清除 vd 的 busy 标记
5. 测试场景：连续的 CFMA 指令，验证无数据冒险

**验收标准**：
- ✓ 理解了 CFMA 的依赖关系
- ✓ fence 逻辑正确（或有理由移除）
- ✓ scoreboard 正确更新
- ✓ 不会引入数据冒险
- ✓ 编译通过

**Git 操作**：
```bash
git add hw/ip/spatz/src/spatz_vfu.sv
git commit -m "[cfma] Handle fence and data dependency for CFMA hardware unit"
```

---

### 步骤 15：全系统编译和语法验证

**目标**：确保所有修改能够成功编译

**长时间编译许可**：允许进行长时间编译工作以验证指令集修改的合理性。RTL、opcode、
decode、benchmark 或 ISA 行为发生变化后，应运行完整 Verilator 构建、软件构建或
目标 CTest；耗时较长不是跳过验证的理由。每次长时间验证必须记录命令、开始/结束
时间、退出码和关键输出摘要。失败或超时必须记录为风险或 blocker，不能把相关步骤
标为完成。

**具体任务**：
1. 清理之前的编译产物：
   ```bash
   cd hw/system/spatz_cluster
   make clean
   ```
2. 编译 Verilator 仿真器：
   ```bash
   make bin/spatz_cluster.vlt
   ```
3. 记录编译输出到日志：
   ```bash
   make bin/spatz_cluster.vlt 2>&1 | tee compile.log
   ```
4. 检查编译日志：
   - 0 error（必须）
   - warning < 10（建议）
5. 如果有错误，按优先级修复：
   - 语法错误（最高优先级）
   - 未定义信号
   - 端口连接错误
   - 类型不匹配
6. 记录编译统计：
   - 编译时间
   - 生成的文件大小
   - 主要 warning 类型

**验收标准**：
- ✓ `make bin/spatz_cluster.vlt` 成功完成
- ✓ 编译日志中 0 error
- ✓ 所有 critical warning 已解决或有合理解释
- ✓ 生成了可执行的仿真器二进制文件
- ✓ 文件大小合理（与之前版本相比增长 < 20%）

**Git 操作**：
```bash
git add hw/ip/spatz/src/spatz_vfu.sv hw/ip/.../fpnew_complex_fma.sv
git commit -m "[cfma] Fix compilation errors and complete system integration"
```

---

### 步骤 16：功能仿真测试

**目标**：运行基本测试验证 CFMA 硬件单元功能正确

**具体任务**：
1. 选择一个简单的 complex benchmark 进行测试：
   ```bash
   cd hw/system/spatz_cluster
   bin/spatz_cluster.vlt sw/build/spatzBenchmarks/dp-cdotp
   ```
2. 检查仿真是否能正常运行（不崩溃）
3. 检查输出日志中是否有异常：
   - 查找 "ERROR", "FATAL", "ASSERTION" 等关键字
4. 如果仿真失败，使用波形调试：
   ```bash
   make bin/spatz_cluster.vlt TRACE=1
   bin/spatz_cluster.vlt sw/build/spatzBenchmarks/dp-cdotp
   gtkwave dump.vcd
   ```
5. 验证 CFMA 指令的执行：
   - 检查状态机是否正确转移
   - 检查操作数是否正确读取
   - 检查结果是否正确写回
6. 记录仿真结果：
   - 执行时间
   - cycle 数
   - 是否产生正确结果

**验收标准**：
- ✓ 仿真能够完整运行不崩溃
- ✓ 没有 ERROR 或 FATAL 消息
- ✓ CFMA 指令能够被识别和执行
- ✓ 基本功能正确（即使性能未达标）
- ✓ 波形显示状态转移正常

**Git 操作**：
```bash
# 如果发现 bug 并修复
git add <修复的文件>
git commit -m "[cfma] Fix functional bugs found in simulation"
```

---

### 步骤 17：性能测试和优化

**目标**：验证性能提升是否达到预期目标

**具体任务**：
1. 运行完整的 benchmark suite：
   ```bash
   cd hw/system/spatz_cluster
   make sw  # 重新编译所有测试
   ./run_benchmarks.sh  # 或手动运行
   ```
2. 记录关键 benchmark 的性能数据：
   - dp-cdotp: cycle 数、执行时间
   - dp-caxpy M4096/M1024/M256: cycle 数、执行时间
3. 与基线（4-phase 串行实现）对比：
   ```bash
   # 切换到不使用 CFMA 硬件的版本（如果有编译选项）
   # 运行相同的测试
   # 对比结果
   ```
4. 计算加速比：
   - 总 cycle 数减少比例
   - 执行时间减少比例
   - 是否达到 3.5× 目标
5. 分析性能瓶颈：
   - 如果未达标，使用性能计数器找到瓶颈
   - VRF 访问延迟？
   - fence 开销？
   - 状态机效率？
6. 创建性能报告：`docs/complex-instruction-extension/cfma_performance_results.md`
   包含：
   - 测试配置
   - 各 benchmark 的详细数据
   - 加速比分析
   - 瓶颈分析
   - 优化建议（如果需要）

**验收标准**：
- ✓ 所有 benchmark 运行完成
- ✓ 性能数据完整记录
- ✓ 加速比达到 2× 以上（目标 3.5×）
- ✓ 功能正确性验证通过（结果与参考实现一致）
- ✓ 性能报告文档完整

**Git 操作**：
```bash
git add docs/complex-instruction-extension/cfma_performance_results.md
git commit -m "[cfma] Add performance benchmark results and analysis"
```

---

### 步骤 18：文档更新和最终清理

**目标**：完善文档，清理临时代码，准备合并

**具体任务**：
1. 更新 CLAUDE.md：
   - 添加 CFMA 硬件单元的说明
   - 更新架构图（如果需要）
   - 说明如何启用/禁用 CFMA 硬件
2. 更新本文档：
   - 标记所有步骤为已完成 ✅
   - 更新验收标准部分的实际结果
   - 添加实际的性能数据
3. 清理代码：
   - 移除临时的 debug 代码
   - 移除注释掉的旧代码
   - 确保代码风格一致
   - 添加必要的注释
4. 检查 git 状态：
   ```bash
   git status  # 确保没有未跟踪的重要文件
   git log --oneline  # 检查 commit 历史
   ```
5. 创建总结文档：`docs/complex-instruction-extension/IMPLEMENTATION_SUMMARY.md`
   包含：
   - 实施过程概述
   - 遇到的主要问题和解决方案
   - 最终性能结果
   - 与设计目标的对比
   - 后续工作建议
6. 准备 PR 描述（如果需要）

**验收标准**：
- ✓ 所有文档已更新
- ✓ 代码清理完成
- ✓ git 历史清晰（至少 15 个有意义的 commit）
- ✓ IMPLEMENTATION_SUMMARY.md 完整
- ✓ 可以提交 PR 或合并到 main

**Git 操作**：
```bash
git add docs/complex-instruction-extension/*.md CLAUDE.md
git commit -m "[cfma] Update documentation and finalize implementation"
```

---

## 7. 验收标准（更新版）

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

---

## 11. 实施步骤总结

本实施计划包含 **18 个可量化、可验收的步骤**，每个步骤完成后都需要进行 git commit。

**步骤分组**：

### 阶段 1：模块开发（步骤 1-9）
- 步骤 1：定位 FPU 基础设施
- 步骤 2：扩展 fpnew_pkg 添加操作码
- 步骤 3-5：创建 fpnew_complex_fma 模块核心（接口、状态机、寄存器）
- 步骤 6-8：实现数据通路（FMA 实例化、操作数 mux、结果路由）
- 步骤 9：独立验证模块

**预计时间**：2-3 周

### 阶段 2：系统集成（步骤 10-14）
- 步骤 10：在 spatz_vfu 中实例化 CFMA 模块
- 步骤 11：实现 VRF 分拍读取逻辑
- 步骤 12：实现 VRF 分拍写回逻辑
- 步骤 13：更新控制逻辑
- 步骤 14：处理 fence 和依赖关系

**预计时间**：2-3 周

### 阶段 3：验证和优化（步骤 15-18）
- 步骤 15：全系统编译验证
- 步骤 16：功能仿真测试
- 步骤 17：性能测试和优化
- 步骤 18：文档更新和最终清理

**预计时间**：2-3 周

**总计**：6-9 周，至少 18 个 git commit

---

## 12. 性能对比分析

### 当前方案 vs. 专用硬件单元

| 指标 | 当前串行方案 | 专用硬件单元 | 改进 |
|------|-------------|--------------|------|
| 每元素 Cycles | ~28 cycles | 8 cycles | 3.5× |
| VRF 访问次数 | 4 次往返 | 1 次往返 | 4× |
| 硬件开销 | 基线 | +10-15% | 可接受 |
| 实现复杂度 | 低 | 中等 | 可控 |

### 预期 Benchmark 性能

| Benchmark | 当前 | 目标 | 加速比 |
|-----------|------|------|--------|
| dp-caxpy M4096 | 4.09秒 | ~1.2秒 | 3.4× |
| dp-caxpy M1024 | 2.23秒 | ~0.65秒 | 3.4× |
| dp-caxpy M256 | 3.33秒 | ~0.95秒 | 3.5× |
| dp-cdotp | 基线 | 预计 3-3.5× | 3-3.5× |

**关键收益**：
- ✅ 消除 4-phase 串行执行
- ✅ 减少 VRF 访问延迟
- ✅ 减少 pipeline bubble
- ✅ 优化 fence 开销

---

## 13. 使用指南

完成实施后，请将此提示词复制到新对话中使用 `/goal` 命令启动：

```
根据 docs/complex-instruction-extension/complex_fma_hardware_design.md 中的详细实施步骤（步骤 1-18），完成 Spatz VFU 的 Complex FMA 硬件单元实现。

要求：
1. 严格按照步骤顺序执行（步骤 1 → 步骤 18）
2. 每完成一个步骤，必须验证其验收标准
3. 每完成一个步骤，必须执行相应的 git commit
4. 遇到问题时，记录到文档并寻找解决方案
5. 最终完成所有 18 个步骤并通过所有验收标准

当前分支：feature/cfma-instruction-extension
```
