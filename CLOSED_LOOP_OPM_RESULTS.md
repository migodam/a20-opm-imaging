# Closed-loop OPM：NOT_RUN

Phase2 未启动。五对象 late WIDE-M median H-error=209.5953%，CHEAP-TASK=235.1696%；两者均未通过 Gate B 的 ≤50% 且降低≥70% 条件。Gate A/C 又因 early baseline 复现停止而 HOLD。没有合法 winner，不能执行规定的三对象九次成像矩阵。

|规定比较|状态|
|---|---|
|2001/2007/2013 FULL_GN，A1|NOT_RUN_GATE_CLOSED|
|三对象原 history-aware FIXED_OPM|NOT_RUN_GATE_CLOSED|
|三对象 best legal adaptive OPM|NOT_RUN_NO_LEGAL_WINNER|
|三对象 FIXED history OFF 控制|NOT_RUN_PARENT_GATE_CLOSED|
|reconstruction/objective curves|NOT_RUN_NO_TRAJECTORY|
|closed-loop 质量与部署 GO|NOT_RUN|
|NN / 更大 campaign|NOT_RUN_NOT_ELIGIBLE|

不得把 frozen one-step truth error、rank56、模拟循环测试或 late current capture 当成 nonlinear imaging 结果。也不存在 FULL_GN 候选之间的闭环成本比值、final KKT 比值或 wall-time improvement。

实现已保留：自然产生的自身 alpha×step history、owner/index 检查、每对象 cold 起点、三方法轮换、原 full-objective 接受与 full-KKT 审核、QP/core 失败停止、禁止 full-model salvage、offline 自身 state reference 分账。所有真实实验调用仍由 gates 与累计 budget 限制。本次 Phase2 CPU/GPU 费用均为 0。

正式机制结论 D—INCONCLUSIVE；合法候选扩展为 NO_GO_GATE_B。缺少 oracle PASS、合法 enrichment PASS 和真实闭环 headroom 三个前提，不能进入 NN material-enrichment 学习。
