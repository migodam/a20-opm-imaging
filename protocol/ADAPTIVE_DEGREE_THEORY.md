# Material-update-aware degree control

All formulas use whitened REAL data/material coordinates; * below is a transpose in these coordinates. Keep the state, residual, regularization and feasible set frozen during a degree comparison unless their differences are included explicitly.

## 1. Exact perturbation identity

Let

    H=J^*J+Lambda, g=J^*r+ell, s_F=-H^{-1}g,
    J_m=J+E, r_m=r+delta_r,
    H_m=J_m^*J_m+Lambda, g_m=J_m^*r_m+ell.

Then

    Delta_H = J^*E+E^*J+E^*E,
    Delta_g = E^*r+J_m^*delta_r,
    s_m-s_F = -H_m^{-1}(Delta_g+Delta_H s_F).

Let epsilon=||E H^{-1/2}|| and delta=2 epsilon+epsilon^2. Since Lambda>=0 implies ||J H^{-1/2}||<=1,

    ||H^{-1/2}Delta_H H^{-1/2}|| <= delta.

If delta<1,

    ||s_m-s_F||_H
      <= [||H^{-1/2}Delta_g||+delta||s_F||_H]/(1-delta).

This is an a priori perturbation bridge. The exact full H in it makes it a theorem/diagnostic, not a free deployment estimator. Large residual or small regularization can amplify apparently small Jacobian error.

## 2. The more useful a posteriori identity

For an actually computed step s_m, define the FULL quadratic stationarity defect

    q_m = H s_m+g.

Then exactly

    s_m-s_F = H^{-1}q_m,
    ||s_m-s_F||_H = ||q_m||_{H^{-1}},
    Phi_F(s_m)-Phi_F(s_F) = 0.5 q_m^*H^{-1}q_m.

For an exact reduced step, fixed full residual, and D=J-J_m,

    q_m = J_m^*D s_m
          +D^*(r+J_m s_m)
          +D^*D s_m.

With reduced residual r_m=r+delta_r, add -J_m^*delta_r. With an inexact material solve, retain its reduced normal-equation residual as an additional term.

This formula shows why ||field residual|| alone is insufficient: both the forward action on the proposed MATERIAL step and the adjoint pullback of the post-step DATA residual matter.

### Evaluation without forming a full Jacobian

At a fixed full state:

    v = J s_m                  # one full tangent RHS per source/frequency
    q = J^*(r+v)+Lambda s_m+ell # one full adjoint RHS per source/frequency

One J action or J^* action consists of an ensemble of physical solves, not one solve for the entire experiment. All iterations within these solves count as Maxwell actions. No full Jacobian columns or full GN solve are needed. The audit is still potentially expensive and must be timed.

### A genuine bound versus an empirical metric

If H>=lambda I is known,

    ||s_m-s_F||_H <= ||q_m||/sqrt(lambda),
    quadratic excess <= ||q_m||^2/(2 lambda).

If a VALID spectral-equivalence bound

    eta=||H_m^{-1/2}(H-H_m)H_m^{-1/2}||<1

is available, sharpen this to

    ||s_m-s_F||_H <= ||q_m||_{H_m^{-1}}/sqrt(1-eta).

A handful of probes usually does not certify eta. A reduced-core condition number does not bound ||L^{-1}||. A numerical Ritz estimate is not automatically a lower bound on lambda_min of an unobserved full operator. Label unvalidated substitutes as indicators.

## 3. Constraints and LM

If both quadratics are minimized over the same convex feasible step set D, choose v_m in the normal cone N_D(s_m). Put

    q_KKT=H s_m+g+v_m.

For an exact reduced constrained solve, v_m=-(H_m s_m+g_m). Monotonicity of the normal cone gives

    ||s_m-s_F||_H <= ||q_KKT||_{H^{-1}},
    Phi_F(s_m)-Phi_F(s_F) <= 0.5 ||q_KKT||_{H^{-1}}^2.

