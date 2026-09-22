# Figure Revision Notes

本文件记录当前图片在论文排版和审查中发现的修改项。图片本身不在本次任务中
重新绘制；后续由作者替换或编辑图片后，应重新编译论文并检查单栏可读性。

## 修改清单

| 图片 | 当前状态 | 优先级 | 需要处理的内容 |
| --- | --- | --- | --- |
| `fig2_fixed.png` | 单栏排版已满足要求；图中未显示 completion response 回程 | P1 / DEFERRED | 补充 SMU/OMERGE adapter → owner-routed response demux → issuing Snitch core 的回程；保持 SMU 为独立 TCDM requester，不要画成 RVV datapath 的内部单元 |
| `fig3.png` | 单栏排版已满足要求；图中未显示更新后的标量状态回写 | P1 / DEFERRED | 补充 `\widehat{m}'`、`\widehat{l}'` 经 FP32 编码后写回 TCDM 的路径，并明确 FP32 是 memory-side carrier、Q16.32 是内部 normalization carrier |
| `fig1.png` | 图内已包含一行 `Fig. 1.` 说明，可能与 LaTeX caption 重复 | P2 / SUGGESTION | 后续导出时优先裁掉图内 caption 行，或改用不含 caption 的图像源；保留图内 `Key observation` 框即可 |

## Fig. 2 (`fig2_fixed.png`)

建议在现有 OMERGE adapter/Scalar SMU 模块和 Snitch scalar core 之间增加一条
明确的 completion 回程：

```text
OMERGE adapter / SMU
        -> response
        -> owner-routed response demux
        -> issuing Snitch scalar core
```

建议同时检查：

- `Cluster Issue Arbiter` 记录 issuing core/owner 的位置是否清楚；
- response demux 与 issue arbiter 的方向是否可区分，避免读者误认为只有请求路径；
- SMU 与 Existing Spatz/RVV Datapath 是否仍画成两个独立的 TCDM requester；
- 图片中的 `standard RVV semantics` 可改为 `supported RVV instruction semantics`，
  以避免把实现的 RVV 子集表述成完整 RVV 覆盖；
- 缩放到 IEEE 单栏宽度后，模块名、箭头标签和 `128 KiB, 16 banks` 仍应可读。

正文证据位置：`main.tex` 的 System Overview 段落；RTL 路径位于
`hw/system/spatz_cluster/src/spatz_cluster.sv` 的 OMERGE issue arbiter、owner
记录和 response demux。

## Fig. 3 (`fig3.png`)

建议在现有混合精度数据通路中补充状态回写分支：

```text
updated m', l'
  -> FP32 encoding / carrier
  -> TCDM state writeback
```

建议同时检查：

- `\widehat{m}'` 来自 FP16-RNE maximum，`\widehat{l}'` 来自 Q16.32 recurrence；
- FP32 回写只恢复 memory-side carrier，不恢复已经丢弃的内部精度；
- EXP 路径明确标注：256-entry signed Q1.14、`[-8,0]`、direct lookup、winner bypass；
- reciprocal 路径明确区别于 EXP：256-entry unsigned Q1.15、piecewise-linear
  interpolation 和 exponent correction；
- shared 48x16 multiplier 的 old/tile sequential reuse 仍保持可见；
- `static per-stage assignment` 保持不变，不能暗示 runtime-adaptive precision；
- 图中若保留 `FP32/Q16.32 preserve external state`，建议改为：
  `FP32 carries memory-visible state; Q16.32 provides internal normalization range.`

正文证据位置：`main.tex` 的 Stage-Aware Mixed-Precision SMU 段落；数值路径位于
`hw/ip/online_merge/src/online_merge_update_engine.sv` 和相关 fixed-point helper。

## 统一排版复核

替换图片后请确认：

1. Fig. 2 和 Fig. 3 继续使用 `\begin{figure}`，而不是 `figure*`；
2. `\includegraphics[width=\columnwidth]{...}` 保持单栏宽度；
3. caption、`\label` 和 `\ref` 名称不变；
4. 最终 PDF 中图片在约 `252 pt` 单栏宽度下文字清晰，且没有 overfull box；
5. 新图片应保留可编辑源文件或生成 provenance，便于后续审稿和复现。
