# Lightweight experiment specification: one RTX 4060 Laptop

## 0. Evidence status

Only the algebraic NumPy tests in experiments/ have been run for this research memo. No access to the original Maxwell backend or completed nonlinear reconstruction dataset is claimed. The A17/A18/A19 measurements in the task brief are supplied background. This file specifies the next experiments, not completed results.

## 1. Reuse and split discipline

Use the existing validated 3D VECTOR Maxwell backend, source/receiver geometries, material parameterization, current metric, and reference objects. Do not replace it with a scalar 2D simulator for the main claim. Record the actual repository commit and numerical settings. Locate existing adapters by inspecting the local workspace; no new repository path is assumed here.

Pick six genuinely independent parent objects covering smooth Gaussian, near-contact, asymmetric, layered/voxel, and higher contrast, with one additional independent member of a stress family. Keep frequency, source, receiver, voxel spacing, real/imaginary material convention, and parameter scales explicit. Where Gaussian and voxel parameterizations differ, compare algorithms within the same inverse space first. Do not give one method privileged geometry support or truth parameters.

For learning, all states, rotations, noise realizations and frequencies derived from one parent remain in one split. Six objects suffice only for a deterministic feasibility pilot, NOT for a credible neural generalization claim. Use other existing independent objects for a neural pilot, or report insufficient training evidence and stop before training.

## 2. Stage 0: algebra and adapter tests

Run experiments/check_theory.py in complex128. Add backend tests for L/L*, B/B*, S/S*, full realified J/J*, Schur feedback and its adjoint, fixed-basis finite-difference tangents, frozen-basis trial objectives, and reduced-state injection error. Test zero/deflated seeds, near-singular reduced cores, empty U, all-source stacking, gauge rotations, and constrained updates.

Never label a random dense matrix as a Maxwell validation. G0 must pass before imaging.

## 3. Stage 1: cheap frozen replay

For each object use two already available nonlinear states where possible: an early state and a late state. Cache the full state, full data residual, and one trusted full GN step. Evaluate OPM degree 0-5 at fixed state and fixed regularizer. Measure H-step error and true one-step material improvement separately; they need not agree.

Compare O-only, P-only, M-only, O/P/M mixed, forward-only O/P/M, random current subspace, receiver/SOM ROM, ordinary right block Krylov, and available current POD. Match TOTAL seed rank/current rank and ALSO report action-matched frontiers. Increasing O/P/M seed count threefold is not a fair fixed-budget comparison. Ensure degree-zero seeds do not already span almost the full current space.

POD training and snapshot acquisition cost must be counted or explicitly amortized. Bases based on the full solution of the test state are oracle baselines, not deployable competitors. Full current updates may be used only for reference and held-out labels, never as hidden test-time seeds.

Record: rank, degree, orthogonality, sigma_min and condition of each reduced core, primal/dual residuals, material scaling, full stationarity defect, relative H-step error, full quadratic gap, truth one-step error, and action counts.

## 4. Stage 2: actual nonlinear reconstruction

A full initial matrix is six objects times seven methods: full GN; OPM degree 0,1,2,3; receiver/SOM ROM; ordinary Krylov ROM. This is 42 reconstructions before optional methods. Frozen replay may eliminate obviously dominated degrees before this stage, but report the elimination rule and replay results. Add adaptive OPM only after its audit controller is correct; this adds six runs.

Implement A1 first: trusted full state and residual each outer iteration, reduced Jacobian, full-objective line search/LM. This isolates representation quality. Then test A2 with a coherent frozen-basis reduced state and tangent, plus conditional full-objective validation. A1 may not accelerate because it retains full state costs; A2 is where a reduced imaging-engine speed claim is tested.

All methods share initialization, bounds, regularizer, LM updates, acceptance thresholds, and a common full-physics stopping rule for comparison. A reduced residual cannot certify completion of a full-physics method. Record failed line searches and full fallback calls. Do not tune regularization separately on each test truth.

## 5. Stage 3: noise and robustness, only for survivors

For two independent stress objects, add 1% and 3% relative complex data noise with three paired realizations. Initially compare full GN and the best fixed/adaptive OPM survivor: 2 objects x 2 levels x 3 realizations x 2 methods = 24 runs. Adding a third method gives 36 runs. This is staged work, not permission to start every combination at once.

Define noise explicitly: draw circular complex Gaussian noise, then scale it to the declared global relative measurement norm. When whitening, document the corresponding covariance convention and real/imaginary factors. Report both achieved relative norm and SNR. Fixed-norm rescaling changes the exact Gaussian distribution; use truly Gaussian draws with a calibrated expected norm when Gaussian likelihood identities are being tested.

Use the same noise draw for competing methods. Report clean-data residual, noisy-data residual, and held-out receiver/frequency residual where available. Optional model mismatch must be separated from additive noise, not silently absorbed into a new noise level.

## 6. Metrics and accounting

Primary: final mass-weighted relative material error, separately real and imaginary contrast, and paired final full nonlinear objective. For a near-zero true imaginary part use a prespecified denominator floor and also report absolute error. Include distance to full-GN reconstruction but never substitute it for truth error.

Secondary: data residual, outer iterations, H-step error, accepted step length, KKT residual, selected degree/rank, reduced-core stability, and failure/fallback rate.

Cost: cold and warm total wall time; basis/seeds/QR/projected core/material solve/globalization/audit sub-times; F and F* vector actions; full forward/tangent/adjoint solve calls; total RHS; iterations/actions inside those solves; source/frequency counts; peak CPU/GPU memory. Batch applications still count their vector RHS. Synchronize the GPU before timing and use the actual device memory, not an assumed model specification.

Report setup and reference-generation time separately. Reference full solves are not free when used in deployment. Count amortization over the actual number of reconstructions, not an invented future dataset.

## 7. Output schema

Write one machine-readable row per outer iteration and one per completed run. Required run keys:

    experiment_id, parent_object_id, split, backend_commit, method,
    parameterization, n_current, p_material, n_source, n_receiver,
    frequencies, noise_seed, noise_level, initial_state_id,
    degree_policy, seed_budget_O, seed_budget_P, seed_budget_M,
    final_truth_error, final_real_error, final_imag_error,
    final_full_objective, final_data_residual, final_KKT_residual,
    wall_total, wall_setup, wall_audit, peak_memory,
    F_actions, F_adjoint_actions, full_forward_RHS,
    full_tangent_RHS, full_adjoint_RHS, fallback_count, status.

Iteration rows additionally include rank, degree, model refresh, predicted/actual reduction, step size, H-error when available, full stationarity audit, and core stability.

## 8. Decision report

Produce paired scene tables and quality-versus-total-cost frontiers, not only averages. Give the worst scene and every failure. Distinguish algebra pass, representation pass, end-to-end cost pass, and neural-prior pass. Use GO_NO_GO_GATES.md. No large dataset or neural training starts merely because degree-2 development current coverage was high.
