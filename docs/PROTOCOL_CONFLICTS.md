# 协议冲突与显式处理

1. **旧可行化并非受约束 GN。** A17 先求无约束步再做 Euclidean projection；该步一般不是 H 度量下受约束二次最优解。A20 在共同二次目标内施加线性/box 约束并核验 KKT。旧不可行步只标为无约束参考；生成新的可行参考单独计费。这是用户批准的纠正，适用于 full GN 和所有 ROM。
2. **物理系数不是裸 χ。** 复用非线性 CM/radiation-reaction 极化率及原导数。抽象 F=反馈在本后端是 diag(α(χ))Goff，B 含 b′−L′j。未将它替换成 diag(χ) 的简化模型。
3. **旧数据已暴露。** 六 parents 与 iteration 0/17 保留历史身份。离线 truth/旧 full steps 从运行 problem.npz 中删除，放在 data/offline；它们只用于付费参考审核及评估。这不是新的盲测划分。
4. **数据 norm normalization 不是噪声协方差白化。** 原 scale 继续复用。真实多频必须分别建立 Green/receiver adapter 后在同一实材料坐标堆叠；主 pilot 仍为原 k=2 的单频采集。
5. **旧 hash 字段是历史记录。** 遵循用户批准计划，不计算、核验或声称重新核验 SHA256。A20 记录实际 Git source commit；历史声明与本轮 numerical equivalence 分开。
6. **并行分工授权有更新。** 最初任务要求独自执行；用户随后明确允许必要的 multiagent workflow。Codex 子代理仅分担测试、已知协议 replay 实现和证据整理；主线程负责数学、真实物理调度、预算及科学裁决。不使用 DeepSeek，不创建或联系其他用户聊天。

实际发现的数值/运行冲突和修复随失败日志、软件 commit、G0 与各 job receipt 留存。缺失条件不会被默认当成通过。
