# A21 Complete Research Memo

## Two-Sided GN Interpolation Anatomy for OPM Full-Wave Imaging

This consolidated memo combines the proofs, prior-art audit, frozen oracle specification, conditional online candidates and executed synthetic tests. The actual A20 five-state Maxwell anatomy has not been run in this environment. Start with `START_HERE.md`; give `CODEX_TWO_SIDED_ANATOMY.md` to the implementation agent.

## Contents

1. [TWO_SIDED_GN_THEOREM.md](TWO_SIDED_GN_THEOREM.md)
2. [APPROXIMATE_ERROR_BOUND.md](APPROXIMATE_ERROR_BOUND.md)
3. [MAXWELL_PRIMAL_DUAL_INTERPRETATION.md](MAXWELL_PRIMAL_DUAL_INTERPRETATION.md)
4. [PETROV_GALERKIN_TASK_INTERPOLATION.md](PETROV_GALERKIN_TASK_INTERPOLATION.md)
5. [OPM_PRIMAL_DUAL_ARCHITECTURE.md](OPM_PRIMAL_DUAL_ARCHITECTURE.md)
6. [CLOSEST_PRIOR_AUDIT.md](CLOSEST_PRIOR_AUDIT.md)
7. [ORACLE_ANATOMY_SPEC.md](ORACLE_ANATOMY_SPEC.md)
8. [ONLINE_ALGORITHM_CANDIDATES.md](ONLINE_ALGORITHM_CANDIDATES.md)
9. [GO_NO_GO_GATES.md](GO_NO_GO_GATES.md)
10. [CODEX_TWO_SIDED_ANATOMY.md](CODEX_TWO_SIDED_ANATOMY.md)
11. [VALIDATION_REPORT.md](VALIDATION_REPORT.md)
12. [REFERENCES.md](REFERENCES.md)

# Exact Two-Sided GN Task Interpolation

## 1. Frozen mathematical problem

All material vectors are real. Let C be a nonempty closed convex subset of R^p. Fix the same real residual r, real vector ell, and symmetric positive semidefinite matrix Lambda in both models. For a real, whitened, packed Jacobian J define

\[
q_J(s)=\tfrac12\|r+Js\|_2^2+\ell^Ts+\tfrac12s^T\Lambda s,
\qquad s\in C.
\]

Write J_F and J_R for the full and reduced models and H_a=J_a^T J_a+Lambda. Assume a full minimizer s_F exists. Define

\[
e_F=r+J_Fs_F,
\qquad
N_C(s)=\{n:n^T(z-s)\le0\ \text{for every }z\in C\}.
\]

Convex first-order optimality gives a valid normal n_F satisfying

\[
J_F^T e_F+\Lambda s_F+\ell+n_F=0,
\qquad n_F\in N_C(s_F).
\]

For this normal-cone formulation, no separate Slater hypothesis is needed: it is the variational-inequality characterization of a differentiable convex function minimized over C. Representing that normal by multipliers of a particular constraint representation can require additional regularity.

This theorem concerns the raw minimizer of the **frozen constrained quadratic**. A line-search-scaled step, a clipped unconstrained step, or the accepted nonlinear material increment need not be that minimizer.

## 2. Theorem

Suppose

\[
J_Rs_F=J_Fs_F,
\qquad
J_R^Te_F=J_F^Te_F.
\]

Then s_F is a global minimizer of q_R over C. If H_R is positive definite, it is the unique minimizer, so s_R=s_F. In particular, Lambda positive definite suffices.

### Proof

The first equality gives r+J_Rs_F=e_F. Therefore

\[
\begin{aligned}
\nabla q_R(s_F)+n_F
&=J_R^T(r+J_Rs_F)+\Lambda s_F+\ell+n_F\\
&=J_R^Te_F+\Lambda s_F+\ell+n_F\\
&=J_F^Te_F+\Lambda s_F+\ell+n_F=0.
\end{aligned}
\]

Thus the same valid normal n_F certifies reduced optimality. Convexity makes this sufficient for global optimality. Positive definiteness of H_R makes q_R strictly convex and gives uniqueness. QED.

The primal equality also gives q_R(s_F)=q_F(s_F), and the two equalities give equality of the full and reduced gradients at s_F. They do **not** require H_R=H_F or uniform accuracy of J_R.

## 3. What is sufficient and what is necessary?

Two-sided interpolation is sufficient, not necessary. More generally, define

\[
\delta_p=(J_R-J_F)s_F,
\quad
\delta_d=(J_R-J_F)^Te_F,
\quad
\eta=\delta_d+J_R^T\delta_p.
\]

The condition eta=0 already preserves the same KKT normal, even if the two terms are individually nonzero and cancel. With constraints, even eta=0 is not necessary: a different valid reduced normal may certify the same minimizer. The exact necessary and sufficient condition is

\[
-\nabla q_R(s_F)\in N_C(s_F).
\]

For example, on C=[0,infinity), r=1, Lambda=1 and ell=0, both J_F=1 and J_R=2 have minimizer 0. Primal interpolation holds automatically, dual interpolation fails, and the normals are respectively -1 and -2.

If e_F=0, the dual requirement is vacuous. If s_F=0, the primal requirement is vacuous. If H_R is semidefinite, s_F remains a minimizer under exact interpolation, but another minimizer may be returned. Strict convexity on feasible differences is enough for uniqueness; global H_R positive definiteness is a convenient stronger hypothesis.

A nonconvex feasible set is outside the global theorem. A local normal-cone stationarity condition alone does not imply global optimality there.

## 4. Why primal-only interpolation is insufficient

Take

\[
J_F=\begin{pmatrix}1&0\\0&1\\0&0\end{pmatrix},
\quad J_R=\begin{pmatrix}1&0\\0&0\\0&1\end{pmatrix},
\quad r=\begin{pmatrix}-2\\0\\8\end{pmatrix},
\quad \Lambda=I,\quad\ell=0,\quad C=\mathbb R^2.
\]

Then s_F=(1,0)^T and s_R=(1,-4)^T. The primal interpolation is exact, but

