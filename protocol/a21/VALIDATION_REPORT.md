# Validation Report: Executed Synthetic Algebra Checks

## Scope and evidence status

These tests were executed in this response. They use random complex, non-Hermitian linear systems with real material coordinates. They are **not** the A20 Maxwell backend, the five Gaussian late states, a physical scattering simulator, or nonlinear image reconstruction. No NN was trained.

The main suite contains 16 two-source problems plus one six-source problem. Every problem uses four real material parameters and a box-constrained quadratic with two deliberately active coordinates. Each full optimum is checked by exhaustive enumeration of the 81 possible box-face patterns. The same exact tiny-QP procedure is used for the reduced problems.

Seventeen problems times five basis constructions gives **85 arm-state configurations**. The five constructions are BASE_G, PRIMAL_G, DUAL_G, BOTH_G and BOTH_PG. This suite is a theorem/interface test, not a performance benchmark or an estimate of which architecture will win on Maxwell data.

A separate 32-case suite checks first-order interpolation at feasible non-optimal points, general real measurement whitening and full-frozen-quadratic descent. Its matrices and QPs are also synthetic.

## Reproduction

From the package root:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python validation/validate_two_sided.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python validation/validate_online_descent.py
```

The scripts require NumPy and SciPy. They overwrite only their own JSON result files in `validation/`. They never search for or modify an A20 project. Use the recorded JSON as the source for exact values; roundoff-level figures can change across numerical libraries.

## Exact interpolation results

| Configuration | Maximum relative primal error | Maximum relative dual error | Maximum relative H_F step error |
|---|---:|---:|---:|
| BOTH_G | 5.2683e-16 | 8.0332e-16 | 1.0209e-15 |
| BOTH_PG | 4.2147e-15 | 9.5122e-15 | 1.5269e-15 |

All exact two-sided configurations recover the constrained optimum to numerical precision. They do **not** necessarily approximate the whole Jacobian well: the median relative Frobenius Jacobian discrepancy is 0.677921 for BOTH_G and 1.422801 for BOTH_PG. This is consistent with a task-specific theorem, not a uniform Jacobian approximation theorem.

PRIMAL_G has maximum relative primal error 5.1065e-16, but its median H_F step error is 0.814168. This explicitly verifies that primal interpolation alone is insufficient. DUAL_G is also not an exact interpolation guarantee; any lower error in this random ensemble is not evidence of superiority on the target Maxwell states.

## Identities and inequalities

| Check | Maximum observed discrepancy |
|---|---:|
| Stationarity-defect vector identity | 2.6846e-15 absolute |
| Complex-current / real-material pullback | 7.4476e-16 absolute |
| Tied reduced adjoint | 1.0468e-15 relative |
| Retained-U Schur / Petrov resolvent identity | 7.9340e-15 relative |

The script also checks the constrained H_R and H_F bounds, both sides of the reduced-gap bound, the full-gap bound including normal work, and the feasible inexact-reference/inexact-solver inequality. All assertions passed. These are finite numerical checks supporting the algebra, not replacements for the proofs.

## Six explicit counterexamples

**1. Primal exact, optimum wrong.** The protected direction has zero primal error, but the full optimum (1,0) changes to (1,-4), giving relative H_F error 4. The missing post-step dual pullback is (0,8).

**2. The pre-step residual is the wrong dual target.** A model can match J s_F and J^T r exactly but fail to match J^T(r+J s_F). The example produces about 31.94% relative H_F step error. Protecting an adjoint driven by r is not generally the theorem's condition.

**3. Small relative endpoint errors, enormous step error.** With epsilon=1e-6, epsilon_P=0 and epsilon_D=1e-6, the reduced optimum is (1,-500000). The reduced minimum curvature is 2e-12. The measured absolute H_F error and its correctly scaled bound are both about 500000. This falsifies an unqualified 'small endpoint errors imply a code bug if the step is large' rule.

**4. Perfect containment, singular Petrov core.** L=I, Z=e_1 and W=e_2 capture their respective designated currents but W^*LZ=0. Invertibility is a separate hypothesis; a pseudoinverse is not an exact substitute.

**5. Constrained full gap includes normal work.** The example gives full gap 0.75, while half the squared H_F step error is only 0.25. The missing 0.5 is the nonnegative normal-work term.

**6. Two-sided equality is sufficient, not necessary.** On a half-line constraint, two objectives can have the same boundary optimum with different valid normals and nonzero dual discrepancy. Failure of one sufficient equality is not proof of a wrong optimum.

## First-order interpolation and descent at a feasible point

The separate suite uses 32 feasible points, including points on box boundaries. It applies a general real measurement transformation D and verifies that the dual forcing uses D^T.

| Check | Maximum discrepancy |
|---|---:|
| Primal endpoint interpolation | 3.4283e-16 absolute |
| Gradient interpolation | 9.2389e-16 absolute |
| Objective value interpolation | 7.1054e-15 absolute |
| General real-whitening adjoint identity | 1.0296e-15 absolute |

All 32 cases satisfy grad(q_F)(u)^T d <= -d^T H_+ d. Exact line minimization along the feasible segment decreases the full frozen quadratic in every case. This tests the future online candidate's descent safeguard, not nonlinear convergence or runtime benefit.

## What remains to be measured

The five-state A20/A21 experiment must still establish actual real-packing conventions, valid cached constrained optima, six-source basis bookkeeping, stable rank-56 cores, numerical solver tolerances and the measured dual/curvature anatomy. No claim in this report identifies the cause of the five late-state failures empirically. The files `ORACLE_ANATOMY_SPEC.md` and `CODEX_TWO_SIDED_ANATOMY.md` specify that experiment.
