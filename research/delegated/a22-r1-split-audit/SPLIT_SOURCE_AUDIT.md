# A22-R1 frozen split-source audit

Audit date: 2026-10-08. Experiment root: `/Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/a22-r1-subspace-separation`.

This is a source and online-cache audit, not a scientific gate decision. It read frozen source, protocol, configuration, online provenance, direction definitions and budget definitions. NPZ inventory read member headers only. It did not open truth arrays, reconstruction errors, directional results, fitted calibration scales or offline Jacobian values. No Maxwell action, forward solve, NN, frozen-source modification, integrity hash check or numerical experiment was performed. During the read-only audit only this report was written. A later, separate parent assignment added the online driver described below.

## Findings that affect the experiment

1. The material chart is exactly 32 real volume-normalized patch coordinates. It is not a learned chart and is not the 32-column current basis.
2. Every saved `online_split_16.npz` contains a complete signed AW-SVD material frame through the concatenation `[V_phys, V_prior]`. This is an existing transformed 32D basis that can be frozen unchanged as the common candidate frame, if the parent elects to use it. The original canonical chart axes are also available through the chart definition.
3. Stage A saved eight selected direction descriptors, not 32. Only the first four selected directions received complete finite-amplitude budgets. Eight JSON budget rows mean four directions times two amplitudes, not eight independent directions.
4. The saved split is a generic AW-SVD split. `build_split` does not sort by A1, A2 or A3. Reusing that same saved split as all three methods would not test incremental split selection.
5. A1/A2/A3 in the frozen executable implementation are absolute coefficient-error budgets, conditional on amplitude, noise level and intervention. No unique A1/A2/A3 ranking operation is implemented. A parent must preregister how to take those existing scalar budgets into a ranking before opening outcomes. Lower budgets mean better predicted recoverability. `profile_g` and attribution, in contrast, have the higher-is-better orientation.
6. AW suffices to recompute frozen A1 quantities for any fixed 32 candidate directions. AW/MW/PMW suffice for the alpha/beta/gamma signatures. Those factors do not suffice for the exact frozen A2/A3 budgets: omitted primal/dual residual maps and known-anchor field-dependent quantities were not saved.
7. The old eight direction norms cannot identify the missing 32-direction residual behavior. Reconstructing an A2/A3 score from alpha/beta/gamma alone, from an interpolation of the old eight budgets, or from full J would change the method or breach the online boundary.
8. Test B needs an explicit full-AW lambda argument. The existing generic restricted solve otherwise recomputes lambda from the restricted operator, making regularization depend on the split.

## Exact fixed material chart and coordinate orientation

`src/a22/assets.py:120-160` defines the chart from mesh geometry alone:

- Divide cells into eight octants about the bounding-box center. The octant index is `4*x_bit + 2*y_bit + z_bit`.
- Spatial columns 0 through 7 are positive, normalized octant indicators.
- Spatial columns 8 through 15 are centered x-sign details within the corresponding octant. The positive sign is the high-x half. Each detail has its mean removed and its Euclidean norm set to one.
- Let this 16-column Euclidean-orthonormal matrix be H. The saved spatial chart is `Q_patch = H / sqrt(cell_volume)` and satisfies `cell_volume * Q_patch.T @ Q_patch = I_16`.
- The real material coordinate ordering is `[16 real coefficients, 16 imaginary coefficients]`, with coarse real indices 0-7, detail real indices 8-15, coarse imaginary indices 16-23, and detail imaginary indices 24-31.

`MaterialChart.expand` and `project`, in `src/a20/backend.py:41-68`, give the exact physical maps:

\[
\Delta\chi=Q_{\rm patch}(x_{0:16}+i x_{16:32}),\qquad
x={\rm cell\_volume}\,[\Re(Q_{\rm patch}^{T}\Delta\chi),\Im(Q_{\rm patch}^{T}\Delta\chi)].
\]