\[
e_F=(-1,0,8)^T,\quad
\delta_d=(0,8)^T.
\]

Since H_F=2I, the relative H_F step error is 4, or 400%. The reduced model maps a residual component that is invisible to the full model into a false material update. This is a synthetic counterexample, not a reconstruction of the user's 366% experiment.

## 5. Why the dual target must be the post-step residual

Replace J_R above with

\[
J_R=\begin{pmatrix}1&1\\0&1\\0&1\end{pmatrix},
\qquad r=(-2,0,2)^T.
\]

Now J_Rs_F=J_Fs_F and J_R^Tr=J_F^Tr both hold, yet

\[
(J_R-J_F)^T e_F=(0,1)^T,
\qquad s_R=(8/7,-2/7)^T\ne s_F.
\]

The relative H_F error is sqrt(5)/7. Matching the current residual pullback J^Tr is not matching the GN stationarity target J^T(r+Js_F).

## 6. Interpretation and novelty limit

This is a first-order optimality interpolation statement for one frozen optimization task. It follows directly from convex KKT conditions combined with classical left/right tangential projection properties. It is valuable as an exact diagnostic and architecture constraint, not as a claim of the first two-sided ROM theorem. See the literature audit.


---

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


---

# Maxwell Primal/Dual Currents and Real-Material Conventions

## 1. Standard packed convention

Let L be a nonsingular complex current operator at one frozen material state. Let B map a real material step to a complex current forcing, and let S map complex currents to already-whitened complex measurements. Define

\[
\mathcal J_F=SL^{-1}B,
\qquad
\mathcal Pz=\begin{bmatrix}\operatorname{Re}z\\\operatorname{Im}z\end{bmatrix},
\qquad J_F=\begin{bmatrix}\operatorname{Re}\mathcal J_F\\\operatorname{Im}\mathcal J_F\end{bmatrix}.
\]

Here the complex spaces use the real Hilbert inner product Re(u^*v). P is an isometry to Euclidean real coordinates. If e=(e_Re,e_Im), define e_c=e_Re+i e_Im. Then

\[
J_F^Te=\operatorname{Re}(\mathcal J_F^* e_c).
\]

For a real material step s_F, define

\[
x_F=L^{-1}Bs_F,
\qquad y_F=L^{-*}S^*e_{F,c}.
\]

The two GN targets are

\[
J_Fs_F=\mathcal P(Sx_F),
\qquad J_F^Te_F=\operatorname{Re}(B^*y_F).
\]

There is no extra factor two for q(s)=0.5||P(r_c+J_c s)||^2. A convention using a different prefactor or sqrt(2)-packing must carry that factor consistently. In particular, the adjoint of alpha*P is alpha*P^flat, not merely an unscaled unstacking operation.

The physical interpretation is specific: x_F is the incremental current excited by the optimum **material step**, not the total forward induced current. y_F is the adjoint current excited by the **post-step predicted residual**, not by the current residual r alone.

## 2. General whitening and packing

If the backend uses a real whitening matrix D after packing, write

\[
J_F=D\mathcal P SL^{-1}B.
\]

Then the correct dual forcing is

\[
g_e=S^*\mathcal P^\flat D^T e,
\qquad
\mathcal P^\flat v=v_{\mathrm{Re}}+i v_{\mathrm{Im}},
\]

and J_F^T e=Re(B^*L^{-*}g_e). The transpose D^T, rather than an inverse-whitening operation, belongs in the adjoint. Complex whitening may instead be absorbed into S. A source-major interleaved real layout is also valid, but its exact inverse permutation and adjoint must be used.

These formulas state conventions; they are **not a claim that the unavailable A20 backend uses a particular layout**. Codex must identify the actual layout, scaling, source weights and parameter scaling from code and validate a real dot-product identity.

## 3. Shared bases for six illuminations

For source a, let B_a and S_a denote the corresponding injection and receiver map. The same material vector s acts across sources. For independent source blocks,

\[
x_F^{(a)}=L^{-1}B_as_F,
\quad
y_F^{(a)}=L^{-*}S_a^*e_{F,c}^{(a)},
\]

\[
J_F^Te_F=\operatorname{Re}\sum_a B_a^*y_F^{(a)}.
\]

If a single spatial current basis is shared by six sources, protect the complete banks

\[
X_F=[x_F^{(1)},\ldots,x_F^{(6)}],
\qquad
Y_F=[y_F^{(1)},\ldots,y_F^{(6)}].
\]

The safe containment conditions hold source by source. Their numerical ranks may be below six, and exactly dependent columns may be removed after verifying the complete protected span. Summing the six currents into one spatial vector or retaining a random mixture does not preserve these conditions.

A single vector in a 6n-dimensional block-diagonal current space is mathematically legitimate, but it is not the same rank accounting as a single n-dimensional spatial basis shared by six sources. Log the actual backend convention. Apply the argument separately per frequency when L changes with frequency; a cross-frequency shared basis must contain all relevant banks.

## 4. Operator and state consistency

Use the conjugate transpose L^*, not L^T, in a complex Euclidean adjoint. Reciprocity or complex symmetry does not justify dropping conjugation. If quadrature or mass weights define the current inner product, whiten the coordinates or use the corresponding weighted adjoint throughout the projection, capture and dot-product tests.

Freeze the material coordinates and any scaling transform. If s=Tz, then J_z=J_s T, Lambda_z=T^T Lambda_s T, ell_z=T^T ell_s and the feasible set must be transformed consistently. Mixing coordinate systems changes both KKT and the H metric.

Freeze L, S, B, r, Lambda, ell and C across anatomy arms. In particular, B is the material injection at the same full state. For a nonlinear forward equation L(chi)j=b(chi), it typically contains Db[s]-DL[s]j. Replacing j by a reduced state in only some arms tests a different hypothesis.

If the true derivative includes a direct observation/material term outside SL^{-1}B, retain it identically in both models and include it in both GN targets. Do not silently drop it.

## 5. Required backend tests

For several real d and packed-real v, verify

\[
v^T(Jd)=d^T(J^Tv).
\]

