# A22: frozen experiment package for GPT

Public branch: [a22-three-fold-opm](https://github.com/migodam/a20-opm-imaging/tree/a22-three-fold-opm). This entry concerns A22. Inherited A20/A21 reports and root-level historical gates are not A22 decisions.

**Conclusion: Gate A screening PARTIAL; STOP.** The formal 24-scene study, one-shot physics imaging and prior-only NN are NOT_RUN. Gate T is NOT_ESTABLISHED. No NN was trained and no follow-on reconstruction was started.

Original completed local experiment commit: `153e326b14062aacb696c5e466eeac6fc01162a1`. Publication followed the user's subsequent request for a GPT-readable URL; the original manifest's LOCAL_ONLY field retains its historical meaning.

The four historically exposed scenes are 2001, 2003, 2014 and 2009: four independent statistical clusters, not 2112 independent objects. The deployment assumption is known background `0.1+0.04i`, a 32-real-dimensional material chart and U8/O4/P4/M4 degree1, with actual current rank32.

A3 scene-median Spearman is 0.506893. A2 MAE is 0.0375231 and A3 MAE is 0.0375705: relative improvement -0.1263%, versus the preregistered positive entry requirement of at least 15%. The 2000 paired scene-bootstrap interval crosses zero. All original objects exceed the declared pointwise prior. These budgets are empirical indicators, not full nonlinear certificates. The 130 unit tests and actual tiny-backend checks support implementation consistency only.

## Frozen theory and execution contract

- [START_HERE.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/START_HERE.md)
- [THREE_FOLD_RECOVERABILITY_THEORY.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/THREE_FOLD_RECOVERABILITY_THEORY.md)
- [TWO_SIDED_RECOVERABILITY.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/TWO_SIDED_RECOVERABILITY.md)
- [MATERIAL_PHYSICS_PRIOR_SPLIT.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/MATERIAL_PHYSICS_PRIOR_SPLIT.md)
- [ONE_SHOT_OPM_IMAGING.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/ONE_SHOT_OPM_IMAGING.md)
- [LIGHTWEIGHT_EXPERIMENT_SPEC.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/LIGHTWEIGHT_EXPERIMENT_SPEC.md)
- [GO_NO_GO_GATES.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/GO_NO_GO_GATES.md)
- [THEOREM_COUNTEREXAMPLE_LEDGER.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/THEOREM_COUNTEREXAMPLE_LEDGER.md)
- [CODEX_ROUTE_A_RECOVERABILITY.md](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/protocol/a22/CODEX_ROUTE_A_RECOVERABILITY.md)

## Raw evidence

- [Frozen configuration](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/configs/a22_portable.json)
- [Preregistration](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/PREREGISTRATION.json)
- [Statistical evidence](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/statistics/STATISTICS_EVIDENCE.json)
- [Per-scene statistics](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/statistics/per_scene_statistics.csv)
- [Complete cases CSV](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/stage_a/direction_metrics.csv)
- [Screening decision](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/SCREENING_DECISION.json)
- [Resource and operator accounting](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/ACTION_ACCOUNTING.json)
- [Failure ledger](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/FAILURE_LEDGER.jsonl)
- [Original local delivery manifest](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/FINAL_DELIVERY_MANIFEST.json)
- [Pairing and completeness audit](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/stage_a/EVIDENCE_COMPLETENESS_AUDIT.json)

[Implementation](https://github.com/migodam/a20-opm-imaging/tree/153e326b14062aacb696c5e466eeac6fc01162a1/src/a22) | [Tests](https://github.com/migodam/a20-opm-imaging/tree/153e326b14062aacb696c5e466eeac6fc01162a1/tests) | [Plots](https://github.com/migodam/a20-opm-imaging/tree/153e326b14062aacb696c5e466eeac6fc01162a1/figures/a22/statistical)

## Interpretation boundaries

Separate conditional theory, numerical identities, actual Maxwell evidence, OFFLINE diagnostics and deployable online provenance. Unit tests, raw budget coverage and low rank do not establish imaging or deployment success. The reports below preserve sample limits, chart-exterior energy, failed attempts, unrecorded full 32-dimensional solution vectors and NOT_RUN work.

---

## Complete report: A22_GATE_DECISION.md

# A22 科学判定：PARTIAL，停止

**停止24场景扩展、one-shot physics 成像和 prior decoder。** 四场景筛查完整，但结构化描述子未显示预注册要求的增量价值。结果保留为 PARTIAL，不制造 PASS，也不将条件定理判为已被推翻。

| Gate | 状态 | 依据 |
|---|---|---|
| 实现验证 | PASS | 130项单元验证及两份随包 verification/真实 tiny backend 检查通过 |
| A screening | **PARTIAL** | 中位rho0.5069，但MAE改善−0.1263%，95%区间跨零；不满足扩展入口 |
| A 完整24场景 | NOT_RUN | screening没有正向增量信号，不扩展 |
| B 物理/先验分离 | NOT_RUN | A非正式PASS；候选split未获有限幅度成像验证 |
| C 有用one-shot结构 | NOT_RUN | 未进入Stage B；coarse coefficient主门槛未评估 |
| D prior-only decoder | NOT_RUN | A/B/C未全部PASS；没有训练任何NN |
| T 部署成本 | **NOT_ESTABLISHED** | 缺同质量的端到端对照；不从低rank推出速度收益 |

冻结 screening 的正向入口是 A3 场景中位 Spearman≥0.5 且相对较强 A1/A2 的 LOSO MAE改善≥15%。clear-negative 定义为rho<0.5且改善区间上界≤0；两者均未满足，因此按预注册的其它分支判PARTIAL并停止。四场景 screening 永远不能授予正式 Gate A PASS。权威机器记录为 [GATE_DECISION.json](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/GATE_DECISION.json) 与 [SCREENING_DECISION.json](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/results/a22/SCREENING_DECISION.json)。

A2 MAE为0.0375231，A3为0.0375705；A3−A2的变化不能支持结构化 recoverability descriptor 更准确。绝对改善95%区间 `[−0.0061458,+0.0018125]`，bootstrap以4个场景为paired cluster，条件于已保存的校准，不是2112个独立样本。

## 五类证据

| 类别 | 已完成的内容 | 科学边界 |
|---|---|---|
| 理论包已有命题 | 原文冻结保留 | 未重新做理论；实验不代替条件证明 |
| 数值身份/单元验证 | packing/adjoint/metric/两侧/极化率/KKT/隔离/预算 | 支持实现一致性，不授予成像GO |
| 实际Maxwell实验 | 四对象、32 clean标签、2112恢复案例 | 历史暴露、known-background、固定32维图的经验筛查 |
| OFFLINE/oracle | full-J/SVD式比较、原材料审计 | 未用truth-state/late-GN oracle作在线方法；未跑新的oracle construction |
| Deployable online | 仅known-background/probe/residual动作构基与冻结预测 | 证明信息来源合规；尚无one-shot图像质量或部署收益证据 |

四对象均超出声明逐点先验，asymmetric/shell 的 W 能量覆盖很低。这些事实限定当前经验指标和材料模型的适用性；不把宽 raw budget 的100%覆盖包装成严格证书，不通过扩大rank/degree/先验或网络救场延续实验。

本地代码、配置、输入、原始结果、表图、失败与费用全部保留。后续路线条件驱动仍未冻结，研究状态不是三阶段全部实施成功。The experiment stopped at local delivery. The completed evidence is subsequently shared on an independent A22 public branch following the user's link request. Scientific gates remain unchanged; no follow-on stage is started. The original LOCAL_ONLY manifest is preserved as a historical record.


---

## Complete report: A22_RESULTS_LEDGER.md

# A22 Maxwell 筛查结果

O/P/M 结构化描述子能显示部分方向难度相关性，但没有达到相对普通 nuisance/ROM 基线的预注册增量门槛。**Gate A：PARTIAL，停止扩展与 Stage B/C。** 这是四个历史暴露场景的已知背景经验筛查；完整24场景及新的盲评估均 NOT_RUN。

## 实验与统计单位

对象固定为2001、2003、2014、2009。各冻结8个在线方向，前4个做两档有限幅度；使用完整 complement nuisance、零/低/高噪声、nominal 与5%源幅度/3% receiver增益干预。噪声在同一 clean data 上生成，两干预共享实现。零噪声1次，非零各16次。

保存32个 clean Maxwell 标签、2112个独立案例键，0 INVALID_QP，全部实际 current rank32。先平均噪声重复，得到192个评估单元、每场景48个；独立 cluster 只有4个。A0–A3 预测同一个受约束32维 OPM 求解的方向系数误差，未各自运行不同求解器。

主标签是 `abs(vᵀ(theta_hat-theta_true))`，v为质量度量下单位材料方向；Gate A 不使用相对误差 floor。相对误差辅助字段使用预注册 `1e-6` floor，此次0个案例落入该 floor。每个方法使用一个非负、无截距的乘数，按场景留一校准；没有按家族、方向或噪声重新调参。

## 主比较：等场景权重、LOSO、全部噪声

| 方法 | 信息范围 | 场景中位 Spearman | 等场景 MAE | 校准后经验 coverage |
|---|---|---:|---:|---:|
| A0 | 在线总响应/小矩阵 sensitivity | 0.4111 | 0.047168 | 12.50% |
| A1 | 在线 nuisance/attribution | 0.5032 | 0.040727 | 20.83% |
| A2 | 在线非结构化 ROM/有限幅度预算 | 0.4812 | **0.037523** | 39.58% |
| A3 | 在线 O/P/M 与 primal/dual 结构预算 | **0.5069** | 0.037571 | 40.63% |
| full_J | OFFLINE profiled full-J witness | 0.4848 | 0.039599 | 23.44% |
| full_J_total | OFFLINE total sensitivity/SVD-style | 0.4111 | 0.050071 | 7.81% |

完整 J 对照也是难度预测量；表中不是 full-J 求解器的成像误差，不能据此声称 OPM 成像优于完整 Maxwell。coverage 定义为观测平均误差不超过预测值的比例，是经验量；A3 原始宽预算覆盖率100%，缩放后40.63%，二者均不是标称置信保证。failure AUC 为 UNDEFINED：没有预注册并形成有效双类的 failure labels；0个无效QP不等于0个恢复失败。

相对较强 A2，A3 的 MAE 改善为 **−0.1263%**（略变差），要求为至少+15%。2000次 paired scene bootstrap 的绝对改善95%区间为 **[−0.0061458,+0.0018125]**，相对区间为 **[−35.78%,+2.77%]**。每次重选较强 A1/A2；区间条件于已保存 LOSO fits，不包含重新训练/校准的不确定性。

## 逐场景与材料模型

| 场景/原 family | A3 Spearman | A3 MAE | 固定 W 保留的原对象材料能量 | 最大逐点材料扰动 |
|---|---:|---:|---:|---:|
| 2001 gaussian | 0.2249 | 0.027771 | 46.49% | 0.8333 |
| 2003 gaussian | **−0.1811** | 0.098638 | 48.98% | 2.3426 |
| 2014 asymmetric | 0.9457 | 0.009975 | **5.77%** | 2.1023 |
| 2009 shell | 0.7889 | 0.013899 | **13.37%** | 2.2024 |

Gaussian 两场景排序较弱，2003为负相关；较高 aggregate 中位相关性不能覆盖这一点。A3 相对 A2 在两个 Gaussian 的 MAE略改善，在 asymmetric/shell 上变差，增量不稳定。

四场景均超出0.25逐点先验；非Gaussian对象大部分材料能量在固定 W 外。因此这些结果检验的是所实现的经验预测器及其声明范围，不能反驳要求有效区域预算的理论命题，也不能证明 `V_phys/V_prior` 已形成有用成像分离。未按结果扩大先验、材料维数或 OPM 阶数。

## 噪声与数值核对

128个非零噪声组各16次，无缺失；1056个 nominal/calibration 配对的 noise seed 完全一致。方向系数实际标准差除以 whitened noise SD 的场景中位分别为：2001 `5.9794e-4`、2003 `5.5504e-4`、2014 `3.2517e-4`、2009 `1.3478e-4`。对应 regularized linear witness gain 为 `5.5810e-4`、`6.1661e-4`、`4.0673e-4`、`3.7745e-4`；受约束非线性估计器的经验方差不必等于线性读出公式。

四个 anchor source residual 最大 `5.1936e-15`。32个有限标签中28个保存数值 residual，最大 `5.2355e-15`；4个 legacy 标签未保存该数值，保留 `LEGACY_NOT_RECORDED`，不补造值。legacy 缓存经重新付费 AW/provenance/冻结输入核对后使用。

## 输出与成本

| 输出 | 位置 |
|---|---|
| 全案例、状态/家族与split审核 | `results/a22/stage_a/` CSV、JSONL与各 scene 目录 |
| Canonical 统计、单方法校准和2000次bootstrap | `results/a22/statistics/` |
| 主图与精确绘图数据 | `figures/a22/statistical/`、`results/a22/reporting/statistical/` |
| 经验噪声放大 | `stage_a/noise_amplification.csv` |
| 已观察方向的系数重建数组 | `stage_a/directional_reconstructions.npz` |
| Clean 六源标签、原对象中心与truth系数 | `stage_a/scene_*/OFFLINE_label_*.npz`，OFFLINE ONLY |
| 完整性/配对/缺口审计 | `stage_a/EVIDENCE_COMPLETENESS_AUDIT.json` |
| 全部资源/动作与失败 | `results/a22/ACTION_ACCOUNTING.json`、`cost_ledger.csv`、`COST_LEDGER.jsonl`、`FAILURE_LEDGER.jsonl` |

方向数组包含2112个实际 target coefficient、estimate、signed error及32维误差范数。Stage A 没有保存每次完整32维解向量；空间 Stage B 重建数组为 NOT_RUN。这一缺口不通过新物理重跑掩盖。所有原始标量、输入、冻结模型与噪声seed已保存，可按原收费规则复现。

计费权威为各作业 inclusive receipt 和唯一 external scope。CPU 含明确标注的保守源码/交付 allowance；GPU 为CUDA相关作业整段占用。嵌套 span、generic Maxwell aggregate 不再次叠加。F/F*/L/L*、完整 solve RHS、LU、receiver、缓存、失败及重跑分别列出。A0–A3 共用此次实现，独立部署耗时为 NOT_MEASURED；单场景尾段时间不是冷启动端到端成本。旧 A20/A21 成本仅作历史来源，不计入 A22。最终数额以 `ACTION_ACCOUNTING.json` 和 `FINAL_DELIVERY_MANIFEST.json` 为准。

| 最终A22账本 | 已计费用/次数 | 上限 |
|---|---:|---:|
| CPU费用，含明确保守allowance | 1838.861312秒（30.65分钟） | 无新增CPU硬上限；完整记录 |
| CUDA相关整段占用，含失败与重跑 | 1350.713880秒（22.51分钟） | 32400秒（9小时） |
| 生成/扰动full-wave额度，含验证 | 60 | 192 |
| 新场景teacher labels | 0 | 9 |

费用summary为 `RECORDED_ONLY`，没有live job、未解决记账记录或计费问题。导出/本地Git检查的10秒CPU保守预留有明确来源，不称为实测CPU。

未生成九个新场景，未进入24场景扩展、Stage B/C、runtime campaign或NN。Gate T 没有同质量端到端对照，保持 NOT_ESTABLISHED。


---

## Complete report: A22_IMPLEMENTATION_REPORT.md

# A22 实现与验证报告

Stage A 四场景筛查已完成。Gate A 为 **PARTIAL**，按预注册停止扩展、one-shot 成像和 NN。完整 24 场景实验、Stage B/C 的条件性驱动均未执行；不能把本地接口和测试通过称为整条路线成功。

## 冻结来源与计算模型

工作分支为 `a22-three-fold-opm`，基于 A21 commit `8aa2d5d03c8fc41bda508c2e173a45fa2fea956a`。八份原理论文件与三个 route 的副本保存在 `protocol/a22/`；母目录理论、A17–A21 原代码及账本保持冻结。A22 使用独立 `src/a22` 和账本，未修改 DenseDDA/Maxwell solver，未调用旧 `reconstruct()` 或 A21 oracle cache loader。

部署假设是已知实际背景 `0.1+0.04i` 的材料扰动成像。材料图包含 8 个粗八分块、8 个中心化局部 x 细节，共 16 个与 truth 无关的空间基，分别用于实部和虚部，形成 32 个实自由度。空间基满足 `v QχᵀQχ=I16`，因此系数欧氏范数等于图内的体积加权材料范数。W 外材料不属于 `V_prior`，另行记录。

电流采用原 `dipole/sqrt(v)` 单位。固定 `U8/O4/P4/M4`、degree1、总 current rank 上限32；四场景实际 rank 均32。六源先汇集再压缩，O 探针显式使用固定随机数，构基残差置零，不由 noisy measurement 替换。Galerkin core 使用原尺度与条件门槛；失败直接留账，无 Petrov/full fallback、Maxwell 伪逆或隐藏 jitter。

六源各有128复通道，逐源 `[Re128, Im128]` 打包，总1536实数据。proper complex Gaussian 噪声满足实、虚方差各 `σc²/2`；`σc=0.01×已知背景预测数据RMS`，白化为 `sqrt(2)/σc`。旧 `1/problem.scale` 仅保留为历史目标归一化，不用于此次噪声尺度。

## 五个接口

| 接口 | 实现 | 职责 |
|---|---|---|
| `build_anchor` | `src/a22/online.py` | 付费构造已知背景完整状态、噪声参考与 provenance |
| `build_opm` | 同上 | 固定浅层 O/P/M 与 Schur feedback，返回实际 rank 和成本 |
| `material_features` | 同上 | 用压缩 B、小核及接收像形成六源 MW/PMW 和1536×32实 AW |
| `build_split` | `src/a22/core.py` | 构造图内候选 `V_phys/V_prior`、读出 D 和 block 审核；有限幅度未验证时保留未解决状态 |
| `evaluate_recovery` | `src/a22/evaluate.py` | measurement 减背景、白化、一次受约束材料 QP；不读取 truth/full J |

下层 `constrained_material_solve` 保持原约束、显式 Tikhonov 正则化、SLSQP/active-equation 路径及原 KKT/可行性容差 `1e-8`。原3456条逐单元不等式在此固定图中只有32种完全相同的 `(系数行,下界)`；仅在优化器输入中精确去重，最终可行性、法向、互补性和 KKT 仍按全部原约束审核。没有近似合并或事后裁剪。等价性记录见 `results/a22/EXACT_CONSTRAINT_EQUIVALENCE.json`。

公式—函数、配置、种子和成本来源详见 [源码映射](https://raw.githubusercontent.com/migodam/a20-opm-imaging/153e326b14062aacb696c5e466eeac6fc01162a1/research/delegated/a22-delivery-audit/SOURCE_INTERFACE_MAP.md)。

## 信息边界与有限幅度范围

在线资产白名单仅含 geometry、选定 measurement、init；构建视图拒绝 truth、teacher、full J/H、GN optimum 和 oracle currents。所有方向、预测和预算先冻结，再打开独立的 `data/a22/offline_eval`。full-J/SVD 对照只在 OFFLINE 评估器中建立，未进入在线特征、选方向或基底。

有限标签的中心是原对象材料，目标和全部31维 complement nuisance 同时变化；在线 anchor 始终为公开已知背景。旧 data0 生成网格为 n14，保存材料与新标签求解网格为 n12；旧观测不作为新同网格标签。四个原对象及其变体均标记历史暴露。

T10 实现包含实际 Clausius–Mossotti/辐射反作用的 `a''=-18vc/(3+cχ)^3`，其中 `c=1-i·3k³v/(6π)`，并检查区域分母与充分 resolvent 裕度。背景/局部分量的代数界不能自动覆盖原对象及 W 外成分。全部预测仍标记 `empirical_indicator`、`full_model_uniform_certificate=False`；校准不使其成为严格证书。

## 实现验证

| 证据 | 保存结果 | 范围 |
|---|---|---|
| 单元与 tiny fixture | `a22-unit-013`：130 PASS，0失败/错误/跳过 | packing、白化、metric/gauge、nuisance profiling、block、QP/KKT、隔离、缓存、预算与监控 |
| 两份随包 verification | `a22-cuda-validate-002`：均 PASS | 原协议代数与小规模数值验证，未重做证明 |
| 实际 DenseDDA 健康检查 | CPU/CUDA 均 PASS | 4³单元、原六源/128通道、伴随、导数、直接通路和 Schur/Galerkin |
| 实际两侧缺陷恒等式 | 相对残差 `9.1632e-15` | 小网格实现一致性 |
| 实际极化率二阶导数 | 有限差分相对误差 `2.6784e-11` | 包含物理非线性余项，不是全域成像证书 |

具体记录位于 `results/a22/unit_validation/`、`validation/`、`validation_cuda/`。失败版本也保留。后加报告 discovery fixture 曾因 macOS `/var` 与 `/private/var` 路径别名失败，规范化 fixture 后全部通过；这不涉及物理代码。

## 运行、恢复与未执行部分

XINAN 使用既有 Python3.10.9、NumPy2.2.6、SciPy1.15.3、PyTorch2.6.0+cu124、RTX4060 Laptop/8GB，complex128/float64。共享 A20 GPU 锁保护单一作业。每个失败、重跑、参考、验证和计时保留费用，不重置额度。

screen001/002 因 Windows 监控读取 `PermissionError` 中断，209与337条阶段记录分别归档。screen003 使用 native `FILE_SHARE_READ|WRITE|DELETE` 快照读取，正常完成，0次读取冲突。原始两个错误记录未保存具体函数/errno，根因精度缺口保留。续跑重新付费构基，AW 与原值差0，科学 provenance、方向、预算与缓存严格核对；保留终止性 INVALID 行，不为失败挑选重跑。

Stage B/C 的完整条件驱动未冻结、未实现、未运行；CLI 明确拒绝前置 gate 未通过的调用。已有一次材料求解接口不是完成的 split-image pipeline。24场景扩展的输入、独立新seed接线和训练缓存也未执行。没有训练任何 NN、启动 nonlinear reconstruction、增加 degree/rank 或发布。


---

## Complete report: A22_COMMANDS_AND_SEEDS.md

# A22 命令、环境与固定随机性

源码基线：A21 `8aa2d5d03c8fc41bda508c2e173a45fa2fea956a`；分支 `a22-three-fold-opm`。最终本地 commit 由 Git 记录。完整科学配置是 `configs/a22.json`，重定位资产路径用 `configs/a22_portable.json`。没有重新检查 SHA256。

XINAN 实际环境：Python3.10.9、NumPy2.2.6、SciPy1.15.3、PyTorch2.6.0+cu124、RTX4060 Laptop/8GB。精度 complex128/float64。实际启动器固定 OMP/OPENBLAS/MKL/NUMEXPR threads=1。

## 已执行命令的入口与记录

每条命令使用唯一 job ID；不要覆盖已有receipt。下列为对应实际作业的可复核CLI入口，远程transport还承担共享锁、队列检查、child CPU尾段与硬预算停止。连接配置在仓库外，未复制凭据。准确environment/outcome/receipt保存在 `results/jobs/a22-*/`，transport记录在 `results/a22/transport/`。

```sh
PYTHONPATH=src python -m a22.cli unit --job a22-unit-013
PYTHONPATH=src python -m a22.cli validate --job a22-cuda-validate-002 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python -m a22.cli screen --job a22-cuda-screen-001 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python -m a22.cli screen-resume --job a22-cuda-screen-002 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python -m a22.cli screen-resume --job a22-cuda-screen-003 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python tools/a22_screen_decision.py --job a22-screen-statistics-001
PYTHONPATH=src python tools/a22_evidence_audit.py --job a22-evidence-audit-002
PYTHONPATH=src MPLBACKEND=Agg python tools/a22_render_outputs.py --job a22-render-001
```

上列 job ID 是历史记录，直接重用将拒绝。复现需复制干净输出、使用新ID并保留原收费上限；GPU物理作业须经现有transport/共同锁启动。`tools/a22_preserve_attempt.py`、`a22_remote_jobs.py stop/pull` 保留了两次中断与锁清理，不把缓存重放当成新物理标签。

## Seed与案例生成

master seed：**20261007**；bootstrap seed：**20261909**，repetitions=2000。场景顺序 `[2001,2003,2014,2009]`。实际 probe provenance、8个候选方向、完整预算均在 `stage_a/scene_*/online_provenance.json`、`frozen_online_directions.json`、`frozen_online_budgets.json` 冻结。

固定配置 U8/O4/P4/M4、degree1、material dimension32、current cap32。幅度 fractions `[0.2,1.0]`、pointwise max0.25、feasible fraction0.8、nuisance fraction0.35；方向来自online AW，筛查前4个方向做有限标签。

noise levels `[0,1,3]`，零噪声1次，非零各16次。每行的 `noise_seed` 是完整 `SeedSequence` 输入，见 `direction_metrics.csv/jsonl`；nominal/calibration成对共享seed。proper complex noise实虚各方差 `σc²/2`，尺度来自背景预测。物理干预通过相同六源/receiver布局的确定性线性变换实现，不采用独立随机factor噪声。

九个注册新场景未生成，24场景划分未执行。NN seeds只存在未执行配置中，不代表模型或训练记录。Stage B/C gate被拒绝；不要通过复现命令自动启动这些阶段。


