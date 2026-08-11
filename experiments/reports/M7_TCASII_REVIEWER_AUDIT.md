# M7 TCAS-II Reviewer Audit

**STATUS: FIX**

**Review date:** 2026-08-12

**Target:** IEEE Transactions on Circuits and Systems II: Express Briefs

**Evidence anchor:** `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`

Three independent Sol Max reviews examined technical soundness, novelty and
significance, and readability/submission compliance.  This report synthesizes
their findings into the only authorized M8 issue list.  M7 changed no RTL,
software, experiment, figure, bibliography, or manuscript file.

The present paper is evidence-consistent but not submission-ready.  The three
reviews agree that no new cluster-PPA, power, energy, Fmax, or end-to-end
experiment is required under the paper's bounded claim.  They also agree that
the selective specialization boundary is the publishable contribution.  The
remaining blockers are factual wording, novelty framing, scope-safe figure
semantics, and TCAS-II page layout.

## Reviewer 1: Technical Soundness and Evidence

### Recommendation

**Major revision / weak reject in the current form.**  The measured-cycle,
area, and timing numbers match the frozen evidence, and Full-Offload remains an
ablation.  Three issues nevertheless require correction before submission.

### Strengths

- B2R and Proposed call the same RVV vector-update implementation, so the
  vector path is matched in the primary comparison.
- All frozen workload, fit, area, and delay values reproduce the active CSVs.
- Standalone area ownership is explicit.  The timing numbers are correctly
  bounded to pre-layout combinational-delay proxies and are not inverted into
  Fmax.
- The paper does not misclaim cluster PPA, power, energy, or end-to-end
  inference.

### Major findings

1. **B2R is matched, but not demonstrated to be an optimized strong
   baseline.**  It uses matched LUT arithmetic and the same RVV update as
   Proposed, but its scalar conversion contains a 48-iteration linear bit
   scan in `sw/spatzBenchmarks/online-softmax-merge/rtl_reference.c`.  The
   4.53x result is valid against this implementation; the evidence does not
   establish a generally optimized software lower bound.

2. **The 24-cycle claim is too strong.**  The `13+1+1+9` result is the nominal
   no-stall state schedule.  Current M2 observers measure 289 cycles for 12
   BERT rows, 769 for 32 Mistral rows, and 962 for 40 Qwen rows.  These are
   24 cycles per row plus one or two TCDM wait cycles.  The manuscript and
   active evidence dictionary must not call 24 a fixed measured busy latency.

3. **The fitted terms are whole-kernel regression coefficients, not direct
   phase counters.**  `C_s` includes all N-dependent work outside the
   `C_vND` term; `C_v` is the fitted ND slope.  Figure 2's phase-cost labels
   and causal wording currently overstate that interpretation.  Because B2R
   and Proposed share RVV, the 6.22% difference should be described as
   coefficient proximity, not as an RVV-hardware improvement.

4. **Correctness coverage needs reader-facing definition.**  The 234 records
   are 26 cases x 3 configurations x 3 reruns with one deterministic seed and
   input pattern.  They pass a scale-aware `1e-3` matched-LUT functional check;
   rerun identity establishes reproducibility, not formal verification or
   model-level accuracy.

5. **Model-shape mapping is underdefined.**  For the selected rows, `N` is the
   published query-head count and `D` is hidden width divided by query-head
   count.  Mistral and Qwen therefore use query heads rather than KV heads.

### Technical evidence

- `experiments/parsed/m2/m2_all_records.csv`
- `experiments/parsed/m2/m2_model_source_audit.csv`
- `experiments/parsed/final_scaling_model.csv`
- `experiments/parsed/final_workload_comparison.csv`
- `experiments/parsed/final_area.csv`
- `experiments/parsed/final_timing.csv`
- `experiments/reports/P7R_SYNCHRONOUS_TIMING_AUDIT.md`

## Reviewer 2: Novelty and Significance

### Recommendation

**Major revision / borderline weak reject in the current form.**  Algorithmic
and arithmetic novelty are limited, but the dependency-aligned hardware and
software boundary is a credible system-microarchitecture contribution.

### Strengths

- The proposed identity is stable: recurrence-only Scalar SMU, shared-TCDM
  handoff, and reuse of the existing RVV datapath.
- The `C_s/C_v` fit and Full-Offload ablation expose why the boundary matters,
  instead of reporting only a headline cycle ratio.
- The Related Work section avoids an absolute first/only claim and records its
  source limitations.

### Major findings

1. **The first page still reads too much like another Softmax accelerator.**
   The paper should state the field-level gap between broad/full offload and
   all-programmable vector execution before introducing internal baseline
   names.

2. **Originality must be owned precisely.**  The contribution is the
   dependency-aligned specialization boundary, not the established online
   merge recurrence, EXP/reciprocal LUTs, or a new Softmax algorithm.

