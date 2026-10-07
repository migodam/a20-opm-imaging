# A22-R1 metrics and synthetic checks

Implemented the three diagnostic functions in `src/a22_r1/metrics.py` and
synthetic-only checks in `tests/test_a22_r1_metrics.py`. A minimal package
`src/a22_r1/__init__.py` was added. No old source was changed. No experiment
truth, error, data, material, or Maxwell cache was opened. No physical action,
new full-wave label, nonlinear solve, NN run, or hash check was performed.

The final verification ran **25 synthetic tests; all passed**. This verifies
metric and aggregation behavior on constructed fixtures only. It does not
support any scientific separation claim, screening gate, or expansion.

## Metric API

```python
subspace_metrics(
    x_hat, x_true, v_phys, v_prior,
    norm_floor=1e-6, orthonormal_atol=1e-9,
)
```

The arguments are real coefficient arrays in the existing mass-orthonormal
32D material chart. `x_hat` and `x_true` are shape `(32,)`, `v_phys` is
`(32,k)`, and `v_prior` is `(32,32-k)`. The supplied bases must be orthonormal
complements. Complex, nonfinite, incorrectly shaped, or noncomplementary
inputs are rejected. The code assumes the caller already verified physical
normalization of the fixed chart; it never reads or changes W.

The result is a plain dictionary of Python scalars and a reason dictionary.
Undefined ratios use `None`, and ordinary outputs serialize with strict JSON
without NaN or Infinity. A declared positive norm floor changes only NRMSE
denominators. A flag is active when the raw subspace truth norm is strictly
below the floor. Raw energy fractions and q never use an added epsilon.

| Fields | Meaning |
| --- | --- |
| `nrmse_phys`, `nrmse_prior` | Error norm divided by the corresponding raw truth norm or the declared floor |
| `s_sep` | Prior NRMSE / physics NRMSE; undefined when physics NRMSE is zero |
| `f_error_phys`, `f_error_prior` | Raw subspace error energy / total in-chart error energy |
| `f_truth_phys`, `f_truth_prior` | Raw subspace truth energy / total in-chart truth energy |
| `q_phys`, `q_prior` | Raw error fraction / corresponding raw truth fraction; undefined for zero truth fraction or an undefined raw fraction |
| `error_norm`, `error_phys_norm`, `error_prior_norm` | Common in-chart error and projected error norms |
| `truth_norm`, `truth_phys_norm`, `truth_prior_norm` | Raw common and projected truth norms |
| Corresponding `_energy` fields | Squares of those norms, without a normalization floor |
| `norm_floor`, `floor_phys_active`, `floor_prior_active` | Explicit normalization-floor declaration and activation flags |
| `nrmse_phys_denominator`, `nrmse_prior_denominator` | Denominators actually used by the NRMSE calculations |
| `basis_orthonormality_residual`, `projector_completeness_residual` | Frobenius norm of the joint Gram defect and of P_phys + P_prior - I |
| `signal_projection_identity_residual`, `error_projection_identity_residual` | Norm of the projected-vector partition defect |
| `signal_energy_identity_residual`, `error_energy_identity_residual` | Absolute projected-energy partition defect |
| `q_identity_applicable`, `q_identity_residual` | Applicability and absolute defect of S_sep² = q_prior / q_phys, evaluated only when both floors are inactive and the required ratios are defined |
| `q_identity_s_sep_squared`, `q_identity_q_prior_over_q_phys` | The two quantities used for that identity audit |
| `undefined_reasons` | Explicit reasons for each unavailable ratio or q identity |

`chart_dimension`, `k`, and `prior_dimension` are included. Test A supplies
the common full estimate. Test B supplies its restricted estimate and retains
its separate caller test label. Nothing in this module fills the prior branch.
A constructed restricted-estimate test confirms prior NRMSE = 1 when omitted
prior truth has nonzero signal and the floor is inactive.

## Hierarchical averaging API

```python
hierarchical_scene_average(
    rows,
    metric_names=("nrmse_phys", "nrmse_prior", "s_sep", "f_error_prior",
                  "f_truth_phys", "q_phys", "q_prior"),
    expected_conditions=frozen_48_conditions,
    expected_noise_draws={0.0: 1, 0.1: 16},
    expected_groups=frozen_scene_method_k_test_groups,
)
```

Each input row requires `scene`, `direction`, `amplitude`, `noise`,
`intervention`, `method`, `k`, `test`, and `noise_draw`. Metric values can be
flat fields or reside in `row["metrics"]`. Per-condition means first average
the noise draws within the full scene/direction/amplitude/noise/intervention/
method/k/test key. The per-scene row is then the mean of **48 equally weighted
conditions**. Ratios are averaged as requested per-case metrics; they are not
recomputed from averaged energies. That reporting convention must match the
parent's preregistration.

