# Generated plots

Plots are generated from `experiments/parsed/`.  Plot scripts must reject
missing or ineligible data instead of substituting historical constants.

## P0 figure contract

- Core conclusion: successive RVV, scalar-SMU, and full-SMU stages must be
  compared against the same input and the strong B2-R baseline.
- Evidence chain: `progressive_cycles.pdf` shows total kernel cost;
  `progressive_breakdown.pdf` separates trace-attributed software intervals
  from exact SMU FSM and timing-boundary counters.
- Archetype: quantitative comparison grid with the total-cycle panel as the
  primary evidence.
- Export: double-column-width PDF and SVG with editable text plus a 600 dpi PNG
  preview, white background, restrained method-family colors, and 7 pt base
  text.
- Source data: `progressive_baseline.csv` and `progressive_breakdown.csv`.
- Replicates: three independent deterministic simulator processes; no mean or
  error bar is shown unless all cycle values are exactly equal.

Historical P0 environment note: the selected backend was Python, and that
environment stopped rendering with an explicit dependency error because
`matplotlib` was absent.  Figure 1 is rendered from the existing
Python/matplotlib environment; no cross-backend substitute or fabricated
preview is used.

The source preflight reports one accepted warning: no TIFF export.  These are
vector bar charts, so PDF/SVG are the submission masters; the 600 dpi PNG is
only a review preview, not a replacement for vector line art.

## Figure 1 — proposed architecture

`experiments/scripts/make_figure1_architecture.py` generates
`figure1_proposed_architecture.svg`, `figure1_proposed_architecture.pdf`, and
`figure1_proposed_architecture.png`.  The schematic is a 180 × 88 mm white
canvas with 7 pt minimum text, editable SVG text (`svg.fonttype=none`),
TrueType PDF text (`pdf.fonttype=42`), and a 600 dpi PNG review preview.

The binding architecture is Scalar SMU + RVV: a new blue Scalar SMU performs
the state-dependent scalar recurrence and writes weights to the shared,
software-visible TCDM; the reused green RVV datapath later performs the regular
`O[D]` vector update.  The separate MMIO interface and dashed software paths
show command/status sequencing.  Solid paths show TCDM data movement; there is
no direct SMU-to-RVV datapath.
