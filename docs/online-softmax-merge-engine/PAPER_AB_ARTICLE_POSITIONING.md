# Paper A+B Article Positioning Notes

本文档记录将 Paper A 和 Paper B 两阶段工作合并成一篇文章时的成文口径、可支撑主张、创新点、可扩展性讨论和需要主动声明的边界。

## 文章定位

A+B 合成一篇文章是合理的，而且比单独写 Paper B 更完整。推荐将文章定位为 architecture / system prototype paper，而不是完整 attention accelerator paper。

核心叙事：

```text
本文研究如何在不修改 Spatz ISA 和主指令流水线的前提下，为 online softmax merge 提供一个低侵入硬件 offload 路径。第一阶段通过受限语义验证 MERGE engine 的系统集成可行性；第二阶段进一步实现完整 mixed-scalar online softmax merge 公式，并通过 RTL correctness、近似误差和 microbenchmark 性能数据证明该路径具备扩展到 attention workload 的潜力。
```

更精炼的 thesis：

```text
Online softmax merge is small enough to be offloaded through an auxiliary merge engine, but structured enough to require full mixed-scalar datapath support. We show that an interface-preserving SMU design can implement the complete merge recurrence with LUT-based approximations, pass RTL correctness gates, and reduce merge-cycle cost by up to 37.9x on evaluated microbenchmarks.
```

本文应强调的是“低侵入接口保守集成 + 完整 online merge 公式 RTL 化 + 近似数值证据闭环”，而不是最终端到端 attention 加速性能。

## A 阶段在文章中的角色

Paper A 不应被写成最终能力，而应作为 baseline 和 integration feasibility study。

A 阶段回答的问题：

```text
Can this kind of merge offload be integrated safely into Spatz without modifying the ISA or main pipeline?
```

A 阶段可支撑的贡献：

- 验证 `MERGE_*` MMIO/TCDM path 可以作为在线 softmax merge offload 的系统入口。
- 验证 restricted-semantics merge engine 可以在 Spatz cluster 中完成配置、启动、busy/done/error 状态处理和 TCDM 读写。
- 建立 benchmark、CTest、error-path regression 和文档记录流程。
- 为 B 阶段提供保守 baseline 和 regression anchor。

建议表述：

```text
Phase A establishes the minimum system integration path for a merge-update offload engine. Its restricted semantics are intentionally conservative: the goal is not to solve the full softmax recurrence, but to validate that the Spatz cluster can host and exercise an auxiliary SMU through the existing control and TCDM interfaces.
```

## B 阶段在文章中的角色

Paper B 是主贡献。B 阶段回答的问题：

```text
Can the same integration path support the full mixed-scalar online softmax merge equation?
```

B 阶段可支撑的贡献：

- 在不修改 ISA、decoder、controller、VFU、VRF、VLSU 或 instruction pipeline 的前提下，扩展到完整 mixed-scalar online softmax merge recurrence。
- 在 `online_merge_update_engine.sv` 中接入 `exp` LUT approximation、reciprocal approximation 和 FP32/fixed-point helper。
- 用 Q16.32 fixed-point 表示和 weighted accumulation 完成 `O_new` 更新。
- 将 full-reference probe 从 expected-error 改为 correctness gate。
- 保留 invalid config、both-zero-`l`、stride-zero packed layout 和 restricted semantics regression。
- 通过 full mixed sweep、attention-like SMU merge-chain fallback、TCDM counters 和 numeric approximation summary 形成最小闭环证据。

建议表述：

```text
Phase B keeps the Phase-A interface contract but replaces the restricted scalar/vector behavior with a full mixed-scalar merge datapath. The design computes the max update, two exponential scaling factors, the merged length, a reciprocal-based normalization, and weighted vector output updates inside the SMU.
```

## 可支撑主张

当前证据足以支撑以下主张：

- 在不改 Spatz ISA / pipeline / `MERGE_*` 接口的前提下，可以将 online softmax merge 从受限语义推进到完整 mixed-scalar merge datapath。
- 当前 RTL path 可以通过 correctness gate，而不只是通过 expected-error probe。
- 当前固定 256 段 `exp` LUT 和 256 段 reciprocal approximation 在评测 workload 上具有很小的观测误差。
- 在 SMU microbenchmark 中，engine cycles 相比 RTL-aligned software reference 有明显下降。
- attention-like fallback 真实调用 SMU merge-chain path，可以作为 attention 集成前的 workload proxy。

当前关键数据：

- Full mixed sweep speedup:
  - `N=1,D=1`: `2327 / 1207 = 1.93x`
  - `N=4,D=8`: `17490 / 1478 = 11.83x`
  - `N=8,D=16`: `56103 / 2343 = 23.94x`
  - `N=8,D=32`: `97554 / 3371 = 28.94x`
  - `N=16,D=64`: `365620 / 9650 = 37.89x`
