# A22-R1 cache recomputation audit

Audit date: 2026-10-08. Worktree: `Gaussian/A22/a22-r1-subspace-separation`, based on the parent-declared frozen A22 commit `4dd4a9f`.

## Decision before any new physical action

**The saved A22 bundle does not yet support exact small-matrix-only replay of all 2,112 32D one-shot solutions.** The missing numerical quantity is the known-background predicted complex data

`y0 = anchor.state.field`, shape `(6,128)`, complex128, at `chi0 = 0.1 + 0.04i`.

Every frozen solve uses `d = whitening * pack(observation - y0)` (`src/a22/evaluate.py:430`). The cache saves `AW`, `MW`, `PMW`, finite observations, truth coefficients, σ, constraints and all noise seeds, but never saves `y0`, the whitened residual `d`, `AW.T @ d`, or the full 32D solution. No such background field/current was found in the local A22 artifact inventory. **No Maxwell action, material solve, new label, reconstruction-error calculation, or split selection was performed by this audit.**

For coefficient recovery alone, the missing 32-vector `AW.T @ whitening*pack(y0)` would suffice because the objective uses only `AW.T @ d`. The full `(6,128)` `y0` is the preferable replay artifact: it also permits the declared Test B data consistency residual. The scalar σ/RMS does not determine the phase or direction of this data vector.

The parent should first seek a saved field at the same material, mesh, frequency, source order and receiver geometry in an existing execution cache. If none exists, an unavoidable known-background prediction is a concrete missing-cache exception, not a request for new object labels. This audit documents that exception before any possible physical run. It does not authorize or run one.

## Local inventory and rejected substitutes

- Header-only inventory under `Gaussian/A22/` covered 2,136 `.npz` files in 16 schema families across the original implementation and this worktree. There is no member naming a known-background field/current or complete A22 anchor state.
- A22 Stage A final archives contain 4 `online_factors.npz`, 32 `OFFLINE_label_d{0..3}_a{0..1}.npz`, 4 `OFFLINE_J_benchmark.npz`, and 12 saved legacy splits. Resume factor archives contain more state/layout provenance, but no field/current.
- A22 `data/a22/online/scene_{sid}.npz` has only `points`, `data0`, `init`. `data0` is the original object observation, generated with declared `truth_n=14`; it is not the uniform-background response or the same-grid finite perturbation label. The frozen Stage A instead uses its saved finite `(6,128)` labels generated at `n=12`.
- A21 anatomy caches contain `r` and `data0`, which in principle can recover a field at their own state. The only five local A21 caches are `*_17.npz`; their materials differ from `chi0` by maximum magnitudes 0.2557–2.0202. They are not legal same-anchor substitutes. No `*_0.npz` anatomy state cache was found.
- The current-space `Q_current`, projected core, `S Q_current`, full injection factor, primal residual `IR`, and dual residual arrays are not recorded as A22 numerical cache members. `chart_Q` is the 16-column **material** chart, not `Q_current`.
- `AW/MW/PMW` encode tangent factor products. Recovering a projected receiver map from them, even if algebraically possible, does not certify `S Q_current Q_current* c0 = y0`. The full background current/output is not declared to lie in this fixed shallow basis. An approximate background subtraction would change the frozen one-shot solve and cannot serve as exact replay.
- `directional_reconstructions.npz` records one target coefficient and a total 32D error norm per case, with the explicit marker `full_solution_vectors = NOT_RECORDED; no spatial Stage B images were run`. Those scalars do not specify the remaining 31 coefficients. No inverse inference from reconstruction errors or truth is proposed.

Scope limitation: the audit checked local A22 artifact files and nearby package filenames. It did not inspect or retrieve a live remote process cache; any remote-only `y0` remains unverified.

## Required saved inputs

For each `sid` in `{2001,2003,2014,2009}`:

