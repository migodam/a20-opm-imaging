# Stage-A partial resume implementation

Status: SOURCE_WRITTEN_NOT_EXECUTED. Only `src/a22/evaluate.py` and new
`tests/test_a22_resume.py` were changed as scientific/test source. No Maxwell
action, test, source import, SSH, generator or integrity-hash check ran here.
CLI, core, budget and transport files were not edited.

- API: `run_stage_a(root, config, book, *, device='cuda', screening=True,
  resume=False)`. Default execution retains the existing algorithm. New cache
  outputs additionally carry known-anchor state/layout metadata.
- `stage_a_case_key(row)` uses scene, direction, amplitude level, noise level,
  draw and intervention. `_restore_stage_a` restores every prior direction,
  split and scene row even if interruption preceded a scene summary. Successful
  OK keys require finite error/KKT/feasibility evidence. INVALID_QP keys are also
  terminal and skipped without becoming valid solutions or eligible statistics;
  their original rows remain in the output and failure ledger. Completed scenes require complete registered
  case coverage before skipping; invalid QPs in an explicitly completed scene
  remain historical failures.
- Partial scenes rebuild and pay the online anchor, basis and descriptors.
  `_verify_online_factors` checks rebuilt AW against saved AW at relative
  1e-9 before any offline read. `_freeze_json` compares scientific provenance,
  direction vectors/selection and forecasts; it preserves original files.
  Regenerated factors and JSON comparison material go under
  `scene_ID/resume_audits/unique_id/`. Costs, timing, job IDs and structured
  runtime cache identity objects are omitted from scientific provenance equality.
- `_validate_split_rows` treats ONLY orthogonality and nuisance_leakage as
  dimensionless identity residuals: both independently must be <=1e-9 and
  their difference is audited. All other split quantities, AW, directions,
  amplitudes and forecasts retain the original strict comparison. This is
  numerical identity handling; it does not change a scientific gate.
- `_load_j_cache` requires online freeze first and the offline-evaluation
  full-J capability. `_load_label_cache` uses the offline-label truth capability
  and validates clean-data shape, original object material, 32 coefficients,
  perturbation, direction, nuisance, amplitude and exact six-source order.
  New caches also validate anchor material, mesh, volume, frequency, chart,
  acquisition, whitening, configuration and data/material layout.
- Legacy JF-only caches rely on the paired compatible online freeze and known
  immutable original producer semantics; they have no independent state
  metadata. Legacy finite-label caches retain their original fields and have
  no numeric backward-residual receipt. Replay records these legacy cases
  explicitly. An incompatible present cache fails; it is never silently
  replaced with a new full forward/Jacobian.
- Every attempted read is paid as `offline_cache_reads`. A successfully
  validated replay additionally records `offline_cache_hits` and a J/label
  subtype. Replay adds no data-generation F, full-forward or full-J-build
  counter. Missing caches use the ordinary paid offline path. Original object
  finite-label centering and `evidence_scope='deployable'` are preserved.
- Eight unit-test methods were written, including a fully mocked partial-scene
  resume that retains and skips a terminal invalid attempt, skips prior OK keys,
  executes only one missing key, pays one online rebuild, replays J and label, preserves frozen
  bytes and makes no physical call. AW mismatch must refuse before truth load.
  Execution and controlled remote stop/deployment remain with the parent.

CPU receipt: `RESUME_CPU_RECEIPT.json`, unique scope
`a22-stage-a-partial-resume-source-implementation`.