Thus `cell_volume * ||Delta_chi||^2 = ||x||^2` for in-chart material. The physical real-linear material basis is `[Q_patch, i Q_patch]`; the corresponding basis in declared 32-coordinate space is `I_32`. `material_features` uses this identity by default (`src/a22/online.py:299-305`). The `W` argument to that function is a coordinate transform, while `Q_patch` is the spatial expansion map. Neither is the current-space basis `model.basis`.

Every online provenance file reports eight octants of 216 cells each, chart dimension 32, and geometry-only chart construction. Three primary factor archives store `chart_Q(1728,16)` explicitly. Scene 2001's primary factor archive is legacy and lacks chart/geometry members, but its two preserved `resume_audits/*/regenerated_online_factors.npz` files have the full chart contract. Use those existing chart members after checking their declared online identity; recreating a learned chart is unnecessary.

### Existing transformed candidate frame

`src/a22/core.py:55-95` computes an SVD of real whitened AW, sets `V = Vt.T`, and makes each column's largest-magnitude entry positive. It stores `V[:, :r]` and `V[:, r:]`. `src/a22/evaluate.py:520-537` writes these arrays to `online_split_r.npz`.

For each scene, the existing `online_split_16.npz` holds `V_phys(32,16)` and `V_prior(32,16)`. Their concatenation supplies all 32 signed columns in original singular-value order. The candidate direction for column j is that stored material-coordinate vector; its physical lift is the declared patch expansion of that vector. This transform is scene-specific and online-derived, but all split methods can rank the exact same stored 32 columns within a scene.

The saved frame should be reused exactly if selected. Recomputing an SVD needlessly risks a different orientation inside a nearly degenerate singular block. Deterministic column signs alone do not make a degenerate SVD frame unique. Selecting different columns inside such a block can produce different projectors; that sensitivity must be reported, not silently corrected with outcome information.

## Eight descriptors versus 32 candidates

`src/a22/core.py:187-210` creates a 36-direction pool:

- 32 canonical chart axes;
- AW right singular vectors at indices 0, 7, 15 and 31, recorded with candidate indices 32, 33, 34 and 35.

It chooses strata from strongest/weakest total gain and highest/lowest attribution, then coarse/detail and SVD controls. Duplicate antipodal directions are removed using `abs(v @ u) > 1 - 1e-10`. Ties in the extrema use candidate index. It stops after the configured count of eight. The `descriptors` parameter is unused.

`configs/a22.json:35-37` freezes eight descriptors and four finite screening directions. `evaluate.py:480-481` computes only those eight descriptors. `evaluate.py:511-519` saves a reduced set of fields, not the complete dictionary returned by `direction_descriptor`. `evaluate.py:390-416` computes complete budgets for only the first four directions, at two amplitudes, three noise levels and two interventions.

Observed online inventory:

| Scene | Eight selected candidate indices, in saved order | Number of full budget directions |
|---|---|---:|
| 2001 | 32, 35, 22, 0, 8, 1, 2, 3 | 4 |
| 2003 | 32, 35, 3, 0, 8, 1, 2, 4 | 4 |
| 2014 | 32, 35, 33, 6, 0, 8, 1, 2 | 4 |
| 2009 | 32, 35, 33, 21, 0, 8, 1, 2 | 4 |

Each direction JSON saves only `v`, IDs/origin, alpha/beta/gamma, `profile_g`, attribution, `dual_defect_norm`, and `IR_direction_norm`, plus no-label/no-full-J flags. It does not save nuisance residual norms, regularized witness vectors, psi norms, adjoint coefficient norms, external pullback norms or background calibration correlations.

None of the four scenes has 32 complete saved A1/A2/A3 budgets. The eight selected directions are a descriptive stratified sample; they are not an orthonormal 32D basis.

## Frozen descriptor and nuisance definition

The source of record for the executable descriptor is `src/a22/features.py:156-216`. Every direction is normalized in the same Euclidean material metric. `profiled_witness`, in `src/a22/core.py:11-41`, uses the complete 31D orthogonal complement `N = null_space(v[None, :])` when no nuisance basis is supplied. It profiles `K = AW @ N` with a numerical-range SVD, using relative tolerance `1e-10`. It does not remove noisy nuisance modes.