| Quantity | Actual path/member | Status |
|---|---|---|
| Frozen reduced material data map | `results/a22/stage_a/scene_{sid}/online_factors.npz::AW` | `(1536,32)`, float64, present |
| Three-fold injection/propagation products | same archive `MW`, `PMW` | `(6,32,32)`, complex128, present |
| Physical material basis | same archive `chart_Q` for 2003/2014/2009; for 2001 rebuild the frozen mesh-only chart from `data/a22/online/scene_2001.npz::points` | `(1728,16)`, float64 |
| Chart volume | same archive `cell_volume` for three current-contract scenes; known mesh/edge for legacy 2001 | `0.001953125` |
| Known background material | current-contract `anchor_material`, or frozen config and `init` | `(1728,)`, complex128 |
| σ and regularization | `online_provenance.json::anchor.sigma_complex_reference`, `descriptor.regularization` | present for all scenes |
| Finite clean observations | `OFFLINE_label_d{dir}_a{level}.npz::clean_data` | 8/scenes, `(6,128)` complex128 |
| True 32D chart coefficients | same label archive `coefficients` | `(32,)`, float64 |
| Perturbation metadata | same label archive `direction`, `nuisance`, `amplitude`, `perturbation_coefficients`, `source_order` | present |
| Original material for exterior audit | same label archive `original_material`; independently `data/a22/offline_eval/scene_{sid}.npz::truth` | `(1728,)`, complex128 |
| Physical calibration | `calibration_d{dir}_a{level}.json` | 6 source gains, 128 channel gains, present |
| Case identities and seeds | `results/a22/stage_a/direction_metrics.jsonl` | 2,112 unique registered rows, present |
| Known-background data | `anchor.state.field` | **NOT_RECORDED in local A22 caches** |
| Offline full-J diagnostic | `OFFLINE_J_benchmark.npz::JF` | `(1536,32)`, float64, present; evaluator only |

Scene 2001's final factor, labels, and `JF` caches use the legacy schemas. Scenes 2003/2014/2009 include `cache_schema=a22_stage_a_anchor_v1`, material/layout/geometry contracts and label backward residuals. Resume factors provide a current-contract provenance cross-check for 2001 without changing the original cached `AW`.

## Fixed material chart and constraints

The existing chart contains 16 real spatial columns: eight octant indicators plus eight centered x-sign detail functions. Let `Qm` be its spatial matrix and `vcell` the cell volume. `vcell * Qm.T @ Qm = I16`. Coordinates use the exact order `[16 real coefficients, 16 imaginary coefficients]`, and

`W x = Qm @ (x[:16] + i*x[16:])`.

No basis fitting or new normalization is needed. The legacy chart can be rebuilt exactly by `assets.fixed_patch_chart(points, volume)` (`src/a22/assets.py:121`). The full 32D basis in coefficient coordinates is the identity. The nonlinear pixel-material lower bounds reduce to the frozen linear constraint

`C x >= lower`, where `C = block_diag(Qm,Qm)` and `lower = concat(-0.5 - Re(chi0), -Im(chi0))`.

Thus all 3,456 original pixel inequalities remain the validation contract. Exact duplicate rows including their bounds can be removed for the optimizer only; first-occurrence order and the full inequalities remain in the final KKT/feasibility audit (`src/a22/core.py:144`).

The solve is the same SPD quadratic, with `H = AW.T @ AW + λ I32`, `g = -AW.T @ d`, and objective `0.5*x.T*H*x + g.T*x`. Its unconstrained branch is a direct SPD solve; otherwise it uses SLSQP with the same active-equation refinement and tolerances. Frozen values: `tikhonov_relative=1e-4`, feasibility/KKT relative tolerance `1e-8`, SLSQP `ftol=1e-16`, maximum iterations 200. No clipping, jitter, pseudoinverse or nonlinear material iteration is used (`src/a22/core.py:112`).

