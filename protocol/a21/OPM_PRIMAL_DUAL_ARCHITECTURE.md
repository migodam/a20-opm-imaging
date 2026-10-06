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
