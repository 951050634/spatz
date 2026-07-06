# 实现专用 Complex FMA 硬件的路径

## 当前架构

**现状**: vfcmacc 通过 **4条独立的 FMA** 串行执行：
```
1. vfmacc  v16, v0, v8   # real_acc += xr * yr
2. vfnmsac v16, v4, v12  # real_acc -= xi * yi
3. vfmacc  v20, v0, v12  # imag_acc += xr * yi  
4. vfmacc  v20, v4, v8   # imag_acc += xi * yr
```

**瓶颈**:
- 4个 FPU operation 串行执行
- Conservative fence 阻止并行
- 无法利用复数运算的并行性

---

## 专用硬件方案

### 方案 1: 复用现有 FPU，移除 Fence（快速，中等收益）

**修改点**:
- `hw/ip/spatz/src/spatz_decoder.sv` - 移除 VFCMADD 的 serialization fence
- `hw/ip/spatz/src/spatz_vfu.sv` - 允许 4个 FMA 并行发射

**收益**: ~1.5-2x（4条指令可并行执行）

**工作量**: 1-2周
- 修改 scoreboard hazard 检测
- 验证 register dependency tracking
- 确保 real/imag pairs 的 WAR/WAW hazard 正确处理

---

### 方案 2: 专用 Complex FMA Datapath（最佳，需要新硬件）

**新增模块**: `hw/ip/fpnew/src/fpnew_complex_fma.sv`

**核心思路**: 
单个 complex FMA 单元同时计算 real 和 imag：

```systemverilog
// 输入: a (complex), b (complex), c (complex)
// 输出: c + a * b (复数乘加)

// 并行计算:
real_out = c.real + (a.real * b.real - a.imag * b.imag)
imag_out = c.imag + (a.real * b.imag + a.imag * b.real)

// 需要 6个 FP multiplier + 4个 FP adder
// 可复用现有 FMA 单元的部分逻辑
```

**架构**:
```
                    ┌──────────────────────┐
                    │  Complex FMA Unit    │
  a.real ───────────┤                      │
  a.imag ───────────┤  ┌────────────────┐  │───── real_out
  b.real ───────────┤  │ 4x FP Multiply │  │
  b.imag ───────────┤  └────────┬───────┘  │
  c.real ───────────┤           │          │
  c.imag ───────────┤  ┌────────▼───────┐  │───── imag_out
                    │  │ 4x FP Add/Sub  │  │
                    │  └────────────────┘  │
                    └──────────────────────┘
```

**收益**: ~3-4x（真正的单周期复数 FMA）

**工作量**: 2-3个月
1. **新增 fpnew operation** (~2周)
   - 修改 `hw/ip/fpnew/src/fpnew_pkg.sv` 添加 `CFMA` operation
   - 实现 `fpnew_complex_fma.sv` 模块
   - 验证 rounding、NaN、Inf 处理

2. **集成到 Spatz VFU** (~3周)
   - 修改 `spatz_vfu.sv` 识别 VFCMADD operation
   - 路由到新的 complex FMA 单元
   - 处理 paired register groups (vd, vd+LMUL)

3. **验证** (~3-4周)
   - 扩展 ISA tests 覆盖 edge cases
   - RTL simulation
   - 功耗/面积分析

---

### 方案 3: 混合方案（推荐起步）

**阶段 1**: 移除 fence（1-2周） → 1.5-2x 提升  
**阶段 2**: 专用 datapath（2-3月） → 额外 2x 提升

**总收益**: 3-4x，分阶段交付

---

## 关键技术挑战

### 1. FP Multiplier 数量
- 现有 FPU: 通常每个 lane 1个 FMA 单元
- Complex FMA: 需要 **4个并行乘法器**
- **解决**: 时分复用（2 cycle latency）或增加硬件

### 2. Register Bandwidth
- 需要同时读取 6个操作数 (a.real, a.imag, b.real, b.imag, c.real, c.imag)
- 写回 2个结果 (c.real, c.imag)
- **解决**: 分两拍读取，或增加 VRF 端口

### 3. Rounding Mode
- 4个独立的 FP 操作需要一致的 rounding
- **解决**: 在最后的 add 阶段统一 round

---

## 实现优先级

**短期（1-2周）**: 
- ✅ 移除 conservative fence
- 验证并行执行正确性

**中期（1-2月）**:
- 设计 Complex FMA 单元
- 集成到 fpnew

**长期（3-6月）**:
- 优化面积/功耗
- 添加更多复数指令（conjugate, multiply）

---

## 投入产出比

| 方案 | 工作量 | 性能提升 | 面积成本 | 推荐度 |
|------|--------|----------|----------|--------|
| 移除 fence | 1-2周 | 1.5-2x | 0% | ⭐⭐⭐⭐⭐ |
| 专用硬件 | 2-3月 | 3-4x | +20-30% | ⭐⭐⭐⭐ |
| 完整优化 | 6月+ | 4-5x | +30-40% | ⭐⭐⭐ |

**建议**: 先移除 fence 快速验证收益，再决定是否投入专用硬件。
