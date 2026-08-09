# P9–P11 — Derived Latency / Throughput / Area Efficiency

Cluster-level timing is unavailable (P8).  Therefore `f_iso = 81.0186 MHz`
is a common iso-frequency **assumption**, equal to the A1 estimated standalone
Fmax from P7.  `Derived latency = cycles / f_iso` and
`Derived throughput = N·D / derived latency`; neither is measured wall time or
system throughput.  Area efficiency uses only incremental standalone SMU area
from P0-6: A1 = 1.0, A2 = 1.4878, and B2R has no SMU increment.

## P9 — Derived iso-frequency latency (us)

| Workload | Design | Measured cycles | Derived latency (us) |
| --- | --- | ---: | ---: |
| BERT (12,64) | B2R / A1 / A2 | 20,785 / 4,128 / 7,704 | 256.5 / 51.0 / 95.1 |
| Mistral (32,128) | B2R / A1 / A2 | 59,500 / 12,866 / 34,728 | 734.4 / 158.8 / 428.6 |
| Qwen14B (40,128) | B2R / A1 / A2 | 75,027 / 15,733 / 43,206 | 926.0 / 194.2 / 533.3 |

## P10 — Derived iso-frequency throughput (MElements/s)

| Workload | B2R | A1 Proposed (Scalar SMU + RVV) | A2 Full-Offload Ablation |
| --- | ---: | ---: | ---: |
| BERT | 2.99 | **15.07** | 8.08 |
| Mistral | 5.58 | **25.79** | 9.56 |
| Qwen14B | 5.53 | **26.37** | 9.60 |

## P11 — Incremental-SMU area efficiency

| Workload | A1 (area=1.0) | A2 (area=1.488) | A1/A2 efficiency ratio |
| --- | ---: | ---: | ---: |
| BERT | **15.07** | 5.43 | 2.78× |
| Mistral | **25.79** | 6.42 | 4.02× |
| Qwen14B | **26.37** | 6.45 | 4.09× |

## Conclusion

Speedup over B2R is baseline cycles/design cycles because the common
iso-frequency factor cancels: A1 is 5.04× / 4.62× / 4.77× on BERT / Mistral /
Qwen14B, with exact geomean 4.806510911× (display 4.81×).  A1 is smaller and
faster than A2 in this incremental-SMU comparison; its area-efficiency
advantage is 2.8–4.1× across the three workloads.

## Data files

- `experiments/parsed/p9_p11/p9_latency.csv`
- `experiments/parsed/p9_p11/p10_throughput.csv`
- `experiments/parsed/p9_p11/p11_area_efficiency.csv`
- Generator: `experiments/scripts/derive_p9_p11_metrics.py`
