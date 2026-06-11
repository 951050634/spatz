# 复数指令扩展路线图

## 当前状态：vfcmacc.vv 的价值

### 已完成的工作
1. **ISA 定义** - `vfcmacc.vv` 编码、语义已确定
2. **RTL 实现** - Decoder, Controller, Sequencer 已支持
3. **软件支持** - `.insn` 格式可用，benchmark 已验证
4. **验证基础** - ISA tests 框架已建立

### 当前架构的价值

**vfcmacc 当前实现**（4条 FMA 串行）虽然性能有限（12% 提升），但它是：

1. **指令集的基石** - 证明了复数指令在 Spatz 上可行
2. **软件生态起点** - 编译器、库函数可以开始使用
3. **硬件优化目标** - 专用硬件单元的验证基准

**重要性**：即使硬件优化后，**指令编码和语义保持不变**，软件完全兼容。

---

## 添加新指令的流程

### 标准流程（7个步骤）

以添加 `vfcjmacc.vv`（conjugate multiply-accumulate）为例：

#### 1. ISA 定义

**文档**: `docs/complex-instruction-extension/PLAN.md`

```
vfcjmacc.vv vd, vs1, vs2
  vd += conj(vs1) * vs2
  
数学:
  vd.real += vs1.real * vs2.real + vs1.imag * vs2.imag
  vd.imag += vs1.real * vs2.imag - vs1.imag * vs2.real
  
编码: 选择未使用的 funct6
```

**Opcode 分配** (`sw/toolchain-patches/riscv-opcodes/vfcmacc-vv.patch`):
```
vfcmacc.vv   31..26=0x3a vm vs2 vs1 14..12=0x1 vd 6..0=0x57
vfcjmacc.vv  31..26=0x3b vm vs2 vs1 14..12=0x1 vd 6..0=0x57  # 新增
```

#### 2. 更新 Opcode 生成

```bash
make update_opcodes
```

生成 `hw/ip/snitch/src/riscv_instr.sv`:
```systemverilog
localparam logic [31:0] VFCMACC_VV  = 32'b111010???????????001?????1010111;
localparam logic [31:0] VFCJMACC_VV = 32'b111011???????????001?????1010111; // 新增
```

#### 3. Decoder 识别

**文件**: `hw/ip/spatz/src/spatz_decoder.sv`

```systemverilog
// 添加新的内部 operation
typedef enum {
  // ... 现有 ...
  VFCMADD,   // Complex FMA
  VFCJMADD,  // Complex conjugate FMA (新增)
} spatz_operation_e;

// Decoder 逻辑
unique casez (instr_i)
  riscv_instr::VFCMACC_VV:  spatz_req.op = VFCMADD;
  riscv_instr::VFCJMACC_VV: spatz_req.op = VFCJMADD;  // 新增
endcase
```

#### 4. Controller 处理

**文件**: `hw/ip/spatz/src/spatz_controller.sv`

如果需要特殊处理（如 fence），添加逻辑：
```systemverilog
// VFCJMACC 使用相同的 fence 逻辑
assign cfma_fence_stall = 
    ((buffer_spatz_req.op == VFCMADD || buffer_spatz_req.op == VFCJMADD) && |running_insn_q) ||
    (|cfma_running_q && buffer_spatz_req.ex_unit != CON);
```

#### 5. 硬件实现

**软件实现路径** (当前方式):

`sw/spatzBenchmarks/*/kernel/*.c`:
```c
#define VFCJMACC_VV_VM1(vd, vs1, vs2) \
    asm volatile(".insn r 0x57, 0x1, 0x76, " vd ", " vs1 ", " vs2)

// 使用 4条 FMA 实现
asm volatile("vfmacc.vv v16, v0, v8");   // real += xr*yr
asm volatile("vfmacc.vv v16, v4, v12");  // real += xi*yi (conj!)
asm volatile("vfmacc.vv v20, v0, v12");  // imag += xr*yi
asm volatile("vfnmsac.vv v20, v4, v8");  // imag -= xi*yr (conj!)
```

**硬件优化路径** (专用单元):

`hw/ip/fpnew/src/fpnew_complex_fma.sv`:
```systemverilog
// 在 Complex FMA 单元中添加 conjugate 模式
if (op_i == VFCJMADD) begin
  // 修改符号: a.imag 取反
  operand_a_imag_internal = -operand_a_imag_i;
end
```

#### 6. ISA Tests

**文件**: `sw/riscvTests/isa/rv64uv/vfcjmacc.c`

