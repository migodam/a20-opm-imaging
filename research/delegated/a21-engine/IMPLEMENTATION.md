# A21 engine and immutable source mapping

## Scope and verification status

This worker owns only `src/a21/core.py` and `src/a21/anatomy.py`. Existing A20 physics, constrained-QP solver, material chart, and R1 source files were reused without modification. The engine implements the frozen five late states `[2001, 2005, 2003, 2007, 2013]`, each at iteration 17. It does not load truth or labelled update arrays. No physical experiment was run by this worker.

The parent reported a successful bounded CLI validation receipt, inclusive CPU 1.904221 seconds, before the final anatomy-only provenance, cache-size, and failure-evidence edits. Those edits were checked by parsing both owned source files. Final runtime evidence belongs to the parent-run CLI receipts and anatomy records; source implementation and tiny fixtures do not imply scientific acceptance.

## Existing backend and reference inputs

The immutable backend is the A20-R1 package at `Gaussian/A20/a20-r1-mechanism`. `a20.backend.Adapter` supplies one full state per parent, `state._L_factor` supplies the existing full LU, and `state.model.solver.solve` applies it with `trans=0` for the primal and `trans=2` for the conjugate adjoint. `a20.opm.FullJacobian` assembles the reference real material Jacobian once, as 54 directions times six sources, for 324 full derivative RHS per state.

The case dimensions are 1728 cells, 5184 complex current coordinates, 27 complex material-chart coordinates, 54 real material coordinates, six sources, 128 complex channels per source, and 1536 packed real data entries. Each source is packed as `[Re(128), Im(128)]`; source blocks are then concatenated. Real whitening follows packing. The deployed scalar whitening uses the original measured-data normalization and is not a calibrated noise covariance.

`a20.material.solve_quadratic` is the unchanged constrained-QP solver. The material inequalities use `A = block_diag(Q, Q)` and lower increments `[-0.5 - Re(chi), -Im(chi)]`; the recovered normal is `-A.T @ multipliers`. The engine keeps the raw QP minimizer, recovered multipliers, slack, active indices, violation, complementarity, and KKT residual. It does not clip the final step or use truth-informed constraints.

`a20.r1_anatomy` canonical resolvers select the latest non-historical full-GN-reference replay records and the original mixed degree-three baseline records. The canonical full step pattern is `results/replay/steps/20261005T082521_71339a28_<parent>_17_full_GN_reference_None.npz`; the original labelled `step_17` arrays and `_historical` reference records are not reference inputs. The same quadratic may receive a separately counted reference repair only when its saved full step fails the frozen audit and the protocol permits repair.

## Baseline construction and previous gauge conflict

`prepare_case` directly constructs `SchurFeedback(view, view.receiver(8), config)`. It never calls the legacy builder that can construct an empty retained-U rescue. The R1 paired random bank, residual observation at O column zero, O4/P4/M4 seed order, degree-three `Hierarchy`, and direct rank-56 Galerkin `Projection` reproduce the declared baseline with `previous=None`. Original O, P, M draw ordering and the degree/index priority are retained. The final baseline step must match its canonical saved R1 step within relative tolerance `1e-9`; mismatch raises an input error and does not select a different reconstruction.

`BASE_G` copies the original Z and uses a bank selector transform. It receives no new SVD, QR, or retained-U gauge. Other arms start with the retained U, then all protected source columns in source order, then the original earlier-degree/index fillers. A20 recorded an original-replay/R1 retained-U gauge difference and an early-state conflict. The five late cases previously matched their canonical steps at the required tolerance; the engine rechecks that statement. Gauge difference and causal explanation are separate statements. No early state is added to this protocol.

## Core interfaces and shared images

`ordered_protected_basis(D, protected_indices, filler_indices, target_rank, rtol=1e-10, retained_count=0)` returns `ProtectedBasis(Z, T, metadata)` with `Z = D @ T`. Double modified Gram-Schmidt visits raw columns in order. All protected columns are processed before fillers, and only numerically zero or dependent directions may be deflated. Independent protected rank exceeding the fixed rank or insufficient filler rank raises `RankBudgetInfeasible`. There is no top-k protected truncation, shift, pseudoinverse, or fallback.

`independent_addition_rank(U, additions, rtol=1e-10)` measures the actual protected additions relative to retained U. `random_bank(n, count, seed)` produces a normalized complex Gaussian bank from the supplied `SeedSequence` without redraws. The anatomy seed words are `[20261006, parent, 17, suffix]`, with suffix 2101 for common random Galerkin, 2102 for random PG trial, and 2103 for random PG test. Actual random addition ranks must match the corresponding oracle addition ranks.

`SharedBank(D, LD, SD, DHB, whitening, L_scale, ...)` owns the common raw bank. Shapes are `D, LD: (5184, bank_width)`, `SD: (128, bank_width)`, and `DHB: (6, bank_width, 54)`. `SD` stores one receiver image matrix; source-major illumination dependence is in `DHB = D* B` and the six-source packing. `DHDL = D* LD` is computed once. The raw block order is `[baseline(56), X(6), Y(6), random_G, random_PG_trial, random_PG_test]`.

`SharedBank.project(trial, test, config, book)` returns a `CachedProjection` with `A_core = T_test* DHDL T_trial`, `S_trial = SD T_trial`, and `B_test = T_test* DHB`. One small LU serves the action and its conjugate adjoint. Unsafe relative, absolute-scaled, or condition checks raise `UnsafeCore`. The projection verifies bank ownership, basis transforms, and orthogonality; it records each primal/adjoint small-solve backward residual.