The diagnostic `profile_g` is

\[
g=\|(I-U_K U_K^T)Av\|,
\qquad {\rm attribution}=g/\|Av\|,
\]

where `A = AW` and `U_K` spans the numerical range of `AN`. These are conditional on the declared complete in-chart nuisance space. Replacing N by only the chosen prior complement, or rebuilding N after ranking, would change the frozen directional descriptor.

The A1-A3 budgets use a common **regularized** witness, not the unregularized profiled witness:

\[
h=A(A^TA+\lambda I_{32})^{-1}v,\qquad b=A^Th-v.
\]

They retain target bias `|b.T @ v|` and complete-complement bias `||N.T @ b||`. An unidentifiable profiled direction is flagged by the descriptor, but the common regularized budget can remain finite. A finite budget therefore is not a certificate of arbitrary-nuisance unbiased identifiability.

The alpha/beta/gamma signature is obtained from six complex source blocks:

\[
\alpha=\|MWv\|,\qquad\beta=\|PMWv\|/\|MWv\|,
\qquad\gamma=\|Av\|/\|PMWv\|.
\]

The two current norms are Euclidean in `current = dipole / sqrt(cell_volume)`. AW is real, source-major and whitened after data packing. The proper-complex noise convention is `E|n|^2 = sigma_complex_reference^2`; each real channel has half that variance. Whitening is `sqrt(2)/sigma_complex_reference`. The scalar noise setting in `predict_budget` is the relative noise multiplier 0, 1 or 3, so real white-channel standard deviation becomes that multiplier. All `pred_A*` values have absolute material coefficient units.

Zero factor denominators return undefined values and explicit branches. There is no epsilon-generated recoverability score. A1/A2/A3 use empirical indicators; the source explicitly refuses a full-model uniform certificate.

## Exact executable A1/A2/A3 budgets

`src/a22/features.py:219-278` is the complete formula source. This is more specific than `protocol/a22/LIGHTWEIGHT_EXPERIMENT_SPEC.md:43`, whose shorthand calls A1 a nuisance-profiled gain. The implemented A1 is the common regularized witness's noise-plus-attribution-bias budget. The parent should explicitly identify which existing executable scalar it uses; the audit does not choose between that budget and `profile_g`.

For concise notation, let:

- a be the absolute registered amplitude;
- eta be the frozen nuisance fraction 0.35;
- r0 be the declared object radius from the 0.25 pointwise prior;
- delta be the saved positive full-L lower-bound indicator, or the existing fallback divisor 1 if that lower bound is unavailable;
- t be the noise multiplier;
- R be `_polar_remainder_radius(context, a*sqrt(1+eta^2))['bound']`;
- IR be `B - L Q_current PMW`;
- psi, dual and c be `_dual_residual(context, h)`.

The source computes:

\[
\begin{aligned}
n&=t\|h\|,\\
B_{\rm bias}&=r_0\|b\|+a\bigl(|b^Tv|+\eta\|N^Tb\|\bigr),\\
I&=r_0\|IR\|_{\mathbb R\to\mathbb C}+a\bigl(\|IRv\|+\eta\|IRN\|_{\mathbb R\to\mathbb C}\bigr),\\
R_2&=\|h\|\,O_{\rm defect}\,I/\delta,\\
R_3&=\|{\rm dual}\|\,I/\delta,\\
L_2&=\|h\|\,\|S_{\rm white}\|\,R/\delta,\\
L_3&=(\|\psi\|+\|{\rm dual}\|/\delta)R.
\end{aligned}
\]

Here the ROM norm uses a real-to-complex material map, implemented by stacking real and imaginary output blocks before computing its spectral norm. The source's observation-defect bound is

\[
O_{\rm defect}=\|S_{\rm white}\|+\|S_{\rm white}Q\|\,\|P\|\,\|L^*Q\|.
\]

