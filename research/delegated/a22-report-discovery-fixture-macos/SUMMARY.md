# A22 macOS discovery fixture path compatibility fix

Only tests/test_a22_report_discovery.py changed: the three TemporaryDirectory fixture roots now use Path(directory).resolve(), matching reporting's existing resolved absolute source paths. This makes /var and its macOS /private/var target comparable without changing report discovery behavior or production source.

Parent reports metered a22-unit-012 ran 130 tests with only these 3 new fixtures failing because expected paths were not resolved. The worker did not read/rewrite that job, its output/logs, or its accounting, and did not independently rerun any test.

No reporting source, reducer, statistics, gate, CLI, module imports, syntax checks, test execution, data, plots, physics, SSH/remote, GPU or hashes were touched/executed. Existing a22-report-discovery CPU receipt/scope remains unchanged. This independent scope records only the assigned test-source read, three-line patch, and this short handoff/receipt. Parent will execute the metered follow-up test.
