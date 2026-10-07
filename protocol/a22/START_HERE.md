# Three-Fold OPM Physics–Prior Imaging：研究结论与执行入口

研究日期：2026-10-07。任务依据：本轮上传的 `粘贴的文本 (1).txt`。本包不是 A17 主稿修订，也不是 A21 online GN 方案。

## 1. 本轮裁决

**PRIMARY：继续 one-shot OPM + material recoverability split 的轻量验证，但将核心判据升级为「可归因、对模型误差稳健、在有限幅度上有效」的双向物理见证。**

**SECONDARY：前述判据与 one-shot headroom 都通过后，训练 prior-only deterministic MLP。**

**HIGH-RISK：prior-subspace posterior modeling 只保留理论接口。本轮不训练 diffusion / flow，不生成训练 campaign。**

**OPTIONAL：先用解析阈值做 early exit，再考虑小 classifier。模型失效必须有 abstain / physics-correction 出口，不能统一转交生成模型。**

这不是重新命名小奇异值，也不声称「三个 gain 比完整 Fisher 拥有更多静态统计信息」。新研究对象是：在已声明材料类、噪声与模型误差范围内，哪些材料坐标存在低噪声放大的、跨状态仍可靠的 measurement-to-material 线性见证？OPM 用来解释并约束该见证的失效来源。

## 2. 最重要的研究结果

1. **可检测 ≠ 可归因。** 单方向的总响应强度 `||Jv||` 没有排除其他材料方向的混淆。可恢复性必须相对于 nuisance space 定义。
2. **一个可证明的正面结果。** 若同一组 measurement witnesses 在一段非线性材料区域内，经 `O* -> P* -> M*` 返回近似相同的材料坐标，则一个固定、小规模线性解码器可以 one-shot 恢复这些坐标；不要求整个 forward map 近似线性。
3. **OPM 的增量价值在结构化稳定性。** 同一个 J 可以对应完全不同的 M/P/O 机制；它们在精确线性、同噪声条件下有相同统计难度，但对 illumination、feedback、receiver 等不同扰动的脆弱性可以相差很大。
4. **保护材料分量不等于保护数据。** `V_phys^T V_prior=0` 只保证材料投影不变。数据一致性还需要 full-physics 弱响应、ROM 缺陷界和非线性曲率预算。
5. **低维 OPM 不自动产生低维 prior。** 若材料维数 p、可恢复维数 r，则线性补空间维数为 p-r。低维 posterior latent 还需要额外的材料分布结构与残差谱证据。

## 3. 实际完成了什么

- 给出了定理、证明、反例、算法接口、文献审计与轻量实验规格。
- 运行了固定随机种子的小矩阵测试。
- 运行了 8 个极化粒子、24 个复电流分量的三维矢量 coupled-dipole 检查，验证材料导数与 two-sided defect identity。
- 没有运行用户 A20/A21 仓库实验，没有训练 NN，也没有实测 RTX 4060 的 time-to-image。
- 上传任务中的 A17–A21 结果作为给定研究背景接受；本轮不将这些背景数字冒充独立复核结果。

完整数值见 `verification/results.json`；复现代码见 `verification/verify_theory.py`。它们验证代数及实现，不等于 imaging Gate A/B/C 已通过。

## 4. 阅读顺序

先读 `THREE_FOLD_RECOVERABILITY_THEORY.md` 和 `TWO_SIDED_RECOVERABILITY.md`，再读 `MATERIAL_PHYSICS_PRIOR_SPLIT.md`、`ONE_SHOT_OPM_IMAGING.md`。做算法决策时看 `NOVELTY_AUDIT.md` 与 `GO_NO_GO_GATES.md`。其余文件是 encoder、decoder、posterior、classifier 和成本的分项 specification。

工程执行顺序：

`CODEX_ROUTE_A_RECOVERABILITY.md` → `CODEX_ROUTE_B_ONE_SHOT.md` → 仅在前置 gates 通过后运行 `CODEX_ROUTE_C_PRIOR_DECODER.md`。

注意：这三个文件名是工程阶段编号；上传任务的科学 Route B（physics/prior split）在工程阶段 A 就要检验，不能等 NN 训练后再定义 split。

## 5. 十二个问题的答案

| 问题 | 本轮答案 |
|---|---|
| OPM 能否定义 recoverability？ | 能给机制化、条件化判据；三个 norm 单独不够。 |
| 比 JᵀJ/Fisher 多什么？ | 结构化扰动来源、跨状态一致性、ROM 漏失与归因路径；不增加同一精确 likelihood 的信息。 |
| 稳定 V_phys ⊕ V_prior？ | 可以条件性构造；必须有 block certificate、nuisance 和模型余项预算。 |
| V_phys 能 one-shot？ | common-dual / finite-region 条件成立时可以。真实场景 headroom 未验证。 |
| 剩余误差集中在 V_prior？ | 是必须测试的假设，不是线性代数恒等式。 |
| OPM 能作为 physics encoder？ | 固定线性 Gaussian 模型下可构造充分统计量；非线性情况下是有误差预算的 encoder。 |
| NN 优先预测什么？ | 通过 gates 后的 prior coefficients；分类器次之，不优先预测全图/regularizer。 |
| diffusion 必要吗？ | 目前没有证据；本轮 NO-GO。 |
| 总 time-to-image 会下降吗？ | 尚无实测；必须计入背景场、Q 构造、诊断、检查和失败回退。 |
| 比 iterative OPM-GN 合理吗？ | 值得作为新的首选 pilot；不能把理论机制当作已实现速度优势。 |
| 最小实验？ | 缓存/小模型、32–64 材料坐标、4 个 screening scenes 起步、固定上限逐级扩展。 |
| 哪些结果杀死方向？ | 在线可用状态下无 headroom、错误不分离、OPM 无增量预测价值或成本不占优。 |

## 6. 本包的使用边界

文献条目采用 [Rxx]，统一见 `REFERENCES.md`。定理分为本轮推导与已有标准结论的 OPM 具体化；不把它们自动称为首次发现。最近邻中的 NSN、NPN、SOM-Net、data-driven inverse ROM 必须进入未来论文的定位。

## 7. 补充材料

ONE_SHOT_OPM_IMAGING.md 中的 T10 给出了 Maxwell task-curvature 的伴随配对 identity 和 residual-certified bound，直接解释目标坐标为何可能比整个 data map 更线性。REFERENCES.md 保留33个编号与逐条阅读层级，不表示精读33篇。VERIFICATION_REPORT.md 汇总两份已执行验证脚本。SOURCE_TASK.txt 原样保留用户本轮任务，便于工程 agent 核对要求。
