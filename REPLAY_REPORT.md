# Frozen replay证据索引

固定parents 2001/2005/2003/2007/2010/2013，各iteration 0/17；全部尝试完成，`COMPLETE_WITH_FAILURES`。完整12-state参考筛选HOLD，当前实现进阶NO_GO；没有eligible degree。科学解释与数值表见[中文报告](RESEARCH_REPORT_ZH.md)，机器判断见[最终gate](results/GATE_DECISION.json)。

- [原始930行：shared、method和NOT_RUN](results/replay/replay.jsonl)
- [完整replay表](results/replay/REPLAY_RESULTS.csv)、[动作计数表](results/replay/ACTION_COUNTS.csv)
- [130条QPFailure，含2个full参考失败](results/replay/failures.jsonl)
- [shared geometry/state/reference/U费用](results/summary/NON_METHOD_RECORDS.csv)、[独占跨度与动作账本](results/jobs/replay-01/cost.jsonl)
- [逐state/parent、失败/缺失标志](results/summary/REPLAY_ROWS.csv)、[degree汇总](results/summary/DEGREE_MAIN.csv)
- [精确配对state](results/summary/PAIRED_STATE_DETAILS.csv)、[2000次parent bootstrap](results/summary/PAIRED_PARENT_BOOTSTRAP.csv)
- [实际rank/在线动作前沿](results/summary/FRONTIER_RAW.csv)、[确实匹配的点](results/summary/FRONTIER_MATCHED_PAIRS.csv)
- [早晚状态分图和完整raw CSV](results/replay/phase_plots/mixed_H_step_selection.json)
- [实际运行manifest](results/jobs/replay-01/manifest.json)、[job receipt](results/jobs/replay-01/job_receipt.json)、[最终预算](results/BUDGET_FINAL.json)

raw中的step_path保留原运行主机路径以记录来源；对应公开文件均在本仓库`results/replay/steps`或`failed_steps`，可按basename查找。它们是离线结果，不能进入online seeds。没有保存full J/H或完整Green/LU工作矩阵。

物理replay源码身份为`68ab91576c2f457e8afec0a2a9537ca5134018ea`。原自动gate[原样留存](results/REPRESENTATION_GATE_AUTOMATIC_ORIGINAL.json)；缺参考与QP失败共存的汇总修复见[协议冲突](docs/PROTOCOL_CONFLICTS.md)。新离线gate[HOLD](results/REPRESENTATION_GATE.json)保留实际`method_validation_status=FAIL`，未在十个有效参考上伪造完整12-state median。
