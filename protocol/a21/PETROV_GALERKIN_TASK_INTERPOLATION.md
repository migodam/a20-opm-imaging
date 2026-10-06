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
