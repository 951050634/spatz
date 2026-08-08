# P3 — Scalar SMU 内部 latency breakdown

来源：P0-4 正式 17 roots 中 A1_SMU_SCALAR 的 FSM observer 计数（`online_merge_update_engine.sv` 仿真专用 observer，synthesis 时被 `translate_off` 剔除）。所有 (N,D) 点逐行值确定一致（三次 trial 完全相同）。

## 每行（per-row）SMU busy 分解

| Stage (RTL FSM) | Cycles/row | 占比 | 内容 |
| --- | ---: | ---: | --- |
| LOAD_SCALAR | 13 | 54% | command accept + 4 个 scalar TCDM 读（m_old/l_old/m_tile/l_tile），每个读 req+resp 握手约 3 cycle |
| COMPUTE_SCALAR | 1 | 4% | max/delta + exp_old + exp_tile + l update：全部组合逻辑（两个 exp 为单周期 LUT 近似） |
| COMPUTE_WEIGHT | 1 | 4% | reciprocal + weight generation：单周期 LUT 近似，无需迭代 |
| STORE_SCALAR | 9 | 38% | writeback：m、l、old_weight、tile_weight 4 个 scalar 写，每个约 2 cycle |
| **SMU busy 合计** | **24** | 100% | scalar-only mode，UPDATE_VECTOR=0 |

## 结论

- SMU 硬件完成一次 scalar recurrence 只需 **24 cycles/row**：主要开销是 TCDM 标量读写（load 13 + store 9），EXP / RECIP / weight generation 全部组合逻辑单周期完成，没有多周期迭代单元。
- 对比软件 recurrence（B2R `Cs ≈ 1594 cycles/row`），硬件 scalar merge 把逐行 recurrence 开销降低 `66×`。
- 软件侧 `smu_scalar` 窗口（命令寄存器配置 + done 轮询）固定开销中位数 ≈ 1316 cycles（与 N 无关），加上 `24·N` 的 SMU busy，解释了 A1 拟合模型中的 C0 与 Cs。

## 数据文件
- CSV：`experiments/parsed/p3_smu_latency_breakdown.csv`
- 图：`experiments/plots/p3_smu_latency_breakdown.png`