The external-chart budgets, which remain in the frozen score even though evaluation will report chart-exterior error separately, are

\[
E_2=\|h\|\,\|S_{\rm white}\|\,B_{\rm voxel}\,r_0/\delta,
\qquad
E_3=(\|g_{\rm outside}\|+B_{\rm voxel}\|{\rm dual}\|/\delta)r_0.
\]

Calibration intervention multiplies these two external budgets by 1.0815. Its additional frozen factor budgets are `fac2` and `fac3` in `features.py:251-257`; both are zero for nominal data. They use epsM=`0.05*material_norm`, epsO=`0.03*observation_norm`, rho=`r0 + a*sqrt(1+eta^2)`, adjoint coefficient norm, propagation norms and background source/receiver correlations. Actual intervention signs are excluded from the descriptor.

Finally:

\[
\begin{aligned}
{\tt pred\_A1}&=\sqrt{n^2+B_{\rm bias}^2},\\
{\tt pred\_A2}&=\sqrt{n^2+(B_{\rm bias}+R_2+L_2+F_2+E_2)^2},\\
{\tt pred\_A3}&=\sqrt{n^2+(B_{\rm bias}+R_3+L_3+F_3+E_3)^2}.
\end{aligned}
\]

A2/A3 return `None` if the nonlinear bound is unavailable. The rank policy must not silently turn a missing indicator into a favorable score.

### Conditions still needing a ranking freeze

The existing budget is a function of direction, amplitude, noise and intervention. The implementation does not aggregate that function into one scene ranking. Existing amplitudes are direction-dependent: `_registered_perturbation` (`evaluate.py:355-374`) generates a nuisance direction from `[master_seed, scene_id, direction_id, 511]`, uses `v + 0.35*n`, and computes a feasible maximum from chart amplitudes and material constraints. Its two fractions 0.2 and 1.0 therefore do not denote the same physical amplitude across different directions.

For a fair common-frame comparison, the parent must freeze the score context or frozen aggregation rule and tie rule before results. This is a definition of how an existing score is used, not authority to tune or create a new score. No rank choice is justified by reconstruction outcomes.

Within any fixed method and score context, the source's scalar calibration is one nonnegative zero-intercept multiplicative coefficient (`src/a22/statistics.py:1-6,97-125`). A strictly positive coefficient leaves the within-scene direction order unchanged; a zero coefficient destroys that order through ties. Fitted calibration outcomes were not inspected and are not needed to audit ranking orientation.

## What is actually cached

For all four scenes:

| Artifact | Saved members relevant to the audit | What it supports |
|---|---|---|
| `online_factors.npz` | AW(1536,32), MW(6,32,32), PMW(6,32,32) | A1 witness/bias/noise quantities; alpha/beta/gamma; generic AW-SVD frame |
| Factor cache contract, when present | geometry, `chart_Q`, uniform anchor material, whitening, layouts, config | Exact fixed chart and geometry identity; no saved anchor state |
| `online_split_16.npz` | V_phys(32,16), V_prior(32,16), D(16,1536) | Full signed transformed 32D candidate frame; old profiled linear decoder |
| `frozen_online_directions.json` | Eight vectors and partial descriptor norms | Verifiable old sampled directions only |
| `frozen_online_budgets.json` | Four directions x two amplitudes x six contexts | Exact old scores only in those registered contexts |
| `online_provenance.json` | lambda, declared radius, full-L margin and F bound, units and source declarations | Several common scalar parameters; not a descriptor-context snapshot |

The main scene 2001 factor archive has only AW/MW/PMW. The other three have the full known-anchor layout contract. Both scene 2001 regenerated factor archives also have that contract. None of the primary or regenerated factor archives contains `Q_current`, `B`, `IR`, `LQ`, `L_adjoint_Q`, the reduced core, `SQ`, the full background state, exciting fields or the full `DescriptorContext`.

