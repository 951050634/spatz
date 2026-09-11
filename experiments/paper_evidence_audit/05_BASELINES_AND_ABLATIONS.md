# Baselines and Ablations

## Canonical names

| Final paper name | Recurrence | O update | Configuration | Invocation | Arithmetic relation | Final-use status |
|---|---|---|---|---|---|---|
| B1 | software scalar | software scalar | none | function call | software reference; not the matched RVV baseline | context/weak baseline only |
| B2R | software scalar | existing RVV | none | function call | matched-LUT/matched recurrence reference and same RVV update in its evidence epoch | primary software baseline for Phase 5/6 |
| A1-MMIO | Mixed Scalar SMU | existing RVV | legacy generated MMIO registers | per-merge MMIO clear/start/poll | same SMU arithmetic and RVV as A1-ISA | Phase 7 recurring-control baseline |
| A1-ISA / OMERGE | Mixed Scalar SMU | existing RVV | Phase 7: persistent MMIO setup before timer | one OMERGE per merge | matched to A1-MMIO | Phase 7 proposed call path |
| OMCFG-config + OMERGE | Mixed Scalar SMU | existing RVV | nine OMCFG fields + one INIT per workload | one OMERGE per merge | matched to MMIO-config + OMERGE | **final programming model** |
| MMIO-config + OMERGE | Mixed Scalar SMU | existing RVV | nine MMIO fields + one MMIO INIT per workload | one OMERGE per merge | matched to OMCFG-config path; within-shape `.text` identical | Phase 8C config-plane baseline |
| Full SMU / A2 | SMU | SMU vector path | legacy control | SMU command | separate Full-Offload architecture | ablation/history only, not Proposed |

## Interpretation rules

### B1

B1 isolates a fully scalar software implementation. Its measured scalar symbol is
audited to contain zero RVV instructions. It demonstrates the value of the existing
RVV update but is not the strongest current baseline and is not used in Phase 7/8.

### B2R

B2R combines software scalar recurrence with the same existing RVV output routine.
It is best described as the **matched-arithmetic RVV baseline**, not an optimized
state-of-the-art software implementation. Phase 5/6 compare its native recurrence
with the mode-3 Mixed Scalar SMU while keeping the RVV update and tile dataflow
common.

### A1-MMIO

This is the final architectural partition reached through legacy MMIO. In Phase 7
the recurring window includes per-merge setup, clear, start, polling, and accelerator
execution. It is the reference for evaluating OMERGE, not a software baseline.

### A1-ISA / OMERGE

This uses the same Mixed Scalar SMU and RVV update as A1-MMIO. The A/B context is
configured once before the Native Core timer; each non-first tile invokes one
OMERGE and consumes returned status. The delta A1-MMIO → A1-ISA is therefore a
**recurring invocation/control-path benefit**, not an arithmetic speedup.

### OMCFG-config + OMERGE

This is the final ISA-facing design. OMCFG writes the same physical persistent
registers as MMIO and INIT commits readiness/selector state. The Phase 8C delta
MMIO-config → OMCFG-config is a **configuration-plane/one-time setup benefit**.
Both paths use OMERGE in the Native Core, so no meaningful steady-state gain is
claimed.

### Full SMU

Full SMU moves both recurrence and dimension-dependent vector update into the
accelerator. It duplicates/implements a vector datapath rather than reusing RVV.
It remains useful only to demonstrate the area/dataflow trade-off. Do not call it
the final or proposed architecture.

## Historical aliases

| Historical name | Final paper name / disposition |
|---|---|
| `B1_SCALAR` | B1 |
| `B2R_RVV`, `B2-R`, `A0` | B2R |
| `A1_SMU_SCALAR`, `C1_SCALAR`, `Proposed` | Scalar SMU + RVV architectural partition; add `MMIO`, `OMERGE`, or `OMCFG+OMERGE` suffix for the relevant evidence epoch |
| Phase 5 `software` | B2R native path |
| Phase 5 `smu` | Mixed Scalar SMU+RVV through MMIO |
| Phase 7 lowercase `mmio` | A1-MMIO |
| Phase 7 lowercase `isa` | A1-ISA / OMERGE |
| Phase 8C `mmio` | MMIO-config + OMERGE |
| Phase 8C `omcfg` | OMCFG-config + OMERGE |
| `A2_SMU_FULL`, `C2_FULL`, `FULL`, `Full-Offload`, `B3` | Full SMU / A2 ablation |

## Evidence-epoch warning

“A1” identifies the same selective architectural partition across the repository,
but not one immutable numerical/control implementation. The M2/TCAS-II freeze used
an older standalone/microkernel A1 and predates OMERGE/OMCFG; Phase 5–8 use the
frozen Mixed Scalar mode-3 native path. Never combine M2 A1 cycles/PPA with Phase
5–8 cycles as if collected from one binary.

## Formal comparison membership

| Question | Formal comparison |
|---|---|
| Does selective recurrence offload help native attention? | B2R vs Phase 5/6 Mixed Scalar SMU+RVV |
| Does scalar ISA invocation reduce recurring control? | A1-MMIO vs A1-ISA/OMERGE, Phase 7B |
| Does OMCFG reduce one-time setup? | MMIO-config+OMERGE vs OMCFG-config+OMERGE, Phase 8C |
| Is SMU a generic explicit-P Softmax replacement? | Phase 4 Software Softmax vs Mixed SMU (negative control) |
| What is the standalone mixed arithmetic cost? | Legacy vs Mixed+Division vs Mixed+Reciprocal, Phase 3 |
| What is the cost of moving O update into SMU? | historical A1 vs Full SMU/A2 standalone ablation; separate evidence epoch |
