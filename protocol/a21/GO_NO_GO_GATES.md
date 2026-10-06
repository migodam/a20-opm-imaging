# Predeclared Scientific and Implementation Gates

## T0: Algebra and implementation consistency

The standalone synthetic tests must pass: complex-to-real pullback, active-box full KKT, exact two-sided Galerkin and Petrov minimizer equality, defect decomposition, constrained bounds, full normal-work gap and Schur equivalence. The included double-precision tests use a relative exact-step target of 1e-8 and achieve substantially smaller errors; this tolerance is not a universal full-sized Maxwell tolerance.

For backend tests, record core conditioning and current-solve backward errors, choose a numerical tolerance before inspecting the new step errors, and retain reference/reduced KKT residuals. A forward model and an independently untied backward map fail this gate.

If the numerical full step is not a constrained frozen optimum, repair/re-solve that same reference using the existing solver or report a blocker. Do not use an accepted line-search displacement as the optimum. No physical explanation is valid before this distinction is resolved.

## T1: Five-state diagnosis

The primary endpoint is measured H_F step error together with the solver-aware bound. Predeclare 5% relative H_F error as the scientific small-error target when ||s_F||_{H_F} is well-scaled. In well-resolved exact-current cases, expect numerical agreement much tighter than 5%; 5% is not the exact-theorem tolerance.

- **Full support:** all five assessable BOTH_G states meet the target and consistency checks, while PRIMAL_G exhibits the relevant missing dual/stationarity contribution and the rank-matched random control does not explain the result.
- **Partial support:** only a subset is assessable or passes; report each state and failure reason. Do not hide an unstable or ill-scaled state in a median.
- **Implementation inconsistency:** measured error violates the solver-aware norm bound beyond the declared floating-point allowance. Stop and debug packing, adjoints, constraints, solver accuracy, coordinates and cached-model identity.
- **Conditioning-limited approximation:** both relative endpoint errors are small but the valid H_F bound is large because mu is small or beta is large. This is not a theorem violation.
- **Rank/core issue:** containment is impossible at the frozen rank, or the core is singular/unsafe. This is an architecture or numerical limitation, not a failure of a theorem whose hypotheses are absent.

The label `LATE_GN_TWO_SIDED_FIDELITY_CONFIRMED` is allowed only with the stated causal pattern and full disclosure of absolute errors, normals, scales and controls. Otherwise use a more specific partial or negative label.

## Alternative explanations the protocol must preserve

If PRIMAL_G now succeeds without deliberate dual protection, inspect its measured dual error. The exact-current bank may indirectly capture dual information, or the old injection-only oracle may have left a relevant primal defect. Do not attribute every improvement exclusively to adding Y_F.

If DUAL_G succeeds, the practical missing information may be dominated by the residual pullback, but the theorem still does not say primal interpolation is universally unnecessary.

If BOTH_G succeeds but BOTH_PG fails, preserve the two-sided mechanism and reject the claimed advantage of this Petrov implementation. If random controls also succeed, the oracle-specific explanation has weak discrimination; rank-matched replacement or baseline truncation may be sufficient.

If near-zero reference steps make percentage errors meaningless, report absolute error, full quadratic gap and predicted reduction. Such a state cannot support or refute a 5% ratio gate without a declared meaningful scale.

## T2: Practical headroom, not part of this execution

Only after T0/T1 are resolved, test a non-oracle one/two-refinement algorithm with fixed initial depth and fair total action counts. Judge quality versus full GN and common/two-sided goal-aware ROM controls, not only improvement over the failing old OPM baseline.

A frozen-step improvement is not yet nonlinear imaging success. A later paper-quality study must include genuinely nonlinear 3D material reconstruction and all setup, audit, factorization, QR, adjoint and acceptance costs.

Do not train NN after an oracle-only pass. The next question is whether useful task currents can be obtained online at acceptable cost.

## What can be killed now?

The exact algebra is proved under its hypotheses; an inconsistent implementation is not evidence of new physics. The proposed **explanation** can be rejected if measured defect anatomy shows a different dominant cause. The low-rank **architecture** can be rejected if valid protection is unaffordable or unstable. The prospective **algorithm** can be rejected if online audits/enrichment erase its cost benefit. None of these conclusions requires claiming that all current ROMs or all two-sided methods are impossible.
