# CFMA v1 文档归档

本目录归档 Spatz 平台 `vfcmacc.vv` 复数浮点乘加指令的 v1 工作成果。

v1 的定位是：**完成一条软件可见的复数 FMA 指令，并用已有四阶段 FPU 复用路径保证功能正确性**。
它不是 dedicated complex-FMA datapath 的完成版本，也不声明完整 benchmark speedup。

## 1. 当前结论

| 项目 | v1 状态 |
| --- | --- |
| 指令 | `vfcmacc.vv` |
| ISA 语义 | `vd += vs1 * vs2`，按 real/imag paired register group 表示复数向量 |
| 硬件实现 | Spatz VFU 内部四阶段复用已有 FPU 路径 |
| 专用 datapath | 有 prototype/草稿，但默认禁用，不作为 v1 结果来源 |
| 功能验证 | `vfcmacc` RTL regression 已通过，邻近 `vfmacc`/`vfnmsac` 回归通过 |
| 性能结论 | 只声明指令数和前端压力下降；不声明完整 benchmark speedup |
| 归档状态 | v1 可作为功能正确性版本归档 |

## 2. v1 做了什么

v1 完成以下内容：

- 确定 `vfcmacc.vv` custom encoding。
- 接入 Snitch/Spatz decode。
- 定义 paired vector register layout：
  - `vs1.real = vs1`，`vs1.imag = vs1 + LMUL`；
  - `vs2.real = vs2`，`vs2.imag = vs2 + LMUL`；
  - `vd.real = vd`，`vd.imag = vd + LMUL`。
- 定义并验证 v1 合法/非法策略。
- 支持 e16/e32/e64 行为。
- 覆盖 mask、tail、`vstart != 0` illegal 策略。
- 覆盖 fflags 累积行为。
- 使用 conservative serialization/fence 保护隐式 real/imag register dependency。
- 通过 inline assembly 路径进行软件使用；完整 LLVM mnemonic/objdump 支持不作为 v1 硬门槛。

## 3. v1 没有做什么

以下事项不属于 v1 完成范围：

- 默认启用 dedicated complex-FMA datapath。
- 证明 `fpnew_complex_fma` dedicated path correctness。
- 证明 dedicated split VRF writeback correctness。
- 完整 benchmark correctness 和 speedup。
- 面积、功耗、时序收敛评估。
- LLVM 自动选择、完整 register allocator 支持。
- `vfcmacc.vf`、conjugate、rotation、butterfly 等扩展变体。

## 4. 推荐阅读顺序

1. [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)：v1 最终实现总结。
2. [RESUME_INFO.md](RESUME_INFO.md)：恢复和交接信息。
3. [PHASE_RESULTS.md](PHASE_RESULTS.md)：阶段结果和验证证据。
4. [cfma_performance_results.md](cfma_performance_results.md)：性能和 benchmark 证据边界。
5. [PLAN.md](PLAN.md)：v1 冻结计划和设计边界。
6. [complex_fma_hardware_design.md](complex_fma_hardware_design.md)：硬件实现说明和 dedicated path 风险。
7. [register_layout.md](register_layout.md)：寄存器布局表和合法性规则。
8. [toolchain_mnemonic_status.md](toolchain_mnemonic_status.md)：工具链 mnemonic 支持状态。

## 5. 后续路线

v1 后续不应继续扩大范围。若要继续做性能优化或 dedicated datapath，请转到：

```text
docs/v2/
```

v2 应从独立 `fpnew_complex_fma` reference/testbench 开始，而不是直接启用 v1 中保留的 guarded writeback prototype。

## 6. 验证命令记录原则

涉及 RTL、opcode、decode、benchmark 或 ISA 行为的修改时，应记录：

- 命令；
- 开始/结束时间；
- 退出码；
- 关键输出摘要；
- 不能完成或超时时的实际失败证据。

长时间编译或仿真不能作为跳过验证的理由。
