# M8 Final Fix

**Status:** FIX-01--FIX-15 implemented and mechanically checked.  No new
experiment, RTL change, software change, cluster-PPA flow, or active final
evidence regeneration was performed.

**Authorized issue list:** `experiments/reports/M7_TCASII_REVIEWER_AUDIT.md`.
The manuscript remains bounded to the measured merge-kernel and standalone
Scalar SMU block evidence.  Full-Offload remains an internal ablation.

## FIX closure

| Issue | Closure evidence |
| --- | --- |
| FIX-01 | Figure 3 is a single-column 88.9 mm export.  `main.pdf` has exactly five pages; the page-5 right column contains references only.  Figure 3 and the Conclusion are both in the left column, with the Conclusion uninterrupted by a float. |
| FIX-02 | Main text, claim dictionary, P3, P3 CSV notes, and P18 call `13+1+1+9` a nominal no-stall schedule.  They report model-shape observers of 289/769/962 cycles with occasional TCDM waits and separate these observations from fitted coefficients and system latency.  Raw P3 cycle values are unchanged. |
| FIX-03 | B2R is first defined as the matched-arithmetic RVV baseline.  The cycle ratio is explicitly B2R measured cycles divided by design measured cycles. |
| FIX-04 | Page 1 positions prior work at broad/full-offload or programmable/vector endpoints and states that the contribution is dependency-aligned recurrence placement, not a new recurrence, algorithm, or LUT. |
| FIX-05 | VFA is cited and distinguished in Related Work.  The manuscript uses positive bounded positioning and contains no exhaustive negative novelty sentence. |
| FIX-06 | Figure 2, its caption, and the evaluation call $C_s$ the fitted N-dependent cycles/row coefficient and $C_v$ the fitted ND-dependent cycles/element coefficient.  The text reports $R^2=0.99928$--$0.99999$ and says $C_v$ remains within 6.22% of B2R. |
| FIX-07 | Figure 3 and its surrounding text use “merge-kernel cycle-count ratio versus standalone accelerator-block area,” state that the axes are separate evidence rather than cluster PPA or area efficiency, and distinguish B/M/Q markers. |
| FIX-08 | Setup and Table I define $N$ as query-head count and $D$ as per-head width, state the GQA query-head convention, and identify deterministic generated states for one logical query position rather than captured activations or end-to-end inference. |
| FIX-09 | Setup states 26 cases x 3 configurations x 3 deterministic reruns, the matched-LUT scale-aware $10^{-3}$ functional check, no nonfinite values, and rerun reproducibility.  It disclaims formal verification, IEEE-exact arithmetic, and model-level accuracy. |
| FIX-10 | The three contributions are recurrence-only Scalar SMU plus nominal schedule, unchanged-ISA TCDM/RVV integration, and the measured selective-boundary result with Full-Offload limited to an internal ablation. |
| FIX-11 | Repeated mechanism/workload/hardware takeaway paragraphs were removed.  TCDM is described as the handoff mechanism; causal language is bounded to the measured comparison. |
| FIX-12 | Reader-facing terminology uses Scalar SMU + RVV, Qwen2.5-14B-Instruct, Softmax, and $F_{\max}$.  VFA is included in `refs.bib` and resolves in the compiled bibliography. |
| FIX-13 | Table II displays 12.34 ns and 13.20 ns PARTIAL reg-to-reg proxies and names Nangate45 Liberty cell-area units.  The manuscript states once that area is an unconstrained pre-layout research-library proxy and timing does not support $F_{\max}$ or design ranking. |
| FIX-14 | Figure 2 is 180 x 72 mm and Figure 3 is 88.9 x 68.0 mm.  Both retain editable SVG/PDF text, 600-dpi PNG previews, readable labels, and unclipped exports. |
| FIX-15 | PDF title metadata, two-pass LaTeX build, five-page output, embedded fonts, zero overfull boxes, zero unresolved citations/references, and `git diff --check` all pass. |

## Evidence and source mapping

Figure 2 reads the three `parameter` rows of
`experiments/parsed/final_scaling_model.csv`; no rows are excluded.  Figure 3
reads all three workload rows and the geomean from
`experiments/parsed/final_workload_comparison.csv`, plus A1/A2 area from
`experiments/parsed/final_area.csv`.  Table I uses the same workload rows and
Table II uses `final_area.csv` and `final_timing.csv`.  The correctness and
observer statements are checked against the 234 PASS rows in
`experiments/parsed/m2/m2_all_records.csv` and the model-shape audit.  The
active final CSVs were not modified in M8.  `p3_smu_latency_breakdown.csv`
received notes only; its numeric stage values remain 13, 1, 1, 9, 24, and
1316.

Independent recomputation from the active integer cycle rows gives:

| Quantity | Recomputed value |
| --- | ---: |
| A1 geomean cycle ratio | 4.526920018368193 |
| A2 geomean cycle ratio | 1.8857656103077807 |
| B2R/A1 fitted $C_s$ ratio | 16.303154467395252 |
| A1 fitted $C_v$ relative to B2R | -6.221841243413994% |
| A2/A1 fitted $C_v$ ratio | 3.776776267059129 |
| A2/A1 Liberty area ratio | 1.487787291883724 |
| A2/A1 Liberty area delta | 48.778729188372381% |

