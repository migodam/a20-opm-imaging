# Approximate Two-Sided Interpolation: Bounds and the Correct Consistency Test

## 1. Exact defect decomposition

Use the setting of `TWO_SIDED_GN_THEOREM.md`. Let H_R be positive definite, mu=lambda_min(H_R)>0, and let s_R be the exact reduced constrained minimizer. Fix the valid full normal n_F. At s_F,

\[
\eta_R:=\nabla q_R(s_F)+n_F
=\delta_d+J_R^T\delta_p,
\]

where delta_p=(J_R-J_F)s_F and delta_d=(J_R-J_F)^T e_F. This follows by writing r+J_Rs_F=e_F+delta_p and subtracting full KKT.

Consequently,

\[
\|\eta_R\|_2\le\|\delta_d\|_2+\|J_R\|_2\|\delta_p\|_2.
\]

Compute the vector sum, not only this triangle bound: the two contributions may cancel or reinforce. A large relative dual error need not dominate the combined stationarity error, and a small primal relative error need not make J_R^T delta_p negligible.

## 2. Constrained monotonicity proof

Let d=s_R-s_F, and choose n_R in N_C(s_R) with grad q_R(s_R)+n_R=0. Subtraction gives

\[
\eta_R=-H_Rd+n_F-n_R.
\]

Normal-cone monotonicity says (n_R-n_F)^T d>=0. Hence

\[
\|d\|_{H_R}^2\le-\eta_R^Td
\le\|\eta_R\|_{H_R^{-1}}\|d\|_{H_R}.
\]

With b_R=||eta_R||_{H_R^{-1}}, this proves

\[
\boxed{\|s_R-s_F\|_{H_R}\le b_R},
\]

\[
\boxed{\|s_R-s_F\|_2\le b_R/\sqrt\mu
\le\|\eta_R\|_2/\mu
\le(\|\delta_d\|_2+\|J_R\|_2\|\delta_p\|_2)/\mu.}
\]

Lambda positive definite implies mu>=lambda_min(Lambda). No claim that Lambda must be the only source of positive curvature is needed.

## 3. Reduced quadratic gap

Quadratic expansion and n_F^T d<=0 give

\[
q_R(s_F)-q_R(s_R)
=-\eta_R^Td+n_F^Td-\tfrac12\|d\|_{H_R}^2
\le b_R\|d\|_{H_R}-\tfrac12\|d\|_{H_R}^2
\le\tfrac12 b_R^2.
\]

Strong convexity at the reduced minimizer gives the lower bound:

\[
\boxed{\tfrac12\|d\|_{H_R}^2
\le q_R(s_F)-q_R(s_R)
\le\tfrac12\|\eta_R\|_{H_R^{-1}}^2
\le\|\eta_R\|_2^2/(2\mu).}
\]

These are inequalities in the constrained case. The unconstrained solution has d=-H_R^{-1}eta_R, and both energy and reduced-gap bounds become equalities.

## 4. Full-Hessian norm

Define the metric comparison constant

\[
\beta=\sup_{v\ne0}\frac{v^TH_Fv}{v^TH_Rv}
=\lambda_{\max}(H_R^{-1/2}H_FH_R^{-1/2}).
\]

Then

\[
\boxed{\|d\|_{H_F}\le\sqrt\beta\,b_R.}
\]

For small material dimension, compute beta as the largest symmetric generalized eigenvalue of (H_F,H_R), not the spectral radius of an arbitrarily nonsymmetric product. For large dimension, a rigorous upper bound is needed before calling this a certificate; an unconverged Ritz estimate is not automatically an upper bound.

A looser bound is ||d||_{H_F}<=sqrt(lambda_max(H_F))*||eta_R||_2/mu.

## 5. Full quadratic gap: retain normal work

The exact full-gap identity is

\[
\boxed{q_F(s_R)-q_F(s_F)
=\tfrac12\|d\|_{H_F}^2-n_F^Td.}
\]

Since n_F^Td<=0, the normal-work term is nonnegative. It cannot generally be omitted. In particular,

\[
\tfrac12\|d\|_{H_F}^2
\le q_F(s_R)-q_F(s_F)
\le \tfrac12\beta b_R^2+\|n_F\|_{H_R^{-1}}b_R.
\]

