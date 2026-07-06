# CFMA v1 实现总结

**归档日期**：2026-07-07
**v1 归档分支**：`feature/cfma-instruction-extension`
**v2 起始分支**：`feature/cfma-v2-datapath`

## 1. 一句话总结

CFMA v1 在 Spatz 上实现并验证了软件可见的 `vfcmacc.vv` 复数 FMA 指令；硬件内部使用已有 FPU 的四阶段复用路径完成计算，不默认启用 dedicated complex-FMA datapath。

## 2. 指令语义

`vfcmacc.vv vd, vs1, vs2` 的 v1 语义为：

```text
vd.real += vs1.real * vs2.real - vs1.imag * vs2.imag
vd.imag += vs1.real * vs2.imag + vs1.imag * vs2.real
```

复数向量使用 paired register group：

```text
real group = base
imag group = base + LMUL
```

## 3. v1 硬件路径

v1 没有把 `vfcmacc.vv` 映射为单个 dedicated complex-FMA datapath。当前功能路径是：

```text
一条软件可见 vfcmacc.vv
  -> Spatz VFU 内部 Cfma_RR
  -> Spatz VFU 内部 Cfma_II
  -> Spatz VFU 内部 Cfma_RI
  -> Spatz VFU 内部 Cfma_IR
  -> 整条架构指令完成
```

四个 phase 分别复用已有 FPU：

| Phase | 作用 | FPU 操作 |
| --- | --- | --- |
| `Cfma_RR` | `vd.real += vs1.real * vs2.real` | `FMADD` |
| `Cfma_II` | `vd.real -= vs1.imag * vs2.imag` | `FNMSUB` |
| `Cfma_RI` | `vd.imag += vs1.imag * vs2.real` | `FMADD` |
| `Cfma_IR` | `vd.imag += vs1.real * vs2.imag` | `FMADD` |

因此 v1 的主要收益是降低软件可见指令数、fetch/decode/offload 压力，而不是提升原始 FPU 吞吐。

## 4. 已完成范围

- custom encoding 和 decode integration。
- paired register layout 和 legal/illegal policy。
- e16/e32/e64 ISA 行为。
- mask/tail 行为。
- `vstart != 0` illegal 策略。
- fflags 累积。
- 隐式 real/imag register dependency 的 conservative serialization/fence。
- inline assembly 软件使用路径。
- v1 文档归档。

## 5. 专用硬件状态

RTL 中存在 `fpnew_complex_fma` integration/prototype 和 split VRF writeback 草稿，但 v1 明确保持默认禁用：

```systemverilog
localparam bit CfmaDedicatedWritebackEn = 1'b0;
```

该路径不作为 v1 功能结果来源，也不能作为 dedicated hardware correctness 证据。

## 6. 步骤 13-18 收尾状态

| Step | v1 结论 |
| --- | --- |
| Step 13 | 作为架构决策关闭：v1 保留四阶段 FPU 复用路径，不默认启用 dedicated hardware。 |
| Step 14 | v1 保留 conservative serialization/fence，dedicated scoreboard 优化推迟。 |
| Step 15 | 当前 v1 源码完成 build 层面的验证记录。 |
| Step 16 | ISA RTL 行为验证通过。 |
| Step 17 | benchmark/performance 未完整关闭，不声明 speedup。 |
| Step 18 | 文档交接和归档完成。 |

## 7. 已记录验证证据

2026-07-06 记录的验证证据：

```text
git diff --check: PASS
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt: PASS
make -C hw/system/spatz_cluster sw.vlt: PASS
ctest riscvTests-rtl-(vfcmacc|vfmacc|vfnmsac): PASS, 3/3
benchmark probe: dp-caxpy old/new 通过；dp-cdotp_old_M128 超过观察窗口未完成
```

注意：这些是归档记录中的证据；若后续要合并、发布或做 v2 基线，应重新运行 fresh verification。

## 8. 残留风险

- dedicated datapath 未完成。
- dedicated split writeback 未证明正确。
- `dp-cdotp` benchmark 仍有 timeout/closure 问题。
- 不存在完整 old/new benchmark speedup 数据。
- 工具链 mnemonic/objdump 支持仍需后续整理。

## 9. 归档建议

v1 可以作为“功能正确性版本”归档；v2 应单独开发 dedicated datapath，不应在 v1 归档文档中继续扩大范围。
