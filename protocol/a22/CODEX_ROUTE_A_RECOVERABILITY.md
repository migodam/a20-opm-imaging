# Codex Stage A — Recoverability 与 material split，不训练 NN

## 可以直接交给 Codex 的任务

你负责落实本目录的第一阶段实验。先读 START_HERE.md、THREE_FOLD_RECOVERABILITY_THEORY.md、TWO_SIDED_RECOVERABILITY.md、MATERIAL_PHYSICS_PRIOR_SPLIT.md、LIGHTWEIGHT_EXPERIMENT_SPEC.md、GO_NO_GO_GATES.md、TIME_TO_IMAGE_ANALYSIS.md。

目标：检验可线上计算的 OPM 双向 signature 是否能预测实际材料恢复难度，并形成可信、非平凡的 V_phys/V_rem。不要研究 current selection/exchange、增加 degree、GN solver acceleration，也不要训练 NN/diffusion。

## 执行顺序

先盘点当前工作区内 A20/A21 及相关 full-wave solver、cached features、scene manifests 和日志。不要假设本研究包已经包含这些资产；找不到就列出缺项。不得用其他工程中的相似文件冒充本项目缓存。只读原资产，所有新输出放独立研究目录。

列出一份短实现计划：复用接口、四个 screening scenes、可部署 anchors、W、operator action 预算与断点。然后运行本包 verification/verify_theory.py。再接入实际 solver 做 finite-difference/adjoint/Schur consistency checks。

固定 k=32 起步，最多64；固定 shallow Q，不按 test error 搜索 rank/degree。先跑4-scene screening；有信号后按预算扩大。按 scene 分割数据，严格隔离 truth labels 和 online features。

实现 A0/A1/A2/A3 diagnostic baselines，比较 sensitivity、profiled attribution 和结构化 OPM 对有限幅度/物理失配的增量预测。不要用 full J/H 作 online features。truth/full derivative 可只在 evaluation 侧出现。

## 推荐接口（以现有仓库风格实现，不要求重构）

`build_anchor(y, geometry, frequencies) -> anchor, provenance, cost`

`build_opm(anchor, fixed_config) -> factors_or_actions, residual_actions, cost`

`material_features(opm, W) -> MW, PMW, AW, signatures`

`build_split(features, declared_uncertainty) -> Vp, Vrem, D, certificate, eligibility`

`evaluate_recovery(scene, split, perturbation, noise) -> metrics`

复物理算子与实材料矩阵的接口要明确 shape、stack ordering 和 noise convention。每个 certificate 存 type=`deterministic_bound` / `probabilistic_bound` / `empirical_indicator`，不可混用。

## Stage A 输出

生成 asset_inventory.json、scene_manifest.csv、direction_metrics.csv、split_metrics.csv、cost_ledger.csv、STAGE_A_REPORT.md、GATE_REPORT.md。报告必须解释失败属于 detection/attribution/ROM credibility/finite amplitude/material support 哪一种。

Gate A/B 没有通过就停止；预算导致证据不足标 PARTIAL/NOT_RUN，不编造 pass。即使失败也保留全部负结果与用于解释的最小反例。只有现成低成本的一次成像可作为 Gate B 验证，不启动完整 Stage B campaign。

本阶段不改 A17 主稿，不启动新论文性能 claim。最后给出继续 Stage B、修正假设或杀死 OPM-specific split 的明确裁决。
