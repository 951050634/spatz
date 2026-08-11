# M4 Figure/Table Freeze

Status: **FROZEN — generated from M3 active evidence**

This freeze updates only the quantitative visualization/table layer. It does
not revise the broader manuscript narrative. The selected plotting backend is
Python/matplotlib; all figure drawing, export, and visual inspection used that
backend.

## Figure contract

- **Core conclusion:** Proposed combines a low fitted scalar term `C_s` with a
  low fitted vector term `C_v`, giving the strongest measured-cycle/
  standalone-area trade-off; Full-Offload is an ablation with high `C_v` and
  48.8% larger standalone mapped area.
- **Archetypes:** Fig. 2 is a two-panel quantitative grid/mechanism view;
  Fig. 3 is a quantitative performance–area comparison; Fig. 1 remains the
  accepted schematic-led architecture figure.
- **Panel map:** Fig. 2(a) plots positive `C_s` on a log axis and Fig. 2(b)
  plots `C_v` linearly. Fig. 3 uses incremental standalone SMU Liberty area
  on x and measured-cycle speedup over B2R on y; crosses are BERT/Mistral/
  Qwen14B and circles are geomeans.
- **Statistics:** 23 measured scaling shapes per configuration are retained
  in the active source and fit without error bars; the three workload ratios
  and geomeans are deterministic model-derived values. Formal repetitions were
  bit-identical, so variability is not invented.
- **Reviewer-risk controls:** B2R x=0 is explicitly labelled zero incremental
  SMU area, not zero cluster area. Full is labelled an ablation. Fig. 3 and
  Table II contain no Fmax, absolute latency, throughput, cluster PPA,
  power, or energy claim. Cell counts and Liberty units remain separate.

## Active source mapping

| Artifact | Active source fields | Mapping |
| --- | --- | --- |
| Fig. 2 | `final_scaling_model.csv` parameter rows | `C_s` → panel (a), `C_v` → panel (b), all B2R/A1/A2 rows |
| Fig. 3 | `final_workload_comparison.csv` | `A1_speedup_over_B2R`/`A2_speedup_over_B2R` → workload crosses and geomeans |
| Fig. 3 | `final_area.csv` | A1/A2 `liberty_area / 1000` → x positions; B2R is defined as zero incremental SMU area |
| Table I | `final_workload_comparison.csv` | `workload`, `N`, `D`, three cycle columns, and `A1_speedup_over_B2R`; BERT/Mistral/Qwen14B/geomean |
| Table II | `final_area.csv`, `final_hardware_results.csv` | mapped cells, Liberty area, relative area, and PARTIAL reg→reg delay proxy |

No requested workload/configuration row was excluded. Fig. 2 uses the three
formal parameter rows while retaining all 69 measured point rows in the active
source. Fig. 3 uses all three workload rows plus the active geomean row.

## Frozen values

Fig. 2 labels are `C_s = 1471.82 / 90.28 / 19.32` and `C_v = 2.27 / 2.13 /
8.03` for B2R / Proposed / Full-Offload. Fig. 3 uses geomeans `4.53×` and
`1.89×` for Proposed and Full-Offload, with x positions `77.103` and
`114.713` k Liberty units; B2R is `0` incremental SMU area.

Table I uses measured cycles:

| Workload | N | D | B2R | Proposed | Full | Prop./B2R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BERT | 12 | 64 | 19,856 | 4,128 | 7,704 | 4.81× |
| Mistral | 32 | 128 | 56,296 | 12,866 | 34,728 | 4.38× |
| Qwen14B | 40 | 128 | 69,348 | 15,733 | 43,206 | 4.41× |
| Geomean | — | — | — | — | — | 4.53× |

Table II uses A1/A2 mapped cells `73,505 / 107,372`, Liberty areas
`77,103.292 / 114,713.298`, relative areas `1.000× / 1.488× (+48.8%)`, and
PARTIAL reg→reg delay proxies `12.34285 / 13.20260 ns`. Synchronous Fmax is
not a Table II row.

## Figure 1 freeze

Figure 1 was not regenerated or edited. Its accepted visual semantics remain:
Scalar SMU recurrence, existing RVV vector update, software-visible TCDM
handoff, and no Full-Offload path. Its hashes are recorded below and were
identical before and after M4.

## QA and export checks

- `python3 -m py_compile experiments/scripts/make_figure2_scaling.py experiments/scripts/make_figure3_tradeoff.py`: PASS.
- `validate_figure.py`: Fig. 2 `13 PASS / 1 WARN / 0 FAIL`; Fig. 3
  `13 PASS / 1 WARN / 0 FAIL`. The sole warning is the absence of a TIFF;
  the contract requests vector PDF/SVG plus a 600-dpi PNG preview. Fig. 2's
  positive-value guard is explicit before its log axis.
