# Codex Stage B — One-shot headroom 与总 time-to-image

## 前置条件

读取 Stage A 的 GATE_REPORT.md 和原始表格，不只读结论。Gate A/B 通过或有清晰、限定范围的正面证据才继续相应场景；未通过时不要自动执行全队列。

阅读 ONE_SHOT_OPM_IMAGING.md、MATERIAL_PHYSICS_PRIOR_SPLIT.md、TIME_TO_IMAGE_ANALYSIS.md、LIGHTWEIGHT_EXPERIMENT_SPEC.md、GO_NO_GO_GATES.md。

## 任务

实现一次 OPM construction、一次 small material solve 的 imaging pipeline；可选最多一次 full-wave correction event。使用真实可部署 anchor，禁止把 late-state truth-near oracle 当初始化。所有 BP/EBA pilot、background field、basis construction、diagnostics 与 consistency checking 均计时。

比较可用的 Born/BP/EBA、one-shot A-SVD、one-shot OPM-witness、Full GN/DBIM 与 OPM-GN。只复用已有可靠实现，不为了扩baseline耗尽预算。GN/DBIM 若是同一个算法实现就不要重复命名增加 baseline 数量。

按相同 task quality 和 discrepancy 标准计 first time-to-acceptable-image；失败样本单列并计超时，不只比较成功样本毫秒数。打印 cold/warm 与 amortization 条件。

在最多6个分层场景里检查 iterative ROM 的 N_outer、line-search trials、rejected directions、final error、total runtime。没有完整可比日志时允许 NOT_ESTABLISHED，不写成已经证实加速/减速。

## 不允许事项

不得自动增加 nonlinear iterations 并继续把方法叫 one-shot；不得更换更宽 Q、增加 polynomial degree、接 unrestricted NN 修补 physics error；不得用同一 reduced residual 自证 true data consistency。

## 输出

生成 image_metrics.csv、cost_ledger.csv、STAGE_B_REPORT.md、GATE_REPORT.md 的更新。保留 reconstruction arrays 与可视化；每张图标方法、anchor来源、r/k、是否correction、真实full-wave residual和elapsed time。不要只保存漂亮案例。

报告回答：V_phys 是否真已恢复？剩余误差是否在 eligible complement？总结构是否实用？实际时间是否低于达到同精度的 iterative baseline？诊断成本占多少？

只有 Gate A/B/C 的非平凡子集通过，且有合法 training cache，才授权 Stage C。不能因为“用户最终想用 NN”而跳过这一步。
