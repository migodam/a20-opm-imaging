# A21：五态双侧 GN anatomy

**T0 PASS；T1 LATE_GN_TWO_SIDED_FIDELITY_CONFIRMED。** 五个历史暴露的 Gaussian late states、35 个固定 rank 主实验均完整有效。双侧 oracle 恢复同一个原始受约束 full-GN optimum；这仅验证冻结二次任务的双侧保真机制。

PRIMAL_G 的 current capture 充分，GN 步误差仍很大；DUAL_G 单独保护也不足。BOTH_G 的最大 relative H-step error 为 **4.40e-11**，匹配随机控制的中位误差为 **280.15%**。报告包含完整 dual defect、stationarity decomposition、Hessian 尺度、有效法锥、KKT 和 solver-aware H-step bound。

先读 [中文科学报告](results/a21/A21_ORACLE_REPORT_ZH.md)，再读 [A21 证据索引](results/a21/START_HERE.md)、[gate](results/a21/GATE_DECISION.json)、[35 臂指标](results/a21/A21_METRICS.csv) 和 [复现说明](results/a21/REPRODUCE.md)。

- [Backend 接线](results/a21/A21_BACKEND_MAPPING.md)、[冻结 manifest](results/a21/A21_FROZEN_MANIFEST.json)、[数值约定](results/a21/A21_NUMERICAL_CONVENTIONS.md)。
- [逐态记录](results/a21/per_state/)、[图表](results/a21/figures/)、[图表原始数据](results/a21/rawdata/)、[独立数组复核](results/a21/INDEPENDENT_ARRAY_REVIEW.json)。
- [成本](results/a21/COST_LEDGER.jsonl)、[失败](results/a21/FAILURE_LEDGER.jsonl)、[物理动作口径](results/a21/ACTION_ACCOUNTING.md)、[累计预算](results/a21/BUDGET_PUBLICATION.json)。
- [独立 A21 release](https://github.com/migodam/a20-opm-imaging/releases/tag/v0.3.0-a21-two-sided-anatomy)、[离线诊断数组](https://github.com/migodam/a20-opm-imaging/releases/download/v0.3.0-a21-two-sided-anatomy/a21-offline-diagnostics-v0.3.0-a21-two-sided-anatomy.zip)、[发布状态](results/a21/PUBLICATION.json)。

**ORACLE / OFFLINE / DIAGNOSTIC ONLY。** Full J/H、primal/adjoint currents 和底层诊断向量在单独 release 资产中；它们用于复核，不能当作在线输入。在线算法、非线性成像、部署收益、T2、NN 和 solver acceleration 均为 NOT_RUN。实验在五态 anatomy 后停止。

本仓库保留 [A20-R1 入口](A20_R1_START_HERE.md)、[原 A20 pilot 入口](A20_PILOT_START_HERE.md) 及其旧结果、账本与 releases。A21 不改写原 A20/R1 的 NO_GO/HOLD/INCONCLUSIVE 判断。输入仍是历史暴露数据，没有新增盲测。

English: this is an offline two-sided task-interpolation anatomy of five historically exposed constrained Gaussian GN quadratics. Both oracle current banks recover the frozen optimum at trial/test rank 56. It is not an online, nonlinear-imaging or deployment-speed result.
