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
