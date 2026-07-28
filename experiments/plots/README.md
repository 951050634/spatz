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

The selected backend is Python.  Rendering currently stops with an explicit
dependency error because `matplotlib` is absent; no cross-backend substitute
or fabricated preview is produced.

The source preflight reports one accepted warning: no TIFF export.  These are
vector bar charts, so PDF/SVG are the submission masters; the 600 dpi PNG is
only a review preview, not a replacement for vector line art.
