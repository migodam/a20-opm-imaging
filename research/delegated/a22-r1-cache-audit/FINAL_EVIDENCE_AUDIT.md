# A22-R1 final evidence audit

The reviewed tables, numeric gate decisions, scene aggregation, and selected-set audit are internally consistent. No material evidence discrepancy was found. This is an implementation/evidence audit; the parent retains final scientific interpretation. The reported conclusion is **CASE_C_A2_MATCHES_OR_BEATS_A3**, with screening SUPPORT/FAIL only and no formal PASS.

No source, solver, protocol, score, split, or experiment artifact was changed. No new solve, score computation, physics action, or label generation occurred. Detailed independent checks are preserved in `FINAL_EVIDENCE_AUDIT.json`.

## Numeric consistency

The independent reader regrouped all 42,240 existing metric rows by draws, conditions, and scene. It found 3,840 complete condition groups and 80 complete scene/method/k/test groups, exactly `4 scenes × 5 methods × 2 k × 2 tests`. Each scene group has the frozen 48 conditions; noise-zero conditions have one draw and other conditions have 16 distinct registered draws. No missing, duplicate, excess, or invalid draws/statuses were found.

| Check | Maximum absolute difference |
|---|---:|
| Independent draw/condition averages vs `PER_SCENE_SPLIT_METRICS.csv` | 8.8818e-16 |
| Independent equal-scene means/medians vs `SPLIT_COMPARISON.csv` | 4.4409e-16 |
| Independent medians/ratios vs `GATE_DECISION.json` | 2.2204e-16 |
| Stored vs independently checked projector distances | 0 |

All 15 primary method table rows in `A22_R1_START_HERE.md`, `ONE_SHOT_ERROR_LOCALIZATION.md`, and `RESTRICTED_PHYSICS_BRANCH.md` agree with their CSV sources at the stated six-significant-digit display precision. Raw lambda values equal the original full-scene lambda on every row. The CSV `full_scene_lambda` field is a boolean provenance flag, not a second numeric lambda.

## Gates and statistical unit

Recomputing primary k=16 gates from the existing metric values yields S1 SUPPORT, S3 SUPPORT, S4 SUPPORT, S2 FAIL. These match the saved gate decision.

| Primary A3 quantity | Audited value | Frozen screening requirement |
|---|---:|---|
| Median scene S_sep | 3.399403243 | >=2 |
| Median scene q_phys | 0.3542494613 | <=0.7 |
| Median scene q_prior | 3.439209632 | >=1.3 |
| Median scene truth-energy coverage | 0.7409675920 | >=0.35 |
| Median scene restricted/common physics NRMSE ratio | 0.9863173371 | <=1.25 |
| A3 relative improvement in equal-scene mean physics NRMSE vs A2 | 0 | >=0.15 |

The aggregation averages draws first, gives each scene's 48 conditions equal weight, and gives the four scenes equal weight. The bootstrap records four paired scene clusters, 2,000 resamples, seed 20261911. The 2,112 cases are not treated as independent objects. Ratios and q are averaged as preregistered per-case quantities; they are not reconstructed from averaged energies. S4 uses each scene's ratio of Test-B and Test-A physics NRMSE means, then the four-scene median.

All four scenes are historically exposed. The saved `formal_PASS=false`, formal validation NOT_RUN, NN NOT_RUN, expansion NOT_RUN, nonlinear reconstruction NOT_RUN, and LOCAL_ONLY flags are consistent with the documents.

## Identical candidate subsets

Reading the frozen split NPZ files confirms that **A1, A2, and A3 select exactly the same direction sets in every scene at both k=8 and k=16**. All choose candidate indices `{0,...,7}` at k=8 and `{0,...,15}` at k=16. Column order can differ, but all pairwise selected-set Jaccards are 1 and reported projector differences are at most `4.4011e-16`.

Thus the Test-A zero A3 increment is the consequence of the same subspace projector. The machine-level bootstrap interval is not independent evidence of general A2/A3 equivalence on unseen scenes. This finding applies to the frozen AW-SVD candidate frame, scoring condition, and two k values. It does not establish that the scoring functions are identical or that O/P/M information can never matter in another candidate pool or regime. The current main documents make this limitation explicit for A2/A3; this audit additionally confirms A1 and both k values.

