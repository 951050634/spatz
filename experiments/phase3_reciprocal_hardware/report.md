# Phase 3: Reciprocal-LUT normalization

## 结论先行

Reciprocal normalization 在系统级周期上达到目标，但没有改善当前的
综合 timing proxy。对于同一输入的 `A1_MIXED_SCALAR`，它将 FP16 sequential
division 的主要周期开销替换为 LUT + shared multiplier：N8/D32 的 kernel
cycles 从 3171 降至 2622（-17.31%），N16/D64 从 6061 降至 5024
（-17.11%）。但 post-synthesis timing proxy 从 14619.73 ps 增至
15539.55 ps（+6.29%），因此本阶段不能声称 critical path 已改善。

## 1. 修改内容总结

- 保留 FP16 max、INT16 exponential LUT、FP32/Q16.32 recurrence 和 FP16
  output contract，仅替换 Mixed normalization 的 division datapath。
- 新增 `online_merge_recip_approx_q1_15`：FP32 denominator 的 mantissa /
  exponent decomposition、256-entry Q1.15 reciprocal ROM、分段线性
  interpolation 和 exponent correction。ROM 为 256×16 bit（4096 bit），
  `code[256] = 0x4000` 为 `m=2` 的 terminal half endpoint（0.5）；unity
  为 `code[0] = 0x8000`。
- `online_merge_update_engine` 以
  `MixedNormalizationReciprocal` 参数选择实现。Reciprocal 分支使用一个
  shared 48×16 unsigned multiplier，normalization 为 3 个 weight phases；
  reciprocal 配置下 divider hierarchy 被 generate-prune，division 配置
  仍保留作对照。
- `spatz_cluster.sv` 通过 `ONLINE_MERGE_MIXED_RECIPROCAL` 宏最小透传该
  参数。Division binary 使用 `-DSPATZ_DISABLE_DASM`，Reciprocal binary
  使用 `-DSPATZ_DISABLE_DASM -DONLINE_MERGE_MIXED_RECIPROCAL`。
- runner 增加 `A1_MIXED_SCALAR` 的 mode-3 FSM gate，并允许本阶段明确要求
  的 `--trials 1`；没有新增 runner/gate 基础设施。性能 policy 只使用
  `A1_SMU_SCALAR` 和 `A1_MIXED_SCALAR`，未将早期错误的 B1 记录用于结论。

## 2. 软件模型验证

Model A 为现有 `mixed_rtl_exact`（FP16 divider）；Model B 为
`mixed_rtl_reciprocal`（FP16 RNE denominator/numerator、FP32
mantissa/exponent、Q1.15 endpoint RNE、interpolation truncation 和固定
net-shift contract）。测试矩阵覆盖 sequence length 128/256/512/1024、
head dimension 64/128，以及 random-score 和 single-head QK^T V。

- 完整正有限 FP16 denominator domain（31743 个值）的 reciprocal 最大
  relative error 为 `6.696581841e-05`；257-point mantissa probe 最大值为
  `7.297017146e-05`。
- Random-score 矩阵中，A/B softmax MAE、stable-relative error、cosine
  分别为 `1.362e-07`、`5.553e-05`、`0.999999961`；attention 对应为
  `1.233e-05`、`2.649e-04`、`0.999999972`。
- Single-head QK^T V 中，A/B softmax 为
  `9.914e-08`、`7.076e-05`、`0.999999971`；attention 为
  `1.027e-05`、`2.540e-04`、`0.999999974`。
- Reciprocal 相对 FP32 oracle 的常规矩阵结果保持在约 0.99994 以上
  cosine；但扩展 stress scan 的最低 optimized-vs-FP32 cosine 为
  `0.999873853`，低于本阶段的 `0.9999` 目标。这一失败与既有 Mixed
  EXP/FP16-max 误差有关，不能归因于 reciprocal LUT，也没有被隐藏在
  A/B selection gate 中。

详细模型数据和 LUT sweep 保存在
`experiments/phase1_online_softmax/results/phase3_reciprocal_model/report.md`。

## 3. RTL 修改说明

Reciprocal branch 对每一行先锁存 reciprocal code/scale，再用同一物理
multiplier 完成 old/tile 两次 numerator × reciprocal；FP16 widening、
Q16.32 product 和 exponent shift 与 Division reference 保持一致。这样
既复用了已有 Mixed scalar merge 数据流，也保持了 Division/Reciprocal
两种配置可独立综合和仿真。

## 4. 仿真与功能验证

系统性能 runner 使用 `OM_SIM_CONFIG`：

```text
profile=low_perturbation, dasm=false, fsm=true
```

cases 为 `N8_D32_S1_main,N16_D64_S1_main`，`profile=memory`，trials=1。
Division binary 测量 Legacy + MixedDiv；Reciprocal binary 测量 MixedRecip。
六条记录均为 `PASS`，FSM gate 均为 `PASS`；manifests 和 simulator hashes
完整。由于每条结果仅运行 single trial，这里只是阶段性确定性测量，不构成
paper-ready multi-trial reproducibility。FSM mode 为 Legacy=1、Mixed=3。

