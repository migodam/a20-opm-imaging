# OPM imaging theory: definitions, exact bridges, and limits

Status: original derivations in this memo, with their classical antecedents identified in NOVELTY_AUDIT.md. Finite-dimensional checks are supplied; no claim of a completed Maxwell imaging experiment is made. The user's A17/A18/A19 observations are accepted as supplied project background, not independently re-measured.

## 1. Conventions and the nonlinear problem

Let x be a REAL material parameter vector, including separate real and imaginary contrast coordinates where necessary. For each frequency and illumination, write

    L(x) j(x) = b(x),       y(x) = S j(x),
    L = I - F,             F = X(x) G_D.

For the usual contrast-current convention, b = X e_inc. Differentiation gives

    B(x)d = b'(x)d - [L'(x)d]j(x)
           = [X'(x)d](e_inc + G_D j(x)),
    J_c d = S L^{-1} B d.

An x-dependent S contributes S'(x)d j and must not be silently omitted. This project initially fixes geometry and S. Stack all sources/frequencies and whiten by the measurement-noise covariance. Set

    J = [Re J_c; Im J_c],  r = [Re(y-y_obs); Im(y-y_obs)].

All subsequent GN transposes are REAL transposes. In complex notation their material pullbacks are Re(J_c^*v), not unconstrained complex parameter updates. Current-space adjoints remain complex conjugate transposes. Use the backend's mass-weighted current metric, or transform it to Euclidean coordinates before QR.

The target is

    minimize Phi(x) = 0.5 ||r(x)||^2 + R(x),  x in C.

Use a positive definite local regularization/LM metric Lambda and gradient ell. Bounds requiring lambda > 0 refer to Lambda >= lambda I in scaled real material coordinates. An indefinite regularizer Hessian cannot be inserted into these results unchanged.

## 2. Exact retained-space Schur feedback

Choose an orthonormal retained basis U. Require A_U = U^* L U invertible. Define

    R_U = U A_U^{-1} U^*,   P = I-UU^*.

All operators below act on W = range(P); I_W is the identity on W, NOT the full identity. Define

    T = (I-R_U L)|_W,
    K = P(I-LR_U),
    A = P L T|_W = I_W-F_eff,
    F_eff = P F P + P F U (I-U^* F U)^{-1} U^* F P.

Then the exact identities are

    L^{-1} = R_U + T A^{-1} K,
    J_c = J_U + C A^{-1} N,
    J_U = S R_U B,   C = S T,   N = K B.

Proof: solve the U block of L(Ua+w)=b for a, substitute into the W block, and back-substitute. No Hermitian, normality, contraction or Born-series assumption is needed. Singular L or singular A_U is outside this construction. A poorly chosen U may make A_U nearly singular even when the full L is well-conditioned; monitor absolute scaled sigma_min as well as condition numbers. An empty U is a valid fallback and gives F_eff=F.

F_eff describes an excursion in W with any retained-U feedback already eliminated. One application is NOT exactly one elementary physical scattering event. U feedback has already been resummed.

## 3. Physics seeds, not oracle current directions

Choose a fixed material scaling T_x, so x=x_ref+T_x z. Let Omega_z and Omega_y be low-rank probe banks independent of test truth.

    M seeds: B_M = N T_x Omega_z.
    O seeds: B_O = C^* Omega_y.
    P seeds: B_P = K b, or a block of retained-model state residuals.

For multiple sources, concatenate the individual physical RHS blocks before compression. Include a measured-residual direction in Omega_y and previous accepted material steps among material probes where useful, but also keep independent exploration probes. Seed rank, source count and current rank must all be reported. Using every material/receiver column may saturate the whole current space at degree zero; it is not evidence for a shallow representation.

P seeds protect state/illumination response. M seeds protect derivative injection. O seeds protect adjoint receiver return. Their subspaces may overlap; O/P/M is provenance, not a canonical direct-sum decomposition.

For m >= 0 define the MIXED hierarchy

    V_m = span {F_eff^j [B_P,B_M] : j=0,...,m},
    W_m = span {(F_eff^*)^j B_O : j=0,...,m},
    Q_m = orth(V_m + W_m).

A forward-only K_m(F_eff,[B_O,B_P,B_M]) is a legitimate ablation, but it does not provide the two-sided moment statement below. Maintain separate right and left Arnoldi streams before joint orthogonalization. Projecting a right stream against arbitrary left-stream vectors, then propagating only that projected right remainder, can lose the intended pure powers. Do not accidentally replace this hierarchy by all noncommutative words in F_eff and F_eff^*.

## 4. Reduced engine and a useful explanation of shallow degree

Let Z_m=orth[U,Q_m] in the original current coordinates. Equivalently,

    R_m = Z_m (Z_m^* L Z_m)^{-1} Z_m^*
        = R_U + T Q_m (Q_m^* A Q_m)^{-1} Q_m^* K.

Define H_f = Q_m^* F_eff Q_m, to distinguish it from a material GN Hessian. The correction is C Q_m(I-H_f)^{-1}Q_m^*N.

This is a small projected resolvent, NOT the truncated Neumann sum I+F+...+F^m. A shallow basis may still represent repeated loops within its reduced core. The basis-construction degree and the actual multiple-scattering order of the resulting rational transfer model are different concepts.

### Proposition 1: tangential two-sided moment matching

Let B_s=N T_x Omega_z and C_s=Omega_y^* C. Suppose Q contains F_eff^j B_s for j=0,...,p and (F_eff^*)^j C_s^* for j=0,...,q. Put H_f=Q^*F_eff Q. Then

    C_s F_eff^k B_s = C_s Q H_f^k Q^* B_s,
    k=0,...,p+q+1.

Proof: right inclusion gives F_eff^j B_s=Q H_f^j Q^*B_s through j=p; left inclusion gives C_s F_eff^i=C_s Q H_f^i Q^* through i=q. For k<=p+q split into those two powers. For k=p+q+1 place one F_eff between them and use Q^*F_eff Q=H_f. Smaller k follow by the corresponding split.

Consequently C_s(I-z F_eff)^{-1}B_s and its projected transfer function have equal Taylor coefficients at z=0 through degree p+q+1. For p=q=2, moments 0,...,5 match. This is a classical two-sided projection mechanism, not a new universal moment-matching theorem. Here its role is to explain why material injection and receiver return both matter.

Important qualifications: these are SKETCHED/tangential moments unless all endpoint columns are included. The expansion is local in z; equality of a few coefficients does not bound the error at z=1 near resonance or under nonnormal transient amplification. z is a formal feedback-strength variable with frozen endpoints, not automatically a physical frequency or contrast continuation.

### Proposition 2: exact two-sided residual identity

For fixed Q, set A_Q=Q^* A Q and

    X_Q = Q A_Q^{-1} Q^* N,
    Z_Q = Q A_Q^{-*} Q^* C^*,
    E_M = N-A X_Q,
    E_O = C^*-A^* Z_Q.

Then

    J_c-J_{c,Q} = E_O^* A^{-1} E_M,
    ||J_c-J_{c,Q}|| <= ||E_O|| ||A^{-1}|| ||E_M||.

Proof: the error equals C A^{-1}E_M. Since C=Z_Q^* A+E_O^* and Q^*E_M=0, the Z_Q term vanishes. The result is the input-output analogue of a primal/dual residual estimate. Restricted versions replace N and C by material and measurement probe blocks. A random-probe estimate is not an operator-norm certificate.

This PRODUCT gives a more precise explanation than 'orthogonality improves physics': simultaneous control of injection residual and return residual can improve the task error even when the entire current field is not accurate.

## 5. Why full-operator norm is the wrong primary target

If rank(R_m)<n, a unit vector v exists in ker(R_m). Thus

    ||L^{-1}-R_m|| >= ||L^{-1}v|| >= 1/||L||.

For L=I and a proper projection R_m, the error is exactly one, although S R_m B may equal S B exactly on selected endpoints. Prefer ||S(L^{-1}-R_m)B T_x||, its task-restricted version, or directly the GN stationarity defect. A theorem about ||L^{-1}-R_m|| going to zero uniformly at very small rank cannot be true in general.

## 6. The state/Jacobian consistency issue

A frozen-state approximate tangent is J_m=S R_m B(j_full). This is suitable as an INEXACT tangent for the full objective. It is not generally the derivative of a reduced forward map with approximate state.

For a fixed Z during the local solve, define

    j_m(x) = Z[Z^*L(x)Z]^{-1}Z^*b(x).

Its exact derivative is

    D y_m(x)d = S R_m B(j_m)d.

The difference from the full tangent splits as

    J_full - D y_m
    = S(L^{-1}-R_m)B(j_full)
      + S R_m [B(j_full)-B(j_m)].

If ||B(j)-B(j_m)|| <= c_B ||j-j_m||, the second term is bounded by ||S R_m||c_B||j-j_m||. It must not be silently dropped.

If Z=Z(x) is rebuilt inside the evaluated forward map, additional basis-derivative terms appear. Either freeze U/Q within a trust-region/line-search trial, explicitly differentiate them, or use a full-objective inexact model with appropriate acceptance. Do not stop-gradient through a moving basis and call the resulting map's derivative exact.

## 7. Link to a final nonlinear reconstruction

The GN results in ADAPTIVE_DEGREE_THEORY.md concern a frozen quadratic. A local reconstruction statement requires additional assumptions. If the full regularized nonlinear objective is mu-strongly convex on a convex neighborhood containing both a full solution x_F and a reduced stationary point x_m, and

    ||grad Phi_full(x_m)-grad Phi_reduced(x_m)|| <= delta_g,
    ||grad Phi_reduced(x_m)|| <= epsilon_opt,

then

    ||x_m-x_F|| <= (delta_g+epsilon_opt)/mu.

Proof: strong monotonicity of grad Phi_full, with grad Phi_full(x_F)=0. The variational-inequality version covers a common convex feasible set. This is a LOCAL, same-basin, identifiable/stable-neighborhood statement. It is not guaranteed by small GN error alone. Finally,

    ||x_m-x_truth|| <= ||x_m-x_F|| + ||x_F-x_truth||.

The final term contains regularization bias, noise, non-identifiability and model mismatch; OPM approximation cannot eliminate it by algebra alone. This distinction motivates a separate neural PRIOR rather than relabeling all reduced-model error as uncertainty.
