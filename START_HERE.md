# A22 Three-Fold OPM：本地实验交付

**Gate A：PARTIAL，按冻结规则停止。** 四个历史暴露场景的 Maxwell screening 已完成：32个clean标签、2112个有效恢复案例、actual current rank32。130项本地测试及随包/真实tiny验证通过。A3中位相关性0.5069，但相对较强A2的MAE改善为−0.1263%，2000次scene-cluster区间跨零。

完整24场景、one-shot physics image、prior-only NN 均 **NOT_RUN**。Gate T **NOT_ESTABLISHED**。本交付不发布，不自动开展下一阶段。

建议按顺序阅读：

1. [科学判定与证据边界](A22_GATE_DECISION.md)
2. [定量结果、噪声、材料覆盖与缺口](A22_RESULTS_LEDGER.md)
3. [实现、接口、验证及信息隔离](A22_IMPLEMENTATION_REPORT.md)
4. [命令与seed](A22_COMMANDS_AND_SEEDS.md)
5. [最终资源与动作账本](results/a22/ACTION_ACCOUNTING.json)、[交付manifest](results/a22/FINAL_DELIVERY_MANIFEST.json)

主要证据：

- [paired scene MAE与95%区间图](figures/a22/statistical/held_scene_deployable_all_paired_scene_incrementality.png)
- [逐场景相关性图](figures/a22/statistical/held_scene_deployable_all_per_scene_spearman.png)
- [完整案例CSV](results/a22/stage_a/direction_metrics.csv)
- [统计表](results/a22/statistics/statistics_summary.csv)、[逐场景表](results/a22/statistics/per_scene_statistics.csv)
- [权威Gate JSON](results/a22/GATE_DECISION.json)、[完整性与配对审计](results/a22/stage_a/EVIDENCE_COMPLETENESS_AUDIT.json)
- [失败账本](results/a22/FAILURE_LEDGER.jsonl)、[动作与费用CSV](results/a22/cost_ledger.csv)

模型固定为 known background `0.1+0.04i`、32实材料图、U8/O4/P4/M4 degree1。四对象都超出声明逐点先验；分段材料/shell 的 W 能量覆盖较低。预算是经验指标，图内恢复结果不等于完整对象成像。

理论原文在母目录及 `protocol/a22/` 保留。工作树继承 A21 的旧文件作为来源；根层旧 `GATE_DECISION.json`、旧报告和旧结果不属于 A22 判决。A22 唯一权威 gate 是 `results/a22/GATE_DECISION.json`。
