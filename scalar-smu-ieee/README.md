# Scalar SMU IEEE Paper

This directory holds the Scalar SMU manuscript: a selective HW/SW partition for
native online attention on a Spatz RISC-V vector cluster. A cluster-local Scalar
Online-Merge Unit (SMU) handles the state-dependent recurrence while the
existing Spatz/RVV datapath retains the D-dimensional output update.

`main.tex` is the complete manuscript (11 pages, five figures, six tables).
`IEEEtran` journal mode is used as a generic reading layout; no specific journal
template is targeted or claimed.

Build the PDF with:

```sh
make
```

The compiled paper is written to `build/main.pdf`; `make clean` removes the
build products.

References are managed in `references.bib` and cited in `main.tex` with
`\cite{key}`. The `IEEEtran` BibTeX style formats and numbers the bibliography
in citation order. The `make` target runs BibTeX automatically via `latexmk`
when needed.

`figure/` holds the five figure assets the manuscript includes, and
`figure/source/` keeps the base images and the edit script behind the Figure 2
and Figure 3 corrections. `literature-plan.md` records the literature placement
decisions that produced `references.bib`.
