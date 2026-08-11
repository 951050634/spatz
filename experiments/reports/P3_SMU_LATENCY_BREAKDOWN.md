# P3 — Scalar SMU 内部 latency breakdown

来源：P0-4 正式 17 roots 中 A1_SMU_SCALAR 的 FSM observer 计数（`online_merge_update_engine.sv` 仿真专用 observer，synthesis 时被 `translate_off` 剔除）。该计数是 nominal no-stall state schedule；model-shape observers additionally include occasional TCDM wait cycles。

## 每行（per-row）SMU busy 分解

| Stage (RTL FSM) | Cycles/row | 占比 | 内容 |
| --- | ---: | ---: | --- |
| LOAD_SCALAR | 13 | 54% | command accept + 4 个 scalar TCDM 读（m_old/l_old/m_tile/l_tile），每个读 req+resp 握手约 3 cycle |
| COMPUTE_SCALAR | 1 | 4% | max/delta + exp_old + exp_tile + l update：全部组合逻辑（两个 exp 为单周期 LUT 近似） |
| COMPUTE_WEIGHT | 1 | 4% | reciprocal + weight generation：单周期 LUT 近似，无需迭代 |
| STORE_SCALAR | 9 | 38% | writeback：m、l、old_weight、tile_weight 4 个 scalar 写，每个约 2 cycle |
| **Nominal no-stall SMU busy total** | **24** | 100% | scalar-only mode，UPDATE_VECTOR=0 |

## 结论

- `13+1+1+9` is the nominal no-stall state schedule, not a measured system
  latency for each row. Model-shape observers report 289 cycles for BERT,
  769 for Mistral, and 962 for Qwen2.5-14B-Instruct, corresponding to one or
  two TCDM wait cycles beyond `24·N`.
- The software `smu_scalar` window includes command setup and done polling.
  These observer counts remain separate from fitted `C0`, fitted N-dependent
  `Cs`, and measured merge-kernel cycles.

## 数据文件
- CSV：`experiments/parsed/p3_smu_latency_breakdown.csv`
- 图：`experiments/plots/p3_smu_latency_breakdown.png`
