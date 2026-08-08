# Final Scaling Model (P2)

来源：P0-4 正式 scaling 数据（`experiments/parsed/p0_4/p0_4_scaling_points.csv`），每条 `(N,D)` 取一个确定 median（三次 trial 完全一致）。拟合形式 `C(N,D) = C0 + Cs·N + Cv·N·D`，复用 `analyze_scaling.fit_model`（精确最小二乘）。

## 拟合参数

| Design | Points | C0 | Cs / row | Cv / element | R² |
| --- | ---: | ---: | ---: | ---: | ---: |
| B2R_RVV | 23 | 153.48 | 1594.23 | 2.087 | 0.999946203 |
| A1_SMU_SCALAR | 23 | 1382.77 | 90.28 | 2.126 | 0.999275821 |
| A2_SMU_FULL | 23 | 1285.58 | 19.32 | 8.029 | 0.999987011 |

## 解释

- Proposed A1：`Cs = 90.3` cycles/row，相对 B2R 的 `1594.2` 降低 `17.7×`（SMU-like）。
- Proposed A1：`Cv = 2.13` cycles/element，与 B2R 的 `2.09` 基本一致（RVV-like），而 Full 的 `8.03` 更高。
- 即 `Cs(A1) ≈ SMU-like` 且 `Cv(A1) ≈ RVV-like`，验证了 Selective scalar offloading 的执行边界。

## Crossover（拟合模型求解 C_X = C_Y）

| Pair | N | D_crossover |
| --- | ---: | ---: |
| B2R_RVV vs A1_SMU_SCALAR | 1 | 6984.3 |
| A1_SMU_SCALAR vs A2_SMU_FULL | 1 | 28.5 |
| B2R_RVV vs A2_SMU_FULL | 1 | 74.5 |
| B2R_RVV vs A1_SMU_SCALAR | 2 | 22613.9 |
| A1_SMU_SCALAR vs A2_SMU_FULL | 2 | 20.3 |
| B2R_RVV vs A2_SMU_FULL | 2 | 169.8 |
| B2R_RVV vs A1_SMU_SCALAR | 4 | 30428.8 |
| A1_SMU_SCALAR vs A2_SMU_FULL | 4 | 16.1 |
| B2R_RVV vs A2_SMU_FULL | 4 | 217.4 |
| B2R_RVV vs A1_SMU_SCALAR | 8 | 34336.2 |
| A1_SMU_SCALAR vs A2_SMU_FULL | 8 | 14.1 |
| B2R_RVV vs A2_SMU_FULL | 8 | 241.2 |
| B2R_RVV vs A1_SMU_SCALAR | 16 | 36289.9 |
| A1_SMU_SCALAR vs A2_SMU_FULL | 16 | 13.0 |
| B2R_RVV vs A2_SMU_FULL | 16 | 253.1 |
| B2R_RVV vs A1_SMU_SCALAR | 32 | 37266.7 |
| A1_SMU_SCALAR vs A2_SMU_FULL | 32 | 12.5 |
| B2R_RVV vs A2_SMU_FULL | 32 | 259.1 |

方向（谁更好）：
- **B2R vs A1**：crossover D 极大（N=1 时 D≈6984 且随 N 增大），全部实际工作点（D≤512）A1 恒优于 B2R。
- **A1 vs FULL**：N=1 时 crossover D≈28.5；D<28.5 时 Full 略好（对应实测 anchor (1,1) 的 0.94×），D>28.5 时 A1 更好；N≥8 时 crossover D≤14，即中大规模下 A1 几乎恒优于 Full。
- **B2R vs FULL**：N=1 时 D≈74.5；Full 在中高 D 时反而不如 B2R（Full 的 Cv=8.03 太贵）。

## Model-derived workload 预测 vs 实测（P0-5）

| Workload | N | D | Config | 实测 cycles | 模型预测 | 残差 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| BERT | 12 | 64 | B2R_RVV | 20785 | 20887 | -102 |
| BERT | 12 | 64 | A1_SMU_SCALAR | 4128 | 4099 | +29 |
| BERT | 12 | 64 | A2_SMU_FULL | 7704 | 7684 | +20 |
| Mistral | 32 | 128 | B2R_RVV | 59500 | 59716 | -216 |
| Mistral | 32 | 128 | A1_SMU_SCALAR | 12866 | 12980 | -114 |
| Mistral | 32 | 128 | A2_SMU_FULL | 34728 | 34792 | -64 |
| Qwen14B | 40 | 128 | B2R_RVV | 75027 | 74607 | +420 |
| Qwen14B | 40 | 128 | A1_SMU_SCALAR | 15733 | 15879 | -146 |
| Qwen14B | 40 | 128 | A2_SMU_FULL | 43206 | 43169 | +37 |

## 数据文件

- CSV：`experiments/parsed/final_scaling_model.csv`
