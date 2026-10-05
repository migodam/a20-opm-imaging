# A20-R1 baseline conflict: bounded code and saved-record audit

This is an evidence-only mechanical audit. Source, frozen configuration, raw anatomy rows, original replay rows, steps and failure evidence were not modified. No physics, GPU operation, new QP, numerical projection, NPZ-array read, hash, test or retry was performed. This document does not establish causality or change a scientific gate. The saved driver summary remains `FAILED` with `BaselineConflict:(2001,0)`; parent review owns the current INCONCLUSIVE interpretation and any next authorization.

## Saved observation

`results/a20_r1/anatomy/ANATOMY_SUMMARY.json` records 60 intended method rows: 30 `OK`, 1 `FAILED`, 29 `NOT_RUN`; 31 models were built. The 30 completed rows cover six methods on all five iteration-17 states, at rank 56. The first early FIXED-DEEP row, parent 2001 / iteration 0, is QP-valid but fails the frozen baseline guard. Its step-relative difference is **1.670492038118766e-6**, compared with the registered **1e-9** limit.

The `baseline_metrics_reproduction_valid=True` field certifies the saved baseline step's audit, not equality of the new FIXED proposal. The new proposal has `baseline_reproduction_valid=False` and `baseline_step_reproduction_valid=False`. Its relative H error is 0.013247119926976851 versus the saved 0.01324707023497228; their relative difference is 3.751169405046497e-6. The stored full-reference H energy agrees exactly at 0.20386458008370373. These different validity fields must not be conflated.

## Confirmed code differences

1. **Retained receiver preprocessing differs from the canonical replay.** Original `src/a20/replay.py:403–415` calls `orth(view.receiver(8), rank=8, rtol=1e-10)` before `SchurFeedback`. R1 `src/a20_r1/seeds.py:186–204` passes `view.receiver(8)` directly. `orth` is an SVD-based routine (`src/a20/opm.py:13–31`). Original `src/a20/imaging.py:17–22` also uses the direct receiver basis. Therefore matching the original imaging builder is not the same code path as matching the saved replay baseline. An extra SVD can change basis coordinates/phases; this audit did not measure the resulting retained projector, final Z projector or reduced J difference.
2. **Hierarchy call scheduling differs, but the internal degree sequence is unchanged.** Original replay extends one hierarchy at each registered degree (`src/a20/replay.py:717–728`), interleaving model/QP/audit work. R1 calls `hierarchy.at_degree(3)` once (`src/a20_r1/seeds.py:402–403`). The unchanged `Hierarchy.at_degree` visits degrees 0,1,2,3 internally. Saved degree labels match for every executed FIXED row below. The call scheduling difference alone is not evidence of a different degree-3 space.
3. **Material-matrix acquisition is staged differently.** R1 explicitly obtains `model.jacobian.matrix()` before calling `solve_quadratic` (`src/a20_r1/anatomy.py:661–668`); original replay creates the ReducedJacobian and obtains the matrix inside the same QP path (`src/a20/replay.py:462–465`, `src/a20/material.py:53`). The unchanged ReducedJacobian cache supplies the same acquired matrix on the subsequent call. No changed solver or warm-start parameter was found.

## Confirmed unchanged recipe and thresholds

Direct source-text comparisons, without hashes, found `src/a20/backend.py`, `src/a20/opm.py` and `src/a20/material.py` identical between the original repository and R1 worktree. `configs/frozen.json` parses identically. This establishes local source/config equality, not historical remote environment or runtime-array identity.

The FIXED recipe remains O4/P4/M4, degree 3, retained allocation 8. Original `build_seeds` draws M4 before O4, normalizes M4, replaces O column 0 with the measured residual, and injects all sources before compression (`src/a20/opm.py:137–178`). R1's paired bank preserves that draw order; its independent M extras do not advance the legacy stream (`src/a20_r1/seeds.py:164–182`). Both frozen drivers use `previous=None` (`src/a20/replay.py:691`, `src/a20_r1/anatomy.py:640–643`). Both use the same `Hierarchy` with O applying Schur F-adjoint and P/M applying Schur F (`src/a20/opm.py:205–212`). No RNG, family-direction, degree, source-count, previous-history or seed-allocation change was found in this FIXED call path. Saved metadata verifies matching seed RNG, seed ranks and degree labels; it does not contain a proof of equality of all basis/probe arrays.

