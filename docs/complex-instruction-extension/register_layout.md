# vfcmacc.vv Register Layout and Encoding Reference

This file is generated from `scripts/cfma_register_layout.py`. Keep the
script as the single source for decoder and ISA-test layout policy.

## v1 Encoding Decision

`vfcmacc.vv` uses the 32-bit RVV OPFVV shape:

```text
VFCMACC_VV = 32'b111010???????????001?????1010111
funct6     = 111010
vm         = instr[25]
vs2        = instr[24:20]
vs1        = instr[19:15]
funct3     = 001 (OPFVV)
vd         = instr[11:7]
opcode     = 1010111 (OP-V)
```

Bring-up before mnemonic support should use this `.insn` shape:

```asm
.insn r 0x57, 0x1, 0x75, vd, vs1, vs2  # vm=1
```

The immediate conflict check compares the proposed pattern against the
current generated Snitch patterns named by the plan:

| Existing pattern | Pattern | Overlap |
| --- | --- | --- |
| `VFMACC_VV` | `32'b101100???????????001?????1010111` | false |
| `VFNMSAC_VV` | `32'b101111???????????001?????1010111` | false |
| `VFWDOTP_VF` | `32'b111011???????????101?????1010111` | false |
| `VFWDOTP_VV` | `32'b111011???????????001?????1010111` | false |

## v1 Layout Policy

- `LMUL=m1/m2/m4` are legal when every base register is aligned and the
  paired real+imag group fits in `v0..v31`.
- `LMUL=m8` is illegal in v1. A single complex operand consumes all 32
  vector registers, leaving no non-overlapping destination/source pairs
  for `vfcmacc.vv` under the v1 policy.
- `base % LMUL != 0` is illegal.
- `base + 2 * LMUL - 1 >= 32` is illegal.
- `vd` pair overlap with either source pair is illegal in v1.
- `vs1` pair may overlap `vs2` pair.

## Summary

| LMUL | Legal bases | Illegal bases |
| --- | ---: | ---: |
| m1 | 31 | 1 |
| m2 | 15 | 17 |
| m4 | 7 | 25 |
| m8 | 0 | 32 |

## Full Base Table