| case | A1_SMU_SCALAR | A1_MIXED_SCALAR + Division | A1_MIXED_SCALAR + Reciprocal |
| --- | ---: | ---: | ---: |
| N8/D32 kernel cycles | 2625 | 3171 | 2622 |
| N8/D32 busy cycles | 192 | 737 | 208 |
| N8/D32 COMPUTE_WEIGHT | 8 | 552 | 24 |
| N16/D64 kernel cycles | 5067 | 6061 | 5024 |
| N16/D64 busy cycles | 384 | 1474 | 417 |
| N16/D64 COMPUTE_WEIGHT | 16 | 1104 | 48 |

相对 MixedDiv，Reciprocal 的 busy cycles 降低 71.8%，compute-weight
cycles 从 552/1104 降至 24/48。相对 Legacy A1，Reciprocal kernel 在
这两个 case 中分别为 -0.11% 和 -0.85%。系统级 Reciprocal error
（相对软件 reference）为：N8/D32 的 max abs/relative
`0.00758553/0.00379625`，N16/D64 的
`0.00629747/0.00605114`。

Focused RTL counter 的 78 cycles/row 与 system record 的 69 cycles/row
差异来自 `old numerator=0` fast path，不是 build mismatch。

Focused RTL tests 中以下测试通过：

- `online_merge_approx_tb`
- `online_merge_recip_q1_15_tb`
- `online_merge_engine_mixed_tb`
- `online_merge_precision_support_tb`
- `online_merge_engine_reciprocal_tb`

已有 10-case full-engine golden 也通过。`online_merge_mixed_tb` 的
structured/random miter 通过（`158722 + 1000000` vectors），但随后旧的
FP16 divider subtest 在 one-cycle start pulse 下报告 `busy=0` timeout；
保持 start 至下一个时序边界的最小 smoke test 通过。因此该 TB 本次记为
已知 testbench scheduling race，而不是 Reciprocal RTL failure，未修改无关
TB 或引入 workaround。

Python 回归：`experiments/tests` 共 52 tests 通过，
`util/online_softmax_merge/tests` 共 110 tests 通过；`git diff --check`
通过。

原始同输入结果、日志、ELF、manifest 和 simulator hashes 位于
`system_performance/division/` 与 `system_performance/reciprocal/`。

## 5. 面积与性能变化

Nangate45 Yosys/STA proxy 的正式结果如下：

| implementation | area (um2) | vs Legacy | timing proxy (ps) | vs Legacy |
| --- | ---: | ---: | ---: | ---: |
| Legacy Scalar | 72399.082 | — | 12517.79 | — |
| Mixed + Division | 52000.074 | -28.18% | 14619.73 | +16.79% |
| Mixed + Reciprocal | 52407.586 | -27.61% | 15539.55 | +24.14% |

Reciprocal area 比 MixedDiv 增加 `0.78%`，但仍保持相对 Legacy 的面积优势。
Timing proxy 比 MixedDiv 恶化 `6.29%`，所以当前关键路径改善目标失败；
系统 kernel-cycle 改善不能包装成物理 timing 改善。

面积和 timing 的可复现输入及 manifest 分别在 `area/` 和 `timing/`。

## 6. 当前论文可支持结论

本阶段可以支持：在保留 Stage-aware Mixed Precision SMU 数值数据流的
前提下，256-entry Q1.15 reciprocal LUT 能以接近原 FP16 divider 的数值
结果替换 sequential normalization，并在同输入系统仿真中消除约 17% 的
Mixed kernel cycle penalty；Mixed 固定实现相对 Legacy Scalar 仍约有
27.6% 面积优势。

本阶段不能支持：Reciprocal 已降低 critical path、已改善 post-layout
timing，或在所有 stress 输入上保证 cosine `>0.9999`。这些结论需要后续
优化 multiplier/LUT/FP16 conversion 的组合路径，以及单独处理既有
EXP/max stress 误差。

## 7. 尚未解决问题

1. Reciprocal timing proxy 为 15539.55 ps，较 Division 更差；下一步应
   只针对该组合路径做局部 timing 优化，不应将当前结果表述为 timing
   improvement。
2. Extended optimized-vs-FP32 stress scan 最低 cosine 为 0.999873853；
   根因候选是既有 Mixed EXP/FP16-max 量化，而非 LUT reciprocal A/B 误差。
3. `online_merge_mixed_tb` divider 子测试仍有 one-cycle start scheduling
   race；divider hold smoke 和 Reciprocal/full-engine tests 已通过，问题
   暂留，不影响本阶段系统记录。
4. 系统级数据是两个 anchor cases、单 trial 的低扰动 Verilator 测量；
   runner 因 checkout dirty 标记为 paper-ineligible，后续正式论文数据应
   在冻结 snapshot 后重跑，不改变本阶段实验结论。
