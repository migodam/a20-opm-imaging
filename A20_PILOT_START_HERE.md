# A20 Route A：OPM 材料成像

**结果：当前实现不进入 A1（NO_GO）；完整 12-state H-step 筛选为 HOLD。** 注册的 G0 后端检查通过，六个历史对象、各 iteration 0/17 的 replay 已完成尝试。voxel 对象的两个完整受约束参考未过 KKT 审核，真实求解失败保留。A1/A2、噪声成像和完整 cold/warm 部署计时均为 NOT_RUN，未取得成像质量或加速 GO。

有有效参考的五个 Gaussian 对象（10 states）中，mixed degree 3 的 H-step 相对误差中位数为 **74.24%**：初始状态中位数 **2.24%**，晚期 **269.51%**。degree 5 的十状态中位数仍为 **72.72%**。这是有限子集的诊断，不能替代登记的12-state gate。实际 current rank 为20–80，full dimension为5184。

![早晚状态分别展示，灰格没有填造数值](results/replay/phase_plots/mixed_H_step_by_state.png)

先读 [中文结果与科学边界](RESEARCH_REPORT_ZH.md) 和 [最终 gate](results/GATE_DECISION.json)。逐状态、parent 和2000次配对 bootstrap表在 [证据汇总](results/summary/SUMMARY_REPORT.md)；原始动作/费用在 [replay账本](results/jobs/replay-01/cost.jsonl)，全部尝试及失败在 [replay记录](results/replay/replay.jsonl) 和 [失败日志](results/replay/failures.jsonl)。

实现复用保存的 A17/A9 DenseDDA，complex128/float64；精确 Schur、独立 O/P/M native streams、受约束二次步、full-objective 接受和缓存刷新见 [公式—后端映射](docs/BACKEND_MAP.md)。[测试清单](docs/G0_TEST_INVENTORY.md)区分代数、tiny Maxwell、两个原尺寸初始状态及真实多频缺口。[协议冲突](docs/PROTOCOL_CONFLICTS.md)保留旧投影式步骤、缺参考 gate 汇总修复等处理；物理 replay 的实际源码 commit 为 `68ab91576c2f457e8afec0a2a9537ca5134018ea`，修正后的离线 gate 来源另记。

复现前读 [复现合同](docs/REPRODUCE.md) 和 [公开输入索引](docs/PUBLIC_PACKAGE_INDEX.md)。`data/runtime` 为在线输入，`data/offline` 为独立评估真值/旧参考，后者不得进入构基。六对象已历史暴露，保存的 Gaussian Q 还可能继承既有 support 信息；本轮不是盲测或未知形状泛化证据。POD/更强 goal-aware ROM 缺少合规输入，明确 NOT_RUN。最近先例与检索缺口见 [文献审计](docs/CLOSEST_PRIOR_AUDIT.md)。

总计费在两小时 CPU、十二小时 GPU 上限内；GPU占用约89.60分钟，CPU总计低于90分钟，含失败、参考、重跑、审核与明确保守 allowance，详见 [最终预算](results/BUDGET_FINAL.json)。GPU数值为独占作业墙钟而非 kernel time。未训练 NN、未修改 Maxwell solver、未开展 PCG/GMRES acceleration，未新核验 SHA256。

发布状态与科学状态分开：见 [发布回执](results/PUBLICATION.json)。仓库 [migodam/a20-opm-imaging](https://github.com/migodam/a20-opm-imaging)，[release](https://github.com/migodam/a20-opm-imaging/releases/tag/v0.1.0-pilot)，[匿名 raw 入口](https://raw.githubusercontent.com/migodam/a20-opm-imaging/main/START_HERE.md)。

English: registered backend checks passed; all 12 frozen states were attempted. No degree is eligible for nonlinear imaging. Five Gaussian parents show large late-state H-step errors; both voxel references failed the fixed KKT audit. The complete reference screen is HOLD and progression with this implementation is NO_GO. This archive supports neither nonlinear reconstruction parity nor deployment acceleration.
