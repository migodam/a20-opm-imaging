# A20 Route A：公开包文件、数据边界与复现索引

索引日期：2026-10-05。本文件整理当前已有文件及静态可核对的数据合同，不新增实验，不作最终科学或新颖性判断。六个对象均为 `historically_exposed_feasibility`；来源里的 historical `validation` 标签不能被解释为 A20 新盲测。

## 阅读入口

| 文件 / 目录 | 用途 |
|---|---|
| [START_HERE.md](../START_HERE.md)、[README.md](../README.md) | 项目入口与主线程记录的实际进展。 |
| [冻结执行协议](../protocol/CODEX_ROUTE_A_OPM_IMAGING.md)、[GO/NO-GO gates](../protocol/GO_NO_GO_GATES.md) | 研究范围、执行顺序、前置 gate 与 proposed thresholds；任务书阈值不是已完成的结果。 |
| [成像理论](../protocol/OPM_IMAGING_THEORY.md)、[resolvent approximation](../protocol/OPM_RESOLVENT_APPROXIMATION.md)、[degree 理论](../protocol/ADAPTIVE_DEGREE_THEORY.md)、[反例账本](../protocol/THEOREM_COUNTEREXAMPLE_LEDGER.md) | 公式、适用条件和已规定的反例。 |
| [configs/frozen.json](../configs/frozen.json)、[configs/parents.json](../configs/parents.json) | 固定配置及六 parent 的参数化、runtime/offline 路径、两个历史状态。 |
| [后端映射](BACKEND_MAP.md)、[协议冲突记录](PROTOCOL_CONFLICTS.md) | 实际 Maxwell 内核、Schur/O/P/M、A1/A2、共同 constrained QP 的函数落点和证据范围。 |
| [复现合同](REPRODUCE.md) | 依赖、阶段入口、成本账本和独立复现的记录规则。 |
| [最近先例审计](CLOSEST_PRIOR_AUDIT.md)、[protocol/REFERENCES.md](../protocol/REFERENCES.md) | 有界 R04/R05 机制证据、R06 摘要背景及访问缺口。 |
| [NOTICE.md](../NOTICE.md)、[LICENSE](../LICENSE) | 代码和材料来源声明；vendor provenance 中的 hash 为历史字段，本轮不新计算。 |

## 六 parent 的输入范围

下面的维数来自 `configs/parents.json`，未读取 truth 数值。所有对象都有 6 sources、64 receiver positions、配置中的单频参数 `[2.0]`；current 维数为 5184，均保存 iteration 0、17 两个状态。

| parent | 历史 family | 参数化 | 实物料参数维数 | 在线问题 / 状态 | 离线标签 |
|---|---|---|---:|---|---|
| 2001 | gaussian | Gaussian | 54 | `data/runtime/2001/problem.npz`；`state_00.npz`、`state_17.npz` | `data/offline/2001/labels.npz` |
| 2005 | contact | Gaussian | 54 | `data/runtime/2005/problem.npz`；`state_00.npz`、`state_17.npz` | `data/offline/2005/labels.npz` |
| 2003 | gaussian | Gaussian | 54 | `data/runtime/2003/problem.npz`；`state_00.npz`、`state_17.npz` | `data/offline/2003/labels.npz` |
| 2007 | contact | Gaussian | 54 | `data/runtime/2007/problem.npz`；`state_00.npz`、`state_17.npz` | `data/offline/2007/labels.npz` |
| 2010 | shell | voxel | 3456 | `data/runtime/2010/problem.npz`；`state_00.npz`、`state_17.npz` | `data/offline/2010/labels.npz` |
| 2013 | asymmetric | Gaussian | 54 | `data/runtime/2013/problem.npz`；`state_00.npz`、`state_17.npz` | `data/offline/2013/labels.npz` |

**物料图表的先验边界：** 保存的 Gaussian chart `Q` 可能继承历史 support/shape 知识。各方法共用同一个 Q 控制同一参数化的比较，但不能据此宣称一般未知形状成像，也不能消除历史数据暴露。`MaterialChart` 保留原 Q 的体积度量；voxel 参数化使用完整 cell 物料坐标。这个索引没有审计 Q 的历史生成过程或证明 Q 与 support 知识无关。

