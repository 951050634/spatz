# LaTeX 工作区

本目录保存 online softmax merge engine 相关论文草稿、共享引用和本地
TeX Live 配置。正文源文件统一放在 `papers/` 下；根目录不再保留论文 wrapper
文件或编译产物。

## 目录结构

```text
latex/
├── common/
│   ├── bib/
│   │   └── refs.bib
│   └── figures/
│       └── README.md
├── papers/
│   ├── paper-a/
│   │   ├── README.md
│   │   └── paper_a.tex
│   ├── paper-b/
│   │   ├── README.md
│   │   └── paper_b.tex
│   └── paper-ab/
│       ├── README.md
│       └── paper_ab.tex
└── texlive.profile
```

`paper-a` 是受限语义集成 baseline，`paper-b` 是完整 mixed-scalar datapath
阶段草稿，`paper-ab` 是将 A+B 合成一篇系统原型文章的当前主稿。

## 数据来源

论文数据来自：

```text
../docs/online-softmax-merge-engine/COMPARISON_EXPERIMENT.md
../data_process/attnres/data/online_softmax_merge_bypass.csv
../data_process/attnres/data/online_softmax_merge_bypass_stability.csv
../data_process/attnres/data/online_softmax_full_mixed_bypass.csv
../data_process/attnres/data/online_softmax_full_merge_numeric.csv
../data_process/attnres/data/online_softmax_attention_like_smu.csv
```

图表由以下脚本生成：

```bash
source ../.venv/bin/activate
python ../data_process/attnres/code/plot_attnres_results.py
```

## 当前 Linux LaTeX 环境

已安装用户级 TeX Live：

```text
/home/wxt/.texlive/2025
```

`~/.bashrc` 已加入：

```bash
export PATH=/home/wxt/.texlive/2025/bin/x86_64-linux:$PATH
```

已验证的工具：

```text
pdflatex
bibtex
latexmk
tlmgr
```

补装过的 TeX Live 包：

```text
latexmk
ieeetran
booktabs
xcolor
times
courier
```

编译论文 A：

```bash
cd ~/spatz/latex/papers/paper-a
latexmk -pdf -interaction=nonstopmode -halt-on-error paper_a.tex
```

编译论文 B：

```bash
cd ~/spatz/latex/papers/paper-b
latexmk -pdf -interaction=nonstopmode -halt-on-error paper_b.tex
```

编译 A+B 综合稿：

```bash
cd ~/spatz/latex/papers/paper-ab
latexmk -pdf -interaction=nonstopmode -halt-on-error paper_ab.tex
```

清理生成文件：

```bash
cd ~/spatz/latex/papers/paper-a
latexmk -C paper_a.tex

cd ~/spatz/latex/papers/paper-b
latexmk -C paper_b.tex

cd ~/spatz/latex/papers/paper-ab
latexmk -C paper_ab.tex
```

PDF、aux、log、bbl 等编译产物由 `latex/.gitignore` 忽略，不应提交。
