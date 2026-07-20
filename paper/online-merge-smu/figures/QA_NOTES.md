# Figure QA Notes

## SMU scaling and bottleneck

- Core conclusion: Full SMU outperforms B2-R at every direct measurement, and
  the limiting work moves from command overhead to vector streaming.
- Source data: 16 direct scaling coordinates, all three FSM anchor coordinates,
  and all recorded repetitions per anchor.
- Statistics: scaling cells show medians over three simulation repetitions;
  FSM stacks show medians over the three measured runs.
- Exclusions: none. The FSM panel has three coordinates because the source
  experiment measures those three anchors only.
- Integrity: vector SVG contains editable text; no raster data panels or image
  adjustments occur.

## SMU concurrency and proxies

- Core conclusion: shared-TCDM execution preserves component time for the
  recorded core/SMU scenarios; generic-cell and toggle measurements identify
  follow-up targets but do not establish physical PPA.
- Source data: all C1/C2/C3 summary rows, all four Yosys scopes, and all six
  B2-R/B3 toggle samples.
- Statistics: concurrency bars use median slowdown. No inferential tests apply
  to these deterministic RTL simulation measurements.
- Exclusions: none.
- Integrity: resource and toggle panels label their proxy status in the figure.