For an unconstrained optimum, n_F=0. The same simplification applies to a displacement tangent to a common active face with n_F^Td=0, but not to arbitrary feasible displacements or changed active sets.

Counterexample: q_F(s)=0.5(1+s)^2+0.5s^2 on s>=0 has s_F=0, n_F=-1 and H_F=2. With J_R=-1, the reduced optimum is s_R=0.5. The full gap is 0.75, whereas half the squared H_F error is 0.25; the missing normal work is 0.5.

## 6. Approximate full and reduced solves

In code, full references are not mathematically exact. Let a and b be feasible numerical full and reduced solutions. Let n_a in N_C(a), n_b in N_C(b) be independently validated normals, and define

\[
\rho_F=J_F^T(r+J_Fa)+\Lambda a+\ell+n_a,
\]
\[
\rho_R=J_R^T(r+J_Rb)+\Lambda b+\ell+n_b.
\]

Define delta_p and delta_d at a, with e_a=r+J_Fa. Then

\[
\nabla q_R(a)+n_a=\rho_F+\delta_d+J_R^T\delta_p,
\]

and monotonicity gives

\[
\boxed{\|b-a\|_{H_R}
\le\|\rho_F+\delta_d+J_R^T\delta_p-\rho_R\|_{H_R^{-1}}.}
\]

Multiplying the right side by sqrt(beta) bounds the H_F error. This is the appropriate solver-aware consistency test. Compare vector expressions including solver defects; do not subtract their norms as though they were signed scalars.

For q_R(a)-min_C q_R, the gap bound remains 0.5||rho_F+delta_d+J_R^T delta_p||_{H_R^{-1}}^2. It does not automatically give a lower bound on q_R(a)-q_R(b) when b is only an approximate minimizer.

## 7. Valid normals and tighter residuals

For a box lower<=s<=upper, the normal is nonpositive at a lower bound, nonnegative at an upper bound and zero in the interior. A fixed coordinate with equal bounds permits any normal. Use solver multipliers or project -grad q_F onto the correctly signed normal cone. Do not define n_F=-grad q_F and skip normal membership: that makes every point look stationary.

For a trust ball, include its radial normal and nonnegative multiplier when active. For intersecting constraints, use the actual solver's KKT representation or a justified cone calculation.

The supplied full normal gives a useful, possibly conservative bound. One can minimize ||grad q_R(s_F)+n||_{H_R^{-1}} over valid normals for a tighter constrained residual. This refinement is optional; the main diagnostic must preserve the full normal so its two-sided decomposition remains transparent.

On a known common active affine face, if both optima are stationary relative to its tangent basis T, then

\[
d=-T(T^TH_RT)^{-1}T^T\eta_R.
\]

This can remove irrelevant normal errors from a diagnostic. It requires the common-face assumptions and is not a substitute for validating active-set changes.

## 8. Correct the proposed killer test

The implication 'epsilon_P and epsilon_D are both small, therefore the step must be small' is false without a curvature-aware scale. An explicit example is

\[
J_F=\begin{pmatrix}1&0\\0&1\\0&0\end{pmatrix},
\quad J_R=\begin{pmatrix}1&0\\0&0\\0&\varepsilon\end{pmatrix},
\quad r=(-2,0,1)^T,
\quad\Lambda=\operatorname{diag}(1,\varepsilon^2),\quad\ell=0.
\]

With epsilon=1e-6, s_F=(1,0), s_R=(1,-500000), epsilon_P=0, epsilon_D=1e-6, and mu=2e-12. The relative H_F step error is about 353553.39. The bound predicts the absolute H_F error of about 500000 correctly. There is no inconsistency.

The corrected rule is:

> If both interpolation targets, valid constraints/normals and solver tolerances imply a small **solver-aware H_F error bound**, but the measured error violates that bound beyond a declared floating-point allowance, stop and debug. Exact containment in a stable, well-resolved core should reduce to equality at numerical tolerance.

Report ||s_F||_{H_F}, absolute step error, absolute eta, mu, beta and the reference predicted reduction. Late-state relative error can grow solely because its denominator shrinks. A small relative tangent error is a diagnostic, not a complete causal explanation.
