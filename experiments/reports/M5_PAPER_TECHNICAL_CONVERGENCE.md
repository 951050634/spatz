# M5 Paper Technical Convergence

Status: complete after Sol-review targeted fixes.  The working-tree HEAD is
`7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`.  This pass changes only the
selected manuscript sections, the reproducible PDF, and this report.  Related
Work, `refs.bib`, RTL, software, and figure assets remain outside the M5 scope.

## Terminology ledger

| Term | M5 usage |
| --- | --- |
| Scalar Softmax Merge Unit | Expanded first use for the proposed scalar engine |
| Scalar SMU | Short name for the proposed engine after expansion |
| selective scalar offloading | Core architectural abstraction |
| online Softmax merge | The state update operation |
| Proposed | A1: Scalar SMU for recurrence plus existing RVV for vector update; area numbers refer to the standalone Scalar SMU block |
| B2R | Software scalar recurrence plus existing RVV; primary strong baseline |
| Full-Offload ablation | A2: scalar recurrence and vector update in the standalone Full-Offload block |
| RISC-V Vector (RVV) | Existing vector datapath retained by Proposed |
| tightly coupled data memory (TCDM) | Software-visible handoff storage |
| memory-mapped I/O (MMIO) | Command and completion interface |
| vector load/store unit (VLSU) | Existing RVV memory path |
| fused multiply-add (FMA) | Existing RVV arithmetic path |
| measured merge-kernel cycles | RTL/Verilator one-position model-shape scope |
| `C=C_0+C_sN+C_vND` | Fitted cycle model; `C_s` is cycles/row and `C_v` is cycles/element |
| mapped cells | Area-flow cell count, kept separate from Liberty area |
| Nangate45 Liberty cell-area units | Area-flow library units, not cell count |
| PARTIAL reg-to-reg proxy | Pre-layout Nangate45/ABC combinational delay only |
| synchronous Fmax | UNAVAILABLE; no inverse-delay claim is made |

## Claim to evidence to section map

| Claim | Active evidence | Manuscript location |
| --- | --- | --- |
| Online merge separates a scalar recurrence from an `O[D]` update | `experiments/parsed/final_scaling_model.csv`, M2 audit | Abstract, Introduction, Selective-Offload Architecture |
| Proposed assigns only the recurrence to Scalar SMU | `experiments/reports/M2_MATCHED_LUT_REVALIDATION.md`, Figure 1 hash from M4 | Abstract, Introduction, Architecture, Conclusion |
| TCDM mediates completion and weight handoff without a direct SMU-to-RVV link | Figure 1 and M4 figure freeze | Architecture and Figure 1 caption |
| Proposed reaches 4.53x geometric-mean cycle speedup | `experiments/parsed/final_workload_comparison.csv` | Abstract, Introduction, Model-Derived Shapes, Figure 3 reference, Conclusion |
| Proposed reduces fitted `C_s` by 16.30x and `C_v` by 6.22% | `experiments/parsed/final_scaling_model.csv` | Abstract, Introduction, Scaling Mechanism, Conclusion |
| Full-Offload ablation has 3.78x Proposed `C_v` and its standalone block requires 48.8% more mapped Liberty area | Final scaling and area CSVs | Abstract, Evaluation, Conclusion |
| FSM busy schedule is 13+1+1+9 = 24 cycles | `experiments/parsed/p3_smu_latency_breakdown.csv` | Scalar Datapath and Schedule |
| Standalone Scalar SMU block uses 73,505 cells and 77,103.292 Liberty units | `experiments/parsed/final_area.csv` | Abstract, Table II, Hardware Cost, Conclusion |
| Timing is only a PARTIAL reg-to-reg proxy | `experiments/parsed/final_timing.csv`, `P7R_SYNCHRONOUS_TIMING_AUDIT.md` | Abstract, Setup, Table II caption, Hardware Cost, Conclusion |
| Synchronous Fmax, cluster PPA, power, energy, and end-to-end inference are unavailable | `FINAL_EVIDENCE_CLAIM_DICTIONARY.md` and `FINAL_EVIDENCE_FREEZE.md` | Setup, Hardware Cost, Conclusion |

## Old to new number and wording audit