Explicit expected conditions are exactly 48 unique condition dictionaries or
four-tuples of direction/amplitude/noise/intervention. Explicit expected
groups enumerate scene/method/k/test dictionaries. They detect entirely absent
conditions or groups. If omitted, observed unions are used and this inference
is disclosed in the audit; the required count remains 48, so a union of only
47 conditions cannot appear complete. The default draw count is one for a
noiseless condition and 16 for another noise level. Explicit count mappings
are preferred for integration. Draw-count checks do not validate frozen seed
identities; those remain the replay caller's responsibility.

No replicate or condition is silently filtered. Missing draws, excess draws,
duplicate draw identifiers, failed rows, and unexpected conditions invalidate
all metrics for the affected scene group. An undefined or nonfinite metric
invalidates that metric's scene mean, even if other metrics remain defined.
The returned `condition_rows`, `scene_rows`, and `audit` expose all relevant
missing, failure, duplicate, excess, and undefined counts. No unavailable value
is replaced by a successful average.

Status is absent/`ok` by default. The successful status whitelist is `ok`,
`success`, `complete`, `completed`, `valid`, `ran`, `run`, `pass`, without case
sensitivity. Any other state or a true `failed` / false `success` flag remains
failed in the audit, including NumPy boolean flags.

## Paired scene bootstrap API

```python
paired_scene_bootstrap(
    a3_nrmse_by_scene, a2_nrmse_by_scene,
    expected_scenes=(2001, 2003, 2014, 2009),
)
```

Inputs are scalar scene means, never replicate arrays. Exactly four scene
clusters are required. The function resamples paired scene indices only and
enforces **2000 resamples with seed 20261911**. Positive `mean_difference`
means mean(A2 NRMSE) - mean(A3 NRMSE) is positive. The primary relative estimate
is `relative_improvement_of_means = 1 - mean(A3)/mean(A2)`. The function also
returns the distinct mean and median paired per-scene relative improvements,
without silently substituting one convention for another.

Percentile 95% intervals are returned for the difference and relative
improvement of means. Missing or undefined scene means disable the summary
and interval instead of dropping the scene. Cluster-count and missing-pair
counts are explicit. A zero baseline mean makes its relative quantity
undefined. If any bootstrap sample has zero A2 mean, the entire relative
interval remains unavailable; no such sample is filtered. The difference
interval remains defined.

## Synthetic verification coverage

- Known analytic separation: physics/prior NRMSE 0.1/0.4, S_sep 4,
  q_phys 2/17, q_prior 32/17, and energy coverage 1/2.
- Energy, vector, and projector completeness in random rotated orthonormal
  32D charts for k=8 and k=16.
- Frozen random coordinate subsets reproduce direct coordinate projections.
- Empty subspace signal, empty total signal, zero error, and zero physics
  error preserve the appropriate undefined fractions and ratios.
- Below-floor and exact-floor behavior flags the denominator rule while
  retaining raw truth fractions and q.
- A restricted estimate with prior coefficients left zero yields the expected
  prior error and independent physics recovery metric.
- Rotations inside either fixed subspace preserve the primary metrics.
- Invalid chart dimensions, complex and nonfinite values, malformed bases,
  and invalid normalization floors are rejected.
- One noiseless draw and 16 noisy draws contribute equal condition weights;
  draw-level weighting produces a different answer and is explicitly rejected
  by the expected fixture value.
- Missing draws, missing whole conditions/groups, duplicates, failed rows,
  unknown statuses, NumPy failure flags, and undefined values cannot produce a
  complete scene.
- Paired bootstrap intervals exactly match an independent four-index synthetic
  construction and repeat deterministically. Replicate arrays, changed seed,
  changed resample count, and nonfinite NRMSE values are rejected.

## Actual cost receipts

Both attempts used the existing `Gaussian/.venv_nn/bin/python`. Receipts
measure subprocess elapsed wall time and child process user/system CPU time
via `resource.getrusage`; these are ordinary CPU costs and must be appended to
the parent experiment's cost ledger. The first successful run covered 24
checks. The second followed the status-handling review correction and covered
25 checks. There were no failed test attempts.

| Attempt | Tests | Wall seconds | CPU user seconds | CPU system seconds | CPU total seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 001 | 24 passed | 0.189412375 | 0.102077 | 0.026561 | 0.128638 |
| 002 | 25 passed | 0.156608500 | 0.106124 | 0.020229 | 0.126353 |
| Total | | 0.346020875 | 0.208201 | 0.046790 | 0.254991 |

Detailed records are in `COST_RECEIPTS.jsonl`,
`COST_RECEIPT_attempt_001.json`, and `COST_RECEIPT_attempt_002.json`; logs are
`synthetic_tests_attempt_001.log` and `synthetic_tests_attempt_002.log`.

All physical, Maxwell, full-wave-label, and NN counters are zero. The parent
retains split definitions, source provenance, physical chart normalization,
condition/seed identities, data consistency, chart-exterior audit, gate
thresholds, and final scientific interpretation. No further scientific
decision was made by this worker.