## NPZ schema 与在线 / 离线隔离

本轮仅打开 NPZ 目录信息并读取键名，没有索引任何 archive 数组，也未读取 truth、held_truth、旧步或梯度的数值。现有 24 个 NPZ 为 6 个 problem、12 个 state 和 6 个 offline labels。

| 文件模式 | 本轮实际核对的键名 | 用途与读取合同 |
|---|---|---|
| `data/runtime/<parent>/problem.npz`，6 个 | `Q, data0, dirs, historical_exposed, init, k, kind, obs_basis, parent_id, points, pols, receivers, scale, volume` | 与 [`backend.RUNTIME_KEYS`](../src/a20/backend.py) 完全一致；`load_problem` 拒绝额外或未登记的键，使用 `allow_pickle=False`。 |
| `data/runtime/<parent>/state_00.npz` / `state_17.npz`，12 个 | `chi, ell, iteration, lambda_total` | 历史 replay 状态输入，使用独立 state 读取路径；不是 `load_problem` 的 problem schema。保存的 chi 属于已暴露历史轨迹。 |
| `data/offline/<parent>/labels.npz`，6 个 | `gradient_0, gradient_17, held_truth, old_relative_residual_0, old_relative_residual_17, physical_step_0, physical_step_17, step_0, step_17, truth` | 仅供独立离线评价及历史参考审查；不进入在线问题、构基、O/P/M probes、物料更新或停止决策。历史 step 不能自动当成当前 constrained QP 的合格参考。 |

已核对的 **runtime NPZ 不含 truth、held_truth、full J、full H、旧 steps 或旧 gradients**。在线 `Problem` 对 truth/teacher/full_J/full_H/reference_step/labels 属性访问作显式拒绝；`BasisView` 拒绝标签、full J/H、reference step、full current correction 等构基能力。具体实现见 [`src/a20/backend.py`](../src/a20/backend.py)，本地拒绝测试的覆盖范围见 [BACKEND_MAP.md](BACKEND_MAP.md)。公开包包含离线文件以便独立审查；路径和用途隔离不能被解释成标签从未公开或构成盲测。

**Held receiver 残差：`NOT_RUN`。** 当前 runtime 白名单没有登记独立 held receiver geometry/observation contract。offline 里存在 `held_truth` 键不补齐这些几何条件；不能由该字段新造 receivers 或外部观测。普通 truth/held_truth 独立评价也不能冒充 held receiver 接收残差实证。

## 实现与保存证据

| 文件 / 目录 | 索引用途与现有证据边界 |
|---|---|
| [src/a20/backend.py](../src/a20/backend.py)、[vendor/a17/](../vendor/a17/) | 原 vector-Maxwell DenseDDA adapter 和保存的作者既有内核；runtime whitelist、实物料图表和计费物理 actions。 |
| [src/a20/opm.py](../src/a20/opm.py)、[src/a20/material.py](../src/a20/material.py)、[src/a20/imaging.py](../src/a20/imaging.py) | Schur、O/P/M seeds/degree 空间、投影、共同约束二次模型及付费 full-objective/KKT acceptance/stop。源码存在不等于 imaging gate 完成。 |
| [src/a20/replay.py](../src/a20/replay.py)、[src/a20/cli.py](../src/a20/cli.py)、[src/a20/costs.py](../src/a20/costs.py) | replay/阶段调度、历史参考审核、失败与成功成本记录。 |
| [src/a20/robustness.py](../src/a20/robustness.py) | 条件调用的 noise/warm timing 实现；调用须满足主线程 gate 和剩余预算。不能把实现及 tiny 检查当作真实 robustness/timing 结果。 |
| [tests/](../tests/)、[results/G0_LOCAL.json](../results/G0_LOCAL.json)、[results/tests/LATEST.json](../results/tests/LATEST.json) | G0_LOCAL **26/26 PASS**：CPU tiny 2³-cell 真实 Maxwell 接口/数值完整性、独立 synthetic regression 和小 loop；非原六对象质量或速度证据。 |
| [results/G0_REAL.json](../results/G0_REAL.json) | 两个历史真实状态 2001/2005、iteration 0 的 G0 **PASS**；非六对象 replay、完整非线性成像 fidelity 或总成本结果。 |
| [results/G0_ALGEBRA.json](../results/G0_ALGEBRA.json) | 20 次有限维 synthetic algebra 与既定反例的 **ALL ASSERTIONS PASSED**；不属于 Maxwell 成像 benchmark。 |
| [results/jobs/](../results/jobs/) | job manifests、逐动作 cost JSONL、完整 job receipts 及失败材料；失败和重跑成本必须保留。 |
| [tools/summarize_evidence.py](../tools/summarize_evidence.py) | 对已有 replay/action/receipt 做机械 CSV、静态科学图和历史 parent paired bootstrap 汇总；不替主线程作 gate/scientific judgment。 |