3. **The novelty sentence relies on negative absence evidence.**  Several M6
   sources were available only as metadata or abstracts.  Replace “None of the
   reviewed sources documents ...” with a positive, bounded comparison of the
   cited design-space endpoints.

4. **VFA is a recent, conceptually adjacent omission.**  It addresses
   online-Softmax rowmax/rescale vector bottlenecks by changing the update
   schedule.  It should be cited and distinguished from retaining the
   established recurrence while specializing only its state-dependent
   hardware boundary.  FuseMax is already screened and may remain audit-only
   because the manuscript cites another representative full-attention
   hardware point.

5. **The contribution list contains process rather than research content.**
   “Evidence-constrained evaluation” should be replaced by the measured
   boundary result.  TCDM is an integration mechanism, not an independently
   ablated contribution.

6. **Full-Offload is not a proxy for prior accelerators.**  It only isolates
   the cost of full offload in this implementation and must remain framed that
   way.

### Novelty posture

The defensible claim is: a cluster-local, recurrence-only engine is integrated
through TCDM while leaving the ISA and existing RVV update unchanged, and the
measured implementation shows that this boundary retains a low fitted ND term
while reducing the fitted N-dependent term.  The paper must not imply a new
online-Softmax recurrence, a leading full-Softmax accelerator, or superiority
over all-RVV prior work.

## Reviewer 3: Readability, Scope, and Submission Polish

### Recommendation

**Major revision before submission.**  The paper is internally coherent and
mechanically clean, but several expressions are unsafe under a fast reviewer
read and the final-page layout violates the target journal's instructions.

### Strengths

- Figure 1 communicates the NEW/REUSED boundary and TCDM handoff effectively.
- B2R, Proposed, and Full-Offload retain distinct roles throughout the paper.
- The PDF has five pages, all fonts are embedded, and it has no overfull box,
  unresolved citation, or unresolved reference.

### Major findings

1. **Figure 3 juxtaposes separately scoped quantities.**  “Performance-area
   trade-off” can be misread as cluster PPA or area efficiency.  The plot and
   prose should instead say “merge-kernel cycle-count ratio versus standalone
   accelerator-block area” and state explicitly that the two axes are
   separately scoped evidence.

2. **Model names can be misread as captured model inference.**  Setup and
   Table I must state that these are deterministic generated merge states for
   one logical query position, not captured activations or end-to-end runs.

3. **Internal milestone language has leaked into the paper.**  Replace “final
   M2 anchor,” “active rows,” “formal repetitions,” and repeated taxonomy
   labels with reader-facing descriptions of the reference, test matrix, and
   pre-layout proxy.

4. **Repeated takeaway sentences waste brief-format space.**  The Mechanism,
   Workload, and Hardware takeaway sentences repeat their immediately
   preceding paragraphs and should be removed or folded into one causal
   sentence.

5. **Figure and table labels need scope-safe precision.**  Figure 2 should
   label fitted slopes rather than physical phases; Figure 3 workload markers
   need distinguishable B/M/Q labels; Table II should name Nangate45 Liberty
   cell-area units and round proxy values to appropriate precision.

6. **The current fifth page is not TCAS-II compliant.**  Figure 3 spans the
   top of both columns and the Conclusion enters page 5.  TCAS-II currently
   requires 4.5 pages of content plus 0.5 pages of references, with the final
   column reserved only for references.  The current final column contains
   Figure 3 and is therefore a formal submission blocker.  See the official
   instructions: <https://ieee-cas.org/publication/TCAS-II/guidelines-author>.

## Cross-Review Synthesis

### Consensus

All three reviewers agree on the following points:

- The publishable contribution is selective scalar offloading, not a new
  Softmax algorithm or full accelerator.
- B2R is the comparison baseline and Full-Offload is only an internal
  ablation.
- The cycle, area, and timing records are internally consistent and correctly
  exclude unsupported cluster/system claims.
- No new cluster PPA, power, energy, Fmax, or end-to-end inference experiment
  should be added in M8.
- The paper requires a bounded text/figure/layout revision before submission.

### Disagreements resolved by Sol Max

- The technical reviewer accepted the existing representative Related Work,
  while the novelty reviewer requested VFA and FuseMax.  M8 will add VFA, the
  closest online-recurrence counterpoint, and retain FuseMax in the M6 audit
  rather than add a redundant full-attention citation.
- The readability reviewer treated the 24-cycle distinction as an explanation
  problem; the technical review found a direct current-observer discrepancy.
  The technical evidence controls: 24 becomes a nominal no-stall schedule.
- Cluster PPA and power would strengthen a larger systems claim, but they are
  not required for the deliberately standalone, merge-kernel brief.  Their
  absence remains an explicit limitation rather than an M8 blocker.

## Consolidated M8 Issue List

M8 may implement only the following fixes.  It must not rerun experiments,
modify RTL/software, reopen Full-Offload optimization, or activate cluster
PPA.

### P0: submission blockers

