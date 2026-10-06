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