`CachedJacobian(bank, projection, book=None)` exposes `action`, `pullback`, and cached `small_matrix`/`matrix`. The pullback uses the actual real whitening transpose, source unpacking, conjugate receiver image, and the same small LU with `trans=2`. It is tied to the assembled real matrix. `MatrixJacobian(matrix)` adapts cached full or reduced matrices to the existing QP solver.

## Oracle currents and accounting

`prepare_case(root, parent, config, book)` forms `X = L^-1 B(s_F)` and `Y = L^-* S* e_F` from the same full-state LU. X uses exactly six full primal RHS and Y exactly six full adjoint RHS. `full_oracle_RHS` records 12 per state, with directional counters separate; native solver receipts describe those same solves and are not added again. Source-wise and aggregate residuals for `LX - B(s_F)` and `L*Y - S*e_F` must meet `1e-9`. The current images measured for those checks are reused in the shared raw bank.

The original baseline LZ/SZ, oracle images, and random-bank images supply the single shared `LD/SD/DHB` cache. Arm assembly, protected QR, compressed adjoints, captures, QPs, diagnostics, and file IO have their own spans. Backend validation for first/middle/last states is delegated to the parent's `a21.validation.validate_case` and uses the same live case and cache. The validation RHS are additional paid operations, not hidden oracle work.

## Cache and record contract

`results/a21/anatomy/caches/<parent>_17.npz` and its JSON sidecar are written once. Cache fields include x, chart Q and volume, material/data geometry, measurement normalization and whitening, JF/HF/r/ell/lam/Lambda, the raw full step and full normal/multipliers/slack/active indices, constraints, U/baseline/baseline_LZ, canonical baseline step, degree/index priority, X/Y and their residual images, primal/dual/illumination forcing, all frozen random banks and seed metadata, D/LD/SD/DHB/DHDL, L scale, source counts, frozen configuration signature, and source/runtime identities. `B_factor` preserves material-to-current forcing provenance.

Dense L and the redundant raw receiver S are deliberately not persisted. Metadata declares `dense_L_persisted: false`, `raw_S_persisted: false`, and that all arms used the same live full L. This avoids approximately 430 MB of dense L per state while retaining all shared images and offline diagnostic arrays. Existing historical hashes may appear in source provenance; the engine performs no new hash check.

`load_cached_case(path, config)` validates the frozen signature, fixed dimensions, source layout, raw-bank group partition, baseline/U mapping, constraints, and the stored reference normal/multiplier/slack representation. It reuses saved full multipliers and normal rather than rerunning normal recovery. No Adapter, full state, full LU, or full operator is created for a cache-only PG continuation.

`results/a21/anatomy/diagnostics/<parent>_17_<arm>.npz` contains Z/W, the corresponding raw-coordinate transforms, small core and compressed Jacobian, full/reduced raw steps and KKT vectors, protected currents, source-wise capture vectors and definition flags, and the parent diagnostics vectors. Successful records set `reference_valid: true`. Failed cores and QPs preserve available underlying vectors. Failed preparation can preserve a dedicated `<parent>_17_failed_preparation.npz`.

`rows.jsonl` is append-only. A placeholder `NOT_RUN` may acquire one later terminal record; an executed terminal record cannot be overwritten or executed twice. Per-state JSON files retain the latest arm status, and `summary.json` includes all 35 declared state/arm records. Rank limits, unsafe cores, QP failures, consistency failures, blocked inputs, and unexecuted arms remain explicit.

## Staging and validation

`run_anatomy(root, config, book, job)` supports runtime `config["stage"]` values `all`, `galerkin`, and `petrov`. It first consumes the existing CLI `results/a21/validation/T0.json` PASS receipt and checks its frozen protocol source and copied synthetic-result identity. It does not launch another synthetic process, pay the same child CPU twice, or rerun tiny tests.

Physical preparation visits first/middle/last `[2001, 2003, 2013]` before the other two states, using each one-time live state for backend validation and its cache. After those three backend validations pass, all five G arms run for every state in the frozen parent order. Each arm checks cached action, transpose/pullback, and tied dot identity before the raw QP; BASE additionally checks the canonical R1 step. The parent `diagnostics.evaluate` then enforces the two-sided identity and its consistency checks. All 25 G results must be `OK` and consistent before any of the ten PG QPs starts. PG uses only small immutable caches. The 35-QP cap refers to reduced arms; any permitted full-reference repair has a separate count.

Genuine consistency, input, or budget failures preserve current failure evidence and append missing `NOT_RUN` records before re-raising. A limited architecture arm can finish with an explicit failure status while other G arms are evaluated, but it blocks PG advancement. Summary T0 combines the reused tiny receipt with first/middle/last backend checks. T1 and scientific conclusions remain for parent review.

## Boundaries and remaining evidence

The implementation does not prove scientific success, fair deployment cost, or novelty. Existing data are historically exposed. Oracle X/Y are explicitly paid offline diagnostic currents, and cached reduced computation excludes their deployment as a cheap source. The parent's full CLI receipt and frozen backend anatomy records determine which operations actually ran. The parent owns the diagnostics equations, all mathematical interpretation, and final decision about whether the results support the two-sided mechanism claim.
