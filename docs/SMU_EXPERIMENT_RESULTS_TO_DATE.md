# SMU 补充实验阶段性结果与证据边界

更新日期：2026-08-04

## Material Passport

- 分析模式：实验结果验证与解释
- 已验证证据：clean anchor、修复后 `scale-00`
- 进行中证据：修复后 `scale-01` 及后续 P0-4 shards
- 支持性证据：旧规模矩阵、FSM、并发、Yosys/toggle proxy
- 验证状态：部分 `VERIFIED`，部分 `ANALYZED/IN PROGRESS`
- 统计性质：确定性 RTL/Verilator 仿真；三次重复用于验证确定性，
  不用于总体统计推断

## 1. 总体结论

至今实验能够支持的最强结论是：

> 对当前 Spatz online-softmax merge，实现效果最好的划分不是“全部软件执行”，
> 也不是“全部交给 SMU”，而是让 SMU 负责逐行 scalar recurrence，让 RVV
> 负责规则的 `O[D]` 向量更新。

Online softmax merge 同时包含两类性质不同的工作：

```text
m_new、exp、l_new、weight
    -> 逐行、存在状态依赖、并行度低

O_new[d] = w_old * O_old[d] + w_tile * O_tile[d]
    -> 规则逐元素乘加、并行度高
```

SMU 更适合第一类工作，而现有 RVV 更适合第二类工作。A1 正好把两类工作分别放到
更合适的执行单元上。

## 2. 正式 anchor 直接证明的结果

四种被测配置为：

- `B1_SCALAR`：软件 recurrence + 软件标量 `O[D]` 更新。
- `B2R_RVV`：软件 recurrence + RVV `O[D]` 更新。
- `A1_SMU_SCALAR`：SMU recurrence + RVV `O[D]` 更新。
- `A2_SMU_FULL`：SMU recurrence + SMU `O[D]` 更新。

正式 anchor 共 72 条记录，全部 PASS；其中 36 条主测量记录满足 clean
provenance、三次可复现和 paper-eligible 条件。

### 2.1 RVV 软件优化本身非常重要

| `(N,D)` | B1 cycles | B2-R cycles | B2-R 相对 B1 |
| --- | ---: | ---: | ---: |
| `(1,1)` | 2,065 | 1,713 | `1.21x` |
| `(8,32)` | 96,853 | 13,111 | `7.39x` |
| `(16,64)` | 372,649 | 27,302 | `13.65x` |

这说明：

- 在极小问题上，RVV 启动和循环开销尚未充分摊薄，收益有限。
- 随着 `N*D` 增长，规则向量更新成为大量工作，RVV 优势迅速扩大。
- 如果只把 SMU 与 B1 比较，会把普通软件向量化收益错误归功于 SMU。

因此，B2-R 而不是 B1 才是主要强软件基线。

### 2.2 Scalar recurrence 卸载是 SMU 的核心收益来源

| `(N,D)` | B2-R cycles | A1 cycles | A1 相对 B2-R |
| --- | ---: | ---: | ---: |
| `(1,1)` | 1,713 | 1,467 | `1.17x` |
| `(8,32)` | 13,111 | 2,497 | `5.25x` |
| `(16,64)` | 27,302 | 4,778 | `5.71x` |

B2-R 和 A1 的 `O[D]` 更新都由 RVV 执行；二者的主要差别是 recurrence 在软件
还是在 SMU。因此，这个对照说明：

- 软件 recurrence 是 B2-R 中的重要逐行瓶颈。
- 该瓶颈会随 N 增长而重复出现。
- SMU 把 max、exp、reciprocal、`l` 更新和权重生成整合成低成本逐行操作。
- A1 的收益不是来自替换 RVV，而是来自消除 RVV 前面的串行 recurrence。

### 2.3 完整卸载并不总是最优

| `(N,D)` | A1 cycles | A2 cycles | 更快方案 |
| --- | ---: | ---: | --- |
| `(1,1)` | 1,467 | 1,338 | A2 快 `1.10x` |
| `(8,32)` | 2,497 | 3,477 | A1 快 `1.39x` |
| `(16,64)` | 4,778 | 9,820 | A1 快 `2.06x` |

在 `(1,1)` 上，向量工作量很小，A1 的权重写回、SMU/RVV handoff 和 RVV 启动
开销无法摊薄，因此 A2 更快。

