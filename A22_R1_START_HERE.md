# A22-R1 直接 physics/prior 分离实验

**裁决：CASE_C_A2_MATCHES_OR_BEATS_A3。** 在本筛查中，A2达到相对分离筛查阈值，而A3没有达到预注册15%的增量；不能把O/P/M标签宣称为构造该split所必需。停止NN，保留更简单的物理编码对照。

本实验只检验已知背景 `0.1+0.04i` 下、固定32维质量归一材料图中的分离。四个对象全部历史暴露；2001/2003是Gaussian，2014为非Gaussian/asymmetric分段材料，2009为多尺度shell。统计单位只有四个scene，不能把2112个noise/方向案例作为独立对象。没有NN、nonlinear GN/DBIM、新标签、rank/degree搜索或自动扩展。

主k=16的A3：S_sep场景中位数 **3.3994**，q_phys **0.354249**，q_prior **3.43921**，truth_phys **0.740968**。相对A2的等场景平均physics NRMSE改善 **0**；2000次四scene配对bootstrap区间 `[0.0, 2.220446049250313e-16]`。S1/S2/S3/S4：`{'S1': 'SUPPORT', 'S3': 'SUPPORT', 'S4': 'SUPPORT', 'S2': 'FAIL'}`。这些是screening SUPPORT/FAIL，没有formal PASS。

physics NRMSE中位数仍为 **0.535099**；相对分离不等于低绝对误差，不能据此宣称物理分支已经可靠成像。A2/A3在主k16是否选取相同候选集合：`True`，详见[projector audit](results/a22_r1/SPLIT_PROJECTOR_EQUALITY.csv)。若集合相同，零增量是同一投影的结果，不是四scene上的一般无效性证明。

| 方法 | physics NRMSE均值 | prior NRMSE均值 | S_sep中位数 | q_phys中位数 | q_prior中位数 | truth_phys中位数 |
|---|---:|---:|---:|---:|---:|---:|
| RANDOM | 0.995677 | 1.35788 | 2.14261 | 0.597327 | 2.41554 | 0.742074 |
| A1 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| A2 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| A3 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| FULL-J（仅离线） | 0.574034 | 1.66618 | 2.88516 | 0.425535 | 3.0886 | 0.741394 |

旧标量严格复现仍为FAILED：Mac104/2112、原Windows26/2112不匹配。Test A/B使用整组Windows共同向量，先重验同一个缓存quadratic、可行域、保存normal及原KKT；2112/2112有效。选择平台与这项处理在查看split结果前登记。参见[显式补充](REPRODUCTION_CONFLICT_ADDENDUM.md)和[source audit](research/delegated/a22-r1-cache-audit/PLATFORM_REPRODUCTION_AUDIT.md)。不能把本报告称为bitwise旧Stage A复现。

## 阅读顺序

1. [冻结协议](SUBSPACE_SEPARATION_PROTOCOL.md)及[split来源](SPLIT_DEFINITION_AUDIT.md)
2. [共同解误差定位](ONE_SHOT_ERROR_LOCALIZATION.md)
3. [真实受限分支](RESTRICTED_PHYSICS_BRANCH.md)
4. [图外能量](CHART_EXTERIOR_AUDIT.md)
5. [机器判决](results/a22_r1/GATE_DECISION.json)、[四scene指标](results/a22_r1/PER_SCENE_SPLIT_METRICS.csv)、[方法比较](results/a22_r1/SPLIT_COMPARISON.csv)
6. [费用](results/a22_r1/COST_SUMMARY.json)、[失败账本](results/a22_r1/FAILURE_LEDGER.jsonl)、[原始输出入口](results/a22_r1/REPLAY_SUMMARY.json)

## 证据边界

原理论包已经给出的是条件性的线性recoverability/attribution论证；本实验不重做理论。单元与identity tests验证实现，不能代替Maxwell实验。真实Maxwell证据来自既有32个clean有限幅度label与四个付费背景重建。full-J只在在线split全部冻结之后用于OFFLINE诊断。可部署证据仅限已知背景的缓存OPM及一次受约束材料解，未测未知背景或真正端到端time-to-image；rank32不构成部署加速。

保存2112个共同32D向量、21120个受限向量和42240条split指标。四个背景重建不可避免，因为旧缓存缺y0与完整descriptor映射；新full-wave label数为0，cache replay物理调用为0。费用以[COST_LEDGER](results/a22_r1/COST_LEDGER.jsonl)唯一inclusive receipts为准，失败/重跑没有删除，nested actions不重复加账。历史A22账本保持冻结。

## 图和复现

图A–F的PNG/SVG及原始数据在[figures](figures/A22_R1/PLOT_MANIFEST.json)。缓存入口、参数、seeds、source记录在[SOURCE_AND_COMMAND_MANIFEST](results/a22_r1/SOURCE_AND_COMMAND_MANIFEST.json)。运行 `PYTHONPATH=src python -B -m a22_r1.cli report --job a22-r1-report-NEW` 重新汇总现有缓存；不要重跑freeze或生成label。新的job名称必须唯一。

本地交付；未自动publish、扩展场景、启动NN或下一阶段。

计时细分见[CACHED_ONE_SHOT_RUNTIME](CACHED_ONE_SHOT_RUNTIME.md)；缓存kernel不能当完整部署加速。

## 本地代码与压缩证据

实现代码commit：`41194f4d5d0eb472f4785a81c4cd2467cc4581d7`。大型逐case原始记录保留在本地；Git保存其字节一致的gzip副本，完整向量另有NPZ。路径与实际字节数见[DELIVERY_MANIFEST](results/a22_r1/DELIVERY_MANIFEST.json)。report入口可以直接读gzip缓存。