The online source NPZ files contain only `points(1728,3)`, `data0(6,128)` and `init(1728)`. `data0` is measured scene data, not the known-background prediction and not the exciting field. No data values were loaded in this audit. It must not be substituted for the missing known-background field.

## Minimum missing information for exact A2/A3 evaluation

The obstacle is not the missing Stage A full 32D solution vector. The material solution can be recomputed separately from A and data once the background-subtracted whitened residual is available. The split-score obstacle is the discarded descriptor residual information.

The exact existing evaluator needs the following missing directional quantities for every chosen candidate, together with missing shared norms. Either the original cached maps or equivalent exact sufficient statistics would work; sampled scalar norms do not.

| Missing quantity | Required by | Original operation/source |
|---|---|---|
| `||IR v||`, `||IR N||`, and shared `||IR||` for a complete 32-candidate frame | A2 and A3 ROM term | `features.py:51-57,178-179,208,231` |
| `||dual(h)||` | A3 ROM, nonlinear and external terms | `features.py:102-110,173,206,235,242,247` |
| `||psi(h)||` | A3 nonlinear term | `features.py:102-110,206,242` |
| `||adj_coeff(h)||` | A3 calibration factor term | `features.py:107,207,255` |
| `||outside(B_voxel^* psi)||` | A3 external-chart term | `features.py:181-189,213,246-247` |
| Known-anchor per-cell `sum_{source,component}|exciting|^2 / volume` | Frozen polarizability/nonlinear remainder R | `features.py:113-153` |
| Background whitened prediction and its witness source/receiver correlations | Calibration factor terms | `features.py:193-211,252-257` |
| Shared observation/core/residual/geometric norm factors and voxel injection norm | A2/A3 normalization, nonlinear and factor terms | `features.py:54-77,234-255` |

The explicitly absent `DescriptorContext` scalar fields are `injection_defect_norm`, `observation_norm`, `full_observation_norm`, `observation_defect_norm_bound`, `propagation_norm`, `Goff_norm_bound` and `voxel_injection_norm`. Some scalar products could potentially be recovered algebraically from sampled budget components; that does not recover the missing directional maps. Material and propagated norms can be recomputed from MW/PMW. Lambda, r0, F bound and the full-L margin are explicitly saved. P and O may be inferable from MW/PMW/AW if the necessary factor ranks permit it; they are not explicitly saved, and recovering them still does not recover omitted primal/dual paths.

An exact real Gram matrix for the IR map would be enough for all its target/complement norm queries. Corresponding exact norm maps on the regularized witness's 32-dimensional span would suffice for the dual, psi, adjoint-coefficient and exterior-pullback norms. These are alternative cache representations of the same frozen formulas, not new scores. Such maps are absent. The audit does not implement or validate a conversion.

Eight values `||IR v||` impose only eight quadratic constraints on an unknown 32D norm map. The full symmetric Gram matrix has 528 independent entries; the spectral norms of its restrictions to 31D complements require more than those sampled quadratic values. Eight dual norms likewise cannot identify the dual norm map. A2/A3 include additional maps never saved even for those eight directions. There is no unique exact 32-direction completion from the observed scalar data.

AW/MW/PMW encode compressed paths. They do not encode every full-space residual orthogonal to Q_current. Distinct omitted-path operators can have identical compressed factors but different frozen A2/A3 budgets. Hence reconstructing those budgets solely from compressed factors is not a justified exact recovery.

### Physical replay boundary

If no other preserved known-anchor/residual cache exists, computing these quantities with the frozen builder would require recovering the known-background full state, current basis and residual actions. That is new physical computation, even though it creates no new truth labels and changes no rank or degree. The missing quantities should be documented before deciding whether that exceptional known-anchor replay is unavoidable. This audit has not authorized or performed it. Full J cannot replace the missing online residual features.

## Existing split and solve contracts

`core.build_split` uses AW-SVD order. Its D is a regularized **profiled** decoder:

