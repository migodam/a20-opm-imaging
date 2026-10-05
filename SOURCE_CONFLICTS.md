# 来源与协议接线记录

原 A20 source freeze：`e29f345ae5aea170a18cca1b79defe57e878ab29`。R1 运行源码：`5231aea98f6945a77c4f83f030a57248065695ef`。原 release、`results/GATE_DECISION.json`、结果、账本、runtime 与 offline 文件保持历史身份；R1 决策和费用另存。

1. **RNG 配对。** 原实现先抽 M 再抽 O。直接扩大 M 会改变 O，且按行抽 M16 不能保留原 M4 前缀。R1 显式保留原四列 M 和 O，再以独立 RNG 补十二个 M probes。合成回归中的原 probes、Z 与 Jacobian 逐元素一致；精确回归采用空 retained basis，未覆盖真实 replay 的额外 retained 正交化。
2. **六源压缩。** 一个材料方向产生六列 KB excitation，原 M4 压缩可能丢掉目标。新增 O3/P3/M6 degree3 的完整 block 保护和同配置随机控制；是否采用保护 oracle 由压缩阈值决定，不能挑 H-error 更好的结果。
3. **历史信息。** 冻结 replay 的 previous=None 与原真实成像接受后的 previous=alpha×step 是不同信息条件。R1 不借历史 full-GN step 冒充自身 history。兼容 hook 使用有 owner/index 的 accepted-history token；默认旧入口保留原行为。
4. **Oracle 标签。** 原通用 seed metadata 的无-reference 字段不能用于显式 oracle。R1 每方法/通道记录真实 provenance，oracle 大写标识 OFFLINE / DIAGNOSTIC ONLY。
5. **失败救场。** 原通用入口存在 full-model fallback。R1 的显式 `no_full_fallback` hook 禁止用 full 模型拯救候选；QP/core 失败终止并保留。原物理/求解器/材料优化器没有修改，原 Petrov 诊断及费用仍明确记录。
6. **独立费用。** 共享 Schur、probe bank、full state 与 scaffold 分开记录实际账单和冷部署归因；CHEAP 使用独立 ReducedJacobian 实例保证路径隔离。原 ReducedJacobian 的 pullback 本来不走 `_matrix` 快捷分支，这项隔离措施不构成旧版免费梯度缺陷的发现。
7. **绘图工具失败。** gate/report worker 的首次冷字体缓存 fixture 遇到 macOS Matplotlib 字体枚举错误；失败与 CPU 留在 worker receipt。最终真实图使用现有字体缓存，并单独计费。工具失败不计作物理方法失败。
8. **真实 baseline 复现冲突。** 五个 late FIXED-DEEP 均通过 1e-9 门槛，最大 step 相对误差 8.59418e-11；第一 early state 2001 的 step 相对误差为 1.670492e-6，超过门槛。旧/新 QP 都通过原 1e-8 KKT（8.41365e-9 / 6.12898e-9），SLSQP 迭代数 94 / 99。原 replay `_retained` 比原 imaging/R1 路径多一次对 retained receiver basis 的 SVD 正交化；其子空间在数学上相同，但数值 gauge/求解器敏感性可能影响严格复现。**此差异已确认，失配因果尚未证明。** 按冻结协议停止，未改 gauge、QP 容差或用缓存旧 step 替换新 proposal，29 个其余实际候选未运行。详情见 `results/a20_r1/BASELINE_CONFLICT_CODE_AUDIT.md`。

第 1–6 项接线在 R1 物理启动前冻结，第 7–8 项是保存失败后的审计记录。没有更改 KKT 容差、材料约束、reference、lambda/ell、Maxwell solver，或添加 jitter/pseudoinverse。后续只调整报告图的布局和公开元数据，不重新启动物理，不放宽门槛。