Test both the full and each reduced implementation, plus its independently assembled small real Jacobian when feasible. For a Petrov core A=W^*LZ, the reduced adjoint must use

\[
R^*=W A^{-*}Z^*.
\]

An independently chosen backward surrogate is not the derivative of the forward reduced quadratic. The theorem requires the actual transpose of the same J_R.

Record primal and adjoint linear-solve backward errors; capture in a basis alone cannot repair an inaccurate oracle current. Also check the full constrained reference before treating its accepted nonlinear update as s_F.


---

# Petrov-Galerkin Task Interpolation and Its Stability Limits

## 1. Conditions and exact proof

Let Z,W in C^{n x k} have full column rank, let L be nonsingular, and assume

\[
A=W^*LZ\quad\text{is nonsingular}.
\]

Set R=ZA^{-1}W^*, and use the same R in forward and adjoint computations. With the real-material convention in the accompanying document, J_R is the packed-real representation of SRB.

If x_F=L^{-1}Bs_F lies in Range(Z), write x_F=Za. Then

\[
RBs_F=RLx_F=ZA^{-1}W^*LZa=Za=x_F.
\]

If y_F=L^{-*}S^*e_{F,c} lies in Range(W), write y_F=Wb. Since R^*=WA^{-*}Z^*,

\[
R^*S^*e_{F,c}=R^*L^*y_F
=WA^{-*}Z^*L^*Wb=Wb=y_F.
\]

Thus both GN interpolation conditions hold, including the real material pullback. With the same convex frozen quadratic, the exact constrained theorem applies. With multiple sources and a shared spatial basis, include each column of both banks.

No W^*Z=I hypothesis is required. It is W^*LZ that must be nonsingular. Rectangular trial/test pairs and pseudoinverses define different projections and are outside this formula unless separately analyzed.

## 2. Galerkin is already sufficient

When W=Z, a common basis containing both X_F and Y_F is sufficient. These containment conditions are not necessary: S may hide part of a primal current error, and Re(B^*.) may annihilate a dual current error.

Consequently, **test two-sided Galerkin before attributing the failure to Galerkin itself**. If common-Galerkin two-sided protection works, the missing mechanism was task information; it was not proof that common trial/test spaces are fundamentally invalid.

## 3. Dimension versus memory

For a single source, separate spaces can contain one primal and one dual vector with one column each, whereas a common space can require two columns. For six sources, the corresponding protected increments are at most six per side versus twelve in the common space, before overlap with retained U.

However, a k-column Petrov model stores two bases, often applies both forward and adjoint feedback streams, and can have a less stable core. Equal k is not equal memory or setup cost. Report k_Z, k_W, union rank, actual stored complex entries, setup operator actions and small-core factorization cost. Do not claim a rank-56 Petrov model is automatically cheaper than a rank-56 common Galerkin model.

## 4. Containment does not guarantee invertibility

Even with L=I, x=e_1, y=e_2, Z=e_1 and W=e_2 satisfy both current containments but W^*LZ=0. The reduced model is undefined. This is an algebraic stability counterexample, not a violation of the interpolation theorem, whose nonsingularity assumption fails.

Orthogonalize each basis internally before measuring core conditioning. The quantity sigma_min(W^*LZ) diagnoses an inf-sup loss for those spaces. Merely biorthogonalizing W and Z, or rescaling a singular value decomposition to make a small matrix look like the identity, does not eliminate the underlying projection amplification.

A silently regularized or pseudoinverted core changes R and may destroy exact interpolation. A stability fallback must be separately named, logged and re-tested for both interpolation targets. The common-Galerkin two-sided arm is the first useful control, not an assumed universally stable fallback for every nonnormal L.

## 5. Approximate current capture and projection amplification

Let Pi_Z=RL and Pi_W=R^*L^*. They are projectors onto the respective spaces. Then

\[
\delta_p=\mathcal P S(\Pi_Z-I)x_F,
\qquad
\delta_d=\operatorname{Re}B^*(\Pi_W-I)y_F.
\]

For Euclidean-compatible conventions,

\[
\|\delta_p\|\le\|S\|\|I-\Pi_Z\|\operatorname{dist}(x_F,\operatorname{Range}Z),
\]
\[
\|\delta_d\|\le\|B\|\|I-\Pi_W\|\operatorname{dist}(y_F,\operatorname{Range}W).
\]

Stack or sum with the declared source weights. Near-unit orthogonal capture can still be amplified by an unstable oblique projection. Therefore measure endpoint errors directly in addition to capture.

Equivalently, with x_R=RBs_F and y_R=R^*S^*e_{F,c}, define

\[
a_P=Bs_F-Lx_R,\qquad a_D=S^*e_{F,c}-L^*y_R.
\]

Then delta_p=-P S L^{-1}a_P and delta_d=-Re(B^*L^{-*}a_D). A small current residual without a stability factor is not a material certificate.

## 6. Relation to dual-weighted output error

Petrov orthogonality gives W^*a_P=0. Thus the scalar error along the goal e_F obeys

\[
e_F^T\delta_p=-\operatorname{Re}(y_F-y_R)^*a_P.
\]

This is the familiar primal/dual residual product structure. It controls one scalar pairing. The GN condition is stronger in a different way: it needs the complete material vector J_R^T e_F, not only a scalar data-fit pairing. A small scalar output error does not by itself establish an accurate minimizer.

## 7. Experimental interpretation

Common two-sided success with Petrov failure means task interpolation is supported but the split architecture has a stability or cost issue. Both success says splitting is permissible, not that it is more efficient. Exact primal/dual containment, stable cores and matched KKT data imply equality of the minimizers, regardless of errors in unrelated Jacobian columns.


---

# OPM as Task-Specific Primal/Dual Feedback

## 1. Retained-U elimination

Let U be orthonormal and A_U=U^*LU nonsingular. Define

\[
R_U=U A_U^{-1}U^*,\quad P_0=I-UU^*,
\quad T=(I-R_UL)P_0,\quad K=P_0(I-LR_U).
\]

On the omitted space W_0=Range(P_0), define

\[
A_s=P_0LT|_{W_0},\qquad F_s=I_{W_0}-A_s.
\]