For Test B the solver already accepts `basis=V_phys` and `lam=...`. The default recomputes `λ = 1e-4 ||AW @ V_phys||₂²`; that changes with the split. To honor a comparison with the same full-scene regularization, supply the frozen full-scene λ explicitly. Record this as a protocol choice before recovery outputs are inspected.

| Scene | σ_complex_reference | Saved full-scene λ |
|---|---:|---:|
| 2001 | 7.175300851818394e-5 | 39970.28132448953 |
| 2003 | 7.173961684107208e-5 | 40321.322228950965 |
| 2014 | 7.175611516490669e-5 | 40510.39077571165 |
| 2009 | 7.177293919534872e-5 | 40445.83072241458 |

## Complete registered case grid

The identity is `(scene_id, direction_id, amplitude_level, noise_level, noise_draw, intervention)`, in this exact order (`evaluate.stage_a_case_key`). There are 528 cases per scene:

`4 directions × 2 amplitude levels × 2 interventions × (1 zero-noise draw + 16 level-1 draws + 16 level-3 draws)`.

The final JSONL has 2,112 unique identities, all with terminal `OK` status; each scene has 528. There are 64 zero-noise rows and 1,024 rows at each nonzero noise level. This is a complete replay set of four exposed scene clusters, not 2,112 independent objects.

Example identity: `2001|0|0|0.0|0|nominal`. Its amplitude is `0.02234479482419223`; candidate index 32; seed string `20261007:2001:0:0:0:661`. The corresponding clean label is `scene_2001/OFFLINE_label_d0_a0.npz`.

The 4 finite perturbation directions and 2 physical amplitudes have already been frozen and stored. Recovering case data should load their saved values, not rerun direction selection or perturbation generation. For a provenance cross-check only, the nuisance seed is `[20261007, sid, direction_id, 511]`; the unit nuisance vector is orthogonalized against the chosen material direction; the joint perturbation is `amplitude*(direction + 0.35*nuisance)` (`src/a22/evaluate.py:355`). The true coordinates already include the original object's in-chart component, not just the added perturbation.

## Exact observation replay

For each cached raw finite label `raw`:

1. Nominal clean data is `raw`.
2. Calibration clean data is `raw * source_scale[:,None] * receiver_scale[None,:]`, using the saved JSON or the frozen analytic gains:
   `source_scale[p] = 1 + 0.05*cos(2π*(p+0.25)/6)`;
   `receiver_scale[m] = 1 + 0.03*sin(2π*(m+0.125)/128)`.
   The 128 entries refer to packed complex receiver channels, including both polarizations. There is no additional forward solve.
3. Initialize `default_rng(SeedSequence([20261007, sid, direction_id, amplitude_level, draw, 661]))`.
4. Draw the real normal array first, then the imaginary normal array, each `(6,128)`. Add
   `noise_level*σ/sqrt(2) * (normal_real + i*normal_imag)`.
5. Subtract the nominal known-background `y0` exactly as the frozen code does. It is not transformed by the evaluator's calibration gains.
6. Pack source-major with all 128 real channels followed by all 128 imaginary channels for each source; multiply by `sqrt(2)/σ`. The result is `(1536,)`, float64.

The seed omits **both intervention and noise_level**. The same standard normal realization is shared by nominal/calibration and by levels 1/3; the latter scale one realization by 1 and 3. Noise level 0 has draw 0 only. Noise-free draws are still instantiated in the original implementation but multiplied by zero. This pairing must remain unchanged.

The audit checked seed/case metadata and formulas, not numerical reconstruction errors. After the split definitions are frozen, exact replay should be verified against the saved per-case signed target error, total in-chart material error, feasibility and KKT metadata. Such verification must not choose or tune a split.

## Chart-exterior reporting inputs

`true_coeff` in each label equals `project(original_material - chi0) + perturbation_coefficients`. Define

`outside = original_material - chi0 - W*project(original_material - chi0)`.

