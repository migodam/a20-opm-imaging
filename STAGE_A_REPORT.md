# A22 Stage A report

Gate statuses are copied from the parent decision, never derived by this report. Missing evidence is NOT_RUN/UNDEFINED; report generation is not an experiment. Provided proofs, identity checks, actual Maxwell evaluation, oracle-only evidence and deployment evidence are distinct. Historical exposure is preserved; a historical validation label is not a new blind holdout. Directions, amplitudes and noise draws from one scene are correlated observations. No scene-cluster confidence interval is invented.

Parent decision source: `/Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/GATE_DECISION.json`. Availability: RECORDED; no parse error.

Stage A execution: SCREENING_COMPLETE. parent-supplied stage status

## Evidence inventory

| Evidence category | What this report can establish |
| --- | --- |
| Provided theorem/proof text | Source package derivations are supplied; validity remains subject to parent scientific review. Their presence never closes an experimental gate. |
| Identity tests | Saved A22 check receipts only; tiny algebra and real solver checks must retain their actual scope. |
| Actual Maxwell | Only parent/source-declared full-wave evidence qualifies. Metric-row presence alone does not establish physical provenance. |
| Oracle-only | 0 classified direction rows; separately displayed and excluded from a deployment interpretation. |
| Deployable | 2112 direction rows with declared deployable scope/provenance; parent checks legality and sufficiency. |
| Unclassified | 0 direction rows; no deployment or Maxwell claim inferred. |

| Source | Availability | Rows | Path | Missing/error |
| --- | --- | --- | --- | --- |
| direction_metrics | RECORDED | 2112 | /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/direction_metrics.csv |  |
| split_metrics | RECORDED | 12 | /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/split_metrics.csv |  |
| scene_metrics | RECORDED | 4 | /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_metrics.csv |  |
| scene_manifest | RECORDED | 4 | /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_manifest.csv |  |
| cost_ledger_0 | RECORDED | 3592 | /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/COST_LEDGER.jsonl |  |

## Recoverability observations

| Scope | Method | Scenes with defined correlation | Median scene Spearman | Equal-scene mean MAE |
| --- | --- | --- | --- | --- |
| deployable | A0 | 4 | 0.435576 | 0.0674055 |
| deployable | A1 | 4 | 0.518868 | 0.0588533 |
| deployable | A2 | 4 | 0.500483 | 172.757 |
| deployable | A3 | 4 | 0.519692 | 35.4516 |
| oracle_only | A0 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |
| oracle_only | A1 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |
| oracle_only | A2 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |
| oracle_only | A3 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |
| unclassified | A0 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |
| unclassified | A1 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |
| unclassified | A2 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |
| unclassified | A3 | 0 | UNDEFINED / NOT_RUN | UNDEFINED / NOT_RUN |

## Material split evidence

Split rows: 12; availability: RECORDED. Raw projected errors, ranks, retained truth energy, eligibility and certificate fields remain in the source CSV. Absence of any required dimension/normalization is not repaired with a guessed denominator.

## Health/identity checks

| Saved check receipt | Recorded status | Scope note |
| --- | --- | --- |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/attempt_archive/a22-cuda-screen-002/stage_a/scene_2001/resume_audits/c2fcb6ecaced4f179d8eb3da8e76579b/split_16_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/attempt_archive/a22-cuda-screen-002/stage_a/scene_2001/resume_audits/c2fcb6ecaced4f179d8eb3da8e76579b/split_4_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/attempt_archive/a22-cuda-screen-002/stage_a/scene_2001/resume_audits/c2fcb6ecaced4f179d8eb3da8e76579b/split_8_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_2001/resume_audits/41ad6f403ce6414a95933125f2add4a5/split_16_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_2001/resume_audits/41ad6f403ce6414a95933125f2add4a5/split_4_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_2001/resume_audits/41ad6f403ce6414a95933125f2add4a5/split_8_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_2001/resume_audits/c2fcb6ecaced4f179d8eb3da8e76579b/split_16_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_2001/resume_audits/c2fcb6ecaced4f179d8eb3da8e76579b/split_4_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |
| /Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/stage_a/scene_2001/resume_audits/c2fcb6ecaced4f179d8eb3da8e76579b/split_8_IDENTITY_COMPARISON.json | UNREADABLE | JSON document is not an object |

## Parent gate review

| Gate | Parent status | Reason / missing evidence | Next action |
| --- | --- | --- | --- |
| A | PARTIAL | formal 24-scene evidence absent; screening cannot award PASS |  |
| B | NOT_RUN | A is not formal PASS |  |
| C | NOT_RUN | one-shot stage not entered |  |
| D | NOT_RUN | A/B/C not all PASS; NN forbidden |  |
| E | NOT_RUN | No parent decision supplied; report does not evaluate this gate. | Parent must review the required evidence and provide the decision. |
| T | NOT_ESTABLISHED | no same-quality end-to-end timing comparison |  |

## Stage B/C

| Stage | Recorded execution status / prerequisite block | Reason |
| --- | --- | --- |
| A | SCREENING_COMPLETE | parent-supplied stage status |
| B | NOT_RUN | parent-supplied stage status |
| C | NOT_RUN | parent-supplied stage status |

Stage B/C status cards contain no fake images or measurements. A later actual execution receipt is required before either stage is described as run.
