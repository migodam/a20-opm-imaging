# A20 OPM imaging: bounded pilot archive

Read [START_HERE.md](START_HERE.md) for the actual result, reproduction inputs and evidence.

Registered backend checks passed; six historically exposed 3D vector-Maxwell objects were attempted at two frozen states each. The current implementation does not advance to nonlinear imaging: both voxel references failed KKT validation, and the five Gaussian parents have large late-state H-step errors. Complete-cohort representation screening is **HOLD**; progression is **NO_GO**. Nonlinear quality and deployment acceleration are **NOT_RUN**.

No neural training or Maxwell solver acceleration was performed. All reference, failed and audit work is charged within the fixed two-hour CPU and twelve-hour GPU limits. Runtime inputs and offline labels are separate. Historical SHA256 fields are retained without new checks.

See [Chinese report](RESEARCH_REPORT_ZH.md), [gate decision](results/GATE_DECISION.json), [reproduction](docs/REPRODUCE.md), [backend map](docs/BACKEND_MAP.md), and [publication receipt](results/PUBLICATION.json).
