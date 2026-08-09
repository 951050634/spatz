# P16 — Final Hardware Result Table

数据来源：P0-6（正式 standalone area，3-trial 确定）、P7（timing-driven
standalone critical delay / estimated Fmax）、P9–P11（derived
iso-frequency latency / throughput / incremental-SMU area efficiency）。A1
Proposed is Scalar SMU + existing RVV; A2 is the Full-Offload Ablation.  The
common 81.0186 MHz frequency is an assumption for derived performance, not a
measured cluster frequency.

| Metric | Baseline B2R | A1 Proposed: Scalar SMU + RVV | A2 Full-Offload Ablation |
| --- | ---: | ---: | ---: |
| P0-6 standalone mapped cells (SMU increment) | – | 73,505 | 107,372 |
| P0-6 standalone mapped area (SMU increment, Liberty units) | – | 77,103.3 | 114,713.3 |
| P7 standalone critical delay (pre-layout ABC, ps) | n/a | 12,342.9 | 13,202.6 |
| P7 estimated standalone Fmax (MHz) | n/a | 81.02 | 75.74 |
| BERT derived latency (us, 81.0186 MHz iso-frequency) | 256.5 | **51.0** | 95.1 |
| Mistral derived latency (us, 81.0186 MHz iso-frequency) | 734.4 | **158.8** | 428.6 |
| Qwen14B derived latency (us, 81.0186 MHz iso-frequency) | 926.0 | **194.2** | 533.3 |
| Derived iso-frequency throughput geomean (MElements/s) | 4.52 | **21.72** | 9.05 |
| Incremental-SMU area efficiency geomean (ME/s / norm-area) | n/a | **21.72** | 6.08 |

关键比率：

- Speedup over B2R（baseline cycles/design cycles，iso-frequency）：**A1
  4.81×**，A2 2.00×。A1 的 exact geomean is 4.806510911×。
- A1 的 standalone mapped area 为 77,103.3 Liberty units，A2 为
  114,713.3 units；A2 mapped area is +48.8%, and A1 is 32.8% smaller.
- A1/A2 derived iso-frequency throughput is 2.40×；incremental-SMU area
  efficiency is 3.57×。
- A2 的 vector datapath gives Cv=8.03 versus A1 Cv=2.13 (P2); this is the
  Full-Offload ablation evidence, not a cluster-area claim.

Cluster mapped area/overhead, cluster critical delay/Fmax, physical area,
signoff timing, power, and energy remain unavailable (P6/P8).

CSV：`experiments/parsed/p16/p16_hardware_results.csv`（脚本
`experiments/scripts/make_p16_table.py`）。
