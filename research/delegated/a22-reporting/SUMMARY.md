# A22 reporting source handoff

Status: source implemented; report, plot, solver and test execution NOT_RUN.

Owned source: `src/a22/reporting.py`.

Public callable: `generate_reports(root, gate_path=None, output_dir=None, *, make_plots=True, evidence=None)`. `report` and `render_report` alias it. Import has no data/plot/write side effects. Parent must meter the entire callable, including reads and PNG/SVG writes.

Inputs are A22-only: `results/a22/screening/{direction_metrics,split_metrics,scene_metrics}.csv`, fallback equivalent paths directly under `results/a22`, optional scene manifest, A22 CSV/JSONL cost ledgers, and parent `results/a22/GATE_DECISION.json`. Root inherited A21 gate and cost ledgers are excluded. Gate path must remain inside results/a22. Missing files are valid inputs and remain NOT_RUN.

Outputs, when called: `A22_IMPLEMENTATION_REPORT.md`, `A22_RESULTS_LEDGER.md`, `A22_GATE_DECISION.md`, `STAGE_A_REPORT.md`, `GATE_REPORT.md`; `figures/a22/*.png` and SVG; `results/a22/reporting/REPORT_MANIFEST.json`, figure manifest, expected schema, supplied evidence, source copies and descriptive CSVs under rawdata.

Plots: actual versus predicted coefficient error A0-A3; per-scene Spearman; true errors versus amplitude/noise; separate projected/relative/per-coordinate physics and complement error; recorded rank/action/wall; blocked Stage B/C cards when not run. Oracle/deployable/unclassified scopes are separated. Missing metrics are not zero filled. Constant or fewer-than-three paired correlation observations are UNDEFINED. Rows/draws are never counted as independent scenes. No thresholds, win criterion, bootstrap interval, gate outcome or acceleration claim is inferred.

Future columns and row semantics are in EXPECTED_METRICS_SCHEMA.json here; complete flexible aliases are in source SCHEMA. Raw sources preserve failure/status/provenance/exposure fields. Reports list provided derivations, identity checks, actual Maxwell declarations, oracle-only and deployment evidence separately.

Source-only limitations: no import, syntax run, unit test, report generation, rendering or visual QA has been executed by this worker. Parent owns all metered validation and final scientific review. No hashes, remote work, DeepSeek, agents or private SSH configuration reads.
