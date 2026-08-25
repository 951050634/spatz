# Phase-1 Online Softmax Validation

The primary kernel is the repository Scalar SMU contract: each 32-value
tile forms `(m_tile, l_tile, O_tile)`, the scalar block merges it with
`(m_old, l_old, O_old)` and emits `m_new`, `l_new`, `w_old`, and
`w_tile`, then a separate RVV-equivalent vector update updates
probability and attention-output state. All tiles have 32 elements, so
every end-to-end case exercises non-singleton `l_tile` values.

## Configuration

- Matrix: lengths `(128, 256, 512, 1024)` × dimensions `(64, 128)` for both random-score and single-head QK^T V workloads.
- Base seed: `20260823`; every workload/coordinate/rep uses an independent SeedSequence.
- Primary models: `fp32`, `fp16`, `mixed`. `mixed_exact_exp` is diagnostic only.
- Tile size: `32`; selected LUT: `256` entries, Q14, ROM `4096` bits.
- LUT input scale: `32.0` entries/unit; output scale: `16384`.
- Frozen selected ROM raw little-endian INT16 SHA-256: `3ea4629839c7341f1d40b388b444d1d4ae8adf4fefccd2d36e5876f6eb49df30`.
- LUT is a direct-address signed-INT16 ROM over [-8,0], with no interpolation; delta=0 is exact unity and values below -8 saturate to zero.

## Oracle and metrics

Every model is compared with an independent FP64 softmax/attention
oracle, not with the FP32 model. For flattened actual `a` and oracle
`r`, MAE is `mean(abs(a-r))`; stable-relative error is
`sum(abs(a-r)) / max(sum(abs(r)), 1e-12)`; cosine is the normalized
dot product. Probability-sum error is `abs(sum(probability)-1)`.

## Random-score matrix

| model | cases | probability MAE mean/max | probability stable-rel mean/max | probability cosine min | output MAE mean/max | output stable-rel mean/max | output cosine min | probability-sum error mean/max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fp32 | 8 | 2.863e-10 / 5.358e-10 | 8.933e-08 / 1.203e-07 | 1.000000000 | 1.059e-08 / 1.489e-08 | 1.584e-07 / 1.923e-07 | 1.000000000 | 2.984e-08 / 6.023e-08 |
| fp16 | 8 | 2.926e-06 / 7.481e-06 | 8.318e-04 / 1.083e-03 | 0.999999444 | 9.568e-05 / 1.388e-04 | 1.418e-03 / 1.875e-03 | 0.999998187 | 4.571e-04 / 9.007e-04 |
| mixed | 8 | 3.094e-05 / 6.880e-05 | 9.029e-03 / 1.045e-02 | 0.999941018 | 6.376e-04 / 9.890e-04 | 9.267e-03 / 1.122e-02 | 0.999934041 | 2.222e-04 / 4.565e-04 |

## Single-head Attention(QK^T)V matrix

QK^T is generated once in FP32 for each seeded case. Every recurrence
variant receives the same original score vector and quantizes it
inside its own tile kernel; proposed-path V/O remain FP32.

| model | cases | probability MAE mean/max | probability stable-rel mean/max | probability cosine min | output MAE mean/max | output stable-rel mean/max | output cosine min | probability-sum error mean/max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fp32 | 8 | 3.578e-10 / 8.371e-10 | 1.139e-07 / 2.017e-07 | 1.000000000 | 1.242e-08 / 1.535e-08 | 1.647e-07 / 2.399e-07 | 1.000000000 | 6.899e-08 / 1.801e-07 |
| fp16 | 8 | 2.865e-06 / 5.537e-06 | 8.352e-04 / 1.026e-03 | 0.999999261 | 1.088e-04 / 1.462e-04 | 1.395e-03 / 1.682e-03 | 0.999998723 | 4.185e-04 / 9.582e-04 |
| mixed | 8 | 3.304e-05 / 6.935e-05 | 9.548e-03 / 1.199e-02 | 0.999935093 | 7.158e-04 / 1.029e-03 | 9.231e-03 / 1.041e-02 | 0.999947004 | 2.626e-04 / 8.370e-04 |

## Diagnostics

`mixed_exact_exp` keeps FP16 score/max/delta, FP32 length/scaled
length, FP16 weight normalization, and FP32 vector update. Only
the direct LUT lookup is replaced with exact FP32 `exp` of the
FP16 delta, separating LUT error from mixed normalization error.

### Random scores

