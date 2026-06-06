# Online Softmax Merge Engine 对比实验

## 实验目的

对比同一 benchmark 输入下两条路径：

- CPU scalar / RTL-aligned software reference path。
- cluster-local SMU merge engine path，通过现有 `MERGE_*` MMIO 启动，由 engine
  自己访问 TCDM 并写回 `m/l/O`。

论文 A 的受限语义数据仍可作为 baseline；论文 B 当前结果已切换为完整
mixed-scalar online softmax merge 方程。本文档不声称端到端 attention speedup。

## 实验环境

日期：2026-06-06 CST

命令：

```bash
make -C hw/system/spatz_cluster bin/spatz_cluster.vlt
make -C hw/system/spatz_cluster sw.vlt
cd hw/system/spatz_cluster/sw/build
ctest -R online-softmax-merge -V
```

结果：

```text
1/1 Test #91: spatzBenchmarks-rtl-spatzBenchmarks-rtl-online-softmax-merge ... Passed 1105.98 sec
online-softmax-merge PASS
```

## Full Mixed-Scalar Sweep

`speedup = cpu_cycles / engine_cycles`。CPU path 是 RTL-aligned fixed-point
software reference，不是优化过的 libm 或向量化 CPU baseline。

| N | D | CPU cycles | Engine cycles | Speedup | TCDM accessed | TCDM congested |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 2327 | 1207 | 1.93x | 327 | 0 |
| 4 | 8 | 17490 | 1478 | 11.83x | 495 | 2 |
| 8 | 16 | 56103 | 2343 | 23.94x | 985 | 4 |
| 8 | 32 | 97554 | 3371 | 28.94x | 1583 | 9 |
| 16 | 64 | 365620 | 9650 | 37.89x | 5229 | 27 |

最强数据点：

```text
N=16,D=64: cycle reduction = (365620 - 9650) / 365620 = 97.36%
```

## Correctness 与 Error Path

保留的 correctness / error path 输出：

```text
online-softmax-merge stride-zero N=4 D=8 case=2 status=0x2
online-softmax-merge invalid n-zero status=0x4
online-softmax-merge invalid d-zero status=0x4
online-softmax-merge invalid misaligned-address status=0x4
online-softmax-merge invalid misaligned-stride status=0x4
online-softmax-merge unsupported both-zero-l status=0x4
online-softmax-merge full-ref-probe generic-mixed N=4 D=8 status=0x2 cpu=17072 engine=1465 tcdm_accessed=495 tcdm_congested=2 ref_l0=0x3f5e3b41 ref_o00=0xbe567a3e
```

## Numeric Approximation

Host numeric model：

```bash
python3 data_process/attnres/code/full_merge_numeric_model.py
```

固定近似配置：

- `exp`：`[-8, 0]` 256 段 Q1.23 LUT 线性插值。
- reciprocal：`[1, 2]` mantissa 256 段 Q1.23 LUT 线性插值。

最差误差：

```text
max_abs_err=9.775161743e-06
guarded_max_rel_err=3.325012490e-06
mean_abs_err=2.174088011e-06
```

所有记录均满足 `<=1e-3`，并已满足 `<=1e-4`。

## Attention-Like SMU Chain

最小 B6 fallback workload：

```text
online-softmax-merge attention-like rows=8 blocks=4 D=32 cpu=388826 engine=13432 tcdm_accessed=6188 tcdm_congested=32 state_bytes=4352 saw_busy=1
```

该 workload 真实调用 SMU hardware path，并模拟多 row、多 block、多 hidden
dimension 的 `m/l/O` merge 链。它不是完整 attention kernel，不包含 QK/PV 或
runtime/DRAM 调度，因此只能作为 attention-like merge-chain 证据。

## 数据与图表

CSV：

```text
data_process/attnres/data/online_softmax_full_mixed_bypass.csv
data_process/attnres/data/online_softmax_full_merge_numeric.csv
data_process/attnres/data/online_softmax_attention_like_smu.csv
```

SVG 图：

```text
data_process/attnres/pic/paper_b_full_mixed_cycles.svg
data_process/attnres/pic/paper_b_full_mixed_speedup.svg
data_process/attnres/pic/paper_b_full_mixed_tcdm.svg
data_process/attnres/pic/paper_b_numeric_error.svg
data_process/attnres/pic/paper_b_attention_like_smu.svg
```

## 结论边界

当前结果可以支撑：

- 完整 mixed-scalar online softmax merge 方程已在 cluster-local SMU path 中闭环。
- benchmark 的 full-reference probe 已从 expected-error 变为 correctness gate。
- 固定 256 段 exp/reciprocal LUT 配置满足 `1e-4` 级误差目标。
- 至少一个完整 mixed-scalar case 中 engine path 快于 RTL-aligned software path；
  当前全部 full mixed-scalar sweep 点均快于该 reference path。
- attention-like merge-chain fallback 真实调用 SMU path。

当前结果不能支撑：

- 端到端 LLM attention 或完整 runtime speedup。
- 面积、功耗、频率或综合后资源结论。
- 对 NaN、Inf、subnormal 或超出 finite normal 输入范围的数值承诺。
