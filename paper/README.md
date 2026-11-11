# Scalar SMU Paper - Fig. 1 and Fig. 2 Updated

This bundle contains the original IEEEtran LaTeX manuscript with **Fig. 1 and Fig. 2 replaced by the newly provided diagrams.net PDF figures**.

Build in this directory:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The paper uses `figure/cluster_integration.pdf` (Fig. 1) and `figure/smu_microarchitecture.pdf` (Fig. 2) directly to preserve the vector drawings and embedded fonts. Corresponding SVG vector exports and the recovered editable `.drawio` sources are provided in `figure/`. `figure/performance_isa.pdf` remains the paper's Fig. 3.

All main text, figure references, labels, and the remaining experimental plots are kept as in the preceding manuscript.
