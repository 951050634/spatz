# P9–P11 — Latency / Throughput / Area Efficiency

频率口径见 P8：iso-frequency `f_iso = 81.0186 MHz`（= Proposed standalone Fmax，
pre-layout ABC）。`Latency = cycles / f`；`Throughput = N·D / Latency`；
`AE = Throughput / normalized area`（面积 = standalone incremental mapped area，
P0-6 精确值；Proposed = 1.0，Full = 1.4878，B2R 无 SMU 增量 → AE n/a）。

## P9 — 真实 Latency（iso-frequency，us）

| Workload | Design | Cycles | Latency (us) |
| --- | --- | ---: | ---: |
| BERT (12,64) | B2R / Proposed / Full | 20,785 / 4,128 / 7,704 | 256.5 / 51.0 / 95.1 |
| Mistral (32,128) | B2R / Proposed / Full | 59,500 / 12,866 / 34,728 | 734.4 / 158.8 / 428.6 |
| Qwen14B (40,128) | B2R / Proposed / Full | 75,027 / 15,733 / 43,206 | 926.0 / 194.2 / 533.3 |

## P10 — Throughput（MElements/s）

| Workload | B2R | Proposed | Full |
| --- | ---: | ---: | ---: |
| BERT | 2.99 | **15.07** | 8.08 |
| Mistral | 5.58 | **25.79** | 9.56 |
| Qwen14B | 5.53 | **26.37** | 9.60 |

## P11 — Area Efficiency（MElements/s / normalized area）

| Workload | Proposed (area=1.0) | Full (area=1.488) | AE 比 |
| --- | ---: | ---: | ---: |
| BERT | **15.07** | 5.43 | 2.78× |
| Mistral | **25.79** | 6.42 | 4.02× |
| Qwen14B | **26.37** | 6.45 | 4.09× |

## 结论

- Speedup over B2R（iso-frequency = cycle ratio）：Proposed 4.62–5.04×；
  Full 1.71–2.70×。Proposed 在 BERT 上 5.0×、Mistral/Qwen 约 4.6–4.8×。
- Proposed 面积更小（1.0 vs 1.488）且更快，area efficiency 比 Full 高
  **2.8–4.1×**——正是 TCAS-II 期望的"小加速器 + 好划分"证据。

## 数据文件
- `experiments/parsed/p9_p11/p9_latency.csv`
- `experiments/parsed/p9_p11/p10_throughput.csv`
- `experiments/parsed/p9_p11/p11_area_efficiency.csv`
- 生成脚本：`experiments/scripts/derive_p9_p11_metrics.py`
