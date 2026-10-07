# A22 core API tests: source-only handoff

Status: IMPLEMENTED_SOURCE_ONLY; NOT_RUN. This worker has not imported, syntax-checked or executed this test module, run numerical tests, loaded experiment arrays, called physics, generated reports/plots, contacted a remote service or computed hashes. The parent owns all metered execution and scientific interpretation.

Owned source: `tests/test_a22_core.py`. The existing `src/a22/core.py` and other agents' files were read but not edited. Ordinary `unittest` fixtures use small synthetic real matrices and a declared paired material chart. They are API/identity regressions and cannot establish any Maxwell or experiment gate.

The 13 tests cover:

- Bright response with near aliasing: small profiled gain and large witness noise variance; zero direction and unidentifiable zero response retain undefined witnesses.
- Full nuisance normal orthogonality, target attribution and the small full-rank reference witness.
- An individually bright, rank-deficient bad-span counterexample; no nontrivial full-material split is accepted.
- SVD split orthogonality/full complement, explicit decoder shrinkage, noise gain, invalid zero model and unchanged uncertainty status.
- Rectangular SVD regressions: retain the complete material null complement and avoid out-of-range direction candidates. The parent fixed the rectangular API before this source handoff.
- Internal O/P/M factor gauge product invariance and real material coordinate gauge invariance through projectors and lifted decoders.
- A general real 32-coordinate basis mixing paired real/imaginary coordinates: original physical material bounds, coefficient-space KKT normal, unchanged registered lambda, and no post-clipping or pseudoinverse/jitter flag.
- Fault injection of a feasible but nonstationary quadratic solution: KKT failure is raised with its audit, rather than accepted or rescued by a new ridge/pseudoinverse.
- Deterministic direction selection is independent of supplied truth/error/recovery labels.

No result or gate outcome is claimed. All test execution remains NOT_RUN. The worker performed only static source review, file writing and receipt preparation. The intended metered command is `PYTHONPATH=src python -m unittest discover -s tests -p test_a22_core.py`; this command was not invoked by the worker.

CPU accounting is unique to `a22-core-tests`, separate from `a22-reporting`. `CPU_EVENTS.jsonl` records measured child-process CPU where available and explicit conservative allowances for shell startup/source-write tool execution. Allowances are not measurements. `CPU_RECEIPT.json` gives the bounded source-work charge and zero runtime/test/physics events. The parent should incorporate this unique scope once into its A22-only implementation ledger.
