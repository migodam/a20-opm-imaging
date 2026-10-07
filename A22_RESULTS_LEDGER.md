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