```c
#define VFCJMACC_VV_VM1(vd, vs1, vs2) \
    asm volatile(".insn r 0x57, 0x1, 0x76, " vd ", " vs1 ", " vs2 ::: "memory")

int main() {
  // Test case 1: 基本正确性
  VLOAD_64(v0, 1.0, 2.0);  // (1+2i)
  VLOAD_64(v2, 3.0, 4.0);  // (3+4i)
  VLOAD_64(v8, 0.0, 0.0);
  
  VFCJMACC_VV_VM1("v8", "v0", "v2");
  // 预期: conj(1+2i) * (3+4i) = (1-2i) * (3+4i) = 11 - 2i
  
  CHECK_VEC_REAL(v8, 11.0);
  CHECK_VEC_IMAG(v9, -2.0);
  
  // 更多测试: NaN, rounding, mask...
}
```

#### 7. Benchmark 集成

`sw/spatzBenchmarks/dp-ccorr/` (新 benchmark):
```c
// Complex correlation: sum += conj(x[i]) * y[i]
cdouble ccorr(const cdouble *x, const cdouble *y, unsigned int n) {
#if SPATZ_USE_VFCJMACC
    // 使用 vfcjmacc
    asm volatile("vfcjmacc.vv v16, v0, v8");
#else
    // 使用 4条 FMA
    // ...
#endif
}
```

---

## 推荐的指令扩展优先级

基于 PLAN.md 的路线图：

### Phase 1: 完善现有指令（当前）
- ✅ vfcmacc.vv - 已实现
- 🔄 专用硬件优化 - 设计完成，待实施

### Phase 2: 共轭变体（v1.5）
**vfcjmacc.vv** - Conjugate multiply-accumulate
```
result = c + conj(a) * b
```
**用途**: 复数相关、频域滤波、通信信号处理

**实施成本**: 
- 软件路径: 1-2天
- 硬件优化: +1周（在 Complex FMA 单元中添加模式）

### Phase 3: 纯乘法（v2）
**vfcmul.vv** - Complex multiply (无累加)
```
result = a * b
```
**用途**: 频域乘法、相位调制

**实施成本**:
- 软件路径: 1天
- 硬件优化: 0周（复用 Complex FMA，c=0）

### Phase 4: 标量-向量形式（v3）
**vfcmacc.vf** - Complex scalar-vector FMA
```
vd[i] = vd[i] + fs1 * vs2[i]  (fs1 是复数标量)
```
**用途**: BLAS Level 2（向量缩放）

**实施成本**:
- 软件路径: 1周
- 硬件优化: 2-3周（需要标量寄存器接口）

### Phase 5: 专用变换（v4）
**FFT butterfly** 或 **rotation** 指令

**实施成本**: 2-3月（高度专用化）

---

## 快速添加新指令的模板

### 最小化实施（软件路径）

只需修改 **3个文件**：

1. **Opcode 定义** (`sw/toolchain-patches/riscv-opcodes/*.patch`)
2. **Decoder** (`hw/ip/spatz/src/spatz_decoder.sv`)
3. **Software wrapper** (benchmark 中添加 `.insn` 宏)

**时间**: 1-2天

### 完整实施（硬件优化）

需要修改 **6-8个文件**：

1-3. 同上
4. Controller (`spatz_controller.sv`)
5. FPU Sequencer (`spatz_fpu_sequencer.sv`)
6. Complex FMA unit (`fpnew_complex_fma.sv`)
7. ISA tests (`sw/riscvTests/isa/rv64uv/*.c`)
8. Benchmarks (`sw/spatzBenchmarks/*/`)

**时间**: 1-2周（如果硬件单元已存在）

---

## vfcmacc 的当前价值总结

| 层面 | 价值 |
|------|------|
| **ISA 层** | 定义了复数指令的编码空间和语义规范 |
| **RTL 层** | 验证了 Spatz 支持复数指令的可行性 |
| **软件层** | Benchmark 和测试框架可复用 |
| **研究层** | 量化了性能基线和优化空间 |

**关键点**: vfcmacc 不是"无用"的，它是：
- ✅ **MVP** (Minimum Viable Product) - 功能完整
- ✅ **基准** - 硬件优化的对照组
- ✅ **基石** - 未来指令的模板

---

## 建议

**短期（1-2周）**:
1. 实施专用 Complex FMA 硬件单元
2. 验证 vfcmacc 性能提升到 40%

**中期（1-2月）**:
1. 添加 vfcjmacc.vv（只需软件路径）
2. 添加 vfcmul.vv（几乎零成本）
3. 扩展 benchmarks（ccorr, fft-butterfly）

**长期（3-6月）**:
1. 标量-向量形式（vfcmacc.vf）
2. 编译器自动向量化支持
3. 完整的复数 BLAS 库

---

**结论**: vfcmacc 已经奠定了基础，现在的重点是**硬件优化**让它真正发挥价值，然后**扩展指令集**覆盖更多应用场景。
