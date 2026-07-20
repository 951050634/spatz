# CFMA v2 阶段 7：性能 microbenchmark 与 dedicated-mode 限界

**日期**：2026-07-07
**分支**：`feature/cfma-v2-datapath`

## 1. 小阶段目标

阶段 7 的目标是给 dedicated CFMA path 建立可复现的性能证据，并用 benchmark 暴露 correctness/throughput gap。

本小阶段新增 ISA-style microbenchmark，而不是继续依赖 `spatzBenchmarks` full kernels：后者在当前 RTL direct run 中存在多 hart/tohost 先退出和长时间无 cycle 输出的问题，不适合作为自动 closure 的唯一证据。

## 2. 新增 microbenchmark

新增：

```text
sw/riscvTests/isa/rv64uv/vfcmacc_perf.c
```

CMake target：

```text
vfcmacc_perf
```

当前 workload：

```text
64 x vfcmacc.vv
vl=1
vsew=e64
LMUL=m1
hart0 only
```

输出：

```text
vfcmacc_perf iterations=64 vl=1 vsew=e64 cycles=<mcycle delta> cycles_per_insn_x100=<...>
```

## 3. RED 发现与 RTL 修复

`CFMA_DEDICATED_V2` 下的 back-to-back `vfcmacc_perf` 首先暴露了 dedicated path 的三个问题：

1. `word_issued` 未等待 dedicated read collector `start_ready`，长串 CFMA 可能丢 start；
2. collector 使用 `last_request`，而不是当前 issued word 的 `(vl_q + nr_elem_word) >= vl`，导致最后一个 word 可被标成 `last=0`；
3. dedicated split writeback 完成后没有向 VFU completion path 注入 result-valid/tag，request 可能不能 architectural complete。

对应修复在：

```text
hw/ip/spatz/src/spatz_vfu.sv
```

## 4. 重要限界：当前 dedicated path 只启用 `vl=1,e64`

调试 full `vfcmacc` 时确认：当前 `fpnew_complex_fma` 实例固定为 `FP64`，并且只计算一个 complex element；它还不是 packed e32/e16 或多 e64 lane 的 vector datapath。

因此本小阶段将 dedicated enable 条件收敛为：

```text
CFMA_DEDICATED_V2 && cfma_insn && vsew == EW_64 && vl == 1
```

其它情况（e16/e32、多 lane e64、mask/tail/fflags full ISA cases）继续走 v1 fallback，即使在 `CFMA_DEDICATED_V2` build 中也是如此。默认 build 仍然完全关闭 dedicated path。

## 5. 验证结果

完整证据：

```text
docs/v2/evidence/stage7_vfcmacc_perf_microbenchmark.txt
```

结果摘要：

| Mode | Build | Workload | Cycles | cycles/insn |
| --- | --- | --- | ---: | ---: |
| v1 fallback | default-off | 64 x `vfcmacc.vv`, `vl=1`, `e64` | 1058 | 16.53 |
| v2 dedicated limited | `DEFS=-DCFMA_DEDICATED_V2` | 64 x `vfcmacc.vv`, `vl=1`, `e64` | 624 | 9.75 |

该 limited microbenchmark 的 speedup：

```text
1.70x
```

验证通过项：

```text
git diff --check: PASS
make sw.vlt: PASS
default-off system build: PASS
default-off vfcmacc_perf: PASS
default-off ctest vfcmacc/vfmacc/vfnmsac: PASS, 3/3
dedicated-mode system build: PASS
dedicated-mode vfcmacc_perf: PASS
dedicated-mode full vfcmacc: PASS
```

## 6. 结论与后续 gap

本小阶段给出了 dedicated scalar-lane e64 path 的可复现性能证据，但不能声明 full vector dedicated CFMA 完成。

后续若要切换默认 path，仍需：

- 扩展 `fpnew_complex_fma` 或外层 datapath，使其覆盖 e16/e32 packed lanes 和多 e64 lanes；
- 将 dedicated enable 从 `vl=1,e64` 扩展到 full legal `vfcmacc.vv`；
- 重新运行 full dedicated ISA matrix 和 spatzBenchmarks kernels；
- 完成默认路径切换决策。
