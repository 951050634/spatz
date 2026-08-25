# Phase-1 Scalar SMU Online-Softmax Validation

This folder is a self-contained NumPy validation and RTL handoff record for
the repository's actual Scalar SMU contract. It does not modify B1, B2-R, B3,
or the experiment infrastructure.

Run the smoke case:

```sh
python3 experiments/phase1_online_softmax/run_validation.py \
  --smoke --output-dir /tmp/phase1-online-softmax-smoke
```

Run the full matrix:

```sh
python3 experiments/phase1_online_softmax/run_validation.py \
  --output-dir experiments/phase1_online_softmax/results
```

Both random-score and single-head `Attention(QK^T)V` workloads cover sequence
lengths 128/256/512/1024 and head dimensions 64/128 in a full run. Every case
is partitioned into non-singleton 32-element tiles. Each tile forms
`(m_tile, l_tile, O_tile)`; the Scalar SMU merge consumes old/tile summaries and
emits `m_new`, `l_new`, `w_old`, and `w_tile`; a separate RVV-equivalent vector
update then updates the probability and attention-output state.

The primary models are:

1. `fp32`: FP32 summary, merge, normalization, and vector update;
2. `fp16`: explicit FP16 input/max/exp/length recurrence/normalization/vector update;
3. `mixed`: FP16 score/max/delta, direct signed-INT16 exponential LUT over
   `[-8,0]`, FP32 lengths and scaled-length products, FP16 numerator/denominator
   weight normalization, and FP32 vector update after widening FP16 weights.

For the proposed path, V/O remain FP32. `mixed_exact_exp` is diagnostic-only:
it keeps every mixed stage unchanged and replaces only the LUT lookup with
exact FP32 `exp` of the FP16 delta. `mixed_rtl_exact` is a second diagnostic
handoff row: it uses the frozen LUT plus Q16.32 conversion/product
truncation/addition/fixed-to-FP32 length recurrence and the same FP16 divide.
Neither diagnostic is a fourth primary model; the high-level `mixed` row keeps
the Phase-1 abstract FP32 length recurrence. The local 32-element tile
construction of `mixed_rtl_exact` is explicitly a system-level diagnostic
assumption because the RTL handoff contract is scalar-summary based. The
report and `summary.json` also contain frozen scalar-interface vectors with
input bits, Q16.32 exp products, `l_new`, FP16 weight bits, and widened FP32
bits; the first vector is asserted by the focused RTL engine TB.

The direct LUT sweep covers 64/128/256 entries and Q10/Q12/Q14. Every candidate
uses signed 16-bit storage (`ROM bits = entries * 16`); Q bits do not fake an
area difference. The input address scale is `entries/8`; each bin has one
INT16 code and there is no interpolation. Calibration, validation, and final-
test cases use independent seeds for every score scale, length, dimension, and
repetition. A candidate must pass the validation per-case worst-error threshold
before it can be selected; the independent final-test split is reported but is
not used for selection. The current validation gate is `1.5e-2`. The selected
256-entry Q1.14 image is exported in `summary.json` and has raw little-endian
INT16 SHA-256
`3ea4629839c7341f1d40b388b444d1d4ae8adf4fefccd2d36e5876f6eb49df30`.

All model rows are compared with an independent FP64 softmax/attention oracle:

```text
MAE = mean(abs(actual - oracle))
stable_relative_error = sum(abs(actual - oracle)) /
                       max(sum(abs(oracle)), 1e-12)
cosine_similarity = dot(actual, oracle) /
                    (norm(actual) * norm(oracle))
probability_sum_error = abs(sum(probability) - 1)
```

Outputs:

- `results.csv` / `results.json`: primary and both diagnostic workload rows;
- `lut_sweep.csv` / `lut_sweep.json`: one row per LUT configuration;
- `lut_sweep_cases.csv` / `lut_sweep_cases.json`: per-case calibration,
  validation, and final-test errors and seeds;
- `boundary.csv` / `boundary.json`: equal/near-tie, `delta=-8`, below-range,
  single-sided zero-length, and small/unequal-length Scalar SMU cases;
- `summary.json`, `manifest.json`, and `report.md`: structured provenance and
  separate random/QKTV, exact-exp, LUT, and boundary summaries.
- `rtl_pruning_smoke.json`: pre-flatten Yosys evidence for the four fixed
  Scalar synthesis tops (generate pruning and one 256x16 mixed ROM path;
  not a formal multi-trial area result).

This remains a host numerical gate for accuracy. The companion focused RTL TB
reports mixed `COMPUTE_WEIGHT` cycles (78 for two serialized divider calls in
the current implementation), but this folder does not claim area, timing,
power, target-FPU flush-to-zero behavior, or full-system integration.
