# 文献规划记录

记录日期：2026-09-22

以下为用户提供的文献方向与放置建议。候选文献已于 2026-09-22
映射到 `references.bib`；新增条目经过元数据核验，尚未新增正文引用。

| 文献方向 | 建议代表工作 | 放置位置 | 作用 |
| --- | --- | --- | --- |
| Attention 基础 | Vaswani et al., *Attention Is All You Need* | Intro P1 | 基础 |
| Online normalization | Milakov & Gimelshein, *Online Normalizer Calculation for Softmax* | Intro P1 / Sec. II | 直接基础 |
| IO-aware attention | *FlashAttention* | Intro P1 / Sec. II | 直接基础 |
| Online attention evolution | *FlashAttention-2* | Intro P1 | 扩展算法背景 |
| Low-precision online attention | *FlashAttention-3* | Intro P1 / comparison | 混合精度/现代 attention 背景 |
| Hardware-friendly Softmax | *Softermax* | Intro P3 / Sec. V | 与你的 mixed-precision / online normalization 很接近 |
| RISC-V EXP acceleration | *VEXP* | Intro P3 / Sec. V | 强相关 |
| Dedicated Softmax HW | *SoftEx* | Intro P3 / Sec. V | 强相关 |
| Softmax HW reuse | *Reusing Softmax Hardware Unit for GELU Computation in Transformers* | Intro P3 / Sec. V | 非线性单元复用背景 |
| Transformer nonlinear HW | *TRETA* | Intro P3 / Sec. V | Softmax/LayerNorm 专用硬件 |
| Nonlinear approximation | *A Low-Cost Reconfigurable Nonlinear Core...* | Sec. V | LUT / approximation 背景 |
| Nonlinear approximation | *A Low-complexity and Reconfigurable Design for Nonlinear Function Approximation in Transformers* | Sec. V | 近期 nonlinear hardware |
| Vector baseline | *Ara* | Intro / Sec. III / V | RISC-V vector 背景 |
| Scalar cluster | *Snitch* | Sec. III / V | 你的平台基础 |
| Vector cluster | *Spatz* | Intro / Sec. III | 直接平台 |
| Matrix accelerator | *RedMule* | Sec. V | heterogeneous cluster |
| Selective vector specialization | *TOP-V* | Intro P3 / Sec. V | 设计思想强相关 |
| RISC-V heterogeneous Transformer | *Toward Attention-based TinyML* | Intro / Sec. V | 与你的 cluster + accelerator 很合适 |
| Full-stack accelerator | *Gemmini* | Sec. V | coarse-grained co-design |
| Heterogeneous deployment | *Deeploy* | Sec. V | compiler/system-level comparison |
| Transformer FPGA compiler | *TRAC* | Sec. V | broader accelerator background |
| End-to-end Transformer accelerator | *DFX* | Sec. V | broader system comparison |
| Attention accelerator | *FAMOUS* | Sec. V | dense MHA hardware |
| Transformer sparsity accelerator | *Edge-MoE* / *FAS-Trans* | Sec. V | broader Transformer HW landscape |

## BibTeX 入库记录

24 行建议包含 25 篇候选文献。复用现有 11 条，新增 14 条；加上原有
RISC-V ISA 手册，`references.bib` 共 26 条。原有条目保持原引用键和信息，
本次未对其执行完整的元数据复核。正文与正文引用均未修改。

新增条目使用 Crossref 的 DOI 元数据，必要时结合出版方或作者页面识别
缩写对应的完整标题。以下 DOI 链接同时作为元数据来源索引。

