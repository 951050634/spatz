# Scalar SMU IEEE Paper Skeleton

This directory contains a minimal IEEE conference paper skeleton for the Scalar
SMU work. The source includes abstract and reference placeholders, the requested
section hierarchy, and TODO comments.

Build the PDF with:

```sh
make
```

The compiled paper is written to `build/main.pdf`.

References are managed in `references.bib` and cited in `main.tex` with
`\cite{key}`. The `IEEEtran` BibTeX style formats and numbers the bibliography
in citation order. The existing `make` command runs BibTeX automatically via
`latexmk` when needed.
