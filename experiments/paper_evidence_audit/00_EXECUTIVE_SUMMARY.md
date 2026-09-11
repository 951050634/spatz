# Paper Evidence Audit — Executive Summary

审计日期：2026-09-10。状态：**COMPLETE（repository-only，未重跑实验或综合）**。

## What was built?

在 Snitch/Spatz cluster 中集成了一个 Scalar Online-Merge Unit（SMU）。它执行
Online Attention 中依赖历史状态的逐行 recurrence，并通过既有 TCDM 读写
`m/l/weight`；规则的 `O[D]` 更新仍由既有 RVV 路径执行。最终还加入了两个
scalar custom 指令：OMCFG 建立 workload-persistent context，OMERGE 每次触发
一次 merge。

## What is the final architecture?

最终 Proposed Design 是 **Mixed-Precision Scalar SMU + unchanged RVV**。
Full SMU（含向量输出更新）仅是历史消融，不是继续开发或论文主架构。未修改
Spatz vector datapath、vector lanes、VRF 或标准 RVV 语义。

## Four strongest contributions

1. 以依赖性为依据的 HW/SW 切分：state-dependent recurrence 进入 SMU，规则的
   `O[D]` 更新复用 RVV。
2. 面向阶段的 mixed precision：FP16 max/diff、256-entry Q1.14 EXP、Q16.32
   recurrence carrier、256-entry Q1.15 reciprocal + interpolation；它不是
   runtime-adaptive precision。
3. 安全且状态化的 scalar programming model：OMCFG 用于一次性配置，OMERGE
   用于每次 merge，硬件 A/B selector 只在成功完成并接受响应后翻转。
4. 原生 Online Attention dataflow 的 matched evidence，同时保留 explicit-P
   负结果，限定加速收益来自 dataflow matching，而非通用 Softmax 替换。

## Main formal results

- B2R → Mixed Scalar SMU+RVV，N8/D32 与 N16/D64：recurrence 分别
  `8.524×`、`14.006×`；merge `5.696×`、`5.899×`；Native Core
  `1.157×`、`1.125×`。Phase 6 两个扩展形状把 recurrence 范围扩展到
  `8.524–17.784×`、merge 到 `4.144–6.275×`、Native Core 到
  `1.066–1.157×`。
- A1-MMIO → A1-ISA/OMERGE：recurrence/control window 在 N8/N16 分别减少
  `59.014%`/`41.523%`；merge 减少 `41.695%`/`21.954%`；setup-inclusive
  Native Core 减少 `0.841%`/`0.448%`。该窗口包含 SMU busy。
- MMIO-config → OMCFG-config：一次性 setup 在 N8/N16 从 `991→659`、
  `986→632` cycles，减少 `33.50%`、`35.90%`；不支持 steady-state 大幅
  加速表述。
- 两条配置/调用路径在两个 anchor 上 final-O word-for-word identical，hash
  分别为 `0x9c7cdedc`、`0xfd0d2cff`。
- standalone SMU mapped area：Legacy `72,399.082`，Mixed+Division
  `52,000.074`，Mixed+Reciprocal `52,407.586` Nangate45 Liberty area units；
  后两者相对 Legacy 减少 `28.176%`、`27.613%`。时序仅为 pre-layout
  reg-to-reg proxy，不是 Fmax。
- extended stress 的最低 optimized-vs-FP32 cosine 为 `0.999873853`；因此
  **不得**写 global cosine `>0.9999`。

## Which evidence is final/frozen?

当前 ISA 以 OMERGE implementation freeze `eac2851…`、OMCFG implementation
freeze `7786820…` 为准；正式结果以 Phase 7 formal recovery、Phase 8C matched
CSV/raw logs 为准。B2R 主性能使用 Phase 5/6 formal CSV。mixed numerics/PPA
使用 Phase 3 frozen reciprocal evidence。早期 M2/TCAS-II matched-LUT freeze
仅保留为独立历史证据，不与当前 Mixed/OMERGE 主表拼接。

## Explicitly unsupported

- cluster-level area overhead、Fmax impact、power/energy：`BLOCKED_RESOURCE`；
- silicon frequency、post-layout timing、silicon latency/throughput；
- full Transformer/end-to-end model acceleration；
- universal Softmax acceleration；
- universal workload speedup、多 seed 统计、multihart/concurrency、interrupt/
  flush semantics；
- OMCFG 对 D、precision、tile size、O-buffer、stride 或 selector 的配置能力；
- global cosine `>0.9999`。

## Evidence to use for paper writing

数字以 [paper_master_results.csv](paper_master_results.csv) 为入口，固定事实以
[paper_master_facts.csv](paper_master_facts.csv) 为入口；主叙事的来源优先级是
Phase 8C → Phase 7B → Phase 5/6 → Phase 3/4。claim 必须先查
[09_CLAIM_EVIDENCE_MATRIX.md](09_CLAIM_EVIDENCE_MATRIX.md)，图表必须从
[10_FIGURE_TABLE_SOURCE_MAP.md](10_FIGURE_TABLE_SOURCE_MAP.md) 指定的 formal
CSV/raw files 生成。