With L nonsingular, the Schur complement A_s is nonsingular and

\[
L^{-1}=R_U+T A_s^{-1}K,
\qquad
L^{-*}=R_U^*+K^* A_s^{-*}T^*.
\]

This is exact retained-space elimination, not a Born truncation. It does not assume a Hermitian or contractive feedback operator.

## 2. Correct primal and dual omitted coordinates

For f=Bs_F and g=S^*e_{F,c},

\[
x_F=R_Uf+T\xi_F,
\quad \xi_F=A_s^{-1}Kf=P_0x_F,
\]
\[
y_F=R_U^*g+K^*\zeta_F,
\quad \zeta_F=A_s^{-*}T^*g=P_0y_F.
\]

Therefore the naturally paired seeds are

\[
\boxed{b_P=KBs_F,\qquad b_D=T^*S^*e_{F,c}.}
\]

The dual Schur seed uses T^*, not an arbitrary reuse of K. With nonstandard measurement whitening, replace S^*e_{F,c} by the exact adjoint forcing specified in the packing document.

Preserving KBs_F as an injection vector is not the same as preserving A_s^{-1}KBs_F or the full current x_F. The new exact-current primal oracle is a stricter test than the previous protected excitation. Its result can therefore change the causal diagnosis even before adding a dual oracle.

## 3. A split OPM representation

At a fixed existing feedback depth m (not a new degree sweep), form

\[
V=\operatorname{orth}\{F_s^j b_P^{(a)}:0\le j\le m,\ a=1,\ldots,N_s\},
\]
\[
Q=\operatorname{orth}\{(F_s^*)^j b_D^{(a)}:0\le j\le m,\ a=1,\ldots,N_s\}.
\]

Other existing state/background seeds may be retained. The key change is task conditioning and sidedness, not additional polynomial degree.

For V,Q in W_0, choose

\[
Z=[U,V],\qquad W=[U,Q],
\]

with equal total dimensions and a nonsingular core. Block elimination gives

\[
\boxed{R_{ZW}=R_U+T V(Q^*A_sV)^{-1}Q^*K.}
\]

The full-space span [U,V] contains T V because their difference lies in U, and similarly [U,Q] contains K^*Q. Hence protecting P_0X_F in V and P_0Y_F in Q is sufficient. The complementary full-current formulation and Schur formulation must agree numerically.

## 4. O/P/M interpretation

M identifies which real material perturbations inject current. O identifies which residual-weighted measurement directions must be pulled back to material. P is the internal feedback propagation needed on both sides.

Thus:

- M/P is a primal task hierarchy, driven by Bs.
- O/P is a dual task hierarchy, driven by the adjoint of the predicted post-step residual.

Generic receiver seeds may cover many possible goals, whereas e_F chooses the current GN goal. This is an explanation of the candidate mechanism, not evidence that residual-weighted seeds will remain accurate when e_F is replaced by an online estimate.

The frozen oracle uses s_F and e_F knowingly. An online algorithm must use its own provisional step and residual, and pay for independent physics information when required. Reapplying the same reduced inverse returns currents inside the existing basis and can produce a self-confirming, non-enriching loop.

## 5. Architecture constraints

Keep the forward and adjoint maps tied through the same Petrov core. Freeze Z and W throughout each quadratic solve. Rebuilding them while differentiating or solving without updating the model definition changes the objective.

Protect complete source blocks before filling remaining rank. Do not perform a post-QR truncation that discards a protected component. Rank 56 includes retained U unless the verified backend convention explicitly says otherwise; report both total and omitted ranks.

There is no claim that Petrov is automatically better than a common Galerkin space. The common-space two-sided arm is necessary to distinguish missing task directions from an intrinsically poor trial/test split.


---

# Closest-Prior Audit and Publication Judgment

## 1. Exact left/right interpolation is classical

**R1, Baur et al. (2011), Theorem 3.1:** right resolvent containment gives right tangential interpolation; left resolvent containment gives left tangential interpolation; paired conditions also support derivative interpolation. This directly precedes the Petrov current-containment proof. Their broader framework includes parameter-gradient and Hessian matching. A21 selects the right direction s_F and the left direction e_F because they form a constrained GN KKT condition. Do not present the containment identity itself as new.

## 2. Inverse-problem ROMs already preserve Jacobians

**R2, de Sturler et al. (2015):** interpolatory parametric ROMs reduce nonlinear inverse problems by preserving forward responses and Jacobian-related transfer information. The application is diffuse optical tomography. A21 is not the first ROM-based nonlinear inverse solver or the first derivative-aware inverse ROM. Its narrower target is one frozen optimum and its residual-weighted pullback, rather than uniform preservation of every Jacobian column across a parameter range.

## 3. Separate primal/dual spaces and optimization consistency

**R3, Keil et al. (2021):** adaptive trust-region reduced-basis optimization treats bilateral parameter constraints, non-conforming dual approximations, a posteriori errors and convergence. This is close prior for the role of valid constraints and dual consistency. A21's full-gap normal-work term and exact frozen quadratic are specific objects, not a replacement for their broader convergence analysis.

**R4, Keil and Ohlberger (2021):** the primal Petrov trial space is the dual test space, and vice versa. The paper explains why the reduced gradient is then the derivative of the actual reduced objective and explicitly notes stabilization issues. This is a particularly close precedent for the proposed architecture. A21 must therefore justify its Maxwell Schur-feedback realization and online cost, not advertise trial/test splitting alone.

## 4. Adaptive accuracy and gradient-based stopping already exist

**R5, Qian et al. (2017):** certified cost/gradient error bounds and adaptive high-fidelity updates are used in a reduced-basis trust-region method. First-order model consistency is an established optimization requirement. A21's proposed distinction is the explicit two-current realization of the frozen material KKT defect and the use of very few source-resolved task directions. The online computational advantage remains an empirical question.

## 5. The goal need not be scalar

**R6, Billaud-Friess et al. (2016):** goal-oriented projection already addresses vector-valued quantities of interest, distinguishes primal, test and dual approximation spaces, and studies saddle-point constructions. A21 must not claim novelty merely because the material pullback is a vector instead of a scalar objective. Its concrete goal is the constrained GN stationarity vector in the Maxwell inverse problem.

