# CFMA v1 冻结计划

本文件记录 v1 已冻结的设计边界。它不再作为继续实施 dedicated datapath 的计划使用；v2 计划见 `docs/v2/`。

## 1. v1 目标

在 Spatz 上新增一条软件可见的复数向量 FMA 指令：

```text
vfcmacc.vv vd, vs1, vs2
```

语义：

```text
vd.real += vs1.real * vs2.real - vs1.imag * vs2.imag
vd.imag += vs1.real * vs2.imag + vs1.imag * vs2.real
```

v1 的优先目标是功能正确、语义清楚、可回归验证。

## 2. v1 默认决策

| 决策项 | v1 决策 |
| --- | --- |
| 实现路径 | 四阶段 FPU 复用 |
| dedicated datapath | 不纳入 v1 默认路径 |
| 软件使用 | inline assembly 可用即可 |
| 性能目标 | 降低指令数和前端压力；不承诺 FPU 吞吐提升 |
| rounding/fflags | 与四条 reference FPU 操作保持一致，fflags OR 后暴露 |
| completion | 每条架构指令只产生一次 architectural completion |

## 3. 寄存器布局

复数向量使用 paired register group：

```text
vs1.real = vs1_base
vs1.imag = vs1_base + LMUL
vs2.real = vs2_base
vs2.imag = vs2_base + LMUL
vd.real  = vd_base
vd.imag  = vd_base + LMUL
```

v1 默认：

- `LMUL=m1/m2/m4` 可在 alignment/range 合法时使用；
- `LMUL=m8` illegal；
- real/imag group 越界 illegal；
- destination pair 与 source pair 的非法 overlap 需要被拒绝。

## 4. v1 微架构

VFU 内部使用四个 CFMA phase：

```text
Cfma_RR -> Cfma_II -> Cfma_RI -> Cfma_IR
```

含义：

| Phase | 计算 | FPU op |
| --- | --- | --- |
| `Cfma_RR` | `vd.real += vs1.real * vs2.real` | `FMADD` |
| `Cfma_II` | `vd.real -= vs1.imag * vs2.imag` | `FNMSUB` |
| `Cfma_RI` | `vd.imag += vs1.imag * vs2.real` | `FMADD` |
| `Cfma_IR` | `vd.imag += vs1.real * vs2.imag` | `FMADD` |

该方案复用现有 FPU、VRF 读写和 result tag/writeback 机制。

## 5. 测试矩阵

v1 必测：

- legal/illegal layout；
- e16/e32/e64；
- mask/tail；
- `vstart != 0` illegal；
- fflags；
- NaN/Inf/zero 等特殊值；
- back-to-back `vfcmacc.vv`；
- `vfcmacc.vv` 与普通 vector 指令之间的 real/imag hazard；
- 邻近 FMA 指令回归。

## 6. 性能记录标准

v1 只允许声明：

- 软件可见指令数从 4 条 reference FMA/FNMSUB 折叠为 1 条 `vfcmacc.vv`；
- fetch/decode/offload/issue queue 压力下降是设计目标。

v1 不允许在没有完整 benchmark 证据时声明：

- cycle speedup；
- dedicated hardware speedup；
- `dp-cdotp` 完整 correctness；
- 面积/功耗收益。

## 7. v1 归档结论

v1 已完成“功能正确性版本”目标。后续 dedicated datapath、scoreboard 优化和性能闭环应作为 v2 工作继续。
