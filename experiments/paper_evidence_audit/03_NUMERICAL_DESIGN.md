# Frozen Numerical / Mixed-Precision Design

## Correct positioning

The final datapath is **stage-aware mixed precision** / **hardware-aware precision
allocation**. It is not runtime-adaptive mixed precision. Legacy, division, and
reciprocal branches are elaboration/configuration choices; data values do not cause
runtime precision selection.

## Stage allocation

| Stage | Frozen representation / mechanism | Evidence |
|---|---|---|
| external state carrier | FP32 `m`, `l`, old/tile weights in TCDM; FP32 O/V for RVV | engine RTL; Phase 1 manifest |
| max / diff | FP32 inputs converted to FP16 with RNE; FP16 compare and subtraction | `online_merge_update_engine.sv`; FP helpers |
| EXP | one 256×16-bit signed Q1.14 ROM over `[-8,0]`; direct bin selection, no interpolation | `online_merge_exp_approx.sv` |
| winner handling | exact winner bypass to unity; equal converted maxima give both unity; loser uses the sole physical EXP LUT | engine RTL |
| recurrence / accumulation | external FP32 `l` converted to 48-bit unsigned Q16.32 carrier; Q1.23 exponent product; scaled terms summed in Q16.32 | engine + `online_merge_fp32_helpers.sv` |
| reciprocal denominator | Q16.32 `l_new` rounded directly to FP16 (RNE), then widened for reciprocal approximation | engine RTL |
| reciprocal | 256×16-bit Q1.15 ROM with piecewise-linear interpolation and exponent correction | `online_merge_recip_approx.sv` |
| normalization numerator | selected Q16.32 scaled-l rounded to FP16 RNE, then represented as Q16.32 | engine RTL |
| weight product | one shared 48×16 multiplier reused for old/tile numerator × reciprocal; Q16.32 result with exponent shift | engine RTL |
| returned weight | rounded to FP16, widened/stored as FP32 for the RVV carrier | engine RTL |
| O update | unchanged FP32 RVV path | native benchmark / RVV helper |

The RTL typedef is historically named `uq16_16_t`, but it is 48 bits with
`UQ_FRAC_BITS=32`; its actual format is Q16.32. Paper text should use the actual
format and may note the legacy identifier only when pointing to code.

## EXP approximation

- input domain: non-positive FP16 difference;
- 256 entries, each signed INT16/Q1.14 (`4096` source ROM bits);
- direct lookup with no interpolation;
- difference ≥0/winner path returns exact 1; values below −8 saturate toward zero;
- one physical LUT services loser/winner selection rather than instantiating two
  independent exponent units.

The high-level Phase 1 selected EXP ROM is archived with SHA-256
`3ea4629839c7341f1d40b388b444d1d4ae8adf4fefccd2d36e5876f6eb49df30`.

## Reciprocal approximation

- denominator is a positive finite FP16 value produced from the Q16.32 recurrence;
- mantissa interval uses 256 Q1.15 ROM entries and a hardwired terminal endpoint
  `code[256]=0x4000` (0.5); `code[0]=0x8000` (1.0);
- bin endpoints are linearly interpolated; the low 15 product bits are truncated;
- exponent decomposition/correction restores the denominator scale;
- one reciprocal code/scale is latched per row and the same multiplier computes
  the two weights sequentially.

The complete positive finite FP16 denominator domain contains 31,743 values. The
selected LUT's maximum relative error is `6.696581841e-05`; the 257-point mantissa
probe maximum is `7.297017146e-05`.

## Numerical rationale

The allocation keeps externally visible state and the high-dynamic-range running
normalization carrier at FP32/Q16.32, while spending low-cost FP16/LUT arithmetic
on bounded max differences, exponentials, and normalization weights. Winner bypass
prevents avoidable error on the identity term. Reciprocal replaces a divider but
preserves an FP16-normalized contract; its error is much smaller than the existing
Mixed EXP/FP16-max approximation in the stress scan.

## Frozen numerical evidence

### Native Online Attention versus generated FP32 reference

| Shape | MAE | Stable relative error | Cosine | Nonfinite |
|---|---:|---:|---:|---:|
| N8/D32 | 2.793084e-4 | 4.884280e-3 | 0.999984541 | 0 |
| N16/D64 | 4.665494e-4 | 7.052819e-3 | 0.999970724 | 0 |
| N24/D64 | 3.736880e-4 | 6.109509e-3 | 0.999980879 | 0 |
| N16/D128 | 5.631592e-4 | 5.219446e-3 | 0.999984751 | 0 |

Source: Phase 6 formal `numerical_agreement.csv`, which includes the two unchanged
Phase 5 anchors.

### Reciprocal A/B isolation

For the reported N128/D128 random-score row, replacing the RTL-exact division
branch with reciprocal gives probability stable-relative error `5.553255834e-05`
and cosine `0.9999999613`; output stable-relative error `2.648930696e-4` and
cosine `0.9999999724`. These isolate the reciprocal change; they are not the total
Mixed-vs-FP32 error.

### Stress boundary

The selected 256-entry reciprocal design's extended optimized-vs-FP32 stress
minimum cosine is **`0.999873853`**, below 0.9999. The Phase 3 report identifies
the existing Mixed EXP/FP16-max quantization as the root-cause candidate and says
the failure cannot be assigned to the reciprocal LUT A/B error.

Paper-safe statement: “The stress minimum was 0.999873853; reciprocal-isolation
error remained much smaller, while EXP/FP16-max quantization was the primary
candidate source.”

Forbidden statement: “global cosine >0.9999” or “the reciprocal removes all
numerical loss.”

Primary sources:

- `hw/ip/online_merge/src/online_merge_update_engine.sv`
- `hw/ip/online_merge/src/online_merge_exp_approx.sv`
- `hw/ip/online_merge/src/online_merge_recip_approx.sv`
- `hw/ip/online_merge/src/online_merge_fp32_helpers.sv`
- `experiments/phase1_online_softmax/results/phase3_reciprocal_model/`
- `experiments/phase3_reciprocal_hardware/report.md`
- `experiments/phase6_integrated_cost_generality/p0_2_workload_generality/formal/numerical_agreement.csv`