## 6. Not IRKA and not a new Krylov solver

**R7, Gugercin et al. (2008):** IRKA uses interpolation-based first-order conditions for H2-optimal dynamical-system approximation. A21 fixes a Maxwell state/frequency and targets material optimization directions. Its optimum is a GN material step, not an H2-optimal reduced dynamical system. Repeated task retargeting can resemble interpolatory iteration without inheriting IRKA optimality or convergence results.

## 7. Maxwell inverse ROMs are already a field

**R8, Borcea et al. (2024):** a data-driven time-domain Maxwell ROM interpolates measurements and supports imaging and quantitative inversion. Its construction and objective differ from a reduced current resolvent used inside a frozen regularized GN step. The distinction is methodological; 'first ROM for electromagnetic inverse scattering' would be false. Do not imply their experiments are full 3D vector benchmarks.

## 8. What is and is not an A21 contribution

The exact theorem is an elementary but useful corollary of convex optimality and classical tangential interpolation. The approximate bounds are standard strong-monotonicity consequences specialized to two explicit GN endpoint errors. The added value here is their consistent combination with real-material complex Maxwell currents, source-wise protection, constraint normals, and the retained-U Schur architecture.

A successful oracle is largely expected once the hypotheses are verified. It demonstrates that the implementation realizes the theorem and helps identify why the old primal-only representation failed. It does not demonstrate an online algorithm, speedup, improved truth reconstruction or broad low-rank compressibility.

A potentially strong paper would need a coherent additional chain:

1. Reproducible late-state anatomy separating primal excitation, dual pullback, curvature amplification and numerical error.
2. A non-oracle, task-conditioned primal/dual construction that works at the same affordable rank and cost.
3. Actual 3D nonlinear imaging evidence against common Galerkin, generic two-sided/goal-oriented ROM and full-reference baselines, with all setup and audit costs included.

A standalone theorem plus five oracle states is not yet a strong TAP paper in my assessment. It is a high-value mechanism decision and can form the backbone of a later imaging paper if the online and nonlinear evidence succeeds. This is a research assessment, not a publication guarantee.

## 9. Diagnosis without overclaiming

The supplied near-exact primal tangent and poor optimum are consistent with a dual/stationarity defect, but also with amplification of the residual primal term, a weak reduced Hessian, a tiny reference-step denominator, invalid constraint normals or a mismatched frozen objective. The experiment must measure these possibilities instead of declaring a new physical mechanism in advance.

If exact current protection makes the primal-only arm good, the previous injection oracle was not an adequate substitute for that current span. If two-sided Galerkin works but Petrov does not, keep the mechanism and reject or stabilize the split architecture. If a valid small solver-aware bound is contradicted, debug before interpreting the result physically.


---

# Minimal Oracle Anatomy: Frozen Five-State Protocol

## 0. Scope and authorization

Use only the five existing Gaussian late states from A20-R1. No new objects, noise sweep, nonlinear reconstruction, degree increase, NN training, full-solver redesign or current-selection study. The primary question is whether the current ROM preserves the two endpoints of the material GN KKT condition.

The user's reported rank is 56. Determine whether this means total current rank including retained U; preserve that actual definition and report both totals and complements. Do not assume the Gaussian parameter dimension, cache paths, source packing, solver type or trust radius from older documents.

## 1. Freeze a verified reference per state

Save immutable identifiers/checksums for the material state, L, source-specific B and S, r, Lambda, ell, C, coordinate scaling, source/frequency order, full real-packed J_F, full step s_F, full H_F and full-solver tolerances. Cache IDs and code commit belong in the manifest.

Check that the alleged s_F is the actual constrained frozen quadratic minimizer, not an accepted line-search increment alpha*s_F or a clipped unconstrained step. Reproduce full KKT with a valid normal. Keep LM damping, trust-region radius and constraint parameterization identical across all arms. A full-state B in one arm and a reduced-state B in another is not this experiment.

For normal recovery, validate feasibility and complementarity. For boxes use the signs given in `APPROXIMATE_ERROR_BOUND.md`; include trust-ball multipliers if present. Store rho_F explicitly. A missing cache or uncertain KKT convention is a blocker to resolve, not permission to replace the five states by synthetic data.

## 2. Stage T0 and backend convention checks

First run `validation/validate_two_sided.py` to verify the mathematics independently. Then validate one or two real cached states for real dot products, tied reduced adjoints, constrained-QP accuracy and source layout. Full-sized oracle solves must report their backward errors.

For a preliminary real-state code test, use the first, middle and last IDs in the frozen manifest, not states chosen after seeing new oracle outcomes. Reuse them when extending to all five. Do not select or drop a state based on the new H-step error.

## 3. One oracle bank per state, shared by every arm

Compute e_F=r+J_Fs_F in the declared real layout. Lift its adjoint forcing using the actual packing and whitening.

For every source a, solve

\[
L X_F^{(a)}=B_as_F,\qquad
L^*Y_F^{(a)}=S_a^*e_{F,c}^{(a)}
\]

or the exactly equivalent general-whitening version. Six sources cost six forward plus six adjoint current right-hand sides per state if these banks are not already cached. Reuse existing factorization/preconditioner and batch the right-hand sides. These are additional oracle costs, not zero-cost inputs.

Do not substitute KB_as_F for X_F^{(a)}. Protect the entire source bank or its retained-U complement. Do not sum or randomly mix the sources. Compute all source-wise and aggregate capture residuals.

## 4. Fixed rank and deterministic protected QR

For a common Galerkin arm, first include U, then every independent protected direction in source order, then fill remaining columns from the frozen baseline basis ordered by its pre-existing priority: earlier degree first, followed by stored column index. If no degree metadata exist, use the stored column order and disclose this fact.

Perform double reorthogonalization or a stable rank-revealing equivalent. Independent protected directions may never be discarded by a later top-k/SVD truncation. If U plus the protected bank exceeds rank 56, label `RANK_BUDGET_INFEASIBLE`; do not silently grow rank or truncate the oracle.

