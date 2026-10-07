# A22 reporting default discovery correction

Status: source-only implementation. No tests, source imports, syntax checks, module/report/statistics calls, data reads, plots, physics, remote, GPU or hashes executed by this worker.

Only reporting default file discovery changed:

- Raw direction_metrics.csv, split_metrics.csv, scene_metrics.csv and scene_manifest.csv now prefer results/a22/stage_a, matching evaluate.run_stage_a outputs. Legacy results/a22/screening and results/a22 root CSV inputs remain fallbacks. A missing metric still points to the canonical stage_a path and stays NOT_RUN.
- Saved statistical evidence now prefers results/a22/statistics/STATISTICS_EVIDENCE.json, then the previous screening and results/a22 root locations. A missing artifact stays NOT_RUN. Existing A22-local explicit path checks, schema check and missing behavior are retained.
- No reducer, calibration, statistics, mathematical formula, gate, main scientific document, CLI dispatch, output-writing contract, solver or source identity logic changed. CLI report still calls only the raw generator; parent explicitly calls statistics/cost/statistical plotting under its own meter.
- Added tests/test_a22_report_discovery.py with 3 unexecuted fixtures: canonical stage_a metrics/manifest precedence over both old locations; canonical statistics artifact precedence; missing defaults retain NOT_RUN and canonical source paths.
- Static textual read confirmed the canonical candidates and existing A22 safety checks. It does not establish runtime success. The parent owns test execution and all interpretations.

This independent source scope charges only this minimal patch, fixture source and its short handoff/receipt. Delivery-audit documentation/source reads are separately charged under a22-delivery-audit.
