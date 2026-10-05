# 维度、物理动作与费用匹配

五个 late states 的六种方法 **actual rank 均为 56**，不是仅 requested rank 一样。未补随机列凑维度。rank 匹配和 action 匹配分别裁决；rank 很低本身不是部署收益。

|方法|O/P/M；degree|actual rank|冷 proposal F/F*/L/L* 向量四元组|四元组总数|basis median s|
|---|---|---:|---|---:|---:|
|FIXED-DEEP|4/4/4；3|56|32 / 20 / 86 / 24|162|3.673195|
|WIDE-M|4/4/16；1|56|28 / 12 / 158 / 24|222|3.879141|
|CHEAP-TASK|4/4/4；3|56|56 / 32 / 172 / 48|308|5.791031|
|ORACLE-M，OFFLINE ONLY|4/4/4；3|56|32 / 20 / 86 / 24|162|3.842905|
|PROTECTED-ORACLE，OFFLINE ONLY|3/3/6；3|56|35 / 17 / 98 / 18|168|3.954650|
|PROTECTED-RANDOM，离线控制|3/3/6；3|56|35 / 17 / 98 / 18|168|3.955995|

每种方法的五个 late states 都有上述相同四元组。时间为实测付费构基加公共依赖/必要 scaffold 的独立归因，不是原状态被免费缓存后的增量。不把这些单次 frozen-state 构基计时当作真实部署或闭环总耗时。

按每分量 `abs(a−b)/max(a,b)` ≤10% 判断 action matched，双零为 0。WIDE-M 和 CHEAP-TASK 均不与 FIXED-DEEP action matched；最近的合法对照是 WIDE-M，但其最大分量差仍约 45.57%。ORACLE-M 与 FIXED-DEEP 完全匹配。保护 oracle 与保护 random 完全匹配；保护配置与 FIXED 的最大分量差 25%，因此两者只有 rank 匹配，不能宣称物理动作匹配。negative KILL 的 rank 条件与此动作匹配条件是不同检查，不互相替代。

WIDE-M 减少反馈 depth 的部分 F/F* 工作，但更宽材料注入使 L 向量工作增多；其四元组总数比 baseline 高 37.04%。CHEAP 的 scaffold、梯度与第二次构基均收费，四元组总数高 90.12%。共享实际执行避免重复公共构建，但独立部署归因会补回必要公共工作；此归因不再次加入累计账本。

`results/a20_r1/report/RANK_ACTION_MATCHING.csv` 给出合法比较的逐 parent 分量差；所有方法的原始 standalone/actual/shared/offline 分解保存在 action JSONL。

四元组不是全部工作。ledger 另外保留 full solve RHS、full-state L/Goff RHS、receiver、LU、compressed B、数据传输、QP 和审核。若闭环启动，总物理向量工作采用互斥 F/F*/L/L* + full solve RHS + full-state L/Goff RHS；不再加入聚合 `Maxwell_matvec_rhs`，receiver/LU/offline 单列。本次未启动闭环，因此该部署 gate 是 NOT_RUN。
