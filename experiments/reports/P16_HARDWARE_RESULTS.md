# P16 — 最终 Hardware Result Table

数据来源：P0-6（面积，3-trial 确定）、P7（timing/Fmax）、P9–P11（latency /
throughput / area efficiency）。Baseline（B2R）不新增 SMU 硬件，因此 cells /
area / Fmax 为 n/a；latency 与 throughput 与 Proposed 同用 iso-frequency
（81.02 MHz，见 P8）以隔离 cycle 效果。

| Metric | Baseline (B2R) | Proposed Scalar SMU | Full SMU |
| --- | ---: | ---: | ---: |
| Mapped cells（SMU 增量） | – | 73,505 | 107,372 |
| Mapped area（SMU 增量, Liberty units） | – | 77,103.3 | 114,713.3 |
| Cluster area overhead | – | ≤ 77.1k cells（上界） | ≤ 114.7k cells（上界） |
| Critical delay（ps, pre-layout ABC） | n/a | 12,342.9 | 13,202.6 |
| Fmax（MHz） | n/a | 81.02 | 75.74 |
| BERT latency（us, iso-freq） | 256.5 | **51.0** | 95.1 |
| Mistral latency（us, iso-freq） | 734.4 | **158.8** | 428.6 |
| Qwen14B latency（us, iso-freq） | 926.0 | **194.2** | 533.3 |
| Throughput geomean（MElements/s） | 4.52 | **21.72** | 9.05 |
| Area efficiency geomean（ME/s / norm-area） | n/a | **21.72** | 6.08 |

关键比率：

- Speedup over B2R（iso-freq，geomean）：**Proposed 4.80×**，Full 2.00×。
- Proposed 比 Full：面积小 33%（77.1k vs 114.7k），throughput 高 2.40×
  （21.72 vs 9.05 MElements/s），**area efficiency 高 3.57×**。
- Full 的 vector datapath 额外增加 +48.8% standalone area，但 throughput 反而
  低于 Proposed（Cv=8.03 vs 2.13，见 P2）。

CSV：`experiments/parsed/p16/p16_hardware_results.csv`（脚本
`experiments/scripts/make_p16_table.py`）。
