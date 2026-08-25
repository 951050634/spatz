# Figure Spec: Nominal Scalar SMU Schedule

- Section: Scalar SMU Microarchitecture
- Archetype: pipeline / process flow
- Backend: Python (matplotlib)
- Final size: 88 x 34 mm
- Claim: The scalar-only no-stall FSM spends 13, 1, 1, and 9 busy cycles in
  load, scalar compute, weight compute, and store states, respectively.
- Content: proportional horizontal state bar, state labels, cycle counts,
  total of 24 cycles/row, and a compact no-stall qualifier.
- Boundary: the figure describes the FSM busy interval, not command polling or
  the RVV vector phase.

