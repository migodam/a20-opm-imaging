# A21 tests and offline report implementation

Status: implementation ready for the parent Codex source freeze and final A21-only test run. This artifact records software work, not a scientific pass.

Owned files:

- `tests/test_a21_two_sided.py`: independent tiny material-quadratic algebra and negative controls.
- `tests/test_a21_core.py`: complex current projection, real source packing/whitening, protected QR, cached adjoints, and report evidence checks.
- `tests/test_a21_flow.py`: parent-authorized additional orchestration checks with temporary sink files and mocked physical preparation/evaluation.
- `src/a21/report.py`: static local reporting; `write_report(root, config=None, *, book=None, make_figures=True, t0=None)`, `generate_report` alias, and `run_report(root, config, book, job)` CLI adapter.

No original tests, protocol documents, frozen configuration, or other source modules were edited by this worker. No Maxwell solve, physical state, truth file, online experiment, NN task, DeepSeek worker, subagent, or hash check was used.

## Meaningful checks

The core checks compare the cached factorization against an independent explicit complex resolvent with a nonsymmetric, source-coupled real whitening map. They verify transpose whitening, conjugate current adjoints, source permutations, primal/dual source-bank protection, constrained Galerkin and Petrov equality, frozen-rank overflow, source-order protection before large fillers, baseline gauge preservation, cached operator reuse, owner checks, singular/absolute-small cores, and frozen independent random namespaces without global RNG mutation.

The material checks retain material-vector dual errors rather than scalar work. They cover wrong pre-step dual interpolation, active-box normal work, nonzero full-solver defect work, inexact full/reduced solver vector defects, independently evaluated normal allowances including both cross-violations, undefined/ill-scaled ratios, the weak-curvature counterexample, invalid normal signs/representation/complementarity, unresolved KKT/curvature, and a deliberately corrupted inverse-energy computation that must trigger a consistency exception.

The report checks require the five-state grid and all required consistency inputs. They preserve missing/ill-scaled/unsafe/duplicate cases, distinguish a NOT_RUN-to-one-terminal lifecycle from an executed retry, require actual independent random-rank matching, keep alternative explanations when PRIMAL_G or random already passes, reject claimed T0 with missing registered backend context, and block positive labels when saved vectors are incomplete.

The nine flow checks have **NOT_RUN** status at this worker handoff, by parent instruction. They check fixed first/middle/last preparation/validation before all G arms; all 25 G arms before PG; G/core/solver/consistency failures blocking PG; cache-only PG without physical preparation or new T0 work; invalid T0/incomplete G blocking before cache loads; the counted 35-QP cap; saved failed backend validation; immutable failed attempts/no automatic retry; and budget-stop billing with the complete 35-row grid.

## Report input/output contract

Inputs are saved `results/a21/anatomy/rows.jsonl`, `summary.json`, `caches/*.npz` plus their JSON provenance, and `diagnostics/*.npz`. The report reads NPZ array headers rather than materializing large current banks. It also preserves saved A21 driver receipts, the external CPU registry, and the local driver T0 record separately from cached real-state T0 context.

Outputs are under `results/a21`:

- `A21_ORACLE_REPORT.md`, beginning with T0 and T1.
- `A21_METRICS.csv`, retaining all expected states/arms and raw nested source/cost records.
- `per_state/<parent>_17.json`, including raw measurements, array layouts, cache provenance and provisional interpretation.
- `GATE_DECISION.json` with measured evidence and `CODEX_REVIEW_REQUIRED` final scientific status.
- `figures/*.png` and `*.svg`, plus each figure's source table under `rawdata/`.
- `rawdata/` source rows, engine summary, local T0, runtime receipts, completeness and provenance.
- `REPORT_MANIFEST.json`.

Raw solver-aware and normal-adjusted bounds are separate; the allowance increment is not presented as a total bound. Undefined percentage denominators remain undefined. Shared setup/RHS costs are labelled nonadditive across arms. The mechanism and Petrov-instance assessment remain separate. All rows and figures are ORACLE/OFFLINE; no online speedup, nonlinear imaging success, blind validation, or truth claim is made. Parent Codex owns the final interpretation and actual-data/figure review.

## Preserved tiny test receipts

| Scope | Result | Tests | Failures/errors | Inclusive process CPU | GPU |
|---|---|---:|---:|---:|---:|
| `a21-tests-report-tiny-tests-20261006-attempt01` | PASS | 27 | 0 / 0 | 0.338769 s | 0 |
| `a21-tests-report-tiny-tests-20261006-attempt02` | PASS | 33 | 0 / 0 | 0.382866 s | 0 |

Both receipts and complete logs are retained in this directory. Each bounded run used the existing Gaussian `.venv_nn` runtime with one BLAS thread and a 30-second CPU ceiling. Import, test, failure/report handling CPU is included in the single-process receipt. Registration was delegated to the parent to avoid concurrent registry writes. No further worker execution was performed after the parent requested the final flow checks and source freeze.