| model | cases | probability MAE mean/max | probability stable-rel mean/max | probability cosine min | output MAE mean/max | output stable-rel mean/max | output cosine min | probability-sum error mean/max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed_exact_exp | 8 | 1.949e-06 / 3.687e-06 | 6.496e-04 / 1.159e-03 | 0.999999514 | 4.521e-05 / 5.715e-05 | 7.116e-04 / 1.387e-03 | 0.999999395 | 3.933e-04 / 1.024e-03 |
| mixed_rtl_exact | 8 | 3.094e-05 / 6.880e-05 | 9.029e-03 / 1.045e-02 | 0.999941018 | 6.376e-04 / 9.890e-04 | 9.267e-03 / 1.122e-02 | 0.999934041 | 2.222e-04 / 4.565e-04 |

### QK^T V

| model | cases | probability MAE mean/max | probability stable-rel mean/max | probability cosine min | output MAE mean/max | output stable-rel mean/max | output cosine min | probability-sum error mean/max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed_exact_exp | 8 | 2.218e-06 / 4.949e-06 | 6.285e-04 / 9.036e-04 | 0.999999642 | 5.682e-05 / 1.037e-04 | 7.240e-04 / 9.423e-04 | 0.999999612 | 2.852e-04 / 5.956e-04 |
| mixed_rtl_exact | 8 | 3.304e-05 / 6.935e-05 | 9.548e-03 / 1.199e-02 | 0.999935093 | 7.158e-04 / 1.029e-03 | 9.231e-03 / 1.041e-02 | 0.999947004 | 2.626e-04 / 8.370e-04 |

### RTL-exact fixed-point diagnostic

`mixed_rtl_exact` uses FP16 m/max/delta, the frozen direct LUT,
Q16.32 conversion/product truncation/addition/fixed-to-FP32
at each length recurrence, and the same FP16 numerator/denominator
divide. It is a diagnostic handoff for the RTL carrier, not a
fourth primary model.

#### Random scores

| model | cases | probability MAE mean/max | probability stable-rel mean/max | probability cosine min | output MAE mean/max | output stable-rel mean/max | output cosine min | probability-sum error mean/max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed_rtl_exact | 8 | 3.094e-05 / 6.880e-05 | 9.029e-03 / 1.045e-02 | 0.999941018 | 6.376e-04 / 9.890e-04 | 9.267e-03 / 1.122e-02 | 0.999934041 | 2.222e-04 / 4.565e-04 |

#### QK^T V

| model | cases | probability MAE mean/max | probability stable-rel mean/max | probability cosine min | output MAE mean/max | output stable-rel mean/max | output cosine min | probability-sum error mean/max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed_rtl_exact | 8 | 3.304e-05 / 6.935e-05 | 9.548e-03 / 1.199e-02 | 0.999935093 | 7.158e-04 / 1.029e-03 | 9.231e-03 / 1.041e-02 | 0.999947004 | 2.626e-04 / 8.370e-04 |

#### Frozen scalar-interface vectors

These vectors are independently checked against the Python carrier/divider reference. The first vector is also asserted bit-for-bit by `online_merge_engine_mixed_tb.sv`; local tile construction remains a system-level diagnostic assumption.

| vector | m_new FP32 | l_new FP32 | old exp Q1.14 | tile exp Q1.14 | old weight FP16 | tile weight FP16 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| engine_mode3_1_0 | `0x3f800000` | `0x3fafd400` | `0x4000` | `0x17ea` | `0x39d3` | `0x345a` |
| equal_max_1_3 | `0x3f800000` | `0x40800000` | `0x4000` | `0x4000` | `0x3400` | `0x3a00` |

## LUT sweep and validation/final-test selection

The sweep evaluates entries `(64, 128, 256)` and Q bits `(10, 12, 14)`. Each split has independent seeds for every scale/length/dimension/rep. Selection requires validation per-case worst error ≤ `1.5e-02`, then minimizes 16-bit ROM size and validation worst error; the independent final-test split is reported but never used for selection.

| entries | q_bits | ROM bits | calibration worst | validation mean | validation worst | final-test worst | pass | selected |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | :---: |
| 64 | 10 | 1024 | 5.512e-02 | 3.994e-02 | 6.995e-02 | 5.579e-02 | no | no |
| 64 | 12 | 1024 | 5.454e-02 | 3.935e-02 | 6.878e-02 | 5.557e-02 | no | no |
| 64 | 14 | 1024 | 5.486e-02 | 3.934e-02 | 6.927e-02 | 5.576e-02 | no | no |
| 128 | 10 | 2048 | 2.843e-02 | 2.102e-02 | 3.151e-02 | 2.870e-02 | no | no |
| 128 | 12 | 2048 | 2.896e-02 | 2.021e-02 | 3.100e-02 | 2.870e-02 | no | no |
| 128 | 14 | 2048 | 2.896e-02 | 2.007e-02 | 3.089e-02 | 2.872e-02 | no | no |
| 256 | 10 | 4096 | 1.569e-02 | 1.063e-02 | 1.384e-02 | 1.473e-02 | YES | no |
| 256 | 12 | 4096 | 1.667e-02 | 9.649e-03 | 1.371e-02 | 1.461e-02 | YES | no |
| 256 | 14 | 4096 | 1.658e-02 | 9.534e-03 | 1.367e-02 | 1.478e-02 | YES | YES |

