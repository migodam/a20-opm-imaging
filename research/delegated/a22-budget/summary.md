# A22 budget/transport implementation contract

Status: IMPLEMENTED; syntax review PASS, all unit/physics/remote execution NOT_RUN.

Owned files: `src/a22/budget.py`, `tools/a22_remote_jobs.py`, and `tests/test_a22_budget.py` under `Gaussian/A22/three_fold_opm/implementation`.

- `A22Book(root, config=None, path=None, *, stage='screen_health', job_id=None, device='cpu', role='online', gates=None, cache_sufficient=False, started_wall=None, started_cpu=0, ...)` implements CostBook `span/check/scope/snapshot/delta/receipt`, `stage_scope(stage)`, `preflight(gpu_seconds=0,counters=None)`, `remaining_gpu_seconds()`, `add_child_cpu()`, `watchdog()`, and immutable `finish(status='COMPLETE',**details)`.
- `history(root, config=None, exclude_job=None)` adds only A22 inclusive final receipts or live checkpoints plus unique external scopes. Nested span rows do not add resource billing. A21 historical costs are descriptive. CPU has no cap; measured CPU and GPU occupation are separate resources.
- `merge_receipt(root,row)` and `register_external(root,scope,seconds,...)` are idempotent when the same identity and content recur; conflicting contents fail without replacing the prior receipt. Paid overages remain recorded.
- GPU wall caps: total 32400 seconds; stage caps screen_health 1800, features 3600, direction 7200, image 5400, runtime 7200, train 5400, exception 1800. Frozen configuration may lower limits, never expand or borrow them.
- `with book.action_guard('perturbation_forward', F_calls=1, role='offline_label',scene_id=...)` counts generation attempts before work, including failures/retries, under the global 192 data-generation F-call cap. `new_teacher_label` also spends the independent 9-new-label cap. Canonical counter is `data_generation_F_calls`; ordinary imaging forward calls are counted separately.
- `full_J/full_H/truth/teacher/s_F/e_F` are forbidden for online and health roles; explicit offline label/evaluation and reference roles permit audited evaluation uses. `health_fd_forward` spends the same data-generation F-call cap. A paid background `full_state` is legal online and counted separately.
- `physical_correction` requires `scene_id` and `method`; `correction_events=0` is an authorization cap and blocks all corrections. A separately authorized/frozen cap of 1 permits at most one attempt per pair, including failed attempts. Training requires A/B/C exactly PASS, sufficient existing legal cache, and the train stage. Diffusion/Flow/larger architectures remain refused.
- Unique jobs reserve `accounting_started.json` exclusively. `accounting_checkpoint.json` retains spent counters before action entry; `finish` writes the immutable `job_receipt.json` and A22 JSONL job/failure ledgers.

The parent configuration aliases `perturbation_evaluation_cap` and `correction_events` are supported. GPU stage scopes record `stage_gpu_seconds`; their exclusive sum equals the inclusive `gpu_occupation_seconds`. Setup/import/host wall belongs to the job's default stage unless a scope explicitly assigns it elsewhere. Stage budgets cannot borrow unused time from other stages.

Transport CLI: `tools/a22_remote_jobs.py ACTION --private-config PATH`, with ACTION `preflight/deploy/run/status/pull`. Run requires `--stage preflight|validate|screen|pilot|one-shot|train|report`, `--job a22-ID`, and `--device cpu|cuda`; optional `--budget-stage screen_health|features|direction|image|runtime|train|exception`. All paths passed to connection remain internal, and raw SSH/SCP diagnostics are neither printed nor stored.

The helper maps preflight/validate to screen_health, screen/pilot to direction, one-shot to image, train to train, and report to exception. It deploys A22/shared-physics sources/vendor/configs, protocol/a22, A22 tests/tools, new online cache inputs, and A22-only accounting. Every deployed data member must belong to `data/a22/online/`; the old `data/runtime/*/problem.npz` and `state_17.npz` inputs are excluded without deleting their original files. It excludes src/a21, offline labels, private files, and old A21 diagnostic/result banks. Pull validates every archive member and immutable receipt before writing any summary, then unions ledgers/external scopes idempotently.

Remote launcher sets numeric `A22_JOB_WALL_ORIGIN` and `A22_BUDGET_STAGE` for the parent CLI. The CLI must pass that origin to the book so startup/import/controller work is included. The foreground watcher polls checkpoints and terminates the whole child at remaining total/active-stage limits with a 2-second stopping margin; terminated paid counters/CPU/wall are retained. A killed shared lock is preserved for owner inspection. No remote connection was attempted, so Windows process-time measurement, queue checks, remote deploy/pull, and actual watchdog termination remain unverified.

Verification here used only Python AST parsing of the three owned files and generated remote controller code. The prepared unittest suite has not run. The parent should run it with the project's CPU meter and then perform the sanitized remote preflight when authorized. Parent Codex owns integration and scientific decisions.

Cost artifact: `research/delegated/a22-budget/CPU_RECEIPT.json`; conservative local CPU charge is 30 seconds, GPU charge is 0. This does not prepay future unit tests or remote work.

## Transport boundary follow-up, 2026-10-07

Only `tools/a22_remote_jobs.py` was changed in the implementation. Deployment enumeration and remote extraction both reject data outside `data/a22/online/`. Windows preflight and launch queue queries now add the querying child process CPU to controller CPU, with explicit availability flags if GetProcessTimes cannot measure it. The reader sets Windows API argument/return types explicitly.

A watchdog/controller exception now attempts child termination before recording a final failure. If termination cannot be confirmed, the job remains a live `STOP_UNCONFIRMED` checkpoint, its shared lock is preserved, and the helper does not create a false final receipt. A previously valid checkpoint is retained for failure accounting if a later snapshot is unreadable. A rejected duplicate remote job uses a new controller-attempt scope instead of rewriting the prior job's launch scope.

AST parsing of the helper and generated preflight/watchdog code passed. Read-only member enumeration found no old runtime deployment members. Windows execution, SSH, GPU work, and unit tests remain NOT_RUN here. New CPU cost only: `CPU_RECEIPT_DEPLOY_BOUNDARY.json`, 5 conservative CPU seconds and 0 GPU seconds; do not register the older 30-second scope again.
