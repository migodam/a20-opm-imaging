# Independent A21 driver

`a21.budget.A21Book(root, config, path, device='cpu', epilogue=False)` preserves
the existing `CostBook` span/scope/snapshot/delta interface. It charges only new
`results/jobs/a21-*/job_receipt.json` and unique A21 external scopes, then adds
the frozen historical CPU/GPU carry. Nested costs are diagnostics, not extra
billing. Imports, report work, failed attempts and validation child CPU are paid.

`python -B -m a21.cli preflight|validate|anatomy|report --job a21-...` defaults
to CPU. `--phase all|galerkin|petrov` changes only runtime configuration.
Anatomy calls `anatomy.run_anatomy(root, config, book, job)`; report calls
`report.run_report(root, config, book, job)`. Physics requires an ignored
`configs/A21_SOURCE_COMMIT.txt` and a complete successful synthetic/unit T0.
The original backend freeze and the execution commit are distinct fields.

Preflight reads NPZ headers and a few scalar identifiers. It does not allocate
5184-dimensional physics or certify full KKT. Validation copies only the supplied
two-sided synthetic script into a new result directory and discovers unit tests;
it does not execute the online descent experiment. Controller plus child CPU
and wall are bounded by 120 seconds, and also by cumulative A21 limits. A selected
development test subset cannot unlock physics.

Remote code uses the existing environment-based `tools/remote_jobs.py` transport.
Missing connection environment is filled from ignored `private/ssh_connection.json`
at use time. Private values/argv are never printed. Raw SSH stderr is kept only
under ignored private files; stdout tolerates Windows non-UTF-8 bytes.

Remote physics uses the pre-existing `D:/AI/A20_OPM_IMAGING/runs/gpu.lock` even
though execution is under `D:/AI/A21_TWO_SIDED_ANATOMY`. Remote device selection
is explicit. Deployment excludes truth labels, old ledgers, private files and
root reports; it carries the five runtime problem/state17 pairs, canonical index,
ten selected baseline/reference steps, code/config/protocol/tests/vendor/tools,
and A21-only accounting/T0 metadata so local charges cannot be reset remotely.

Pull merges external scopes and local validation receipts, refuses different
overlapping immutable job artifacts, and writes only A21 results. Transport/archive/
extract CPU is recorded as a measured component covered by the precharged 30-second
setup/transport allowance; measured excess is registered once. No SHA256 checks occur.

All validation, preflight, transport and physical execution must use unique IDs.
Failed/partial artifacts remain available; replacing an existing job is refused.
