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