- Each figure was generated twice. PDF, SVG, and PNG hashes were byte-identical
  across both runs after fixed metadata and SVG hash salts were set.
- PDF dimensions are 180×80 mm (Fig. 2) and 180×110 mm (Fig. 3). PNG previews
  are 4251×1889 and 4251×2598 pixels at approximately 600 dpi. SVG text remains
  editable (`svg.fonttype=none`); PDF text uses editable TrueType settings.
- Final PNG inspection found no clipping or overlap. Fig. 2 labels are readable
  on the log/linear panels; Fig. 3 labels, workload crosses, geomeans, area
  ticks, and the zero-increment semantic note are readable at final size.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`: PASS;
  five-page PDF, no overfull boxes, undefined references, or citation
  diagnostics. Existing underfull-box diagnostics remain non-fatal.
- The M4 Table I/Table II/Fig. 3 block contains no withdrawn 81.02/75.74 MHz,
  old geomean 4.81×, or old Full 2.00× claim. BERT's 4.81× is the current
  per-workload measured ratio.

## SHA256 manifest

| Role | Path | SHA256 |
| --- | --- | --- |
| Active input | `experiments/parsed/final_scaling_model.csv` | `2e6ba4378bab06238de7250a11eba449eaa1d1bc22f964d19b1c09261f9b2631` |
| Active input | `experiments/parsed/final_workload_comparison.csv` | `faecf75127454915e1337e1f44e0d6cdb54393d79ace4656cf28120ab5b678d5` |
| Active input | `experiments/parsed/final_area.csv` | `a50b8ce4e8efdefa5838e2417bc0d89ff3f99949167925311a3002a9dc0468ce` |
| Active input | `experiments/parsed/final_hardware_results.csv` | `b1431e4f737af0d71d9c459c05725d9c25f32c71768a7aa3ff34600f0a3229d4` |
| Figure script | `experiments/scripts/make_figure2_scaling.py` | `5dc7cea4f0a218841ee9bc569ae606c7c55534956934e16e9c2cd428d743318a` |
| Figure script | `experiments/scripts/make_figure3_tradeoff.py` | `aff7f06a6fa6254ef96d5db59b643068cc175dc3ed460600b7e6c16e8064c987` |
| Frozen Fig. 1 | `experiments/plots/figure1_proposed_architecture.pdf` | `bd504b584fe0fdcb813968f0c1d63d2e5d6e5e3e14a8831007ada65924a6b7d6` |
| Frozen Fig. 1 | `experiments/plots/figure1_proposed_architecture.png` | `1517f85ad373e2bd3842d049660cfa2618e23b0264fb867f9035c4d92b2abf81` |
| Frozen Fig. 1 | `experiments/plots/figure1_proposed_architecture.svg` | `197158ed7302a1aa4339d83aaf6cb957896327e0d533fac1c2193522af8791b3` |
| Fig. 2 output | `experiments/plots/figure2_scaling.pdf` | `05a0b336350e5cc25a27eaca8ed538887d46238d651b1e4f30b4976d0cfdd078` |
| Fig. 2 output | `experiments/plots/figure2_scaling.png` | `fa7b01c16d272a9217c3b6a2f4ce01397162f1c97451e269a7a0b70d955e81bd` |
| Fig. 2 output | `experiments/plots/figure2_scaling.svg` | `a4fe41e42f2d9ff54b75c14f5106294efa5f12655ab4acf4e2c7e0510c8e536b` |
| Fig. 3 output | `experiments/plots/figure3_hardware_tradeoff.pdf` | `268c51e0e91aa6eabd350e0254a2afb318052db81b9a2a43272bb2c958ee9aeb` |
| Fig. 3 output | `experiments/plots/figure3_hardware_tradeoff.png` | `fc393d8ac30dfcd455b88746b79ffc44dd00266d70d34bd441c4eddc7011cae8` |
| Fig. 3 output | `experiments/plots/figure3_hardware_tradeoff.svg` | `15bf6f4ef126897c774ceecb3ffd4a56d38179794fce7db7b3f89aabfeebeaa8` |
| Manuscript local edit | `paper/online-merge-smu/main.tex` | `cb82b334070a3e092b77b6e37e3fcfc75b7eb66ce8c4e2820216ac830dd93f2e` |
| LaTeX validation artifact | `paper/online-merge-smu/main.pdf` | `ea8c9cfb455ba9b6ed94753cdc66664184ba17ff23f94127b9555db5ba19f3b7` |

The source-of-truth CSVs and M3 manifest were not modified in M4. Figure 1,
RTL, software, and all broader manuscript narrative sections remain outside
this freeze.
