# Final Scaling Model (M3 frozen M2 evidence)

来源：Sol 审查通过的 M2 matched-LUT 正式数据 （`experiments/parsed/m2/m2_scaling.csv`、`experiments/parsed/m2/m2_workloads.csv`）。每条 `(N,D)` 使用 M2 正式 measured cycle row；拟合形式 `C(N,D) = C0 + Cs·N + Cv·N·D`，复用 `analyze_scaling.fit_model`（精确最小二乘）。

## 拟合参数

| Design | Points | C0 | Cs / row | Cv / element | R² |
| --- | ---: | ---: | ---: | ---: | ---: |
| B2R_RVV | 23 | 161.35 | 1471.82 | 2.267 | 0.999802230 |
| A1_SMU_SCALAR | 23 | 1382.77 | 90.28 | 2.126 | 0.999275821 |
| A2_SMU_FULL | 23 | 1285.58 | 19.32 | 8.029 | 0.999987011 |

## 解释

- Proposed A1：`Cs = 90.278155` cycles/row，相对 B2R 的 `1471.818713` 降低 `16.303154×`（SMU-like）。
- Proposed A1：`Cv = 2.126010` cycles/element，与 B2R 的 `2.267063` 基本一致（RVV-like），而 Full 的 `8.029465` 更高。
- 即 `Cs(A1) ≈ SMU-like` 且 `Cv(A1) ≈ RVV-like`，验证了 Selective scalar offloading 的执行边界。

## Crossover（拟合模型求解 C_X = C_Y）

| Pair | N | D_crossover |
| --- | ---: | ---: |
| B2R_RVV vs A1_SMU_SCALAR | 1 | — |
| A1_SMU_SCALAR vs A2_SMU_FULL | 1 | 28.5 |
| B2R_RVV vs A2_SMU_FULL | 1 | 57.0 |
| B2R_RVV vs A1_SMU_SCALAR | 2 | — |
| A1_SMU_SCALAR vs A2_SMU_FULL | 2 | 20.3 |
| B2R_RVV vs A2_SMU_FULL | 2 | 154.5 |
| B2R_RVV vs A1_SMU_SCALAR | 4 | — |
| A1_SMU_SCALAR vs A2_SMU_FULL | 4 | 16.1 |
| B2R_RVV vs A2_SMU_FULL | 4 | 203.3 |
| B2R_RVV vs A1_SMU_SCALAR | 8 | — |
| A1_SMU_SCALAR vs A2_SMU_FULL | 8 | 14.1 |
| B2R_RVV vs A2_SMU_FULL | 8 | 227.7 |
| B2R_RVV vs A1_SMU_SCALAR | 16 | — |
| A1_SMU_SCALAR vs A2_SMU_FULL | 16 | 13.0 |
| B2R_RVV vs A2_SMU_FULL | 16 | 239.9 |
| B2R_RVV vs A1_SMU_SCALAR | 32 | — |
| A1_SMU_SCALAR vs A2_SMU_FULL | 32 | 12.5 |
| B2R_RVV vs A2_SMU_FULL | 32 | 246.0 |

## Model-derived workload 预测 vs 实测（M2）

| Workload | N | D | Config | 实测 cycles | 模型预测 | 残差 |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| BERT | 12 | 64 | B2R_RVV | 19856 | 19564 | +292 |
| BERT | 12 | 64 | A1_SMU_SCALAR | 4128 | 4099 | +29 |
| BERT | 12 | 64 | A2_SMU_FULL | 7704 | 7684 | +20 |
| Mistral | 32 | 128 | B2R_RVV | 56296 | 56545 | -249 |
| Mistral | 32 | 128 | A1_SMU_SCALAR | 12866 | 12980 | -114 |
| Mistral | 32 | 128 | A2_SMU_FULL | 34728 | 34792 | -64 |
| Qwen14B | 40 | 128 | B2R_RVV | 69348 | 70641 | -1293 |
| Qwen14B | 40 | 128 | A1_SMU_SCALAR | 15733 | 15879 | -146 |
| Qwen14B | 40 | 128 | A2_SMU_FULL | 43206 | 43169 | +37 |

## 数据文件

- CSV：`experiments/parsed/final_scaling_model.csv`
