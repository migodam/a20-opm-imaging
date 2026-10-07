# Cached common-QP reproduction audit

The strict historical scalar check **failed on both platforms**. All 2,112 common 32D solutions on each platform passed the original feasibility and relative KKT contract. This audit does not change the solver, lambda, tolerances, scores, split, or scientific gates, and does not inspect split outcome metrics. Five cached diagnostic QPs were run; no Maxwell actions or new labels were generated.

## Observed replay results

Both attempts stopped before Test B. The absolute scalar reproduction threshold remains `1e-8 * max(1, abs(saved material_error))`.

| Scene | Mac mismatches / 528 | Windows mismatches / 528 | Mac max material-norm difference | Windows max material-norm difference |
|---|---:|---:|---:|---:|
| 2001 | 32 | 26 | 9.605935853e-7 | 1.631117072e-7 |
| 2003 | 65 | 0 | 5.515810975e-8 | 0 |
| 2014 | 6 | 0 | 3.084821242e-7 | 0 |
| 2009 | 1 | 0 | 1.018089835e-8 | 0 |
| Total | 104 / 2,112 | 26 / 2,112 | 9.605935853e-7 | 1.631117072e-7 |

The maximum signed-direction error difference was `4.617131434e-7` on Mac and `4.164619049e-8` on Windows. Raw true directional coefficients agree to `2.775557562e-17` on Mac and exactly on Windows. Each platform's 2,112 results meets the frozen `1e-8` relative KKT and feasibility requirements. All mismatching results have `solver_success=True`, use the SLSQP branch, and have no accepted active-equation refinement. There are mismatches at noise level zero, so a changed noise draw cannot explain all failures.

Evidence is preserved in:

- `results/a22_r1/replay/20261007T163525Z_1d65fc670927/COMMON_REPRODUCTION.json` and `COMMON_32D_CASES.jsonl` (Mac).
- `results/a22_r1/replay/20261007T164205Z_d1452c27461b/COMMON_REPRODUCTION.json` and `COMMON_32D_CASES.jsonl` (Windows).
- `PLATFORM_REPRODUCTION_METADATA.json` and `PLATFORM_REPRODUCTION_FOLLOWUP_METADATA.json` in this directory, containing per-scene KKT summaries and worst-case records.

## Lambda and matrix identity

The descriptor and the actual full solve use the same mathematical lambda formula:

`lambda = config['tikhonov_relative'] * scipy.linalg.svdvals(model.AW)[0]**2`, with `tikhonov_relative = 1e-4`.

`build_descriptor_context` records this formula in `descriptor.regularization` (`src/a22/features.py:91`). `evaluate_recovery` passes `model.AW` without a restricted basis and leaves lambda at its default (`src/a22/evaluate.py:430-436`). `constrained_material_solve` evaluates the same formula on that same AW (`src/a22/core.py:127-129`). Thus the stored descriptor lambda is not a different restricted-basis lambda. The current R1 common solve passes that old scalar explicitly, as required by its preregistration.

| Scene | Stored original lambda | Mac default minus stored lambda |
|---|---:|---:|
| 2001 | 39970.28132448953 | -1.455191523e-11 |
| 2003 | 40321.322228950965 | -2.182787284e-11 |
| 2014 | 40510.39077571165 | 0 |
| 2009 | 40445.83072241458 | +2.182787284e-11 |

The default lambda differences are floating-point SVD rounding. Explicit old lambda versus current default lambda produced bit-identical solution vectors in both probed cases (the largest material-norm discrepancy in 2001 and in 2003). This rules out that lambda rounding as the cause of those two discrepancies; it does not prove every unprobed case is insensitive.

Every original `online_factors.npz` AW and new R1 AW is exactly equal, shape `(1536, 32)`, dtype float64, C-contiguous, not Fortran-contiguous, strides `(256, 8)`. The raw old/new `AW.npy` archive members also match byte for byte; no hash checks were used. Both saved 2001 resumed factor matrices are exactly equal to the original AW, with the same C layout and original lambda. R1 copying did not convert a stored Fortran AW into C order.

The source constructs AW through the original source-major `pack(raw)`, scalar whitening, then `_readonly(AW)` with `np.array(..., copy=True)` (`src/a22/online.py:29-32,314,336`). For this 2D copied array, the saved C NPY order is consistent with a C-contiguous original model AW. There is no evidence of an authoritative unsaved Fortran AW that R1 should restore. A differently ordered diagnostic copy must therefore remain a diagnostic, not a loader repair.

## Concrete sensitivity probe

The worst Mac 2001 case was `2001|2|1|3.0|14|source_amplitude_5pct_receiver_gain_3pct`. An unchanged C-contiguous AW and old explicit lambda reproduced the Mac archived vector exactly. A Fortran-contiguous copy of the same numeric AW reproduced the old Stage-A signed error and material-error norm to `4.8e-15` and `7.1e-15` respectively.

| Same-case AW layout | SLSQP iterations | Relative KKT defect | Material error | Signed directional error |
|---|---:|---:|---:|---:|
| C, original explicit lambda | 94 | 1.165970861e-10 | 0.1429679141221616 | 0.01301924451489006 |
| C, current default lambda | 94 | 1.165970861e-10 | 0.1429679141221616 | 0.01301924451489006 |
| Fortran copy, original explicit lambda | 86 | 9.751508653e-9 | 0.1429669535285692 | 0.01301970622803833 |