\[
K=AV_{\rm prior},\quad G=(I-U_KU_K^T)AV_{\rm phys},\quad
D=(G^TG+\lambda I)^{-1}G^T(I-U_KU_K^T).
\]

It gives the same tangent-candidate split family for all A1/A2/A3 interpretations. Its complement eligibility is uniformly `finite_amplitude_unvalidated`; the source does not use A3 to select or remove columns (`core.py:89-95`). Saved D should be labeled as the optional profiled branch if used, not as the plain restricted physics-only solve.

The frozen full solve is `evaluate_recovery` (`evaluate.py:430-439`): whiten and source-major pack the observation minus the known-background prediction, then run the common constrained SPD quadratic. `constraint_map` (`src/a20/material.py:12-16`) applies `Re(chi) >= -0.5` and `Im(chi) >= 0` through the same patch map. `constrained_material_solve` (`core.py:112-184`) supports any orthonormal material-coordinate basis and retains the full physical constraint rows, checks feasibility and KKT conditions, and returns the lifted 32D solution.

However, the default lambda inside that solver is `tikhonov_relative * sigma_max(A_input)^2` (`core.py:127-131`). Calling `evaluate_recovery(basis=V)` passes `AW @ V` without an explicit lambda, so a newly ranked split changes the default lambda. The R1 wrapper should pass the saved full-AW lambda directly to `constrained_material_solve(..., basis=V, lam=lambda_full)` to satisfy the user's same-regularization requirement. This is supported by the existing API and needs no frozen-source change.

## Parent decisions and evidence still outstanding

The source audit establishes available chart/frame definitions and missing descriptor quantities. It does not establish whether any split localizes error or whether restricted reconstruction is stable. Parent Codex must freeze the common 32 candidates, score context, ranking orientation/tie handling, primary k and metric floors before evaluating those questions.

The scientifically faithful execution paths are: recover exact missing known-anchor/residual information from an existing cache; or document its absence before a bounded replay of the unchanged known-anchor computation. Substituting generic factor norms for A3, treating eight directions as a complete basis, or calling the old AW-SVD split an A3 split would not answer the requested comparison.

## Subsequent parent-frozen implementation handoff

After receiving this audit, parent Codex selected the exact saved signed 32-column AW-SVD frame and the unchanged `predict_budget` scores at amplitude 0, noise multiplier 1, nominal intervention. A1/A2/A3 sort by ascending `pred_A1`, `pred_A2`, `pred_A3` with stable original-index ties. No calibrator is used. Primary k is 16; secondary k is 8. This is a parent decision recorded after the audit, not a worker-selected score.

The separately assigned driver is `src/a22_r1/freeze.py`. Its `freeze_scene(root, sid, config, book, device='cpu')` uses the parent-supplied CostBook, the unchanged online loader/builders/descriptor functions, and exact old saved direction vectors. It verifies AW/MW/PMW, known-anchor noise scale, material/current/common-frame metrics, rank 32, all eight partial saved descriptors, and the four-direction/two-amplitude/three-noise/two-intervention budgets before publishing a COMPLETE manifest. Numeric identity tolerance is relative `1e-9`; explicitly named tiny dimensionless identity residuals have separately flagged absolute allowances. Scientific scores do not receive those allowances.

The new cache uses the original paid AW/MW/PMW after validation, and preserves original noise/regularization scalars for replay. Rebuilt descriptors calculate the frozen ranking scores. It publishes `results/a22_r1/online/scene_ID.npz`, `scene_ID.json`, and `scene_ID.reproduction.json`; failed attempts receive separate retained failure audits. It never reads offline labels, full J or outcome tables. It counts 40 paid descriptor builds (eight legacy plus 32 common) and 80 budget predictions (48 legacy plus 32 common).

Validation completed by this worker: syntax parsing, module import, and in-memory comparator checks, including rejection of nonzero zero-budget discrepancies and explicit flagging of tiny identity allowances. No builder was called and no physical run was executed. Physical identity reproduction and the scientific experiment remain NOT_RUN by this worker; parent owns the queue and final scientific review.
