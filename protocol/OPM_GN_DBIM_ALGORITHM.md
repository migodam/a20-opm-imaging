# PRIMARY ROUTE: deterministic OPM-GN imaging engine

## Decision

Implement a two-stage engine. First isolate tangent compression with accurate full states and full-objective acceptance. Only after this succeeds, replace forward states by a frozen-basis reduced model. Calling both stages 'OPM-GN' without distinguishing their costs and derivatives would conceal an important failure mode.

### A1. Full-state / OPM-tangent imaging

At x_k, calculate the existing full Maxwell state j_k and the full residual. Build B(j_k) through backend actions, not through a full material Jacobian. Construct Schur O/P/M streams and R_m. Use J_m=S R_m B(j_k) as an inexact full-objective tangent. Solve the existing regularized material QP/GN problem. Perform a full material/KKT audit when needed and full-objective line search/LM acceptance.

This is the first representation test: can small OPM current rank preserve the nonlinear material trajectory? It does NOT remove full forward-state costs. Any acceleration claim must include those costs.

### A2. Reduced-state / OPM-tangent imaging

Freeze U,Q (and any Petrov test basis) while evaluating a local trial model. Compute j_m=R_m b and use B(j_m). This is the consistent derivative of the frozen-basis reduced forward model. Track state, residual and tangent errors separately. Start with full-objective acceptance for every accepted step. Sparse/randomized or certified acceptance can be introduced later, only after false-acceptance rates are characterized. A reduced-only line search may converge to the wrong physical objective.

## Backend adapter: required contract

```
state(x, frequency, source) -> j, forward_diagnostics
apply_L(x, v), apply_L_adjoint(x, v)
apply_F(x, v), apply_F_adjoint(x, v)
apply_S(v), apply_S_adjoint(v)
apply_B(x, j, material_direction)
apply_B_adjoint(x, j, current_cotangent) -> REAL material_cotangent
objective(x), constraints(x)
full_tangent_action(x, j, d)
full_adjoint_action(x, j, v)
```

Use one authoritative sign convention, current definition, quadrature/self term and noise whitening. The adapter must pass complex-current adjoint tests and real-material finite-difference tests. Do not create a replacement scalar backend. The supplied synthetic algebra checks are not a backend.

## Source/frequency handling

Within a frequency, L is shared across illuminations, so reduced cores and operator images can be reused. B is source-state-dependent and must not be shared incorrectly. Across frequencies, Green operators, receiver maps and material dispersion may change. Stack whitened realified data and tangents only after mapping every frequency to the same physical material parameter vector. Distinct frequency states are not interchangeable training examples for the same basis.

## Pseudocode

```
load immutable backend, objects, initialization, constraints, regularization policy
for each independent test object and acquisition:
    x = shared_initialization
    initialize action/timing/memory counters
    for k in 0,...,K_max:
        full_state, full_residual = backend.evaluate(x)
        form/update retained U and its forward/adjoint caches
        make O, P, M seed blocks without test truth
        freeze state/residual/Lambda for degree comparisons
        for m in degree_schedule:
            extend independent right and left feedback streams
            form nested joint Q_m and projected physical model
            check rank loss and projected-core stability
            expose paired J_m/J_m^* actions
            solve the common constrained material quadratic
            record innovation and available error bounds
            run full directional/KKT audit when indicated
            stop degree growth only under the declared rule
        if model accuracy fails at cap:
            use existing full reference step; record full cost and fallback
        perform full-objective globalization with the same constraints
        record accepted/rejected trials, x, rank, degree, errors and costs
        if common full-objective/KKT stopping rule is met: stop
    compare final x to truth and to full-GN reference
```

Do not compare methods at different stopping objectives. A low-degree method stopping early because its own gradient vanished must still be assessed against the full-objective gradient and final truth error.

## Material solve: reuse, do not launch another solver project

For small Gaussian parameter spaces, form the real reduced Jacobian and solve the small SPD material system directly. For large voxel spaces, use the existing matrix-free GN implementation and its existing regularization/preconditioner. A Woodbury/data-space solve is allowed where smaller, but apply the same engineering choice to all baselines. No claim of beating Krylov is part of this route.

For Lambda invertible, a useful identity is

    s = -Lambda^{-1}ell
        -Lambda^{-1}J_m^*
         (I+J_m Lambda^{-1}J_m^*)^{-1}
         (r-J_m Lambda^{-1}ell).

Do not materialize a huge data-space system just because the formula exists.

## Complexity and actual actions

Use n current unknowns per source, u retained rank, q OPM rank, p material unknowns, d data dimension, t source count and f frequency count.

Basis storage and cached operator images: O(n(u+q)) per active frequency. Orthogonalization: approximately O(nq^2), plus retained projections. Reduced factorization: O((u+q)^3) per state/frequency. Each paired tangent action costs B/B^*, basis projections/lifts O(nt(u+q)), reduced solves O(t(u+q)^2), and S/S^* actions. Explicit reduced material operators add O(t(u+q)p) storage and should be avoided for large p.

Each physical feedback-chain extension uses actual F/F^* actions as specified in OPM_RESOLVENT_APPROXIMATION.md. Each full audit adds t*f tangent RHS solves and t*f adjoint RHS solves, plus their iterations. Full line search costs forward solves for each trial. Coarse/basis setup, transfers, logging and failed trials belong in total wall time.

## Comparators

Full-current/full-GN is the physics reference, NOT automatically the minimum truth-error estimator. Compare receiver/SOM current ROM, fixed random current ROM, ordinary forward block Krylov, source/current POD trained on separate objects, O-only, P-only, M-only, O+M, joint OPM, forward-only OPM, and adaptive joint OPM. O+M is important: otherwise a claimed three-channel effect may actually be a familiar two-sided ROM.

Use both matched-current-rank and matched-Maxwell-action comparisons. The crucial stronger baseline is a derivative-/goal-aware interpolatory ROM, where feasible, not only POD/random. Charge any full snapshot solves or Jacobian-derived basis generation. For random baselines report multiple independent seeds on the replay and retain a prespecified seed policy in live runs.

## Failure modes

A1 can fail to accelerate because exact forward states/globalization dominate. A2 can fail from state-induced B error despite good frozen-state tangents. Both can fail from coarse-core resonance, nonnormal tail, inadequate source/task seeds, stale recycling, expensive QR, or artificial weak directions. A small data residual with wrong material is not a success.

## Minimum experiment and gate

Use 6 independent existing objects spanning smooth Gaussian, near-contact, asymmetric, layered/voxel and high-contrast cases. First replay two stored nonlinear states per object. Then run genuinely closed-loop reconstruction on the 6 objects with full GN, OPM m=0/1/2/3, one receiver-ROM and one ordinary-Krylov control: 42 reconstruction runs if all seven methods are retained. Use staged elimination after the replay to reduce cost transparently. Broader ablations remain in the cheap replay; do not launch hundreds of full runs immediately.

A suggested first practical GO is median final material error <=1.05 times full GN (use an additive tolerance near zero reference error), no unexplained catastrophic failures, and median total wall time <=0.8 times full GN for a deployment acceleration claim. These numerical margins are PROPOSED decision thresholds, not established performance. Small pilots cannot establish population confidence. When quality passes but speed does not, the representation may remain useful but the acceleration claim fails.
