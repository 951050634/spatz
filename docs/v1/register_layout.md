# vfcmacc.vv 寄存器布局与编码参考

本文件由 `scripts/cfma_register_layout.py` 生成。寄存器布局策略以该脚本为
decoder 和 ISA test 的单一来源，避免 RTL 与测试各自解释。

## v1 编码决策

`vfcmacc.vv` 使用 32-bit RVV OPFVV 形式：

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

正式 mnemonic 支持完成前，bring-up 应使用以下 `.insn` 形式：

```asm
.insn r 0x57, 0x1, 0x75, vd, vs1, vs2  # vm=1
```

即时冲突检查会把该 pattern 与计划中列出的当前 Snitch 生成 pattern 对比：

| 既有 pattern | Pattern | 是否冲突 |
| --- | --- | --- |
| `VFMACC_VV` | `32'b101100???????????001?????1010111` | 否 |
| `VFNMSAC_VV` | `32'b101111???????????001?????1010111` | 否 |
| `VFWDOTP_VF` | `32'b111011???????????101?????1010111` | 否 |
| `VFWDOTP_VV` | `32'b111011???????????001?????1010111` | 否 |

## v1 布局策略

- `LMUL=m1/m2/m4` 在所有 base register 对齐，且成对 real+imag group
  均落在 `v0..v31` 内时合法。
- `LMUL=m8` 在 v1 中非法。单个复数操作数会消耗全部 32 个 vector
  registers，按 v1 策略无法再留下互不重叠的 destination/source pairs。
- `base % LMUL != 0` 时非法。
- `base + 2 * LMUL - 1 >= 32` 时非法。
- `vd` pair 与任一 source pair 重叠时，在 v1 中非法。
- `vs1` pair 可以与 `vs2` pair 重叠。

## 汇总

| LMUL | 合法 base 数 | 非法 base 数 |
| --- | ---: | ---: |
| m1 | 31 | 1 |
| m2 | 15 | 17 |
| m4 | 7 | 25 |
| m8 | 0 | 32 |

## 完整基址表

