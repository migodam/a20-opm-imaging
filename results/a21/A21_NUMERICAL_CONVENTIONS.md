# Frozen numerical and interpretation conventions

All GN vectors and Hessians use the original 54 real material coordinates.
The full state, B, r, Lambda, ell and feasible set are identical across arms.
The prototype is an offline oracle anatomy, not a deployable algorithm or
new nonlinear reconstruction.

## Tolerances fixed before outcome inspection

- Original constrained QP/KKT and feasibility: 1e-8; original optimizer and
  active-equation polish unchanged.
- Baseline relative-step reproduction: 1e-9 on a nonzero reference scale.
- Backend dot products and decompositions: scale-aware 1e-9; oracle/full
  solve relative residual: 1e-9.
- Rank revelation: original 1e-10; original projected-core relative sigma,
  absolute scaled sigma floors 1e-10 and condition cap 1e10. No ridge,
  pseudoinverse, empty-U rescue or projection-kind replacement.
- Symmetric-Hessian check: relative 1e-12 before Cholesky/generalized-eigen
  diagnostics. Positive definiteness must hold; no added damping.
- Scientific target: relative H_F step error <=5% only on a well-resolved
  reference. The original H-norm floor 1e-12 is a missing/ill-scaled flag,
  not a replacement denominator. Endpoint ratios separately flag machine-
  resolution denominators, with absolute numerator/denominator retained.
- Small dense floating allowance: 1e-9 times declared H-energy scale plus
  100*float64_epsilon times max(1,scale). This is not a new optimizer tolerance.

## Solver-aware identity and normal allowance

`eta_direct = rho_F + delta_d + J_R.T@delta_p` is evaluated as a VECTOR
identity. `eta_pair=eta_direct-rho_R`, `b_R=||eta_pair||_(H_R^-1)` and
`B_F=sqrt(beta)*b_R`, with beta the largest symmetric generalized eigenvalue
of `(H_F,H_R)`. Norms of individual terms are never subtracted as scalars.

The prescribed raw bound assumes independently valid normal-cone members.
For lower constraints `A@s>=lower`, numerical normals remain
`n=-A.T@mu`; their representation, multiplier sign, feasibility and
complementarity are independently audited. For the saved numerical points,

```
c_N = |mu_F*slack_F|_1 + |mu_R*slack_R|_1
      + |mu_F|_1*violation_R + |mu_R|_1*violation_F
```

is a conservative independent upper bound on
`(n_F-n_R).T@(s_R-s_F)` for nonnegative multipliers. The H_R error therefore
obeys `E_R^2<=b_R*E_R+c_N`; its numerical-normal allowance is
`E_R<=(b_R+sqrt(b_R^2+4*c_N))/2`. Report both raw B_F and the separately
allowance-adjusted H_F bound. A large allowance does not establish exact
interpolation, meaningful small error, or scientific success. An error
above the adjusted bound plus the declared floating allowance is a true
consistency stop.

The full gap is computed directly and checked against
`0.5*||s_R-s_F||_HF^2 - n_F.T@(s_R-s_F) + rho_F.T@(s_R-s_F)`.
The last term is retained for approximate full references. An approximate
reduced minimizer does not inherit the exact-reference reduced-gap lower
bound without its solver defect.

## Immutable controls and missing work

Rank56 includes U8. Protect independent source columns before baseline
fillers; preserve X before Y for BOTH_G. Fill by existing degree and column
index, never by observed error. Random streams use master seed20261006,
parent ID, iteration17 and suffix2101/2102/2103 for G/PG-trial/PG-test.
Random controls match actual independent protected rank after retained-U
deflation. Equal Petrov per-side rank does not mean equal stored memory.

T1 requires state-level diagnostics and controls; a median cannot conceal a
blocked, singular, invalid-reference or ill-scaled state. A positive frozen
oracle result is not nonlinear imaging, runtime gain or NN authorization.
