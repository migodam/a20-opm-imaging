# A20 机械证据汇总

数据范围：historically_exposed_feasibility。读取 888 条 replay 记录；预定格缺失 144。

shared geometry/state/reference/U 与其他非 method 记录共 42 条，另留 NON_METHOD_RECORDS.csv；它们不充作失败或缺失实验行。无 record_kind 的 legacy method 记录仍可读取。

失败、invalid、零参考、缺失、重复、oracle 单独计数；标志可重叠，不能相加当样本数。

- metric_valid：720
- failed：128
- invalid：0
- zero_reference：0
- missing：168
- duplicate：0
- oracle：0

配对只采用相同 total seed rank 和 actual rank 的状态；actual_seed_ranks 各压缩流 rank 的和是 total_seed_rank，不以 requested budget 或 joint/basis rank 替代。先平均同父对象所有预定状态差值，完整父对象再做登记的 2000 次 parent bootstrap；控制重复先在状态内汇总。缺一状态的父对象不进入区间，缺失原因保留在 PAIRED_STATE_DETAILS.csv。单 parent（包括 voxel）标 degenerate/descriptive，不给区间或总体显著性；区间仅描述历史可行性，未构成盲测或泛化证据。SOM/random 的 rank-only 匹配可存在，但可能没有严格 seed-plus-rank bootstrap pair，不能补造区间。

DEGREE_MAIN.csv 的有限子集统计不是 gate；缺失或失败不被成功样本平均掩盖，FAILED 即便记录了 fullfallback_used 也不成为有效 reduced-method 指标。FRONTIER_RAW.csv 和 FRONTIER_MATCHED_PAIRS.csv 保留逐父对象/状态的 rank/action 观测前沿及确实匹配点；未插值、未 padding，也未汇集不同场景。优先使用已记录的 online_Maxwell_vector_actions（F/F*/L/L* 真实 RHS）；非 audit F/F* 单列。无法分离 audit 的 legacy action totals 仍在原 counter 列，不伪充在线 action 前沿。

wall_total_attributed（保存在 wall_seconds 与同名原列）包含 offline audit，仅是 replay attribution；wall_basis/projection/QP/fallback/audit 各自保留，不等于在线完整部署。共享 geometry/state/reference/U 成本另表保留并由完整 job receipt 计账；逐 degree 的 basis attribution 是累计轨迹，不能再跨 degrees 求和。

GATE_SNAPSHOT.csv 只复制已有 gate；没有重算 PASS/FAIL。失败 jobs 的资源照样计入 JOB_RECEIPTS.csv；相互嵌套的墙钟与 CPU span 不被重复累加。

绘图状态：GENERATED。科学解释与最终判断由父线程另写。所有来源错误见 INPUT_ISSUES.csv。
