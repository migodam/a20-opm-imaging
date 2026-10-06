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