| LMUL | base | real group 范围 | imag group 范围 | 对齐结果 | 范围结果 | v1 合法性 | 非法原因 |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| m1 | v0 | v0 | v1 | 通过 | 通过 | 合法 | - |
| m1 | v1 | v1 | v2 | 通过 | 通过 | 合法 | - |
| m1 | v2 | v2 | v3 | 通过 | 通过 | 合法 | - |
| m1 | v3 | v3 | v4 | 通过 | 通过 | 合法 | - |
| m1 | v4 | v4 | v5 | 通过 | 通过 | 合法 | - |
| m1 | v5 | v5 | v6 | 通过 | 通过 | 合法 | - |
| m1 | v6 | v6 | v7 | 通过 | 通过 | 合法 | - |
| m1 | v7 | v7 | v8 | 通过 | 通过 | 合法 | - |
| m1 | v8 | v8 | v9 | 通过 | 通过 | 合法 | - |
| m1 | v9 | v9 | v10 | 通过 | 通过 | 合法 | - |
| m1 | v10 | v10 | v11 | 通过 | 通过 | 合法 | - |
| m1 | v11 | v11 | v12 | 通过 | 通过 | 合法 | - |
| m1 | v12 | v12 | v13 | 通过 | 通过 | 合法 | - |
| m1 | v13 | v13 | v14 | 通过 | 通过 | 合法 | - |
| m1 | v14 | v14 | v15 | 通过 | 通过 | 合法 | - |
| m1 | v15 | v15 | v16 | 通过 | 通过 | 合法 | - |
| m1 | v16 | v16 | v17 | 通过 | 通过 | 合法 | - |
| m1 | v17 | v17 | v18 | 通过 | 通过 | 合法 | - |
| m1 | v18 | v18 | v19 | 通过 | 通过 | 合法 | - |
| m1 | v19 | v19 | v20 | 通过 | 通过 | 合法 | - |
| m1 | v20 | v20 | v21 | 通过 | 通过 | 合法 | - |
| m1 | v21 | v21 | v22 | 通过 | 通过 | 合法 | - |
| m1 | v22 | v22 | v23 | 通过 | 通过 | 合法 | - |
| m1 | v23 | v23 | v24 | 通过 | 通过 | 合法 | - |
| m1 | v24 | v24 | v25 | 通过 | 通过 | 合法 | - |
| m1 | v25 | v25 | v26 | 通过 | 通过 | 合法 | - |
| m1 | v26 | v26 | v27 | 通过 | 通过 | 合法 | - |
| m1 | v27 | v27 | v28 | 通过 | 通过 | 合法 | - |
| m1 | v28 | v28 | v29 | 通过 | 通过 | 合法 | - |
| m1 | v29 | v29 | v30 | 通过 | 通过 | 合法 | - |
| m1 | v30 | v30 | v31 | 通过 | 通过 | 合法 | - |
| m1 | v31 | v31 | v32 | 通过 | 失败 | 非法 | imag-group-out-of-range |
| m2 | v0 | v0..v1 | v2..v3 | 通过 | 通过 | 合法 | - |
| m2 | v1 | v1..v2 | v3..v4 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v2 | v2..v3 | v4..v5 | 通过 | 通过 | 合法 | - |
| m2 | v3 | v3..v4 | v5..v6 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v4 | v4..v5 | v6..v7 | 通过 | 通过 | 合法 | - |
| m2 | v5 | v5..v6 | v7..v8 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v6 | v6..v7 | v8..v9 | 通过 | 通过 | 合法 | - |
| m2 | v7 | v7..v8 | v9..v10 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v8 | v8..v9 | v10..v11 | 通过 | 通过 | 合法 | - |
| m2 | v9 | v9..v10 | v11..v12 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v10 | v10..v11 | v12..v13 | 通过 | 通过 | 合法 | - |
| m2 | v11 | v11..v12 | v13..v14 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v12 | v12..v13 | v14..v15 | 通过 | 通过 | 合法 | - |
| m2 | v13 | v13..v14 | v15..v16 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v14 | v14..v15 | v16..v17 | 通过 | 通过 | 合法 | - |
| m2 | v15 | v15..v16 | v17..v18 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v16 | v16..v17 | v18..v19 | 通过 | 通过 | 合法 | - |
| m2 | v17 | v17..v18 | v19..v20 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v18 | v18..v19 | v20..v21 | 通过 | 通过 | 合法 | - |
| m2 | v19 | v19..v20 | v21..v22 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v20 | v20..v21 | v22..v23 | 通过 | 通过 | 合法 | - |
| m2 | v21 | v21..v22 | v23..v24 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v22 | v22..v23 | v24..v25 | 通过 | 通过 | 合法 | - |
| m2 | v23 | v23..v24 | v25..v26 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v24 | v24..v25 | v26..v27 | 通过 | 通过 | 合法 | - |
| m2 | v25 | v25..v26 | v27..v28 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v26 | v26..v27 | v28..v29 | 通过 | 通过 | 合法 | - |
| m2 | v27 | v27..v28 | v29..v30 | 失败 | 通过 | 非法 | misaligned-base |
| m2 | v28 | v28..v29 | v30..v31 | 通过 | 通过 | 合法 | - |
| m2 | v29 | v29..v30 | v31..v32 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m2 | v30 | v30..v31 | v32..v33 | 通过 | 失败 | 非法 | imag-group-out-of-range |
| m2 | v31 | v31..v32 | v33..v34 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m4 | v0 | v0..v3 | v4..v7 | 通过 | 通过 | 合法 | - |
| m4 | v1 | v1..v4 | v5..v8 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v2 | v2..v5 | v6..v9 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v3 | v3..v6 | v7..v10 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v4 | v4..v7 | v8..v11 | 通过 | 通过 | 合法 | - |
| m4 | v5 | v5..v8 | v9..v12 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v6 | v6..v9 | v10..v13 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v7 | v7..v10 | v11..v14 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v8 | v8..v11 | v12..v15 | 通过 | 通过 | 合法 | - |
| m4 | v9 | v9..v12 | v13..v16 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v10 | v10..v13 | v14..v17 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v11 | v11..v14 | v15..v18 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v12 | v12..v15 | v16..v19 | 通过 | 通过 | 合法 | - |
| m4 | v13 | v13..v16 | v17..v20 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v14 | v14..v17 | v18..v21 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v15 | v15..v18 | v19..v22 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v16 | v16..v19 | v20..v23 | 通过 | 通过 | 合法 | - |
| m4 | v17 | v17..v20 | v21..v24 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v18 | v18..v21 | v22..v25 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v19 | v19..v22 | v23..v26 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v20 | v20..v23 | v24..v27 | 通过 | 通过 | 合法 | - |
| m4 | v21 | v21..v24 | v25..v28 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v22 | v22..v25 | v26..v29 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v23 | v23..v26 | v27..v30 | 失败 | 通过 | 非法 | misaligned-base |
| m4 | v24 | v24..v27 | v28..v31 | 通过 | 通过 | 合法 | - |
| m4 | v25 | v25..v28 | v29..v32 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m4 | v26 | v26..v29 | v30..v33 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m4 | v27 | v27..v30 | v31..v34 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m4 | v28 | v28..v31 | v32..v35 | 通过 | 失败 | 非法 | imag-group-out-of-range |
| m4 | v29 | v29..v32 | v33..v36 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m4 | v30 | v30..v33 | v34..v37 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m4 | v31 | v31..v34 | v35..v38 | 失败 | 失败 | 非法 | misaligned-base,imag-group-out-of-range |
| m8 | v0 | v0..v7 | v8..v15 | 通过 | 通过 | 非法 | m8-disabled-v1 |
| m8 | v1 | v1..v8 | v9..v16 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v2 | v2..v9 | v10..v17 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v3 | v3..v10 | v11..v18 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v4 | v4..v11 | v12..v19 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v5 | v5..v12 | v13..v20 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v6 | v6..v13 | v14..v21 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v7 | v7..v14 | v15..v22 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v8 | v8..v15 | v16..v23 | 通过 | 通过 | 非法 | m8-disabled-v1 |
| m8 | v9 | v9..v16 | v17..v24 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v10 | v10..v17 | v18..v25 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v11 | v11..v18 | v19..v26 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v12 | v12..v19 | v20..v27 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v13 | v13..v20 | v21..v28 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v14 | v14..v21 | v22..v29 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v15 | v15..v22 | v23..v30 | 失败 | 通过 | 非法 | m8-disabled-v1,misaligned-base |
| m8 | v16 | v16..v23 | v24..v31 | 通过 | 通过 | 非法 | m8-disabled-v1 |
| m8 | v17 | v17..v24 | v25..v32 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v18 | v18..v25 | v26..v33 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v19 | v19..v26 | v27..v34 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v20 | v20..v27 | v28..v35 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v21 | v21..v28 | v29..v36 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v22 | v22..v29 | v30..v37 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v23 | v23..v30 | v31..v38 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v24 | v24..v31 | v32..v39 | 通过 | 失败 | 非法 | m8-disabled-v1,imag-group-out-of-range |
| m8 | v25 | v25..v32 | v33..v40 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v26 | v26..v33 | v34..v41 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v27 | v27..v34 | v35..v42 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v28 | v28..v35 | v36..v43 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v29 | v29..v36 | v37..v44 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v30 | v30..v37 | v38..v45 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
| m8 | v31 | v31..v38 | v39..v46 | 失败 | 失败 | 非法 | m8-disabled-v1,misaligned-base,imag-group-out-of-range |
