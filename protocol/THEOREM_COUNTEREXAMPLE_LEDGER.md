# Theorem and counterexample ledger

Every equality assumes the dimensions, real/complex conventions, and invertibility conditions in the detailed files. A synthetic test supports implementation consistency; the proof supplies the mathematical claim. Neither is a completed 3D imaging result.

| ID | Statement | Status and required assumptions |
|---|---|---|
| T1 | Exact retained-space Schur resolvent | Proved by block elimination; full L and U*LU invertible. |
| T2 | Galerkin resolvent equals the Schur-projected formula | Exact with Q in range(I-UU*) and invertible reduced core. |
| T3 | Mixed right/left chains match tangential moments 0 through p+q+1 | Proved; endpoint span inclusions exact; classical two-sided mechanism. No z=1 error guarantee. |
| T4 | J-J_Q=E_O* A^-1 E_M | Exact Galerkin dual-residual identity at fixed state and injection. |
| T5 | ||J-J_Q|| bounded by dual residual x resolvent stability x primal residual | Immediate from T4; a computable certificate needs a justified stability bound, not eigenvalues alone. |
| T6 | GN perturbation formula and relative H bounds | Realified J; positive definite H; same local regularizer; include residual changes where present. |
| T7 | Full stationarity defect gives exact unconstrained H-step error and quadratic gap | q=H s_m+g, s_F=-H^-1g. Quantities involving H^-1 need solves or justified bounds. |
| T8 | Common-convex-constraint KKT defect gives step and gap bounds | Use a valid normal-cone multiplier; post-clipping is not an exact constrained solve. |
| T9 | Adjacent-degree step-change identity | Fixed state, residual, metric and regularizer; exact D=J_{m+1}-J_m. |
| T10 | Saturation-based tail bound | CONDITIONAL on a uniform geometric bound for all later innovations in a common norm and correct full limit. Not inferred from two observed ratios. |
| T11 | Local nonlinear reconstruction difference | CONDITIONAL on same-basin strong convexity and uniform gradient approximation; not global truth recovery. |
| T12 | Frozen linear estimator bias-variance formula | Exact for a fixed linear estimator and specified noise; adaptive data-dependent basis adds dependence. |
| T13 | Weak-prior linear leakage bound | Requires full restricted Jacobian defect bound on the selected entire weak space. |
| T14 | Weak-prior finite-step data bound | T13 plus a Jacobian Lipschitz constant over the correction segment; otherwise use full forward validation. |
| T15 | Gauge-safe latent and material pullback | Algebraic equivariance under unitary current-basis changes; seed provenance and scaling remain declared. |

## Counterexamples that change implementation decisions

### C1. Low-rank global inverse approximation need not converge in norm

Take L=I and R=Q Q* with rank(Q)<n. Then ||L^-1-R||=1, even when every requested endpoint is represented exactly. More generally rank(R)<n implies ||L^-1-R|| >= 1/||L||. Use task-restricted error, not a global small-rank inverse norm objective.

### C2. Low-degree plateau can miss a delayed path

Let F be a 7-by-7 lower shift with subdiagonal 0.8. Input is e_1 and receiver is e_7*. Include forward material and adjoint receiver chains through degree m. Degrees 0,1,2 give transfer zero; degree 3 spans the space and gives 0.8^6=0.262144. With scalar material residual -1 and regularization 0.1, the update changes from zero to about 1.553727. Adjacent stability is not a certificate.

### C3. Spectral radius misses nonnormal amplification

F=[[0,100],[0,0]] has spectral radius zero, but ||(I-F)^-1|| is approximately 100.01. Eigenvalue-based confidence in degree or residual bounds is insufficient. Here the Neumann series terminates, yet an early truncation can still be very inaccurate.

### C4. Invertible full L can have a singular Galerkin core

L=[[0,1],[-1,0]] is invertible, but Q=e_1 gives Q*LQ=0. Monitor reduced-core stability and use an explicitly defined stable projection/fallback. Do not silently replace a failed inverse with a pseudo-inverse and retain the same theorems.

### C5. Reduced weak directions can be completely fake

J_full=I_2 and J_low=diag(1,0). The second coordinate is invisible to J_low but fully observed by J_full. A neural correction there can change data by its full amplitude. Audit the proposed weak span against full physics.

### C6. More accurate scalar Jacobians do not imply monotonically increasing variance

For fixed ridge lambda, the estimator from scalar a is a/(a^2+lambda); its variance is sigma^2 a^2/(a^2+lambda)^2. This peaks at |a|=sqrt(lambda), then decreases. Degree is not automatically a bias-down/variance-up regularization path.

### C7. Moving reduced bases invalidate a frozen-basis tangent

The supplied finite-difference experiment differentiates a reduced state with Q(x). Ignoring Q'(x) produces roughly 0.36 relative derivative error in this example, while the correctly frozen-basis tangent agrees near 6e-10. Freeze the basis within the model or account for its derivative.

### C8. Projection after a weak correction is not weak-space preserving

A coordinate-wise material clipping map generally does not commute with P_weak. Enforce feasibility in weak coordinates, not by post-clipping a projected neural output.

### C9. Joint orthogonalization does not preserve semantic column labels

If O and M seeds overlap, QR can combine or deflate them. Arbitrary unitary rotations of Q leave the physical model unchanged but change flattened coefficients. Store provenance and use invariant/equivariant features.

## Unresolved empirical questions, not unproved identities

Does mixed OPM outperform a fair generic ROM in final 3D imaging? Is a useful degree reached before setup/audit costs dominate? Are full-physics weak directions prevalent in the intended material parameterization? Is residual anatomy stable across independent objects? Does the neural graph outperform a linear head? These require the staged backend experiments, not more claims from the synthetic algebra tests.
