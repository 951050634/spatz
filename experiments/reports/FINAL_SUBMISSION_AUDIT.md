# Final Submission Audit

**Date:** 2026-08-12

**STATUS:** PASS

**Submission classification:** Submission Ready, subject only to the repository
cleanliness check performed after the commit containing this audit record.

## Decision

The M0--M8 submission-convergence flow is complete. No open P0, P1, or P2
issue remains within the frozen evidence and manuscript scope. Proposed is
consistently Scalar SMU plus existing RVV; Full-Offload is consistently an
internal ablation. X1 cluster-level PPA remains stopped and is not a submission
blocker.

## Gate results

| Gate | Status | Closure |
| --- | --- | --- |
| M0 evidence policy | PASS | VERIFIED, DERIVED, PARTIAL, and UNAVAILABLE claims are separated; cells and Liberty area are not mixed. |
| M1 matched-LUT revalidation | PASS | 234/234 records pass across 26 cases, three configurations, and three deterministic reruns at experiment source commit `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`. |
| M2 timing audit | PASS | A1/A2 longest paths are true reg-to-reg combinational paths of 12.34/13.20 ns; synchronous Fmax is withdrawn as UNAVAILABLE. |
| M3 evidence freeze | PASS | All 13 manifest input, output, and generation-script hashes match current files; repeated freeze generation is byte-identical. |
| M4 figures and tables | PASS | Figures 1--3 and Tables I--II use active evidence and preserve standalone-block versus cluster scope. |
| M5 paper convergence | PASS | Title, Abstract, Introduction, Architecture, Evaluation, and Conclusion follow the selective scalar-offload argument. |
| M6 novelty audit | PASS | Related Work uses bounded positive positioning and includes the traceable VFA reference `arXiv:2604.12798`. |
| M7 reviewer audit | PASS | All FIX-01--FIX-15 items and the final Sol red-team micro-fixes are closed. |
| M8 final implementation | PASS | Final manuscript, bibliography, figures, reports, and PDF pass mechanical and visual QA. |

## Frozen headline evidence

- Proposed workload geomean: `4.526920018368193x` over matched-arithmetic B2R,
  displayed as `4.53x`.
- Fitted B2R/Proposed N-dependent coefficient ratio: `16.303154467395252x`,
  displayed as `16.30x`.
- Proposed fitted ND-dependent coefficient is `6.221841243413994%` below B2R;
  the manuscript conservatively states that it remains within `6.22%` of B2R.
- Proposed standalone block: 73,505 mapped cells and 77,103.292 Nangate45
  Liberty cell-area units.
- Full-Offload standalone area: 114,713.298 Liberty units, or 48.778729% more
  than Proposed; Full-Offload remains an ablation.

## Manuscript and artifact QA

- Final PDF: `paper/online-merge-smu/main.pdf`.
- PDF SHA256: `97993619a208bde187303ab4cca01fa4eae9bdab9f8d5de96325236ad39343ee`.
- Format: five letter-size pages with embedded/subsetted fonts.
- The page-5 right column contains references only; Figure 3 and the Conclusion
  remain in the left column.
- The LaTeX log contains no fatal error, undefined citation/reference, or
  overfull box.
- The compiled VFA entry displays `arXiv:2604.12798`.
- `git diff --check` and Python syntax checks for the active analysis/figure
  scripts pass.

## Claim boundary

The paper reports measured RTL/Verilator merge-kernel cycles, fitted cycle-growth
coefficients, standalone mapped cells and Liberty area, a nominal no-stall FSM
schedule, observed SMU busy cycles, and PARTIAL pre-layout reg-to-reg delay
proxies. It does not claim synchronous Fmax, cluster area/timing, power, energy,
absolute latency, throughput, or end-to-end inference speedup.

## Provenance

- Experiment/code anchor: `7225d41ad2d1c63376a9fb1ea4e56b3b24a3e97f`.
- Evidence and manuscript freeze commit:
  `6190c038fd08f4318d855fd560f9c88ecf447d35`.
- Final audit commit: the commit containing this file.
- Intended local freeze tag: `smu-tcasii-eval-v2`.

No remote push or submission action is part of this audit.
