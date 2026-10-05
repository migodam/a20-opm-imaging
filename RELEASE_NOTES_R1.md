# v0.2.0-r1-mechanism

A20-R1 adds same-rank late-state seed anatomy, guarded oracle-block preservation, legal reduced-gradient enrichment and own-trajectory history hooks. Source, frozen configs, runtime inputs, offline evaluation inputs, receipts, failures and figures are included.

Formal diagnosis: **D — INCONCLUSIVE**. Thirty late-state Gaussian QPs passed the original KKT tolerance at actual rank 56. Median H-step errors: FIXED-DEEP 269.5060%, WIDE-M 209.5953%, CHEAP-TASK 235.1696%, raw oracle 267.5646%, protected oracle 366.1017%, matched protected random control 213.2166%. Oracle is **OFFLINE / DIAGNOSTIC ONLY**, excluded from algorithm ranking and deployment claims.

Protected oracle captures the six-source KB block and yields 0.0486763% median reference-direction tangent error, yet fails to recover the reduced GN minimizer. This is negative descriptive evidence, not a universal impossibility claim.

The first early-state FIXED-DEEP check failed: relative step difference 1.670492e-6 exceeds frozen 1e-9. The run stopped without relaxing gates or repeating physics. 31 models built, 29 remaining models NOT_RUN. Gate A/C HOLD, legal Gate B FAIL; Phase2, history ablation, deployment GO and NN NOT_RUN.

Physics source: `5231aea98f6945a77c4f83f030a57248065695ef`; inherited A20 freeze: `e29f345ae5aea170a18cca1b79defe57e878ab29`. Original evidence and v0.1.0-pilot release retained. No new SHA256 check, NN, degree expansion or solver changes. START_HERE.md and the separate publication receipt give evidence, budget and actual public commit identities.