- Attention-like SMU fallback:
  - `rows=8, blocks=4, D=32`
  - `cpu_cycles=388826`
  - `engine_cycles=13432`
  - `speedup=28.95x`
  - `tcdm_accessed=6188`
  - `tcdm_congested=32`
- Numeric approximation worst observed:
  - `max_abs_err=9.775e-06`
  - `guarded_max_rel_err=3.325e-06`
  - `mean_abs_err=2.174e-06`

稳妥的英文主张：

```text
We validate the approximation numerically on representative mixed-scalar and attention-like merge-chain workloads. The observed worst-case absolute error is below 1e-5 in our evaluated cases.
```

稳妥的中文主张：

```text
本文在代表性的 mixed-scalar sweep 和 attention-like merge-chain workload 上验证了数值行为；在当前固定 256 段 LUT 配置下，观测到的最大绝对误差低于 1e-5。该结果表明该近似 datapath 对本文评测范围内的 workload 足够稳定，但尚不构成对所有 attention 输入分布的全局误差证明。
```

## 不应过度声明的内容

当前证据不应支撑以下强主张：

- 已实现完整端到端 attention accelerator。
- 已证明端到端 attention speedup。
- 已对所有 softmax / attention 输入分布完成充分数值验证。
- 已完成 exp / reciprocal 参数 sweep 或设计空间探索。
- 已通过 synthesis / area / power / Fmax 证明硬件效率。
- 当前 CPU baseline 代表高性能 CPU、libm、SIMD 或 vector attention baseline。

需要主动说明：

- B6 是 attention-like SMU merge-chain fallback，不是端到端 attention benchmark。
- CPU cycles 是 RTL-aligned software reference cycles，不是优化 CPU baseline。
- 当前固定 256 段 LUT，没有完成参数 sweep。
- 当前验证覆盖代表性 case 和 corner regressions，但不是全输入空间证明。
- 当前平台展示的是最低集成门槛，不是性能上限。

## 为什么不能声称全分布数值验证

当前可以说明的是：

```text
在当前 RTL-aligned 近似配置、当前 benchmark 构造的 mixed-scalar / delta-sweep / attention-like workload 上，误差很小。
```

但不能直接推出：

```text
对所有 softmax / attention 分布都充分验证，误差都满足某个全局界。
```

原因：

- 输入空间包括 `m_old`、`l_old`、`O_old`、`m_tile`、`l_tile`、`O_tile`、block order、row length、hidden dimension、logit delta、mask pattern 和多次 merge 累积误差。
- 近似误差与 LUT 区间、delta 边界、reciprocal 输入、`l_new` 很小的区域以及 old/tile 权重比例有关。
- attention 分布可能包括平滑 logits、尖锐 logits、causal mask、大量无效项、多 head scale、长序列、多 block 累积和病态输入。
- “充分验证”通常要求数学误差上界、大规模随机/真实 trace sweep、corner stress suite 或 FP32/FP64 oracle 统计分布。

因此文章应写成 representative validation，而不是 universal proof。

## 可扩展性口径

本文可以讨论可扩展性，但要区分机制可扩展和当前原型可扩展。

推荐总表述：

```text
This work is not Spatz-only in principle, but the current evidence is Spatz-prototype evidence. The contribution is a scalable merge-offload design pattern demonstrated on a constrained RISC-V vector-cluster platform.
```

中文表述：

```text
本文验证的是一种可扩展的硬件化 merge 模式，而不是声称当前 Spatz 原型已经代表最终规模化实现。Spatz 展示的是最低集成门槛，不代表该方法的性能上限。
```

### 机制上可扩展的部分

- online softmax merge 的硬件化分解：`max + exp + reciprocal + weighted O update`。
- 旁路 merge engine 的接口模型。
- RTL-aligned software reference 和 correctness gate 方法。
- 近似 datapath 的数值验证方法。
- 从 restricted semantics 到 full mixed-scalar semantics 的递进开发路径。
- TCDM/perf counter 驱动的评估框架。

### 当前 Spatz 原型受限的部分

- MMIO 启动粒度较粗。
- 当前是单个 SMU engine，并发性有限。
- TCDM bandwidth 和 congestion 会影响规模化。
- 当前 full mixed sweep 最大到 `N=16,D=64`。
- 当前不是嵌入完整 attention kernel 的端到端实现。
- CPU baseline 不是高性能 attention baseline。
- 尚未展示多 head、多 row、大 sequence 的端到端吞吐。

### 可扩展性的写作方式

算法结构层面：

```text
The merge recurrence is structurally composable across rows, block chains, and heads. The same SMU datapath can be reused by streaming different `(m,l,O)` state tuples through the engine.
```