| Superseded wording or value | Current wording or value | Disposition |
| --- | --- | --- |
| Proposed `C_s` reduction 17.66x | `C_s` reduction 16.30x (16.303154467... from active fit) | Replaced with M2 matched-LUT fit |
| Proposed geomean 4.81x | 4.53x geomean (4.526920018...); 4.81x remains only the current BERT row | Replaced in headline claims; BERT row is explicitly labelled |
| Full geomean 2.00x | 1.89x geomean (1.885765610...) | Replaced with active workload comparison |
| B2R `C_s/C_v` 1594.23/2.087 | 1471.818713/2.267063 | Replaced with active matched-LUT fit |
| Proposed `C_v` increase 1.88% | Proposed `C_v` is 6.22% lower than B2R | Corrected sign and baseline |
| 81.02/75.74 MHz and estimated standalone Fmax | 12.34285/13.20260 ns PARTIAL reg-to-reg proxies; synchronous Fmax unavailable | Numeric Fmax claims withdrawn |
| Timing table mixed delay, Fmax, and area | Table II has mapped cells, Liberty area, relative area, and PARTIAL delay proxy only | Preserves M4 schema and removes unsupported metric |
| Workload configurations and end-to-end implication | Model-derived one-position merge shapes and measured merge-kernel cycles | Scope tightened; no wall time or end-to-end inference claim |

Full-precision active headline values independently recomputed from the final
CSV files are `16.303154467395252` for B2R/Proposed `C_s`, `-6.2218412434%`
for Proposed `C_v` relative to B2R, `3.7767762670591285` for Full/Proposed
`C_v`, `4.526920018368193` for the Proposed workload geomean, and
`1.4877872918837238` for Full/Proposed Liberty area.

## Section checklist

### Abstract

- Uses problem, boundary insight, Scalar SMU plus RVV, mechanism, measured
  result, standalone hardware qualifier, and scope implication in that order.
- Uses only current headline anchors and states that synchronous Fmax is
  unsupported.

### Introduction

- Defines online merge as scalar recurrence plus regular vector update.
- Establishes B2R as the primary strong baseline and Full-Offload as an
  ablation.
- Presents exactly three claim-first contributions: recurrence engine,
  selective boundary, and evidence-constrained evaluation.

### Selective-Offload Architecture

- Identifies the five scalar equations assigned to Scalar SMU and the final
  `O[D]` equation retained on RVV.
- Expands RISC-V Vector (RVV), tightly coupled data memory (TCDM),
  memory-mapped I/O (MMIO), vector load/store unit (VLSU), and fused
  multiply-add (FMA) before abbreviation.
- States TCDM/MMIO ownership, software-visible completion, and no direct
  SMU-to-RVV path. Defines the scalar-only mode as mode 1.
- Records the 24-cycle FSM as `13+1+1+9`, with 22/24 TCDM communication states
  and 2/24 compute states.  It explicitly separates this busy interval from
  fitted `C_s` and system latency.

### Evaluation

- Keeps Setup, Strong Baseline and Full-Offload Ablation, Scaling Mechanism,
  Model-Derived Shapes, and Hardware Cost and Full-Offload Ablation.
- States that the final M2 anchor matches the software reciprocal LUT to the
  RTL LUT, all 234/234 records pass correctness, and three formal repetitions
  are bit-identical.
- Preserves M4 values while changing Table I's final header to `B2R/Proposed`
  and Table II's design headers to `Scalar SMU block` and `Full-Offload block`.
  Table II has no Fmax row, and Figure 3 carries no timing quantity.
- Ends the three results subsections with direct mechanism, workload, and
  hardware takeaways.

### Conclusion

- Restates the selective scalar boundary, 4.53x measured-cycle evidence,
  fitted mechanism terms, component-scoped standalone area, and timing
  limitation.
- Limits the conclusion to measured merge-kernel cycles and standalone SMU
  hardware.  It does not claim cluster PPA or end-to-end inference results.

## Sol-review targeted fixes

- Proposed now explicitly combines Scalar SMU recurrence hardware with
  existing RVV vector-update hardware.  Every numeric area claim names the
  standalone Scalar SMU block or standalone Full-Offload block.
- Table I now uses `B2R/Proposed`; Table II uses `Scalar SMU block` and
  `Full-Offload block` headers.  Figure 3 prose uses the same component scope.
- The manuscript expands RVV, TCDM, MMIO, VLSU, and FMA before abbreviation,
  defines the scalar-only mode as mode 1, and uses the corrected subsection
  heading and `merge-kernel` terminology.
- Setup now states the final M2 LUT match, `234/234` correctness, and three
  bit-identical formal repetitions.  The timing caption lists all required
  exclusions and preserves synchronous Fmax as unavailable.
