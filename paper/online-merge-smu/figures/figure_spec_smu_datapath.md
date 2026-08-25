# Figure Spec: Scalar SMU Datapath

- Section: Scalar SMU Microarchitecture
- Archetype: component detail
- Backend: Python (matplotlib)
- Final size: 180 x 74 mm
- Claim: The RTL computes two exponential rescalings in parallel, registers
  the updated length, and then generates two normalized weights through one
  reciprocal path.
- RTL mapping: maximum selector; two delta subtractors; two independent EXP
  LUT/interpolation blocks; two Q1.23-by-Q16.32 scaling multipliers; adder;
  `l_new`/scaled-length registers; one reciprocal LUT/interpolation block;
  two Q1.23-scaled weight multipliers.
- Reviewer risk: do not imply a direct SMU-to-RVV bypass, a floating-point
  FMA, iterative division, or resource sharing absent from RTL.