For Petrov arms apply the same rule independently to Z and W, with equal total dimensions. Report actual k_Z, k_W and union rank. A singular core is a failed architecture instance, not an available approximate inverse.

## 5. Primary arms: common Galerkin

| ID | Protected additions to a common Z=W | Purpose |
|---|---|---|
| BASE_G | none beyond the frozen baseline | Reproduce the original rank-matched baseline |
| PRIMAL_G | X_F | Exact-current primal-only test |
| DUAL_G | Y_F | Post-step dual-only test |
| BOTH_G | X_F and Y_F | Cleanest interpolation-mechanism test |
| RANDOM_G | independent random bank with the same added rank as BOTH_G | Rank/replacement control |

All have total rank 56 when feasible. The random bank uses a seed frozen before outcome inspection and the same protected-then-fill construction. Matching the number of independent protected additions is more precise than merely generating twelve nominal columns.

If the cached baseline used a Petrov fallback rather than Galerkin, preserve and name its actual projection in a separate reproduction check. Do not silently relabel it BASE_G. Record an unsafe BASE_G as such rather than changing its projection. The causal comparisons require stating which arms are genuinely common Galerkin.

## 6. Architecture arms: Petrov

| ID | Trial Z | Test W | Purpose |
|---|---|---|---|
| BOTH_PG | protect U and X_F | protect U and Y_F | Split-task architecture |
| RANDOM_PG | same number of independent random trial additions | same number of independent random test additions | Equal per-side-rank control |

Use k_Z=k_W=56. These seven arms require at most 35 reduced-QP evaluations across five states, excluding a necessary cached-fallback reproduction check. If the Galerkin theorem/control implementation is still failing, do not start the Petrov batch.

Petrov uses two bases. Equal per-side rank is not equal basis memory to Galerkin. Report both; this tiny experiment is not authorized to expand into a full rank/memory sweep.

## 7. Reduced model assembly

Form and factor A=W^*LZ without explicitly inverting it. For each source,

\[
\mathcal J_R^{(a)}=(S_aZ)A^{-1}(W^*B_a).
\]

Pack/whiten it identically to J_F. Its adjoint is the real transpose of this same matrix; operator code must agree with the factorization form R^*=W A^{-*}Z^*. Never use an independently assembled backward surrogate.

Solve the same constrained QP with the existing solver and a recorded tolerance. A post-solve feasibility projection is not a replacement for the constrained solve. Record rho_R and a valid n_R.

On unsafe cores, log sigma_min, norm, condition, factorization and solve residuals. Do not add a shift or use a pseudoinverse while retaining the exact-interpolation label. Any fallback is a separately named arm whose endpoint interpolation must be rechecked.

## 8. Required metrics

For every state and arm save the underlying vectors, not only scalar aggregates.

**Task endpoints**

- delta_p=(J_R-J_F)s_F; absolute norm and epsilon_P=||delta_p||/||J_Fs_F||.
- delta_d=(J_R-J_F)^T e_F; absolute norm and epsilon_D=||delta_d||/||J_F^T e_F||.
- J_R^T delta_p, its norm, eta_sum=delta_d+J_R^T delta_p, and a cancellation indicator.

Do not replace the material-vector dual error by a single scalar e_F^T delta_p.

**KKT and curvature**

- eta_direct=J_R^T(r+J_Rs_F)+Lambda*s_F+ell+n_F.
- rho_F and rho_R with validated normals.
- Identity residual eta_direct-rho_F-delta_d-J_R^T delta_p.
- An optional epsilon_KKT using the declared scale ||J_F^T e_F||+||Lambda*s_F||+||ell||+||n_F||. Never normalize by the full KKT sum, which is nearly zero.
- mu=lambda_min(H_R), lambda_min(Lambda), beta=lambda_max(H_F,H_R).
- b_solver=||rho_F+delta_d+J_R^T delta_p-rho_R||_{H_R^{-1}} and B_F=sqrt(beta)*b_solver.

Compute H_R and H_F in the same material coordinates and with the same regularizer. For the small existing material dimension, use a stable symmetric generalized eigensolve. If positive definiteness fails, label the norm bound inapplicable; do not add unregistered damping to make it pass.

**Material endpoints and gaps**

- Absolute ||s_R-s_F||_2, ||s_R-s_F||_{H_R}, ||s_R-s_F||_{H_F}.
- Relative epsilon_s=||s_R-s_F||_{H_F}/||s_F||_{H_F}, with numerator and denominator separately.
- q_R(s_F)-q_R(s_R), q_F(s_R)-q_F(s_F), and -n_F^T(s_R-s_F).
- Full predicted reduction q_F(0)-q_F(s_F), only if zero is feasible; otherwise use a declared common feasible baseline. Flag a near-zero denominator before normalizing the gap by predicted reduction.
- The solver-aware norm-bound ratio. Use the exact-reference gap formulas only when full KKT is resolved to the declared tolerance, or retain the rho_F term in the gap identity.

**Current and cost diagnostics**

- Per-source and aggregate orthogonal current-capture residuals for X_F and Y_F.
- Full primal/adjoint solve residuals; tied-adjoint dot-test error.
- k_Z, k_W, rank([Z,W]), retained rank, actual basis memory.
- Core singular values/condition, operator calls, full RHS counts, setup, QR, projection, QP and total time.

Ratios with numerically negligible denominators must be reported as undefined/ill-scaled, with absolute quantities retained. An arbitrary denominator floor may be used only for an additional clearly labeled display ratio, not to make a gate pass.

## 9. Reuse to keep the experiment tiny

Compute L times the baseline bank once. L X_F is already known from B s_F up to its solve residual. Common Galerkin protection of Y_F requires L Y_F, not L^*Y_F; apply L to that six-column block once and reuse it.

A shared raw bank D=[U,X_F,Y_F,baseline,random] and its operator image LD allow each protected orthogonal basis Z=D T_Z to reuse LZ=(LD)T_Z. Keep the coordinate transforms from QR. Do not rebuild the full Maxwell workspace or factorization for every arm.