真实对象的跨频大规模 pilot 未由这三层 G0 覆盖。此索引不核验或宣告 replay、G1 表征质量、G2 总部署成本完成；任何阶段文件或可调用 CLI 的存在均不能替代对应结果和 gate 判决。

## 文献材料与不随包附入的内容

[research/claim_audit/CLAIM_LEDGER.csv](../research/claim_audit/CLAIM_LEDGER.csv) 保存 claim、定位与 gap；[source_access.json](../research/claim_audit/source_access.json)、[verified_sources.json](../research/claim_audit/verified_sources.json)、[search_log.json](../research/claim_audit/search_log.json) 保存访问、身份核验和查询记录；原 ScholarQA 响应亦在该目录。

已保存审计报告记录：精确标题 collect 的四个操作全部 HTTP 429；随后三个预定 arXiv ID 身份核验成功。R04/R05 只按报告中的原文定位与版本读取范围使用，R06 为摘要级背景；没有全面优先权检索或独立实验复现。访问缺口不能被标记为完成验证，也不能作为新颖性证明。

**不附第三方论文全文或 PDF。** 包内只保留引用、外链、元数据、有限证据定位和访问状态；外部依赖源码亦不随包复制。第三方全文需读者自行从合法来源访问。本轮索引没有调用网络或重新计算任何 SHA/hash。

## 复现入口与账本

完整环境和操作顺序见 [REPRODUCE.md](REPRODUCE.md) 与 [pyproject.toml](../pyproject.toml)：Python≥3.10、NumPy、SciPy；静态图另用 matplotlib，真实 CUDA pilot 使用已有支持 complex128 的 PyTorch/CUDA 环境。所有物理计算使用 complex128/float64；复现不要求作者的主机、账号、私钥或新增 GPU infrastructure。

| 入口 | 应复现或读取的范围 |
|---|---|
| `tests/run_integrity.py` / unittest | 本地 tiny G0 完整性；具体覆盖以保存的 test 报告为准。 |
| `python -m a20.cli algebra --device cpu --job <new-id>` | 协议既定 synthetic algebra，写自己的 job receipt。 |
| `python -m a20.cli g0-real --device <cpu-or-cuda> --job <new-id>` | 真实状态 G0；有实际物理成本。 |
| CLI `replay` / `a1` / `a2` / `noise` / `timing` / `evaluate` | 登记的后续阶段入口；前置 gate、矩阵范围和剩余预算见冻结合同。这里列入口，不代表阶段已执行或通过。 |
| `python tools/summarize_evidence.py --root <copy-root>` | 汇总该拷贝已有的结果、缺失、失败及成本；保留实际 rank/actions 与 parent 层级，不把历史 parent bootstrap 当成盲测结论。 |

从拷贝根目录设置 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1` 和单线程 BLAS 环境；每个重跑使用新 job ID。公开包中的旧 `results` 应完整保留为只读 `prior_evidence`，独立复现在新的 `results` 中记录自己的完整成本；不能删除旧失败 receipt 绕过预算，也不能将另一轮成本/结果混入本轮。累计限制、锁和停止条件遵循现有复现合同。

本索引的schema审计只读键名而未读取数组数值；它不能决定科学gates。完整replay、失败及最终判断已另交[中文报告](../RESEARCH_REPORT_ZH.md)、[replay索引](../REPLAY_REPORT.md)及[gate decision](../results/GATE_DECISION.json)，发布状态另见[发布回执](../results/PUBLICATION.json)。