在 `(8,32)` 和 `(16,64)` 上，`O[D]` 更新占比明显增加，RVV 的每元素吞吐优于
当前 SMU vector datapath，因此 A1 开始显著快于 A2。

该结果否定了“卸载越完整越好”，并支持按计算性质划分执行单元。

## 3. 修复后 N/D 扫描显示的趋势

修复后的正式 `scale-00` 已封口：

- 36/36 PASS；
- 36/36 三次精确可复现；
- 36/36 paper-eligible；
- 0 failure。

在固定 `D=64` 下，目前得到：

| N | B2-R | A1 | A2 | A1 相对 B2-R | A1 相对 A2 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 2,011 | 1,610 | 1,825 | `1.25x` | `1.13x` |
| 2 | 3,623 | 1,815 | 2,349 | `2.00x` | `1.29x` |
| 4 | 7,065 | 2,325 | 3,412 | `3.04x` | `1.47x` |
| 8 | 13,995 | 3,192 | 5,559 | `4.38x` | `1.74x` |
| 16 | 27,765 | 4,896 | 9,820 | `5.67x` | `2.01x` |

其中 N=1、2、4 已属于封口正式结果。N=8、16 的四配置各三次记录均 PASS 且
周期一致，但所在 `scale-01` shard 尚未完全结束，因此最终 paper-eligible 字段
仍待 shard 封口。

### 3.1 A1 相对 B2-R 的收益随 N 增长

在固定 D=64 时，A1 相对 B2-R 的加速依次为：

```text
1.25x -> 2.00x -> 3.04x -> 4.38x -> 5.67x
```

这符合 recurrence 是“每行重复一次”的解释。N 越大，软件 recurrence 被重复
执行的次数越多，SMU 消除的累计开销越大。

### 3.2 A1 相对 A2 的收益随 N 增长

在固定 D=64 时，A1 相对 A2 的加速依次为：

```text
1.13x -> 1.29x -> 1.47x -> 1.74x -> 2.01x
```

这说明当前 Full SMU 的 vector update 成本随总元素数增加得更快，而 RVV 更适合
处理越来越多的 `O[D]` 元素。

### 3.3 “小规模”不能只用 N 定义

`(1,1)` 上 A2 更快，但 `(1,64)` 上 A1 已经更快。因此 crossover 不能简单表述
为“N 小就用 A2，N 大就用 A1”。真正影响选择的是：

- 每行固定 recurrence 成本；
- D 决定的向量更新长度；
- N 决定的行数；
- SMU/RVV handoff 固定开销；
- 总体 `N*D` 向量工作量。

完整 P0-4 扫描的目的，是把这个 crossover 直接测出来，而不是只用三个 anchor
进行外推。

## 4. 周期分解揭示的性能机制

A1 的正式周期可以分为 SMU scalar 阶段和 RVV vector 阶段：

| `(N,D)` | A1 总周期 | SMU scalar | RVV vector |
| --- | ---: | ---: | ---: |
| `(1,1)` | 1,467 | 1,335 | 132 |
| `(8,32)` | 2,497 | 1,453 | 1,044 |
| `(16,64)` | 4,778 | 1,685 | 3,093 |

每个点都满足：

```text
A1 total = SMU scalar + RVV vector
```

可以看到：

- SMU scalar 部分随规模增长相对缓慢；
- RVV vector 部分随 `N*D` 增长；
- A1 的主要可扩展成本最终转移到规则向量更新，而不是 recurrence。

A2 的 FSM 结果为：

| `(N,D)` | SMU busy | vector-update cycles | vector 占 busy |
| --- | ---: | ---: | ---: |
| `(1,1)` | 29 | 9 | `31.0%` |
| `(8,32)` | 2,227 | 2,066 | `92.8%` |
| `(16,64)` | 8,537 | 8,217 | `96.3%` |

这意味着：

- 极小规模的主要问题是命令、提交、等待和同步等固定开销；
- 中大规模上，Full SMU 的 recurrence 已经不是主要瓶颈；
- A2 的绝大部分 busy time 已转移到 vector streaming；
- 此时继续优化 exp 或 reciprocal 的边际收益有限，优化 vector datapath 或把它
  保留给 RVV 更有效。

此前 16 点支持性拟合给出相同方向：

| 实现 | 每行成本 Cs | 每元素成本 Cv |
| --- | ---: | ---: |
| B2-R | 约 `1538` cycles/row | 约 `2.06` cycles/element |
| A2 | 约 `22` cycles/row | 约 `8.00` cycles/element |

