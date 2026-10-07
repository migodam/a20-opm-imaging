# Lightweight experiment specification：先检验信息分工，再训练网络

## 0. 状态与目标

本文件是将来交给 Codex 的规格，不是已运行实验报告。唯一已经运行的数值位于 verification/。本轮目标是回答 OPM signature 是否能预测 **真实可归因的材料恢复难度**，并决定哪些方向值得继续；不是扩大 polynomial degree，也不是调 diffusion。

## 1. 第一阶段：4-scene screening

优先从现有项目资产取 4 个独立场景：2 个不同散射强度的 Gaussian、1 个非 Gaussian 分段材料、1 个 multiscale/局部 patch。没有某一类缓存时明确缺项，可用小尺寸真实 full-wave 模型补一个，但不得把人工矩阵代替为该场景成功。

每个场景必须提供至少一个可部署 anchor：已知实际背景，或由 y 计算的 BP/EBA pilot。真值附近/late GN state 只用作 oracle upper bound，单独表格，不参与 route pass。

固定 W 的 k=32；需要时一次升到 64。固定 Q shallow degree≤1、rank 上限沿用已有缓存/预算，禁止以 test accuracy 搜索更大 degree。所有物理量统一 realification、whitening 和 material/current metrics。

先复现本包 verification，再在实际 solver 上做 directional finite difference、adjoint dot product、Schur direct-path 等价性、seed gauge 和 two-sided defect checks。

## 2. 第二阶段：最多 24-scene pilot

仅在 screening 有实用信号时，扩大到 3 个材料家族×每家族 8 个独立场景。每家族可按 3 development、1 calibration、4 held-out 划分，共 9/3/12。这是 pilot 的上限；它不足以支持很低的失败概率声明，confidence intervals 必须保留。

同对象的噪声、频率、材料近邻、不同初始化都归属同一 split。尽可能有至少一个家族完全作为 OOD 检验；这样会改变样本分配，须预先冻结，不能看到结果再挑较好方案。

## 3. Feature 与 label 必须分离

线上 features：M W、P M W、A W、少量指定 B/S/G actions、witness/attribution、模型余项 envelope、频率/几何。禁止 full J/H、truth current、s_F/e_F、full GN 最终解。

评估 labels：允许用 full solver、truth、精确小维 tangent 和可比 reference reconstruction。明确保存 `feature_origin` 与 `label_origin`。整个“诊断很准”的结论必须来自部署时可得到的 features。

## 4. Gate A 的 direction experiment

每个 scene 在固定 W 中选 6–8 个分层方向：较强/较弱 response、类似 total gain 但不同 fingerprint、较高/较低 attribution、不同材料尺度。方向的选择规则先冻结；不可按真实 recovery error 选成功方向。

每个方向做两档有限幅度 perturbation，加零噪声/低噪声/较高噪声。真正昂贵的 full-wave data 只需对无噪声场景求解，随后 noise draws 在缓存数据上生成。每个方向至少允许 nuisance coefficients 同时变化；仅 perturb 一个坐标、又告诉 inverse solver 其他坐标全固定，会把 detection 测成 recovery。

新 full-wave perturbation evaluations 总上限 192，且仍受 TIME 文件 2h 阶段上限约束。可先每场景 4 个方向、2 幅度，共 24×4×2=192；不要与“6–8 个方向全部 finite tests”的上限混淆。其余方向只做廉价 tangent diagnostics。

每次用统一的小 joint material reconstruction 算法得到 xhat；标签为对应 coefficient error、noise amplification、profile confidence coverage。解析 covariance 仅作为局部 Gaussian label，不能命名 full nonlinear posterior variance。

## 5. OPM 增量价值的实验，而非重新做一次 SVD

比较四级 diagnostics：

A0：||A v|| / small singular strength；A1：nuisance-profiled g；A2：A1 + factor-agnostic ROM/曲率量；A3：A2 + O/P/M structured/paired signature。

使用相同训练场景、类似统计模型容量。优先测试不需要训练的理论 error budget；需要回归时只用低容量模型，按 scene 交叉验证。

在固定精确线性模型、同噪声下，A3 不应声称比完整 J 更有信息。额外检验应放在有限幅度、背景失配、物理关联的 illumination/receiver/feedback 变化上；不能只给独立随机 ΔM/ΔP/ΔO 再当成真实 Maxwell 证据。

输出 Spearman、误差预测 MAE/校准、failure classification AUC（有两类时才算）、scene-cluster bootstrap intervals。所有同场景方向是相关样本，不按数百独立 scenes 计算 p 值。

## 6. Gate B/C 的 image experiment

同一场景运行 Born/BP 或已有 EBA、one-shot A-SVD、one-shot OPM-witness；有可用实现时加 Full GN/OPM-GN reference。one-shot OPM 的每次 Q construction、small solve 和可选 correction 次数都记录。

比较 r=4/8/16 中在 development 冻结的选择，不在测试集挑最优 r。分别报告 projected error、单位维度 error、relative retained truth energy、support/location/coarse-scale tasks、完整材料误差、真实 full-wave discrepancy。

要求 physics-only 在 V_p 中已经足够准确，剩余主要误差才集中 V_n。不能把 r=0、低真值能量 V_p 或随机 large complement 的高总误差当作“分离成功”。

## 7. 非线性 ambiguity 的轻量检查

首轮不做大型 reference posterior。已有合法近等数据材料对可以复查；小维模型允许多起点/有限候选扫描，但 solver 不收敛不能作为 posterior 多峰证据。没有可信证据时 Gate E=NOT_ESTABLISHED，diffusion=OFF。

## 8. NN pilot 的执行权限

只有 A/B/C 通过且存在充分已有 training cache 才运行 C-stage。first model 为 MLP；fair comparisons 见 PRIOR_ONLY_NEURAL_DECODER。使用至少两个 train sizes（如已有 32/64/128 中的两个），3 seeds 仅在 1.5h 上限内可完成时运行，时间不够报告未完成。

禁止因为训练不收敛而自动换 U-Net/Transformer、扩数据集或 diffusion。缓存不足也是可以接受的“下一轮需要数据”的结论。

## 9. 输出文件与表结构

`asset_inventory.json`：文件来源、版本/commit、可用场景和算子接口。

`scene_manifest.csv`：scene/family、split、频率/几何、anchor provenance、truth 是否仅用于 label。

`direction_metrics.csv`：scene_id、direction_id、amplitude、noise_seed、alpha/beta/gamma、attribution、profile_g、ROM/factor/curvature bounds、certificate_type、true coefficient error、nuisance setting。

`image_metrics.csv`：method、scene、r/k、projected/full/task errors、discrepancy、protected drift、success、first_hit_time、total_time。

`cost_ledger.csv`：每个方法的 forward/adjoint RHS、operator actions、Q builds、outer/line-search/reject counts、cold/warm time。

`GATE_REPORT.md`：每个 gate 的 PASS / PARTIAL / FAIL / NOT_RUN，缺失证据及 precise next action。不要用自然语言把 PARTIAL 包装成 PASS。

## 10. 停止条件

超过阶段时限、严重数值不一致、部署 anchor 没有 headroom、相同rank公平基线下无法分离误差、full-model 检查显示 prior directions 实际很强，都触发停止/修正报告。预算截止不是科学反证；结构性反例则应明确杀死对应 claim。