All registered perturbations lie in W, so `outside` is unchanged across these cases. Per-case total truth energy is `||true_coeff||² + vcell*||outside||²`; original-object retention fractions below are baseline context and need not equal the perturbed case's fraction.

| Scene/family | Original perturbation norm | Exterior norm | Original retained energy fraction |
|---|---:|---:|---:|
| 2001 Gaussian | 0.26999967527875135 | 0.19750440265659228 | 0.46490969963671186 |
| 2003 Gaussian | 0.9826591374026865 | 0.7018949489533073 | 0.48980236572980707 |
| 2014 asymmetric | 0.3819534926938811 | 0.37077961332177806 | 0.057653280567735034 |
| 2009 shell | 0.6359136412907712 | 0.5918684596342699 | 0.13372832982105157 |

Source: saved per-scene `OFFLINE_material_model_audit.json`. Each original center violates the descriptor's declared 0.25 pointwise material budget; keep that existing limitation visible. This is an empirical exposed-data screening, not a validated finite-region certificate.

For a chart-only reconstruction, physical squared full-grid error decomposes as `||x_hat - true_coeff||² + exterior_norm²` by physical orthogonality. Exterior energy belongs in its separate audit; it must never be assigned to `V_prior` inside the declared 32D chart.

## Runtime evidence and cost limits

Historical construction/solve timings are recorded in `results/a22/COST_LEDGER.jsonl` and its `cost_ledger.csv` export. These are historical GPU-screen span records, not newly measured cached CPU replay timings. OPM-construction spans are nested around material-factor actions, so their wall times must not be added together as independent resource charges.

For `a22-cuda-screen-003`, the four recorded inclusive anchor span walls are 7.5096, 10.2256, 10.1768, 10.1563 seconds (ledger lines 1185,1533,2219,2905). The four fixed-shallow-OPM span walls are 5.8346,6.3639,6.3204,5.9785 seconds (lines 1214,1562,2248,2934). The corresponding factor-action span walls are 0.2405,0.3076,0.2294,0.2392 seconds (lines 1213,1561,2247,2933). Descriptor-residual spans are separately recorded around 2.79–2.87 seconds.

The screening material-subproblem spans occur across preserved attempts: 210 in screen-001, 129 in screen-002 and 1,775 in screen-003. This includes the two failed attempts beyond 2,112 final valid cases; do not discard their cost. The screen-003 individual material span median is 0.1522 seconds, range 0.004883–0.238300. It is not a cached local end-to-end runtime measurement and cannot prove deployment speedup.

Preserve authoritative inclusive job/external receipts and excluded overlapping spans using `src/a22/cost_summary.py`. A22-R1 should measure cache loading/replay, split selection, each small material solve and total cached one-shot time locally, separately from historical OPM construction. No runtime claim is justified by retained rank alone.

## Actionable gaps

1. **Blocking exact common reconstruction replay:** missing `y0` or an equivalent saved projected RHS. A same-anchor cache recovery or documented unavoidable known-background prediction is needed; do not regenerate finite object labels.
2. **A3 descriptor replay for 32 canonical candidates:** final cached A22 descriptor outputs cover the frozen selected direction set, while primal/dual residual matrices and complete descriptor context are not saved. AW/MW/PMW alone do not supply the strong frozen A2/A3 budgets for every new candidate. This is a separate descriptor-cache gap for parent review; no redesign is proposed.
3. **Legacy numerical provenance:** scene 2001 labels have no stored backward residual/current explicit state contract; preserve `LEGACY_NOT_RECORDED` and existing resume validation rather than fabricate a value.
4. **Runtime:** cached A22-R1 split/solve/total timing is not recorded by Stage A. It must be measured when actual replay runs.

The companion `CACHE_SCHEMA_AND_GAPS.json` contains the audited archive member schemas, case-key example, scene scalars and gap statuses. No SHA256/integrity hash was computed.