1. **FIX-01 — TCAS-II final-column compliance.**  Re-layout Figure 3 and the
   manuscript so page 5's right column contains references only.  Preserve a
   five-page PDF and verify the final page visually.
2. **FIX-02 — Correct the FSM claim.**  Replace fixed 24-cycle measured-latency
   wording with the nominal no-stall `13+1+1+9` state schedule plus occasional
   TCDM wait cycles.  Correct the active claim dictionary and P3/P18 reports as
   well as the manuscript; do not change raw observations.
3. **FIX-03 — Calibrate B2R.**  Replace “primary strong baseline” with
   “matched-arithmetic RVV baseline” and define it on first use.  Keep every
   4.53x claim explicitly relative to B2R.
4. **FIX-04 — Make the novelty gap first-page visible.**  State that prior
   approaches occupy broad/full-offload or programmable/vector boundaries and
   that this work specializes the state-dependent recurrence while preserving
   the existing RVV update.  Explicitly disclaim algorithm/LUT novelty.
5. **FIX-05 — Replace the negative novelty claim.**  Add and distinguish VFA;
   replace the near-exhaustive absence sentence with a positive bounded
   positioning statement.  Do not add FuseMax unless it replaces, rather than
   merely appends to, a representative full-attention citation.
6. **FIX-06 — Correct fit semantics.**  In prose and Figure 2, call `C_s` the
   fitted N-dependent cycles/row coefficient and `C_v` the fitted ND-dependent
   cycles/element coefficient.  Say `C_v` remains within 6.22% of B2R rather
   than implying RVV acceleration.  Retain the 16.30x `C_s` result and add the
   existing R-squared range.
7. **FIX-07 — Make Figure 3 scope-safe.**  Rename its title/axes/caption and
   surrounding prose to “merge-kernel cycle-count ratio versus standalone
   accelerator-block area”; explicitly state that this is not cluster PPA or
   area efficiency, and make B/M/Q markers distinguishable.

### P1: required manuscript clarity

8. **FIX-08 — Define workload construction.**  For the selected rows, define
   `N` as query-head count and `D` as per-head width, note the GQA query-head
   choice, and state that deterministic generated states cover one logical
   query position rather than captured activations.
9. **FIX-09 — Define correctness coverage.**  Replace internal M2/formal
   language with 26 cases x 3 configurations x 3 deterministic reruns, the
   matched-LUT `1e-3` scale-aware functional reference, no nonfinite outputs,
   and rerun reproducibility.  Do not imply IEEE-exact or model-level accuracy.
10. **FIX-10 — Rewrite the contributions.**  Use: recurrence-only Scalar SMU
    and its nominal schedule; unchanged-ISA TCDM/RVV integration; and the
    measured selective-boundary result with Full-Offload explicitly limited to
    an internal ablation.
11. **FIX-11 — Remove repetition and causal overclaim.**  Remove the three
    repeated “takeaway” sentences, replace “determines” with evidence-bounded
    wording, and state that TCDM is the handoff mechanism rather than a
    separately quantified source of benefit.
12. **FIX-12 — Normalize reader-facing terminology.**  Use “Scalar SMU + RVV”
    or “Selective-Offload design” after definition; use `Qwen2.5-14B-Instruct`;
    normalize Softmax and `F_max` notation; remove unnecessary Related Work
    acronyms.

### P2: final polish

13. **FIX-13 — Round proxy metrics.**  Use 12.34/13.20 ns and reader-facing
    Nangate45 Liberty cell-area units.  State once that area is an
    unconstrained pre-layout research-library proxy and that timing is not
    used for Fmax or design ranking.
14. **FIX-14 — Compact figures and captions.**  Remove excess vertical space,
    shorten Table II's caption, keep Conclusion continuous, and retain readable
    figure text at final size.
15. **FIX-15 — Mechanical submission QA.**  Set a PDF title, compile twice,
    require five pages, embedded fonts, no overfull boxes, no unresolved
    citations/references, `git diff --check` PASS, and visual confirmation that
    the final column contains references only.

## Claim Decision

After M8, the paper may claim:

- a 4.53x geometric-mean **merge-kernel cycle-count ratio over the specified
  matched-arithmetic B2R implementation**;
- a 16.30x reduction in the fitted N-dependent coefficient while the fitted
  ND-dependent coefficient remains within 6.22% of B2R;
- standalone Scalar SMU area of 73,505 mapped cells / 77,103.3 Nangate45
  Liberty cell-area units; and
- a 48.8% larger standalone Full-Offload block as an internal ablation.

It may not claim optimized-software superiority, absolute runtime or
throughput, cluster PPA/Fmax, power/energy, end-to-end inference speedup,
model-level accuracy, or a new online-Softmax recurrence.

## Next Single Task

**M8 Luna Max final fix round:** implement FIX-01 through FIX-15 without new
experiments or claim expansion, then return the standard Luna report and the
reproducible PDF for final Sol Max review.