These are inequalities, not the unconstrained equalities. Use the QP solver's actual multipliers/normal residual. Clipping an unconstrained step after the fact generally does not solve either QP. With only projected steps, use a projected-gradient/KKT residual rather than applying unconstrained identities to the clipped step.

Keep the LM damping identical during adjacent-degree diagnostics; changing damping can hide or manufacture apparent improvement. Changes in state/injection/residual similarly require explicit bookkeeping.

## 4. Exact adjacent-degree update law

Let J_+=J_m+D_m and H_+=J_+^*J_++Lambda. With fixed r, ell and Lambda,

    H_+(s_+-s_m)
      = -[J_m^*D_m s_m
          +D_m^*(r+J_m s_m)
          +D_m^*D_m s_m].

A cheap innovation is

    iota_m=||s_+-s_m||_W / max(||s_+||_W,s_floor),

where W is a common SPD material metric, for example a fixed local Lambda or reference Hessian. Report its definition. A changing H_m is acceptable as a diagnostic if identified, but not a telescoping tail norm without further assumptions.

If a independently justified saturation law holds in a COMMON norm,

    ||s_{j+1}-s_j||_W <= rho^(j-m)||s_{m+1}-s_m||_W,
    all j>=m, rho<1,

and s_j converges to s_F, then

    ||s_F-s_m||_W <= ||s_{m+1}-s_m||_W/(1-rho).

One observed ratio below one does not establish this hypothesis. The supplied seven-node nilpotent chain gives s_0=s_1=s_2=0 but s_3=s_F>0, including BOTH forward and adjoint chains. Therefore even two or three stable degrees are not a standalone certificate.

## 5. The proposed two-level controller

Use innovation for scheduling, and a full material/KKT audit or a valid two-sided bound for acceptance of model accuracy.

```
for each nonlinear state x_k:
    compute the chosen full or validated reduced state
    freeze residual/state/regularization for the degree sweep
    start from a recycled low degree (not necessarily the previous degree)
    for m in 0,...,m_cap:
        extend separate right/left chains; form joint Q_m
        compute reduced constrained GN step s_m
        record update innovation, projected-core stability, seed residuals
        if promising_to_stop or at_cap or model_disagreement:
            evaluate full q_KKT(s_m), or a valid certified upper bound
            if audit passes: stop increasing degree
        if degree cap hit and audit fails:
            use existing full-GN step; record fallback and its total cost
    accept/reject using a full or certified objective evaluation
    update state; refresh seed and basis provenance
```

Proposed pilot settings, not theorems: degree cap 3 initially; permit one escalation to degree 5 before full fallback. Use iota<0.05 as an audit trigger, not a proof. In the replay, choose the audit threshold to target relative H-step error <=0.05 and report false-acceptance curves. The online implementation must use quantities available online, not a full-reference step hidden in the threshold.

A conservative descent sufficient condition is ||q_m|| <= eta lambda ||s_m||, eta<1. Then g^*s_m<0 unless s_m=0, because H>=lambda I. For constraints use feasible descent and KKT criteria. Full Armijo slopes can be computed from Re(r^*J s_m)+ell^*s_m with the tangent action already available.

## 6. Nonlinear convergence scope

Under bounded level sets, Lipschitz derivatives, a uniform positive regularization metric, an ordinary full-objective line search/trust region, and model improvements that restore first-order accuracy, standard inexact-model arguments support convergence to stationary/KKT points. For asymptotic exactness make the model forcing error tend to zero; fixed low degree only supports convergence to a biased neighborhood unless the needed action becomes exact.

This does not establish global recovery of the true material, uniqueness, or a benefit from higher frequency. Use the local strong-convexity bridge in OPM_IMAGING_THEORY.md only where its assumptions are justified.

## 7. What is potentially publishable here

Not 'inexact GN exists' and not the normal-equation residual identity by itself. The potential contribution is a Maxwell Schur-feedback hierarchy with separately controlled injection and observation residuals, whose degree is selected using material-update/KKT fidelity and whose END-TO-END imaging tradeoff is established against competitive ROMs. Adaptive inverse-problem ROM work is a close antecedent [R04,R05].