The QP calls both omit `initial`, hence start from the same zero default (`src/a20/material.py:66`). The identical solver uses SLSQP `ftol=1e-16`, maxiter=200 and the same objective scaling, feasibility tolerance 1e-8 and KKT-relative threshold 1e-8. Active-equation polish is conditional on initial KKT-relative exceeding 1e-8 (`src/a20/material.py:100–130`). The baseline step-reproduction threshold is separately 1e-9; QP validity does not itself certify that reproduction threshold.

## Saved QP-path comparison

| parent / iteration | saved → R1 QP iterations | saved-step relative difference | degree labels / seed ranks / RNG metadata |
|---|---:|---:|---|
| 2001 / 17 | 63 → 65 | 8.59417966538e-11 | equal |
| 2005 / 17 | 64 → 64 | 3.62472909067e-14 | equal |
| 2003 / 17 | 61 → 55 | 2.53483971719e-14 | equal |
| 2007 / 17 | 0 → 0 | 5.28373475337e-15 | equal |
| 2013 / 17 | 0 → 0 | 1.34990383024e-14 | equal |
| 2001 / 0 | 94 → 99 | 1.67049203812e-06 | equal |

For early parent 2001, the saved and new QPs both use `SLSQP-common-quadratic`, have two active constraints, meet the same KKT tolerance, and do not invoke polish. Saved KKT-relative is 8.41364710636861e-9; new is 6.128983251449256e-9. The recorded quadratic values are -0.10186605507869913 and -0.10186605507870071. Iteration counts differ, but this does not prove a causal chain from retained preprocessing to the optimizer trajectory.

The late states are useful counterevidence against a blanket failure explanation: all five FIXED proposals reproduce within 1e-9 despite the same retained-preprocessing difference. Parent 2001 / 17 also changes SLSQP iterations (63 to 65), yet its step-relative difference is only 8.59417966537516e-11. Parent 2003 / 17 changes 61 to 55 iterations with difference 2.5348397171930662e-14. Late parent 2005 uses validated active-equation polish in both records; 2007 and 2013 use direct SPD in both.

## Unconfirmed causal possibilities and explicit gaps

- Extra retained SVD/gauge changes could perturb subsequent arithmetic. No projector/J comparison was computed, so the observed step discrepancy cannot be attributed to that difference.
- SLSQP termination and floating-point sensitivity could permit two QP-valid approximations to differ by more than a stricter saved-step threshold. The recorded iteration counts and KKT residuals are compatible with that possibility, but reduced-H conditioning and a controlled identical-input comparison are absent. No solver change, tolerance relaxation or new polish was performed.
- Historical device/BLAS/SciPy reduction ordering or exact runtime-input identity has not been established by this code audit. No environment-drift claim is supported here.
- The exact legacy-unit tests in `tests/test_r1_seeds.py:161` and `:193` use `CONFIG.retained_rank=0` (`:23`) and share the same R1 Schur object. They verify legacy probe/seeding and hierarchy equivalence for that synthetic scope; they do not exercise the nonempty receiver basis or canonical replay's extra retained SVD. Their zero-error results therefore did not test this newly identified pipeline difference.

The confirmed correction opportunity is a baseline-definition/code-path discrepancy requiring parent adjudication. None of the hypotheses above is a proven cause, and none authorizes resuming physics. Original source, results and frozen stop remain intact.

## Accounting

All read/write processes are recorded under `baseline_conflict_code_audit` in `results/a20_r1/SEED_WORKER_RECEIPT.json`, separate from the existing seed-test attempts. The audit has an additional 2-second inclusive process-CPU cap and retains the original worker's cumulative 12-second ceiling. There were no failed audit subprocesses, no physics or QP executions, and no source/config edits.
