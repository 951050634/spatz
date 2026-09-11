# Negative Results and Boundaries

## Explicit-P Softmax control — retained negative result

This Phase 4 experiment holds the surrounding quantized-attention path fixed and
replaces only an explicit-P software Softmax backend with the frozen Mixed SMU
backend. Mixed's complete Softmax window includes explicit P initialization, every
SMU launch/poll, RVV probability update, and swap/clear orchestration.

### Performance

| Shape | Metric | Software explicit-P | Mixed SMU | Result |
|---|---|---:|---:|---|
| N8/D32 | Softmax | 12,502 | 14,812 | Mixed +2,310 cycles, **18.477% slower** |
| N8/D32 | five-stage Attention Total | 839,111 | 841,597 | Mixed +2,486, 0.296% slower |
| N8/D32 | raw measured total | 931,920 | 934,412 | Mixed +2,492, 0.267% slower |
| N16/D64 | Softmax | 48,595 | 48,534 | Mixed −61 cycles, **0.126% faster** |
| N16/D64 | five-stage Attention Total | 6,767,387 | 6,768,406 | Mixed +1,019, 0.015% slower |
| N16/D64 | raw measured total | 7,134,015 | 7,135,062 | Mixed +1,047, 0.015% slower |

The QKV Linear stage is approximately 81.3% and 85.9% of the software raw window
for N8 and N16, respectively. This explains why a Softmax-only change has little
effect on the wider measured window; it does not turn the negative result positive.

### Numerical agreement

| Shape | P MAE (host) | P cosine (host) | O MAE (host) | O cosine (host) | Direct-device P/O MAE |
|---|---:|---:|---:|---:|---|
| N8/D32 | 9.01923e-4 | 0.999960077 | 5.22701e-4 | 0.999953092 | 9.02078e-4 / 5.22663e-4 |
| N16/D64 | 4.74585e-4 | 0.999957064 | 6.14677e-4 | 0.999950108 | 4.74481e-4 / 6.14540e-4 |

Host float64 cosine is authoritative. Target-side cosine uses approximate target
sqrt/reciprocal and is diagnostic only.

## Exact conclusion

> **SMU is not a generic row-wise Softmax replacement.**

The two anchors do not support a uniform explicit-P Softmax speedup, and both wider
attention windows are slightly slower. The accelerator's positive result instead
depends on matching the Native Online Attention dataflow: persistent normalized
state plus a scalar recurrence in hardware, with the dimension-dependent output
update left on RVV.

## Contrast with native dataflow

| Dataflow | Relevant result | Supported inference |
|---|---|---|
| explicit P materialization | −18.477% at N8, +0.126% at N16 Softmax; wider totals slower | no generic/uniform Softmax speedup |
| Native Online Attention | recurrence 8.524–17.784×, merge 4.144–6.275×, Native Core 1.066–1.157× over B2R across four shapes | selective acceleration is beneficial in this measured native recurrence/dataflow |

The contrast supports a dataflow-matching claim, not a claim that any one numerical
kernel is universally faster.

Primary sources:

- `experiments/phase4_softmax_ablation/report.md`
- `experiments/phase4_softmax_ablation/results/cycles.csv`
- `experiments/phase4_softmax_ablation/results/numerical.csv`
- `experiments/phase4_softmax_ablation/results/device_numerical.csv`
- `experiments/phase4_softmax_ablation/results/system_logs/`
- Phase 5/6 formal performance CSVs for the native contrast

## Other negative or incomplete evidence

| Item | Status | Boundary |
|---|---|---|
| cluster-level matched PPA | `BLOCKED_RESOURCE` | official r3/r4 OOM at techmap; no mapped statistic |
| N32/D64 native shape | `NOT MEASURED` | rejected before formal collection under host-completion criterion |
| stress cosine >0.9999 | `UNSUPPORTED` | measured minimum is 0.999873853 |
| Phase 7 component hashes/MAEs | `NOT MEASURED` | recovery records contain final-O dumps but not intermediate arrays |
| OMERGE no-trace validation | `NOT MEASURED` / deferred | active formal recovery is trace-enabled |
| multihart/concurrent MMIO-ISA/interrupt/flush | `NOT MEASURED` | outside Phase 7/8 validation |
| full-model acceleration | `NOT MEASURED` | kernels/native core only |