Both layout variants satisfy the original KKT and feasibility tolerances. Their coefficient vectors differ by `2.940368904e-6`. The unnormalized KKT defects are approximately `0.007613` and `0.636729`, respectively, while the normalizing gradient norm is approximately `6.5295465e7`. The KKT contract is a relative gradient/normal defect, whereas the reproduction contract compares absolute material-norm and directional-error scalars. They are distinct tests with different units; satisfying the original relative KKT contract does not establish equality of historical scalar outputs at `1e-8`.

This probe establishes a concrete floating-point assembly / SLSQP stopping sensitivity with identical mathematical inputs. It does not establish that changing layout is an authorized replay fix, that Fortran order explains the old calculation, or that every mismatch has the same cause. Probe data, iterations, objective values, residuals, and runtime build configurations are in `PLATFORM_QP_PROBES.json`.

## Historical localization and source sensitivity

Scene 2001 contains 209 earliest rows without resume markers and 319 later rows with resume markers. The preserved first attempt confirms 209 committed rows (`results/a22/attempt_archive/a22-cuda-screen-001/PRESERVATION.json`). Every one of the remaining 26 Windows mismatches belongs to those 209 earliest rows. All 319 resumed 2001 cases and all 1,584 cases from the other scenes reproduce exactly on Windows.

Git source history between A22 implementation commit `454a873` and closeout commit `153e326` shows a change in the SLSQP constraint representation: the earlier source submits all 3,456 inequalities, while the later source removes only exact duplicate `(row, lower)` pairs and submits 32 unique inequalities. The objective, lambda, initial point, SLSQP options, full final feasibility audit, and full final KKT audit remain the same. The scientific equivalence of the feasible set is recorded in `results/a22/EXACT_CONSTRAINT_EQUIVALENCE.json`; the implementation patch is described in `research/delegated/a22-core-dedup/summary.md`.

That representation change can alter a finite-precision SLSQP trajectory even though it preserves the mathematical quadratic and feasible set. Its historical timing and the concentration of Windows mismatches in the first 209 rows are consistent with the remaining discrepancy. The archived scalar rows do not preserve optimizer input row counts, full solution vectors, or the live source of each solve, so this audit does **not** establish a case-by-case causal proof that pre-dedup constraints produced those 26 old stopping points. No old-source full replay was performed.

The R1 source is unchanged relative to the final frozen A22 core/evaluator/feature/backend files. The historical first implementation and final frozen implementation need not have generated numerically identical stopping points; mathematical feasible-set equivalence alone is not historical scalar reproducibility.

## Observation and chart checks

R1 retains the old sigma and whitening scalars, finite label observations, original `pack` function, calibration implementation, registered proper-complex noise seed tuple, chart, anchor, and original constraints. Full true coefficients and signed direction conventions reproduce as reported above. The three non-2001 scenes reproduce exactly on Windows, providing direct end-to-end evidence against a general layout, seed, calibration, or truth-coordinate mismatch.

The original background observation vector was not persisted, so it cannot be directly compared byte for byte to the recovered known-background field. The background recovery audit matched original AW/MW/PMW, sigma, descriptor scalars, frozen original directions, and finite predictor budgets within their original identity checks. This supports the unchanged physical context without proving identity of every unsaved background component. No additional physical action was used for this diagnosis.

Chart-exterior energy is outside this reproduction comparison and outside the in-chart `V_phys/V_prior` test. Nothing in this audit reassigns chart-exterior truth to the in-chart prior subspace.

## Recorded environments and paid work

Mac actual probe runtime: Python `3.13.13`, NumPy `2.5.3`, SciPy `1.18.1`, macOS `26.6.2`, arm64; NumPy and SciPy report Apple Accelerate BLAS/LAPACK. `threadpoolctl` was unavailable; build configuration text is preserved. All four thread environment limits were set to 1 (`OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `MKL_NUM_THREADS`).

Windows replay: Python `3.10.9` (MSC v.1934, AMD64); the recorded original Windows environment preflight reports NumPy `2.2.6`, SciPy `1.15.3`, and Torch `2.6.0+cu124`. This cached replay used CPU; GPU occupation was zero.

| Receipt | Inclusive CPU seconds | Cached diagnostic QPs | New Maxwell actions |
|---|---:|---:|---:|
| `a22-r1-platform-metadata-001` external receipt file | 0.097141 | 0 | 0 |
| `a22-r1-platform-probe-001` registered R1Book job | 0.418067 | 5 | 0 |
| `a22-r1-platform-metadata-002` registered R1Book job | 0.395002 | 0 | 0 |

The first metadata receipt is preserved in `PLATFORM_METADATA_CPU_RECEIPT.json` for parent registration exactly once. The other two jobs are already additive entries in the R1 cost ledger. No more cached diagnostic QPs were run after the five recorded probes. The failed full cached Mac and Windows replay costs remain in their own receipts; they are not counted again here.

## Interpretation boundary

Strict historical scalar reproduction remains **FAILED**, and no alternative stopping point, memory layout, or tolerance was selected to make it pass. The parent separately registered `REPRODUCTION_CONFLICT_ADDENDUM.md` before split metrics: one entire fixed Windows common-vector archive is to be checked against the original quadratic/KKT/feasibility contract, then used uniformly for Test A. This audit supplies reproduction evidence only; the addendum, subsequent checks, and scientific screening interpretation belong to the parent. No formal PASS or O/P/M subspace conclusion follows from these QP checks.