| LMUL | base | real group range | imag group range | alignment result | range result | v1 legality | illegal reason |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| m1 | v0 | v0 | v1 | pass | pass | legal | - |
| m1 | v1 | v1 | v2 | pass | pass | legal | - |
| m1 | v2 | v2 | v3 | pass | pass | legal | - |
| m1 | v3 | v3 | v4 | pass | pass | legal | - |
| m1 | v4 | v4 | v5 | pass | pass | legal | - |
| m1 | v5 | v5 | v6 | pass | pass | legal | - |
| m1 | v6 | v6 | v7 | pass | pass | legal | - |
| m1 | v7 | v7 | v8 | pass | pass | legal | - |
| m1 | v8 | v8 | v9 | pass | pass | legal | - |
| m1 | v9 | v9 | v10 | pass | pass | legal | - |
| m1 | v10 | v10 | v11 | pass | pass | legal | - |
| m1 | v11 | v11 | v12 | pass | pass | legal | - |
| m1 | v12 | v12 | v13 | pass | pass | legal | - |
| m1 | v13 | v13 | v14 | pass | pass | legal | - |
| m1 | v14 | v14 | v15 | pass | pass | legal | - |
| m1 | v15 | v15 | v16 | pass | pass | legal | - |
| m1 | v16 | v16 | v17 | pass | pass | legal | - |
| m1 | v17 | v17 | v18 | pass | pass | legal | - |
| m1 | v18 | v18 | v19 | pass | pass | legal | - |
| m1 | v19 | v19 | v20 | pass | pass | legal | - |
| m1 | v20 | v20 | v21 | pass | pass | legal | - |
| m1 | v21 | v21 | v22 | pass | pass | legal | - |
| m1 | v22 | v22 | v23 | pass | pass | legal | - |
| m1 | v23 | v23 | v24 | pass | pass | legal | - |
| m1 | v24 | v24 | v25 | pass | pass | legal | - |
| m1 | v25 | v25 | v26 | pass | pass | legal | - |
| m1 | v26 | v26 | v27 | pass | pass | legal | - |
| m1 | v27 | v27 | v28 | pass | pass | legal | - |
| m1 | v28 | v28 | v29 | pass | pass | legal | - |
| m1 | v29 | v29 | v30 | pass | pass | legal | - |
| m1 | v30 | v30 | v31 | pass | pass | legal | - |
| m1 | v31 | v31 | v32 | pass | fail | illegal | imag-group-out-of-range |
| m2 | v0 | v0..v1 | v2..v3 | pass | pass | legal | - |
| m2 | v1 | v1..v2 | v3..v4 | fail | pass | illegal | misaligned-base |
| m2 | v2 | v2..v3 | v4..v5 | pass | pass | legal | - |
| m2 | v3 | v3..v4 | v5..v6 | fail | pass | illegal | misaligned-base |
| m2 | v4 | v4..v5 | v6..v7 | pass | pass | legal | - |
| m2 | v5 | v5..v6 | v7..v8 | fail | pass | illegal | misaligned-base |
| m2 | v6 | v6..v7 | v8..v9 | pass | pass | legal | - |
| m2 | v7 | v7..v8 | v9..v10 | fail | pass | illegal | misaligned-base |
| m2 | v8 | v8..v9 | v10..v11 | pass | pass | legal | - |
| m2 | v9 | v9..v10 | v11..v12 | fail | pass | illegal | misaligned-base |
| m2 | v10 | v10..v11 | v12..v13 | pass | pass | legal | - |
| m2 | v11 | v11..v12 | v13..v14 | fail | pass | illegal | misaligned-base |
| m2 | v12 | v12..v13 | v14..v15 | pass | pass | legal | - |
| m2 | v13 | v13..v14 | v15..v16 | fail | pass | illegal | misaligned-base |
| m2 | v14 | v14..v15 | v16..v17 | pass | pass | legal | - |
| m2 | v15 | v15..v16 | v17..v18 | fail | pass | illegal | misaligned-base |
| m2 | v16 | v16..v17 | v18..v19 | pass | pass | legal | - |
| m2 | v17 | v17..v18 | v19..v20 | fail | pass | illegal | misaligned-base |
| m2 | v18 | v18..v19 | v20..v21 | pass | pass | legal | - |
| m2 | v19 | v19..v20 | v21..v22 | fail | pass | illegal | misaligned-base |
| m2 | v20 | v20..v21 | v22..v23 | pass | pass | legal | - |
| m2 | v21 | v21..v22 | v23..v24 | fail | pass | illegal | misaligned-base |
| m2 | v22 | v22..v23 | v24..v25 | pass | pass | legal | - |
| m2 | v23 | v23..v24 | v25..v26 | fail | pass | illegal | misaligned-base |
| m2 | v24 | v24..v25 | v26..v27 | pass | pass | legal | - |
| m2 | v25 | v25..v26 | v27..v28 | fail | pass | illegal | misaligned-base |
| m2 | v26 | v26..v27 | v28..v29 | pass | pass | legal | - |
| m2 | v27 | v27..v28 | v29..v30 | fail | pass | illegal | misaligned-base |
| m2 | v28 | v28..v29 | v30..v31 | pass | pass | legal | - |
| m2 | v29 | v29..v30 | v31..v32 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m2 | v30 | v30..v31 | v32..v33 | pass | fail | illegal | imag-group-out-of-range |
| m2 | v31 | v31..v32 | v33..v34 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m4 | v0 | v0..v3 | v4..v7 | pass | pass | legal | - |
| m4 | v1 | v1..v4 | v5..v8 | fail | pass | illegal | misaligned-base |
| m4 | v2 | v2..v5 | v6..v9 | fail | pass | illegal | misaligned-base |
| m4 | v3 | v3..v6 | v7..v10 | fail | pass | illegal | misaligned-base |
| m4 | v4 | v4..v7 | v8..v11 | pass | pass | legal | - |
| m4 | v5 | v5..v8 | v9..v12 | fail | pass | illegal | misaligned-base |
| m4 | v6 | v6..v9 | v10..v13 | fail | pass | illegal | misaligned-base |
| m4 | v7 | v7..v10 | v11..v14 | fail | pass | illegal | misaligned-base |
| m4 | v8 | v8..v11 | v12..v15 | pass | pass | legal | - |
| m4 | v9 | v9..v12 | v13..v16 | fail | pass | illegal | misaligned-base |
| m4 | v10 | v10..v13 | v14..v17 | fail | pass | illegal | misaligned-base |
| m4 | v11 | v11..v14 | v15..v18 | fail | pass | illegal | misaligned-base |
| m4 | v12 | v12..v15 | v16..v19 | pass | pass | legal | - |
| m4 | v13 | v13..v16 | v17..v20 | fail | pass | illegal | misaligned-base |
| m4 | v14 | v14..v17 | v18..v21 | fail | pass | illegal | misaligned-base |
| m4 | v15 | v15..v18 | v19..v22 | fail | pass | illegal | misaligned-base |
| m4 | v16 | v16..v19 | v20..v23 | pass | pass | legal | - |
| m4 | v17 | v17..v20 | v21..v24 | fail | pass | illegal | misaligned-base |
| m4 | v18 | v18..v21 | v22..v25 | fail | pass | illegal | misaligned-base |
| m4 | v19 | v19..v22 | v23..v26 | fail | pass | illegal | misaligned-base |
| m4 | v20 | v20..v23 | v24..v27 | pass | pass | legal | - |
| m4 | v21 | v21..v24 | v25..v28 | fail | pass | illegal | misaligned-base |
| m4 | v22 | v22..v25 | v26..v29 | fail | pass | illegal | misaligned-base |
| m4 | v23 | v23..v26 | v27..v30 | fail | pass | illegal | misaligned-base |
| m4 | v24 | v24..v27 | v28..v31 | pass | pass | legal | - |
| m4 | v25 | v25..v28 | v29..v32 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m4 | v26 | v26..v29 | v30..v33 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m4 | v27 | v27..v30 | v31..v34 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m4 | v28 | v28..v31 | v32..v35 | pass | fail | illegal | imag-group-out-of-range |
| m4 | v29 | v29..v32 | v33..v36 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m4 | v30 | v30..v33 | v34..v37 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m4 | v31 | v31..v34 | v35..v38 | fail | fail | illegal | misaligned-base,imag-group-out-of-range |
| m8 | v0 | v0..v7 | v8..v15 | pass | pass | illegal | m8-disabled-v1 |
| m8 | v1 | v1..v8 | v9..v16 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v2 | v2..v9 | v10..v17 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v3 | v3..v10 | v11..v18 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v4 | v4..v11 | v12..v19 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v5 | v5..v12 | v13..v20 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v6 | v6..v13 | v14..v21 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v7 | v7..v14 | v15..v22 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v8 | v8..v15 | v16..v23 | pass | pass | illegal | m8-disabled-v1 |
| m8 | v9 | v9..v16 | v17..v24 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v10 | v10..v17 | v18..v25 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v11 | v11..v18 | v19..v26 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v12 | v12..v19 | v20..v27 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v13 | v13..v20 | v21..v28 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v14 | v14..v21 | v22..v29 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v15 | v15..v22 | v23..v30 | fail | pass | illegal | m8-disabled-v1,misaligned-base |
| m8 | v16 | v16..v23 | v24..v31 | pass | pass | illegal | m8-disabled-v1 |
| m8 | v17 | v17..v24 | v25..v32 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v18 | v18..v25 | v26..v33 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v19 | v19..v26 | v27..v34 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v20 | v20..v27 | v28..v35 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v21 | v21..v28 | v29..v36 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v22 | v22..v29 | v30..v37 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v23 | v23..v30 | v31..v38 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v24 | v24..v31 | v32..v39 | pass | fail | illegal | m8-disabled-v1,imag-group-out-of-range |
| m8 | v25 | v25..v32 | v33..v40 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v26 | v26..v33 | v34..v41 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v27 | v27..v34 | v35..v42 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v28 | v28..v35 | v36..v43 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v29 | v29..v36 | v37..v44 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v30 | v30..v37 | v38..v45 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v31 | v31..v38 | v39..v46 | fail | fail | illegal | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