Reusing an operator image via the exact equation is acceptable only with its measured solve residual included in the numerical error budget. Do not erase that residual by asserting an inexact oracle current solves the equation exactly.

## 10. Output and interpretation

Output a state-by-arm table, not only medians. Include explicit labels for unsupported norms, ill-scaled ratios, unsafe cores, budget failures and invalid references. Preserve the five-state manifest even when a state is blocked.

A successful BOTH_G together with failed PRIMAL_G and a large relevant dual contribution supports the missing-dual interpretation. A successful BOTH_PG adds architectural headroom only. Random controls, absolute scale and metric amplification determine how strong the causal claim is. See `GO_NO_GO_GATES.md` before reporting success.


---

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


---

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


---

# Codex Task: A21 Two-Sided GN Oracle Anatomy

## Mission

Implement and execute a tiny frozen-state mechanism test on the existing A20-R1 backend and its **five Gaussian late states**. Answer whether the missing reduced-GN ingredient is the post-step residual pullback, while separating current-response capture, curvature amplification, active constraints and projection stability.

This is not a request for a new theory search. The required derivations and exact experiment are in this package.

## Read first

Read, in this order:

1. `START_HERE.md` and `TWO_SIDED_GN_THEOREM.md`.
2. `APPROXIMATE_ERROR_BOUND.md` and `MAXWELL_PRIMAL_DUAL_INTERPRETATION.md`.
3. `PETROV_GALERKIN_TASK_INTERPOLATION.md` and `OPM_PRIMAL_DUAL_ARCHITECTURE.md`.
4. `ORACLE_ANATOMY_SPEC.md` and `GO_NO_GO_GATES.md`.
5. Existing repository entrypoints, A20/A20-R1 reports and the cached five-state manifest.

`ONLINE_ALGORITHM_CANDIDATES.md` is background only. Do not execute it now.

## Phase 0: Short backend map and immutable manifest

Locate the actual project/backend from the current working repository; do not invent module names or cache paths. Write `A21_BACKEND_MAPPING.md` identifying:

- full current solve and conjugate-adjoint solve, source batching and factorization reuse;
- injection B at the frozen state and measurement/whitening/real-packing maps;
- constrained QP solver, actual feasible set, LM regularizer and normal/multiplier convention;
- material coordinate scaling and exact H-step metric;
- retained U, baseline basis order/degree metadata, and any Petrov fallback;
- full-GN cached Jacobian, raw constrained step, active constraints and reference residual;
- the five immutable state IDs and relevant code/configuration hashes.

Verify that the cached step is the raw constrained minimizer, not alpha times it after line search. If it is not, reconstruct/re-solve that same frozen QP with the existing trusted solver and record the difference. If the required data cannot be identified, report the specific blocker; do not fabricate five replacement states.

Plan Mode is appropriate only for resolving this map and the shared-cache implementation. Do not redesign the experiment.

## Phase 1: Synthetic and backend consistency tests

Run the supplied standalone validation. Add backend unit tests for real-material dot products, true complex conjugation, same reduced forward/adjoint core, source ordering, parameter scaling and valid constraint normals.

Use the first/middle/last IDs of the frozen manifest for real code validation as needed. Reuse their computations later. Verify primal and adjoint oracle solve residuals, current captures and square-core stability. No nonlinear imaging may start as part of these checks.

## Phase 2: Cache exact task currents once

For each state compute e_F=r+J_Fs_F and the six-source banks

    X_F[a] = solve(L, B[a] @ s_F)
    Y_F[a] = solve(L.conj().T, measurement_adjoint(e_F)[a])

Use the actual real-packing/whitening adjoint, not a guessed unstacking operation. Cache the complete banks. The primal oracle protects X_F, not merely K B s_F. Record all additional full RHS and operator actions.

## Phase 3: Rank-56 common-space controls

Construct BASE_G, PRIMAL_G, DUAL_G, BOTH_G and RANDOM_G exactly as specified. Protect U first, all independent oracle source columns second, and fill from the frozen baseline priority order. Never remove a protected direction later. Replace low-priority/latest-degree fillers deterministically; never choose deletions by observing H-step error.

If the existing baseline is Petrov, add a correctly named reproduction check rather than relabeling it as Galerkin. Unsafe cores or insufficient protected-rank budget are explicit statuses, not permission for silent method changes.

Assemble J_R through small solves, pack it consistently, and solve the same constrained QP. Save reference and reduced normals and their residuals. Do not substitute unconstrained solve plus clipping.

## Phase 4: Two Petrov architecture controls

Only after Phase 3 is mathematically consistent, run BOTH_PG and RANDOM_PG. Use equal trial/test total rank 56 and the actual conjugate-adjoint core. Protect X_F only on the trial side and Y_F only on the test side in BOTH_PG. No pseudoinverse or hidden core shift is allowed under an exact-interpolation label.

This is at most 35 arm-state reduced QPs, plus a necessary original-fallback reproduction check. Share X/Y banks, operator images and setup across arms.

## Mandatory output quantities

Implement all metrics in `ORACLE_ANATOMY_SPEC.md`, especially these often-missed items:

    delta_p = (J_R-J_F) @ s_F
    delta_d = (J_R-J_F).T @ (r+J_F@s_F)
    eta_direct = J_R.T@(r+J_R@s_F) + Lambda@s_F + ell + n_F
    identity_error = eta_direct - rho_F - delta_d - J_R.T@delta_p
    rho_R = J_R.T@(r+J_R@s_R) + Lambda@s_R + ell + n_R
    eta_pair = rho_F + delta_d + J_R.T@delta_p - rho_R
    b_R = sqrt(eta_pair.T @ solve(H_R,eta_pair))
    beta = largest_symmetric_generalized_eigenvalue(H_F,H_R)
    bound_HF = sqrt(beta) * b_R

All these matrices/vectors are in the same **real material coordinates**. Symmetry and positive definiteness must be checked rather than assumed. Core conditioning and material-Hessian conditioning are different metrics; report both.

