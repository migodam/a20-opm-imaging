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
