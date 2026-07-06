# CFMA v1 恢复与交接说明

**最后整理**：2026-07-07
**归档目录**：`docs/v1/`
**v1 分支**：`feature/cfma-instruction-extension`
**v2 分支**：`feature/cfma-v2-datapath`

## 1. 当前状态

v1 已作为功能正确性版本归档。当前结论：

- `vfcmacc.vv` v1 功能路径已完成。
- v1 使用四阶段 FPU 复用实现。
- dedicated CFMA datapath 仍为后续 v2 工作。
- dedicated writeback path 默认禁用。
- benchmark speedup 未声明。

## 2. 恢复阅读顺序

如果需要恢复 v1 语境，按顺序阅读：

```bash
sed -n '1,160p' docs/v1/README.md
sed -n '1,220p' docs/v1/IMPLEMENTATION_SUMMARY.md
sed -n '1,220p' docs/v1/PHASE_RESULTS.md
sed -n '1,180p' docs/v1/cfma_performance_results.md
```

## 3. 关键源码位置

| 文件 | 作用 |
| --- | --- |
| `hw/ip/spatz/src/spatz_vfu.sv` | v1 四阶段 FPU 复用路径和 guarded dedicated writeback 草稿 |
| `hw/ip/spatz/src/fpnew_complex_fma.sv` | dedicated CFMA prototype，v1 不默认启用 |
| `Bender.yml` | 硬件文件集配置 |
| `sw/riscvTests/isa/rv64uv/` | ISA regression 相关测试 |
| `sw/spatzBenchmarks/` | benchmark 相关代码 |

## 4. v1 不要误判的事项

- 不要把 dedicated path 当作 v1 结果来源。
- 不要把 Step 12 dedicated writeback 标记为完成。
- 不要声明完整 benchmark correctness。
- 不要声明 cycle speedup。
- 不要把 `dp-caxpy` 小规模 probe 当成完整性能闭环。

## 5. 后续建议

- v1 只做归档、说明修订和必要修复。
- v2 工作应在 `docs/v2/` 和 `feature/cfma-v2-datapath` 中继续。
- v2 第一项应是独立 `fpnew_complex_fma` reference/testbench，而不是直接启用现有 guarded writeback prototype。
