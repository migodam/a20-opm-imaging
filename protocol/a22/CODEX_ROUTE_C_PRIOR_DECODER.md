# Codex Stage C — Small prior-only deterministic decoder

## 运行权限

必须先检查 Stage A/B 的 GATE_REPORT.md、原始误差分离和 one-shot headroom。前置 gates 未通过、training cache不足或9小时总预算已接近上限时，不训练，输出 BLOCKED 及原因。

先读 PRIOR_ONLY_NEURAL_DECODER.md、OPM_PHYSICS_ENCODER.md、PRIOR_SUBSPACE_DIFFUSION.md、EARLY_EXIT_CLASSIFIER.md、GO_NO_GO_GATES.md。这里的 diffusion 文件只用于理解禁用条件，不是执行训练任务。

## 任务

固定 physics encoder 与样本 split，训练小 MLP 只预测 eligible prior coefficients。采用 train-only standardization/basis fitting；按 scene划分，不能把同对象noise realizations放到test中。

实现 VpᵀVn 数值检查、严格physics projection preservation、coefficient amplitude limiter，以及可行域内的小投影。不要用逐voxelclipping破坏物理保护。没有可靠full-model/curvature界时，data safety输出 empirical，不冒充certified。

公平对比：physics-only、same-encoder whole-image MLP、prior-only MLP、unrestricted residual decoder、小A-SVD split的prior-only MLP。有限预算下先取最简单的匹配容量版本；不得自动引入大U-Net/transformer。

用已有cache的至少两个训练规模观察sample-efficiency；报告独立scene数。训练上限1.5GPU-associated wall hours，且计入全阶段9小时上限。所有新dataset生成需要单独许可，不因模型效果不好自动扩展。

## Gate D 指标

完整图像误差、Vphys/Vprior误差、真实数据一致性、protected-coordinate drift、明确的artifact/hallucination指标、OOD、总inference成本。采用预先冻结的primary advantage，不在许多指标里事后挑赢的。

如果 prior-only 仅保持投影但错误锁得更牢，判定失败；如果训练误差下降但test差，不能解释为“需要diffusion”。模型失效、物理不确定性与posterior multimodality分开。

## 输出与结束条件

生成 STAGE_C_REPORT.md、training_manifest.json、learning_curves.csv、image_metrics.csv、checkpoint metadata、最终GATE_REPORT.md。给出保留MLP、仅保留physics-only、后续需要更多数据或kill prior-only architecture的明确裁决。

本阶段禁止训练DDPM、score、rectified flow、conditional flow matching和full-image diffusion。允许在报告里说明未来posterior gate还缺什么证据，但不生成或启动新的训练campaign。
