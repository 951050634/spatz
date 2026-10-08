# 中文版翻译说明

中文版以 `main.tex` 的完整 v5 稿件为唯一来源，生成 `main-zh.tex`。
翻译涵盖标题、摘要、关键词、全部正文、五幅图的图注、七张表的
表题与说明文字，以及讨论、局限和结论。没有删节或补充实验结果。

公式、变量、指令编码、实验数值、测量范围和引用键保持一致。
专用指令、系统名称、数值格式以及 Native Core 等测量窗口名称保留英文。
图内文字和参考文献条目保留原文；中文图注提供对应说明。
作者姓名沿用英文稿的署名。

| 原文术语 | 中文版用法 |
|---|---|
| native online attention | 原生在线注意力 |
| scalar recurrence | 标量递推 |
| running maximum | 累积最大值 |
| normalizer | 归一化因子 |
| tile-local state | 块内状态 |
| selective partition | 选择性划分 |
| stage-aware mixed precision | 分阶段混合精度 |
| persistent context | 持久化上下文 |
| state ownership | 状态管理权 |
| pre-layout delay proxy | 布局前延迟估计值 |
| explicit-P negative control | 显式 P 负对照 |
| anchor workloads | 主要测试用例 |
| RNE (round-to-nearest-even) | 就近舍入，等距时取偶数 |
| tightly coupled data memory (TCDM) | 紧耦合数据存储器（TCDM） |

英文稿与中文版的全部独立公式环境、公式标签、图文件引用均逐项一致；
行内数学表达式的内容和出现次数一致，顺序随中文语法调整。
全部数字记号以及参考文献引用键的出现次数一致。
逐段对应记录见 `build/translation-source-map.json`，其中包含英文源文件行号。

在 `paper` 目录运行 `make zh` 编译，输出为 `main-zh.pdf`。
使用 IEEEtran 双栏阅读布局、LuaLaTeX 和 Noto CJK 字体。
中文版是中文阅读稿，不声明符合某一具体中文期刊的投稿格式。

## 编译与版面检查

中文 PDF 共 10 页，包含完整的七个正文一级章节、五幅图、七张表和参考文献。
全部字体已嵌入；最终日志无未解析引用、缺字及 overfull 溢出警告。
已查看全部页面缩略图，未发现图表裁切、重叠或空白页。
日志包含字体字形替代和本地 LaTeX 版本提示，未影响编译或文字显示。
英文 `main.tex` 与 `references.bib` 未作修改。

## 贴近原文与中文表达修订

逐段对照英文稿，对摘要、正文、图注和表格用语进行修订。
采用中文计算机体系结构论文的常用表达，调整英语长句的语序，明确主语、
操作对象与因果关系，并统一术语。技术名称和测量窗口名称保留原文。

- running maximum 译为“累积最大值”，避免将 running 误解为运行时配置。
- stage-aware mixed precision 译为“分阶段混合精度”，明确各阶段精度固定。
- status consumption 按语境译为“软件读取返回状态”，不采用“状态消费”的直译。
- matched comparisons 按语境表述为“同条件对照”，anchor workloads 为“主要测试用例”。
- RNE 明确为“就近舍入，等距时取偶数”，保留其完整舍入规则。
- delay proxy 译为“延迟估计值”，其布局前性质、未达到目标及集成测量缺失等限定完整保留。
- 对性能收益、负结果、未验证范围及与既有工作的关系，保持原文的结论强度。

全部数学表达式、数值记号、指令编码、图文件引用和引用键再次核对一致。
