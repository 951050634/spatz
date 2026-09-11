# Evidence Provenance

## Repository state

- Audit repository HEAD: `809805d48e3a65457deb1756051a030d52d16dda`
- HEAD tree: `aa496d26711749ebbf67032c907cbbe57ef8c3f2`
- Branch: `exp/online-softmax-supplement`
- Upstream: `origin/exp/online-softmax-supplement`
- HEAD subject: `[artifacts] Update paths after spatz-archive relocation`
- Working tree before audit output creation: clean.
- Working tree after audit output creation: only the new untracked
  `experiments/paper_evidence_audit/` dossier.
- This audit did not run workloads, simulation, synthesis, or paper builds and did
  not modify existing evidence, RTL, software, OMCFG/OMERGE, RVV, or manuscript.

## Relevant commits

| Evidence role | Commit | Subject / disposition |
|---|---|---|
| mixed+reciprocal RTL | `ec2d70e42011a69432e31757d788edf3e683f627` | add mixed-precision and reciprocal-LUT datapath |
| Phase 1–3 archive | `d249deab7744e842f516007f591e041502bf7b5a` | archive numerical/PPA artifacts |
| explicit-P negative control | `4760567e797485d27b77e3688a51fa4a2d011ae4` | archive Phase 4 Softmax ablation |
| Phase 5 implementation | `7da83c5ad08063e110be8917733b5ebc8bdb3a61` | add native Online Attention benchmark |
| Phase 5 formal results | `a8f2747526c0f9b6c11c6360101a78cd836604fe` | archive native results |
| Phase 5 gate closure | `9d9bd0a0c0f11b023c525ca909d7ed38afb13bac` | finalize Gate 2 |
| Phase 6 implementation/evidence freeze | `117caff8109c0f6c32cf07a8322a3397307c8e14` | freeze matched cost/generality experiment |
| Phase 6 archive | `b5fe69b3f249c55b3b5e0e88b668ab9f2f6d5806` | archive generality and cost blocker |
| Phase 7 initial blocker | `40a679851a9e32e8a59793141a5be4bedccfd7c3` | record invalid custom-0 collision |
| Phase 7A encoding re-freeze | `20dcebed6762c3beeac6d9a12c4528736b828891` | select safe OMERGE encoding |
| OMERGE implementation freeze | `eac2851cbb60754a2e63f64780901ab6fd12a9c0` | implementation tree `fabf72c186506588a1d9352354ce35af57b2b20e` |
| Phase 7 initial result archive | `f72e73d897d8b9f4791a555b4d45be3b5a0a5f66` | matched OMERGE evaluation |
| Phase 7 provenance update | `97b88c800e67828ef3764c0849c85935e0eb5a8e` | finalize provenance |
| Phase 7 formal result/schema | `a62347923dd89cba08aff1c84bc55e34441404ca` | active formal result values |
| Phase 7 schema provenance | `c32c99c90b11831f46d8d79372d38bede8ea3c3b` | Phase 8A audited this HEAD |
| OMCFG implementation freeze | `7786820821102d34e32e9517a7630b028693f25a` | shared-register OMCFG integration |
| Phase 8A audit archive | `dba04985afdf9c02681269614a97536da56d1423` | instruction-space audit |
| Phase 8C formal archive | `e86ace2bdfe499554a7de9e9550ec6f24243f72e` | matched runtime validation |
| Phase 8C matched targets | `4962dc1a7a0c57e2201af2740a019a008660c32f` | matched MMIO/OMCFG test targets |
| artifact relocation | `809805d48e3a65457deb1756051a030d52d16dda` | path update only at audit HEAD |
| older matched-LUT experiment anchor | `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f` | historical M2 code/evidence anchor |
| older M2 evidence/manuscript freeze | `6190c038fd08f4318d855fd560f9c88ecf447d35` | historical TCAS-II evidence freeze |
| older submission audit | `4d92e82265db7f4496902a4969afe1a598f85624` | predates Phase 7/8; not final ISA authority |

## Formal CSV locations

| Domain | Active file(s) |
|---|---|
| Phase 5 native performance | `experiments/phase5_native_online_attention/formal/native_merge_performance.csv`, `native_attention_performance.csv`, `timeline_breakdown.csv` |
| Phase 5 native numerics | same directory `numerical_agreement.csv` |
| Phase 6 four-shape performance | `experiments/phase6_integrated_cost_generality/p0_2_workload_generality/formal/performance.csv` |
| Phase 6 four-shape numerics/setup | same directory `numerical_agreement.csv`, `shape_manifest.csv`, `run_details.csv` |
| cluster synthesis limitation | `experiments/phase6_integrated_cost_generality/p0_1_integrated_cost/formal/synthesis_comparison.csv` |
| Phase 7 OMERGE | `experiments/phase7_omerge_instruction/formal/performance.csv`, `numerical_agreement.csv`, `selector_audit.csv` |
| Phase 8C OMCFG | `experiments/phase8c_omcfg_runtime/matched_results.csv` |
| reciprocal numerics | `experiments/phase1_online_softmax/results/phase3_reciprocal_model/results.csv`, `reciprocal_sweep.csv`, related CSV/JSON |
| standalone PPA | `experiments/phase3_reciprocal_hardware/area/area_trials.csv`, `timing/timing_trials.csv` |
| explicit-P control | `experiments/phase4_softmax_ablation/results/cycles.csv`, `numerical.csv`, `device_numerical.csv` |
| older M2 freeze | `experiments/parsed/final_workload_comparison.csv`, `final_scaling_model.csv`, `final_area.csv`, `final_timing.csv` |