The manuscript displays these values at the contracted precision of 4.53x,
16.30x, 6.22%, 3.78x, and 48.8%.  The headline cycle values are measured
merge-kernel ratios, not frequency, wall time, throughput, or end-to-end
inference results.

## Figure and PDF QA

Both figure scripts use the Python/matplotlib backend and were run twice.
PDF, SVG, and PNG outputs were byte-identical across the two generation runs.
The static figure validator returned 13 PASS and one accepted WARN for each
script.  The WARN is the absence of a TIFF export; the requested deliverables
are vector PDF/SVG plus a 600-dpi PNG preview.  Visual inspection at final
size found no clipping or overlap.  Figure 1 was not regenerated or edited;
its accepted architecture semantics are Scalar SMU recurrence, existing RVV
vector update, TCDM handoff, and no Full-Offload path.

The final PDF was compiled twice with:

```text
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

It has five pages, letter dimensions, title metadata
`A Scalar Softmax Merge Unit With Selective Offloading for RISC-V Vector
Clusters`, and SHA256
`97993619a208bde187303ab4cca01fa4eae9bdab9f8d5de96325236ad39343ee`.
`pdffonts` reports embedded/subsetted fonts.  The log contains no undefined
citation/reference, overfull-box, emergency-stop, or fatal-error diagnostics.
The final page was rendered and inspected: its right column contains only
references [9]--[12].

## SHA256 manifest

| Artifact | SHA256 |
| --- | --- |
| `experiments/plots/figure1_proposed_architecture.pdf` | `bd504b584fe0fdcb813968f0c1d63d2e5d6e5e3e14a8831007ada65924a6b7d6` |
| `experiments/plots/figure1_proposed_architecture.png` | `1517f85ad373e2bd3842d049660cfa2618e23b0264fb867f9035c4d92b2abf81` |
| `experiments/plots/figure1_proposed_architecture.svg` | `197158ed7302a1aa4339d83aaf6cb957896327e0d533fac1c2193522af8791b3` |
| `experiments/plots/figure2_scaling.pdf` | `7207bed4727e9d6eb960491efa4c5fdfebc4b26ce2f1dab19ee7cb107edf9819` |
| `experiments/plots/figure2_scaling.png` | `c77ea57a9413c4006ad57124f18a4ed2f3c0d5bb010e2084ebe9674c92979c33` |
| `experiments/plots/figure2_scaling.svg` | `283a7e635e90a52cf74f3d3e69ac383d6486f0d4e2e6440b0fe96f5efb8e7727` |
| `experiments/plots/figure3_hardware_tradeoff.pdf` | `2030bf329453b8c560d21a7cc33e4d134166304372d33c61de219b7e327167ba` |
| `experiments/plots/figure3_hardware_tradeoff.png` | `3ed9b3e7b1f749ecfbfb4df66c0a077fc7cf74f33621e8c46a8d89e7ad9bbddd` |
| `experiments/plots/figure3_hardware_tradeoff.svg` | `91ddb774e467fa7d4979c71adb96df7007a027b22d21193af343c35852e12488` |
| `paper/online-merge-smu/main.pdf` | `97993619a208bde187303ab4cca01fa4eae9bdab9f8d5de96325236ad39343ee` |
| `paper/online-merge-smu/main.tex` | `7bc6b8666071b526dcf4bdaf101bbed90b6c648d5293e4ef6b7487a4e8f744b6` |
| `paper/online-merge-smu/refs.bib` | `41efbef07a8e8436dc9e0d6ce64a622b678c5f66bd25c54e52f03544e1bd0bbf` |

## Mechanical gates

`python -m py_compile` passes for both figure scripts.  Targeted stale-wording
greps over the manuscript return zero hits for the retired baseline label,
formal-run label, fixed-schedule label, legacy area-axis label, and negative
novelty sentence.  Greps also find no withdrawn 81.02/75.74 MHz claims or
unsupported synchronous frequency inversion.  `git diff --check` passes.

## Final micro-fix closure

The final Sol red-team micro-fix made only three scoped changes.  The
Abstract now defines B2R once as the matched-arithmetic RVV baseline.  The
Conclusion states that fitted $C_v$ remains within 6.22\% of B2R.  The VFA
BibTeX entry uses `howpublished = {arXiv:2604.12798}`; IEEEtran renders
`arXiv:2604.12798` in reference [7].

The post-fix build passes `latexmk -pdf -interaction=nonstopmode
-halt-on-error main.tex` twice.  `pdfinfo` reports five letter-size pages and
the required PDF title.  The final page's right column remains references
only.  `pdffonts` reports all listed fonts embedded and subsetted.  Log greps
find no undefined citation/reference, overfull box, emergency stop, or fatal
error.  `git diff --check` passes.  No CSV, figure, RTL, software, or
experiment file was modified by this micro-fix.

The subsequent provenance repair reran the existing deterministic freeze
script and synchronized the P3 input hash in
`experiments/parsed/final_evidence_manifest.json` to
`b326f794b881f2f6037d6e153544080809a065af3c93aa8645ae74352a14b03a`.
All other active CSV and manifest input/output/script hashes match their
files, and a second freeze run was byte-identical.
