# Codex task A: deterministic OPM imaging (RUN FIRST)

## Objective and scope

Implement and test a reduced full-wave MATERIAL reconstruction engine using the existing 3D vector-Maxwell backend. Do not implement current selection, current exchange, candidate ranking, a new PCG method, or a neural Maxwell surrogate. Preserve A17/A18/A19 originals and references. Work in a new isolated directory/branch and record its commit.

Read in this order:

1. START_HERE.md
2. OPM_IMAGING_THEORY.md
3. OPM_GN_DBIM_ALGORITHM.md
4. OPM_RESOLVENT_APPROXIMATION.md
5. THEOREM_COUNTEREXAMPLE_LEDGER.md
6. LIGHTWEIGHT_EXPERIMENT_SPEC.md and GO_NO_GO_GATES.md

The supplied brief is historical context, not a mandate to reproduce its tentative formulas when the theory files specify a necessary correction.

## First action: map the real backend

Inspect the provided local project workspace for the validated L/L*, B/B*, S/S*, full state, full GN, constraints, source/frequency stacking, whitening, and O/P/M basis routines. Write BACKEND_MAP.md with actual file/function names and the current commit. Reuse those interfaces. Do not invent a public repository or silently substitute a mock/scalar backend. If a required artifact is absent, identify the exact missing contract and stop the dependent step.

Expose an adapter with:

    apply_L(x,v), apply_L_adjoint(x,v)
    apply_F(x,v), apply_F_adjoint(x,v)
    full_state(x, source, frequency)
    apply_B(x,state,d), apply_B_adjoint(x,state,v)
    apply_S(v), apply_S_adjoint(w)
    full_objective(x), material_constraints(x)
    counters_and_timers()

B_adjoint must implement a REAL material pullback after complex state adjoints. Include the physical current metric in QR/adjoints or transform consistently to Euclidean coordinates.

## Deliverable 1: G0 tests

Run experiments/check_theory.py. Add backend tests for all adapter adjoints, Schur elimination, reduced Galerkin equivalence, fixed-basis forward derivative, multi-source/frequency stacking, real/imaginary whitening, gauge invariance, zero/deflated seed blocks, reduced-core singularity, and constrained KKT residuals. Include the delayed-path and fake-weak counterexamples as tests, not just comments.

Do not use central finite differences of an automatically rebuilt basis to validate a frozen-basis derivative. Test both contracts explicitly. A1 uses full state plus an approximate Jacobian; A2 uses a frozen reduced state with its own consistent derivative.

## Deliverable 2: mixed OPM builder

Implement exact retained-space Schur F_eff and its adjoint using cached retained couplings. Empty U must work. Use separate forward P/M and adjoint O block-Arnoldi streams, then joint orthogonalization. Preserve nested degree spaces, seed provenance and scale, rank-deflation thresholds, and residual diagnostics. Do not pretend the joint compressed matrix is necessarily a single Hessenberg matrix.

Choose small declared seed budgets. Use data residual, independent receiver/material probes, illumination residuals and previous accepted steps when appropriate. Do not use test truth or exact current corrections as seeds. Save seed RNGs.

Build Z=orth[U,Q], reduced core Z*LZ, and actions J_m and its REAL adjoint. Monitor absolute scaled sigma_min as well as condition number. Use a named stable projection or full fallback if the core is unsafe; log the model change. Never silently pseudo-invert a singular Galerkin matrix and keep claiming Galerkin error identities.

## Deliverable 3: frozen-state replay

Use the six-object, two-state replay specification, with full steps from existing references where possible. Run degree 0-5 and O/P/M ablations under matched rank and action budgets. Compute full H-step error, full quadratic gap and truth one-step error separately. Do not optimize current-opportunity coverage. Produce REPLAY_RESULTS.csv, ACTION_COUNTS.csv and REPLAY_REPORT.md with all failures.

Stop and evaluate G1 before starting an expensive full run matrix. A weak replay result may warrant fixing state/seed/projection issues, not new NN training.

## Deliverable 4: A1 nonlinear imaging

At each outer iteration use a trusted full state and residual, the OPM approximate Jacobian, a constrained GN/LM subproblem, and a full-objective acceptance step. Compare full GN and surviving fixed-degree OPM with SOM and generic Krylov baselines using the identical constraints and stopping conditions. This stage tests imaging fidelity; do not promise speed when full state solves dominate.

## Deliverable 5: A2 coherent reduced-state engine

After A1 passes, use the frozen basis Z_k for reduced forward trials and the derivative B(x,j_m). Rebuild only at the declared outer refresh. Full-objective validation/conditional-model refinement controls acceptance and eventual stopping. Count all those costs. The derivative of a moving least-squares test basis needs its residual term; preferably freeze a Petrov test basis when that fallback is used.

Reuse factorizations and cached LZ/receiver couplings safely at unchanged state. Any across-state reuse requires a refresh rule and validation, not reuse of stale physics by accident.

## Success/reporting contract

Use the proposed G1/G2 margins without tuning to test truth. Write RUN_MANIFEST.json, per-iteration CSV, final scene CSV, cost decomposition, quality-versus-cost frontier, and a short GO_NO_GO_REPORT.md. Separate:

    algebra PASS/FAIL
    reduced representation PASS/FAIL
    nonlinear fidelity PASS/FAIL
    total deployment cost PASS/FAIL.

Report exact commands, backend commit, numeric precision, hardware, warm/cold timings, all full RHS and internal iterations, memory, and fallbacks. No unrequested neural training, giant dataset generation, or new algorithm search. End with the next justified experiment, not a list of speculative improvements.