## Absolute accuracy and Test B

The primary A3 median scene physics NRMSE is `0.5350985949` (equal-scene mean `0.5247222444`). Relative concentration of error in the complement therefore does **not** establish low-error or reliable absolute imaging. The start document states this directly. "Useful screening split" refers to the registered relative separation, signal-coverage, and restriction criteria, not a new absolute imaging accuracy gate.

Test B holds the original full-scene lambda and feasible chart constraints fixed, sets the complementary coefficients to zero, and reports restriction stability. Its prior NRMSE near 1 is the consequence of this zero output; the restricted-branch document correctly excludes Test-B separation/q from Test-A separation evidence.

The numeric audit reports 21,120 valid restricted QPs, zero invalid QPs, maximum relative KKT `9.991835900e-9`, maximum feasibility violation `5.342948306e-16`, and maximum prior coefficient leakage `4.558140927e-16`. No metric norm floors are active. Ill-conditioned active-KKT warnings are disclosed; their exact warning count was not saved. These saved QP checks do not imply warning-free numerics or a formal new-scene validation. This final audit did not rerun those solves or independently recompute every KKT residual.

## Online/offline and reproduction limits

Method scopes in all raw rows match the reported scopes. Full-J is explicitly OFFLINE/ORACLE DIAGNOSTIC, uses existing full-J caches after the online freeze, and ranks the same frozen directions. The report does not claim that it searched arbitrary optimal LIS subspaces or that an unsuccessful fixed full-J split would prove hard splitting impossible. Online A1/A2/A3 selection is not described as using full J, truth, or reconstruction errors.

Strict historical scalar reproduction is still FAILED: 104 Mac and 26 Windows mismatches. Both failed attempt receipts remain in the cost and failure ledgers. The direct experiment uses one complete fixed Windows common-vector archive uniformly, with zero new common solves in the continuation and separate stored quadratic/KKT/feasibility validation. The pre-outcome addendum is preserved at `REPRODUCTION_CONFLICT_ADDENDUM.md` (commit `7d29bd5`). The documents identify the Windows common archive and Mac restricted branch and do not claim bitwise Stage-A reproduction.

This is an explicit departure from the additional strict scalar replay check, not a passing version of that check. The preserved failure remains a limitation of reproducibility, even though the direct subspace analysis uses valid frozen quadratic solutions.

## Chart-exterior framing

`CHART_EXTERIOR_AUDIT.md` consistently separates `chi-chi0 = W x + chi_outside_W` and reports original chart retention of approximately 46–49% for Gaussian scenes, 5.8% for 2014, and 13.4% for the shell scene. In-chart V_prior excludes exterior truth energy. The document now also states the essential causal limit: the existing full-wave observations still contain scattering from chart-exterior material. Excluding that energy from metric denominators does not remove its influence on recovered in-chart coefficients. No W-only labels or causal removal experiment was run.

Accordingly, this evidence describes separation of actual reconstruction errors inside the declared chart under the cached finite-amplitude/noise/calibration conditions. It does not establish full-object reconstruction or chart-exterior-free intrinsic identifiability.

## Cost evidence and this audit

Before adding this audit, the inclusive receipt sums agree with the then-current cost summary: CPU `729.916521 s` including declared source allowances, GPU-related occupation `155.3568274 s`, four paid known-background forward states, and zero new full-wave labels. Unique additive receipt IDs have no duplicates. Failed Mac and Windows replay costs are retained. Nested actions are not added to inclusive receipts, and complete deployment time/speedup remain NOT_MEASURED/NOT_ESTABLISHED.

The first audit-reader attempt incorrectly treated the boolean `full_scene_lambda=True` field as numeric and stopped. This audit-only failure is retained in receipt `a22-r1-final-evidence-audit-001`, CPU `0.062030 s`. The corrected read-only audit completed in `a22-r1-final-evidence-audit-002`, CPU `0.634938 s`; the combined measured CPU is **0.696968 s**, GPU zero, below the requested 5-second limit. Both receipts are already registered. The successful receipt copy is `FINAL_EVIDENCE_AUDIT_CPU_RECEIPT.json`. The parent should refresh the cost summary to include both audit receipts before final delivery.

No further experiment change or rerun is indicated by this consistency audit. The scientific conclusion and any future work remain the parent's decision.