Report absolute and relative endpoint errors, ||s_F||_HF, actual H-step error, q_R gap, q_F gap, normal work, predicted reduction, current capture, ranks/union rank/memory, core condition and complete timing/action counts. A tiny denominator is a flag, not a pass.

Do not call small epsilon_P and epsilon_D plus a large step a bug unless the correctly scaled solver-aware bound is also contradicted. See the explicit conditioning counterexample.

## Reuse requirements

Reuse L factorization/preconditioner and multi-RHS operations. Reuse baseline operator images. Compute L times dual oracle columns only once when needed by common Galerkin. Preserve QR coordinate transforms to assemble projected cores from a shared raw bank. Avoid rebuilding a complete Maxwell workspace per arm.

Small-core algebra and diagnostic material matrices should use double precision where available. Record actual precision of full oracle solves and do not promise a double-precision interpolation tolerance from a single-precision current solve.

## Deliverables

Write under the project's new A21 results directory, without overwriting A20 references:

- `A21_BACKEND_MAPPING.md`
- `A21_FROZEN_MANIFEST.json`
- `A21_ORACLE_REPORT.md`
- `A21_METRICS.csv` and complete per-state JSON records
- cached oracle currents and diagnostic vectors with provenance
- tests, runnable experiment entrypoint, exact command and environment/commit information

The report must start with T0/T1 status, followed by the per-state table and an explicit answer to whether dual defect, amplified primal defect, conditioning, active constraints, tiny denominators or model inconsistency explain each failure. Include negative/blocked states. Distinguish mechanism confirmation from a Petrov advantage.

## Stop conditions

Stop and debug on invalid full KKT, failed dot products, inconsistent frozen data or a true solver-aware inequality violation. Stop and report a representation limitation on irrecoverable rank/core failure. Stop after the five-state anatomy and report; do not automatically launch online refinement, larger ranks, deeper feedback, nonlinear imaging, new datasets, NN, PCG or GMRES experiments.


---

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


---

# Primary Sources and Access Scope

The audit was checked against public primary sources during this response. These sources establish prior art; the new algebraic derivations and synthetic tests are identified separately. This is a targeted closest-prior audit, not a claim to have exhausted every publication.

**R1.** U. Baur, C. Beattie, P. Benner, S. Gugercin. *Interpolatory Projection Methods for Parameterized Model Reduction*. SIAM Journal on Scientific Computing 33(5), 2489-2518 (2011). DOI: 10.1137/090776925. Primary manuscript: https://vtechworks.lib.vt.edu/bitstream/handle/10919/48155/090776925.pdf . Access: full manuscript; Theorem 3.1 on printed pages 2493-2494 visually checked, with parameter-derivative interpolation context.

**R2.** E. de Sturler, S. Gugercin, M. E. Kilmer, S. Chaturantabut, C. Beattie, M. O'Connell. *Nonlinear Parametric Inversion Using Interpolatory Model Reduction*. SIAM Journal on Scientific Computing (2015). DOI: 10.1137/130946320. https://arxiv.org/abs/1311.0922 ; full HTML https://arxiv.org/html/1311.0922 . Access: full-text sections on inverse-problem transfer functions, Jacobian preservation and projection conditions.

**R3.** T. Keil, L. Mechelli, M. Ohlberger, F. Schindler, S. Volkwein. *A non-conforming dual approach for adaptive Trust-Region reduced basis approximation of PDE-constrained parameter optimization*. ESAIM: M2AN 55(3), 1239-1269 (2021). DOI: 10.1051/m2an/2021019. https://www.numdam.org/articles/10.1051/m2an/2021019/ ; https://arxiv.org/html/2006.09297 . Access: full-text theory and overview, including bilateral constraints and separate primal/dual spaces.

**R4.** T. Keil, M. Ohlberger. *Model Reduction for Large Scale Systems*. 2021 preprint. https://arxiv.org/abs/2105.01433 ; https://arxiv.org/html/2105.01433 . Access: full text, especially Section 2 equations (7)-(9) and the discussion of Petrov stability. This is one of the closest architectural precedents.

**R5.** E. Qian, M. Grepl, K. Veroy, K. Willcox. *A Certified Trust Region Reduced Basis Approach to PDE-Constrained Optimization*. SIAM Journal on Scientific Computing 39(5), S434-S460 (2017). DOI: 10.1137/16M1081981. Primary author manuscript: https://kiwi.oden.utexas.edu/papers/multifidelity-optimization-adaptive-reduced-model-qian-grepl-veroy-willcox.pdf . Also archived at https://dspace.mit.edu/bitstream/handle/1721.1/116912/16m1081981.pdf?sequence=1 . Access: abstract and indexed primary-text passages on cost/gradient error bounds, adaptive high-fidelity updates and first-order consistency; no claim of a complete proof-by-proof audit.

**R6.** M. Billaud-Friess, A. Nouy, O. Zahm. *Projection based model order reduction methods for the estimation of vector-valued variables of interest*. 2016 preprint. https://arxiv.org/abs/1603.00336 ; https://arxiv.org/html/1603.00336 . Access: full text on vector-valued goals, primal/test/dual spaces and saddle-point formulations.

**R7.** S. Gugercin, A. C. Antoulas, C. Beattie. *H2 Model Reduction for Large-Scale Linear Dynamical Systems*. SIAM Journal on Matrix Analysis and Applications 30(2), 609-638 (2008). DOI: 10.1137/060666123. https://vtechworks.lib.vt.edu/bitstream/10919/48145/1/060666123.pdf . Access: primary manuscript indexed text, interpolation optimality conditions and iterative rational Krylov description.

**R8.** L. Borcea, Y. Liu, J. Zimmerling. *Electromagnetic inverse wave scattering in anisotropic media via reduced order modeling*. Journal of Computational Physics (2024). https://arxiv.org/abs/2403.03844 ; https://arxiv.org/html/2403.03844 ; publisher record https://www.sciencedirect.com/science/article/pii/S0021999124005205 . Access: full-text Maxwell/data-driven ROM formulation and scope. The method applies in principle to 3D; the reported setup is reduced to two dimensions using an orthotropic cylindrical configuration. It is not the same frozen GN current-ROM construction as A21.
