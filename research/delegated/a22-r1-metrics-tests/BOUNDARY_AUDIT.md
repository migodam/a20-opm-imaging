# Independent A22-R1 implementation boundary audit

The new test file `tests/test_a22_r1_boundary.py` contains **26 independent
synthetic boundary checks; all passed**. This audit verifies implementation
contracts only. No scientific screening gate, subspace-separation result,
population claim, or expansion decision is asserted.

Only that test file and audit/receipt artifacts were added for this additional
task. This worker did not change `accounting.py`, `freeze.py`, `replay.py`,
`cli.py`, or any original A22 source.

## Inputs and execution boundary

Inspected the new `src/a22_r1/accounting.py`, `freeze.py`, `replay.py`, and
`cli.py`, with synthetic helper tests and source AST checks. Array-layout
fixtures live only in temporary directories and contain constructed values.
They do not reuse experiment truth, error, label, material, or data arrays.
The tests did not open original experiment result files. They compared Python
source bytes under `src/a20`, `src/a20_r1`, `src/a21`, and `src/a22` to the
frozen `Gaussian/A22/three_fold_opm/implementation` source checkout, without
hash calculations.

No Maxwell/background builder or physical label generation ran. No NN or
nonlinear solver ran. `freeze_scene` was invoked only with invalid early
preconditions, while its background builder was patched to reject invocation.
The original `run_replay` function was never invoked: the CLI failure test
replaced it with a synthetic exception. The small constrained solver was also
replaced with constructed success results or a constructed `QPFailure`.
`_freeze_online_splits`, cache readers, data packing, and metrics ran only on
temporary synthetic files or arrays.

## Verified contracts

| Area | Evidence from the independent tests |
| --- | --- |
| Original source preservation | Python sources in all four existing packages have the same file membership and exact bytes as the original frozen checkout |
| Candidate frame | Freeze's common-frame expression is exactly the copied concatenation of the original saved `V_phys` and `V_prior` columns; a synthetic mutation of the input array cannot mutate the copied frame |
| Common cache identity | Replayer retains the exact saved 32D common columns and AW; changing AW, background layout, saved score order, or the common frame is rejected |
| Frozen normalization | Original sigma and whitening are reused; original provenance lambda is retained even when the synthetic online cache's lambda field deliberately contains a different number |
| A1/A2/A3 ordering | Stable ascending score ordering resolves ties by the unchanged common-basis index |
| RANDOM control | `SeedSequence([20261910, scene_id])` yields the tested per-scene permutation; k=8 columns are the prefix of the same k=16 split |
| k and primary budget | Any k set other than exactly 8 and 16, or a primary k other than 16, is rejected before cache loading |
| Global online completion | All four scene manifests must be complete before split-cache reads; a failed scene stops the freeze before any cache archive is opened |
| Offline capability boundary | Direct full-J-split, original-case-grid, and cached-label helper calls reject a missing global online split freeze before any evaluator archive access |
| Offline completion receipt | A pending global freeze or any failed individual online manifest blocks the offline capability |
| Source packing | Nominal data matches explicit per-source real-block-then-imaginary-block packing into 1536 real coordinates |
| Noise recipe | Repeated draw seeds reproduce observations exactly; changing the draw changes observations, and an independent construction matches the saved recipe's SeedSequence components |
| Cached label layout | Source ordering is exactly 0..5; reordering sources is rejected, valid fixture loading retains the original fixture bytes, and the read is marked offline |
| Restricted lambda | Common and restricted solver calls both pass `lam=cache.lam` explicitly; the original configuration object and restricted basis are retained |
| Shared metric integration | A metric record merges chart metadata and primary metrics without duplicate-keyword failure |
| Immutable outputs | Different semantic JSON/NPZ contents are rejected; existing output bytes are retained |
| QP failure | A constructed failure invokes the solver once, retains one counted solve attempt, writes `INVALID_QP`, and records `terminal=True`, `clipping=False`, `fallback=False` with the attached QP audit |
| Inclusive cost accounting | Duplicate external identities and repeated job finish are rejected; a failed synthetic job still emits one additive inclusive receipt and a failure ledger record; nested spans remain nonadditive |
| Online and label guards | Full-J/tangent/adjoint counters and new-label counters reject the action before its body; exhausted known-background allowance and forbidden online information/actions stop immediately |
| Metric eligibility | `INVALID_QP` and unknown solver statuses invalidate the corresponding 48-condition scene group; successful rows cannot mask them through averaging |
| Forbidden stages | CLI requests for NN, training, diffusion, or expansion are refused before configuration or job creation |
| New source calls | New modules contain no neural-training/nonlinear-solver calls; the cached replayer contains no Maxwell/background-builder calls; freeze's NumPy cache reads name original online files only and disable pickle |
| Tiny identity allowance | An explicit documented near-zero identity residual allowance remains audited; zero physical factors and ordinary regularization quantities do not receive a hidden epsilon |

## Actionable issue found during review

The initial accounting predicate rejected `full_adjoint_solve` but allowed
online `full_adjoint_calls` and `full_adjoint_RHS`, both of which are forbidden
by the freeze module's declared counter contract. This worker reported that
gap to the parent before execution and did not change accounting code.

The parent broadened the predicate to `full_adjoint` and also covered
full-H/Hessian and declared offline-only counter names. The final runtime
guard check includes both adjoint counters, and the synthetic verification
passed. The observed implementation gap is resolved; no outstanding source
fix is requested by this audit.

## Actual verification cost

One boundary-test execution used the existing
`Gaussian/.venv_nn/bin/python`. The wrapper recorded child-process CPU user and
system seconds with `resource.getrusage`, plus elapsed wall time. It includes
imports and process startup, rather than only the unittest runner's reported
time.

| Receipt | Tests | Wall seconds | CPU user seconds | CPU system seconds | CPU total seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `BOUNDARY_COST_RECEIPT_attempt_001.json` | 26 passed | 0.452341458 | 0.335051 | 0.083733 | 0.418784 |

The parent must append this measured ordinary CPU receipt to the experiment's
main cost ledger, including it in the source-work allowance. Embedded ledgers
inside temporary synthetic test roots are fixtures only and are nonadditive;
they must not be imported as actual experiment work. Actual physical,
Maxwell, full-wave-label, and NN counters are zero.

Detailed verification output is in `boundary_tests_attempt_001.log`; the
receipt is also retained in `BOUNDARY_COST_RECEIPTS.jsonl`. No boundary test
attempt failed.

## Limits and parent responsibilities

These checks exercise small helpers, cache contracts, refusal paths, and
mocked solver/CLI failures. They do not run a valid `freeze_scene`, a physical
background recovery, the 2112-case common reconstruction, the full replay,
reporting plots, or scientific gates. Source AST checks are bounded audits of
the inspected modules and complement runtime refusal checks; they are not a
formal proof of all transitive behavior.

The parent still owns the planned complete original A22 plus R1 suite,
physical normalization/provenance review, valid-cache reconstruction replay,
cost and failure-ledger integration, and final scientific interpretation.
