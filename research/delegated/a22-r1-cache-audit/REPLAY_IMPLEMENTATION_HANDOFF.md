# A22-R1 cached replay handoff

Status: implementation complete; **not executed against experiment data by this worker**. The parent owns fixture authorization, actual execution, statistics, gates and scientific interpretation.

Only the requested implementation source was added: `src/a22_r1/replay.py`. Frozen `src/a22`, original Stage A data, scores and results were not modified. The initial cache audit and its missing-background-field finding remain the record of what was available before any corrective known-background rebuild.

## Entry point and required inputs

`run_replay(root, config, book) -> summary`

- `root` is the A22-R1 worktree directory.
- `config` is the parent's `configs/a22_r1.json`; `scenes` is supported, with `scene_ids` as an alternative spelling. k is frozen to `{16,8}`, with primary 16. The registered floor is `norm_floor=1e-6`; identity tolerance is `identity_rtol=1e-9`; reproduction tolerance scale is `reproduction_atol_scale=1e-8`.
- `book` supplies `span(name, **integer_counts)`, `check()` and a mutable `counts` mapping for the unchanged constrained solver. An optional `scope(role)` is used for cached evaluator reads and solves. No Maxwell operator/action is instantiated inside replay.
- All four `results/a22_r1/online/scene_{sid}.json` must have schema `a22_r1.online_freeze.v1`, status `COMPLETE`, and the frozen score contract `{amplitude:0, noise_level:1, intervention:nominal, orientation:ascending, tie_breaker:common_basis_index}`.
- Their NPZ files need `AW`, `background_field`, `Q_spatial`, `cell_volume`, `anchor_chi`, `whitening`, `sigma_complex`, `common_V`, `context_json`, `score_A1`, `score_A2`, `score_A3`. Optional `order_A1/A2/A3` are checked against stable ascending score order. `context_json` is a top-level JSON object with `declared_object_radius`.

The split worker confirmed those exact names. Its original validated `AW`, σ and λ retention is consistent with this replay. Replay also reads each scene's exact old full-scene λ and σ from the original online provenance; it never uses a λ based on the restricted operator.

## Boundary and ordering

1. Validate all four online cache receipts and each exact common basis `column_stack(old_split16.V_phys, old_split16.V_prior)`.
2. Freeze RANDOM/A1/A2/A3 orders and complementary vectors in `online/splits/scene_{sid}.npz` and `SPLIT_FREEZE.json` before reading old labels or old reconstruction errors.
3. RANDOM is exactly `default_rng(SeedSequence([20261910,sid])).permutation(32)` using `config.random_seed`; k8 and k16 use nested prefixes of the same order. A1/A2/A3 use raw frozen scores, ascending with candidate-index ties. No truth, error or calibrated score changes those rankings.
4. Optional OFFLINE_FULL_J is enabled by default. The cached `JF` computes the parent's preregistered regularized full-J budget at amplitude 0/noise 1 in the same candidate basis. It is frozen separately in `OFFLINE_SPLIT_FREEZE.json` before labels or errors are opened, and is marked offline/oracle only.
5. The direct evaluator readers `_freeze_offline_splits`, `_registered_rows`, `_load_label` also enforce the global online split receipt and all four scene completions. They cannot be called successfully before that boundary.
6. Load only the exact registered 2,112 case rows sorted by `stage_a_case_key`. Cached finite labels are reused for all their replicates. Replay uses the original calibration function, source-major pack, paired proper-complex noise seed and original noise reference.
7. Solve one common full 32D QP per case. All common solutions are checked against the original signed target error, absolute target error, total in-chart error norm and true target coefficient. Each absolute difference must be at most `1e-8*max(1,abs(saved material_error))`. Actual differences and flags are saved.
8. If any common QP is invalid or any reproduction comparison fails, persist the audit/vectors/failures and stop before Test B. The parent receives `ReplayReproductionError.result`; it must keep the scientific result incomplete.
9. After the complete common gate matches, each Test A metric uses that one saved common solution. Test B uses the same constrained solver with `basis=V_phys`, `lam=old_full_scene_lambda`, and a zero prior component. No full solve is repeated in this phase.