Selection status: `target_met`; selected validation worst case `1.367e-02`, final-test worst case `1.478e-02`. Per-case sweep rows are preserved in `lut_sweep_cases.csv`/`.json`.

## Scalar merge boundaries

These direct two-summary cases exercise equal/near-tie maxima,
delta=-8, below-range saturation, single-sided zero lengths, and
small/unequal lengths. The
table reports the scalar outputs and `|w_old+w_tile-1|`.

| case | model | m_new | l_new | w_old | w_tile | weight-sum error |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| equal_max | fp32 | 0 | 5 | 0.4 | 0.6 | 2.980e-08 |
| equal_max | fp16 | 0 | 5 | 0.399902 | 0.600098 | 0.000e+00 |
| equal_max | mixed | 0 | 5 | 0.399902 | 0.600098 | 0.000e+00 |
| near_tie_max | fp32 | 0 | 3.4985 | 0.571673 | 0.428327 | 2.980e-08 |
| near_tie_max | fp16 | 0 | 3.49805 | 0.571777 | 0.428223 | 0.000e+00 |
| near_tie_max | mixed | 0 | 3.47675 | 0.575195 | 0.424805 | 0.000e+00 |
| delta_minus_8 | fp32 | 0 | 1.25067 | 0.000536452 | 0.999464 | 1.048e-08 |
| delta_minus_8 | fp16 | 0 | 1.25098 | 0.000536442 | 0.999023 | 4.401e-04 |
| delta_minus_8 | mixed | 0 | 1.25073 | 0.000585556 | 0.999023 | 3.910e-04 |
| delta_below_minus_8 | fp32 | 0 | 1.25009 | 7.26346e-05 | 0.999927 | 2.346e-08 |
| delta_below_minus_8 | fp16 | 0 | 1.25 | 7.26581e-05 | 1 | 7.266e-05 |
| delta_below_minus_8 | mixed | 0 | 1.25 | 0 | 1 | 0.000e+00 |
| small_unequal_l | fp32 | 0.25 | 0.776652 | 0.160947 | 0.839053 | 1.490e-08 |
| small_unequal_l | fp16 | 0.25 | 0.776855 | 0.160889 | 0.838867 | 2.441e-04 |
| small_unequal_l | mixed | 0.25 | 0.786926 | 0.158813 | 0.841309 | 1.221e-04 |
| old_l_zero | fp32 | 0 | 1.25 | 0 | 1 | 0.000e+00 |
| old_l_zero | fp16 | 0 | 1.25 | 0 | 1 | 0.000e+00 |
| old_l_zero | mixed | 0 | 1.25 | 0 | 1 | 0.000e+00 |
| tile_l_zero | fp32 | 0 | 1.25 | 1 | 0 | 0.000e+00 |
| tile_l_zero | fp16 | 0 | 1.25 | 1 | 0 | 0.000e+00 |
| tile_l_zero | mixed | 0 | 1.25 | 1 | 0 | 0.000e+00 |

## Limitations and RTL implications

- This is host-side NumPy validation; it reports no RTL area, timing, or power. The focused RTL TB separately observes mixed weight cycles.
- FP16 baseline arithmetic is explicit NumPy FP16 at each scalar/vector stage. The proposed path keeps V/O FP32 and only weights/local score state use FP16 as specified.
- The high-level `mixed` row follows the abstract FP32 length recurrence. `mixed_rtl_exact` is the Q16.32 carrier diagnostic used for RTL handoff; its local tile construction is a system-level assumption, while the scalar-interface vectors are exact; neither diagnostic is a fourth primary model.
- The direct LUT's table encoding, address rounding, saturation, and Q format must be reproduced exactly before RTL claims are made.
- A pre-flatten Yosys generate-pruning smoke is recorded in `rtl_pruning_smoke.json`: legacy-only tops contain no mixed LUT or divider, mixed-only contains no legacy exp/reciprocal, dual contains both with one mixed-LUT hierarchy path and 4096 source ROM bits. This is not a formal multi-trial area result.
- Random cases are seeded synthetic scores/values; QK^T V is one single-query head at each matrix coordinate, not a full transformer layer.
- The selected ROM is a numerical candidate for Scalar SMU integration. Follow-up RTL work should measure the same 32-element tile schedule and validate boundary codes without changing B1/B2-R/B3.

Command: `/usr/bin/python3 experiments/phase1_online_softmax/run_validation.py --output-dir experiments/phase1_online_softmax/results`