## Raw-log locations

- Phase 5: paths and SHA-256 values are enumerated in
  `experiments/phase5_native_online_attention/formal/manifest.json`; archived logs
  reside below its formal/raw evidence tree.
- Phase 6 workload: selected-source logs and recovery details are in
  `p0_2_workload_generality/formal/manifest.json` and its provenance subdirectory.
- Phase 6 synthesis: r3/r4 runner, Yosys evidence, kernel OOM excerpts, and manifests
  are in `p0_1_integrated_cost/logs/formal_recovery/`.
- Phase 7: four active recovery transcripts are
  `experiments/phase7_omerge_instruction/logs/formal_n8_d32_a1_mmio.raw.txt`,
  `experiments/phase7_omerge_instruction/logs/formal_n8_d32_a1_isa.raw.txt`,
  `experiments/phase7_omerge_instruction/logs/formal_n16_d64_a1_mmio.raw.txt`,
  and `experiments/phase7_omerge_instruction/logs/formal_n16_d64_a1_isa.raw.txt`,
  with individual provenance JSON files.
- Phase 8B directed evidence: `experiments/phase8b_omcfg_impl/raw/`.
- Phase 8C: `experiments/phase8c_omcfg_runtime/raw/n8_mmio.log`,
  `experiments/phase8c_omcfg_runtime/raw/n8_omcfg.log`,
  `experiments/phase8c_omcfg_runtime/raw/n16_mmio.log`, and
  `experiments/phase8c_omcfg_runtime/raw/n16_omcfg.log`, plus configure/build logs.
- Phase 4: `experiments/phase4_softmax_ablation/results/system_logs/`.

## Rerun, recovery, and reparse record

| Evidence | Historical action | Active-data rule |
|---|---|---|
| This audit | no rerun or reparse | existing files only |
| Phase 5 | formal runs archived at Phase 5 closure | use formal CSV/manifest |
| Phase 6 anchors | imported from Phase 5; `phase5_anchor_reruns=0` | no duplicate anchor rows |
| Phase 6 N16/D128 | interrupted run recovered once under guarded r2 recovery | use selected recovery source recorded in manifest |
| Phase 7 | first continuation lost formal raw source and Gate 2 failed; all four paths were freshly recovered once in fixed order | use only recovery raw transcripts; reconstructed legacy logs invalidated |
| Phase 8C | four cases ran once in fixed order | no case rerun after collector correction |
| Phase 4 | final aggregate reparsed six already completed fresh logs | raw logs are the source; command list is reparse, not original run command |
| M2 | 26 cases × 3 configs × 3 deterministic runs in its frozen epoch | historical family only |

## Known post-processing correction

Phase 8C N16 exact bit-vector equality produced host float64 cosine
`1.0000000000000002`, which made the first collector result fail. The collector was
corrected so exact word equality maps to cosine `1.0`. Formal cases were not rerun;
raw logs were not edited, and all four stored raw SHA-256 values remained unchanged.
The correction is documented in `experiments/phase8c_omcfg_runtime/manifest.json`.

## Conflicting or stale evidence

| Evidence | Problem | Disposition |
|---|---|---|
| `paper/online-merge-smu/main.tex` | predates OMERGE/OMCFG and describes legacy MMIO/precision | stale for final architecture; do not modify in this audit |
| `experiments/reports/FINAL_SUBMISSION_AUDIT.md` | valid for the older TCAS-II freeze but says no ISA changes | historical, not current ISA authority |
| `GOAL_COMPLETE.md` and pre-M2 workload numbers | e.g. an older BERT B2R value conflicts with final M2 CSV | keep provenance; use final M2 CSV if discussing that epoch |
| paths in `experiments/parsed/SUPERSEDED_EVIDENCE.md` | explicitly superseded | do not cite |
| old P7 inverse-delay MHz / absolute latency-throughput | timing semantics withdrawn | use delay proxy only; Fmax unavailable |
| Phase 7 440/1,062, Phase 8A 441/1,063, Phase 8B 442 decoder counts | different implementation epochs | label epoch; never present as one inconsistent census |
| `experiments/synthesis/p6-stop/elab-stat.json` | generic pre-mapped count, not matched cluster PPA | provenance only |

No stale data are used in `paper_master_results.csv` as current primary results.