这些参数仍需由修复后的完整 P0-4 最终重新拟合，目前只能作为方向性支持。

## 5. 正确性结果

正式 anchor 的最大绝对误差为：

| `(N,D)` | 最大绝对误差 |
| --- | ---: |
| `(1,1)` | `1.25e-6` |
| `(8,32)` | `6.03e-4` |
| `(16,64)` | `2.59e-4` |

全部低于固定门槛：

```text
abs(actual - reference) <= 1e-3 * max(abs(reference), 1)
```

同一形状下四种配置的误差基本一致，说明：

- 性能差异不是通过放宽精度门槛获得的；
- B1、B2-R、A1、A2 对齐了相同输入和数值语义；
- 在正式 anchor 输入范围内，SMU 的固定点/LUT 近似满足正确性要求；
- NaN、Inf 或错误输出不会被作为有效性能记录。

这些结果不能证明 LUT 对所有 FP32 输入均正确、256 段配置全局最优，或完整
attention 链中的误差传播一定可接受。

## 6. 边界实验与缺陷发现

首轮 P0-4 共索引 480 条 scaling、tail 和 numerical 记录，其中保留了 51 条
失败。这些失败没有被删除，而是揭示了两个实际问题。

### 6.1 RVV/TCDM 对齐缺陷

奇数 D 的后续行可能从 `address mod 8 = 4` 的地址开始。当前固定 RTL 对部分 e32
vector memory access 出现 lane 错位，导致以下边界 case 中的 B2-R/A1 出现真实
correctness failure：

- `equal-m`；
- `delta=-8`；
- `delta<-8`；
- `l_tile=0`；
- small-l；
- signed-O。

修复保留原始逻辑 stride，不使用 padding 改变输入；对未对齐首元素执行 scalar
peel，指针对齐后继续正式 RVV load/mul/FMA/store 路径。

针对两个原先稳定失败的 case，修复后 B2-R/A1 共 12 条三次诊断目标执行全部
PASS。

### 6.2 Terminal case 误分类

`l_old == l_tile == 0` 应稳定返回 `UNSUPPORTED_SHAPE`。早期 runner 因 terminal
binary 中相关热符号被编译器消除，将其误判为静态代码错误。

修复后，四配置各三次、共 12 条记录全部稳定返回：

```text
status = UNSUPPORTED_SHAPE
target_status = unsupported
static_code_gate = PASS
```

这说明实验框架能够区分数值错误、合法 unsupported、工具错误、容量跳过和
timeout。

完整 numerical 和 tail 正式复测尚未在修复后的提交上全部封口，因此目前只能说
“已验证修复方向”，不能宣布全部边界 case 最终 paper-ready。

## 7. TCDM 与并发结果

正式 anchor 的 TCDM congestion 事件为：

| 配置 | `(1,1)` | `(8,32)` | `(16,64)` |
| --- | ---: | ---: | ---: |
| B2-R | 0 | 0 | 0 |
| A1 | 0 | 1 | 1 |
| A2 | 0 | 21 | 46 |

虽然 A2 的 TCDM 访问次数更多，但 congestion 事件占比仍较低；A1 的 congestion
几乎为零。

已有 clean concurrency 支撑实验在 `(16,64)` 上还得到：

- SMU slowdown 约 `1.0005x`；
- core slowdown 约 `1.0060x`；
- TCDM congestion ratio 约 `1.27%`；
- 16 个 bank phase 的并发周期范围较窄。

因此，目前能够说明：在被测的单 SMU、单 core stream 和固定规模条件下，TCDM
contention 不是 A1/A2 性能差异的主要解释。

该结论不能外推到多 SMU、任意 core workload、更大数据集或不同 bank mapping。

## 8. 资源与活动度代理

已有 Yosys generic-resource proxy 的 post-techmap cell 数约为：

- exp scope：4,235；
- reciprocal scope：4,629；
- vector scope：33,070；
- full SMU：94,713。

这些结果表明 vector datapath 是明显的结构资源大项，Full SMU 的结构复杂度高于
单独 exp/reciprocal 模块。把 vector update 保留在已有 RVV 上，可能避免在 SMU
内重复建设较重的数据通路。

但是，各 scope 是独立综合的，不能直接相加，也不能解释为标准单元面积、平方毫米、
Fmax、临界路径、真实功耗或能效。

