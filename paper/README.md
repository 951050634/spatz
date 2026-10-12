# Scalar SMU IEEE manuscript

This directory retains the latest manuscript, revision v5 (29 September 2026).
The manuscript text, bibliography, figures, and editable figure sources are
preserved without content changes.

- `main.tex`: editable manuscript.
- `references.bib`: bibliography.
- `figure/`: figure assets and editable sources.
- `main.pdf`: freshly compiled reading copy.
- `main-zh.tex`: complete Chinese translation of the manuscript.
- `main-zh.pdf`: compiled Chinese reading copy.
- `translation-notes.md`: translation scope, terminology, and verification.
- `build/`: compilation outputs and log.

Run `make` to compile `build/main.pdf`. To refresh the reading copy, run
`cp build/main.pdf main.pdf` after a successful build.

Run `make zh` to compile the Chinese version with LuaLaTeX and BibTeX.
The target writes `build/zh/main-zh.pdf` and refreshes `main-zh.pdf`.
Chinese typesetting requires `ctex`, `luatexja`, and the Noto CJK fonts.

The generic IEEEtran journal layout does not target a named venue.

## Chinese manuscript (`main-zh.tex`)

Consolidated Chinese version of the manuscript, task `scalar-smu-20261011`.
It carries the Scalar SMU + RVV design as the main contribution, with Full SMU
kept only as the partitioning ablation. No new experiments were added and no
baseline or measurement window was changed during the Chinese revision rounds.
The `scalar-smu-zh-r1` snapshot package that preceded it was folded into this
file and removed.

Reference verification is still open for four entries (`ref1`, `ref2`, `ref4`,
`ref14`), which have pending Crossref checks. This records an unfinished check,
not a finding that the citations are wrong.
