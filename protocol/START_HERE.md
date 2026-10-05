# OPM-native full-wave imaging: research and implementation package

Date: 2026-10-05
Scope: material reconstruction with a task-conditioned two-sided Schur-feedback representation. No current selector/exchange work; no revival of a learned full Maxwell inverse.

## Executive decision

**Proceed immediately with deterministic OPM imaging and its material-fidelity audit. Keep the neural prior conditional.** OPM is best defined as a local, endpoint-conditioned block Krylov transfer representation, not as Chebyshev/Legendre spatial polynomials and not merely as a current proposal bank.

The central explanatory bridge is two-sided: forward material/P chains and adjoint receiver chains can match more transfer moments than either alone, and the Jacobian defect factors into primal residual, feedback inverse, and dual residual. This motivates a reduced imaging model, but does not prove shallow degree universally works or that its total cost is favorable.

## Evidence status

The supplied task brief reports A18-C development current-opportunity coverage of approximately 0.892/0.966/0.993 for degrees 0/1/2, A19 localization limits, and A18-B deployment failure. These are accepted project inputs; this package did not independently rerun those repositories.

This package contains derived identities, explicit assumptions, primary-source literature comparisons, synthetic numerical checks and counterexamples, and a backend experiment protocol. The included NumPy tests ran successfully. **No new 3D Maxwell nonlinear imaging experiment or neural training result is claimed.**

## Three mature routes

| Route | Actual output | Priority | Main gate |
|---|---|---|---|
| Primary: deterministic OPM-GN/DBIM | A coherent reduced forward/Jacobian/material update with full-objective globalization | Run now | Final imaging quality and total cost versus full GN and fair generic ROMs |
| Secondary: adaptive Arnoldi/feedback approximation | Degree selected using material step fidelity, not current residual alone | Integrate after the basic engine works | Same imaging quality at lower cost, including audits/fallbacks |
| Neural: physics-audited weak-coordinate prior | A small learned quadratic prior/proximal correction, not a full solver or free image network | Blocked on error/weak-space gates | Independent-object truth benefit versus deterministic and linear baselines |

The optional O/P/M x degree graph is an architecture pilot within the third route. The first two routes likely belong in the same paper.

## What to read

For theory, read OPM_IMAGING_THEORY.md, then ADAPTIVE_DEGREE_THEORY.md. For implementation, read OPM_GN_DBIM_ALGORITHM.md and OPM_RESOLVENT_APPROXIMATION.md. For learning, read OPM_REGULARIZATION_THEORY.md, OPM_NEURAL_PRIOR.md, OPM_PHYSICS_LATENT_REPRESENTATION.md and OPM_NN_ARCHITECTURE.md.

NOVELTY_AUDIT.md and REFERENCES.md distinguish established tools from the proposed contribution. THEOREM_COUNTEREXAMPLE_LEDGER.md records what cannot safely be inferred. LIGHTWEIGHT_EXPERIMENT_SPEC.md and GO_NO_GO_GATES.md define staged tests for the existing RTX 4060 workflow.

VALIDATION_REPORT.md summarizes the actual synthetic results. experiments/check_theory.py reproduces them with NumPy. COMPLETE_RESEARCH_MEMO.md concatenates the research documents for single-file reading; the separate files are the authoritative editing units.

## Eleven requested decisions

| Question | Decision |
|---|---|
| 1. What is OPM mathematically? | A state-dependent, task-endpoint-conditioned mixed forward/adjoint Schur-feedback block Krylov hierarchy and its projected transfer model. |
| 2. Should it remain a current proposal basis? | No. Current-valued internal coordinates can serve forward, tangent, adjoint and material imaging directly. |
| 3. Can it define a reduced imaging engine? | Yes, algebraically. A coherent frozen-basis model and nonlinear globalization are specified; practical imaging/cost still require tests. |
| 4. Can it define an iterative approximation? | Yes: classical block projection/resolvent machinery with a proposed material-fidelity degree controller. Do not claim new generic Arnoldi mathematics. |
| 5. Is degree an inverse regularization hierarchy? | Only conditionally and empirically; no universal monotone bias/variance law. Use calibrated risk/shrinkage if supported. |
| 6. Can O/P/M x degree be a physical latent? | Yes as a gauge-aware local transfer state; not a sufficient statistic or posterior by itself. |
| 7. Most natural NN prior? | A positive definite, OPM-conditioned small quadratic prior restricted to a full-physics-audited weak material span. |
| 8. What should NN compensate? | Prefer regularizer/proximal coefficients. Separate numerical image compensation from missing-data prior; do not learn the full coefficient dynamics/resolvent now. |
| 9. Strongest paper path? | Deterministic two-sided feedback reduction plus inverse-update fidelity and end-to-end 3D imaging evidence. Neural work is optional and separate. |
| 10. What goes to Codex now? | Task A immediately; task C after its adapter/replay; task B begins only with diagnostics after the required gates. |
| 11. What kills the program? | Correct, fairly budgeted OPM is dominated by generic ROMs or needs near-full rank/full fallback cost, and its apparent gains disappear under consistent derivatives and independent objects. |

## Codex handoff

CODEX_ROUTE_A_OPM_IMAGING.md is the first assignment. Use a short planning pass to map the actual local backend and lock the comparison protocol, then implement and run G0/replay. Do not let a planning pass turn into another broad literature task.

CODEX_ROUTE_C_ITERATIVE_POLYNOMIAL.md extends the same engine with audited degree adaptation. CODEX_ROUTE_B_OPM_NN_PRIOR.md is explicitly gated; it should not trigger training merely because it is present in the directory.

## Strongest equations to retain

    L^{-1} = R_U + T(I-F_eff)^{-1}K
    J = J_U + C(I-F_eff)^{-1}N
    J-J_Q = E_O^*(I-F_eff)^{-1}E_M
    q_m = H s_m + g
    ||s_m-s_F||_H = ||q_m||_{H^{-1}}
    Phi_quad(s_m)-Phi_quad(s_F) = 0.5||q_m||_{H^{-1}}^2

The last two are exact for the unconstrained frozen quadratic. Use the stated inequalities and KKT residual for a constrained subproblem. They do not equate quadratic quality with final truth error.

## Do not lose these safeguards

Freeze bases within a conditional model or differentiate their dependence. Include reduced-state error in B. Do not turn adjacent-degree stability into a certificate. Do not turn low approximate eigenvalues into a physical nullspace. Count full audit solves. Do not label a projected resolvent as a truncated Born polynomial. Do not infer imaging accuracy from current-opportunity coverage.