已有 toggle proxy 中，B2-R 和 A2 在一个固定 RTL 窗口分别约记录 4148 万和
1247 万次 known-bit toggles。这只能描述该仿真窗口的 RTL 活动度，不能换算为 mW、
pJ 或能量节省。

正式 C0/C1/C2 综合、OpenROAD 和 workload-driven power/energy 尚未完成，因此
目前不能提出物理 PPA 或能效结论。

## 9. 可复现性和证据质量

目前正式证据具备：

- clean committed source；
- 固定 CFG；
- simulator SHA-256；
- ELF、输入、日志和 trace 哈希；
- 三个独立进程；
- 精确一致的确定性周期；
- 相同输入和计时窗口；
- B1 禁止 RVV；
- B2-R/A1 必须存在 RVV load/mul/FMA/store；
- B2-R 独立 DASM witness；
- FSM、正确性和 terminal gate；
- 失败记录不删除。

三次重复的意义不是估计随机分布或置信区间，而是证明在相同提交、工具、CFG 和输入
下，仿真结果确定且可重现。不应对这些确定性重复计算 p 值，也不应把三次重复描述
为三个独立工作负载样本。

## 10. 当前证据分级

### 10.1 已经可以直接支持

1. RVV 是必要的强软件基线。
2. SMU recurrence offload 能显著降低逐行开销。
3. A1 在中大规模 anchor 上优于 A2。
4. A2 在极小 `(1,1)` 上仍可能更优。
5. 最佳划分依赖 N、D 和固定 handoff 开销。
6. Full SMU 的中大规模瓶颈转向 vector streaming。
7. 被测 anchor 满足正确性和确定性要求。
8. 被测单 stream 条件下 TCDM 拥塞不是主要瓶颈。

### 10.2 已显示稳定趋势，但仍需最终封口

1. 固定 D=64 时，A1 相对 B2-R 和 A2 的优势随 N 增长。
2. 完整 N/D crossover 位置。
3. 修复后全部 tail 与 numerical 边界。
4. 精确容量 pass/skip 阈值。
5. 修复后最终周期模型参数。

### 10.3 目前不能主张

1. 真实模型 workload 上一定获得相同加速。
2. 完整 attention 或 LLM 端到端加速。
3. SMU 具有真实面积、频率、功耗或能效优势。
4. 256 段 LUT 是最优数值设计。
5. 多 SMU 或任意 TCDM workload 下都无拥塞。
6. 该架构属于“首次”或不存在最近邻设计。

## 11. 统计与解释风险扫描

已检查 11/11 类常见方法学风险：

- Simpson 悖论：结果按 N/D 分开报告，没有只给聚合平均值；完整网格仍在进行。
- 生态谬误：未从矩阵级结果推断单个模型或用户级结论。
- Berkson/选择偏差：三个 anchor 存在选择风险，P0-4 网格用于缓解。
- Collider bias：没有观察性控制变量模型，不适用。
- Base-rate neglect：不是诊断分类实验，不适用。
- Regression to mean：确定性仿真且未按极端结果选组，不适用。
- Survivorship bias：失败、timeout、unsupported 和 skip 均保留。
- Look-elsewhere effect：case catalog 和 shard 计划预先版本化，最终必须汇总全部点。
- Garden of forking paths：失败后修复有独立提交和新 raw root，旧失败没有被覆盖。
- Correlation != causation：受控消融允许在当前仿真系统内做组件级因果归因，但不能
  外推到物理芯片和真实模型。
- Reverse causality：硬件配置是受控变量，不存在结果反向决定配置的问题。

## 12. 阶段性总结

综合来看，目前证据已较强支持：

> Scalar-only SMU + RVV 是当前实现中更合理的 online-softmax merge 执行边界。

其依据不是单个有利点，而是公平软件基线、A0/A1/A2 消融、周期/FSM 分解、正式
三次确定性运行、正确性 gate、TCDM 计数以及已经发现并保留的失败证据。

完整 scaling、真实 workload 和物理实现成本仍是把这一阶段性结论扩展为完整投稿
主张前必须完成的部分。

## 13. 仓库内结构化来源

- `experiments/parsed/progressive_baseline.csv`
- `experiments/reports/progressive_baseline.md`
- `experiments/reports/baseline_audit.md`
- `docs/online-softmax-merge-engine/实验设计与结果.md`
- `docs/online-softmax-merge-engine/SMU设计与创新点.md`