微结构层面：

```text
The current implementation serializes vector elements through a compact engine, but the datapath exposes natural replication points: vector lanes, row-level parallelism, and independent head-level engines.
```

集成层面：

```text
The prototype intentionally uses the existing MERGE MMIO/TCDM interface and avoids ISA or pipeline modifications. These constraints limit launch overhead and bandwidth in the current Spatz instance, but they also demonstrate the minimum integration requirements of the merge-offload pattern.
```

当前实验证据可以支撑的可扩展性结论：

```text
Engine cycles continue to scale favorably relative to the RTL-aligned software reference across the evaluated workload sizes, and TCDM congestion remains observable and measurable rather than functionally blocking. This suggests engineering value in scaling the datapath width, engine count, or front-end streaming mechanism.
```

不能声称：

```text
The prototype proves linear scaling for large-scale end-to-end attention.
```

## 推荐文章结构

1. Introduction
   - attention / FlashAttention-style block-wise softmax 中 online merge 的重要性。
   - 通用处理路径的开销。
   - 目标：低侵入 SMU offload，不改 ISA / pipeline。

2. Background
   - online softmax merge 公式：

```text
m_new = max(m_old, m_tile)
l_new = l_old * exp(m_old - m_new) + l_tile * exp(m_tile - m_new)
O_new = (O_old * l_old * exp(m_old - m_new)
       + O_tile * l_tile * exp(m_tile - m_new)) / l_new
```

   - Spatz、SMU、MMIO、TCDM 背景。

3. Phase A: Restricted Merge Integration
   - restricted semantics。
   - `MERGE_*` interface。
   - error path。
   - benchmark 和 regression。
   - A 阶段作为 integration baseline。

4. Phase B: Full Mixed-Scalar Merge Engine
   - exp LUT。
   - reciprocal approximation。
   - fixed-point helper。
   - scalar update。
   - vector weighted merge。
   - 保持接口不变。

5. Correctness Methodology
   - RTL-aligned software reference。
   - full-reference correctness gate。
   - invalid config。
   - both-zero-`l`。
   - stride-zero layout。
   - restricted regression。
   - Verilator CTest。

6. Evaluation
   - CPU reference cycles vs engine cycles。
   - speedup vs workload size。
   - TCDM accessed / congested。
   - numeric error summary。
   - attention-like SMU merge-chain fallback。

7. Scalability Discussion
   - Spatz 是受限验证平台。
   - merge-offload pattern 可扩展。
   - 当前原型限制和下一步扩展点。

8. Limitations
   - 非端到端 attention speedup。
   - CPU baseline 是 RTL-aligned reference。
   - 无 PPA。
   - 无全分布数值证明。
   - 未完成 exp / reciprocal 参数 sweep。

9. Conclusion
   - A 证明低侵入系统接入。
   - B 证明完整 mixed-scalar merge datapath 可行。
   - 合起来形成 attention offload building block。

## 贡献点写法

推荐三点贡献：

```text
1. We present an interface-preserving online softmax merge offload path for Spatz that does not require ISA or main pipeline changes.

2. We show a two-stage design progression: a restricted-semantics integration baseline followed by a full mixed-scalar merge datapath implementing the complete online softmax merge recurrence.

3. We provide RTL-level correctness and evaluation evidence, including full-reference gates, error-path regressions, cycle/TCDM counters, and numerical approximation analysis.
```

中文版本：

```text
1. 本文提出一种保持接口不变的 online softmax merge offload 路径，在不修改 Spatz ISA 和主流水线的情况下接入 SMU。

2. 本文展示一个两阶段设计推进过程：先用受限语义验证系统集成路径，再扩展到实现完整 online softmax merge recurrence 的 mixed-scalar datapath。

3. 本文提供 RTL 级 correctness 和评估证据，包括 full-reference gate、error-path regression、cycle/TCDM counter 和数值近似误差分析。
```

## 结论口径

文章可以写，而且故事能成立。最稳的结论是：

```text
Phase A demonstrates that online softmax merge offload can be integrated into Spatz through a conservative auxiliary engine interface. Phase B shows that the same path can support the full mixed-scalar online merge recurrence with small observed approximation error and substantial cycle reduction on evaluated microbenchmarks. The result is a low-intrusion merge-offload building block for future attention acceleration work.
```

中文版本：

```text
A 阶段证明 online softmax merge offload 可以通过保守的外围 engine 接口集成到 Spatz；B 阶段证明同一接口路径可以支撑完整 mixed-scalar online merge recurrence，并在当前评测范围内获得很小的观测近似误差和明显 cycle reduction。本文结果应被理解为面向未来 attention acceleration 的低侵入 merge-offload building block。
```