- Scaling, workload, and hardware subsections end with direct takeaways for
  16.30x/6.22%/3.78x, 4.38x to 4.81x/4.53x, and +48.8%/1.89x versus 4.53x.

## Counts and mechanical style audit

The requested pre-rewrite reference count was 21,208 characters and 2,669
words.  The post-Sol-fix count is 20,231 characters and 2,516 words, measured
with:

```text
wc -m -w paper/online-merge-smu/main.tex
```

The following raw grep-style gates were run on `main.tex` after the Sol fixes:

| Gate | Raw hits | Disposition |
| --- | ---: | --- |
| Unicode em dash | 0 | Pass |
| Unicode en dash | 0 | Pass |
| ASCII triple dash | 0 | Pass |
| Spaced `--` | 5 | Allowed LaTeX `--` placeholders in the Geomean row |
| Decorative antithesis | 0 | Pass |
| Banned hype words | 0 | Pass |
| Fancy verb list | 0 | Pass |
| Qualifier list | 0 | Pass |
| Needless phrase list | 0 | Pass |
| Exclamation marks | 0 | Pass |
| Passive-voice heuristic | 0 | Pass; heuristic has no substantive hits |
| Human-readable sentences over 40 words | 0 | Pass after removing LaTeX commands and math from the check |

The installed `paper-writing` skill package did not contain its optional
`author_profile`, `writing_checklists`, or `section_rhetorical_moves` files.
The available skill instructions and red-team protocol were followed, and the
mechanical checks above were run locally.  This report records the targeted Sol
review fixes without claiming any later reviewer closure.

## Closure record

The final workload paragraph now says “Measured-cycle speedups over B2R”
instead of “Proposed/B2R speedups.”  This matches the frozen definition and
Table I header `B2R/Proposed`, while preserving the BERT, Mistral, Qwen14B, and
4.53x geomean values.  No other manuscript sentence changed in this closure
pass.

## LaTeX and PDF QA

The following command passed from `paper/online-merge-smu`:

```text
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The result is a five-page PDF.  The log contains no overfull boxes, undefined
references, or undefined citations.  It reports only existing underfull box
warnings in narrow IEEE columns.  `pdffonts` reports every listed font as
embedded and subsetted.  All three included graphics exist as PDF/vector
files:

| Output | SHA256 |
| --- | --- |
| `paper/online-merge-smu/main.tex` | `758d22a5972c1577257772c333d63509e89e9c8e39f852cc7bdc523200828d8b` |
| `paper/online-merge-smu/main.pdf` | `b30085b4854ad4c092a6b17498026f102d252c7d5fa00dee71cdff866fbb945d` |
| Figure 1 PDF | `bd504b584fe0fdcb813968f0c1d63d2e5d6e5e3e14a8831007ada65924a6b7d6` |
| Figure 2 PDF | `05a0b336350e5cc25a27eaca8ed538887d46238d651b1e4f30b4976d0cfdd078` |
| Figure 3 PDF | `268c51e0e91aa6eabd350e0254a2afb318052db81b9a2a43272bb2c958ee9aeb` |

The Figure 1 hash is unchanged from the M4 freeze.  The active data inputs
used for the rewritten claims have these SHA256 values:

| Input | SHA256 |
| --- | --- |
| `experiments/parsed/final_scaling_model.csv` | `2e6ba4378bab06238de7250a11eba449eaa1d1bc22f964d19b1c09261f9b2631` |
| `experiments/parsed/final_workload_comparison.csv` | `faecf75127454915e1337e1f44e0d6cdb54393d79ace4656cf28120ab5b678d5` |
| `experiments/parsed/final_area.csv` | `a50b8ce4e8efdefa5838e2417bc0d89ff3f99949167925311a3002a9dc0468ce` |
| `experiments/parsed/final_timing.csv` | `28bd72f31dc78881f2803e595a5629a1089f613c2c6deb95148637915c262331` |
| `experiments/parsed/final_hardware_results.csv` | `b1431e4f737af0d71d9c459c05725d9c25f32c71768a7aa3ff34600f0a3229d4` |
| `experiments/parsed/p3_smu_latency_breakdown.csv` | `e9b422f7fce6e23627ff981eff2aea2bef6cbe0b5efc6b111ece9ec72c8f428d` |

`git diff --check` passed.  No M5 change touched `main.tex` Related Work
prose or bibliography entries, Figure 1/2/3 assets, RTL, software, or active
evidence files.
