# Figure QA Notes

## A0/A1/A2 ablation comparison

- Core conclusion: scalar-only SMU offload plus RVV vector update is fastest at
  the two larger anchors, while Full SMU is slightly faster at `(1,1)`.
- Source data: all A0/A1/A2 measurements at the three recorded anchors from the
  same experiment batch; the accompanying CSV preserves min, median, max, and
  measured-repeat count.
- Statistics: points show medians and whiskers show the full min--max range over
  three measured repetitions. Speedups use ratios of cycle medians. No
  inferential statistical test is claimed for deterministic RTL simulation.
- Exclusions: none; all 27 measured observations contribute to the summaries.
- Transform: panel a uses a guarded positive log scale because the measured
  cycle medians span more than one order of magnitude. Panel b uses A0-normalized
  median speedup on a linear scale.
- Integrity: the SVG contains editable text; PDF/PNG/TIFF previews are rendered
  from that Python-generated SVG. No raster data panels or image adjustments
  occur.
- Evidence caveat: the batch validates the implementation and design trend but
  records a dirty worktree; repeat the same anchors on a clean commit before
  treating the figure as a publication checkpoint.

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
