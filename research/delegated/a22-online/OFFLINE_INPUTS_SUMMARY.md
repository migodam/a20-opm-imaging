# A22 offline evaluator input interfaces

Status: **CODE_WRITTEN_NOT_EXECUTED**. This worker did not prepare data, load
truth, construct a solver, run tests, invoke SSH/SCP, read private connection
configuration, or perform integrity hashes. Actual source-array shape and
transport availability remain runtime checks for the parent.

## Files and APIs

| File | Entry point | Result |
| --- | --- | --- |
| `src/a22/offline_assets.py` | `prepare_offline_screening(root, config, book) -> dict` | Four immutable evaluator NPZs and a separate manifest; returns the manifest |
| `src/a22/offline_assets.py` | `load_evaluation_truth(root, sid, book) -> np.ndarray` | Readonly complex128 object material, checked as solver n=12 / 1728 cells |
| `tools/a22_evaluation_inputs.py` | `evaluation_members(root=ROOT)` | Exact four NPZs plus manifest allowlist; inspects NPY headers only |
| `tools/a22_evaluation_inputs.py` | `deploy(private_config, *, root=ROOT)` | Explicit transfer through existing `PrivateTransport` and `_python` helpers |
| `tools/a22_evaluation_inputs.py` | `main(argv=None)` | Standalone deploy CLI; records local, child and remote transport CPU with `register_external` |

The parent integrates `prepare_offline_screening` into its metered prepare
CLI. Pass the **original A17 asset configuration**, because the portable online
NPZs intentionally have no `truth` member. No configuration is edited by these
interfaces. The low-level `deploy` function relies on the standalone tool CLI
for external accounting, following the existing transport helper convention.

## Offline bundle contract

Only IDs **2001, 2003, 2014, 2009** are accepted, in the frozen order. Each
original mixed NPZ is accessed through `assets.load_offline_scene` inside
`book.action_guard('truth', role='offline_label')`; only its `truth` member is
requested. `held_truth`, old material charts, measurements, scene descriptions,
and objective normalization arrays are not read by this preparation path.

Prepared paths are exactly:

- `data/a22/offline_eval/scene_2001.npz`
- `data/a22/offline_eval/scene_2003.npz`
- `data/a22/offline_eval/scene_2014.npz`
- `data/a22/offline_eval/scene_2009.npz`
- `data/a22/offline_eval/MANIFEST.json`

Every NPZ contains only `truth`, with shape `(1728,)` and dtype complex128.
Manifest records distinguish saved material on **solver n=12** from the
original observations' declared **data-generation n=14**. No measurement is
regenerated. The actual four original array shapes have not been read by this
worker; preparation refuses any source that fails the declared shape contract.

The actual object material is the offline finite-perturbation center and target
label. The online anchor remains **uniform known background 0.1+0.04i**.
Neither label paths nor values are added to online configuration. Truth-only
NPZs fail the online loader's required `points/data0/init` layout. The evaluator
loader is separate and uses `role='offline_evaluation'` for every label read.
These are explicit capability boundaries, not a Python security sandbox.

Existing matching prepared labels are reused. Conflicting arrays or provenance
are refused. Writes use temporary files and atomic replacement; all existing
member comparisons are guarded offline reads. Namespace symlinks are refused.
The caller owns the ledger lifetime; no full forward or data-generation action
is performed by preparation or loading.

## Explicit transport

Future invocation is the standalone `tools/a22_evaluation_inputs.py deploy`
command with explicit `--root` and `--private-config` arguments. The private
configuration is read only when the explicitly called existing transport
constructor executes; connection values, the private file, and raw diagnostics
are never copied, printed, or placed in receipts.

The exact five evaluator files are transferred in a dedicated archive. Its
remote staging path stays under `data/a22/offline_eval/.transfer/`. Remote code
checks the same five-member allowlist and NPY header/layout contract before any
destination writes. Existing remote files must match their incoming bytes;
conflicts are refused without integrity hashes. Header checks do not load
material arrays. Normal completion removes the staging archive; an interrupted
connection can leave a partial staging archive inside the evaluator namespace.

The existing **online deployment whitelist is unchanged**. This is an explicit
evaluator-input transfer, not an extension of the online data route. GPU lock
checks use the existing shared lock path; transport runs no physics or GPU
work. The CLI preserves paid failures and registers controller startup/import
CPU, local child CPU, and both returned remote Python CPU receipts. It does not
claim unavailable remote CPU measurements after a lost connection.

No scientific gate was adjudicated. Preparation, transport, and validation are
**NOT_RUN** by this worker.