All immutable JSON/NPZ freezes reject pre-existing different content. A successful saved `REPLAY_SUMMARY.json` with the same config can be reused; failed attempts remain separate and are never overwritten. Every case checks the passed resource book. Invalid QPs remain terminal failures; no clipping, solver replacement or fallback occurs.

## Output paths and report API

Every attempt has a unique preserved directory `results/a22_r1/replay/<UTC_time>_<run_id>/` with:

- `REPLAY_CONTRACT.json`
- `COMMON_32D_CASES.jsonl` and `.csv` containing 32D estimate/truth vectors, signed/absolute target checks, total chart error, λ, material normal, QP/KKT/feasibility metadata and solve times
- `COMMON_32D_SOLUTIONS.npz` containing all vectors, case keys, status mask, λ, QP JSON and reproduction JSON; invalid vectors use NaN with an explicit status rather than a fake zero solution
- `COMMON_REPRODUCTION.json` with all comparison counts/max differences
- `PER_CASE_SPLIT_METRICS.jsonl` and `.csv`
- `RESTRICTED_SOLUTION_VECTORS.jsonl`, persisted after each restricted attempt
- `scene_{sid}_{method}_k{k}_RESTRICTED.npz` with 32D estimates/truth, k-dimensional physical coefficients, statuses, QP metadata, frozen split order/seed, λ and zero-prior marker
- `REPLAY_SUMMARY.json` for a completed execution or `ATTEMPT_FAILURE.json` on failure

The root `results/a22_r1/REPLAY_SUMMARY.json` exists only after completed execution. Execution `COMPLETE` does not mean a screening gate passed; `invalid_restricted_QPs` and per-group completeness remain mandatory report inputs. Root `FAILURE_LEDGER.jsonl` records both case failures and terminal run/contract failures.

Summary fields for the parent report:

| Field | Meaning |
|---|---|
| `case_metric_path`, `case_metric_csv` | Relative paths to all Test A/B per-case metrics |
| `full_solution_path` | One common 32D estimate per registered case |
| `restricted_vector_jsonl` | All physical-only vectors, including failures |
| `common_reproduction` | 2,112-case matching audit; must be MATCH before Test B |
| `expected_conditions` | Explicit 48 combinations of direction, amplitude level, noise and intervention |
| `expected_groups` | Explicit scene/method/k/test groups for missing-group detection |
| `common_32D_solves`, `restricted_physics_solves` | Attempt counts, not independent objects |
| `invalid_restricted_QPs` | Failed restricted solves that cannot enter valid means |
| `costs` | Split and overall replay wall/process CPU; construction cost is historical |

Methods are `RANDOM`, `A1`, `A2`, `A3`, `OFFLINE_FULL_J`. Tests are exactly `A`, `B`. Group/condition keys are `scene`, `method`, `k`, `test`, `direction`, `amplitude`, `noise`, `intervention`, `noise_draw`. Here `amplitude` is the registered level index 0/1; `physical_amplitude` preserves its real value. Original-key aliases are also retained.

Metric names are the metrics module's lowercase API: `nrmse_phys`, `nrmse_prior`, `s_sep`, `f_error_phys`, `f_error_prior`, `f_truth_phys`, `f_truth_prior`, `q_phys`, `q_prior`, norms/energies, floor flags, identity residuals and `undefined_reasons`. Test B additionally records `data_residual`, `prior_coefficient_norm`, `full_projection_nrmse_phys`, and `restricted_over_common_nrmse_phys`. Undefined ratios remain `None`.

With all five methods, each case has 20 metric rows: 5 methods × 2 k × 2 tests. The complete planned counts are 2,112 common QPs, 21,120 restricted QPs and 42,240 metric rows. These are small constrained quadratics and cached reads, with zero new object-label or Maxwell calls inside replay. The resource cap may still terminate the run; partial vectors and accounting remain preserved.

No aggregate scene statistics, bootstrap, gate judgment, NN, nonlinear solve, expansion or publication is implemented here. No SHA256 checks were run.
