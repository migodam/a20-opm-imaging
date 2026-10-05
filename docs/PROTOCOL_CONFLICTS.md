# 协议冲突与显式处理

1. **旧可行化并非受约束 GN。** A17 先求无约束步再做 Euclidean projection；该步一般不是 H 度量下受约束二次最优解。A20 在共同二次目标内施加线性/box 约束并核验 KKT。旧不可行步只标为无约束参考；生成新的可行参考单独计费。这是用户批准的纠正，适用于 full GN 和所有 ROM。
2. **物理系数不是裸 χ。** 复用非线性 CM/radiation-reaction 极化率及原导数。抽象 F=反馈在本后端是 diag(α(χ))Goff，B 含 b′−L′j。未将它替换成 diag(χ) 的简化模型。
3. **旧数据已暴露。** 六 parents 与 iteration 0/17 保留历史身份。离线 truth/旧 full steps 从运行 problem.npz 中删除，放在 data/offline；它们只用于付费参考审核及评估。这不是新的盲测划分。
4. **数据 norm normalization 不是噪声协方差白化。** 原 scale 继续复用。真实多频必须分别建立 Green/receiver adapter 后在同一实材料坐标堆叠；主 pilot 仍为原 k=2 的单频采集。
5. **旧 hash 字段是历史记录。** 遵循用户批准计划，不计算、核验或声称重新核验 SHA256。A20 记录实际 Git source commit；历史声明与本轮 numerical equivalence 分开。
6. **并行分工授权有更新。** 最初任务要求独自执行；用户随后明确允许必要的 multiagent workflow。Codex 子代理仅分担测试、已知协议 replay 实现和证据整理；主线程负责数学、真实物理调度、预算及科学裁决。不使用 DeepSeek，不创建或联系其他用户聊天。

实际发现的数值/运行冲突和修复随失败日志、软件 commit、G0 与各 job receipt 留存。缺失条件不会被默认当成通过。

7. **预算与执行顺序。** 在启动任何 A1 之前，执行顺序固定为 method-major：先完成六对象 full GN，再依预先规定 degree 顺序完成六对象配对，最后普通 ROM 对照。最多42个主矩阵重建及所有 gates 不变。预算停止保留部分矩阵；初始 cold 顺序不替代 A20 合同要求的完整 cold/warm 成本比较。见 results/STAGE_ORDER_DECLARATION.json。
8. **重试 cohort 不能自动混合。** 单个完整 replay cohort 从空结果开始；不同run产生重复(parent,state,method,degree)时，gate保持HOLD，直到显式声明合规cohort。不能删除失败来制造通过。首次replay没有重试选择。

9. **跨任务计时条款纠正。** 一次文档整理误把之前 A19 的五次计时要求移入 A20；对照本轮 root 执行合同、lightweight spec 及用户批准 A20 计划后已移除。A20 没有规定五次/两次重复。42 是六对象×七方法的初始主矩阵，不是已授权同条件 warm 计时重复的全局次数上限；warm及噪声的所有实际重建/失败仍全额进入12小时GPU、2小时CPU预算。纠正在任何A1或timing动作之前完成，没有调整已执行replay、数值门槛或结果。

10. **求解失败与缺参考可以同时存在。** 真实 voxel replay 暴露了这种情况：QP 返回 success，但 KKT 未达固定 `1e-8`，完整参考也被拒绝。原 gate classifier 将 FAILED 行全部归入实际失败，可能在仅余参考上计算 median，而没有单列缺参考。修正仅作用于离线 gate 汇总：保留 `observed_failures` 和 `method_validation_status=FAIL`，同时以 `missing_reference_states` 阻止完整12-state H-step gate，记 HOLD。五项无物理回归检查通过。正在运行的 replay 源码、QP、阈值、预算和失败行均不改动；原 job 内自动 gate 与修正后的最终 gate 分别留存，不使用已有不合格步生成参考。
