# CFMA v1 硬件设计归档

本文件是 v1 归档版硬件设计说明。v1 的正式功能路径是四阶段 FPU 复用；dedicated complex-FMA datapath 只作为后续 v2 参考。

## 1. v1 硬件目标

v1 目标是在不大幅改动 Spatz/FPnew 数据通路的前提下，实现软件可见的：

```text
vfcmacc.vv vd, vs1, vs2
```

并满足：

- ISA 行为正确；
- mask/tail/fflags 行为可验证；
- 每条架构指令只完成一次；
- 不暴露中间 partial writeback；
- 不默认启用未验证 dedicated hardware。

## 2. 四阶段 FPU 复用路径

v1 在 `spatz_vfu.sv` 中引入 CFMA phase：

```text
Cfma_RR, Cfma_II, Cfma_RI, Cfma_IR
```

四阶段含义：

| Phase | 输入选择 | 写回目标 | FPU 操作 |
| --- | --- | --- | --- |
| `Cfma_RR` | `vs1.real * vs2.real + vd.real` | `vd.real` | `FMADD` |
| `Cfma_II` | `vd.real - vs1.imag * vs2.imag` | `vd.real` | `FNMSUB` |
| `Cfma_RI` | `vs1.imag * vs2.real + vd.imag` | `vd.imag` | `FMADD` |
| `Cfma_IR` | `vs1.real * vs2.imag + vd.imag` | `vd.imag` | `FMADD` |

RTL 通过当前 phase 对 `vs1`、`vs2`、`vd` 加 LMUL offset，从 paired register group 中选择 real 或 imag group。

## 3. 寄存器布局

```text
vs1.real = vs1
vs1.imag = vs1 + LMUL
vs2.real = vs2
vs2.imag = vs2 + LMUL
vd.real  = vd
vd.imag  = vd + LMUL
```

合法性规则见 [register_layout.md](register_layout.md)。

## 4. 专用原型状态

当前 RTL 中保留 dedicated CFMA prototype 和 split writeback FSM 草稿，但默认禁用：

```systemverilog
localparam bit CfmaDedicatedWritebackEn = 1'b0;
```

禁用原因：

- dynamic FP format 选择没有独立证明；
- e16/e32 packed lane 语义没有独立证明；
- complex arithmetic/status flags 没有完整 reference/testbench；
- mask/tail byte enable 没有在 dedicated path 启用模式下闭环；
- response timing/backpressure 没有闭环；
- VRF writeback arbitration 没有在 dedicated mode 下证明。

因此 dedicated prototype 不能作为 v1 correctness 或 performance 证据。

## 5. v1 验证结论

v1 已记录：

```text
git diff --check: PASS
bin/spatz_cluster.vlt build: PASS
sw.vlt build: PASS
riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac): PASS
```

该证据证明 v1 四阶段路径可用，不证明 dedicated datapath 可启用。

## 6. 给 v2 的设计建议

v2 应从以下顺序开始：

1. 建立 `fpnew_complex_fma` 独立 reference/testbench。
2. 冻结 arithmetic、rounding、fflags 行为。
3. 明确 Spatz VFU request/response contract。
4. 实现六操作数分拍读取。
5. 实现 real/imag split writeback 并独立验证 byte enable 和仲裁。
6. dedicated mode 通过 ISA regression 后，才考虑设为默认路径。

详细 v2 计划见 `docs/v2/README.md`。
