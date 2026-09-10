# Correctness

## Exact matched-pair evidence

| Case | Words | Hash, both paths | Output bits SHA-256, both paths | MAE | Stable-rel | Cosine | Non-finite |
|---|---:|---|---|---:|---:|---:|---:|
| N8/D32 | 256 | `0x9c7cdedc` | `40a462b87d57684aaa93be1f3daef39ff779770271ab84cabcd2628102043ed0` | 0 | 0 | 1 | 0 |
| N16/D64 | 1,024 | `0xfd0d2cff` | `19bdf06bb7745d641da824dbe3adc88e1c017e431d3390dd31f20d9fd82a4892` | 0 | 0 | 1 | 0 |

Both pairs are word-for-word identical. Configuration-state hashes also match
within each pair:

- N8/D32: `31a112541234a811901899f55413724b33811aac8b09921b7082a0bb3762a89a`
- N16/D64: `9d07df611b831de36d6e0811b9a78c218923fe2e5f46205992d1f71feadcfd24`

## Raw-log integrity

| Formal run | Raw-log SHA-256 |
|---|---|
| N8 MMIO | `5d8bd958892a8f6fd5ba66cbca9c74536fffae39613b294fab717f5b240164a7` |
| N8 OMCFG | `b6be5348a331985d7cfbaf6436b23396ab98e5238364fd6dfc3d119508918f1c` |
| N16 MMIO | `56cff6489ad924ff2af6a1d368ee7f6689c441a9507be2ee197b4a485c398b65` |
| N16 OMCFG | `bc4062b38a0908bbf438c3e981c02d0589e46849511c45a957f538afde99fd52` |

All formal runs completed once in the mandated order. The first postprocessor
pass incorrectly required a dot/norm recomputation for an already identical
N16 vector to equal the literal float64 value 1.0; it produced
`1.0000000000000002`. The correction maps exact bit identity to its exact
mathematical cosine, 1.0. No tolerance was relaxed, no formal case was rerun,
and the four raw-log hashes above remained unchanged. This event is recorded
in `manifest.json` under `postprocessing_correction`.
