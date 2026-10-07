# Cached chart-exterior audit handoff

Implemented `src/a22_r1/chart_audit.py` and
`tests/test_a22_r1_chart_audit.py`. No common, replay, report, or old source was
changed. The final **11 synthetic tests passed**. One earlier test attempt
failed on JSON serialization of NumPy boolean identity flags; its log and cost
receipt are retained. The new helper converts those flags to ordinary booleans.

## Reusable result and raw outputs

```python
from a22_r1.chart_audit import build_chart_audit
result = build_chart_audit(root)
```

The function first requires the existing global `SPLIT_FREEZE.json` and all
four online manifests to be COMPLETE. It selects only `Q_spatial`,
`cell_volume`, and `anchor_chi` from online caches, the four original `truth`
members from `data/a22/offline_eval`, and material/coefficient members from
the 32 existing finite-label archives. It reads no observation data, AW,
direction scores, full J, reconstruction errors, or solution vectors.

The result and durable outputs are:

- `results/a22_r1/CHART_EXTERIOR_RAW.json`
- `results/a22_r1/CHART_EXTERIOR_RAW.csv`

They contain **36 rows**: one original material and eight finite labels for
each scene. JSON also includes `per_scene_summary`, explicit read counts,
decomposition conventions, and material recipe provenance. Matching existing
artifacts are reusable; different semantic content is refused. All writes
stay under `results/a22_r1`.

## Physical convention and identity checks

The cached chart has 16 real spatial columns with
`volume * Q.T * Q = I16`. Its 32 real material coefficients are ordered as
16 real then 16 imaginary coefficients. The audited material is the contrast
from the uniform known background:

`chi = chi0 + Q @ (x_real + i*x_imaginary) + chi_outside_W`.

The mass energy is `volume * sum(abs(chi - chi0)**2)`. The helper reports
coefficient and field energy, exterior mass energy/fraction, vector and energy
partition residuals, the real/imaginary mass inner product between retained
and exterior components, and the projection of exterior material back into
the chart. Zero-energy fractions remain undefined; no epsilon is used to
manufacture coverage.

For each finite label, the helper compares the projected full material with
stored total coefficients and checks the stored coefficient sum
`base_coefficients + perturbation_coefficients`. It reports perturbation
exterior energy and change in the original exterior component separately.
Declared algebra tolerances are absolute `1e-12` and relative `1e-9`; the
chart Gram defect must be at most `1e-9`. None are scientific screening gates.

The finite perturbed material is reconstructed from the cached generator
recipe: stored `original_material` plus Q expansion of stored perturbation
coefficients. A separate full perturbed material field was not cached. Thus
the perturbation confinement check verifies that recipe and coefficient
consistency, rather than independently remeasuring physical label generation.
That limitation is recorded in every finite row and the result metadata.

## Actual cached audit observations

The actual audit ran once after the completed barrier and returned COMPLETE
for all decomposition/material identities. Original-object energy coverage
was:

| Scene | Family | Retained in W | Outside W |
| --- | --- | ---: | ---: |
| 2001 | Gaussian | 0.464909699637 | 0.535090300363 |
| 2003 | Gaussian | 0.489802365730 | 0.510197634270 |
| 2014 | Asymmetric | 0.057653280568 | 0.942346719432 |
| 2009 | Shell | 0.133728329821 | 0.866271670179 |

Across the finite cached materials, the maximum stored-coefficient projection
error was `1.4746871413423452e-16`; the maximum exterior change mass norm was
`1.6578207823712529e-16`. Across all 36 decompositions, the maximum mass-energy
identity absolute residual was `2.220446049250313e-15`, and the maximum
projected exterior coefficient norm was `1.7667778419409373e-16`.

These are algebra and cache-consistency observations. The exterior mesh-space
energy is explicitly marked as distinct from any prior subspace inside W.
No reconstruction, split, recoverability score, scientific gate, or research
conclusion was produced by this helper.

## Verification and separate cost receipts

Synthetic checks cover analytic mass-energy conservation, real/imaginary
coordinate order, rotated orthonormal charts, zero-energy undefined fractions,
bad chart/layout/nonfinite rejection, the global capability barrier, selective
cache-member reads using deliberately unreadable unused fields, 36-row
completeness, immutable inputs/outputs, coefficient mismatch reporting, changed
material-center refusal, and idempotent artifacts.

Every execution used the existing `Gaussian/.venv_nn/bin/python`. Inclusive
child-process CPU includes imports and startup. The parent must import all
three distinct receipts, including the failed test attempt:

| Receipt | Outcome | Wall seconds | CPU user seconds | CPU system seconds | CPU total seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| `CHART_TEST_COST_RECEIPT_attempt_001.json` | 11 tests, 6 serialization errors | 0.494349000 | 0.369684 | 0.102452 | 0.472136 |
| `CHART_TEST_COST_RECEIPT_attempt_002.json` | 11 tests passed | 0.548247375 | 0.427510 | 0.109664 | 0.537174 |
| `CHART_AUDIT_COST_RECEIPT_attempt_001.json` | Cached audit COMPLETE, 36 rows | 0.285742458 | 0.234582 | 0.039298 | 0.273880 |
| Total | | 1.328338833 | 1.031776 | 0.251414 | 1.283190 |

`CHART_COST_RECEIPTS.jsonl` retains all three records. Logs are
`chart_tests_attempt_001.log`, `chart_tests_attempt_002.log`, and
`cached_chart_audit_attempt_001.log`. The first attempt belongs in the main
failure ledger as well as its cost ledger. The actual audit read four online
chart caches, four original material caches, and 32 finite-label caches.

Actual physical, Maxwell, new-full-wave-label, new-solve, new-score, and NN
counts are zero. The parent retains final gates, interpretation, reporting,
and ledger integration.
