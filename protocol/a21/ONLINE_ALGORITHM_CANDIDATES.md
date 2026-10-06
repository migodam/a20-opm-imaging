# Conditional Online Candidates After the Oracle Anatomy

These are derivations and future specifications. They are **not part of the immediate five-state execution authorization**. Keep polynomial depth fixed initially and use the existing material solver.

## A. Cheap task-retargeted two-sided OPM

At a frozen outer state, start from the existing fixed-depth primal M/P and dual O/P bases. Solve the reduced constrained quadratic for s_m, form e_m=r+J_m s_m, and retarget the source-wise material seeds B_a s_m and receiver adjoint seeds S_a^* e_m^{(a)}. Propagate the former forward and the latter adjoint at the existing shallow depth, update Z/W, and re-solve. Limit to one or two refinements.

The Schur seeds are K B_a s_m and T^*S_a^*e_m^{(a)}, with actual packing/whitening accounted for. Preserve tied adjoints, a fixed basis during each solve and the same constrained quadratic data.

This uses neither s_F nor truth. But e_m is a model prediction, not the full e(s_m). There is no general contraction guarantee. Recomputing a current using the same reduced inverse produces a vector already inside the basis and adds no information. An independent operator residual, feedback action outside the present span, or a full audit is necessary to escape such self-confirming fixed points.

**Future minimum test:** after the oracle passes, try one and two refinements on the same frozen states, with total rank and full action counts recorded. Stop if the gradient certificate does not improve or unstable cores appear. Do not infer success from basis changes alone.

## B. Audited primal-dual tangential refinement

This is the simplest mathematically controlled candidate. It pays for a small number of full current solves but never asks for the unknown optimum or all full Jacobian columns.

Given a feasible reduced solution u and a valid reduced normal n_u, compute

\[
x_u^{(a)}=L^{-1}B_a u,
\qquad e(u)=r+J_Fu,
\qquad y_u^{(a)}=L^{-*}S_a^*e_c(u)^{(a)}.
\]

The source banks produce the full KKT defect

\[
\xi_F=J_F^Te(u)+\Lambda u+\ell+n_u.
\]

For H_F positive definite,

\[
\|u-s_F\|_{H_F}\le\|\xi_F\|_{H_F^{-1}}
\le\|\xi_F\|_2/\sqrt{\lambda_{\min}(\Lambda)}
\]

when the latter lower bound is positive. The first inequality uses the same constrained monotonicity argument. A full inverse-Hessian action is not needed for the looser certified bound. An approximate inverse action without an error estimate is only an estimator.

If the audit is not satisfactory, protect X_u in the trial basis and Y_u in the test basis (or both in a common Galerkin basis), retaining stable square cores. The already-computed audit currents become the enrichment bank; do not solve for them twice. Re-solve the reduced constrained quadratic.

## A further result: first-order interpolation at any feasible point

The current-containment proof is not restricted to an optimum. If the new model J_+ matches

\[
J_+u=J_Fu,\qquad J_+^Te(u)=J_F^Te(u),
\]

then

\[
q_+(u)=q_F(u),\qquad\nabla q_+(u)=\nabla q_F(u).
\]

Let v minimize the new reduced quadratic over the same convex C, and set d=v-u. If H_+ is positive definite, reduced optimality gives

\[
\nabla q_F(u)^Td=\nabla q_+(u)^Td\le-d^TH_+d<0
\]

unless d=0. Indeed, grad q_+(v)+n_v=0 and n_v^T(u-v)<=0 imply the inequality after subtracting the quadratic gradients.

Therefore d is a feasible descent direction for the **full frozen quadratic**. The segment u+alpha*d is feasible for 0<=alpha<=1. Since

\[
q_F(u+\alpha d)-q_F(u)
=\alpha\nabla q_F(u)^Td+\tfrac12\alpha^2d^TH_Fd,
\]

a full-quadratic line minimization may use

\[
\alpha_* = \min\left\{1,\frac{-\nabla q_F(u)^Td}{d^TH_Fd}\right\}>0
\]

for d nonzero. Its curvature denominator needs a full tangent action J_Fd and the known regularizer. If d=0, first-order interpolation means u is already the full constrained optimum under the theorem's assumptions.

This gives a descent safeguard, **not** a contraction factor, a one-step recovery guarantee or global nonlinear convergence. With approximate current protection, use the measured first-order defect and a full-quadratic acceptance check instead of assuming descent.

## Pseudocode for a future two-refinement pilot

```text
u, valid_normal = existing_reduced_constrained_QP()
repeat at most twice:
    X = full_current_solve(B * u)                 # all source columns
    e = r + pack_measurement(S * X)
    Y = full_adjoint_current_solve(adjoint_measurement(e))
    xi = real_material_pullback(B, Y) + Lambda*u + ell + valid_normal
    if declared full-KKT error bound is adequate:
        return u
    Z, W = protect_and_fill(X, Y, retained_U, fixed_rank)
    require stable core and tied adjoint
    v = existing_constrained_QP(J(Z,W), r, Lambda, ell, C)
    d = v - u
    if d is zero:
        recheck the measured certificate and numerical tolerances
        return or flag inconsistency
    perform full-frozen-quadratic line minimization/acceptance on u + alpha*d
    update u and compute a valid normal for its current location
return u with its final audit, or declared full-solver fallback / failure status
```

After line minimization, the new u need not minimize a reduced model, but any valid normal (including zero) is permitted in the full monotonicity audit. Do not reuse an old active-set multiplier at a point where it is no longer a valid normal.

## Cost and falsifiability

For six sources, each audit requires six primal and six adjoint RHS if not cached. A full-quadratic line-curvature evaluation requires an additional six tangent RHS. Existing factorization reuse can reduce overhead but does not remove cost. Compare with the actual full GN implementation, including its matrix-free actions and batching, rather than an artificially expensive dense-J baseline.

The exact line-descent result follows from first-order consistency, a classical reduced-optimization principle (see R3-R5). The potentially useful Maxwell-specific contribution is reusing these two source-resolved audit banks as the physical interpolation basis and quantifying whether one or two updates suffice.

## When NN may re-enter

Not after oracle success alone. First demonstrate an online-legal two-sided model and stable data-supported material updates. Only then test whether few task directions can be predicted more cheaply, or whether a remaining full-physics weak space supports a learned prior. Do not use NN to hide a wrong reduced adjoint or to emulate the complete resolvent.
