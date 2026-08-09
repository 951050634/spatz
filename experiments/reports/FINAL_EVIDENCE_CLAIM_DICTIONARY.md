# Final evidence and claim dictionary

This file is the binding vocabulary for the evaluation artifacts.  `A1` is
the proposed design: Scalar SMU plus the existing RVV path.  `A2` is retained
only as the Full-Offload ablation.

## Evidence and allowed wording

| Claim | Evidence source | Allowed wording | Forbidden wording | Precision |
| --- | --- | --- | --- | --- |
| Scaling fit | `parsed/final_scaling_model.csv` | fitted cycle terms `C0`, `Cs/row`, and `Cv/element` | treating fit terms as measured wall time or SMU busy cycles | source: B2R `Cs=1594.233808`, `Cv=2.086684`; A1 `Cs=90.278155`, `Cv=2.126010`; A2 `Cs=19.317262`, `Cv=8.029465`; display 1594.23/2.09, 90.28/2.13, 19.32/8.03 |
| Workload cycles | `parsed/final_scaling_model.csv` and P0-5 records | measured model-derived-shape cycles; speedup = baseline cycles/design cycles | measured wall latency or system throughput | BERT 20785/4128/7704; Mistral 59500/12866/34728; Qwen14B 75027/15733/43206; A1 speedups 5.04×/4.62×/4.77×; geomean 4.806510911×, display 4.81× |
| A1 FSM busy | `parsed/p3_smu_latency_breakdown.csv` | 24 SMU busy cycles = 13+1+1+9; 22/24 are TCDM communication | equating 24 cycles with fitted `Cs=90.28` | exact integer counts |
| Formal standalone area | `parsed/p0_6/p0_6_synthesis_summary.csv` | P0-6 standalone mapped cells and Liberty cell-area units | physical/layout area, cluster area, or P7 timing-flow area as formal area | A1 73,505 cells / 77,103.292 Liberty units; A2 107,372 cells / 114,713.298 units |
| Standalone timing | `parsed/p7_timing/p7_timing.csv` | P7 timing-driven standalone critical delay and estimated standalone Fmax | formal area, cluster critical delay/Fmax, signoff timing, upper bound, or achievable cluster frequency | A1 12,342.85 ps / 81.0186 MHz; A2 13,202.60 ps / 75.7427 MHz |
| Derived performance | `parsed/p9_p11/*.csv` | derived latency/throughput under a common 81.0186 MHz iso-frequency assumption | real/measured latency, measured system throughput, or per-design wall time | report the common assumption explicitly |
| Area efficiency | `parsed/p9_p11/p11_area_efficiency.csv` | incremental-SMU A1-vs-A2 area efficiency | cluster/system efficiency or baseline efficiency with an invented area | exact displays: A1/A2 throughput 2.40×; incremental-SMU area efficiency 3.57× |

## Availability matrix

| Evidence item | Status | Required boundary |
| --- | --- | --- |
| P0-6 standalone SMU mapped cells/area | Available | Formal area values are P0-6 only |
| P7 standalone critical delay/estimated Fmax | Available | Timing-flow cells/area are not formal area |
| Cluster mapped area/overhead | Unavailable | Do not report numeric cluster overhead |
| Cluster critical delay/Fmax | Unavailable | Do not call standalone Fmax a cluster limit or achievable frequency |
| Physical/layout area, signoff timing, power, energy | Unavailable | No derived substitute claim |
| Latency/throughput | Derived only | Common 81.0186 MHz iso-frequency assumption; not wall-time/system measurements |
