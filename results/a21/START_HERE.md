# A21：五态双侧 GN anatomy 已完成

**T0 PASS；T1 LATE_GN_TWO_SIDED_FIDELITY_CONFIRMED。** 五个历史暴露 late states、35个固定rank主实验完整有效。BOTH_G最大相对H-error 4.40e-11，PRIMAL_G中位262.00%，匹配RANDOM_G中位280.15%。双侧oracle恢复原冻结受约束full-GN步；在线/成像/部署收益尚未验证。

先读[中文科学报告](A21_ORACLE_REPORT_ZH.md)，再查[Gate](GATE_DECISION.json)、[全部指标](A21_METRICS.csv)。

- [Backend接线](A21_BACKEND_MAPPING.md)、[冻结manifest](A21_FROZEN_MANIFEST.json)、[数值约定](A21_NUMERICAL_CONVENTIONS.md)。
- [逐态记录](per_state/)、[原始cache](anatomy/caches/)、[诊断向量](anatomy/diagnostics/)、[独立数组复核](INDEPENDENT_ARRAY_REVIEW.json)。
- [图表](figures/)、[图表原始数据](rawdata/)、[自动初审报告](A21_ORACLE_REPORT.md)。
- [完整T0](validation/T0.json)、[真实T0与summary](anatomy/summary.json)、[复现命令](REPRODUCE.md)。
- [成本](COST_LEDGER.jsonl)、[失败](FAILURE_LEDGER.jsonl)、[动作口径](ACTION_ACCOUNTING.md)、[最终预算](BUDGET_FINAL.json)。

物理冻结源码 `5c6bcb02bb4ab88f7b46f07bca4ca3f4e38a067c`；报告源码见冻结manifest和独立job receipts。参考未缩放、未修复；原A20/R1源码、账本、结果、release保持原样，未重新计算SHA256。

实验已经停止。NN、nonlinear reconstruction、degree增加、solver acceleration、T2均NOT_RUN；发布状态单列于 [PUBLICATION.json](PUBLICATION.json)。

At scientific closeout, inclusive budget: A21 CPU 349.157858 s /1200 s; GPU 281.661815 s /1200 s. Historical carry included: CPU 5955.773909 s /7200 s; GPU 5943.440674 s /43200 s.

Publication CPU is charged separately in [BUDGET_PUBLICATION.json](BUDGET_PUBLICATION.json); the scientific-closeout receipt above is retained.

Publication status: **PUBLISHED_AND_ANONYMOUSLY_VERIFIED**. [A21 release](https://github.com/migodam/a20-opm-imaging/releases/tag/v0.3.0-a21-two-sided-anatomy) and [publication receipt](PUBLICATION.json). All later publication/verification CPU receipts are included in the [final closeout asset](https://github.com/migodam/a20-opm-imaging/releases/download/v0.3.0-a21-two-sided-anatomy/A21_PUBLICATION_CLOSEOUT.json).
