# Scalar SMU: current English manuscript

This directory contains the 27 October 2026 English revision of
“Scalar SMU: Selective Recurrence Acceleration for Online Attention in a
RISC-V Vector Cluster”. It replaces the earlier long manuscript here.
The manuscript text, bibliography and figure assets are copied unchanged
from the current delivery package.

- `main.tex`, `references.bib`: manuscript and bibliography.
- `figure/`: three required figures and the editable architecture source.
- `IEEEtran.cls`, `IEEEtran.bst`: bundled class and bibliography style.
- `main.pdf`: reading copy, refreshed after a successful build.
- `build/`: ignored compiler outputs.

Run `make -C paper` from the repository root (or `make` here).
Dependencies: TeX Live, latexmk, pdfLaTeX, BibTeX and the packages named in
`main.tex`. Run `make -C paper clean` to remove compiler outputs.

Earlier English and Chinese manuscripts, delivery packages, revision notes
and the previous build directory are preserved in
`../archive/paper-before-20261101/`. The original current delivery package
there retains its evidence CSVs, provenance notes and independent review.
The review scope and limitations remain those stated in that report;
this directory cleanup does not establish new scientific validation.

The former root `run-archive/` is now `../archive/run-archive/`.
Historical paths inside archived reports are preserved as recorded.