| 记录中的工作 | BibTeX key | 入库情况 / 来源 |
| --- | --- | --- |
| Attention Is All You Need | `vaswani2017attention` | 复用现有条目 |
| Online Normalizer | `milakov2018online` | 复用现有条目 |
| FlashAttention | `dao2022flashattention` | 复用现有条目 |
| FlashAttention-2 | `dao2024flashattention` | 复用现有条目 |
| FlashAttention-3 | `shah2024flashattention3` | 新增；[NeurIPS 2024](https://papers.nips.cc/paper_files/paper/2024/hash/7ede97c3e082c6df10a8d6103a2eebd2-Abstract-Conference.html) |
| Softermax | `stevens2021softermax` | 新增；[DAC 2021](https://doi.org/10.1109/DAC18074.2021.9586134) |
| VEXP | `wang2025vexp` | 复用现有条目 |
| SoftEx | `belano2025softex` | 复用现有条目 |
| Reusing Softmax Hardware Unit for GELU | `peltekis2024gelu` | 新增；[AICAS 2024](https://doi.org/10.1109/AICAS59952.2024.10595882) |
| TRETA | `shao2023treta` | 新增；[IEEE TVLSI 2023](https://doi.org/10.1109/TVLSI.2023.3305569) |
| A Low-Cost Reconfigurable Nonlinear Core... | `li2020nonlinear` | 新增；[ICFPT 2020](https://doi.org/10.1109/ICFPT51103.2020.00014) |
| A Low-complexity and Reconfigurable Design... | `wu2025nonlinear` | 新增；[IEEE TCSII 2025](https://doi.org/10.1109/TCSII.2025.3585109) |
| Ara | `cavalcante2020ara` | 新增；[IEEE TVLSI 2020](https://doi.org/10.1109/TVLSI.2019.2950087) |
| Snitch | `zaruba2021snitch` | 新增；[IEEE TC 2021](https://doi.org/10.1109/TC.2020.3027900) |
| Spatz | `Spatz2025` | 复用现有条目 |
| RedMule | `tortorella2023redmule` | 复用现有条目 |
| TOP-V | `chen2026topv` | 复用现有条目 |
| Toward Attention-based TinyML | `wiese2025tinyml` | 新增；[IEEE Design & Test 2025](https://doi.org/10.1109/MDAT.2025.3527371) |
| Gemmini | `genc2021gemmini` | 复用现有条目 |
| Deeploy | `scherer2024deeploy` | 复用现有条目 |
| TRAC | `plagwitz2022trac` | 新增；[FPL 2022](https://doi.org/10.1109/FPL57034.2022.00015) |
| DFX | `hong2022dfx` | 新增；[MICRO 2022](https://doi.org/10.1109/MICRO56248.2022.00051) |
| FAMOUS | `kabir2024famous` | 新增；[ICFPT 2024](https://doi.org/10.1109/ICFPT64416.2024.11113430) |
| Edge-MoE | `sarkar2023edgemoe` | 新增；[ICCAD 2023](https://doi.org/10.1109/ICCAD57390.2023.10323651) |
| FAS-Trans | `wang2024fastrans` | 新增；[ICCAD 2024](https://doi.org/10.1145/3676536.3676743) |

### 版本选择

- FlashAttention-3 使用 NeurIPS 2024 正式版本；TinyML 使用 2025 年期刊版本。
- TRETA 的正式标题为 *An Efficient Training Accelerator for Transformers
  With Hardware-Algorithm Co-Optimization*。
- 省略的 Low-Cost 标题补全为 *A Low-Cost Reconfigurable Nonlinear Core for
  Embedded DNN Applications*。
- Wu 等的 Low-Complexity 工作存在 ISCAS 与 TCSII 两个 2025 年同名版本；
  选用 TCSII 期刊版本，未重复收录会议版。
- DFX 选用 MICRO 2022 的 616–630 页版本，未重复收录 Hot Chips 版本。
- FAMOUS 选用 ICFPT 2024 的两页正式条目，并保留完整预印本
  [arXiv:2409.14023](https://arxiv.org/abs/2409.14023) 的标识，便于后续精读。
- FAS-Trans 的作者顺序采用出版方注册到 Crossref 的元数据：
  Hongji Wang、Kun Wang、Yifan Zhang、Jun Yu；作者个人网页的简写顺序与之不同。

本次为书目信息入库，不代表已核验原表中每项“作用”所对应的技术论断。
