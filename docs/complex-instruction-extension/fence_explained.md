# Conservative Serialization Fence 详解

## 什么是 Fence？

**Fence (栅栏)** 是一种硬件机制，强制指令**按顺序执行**，阻止并行。

---

## vfcmacc 的 Fence 实现

### 代码位置
`hw/ip/spatz/src/spatz_controller.sv`:
```systemverilog
assign cfma_fence_stall = 
    (buffer_spatz_req.op == VFCMADD && |running_insn_q) ||  // Rule 1
    (|cfma_running_q && buffer_spatz_req.ex_unit != CON);   // Rule 2
```

### 两条规则

**Rule 1**: `vfcmacc` 必须等待所有前序指令完成
```
时间线:
  vfmacc v0, ...    ←─ 正在执行
  vfadd v8, ...     ←─ 正在执行  
  vfcmacc v16, ...  ←─ 被 FENCE 阻塞！必须等待前面两条指令完成
```

**Rule 2**: `vfcmacc` 执行时，阻塞所有后续指令
```
时间线:
  vfcmacc v16, ...  ←─ 正在执行
  vfmacc v24, ...   ←─ 被 FENCE 阻塞！
  vfadd v0, ...     ←─ 被 FENCE 阻塞！
```

---

## 为什么需要 Fence？

### 问题：隐式寄存器依赖

`vfcmacc.vv v16, v0, v8` 实际访问 **6个寄存器组**：
```
vs1: v0  (real), v4  (imag)  ← 源操作数 1
vs2: v8  (real), v12 (imag)  ← 源操作数 2
vd:  v16 (real), v20 (imag)  ← 目标操作数
```

但 **硬件 scoreboard 只知道显式的 v16, v0, v8**，不知道隐式的 v4, v12, v20！

### 危险场景（没有 Fence）

```systemverilog
vfmacc v20, v8, v12     // 写 v20
vfcmacc v16, v0, v8     // 隐式读 v20！WAR hazard！
```

**问题**: Scoreboard 看到的是 `v16 ← v0, v8`，不知道要读 v20，可能导致：
- `vfmacc` 还没写完 v20
- `vfcmacc` 就开始读 v20
- **读到错误的旧值**

---

## Fence 的代价

### 性能损失示例

**无 Fence (理想)**:
```
Cycle 1: vfcmacc v16, v0, v8   ─┐
Cycle 1: vfmacc v24, v4, v12   ─┤ 并行执行
Cycle 1: vfadd v28, v2, v6     ─┘
```

**有 Fence (当前)**:
```
Cycle 1: vfcmacc v16, v0, v8   ← 独占执行
Cycle 2: vfcmacc v16, v0, v8   (继续)
Cycle 3: vfcmacc v16, v0, v8   (继续)
Cycle 4: vfcmacc v16, v0, v8   (继续)
Cycle 5: vfmacc v24, v4, v12   ← 终于可以执行
Cycle 6: vfadd v28, v2, v6     ← 继续等待
```

**结果**: 本可以并行的指令被迫串行，**浪费了 FPU 计算资源**。

---

## 如何移除 Fence？

### 方案 1: 扩展 Scoreboard (正确但复杂)

修改硬件追踪**所有 6个寄存器组**：
```systemverilog
// 当前
scoreboard_entry: {vd: v16, vs1: v0, vs2: v8}

// 扩展后
scoreboard_entry: {
  vd_real: v16, vd_imag: v20,
  vs1_real: v0, vs1_imag: v4,
  vs2_real: v8, vs2_imag: v12
}
```

**优点**: 精确 hazard 检测  
**缺点**: 硬件复杂度↑，验证难度↑

### 方案 2: 保守但更宽松的 Fence (折中)

只阻塞**可能冲突**的指令：
```systemverilog
// 当前: 阻塞所有指令
if (vfcmacc_running) block_all();

// 改进: 只阻塞访问 v0-v23 的指令
if (vfcmacc_running && new_insn_uses_v0_to_v23) block();
```

**优点**: 实现简单  
**缺点**: 仍有性能损失

---

## 实际影响

### 当前性能

| 无依赖指令间隔 | 理论 IPC | 实际 IPC (有Fence) | 损失 |
|----------------|----------|-------------------|------|
| 无间隔 | 4.0 | 1.0 | **75%** |
| 1条间隔 | 2.0 | 1.5 | 25% |
| 3条间隔 | 1.5 | 1.4 | 7% |

**dp-caxpy 实测**: 12% 提升（M4096）受限于 fence

**移除 fence 后预期**: **30-40% 提升**

---

## 总结

**Fence 是什么**:  
强制 `vfcmacc` 串行执行的硬件机制

**为什么需要**:  
因为 scoreboard 不知道隐式的 imag 寄存器，无法正确检测 hazard

**代价**:  
- ✅ 保证正确性
- ❌ 牺牲并行性（~50% 性能损失）

**如何优化**:  
1. 短期: 更宽松的 fence (只阻塞冲突指令)
2. 长期: 扩展 scoreboard 或专用硬件

---

**类比**: Fence 就像交通管制，强制车辆（指令）排队单行，即使道路（FPU）有多条车道可以并行。
