# Novelty audit：Three-Fold OPM material recoverability

检索日期：2026-10-07。这是有明确最近邻的研究审计，不是穷尽检索或“首次”证明。来源与阅读深度统一列在 REFERENCES.md。以下严格区分已经存在的思想、本文新推导的组合条件、尚待实验的假说。

## 1. 核心裁决

**不能以「physics reconstructs measured components, NN completes unmeasured components」作为主 novelty。** Null-space networks、DDN、NPN 已直接覆盖这一基本架构；电磁领域的 SOM/TSOM、ICLM 和 SOM-Net 也已把解析物理部分与待优化/待学习部分联系起来。

**不能以「ROM 不再服务每一步 GN，而直接用于 inverse imaging」作为主 novelty。** Borcea 等 data-driven ROM 及 regularized Lippmann–Schwinger–Lanczos 已有直接/非迭代成像路线。

值得继续的是：把三维 Maxwell 的 material excitation、feedback propagation、receiver observation 明确纳入 nuisance-aware、factor-uncertainty-aware 和 finite-amplitude material-coordinate recoverability，并检验它能否决定可信的 one-shot / prior-only 分工。

## 2. 最强重合组

| 最近邻 | 已有的内容 | 本项目还必须证明的差异 |
|---|---|---|
| SOM/TSOM [R00] | 由 data/state operators 分解 induced current 的可直接恢复、待优化与可忽略部分 | 从 current visibility 转到实际 material coordinates；处理 attribution、背景和有限幅度 |
| ICLM [R31] | contrast-source-domain learning；与当前想法相邻 | 本轮未获得该文原始全文，不能宣称所有细节已比对；需在投稿前补原文审计 |
| SOM-Net [R05] | deterministic current + BP 输入，交替 current/material unrolling，材料解析更新 | 不是复现 unrolling；要证明固定 material split 和 near-one-shot 的独特收益 |
| Null-space networks [R01] | 用 projected learned correction 保持线性 data consistency，具有正则化分析 | 近似/非线性 Maxwell 的 safe radius 和可信材料子空间，而不是同一网络公式 |
| Nonlinear data-consistent networks [R02] | 将 data-consistency 思想扩展到非线性逆问题 | 不能声称首个 nonlinear safe learned correction；具体比较 OPM 可计算条件 |
| DDN [R03] | 分解 range/null 两类分量进行学习 | “两分支”本身没有 novelty |
| NPN [R04] | 学习 sensing null-space 的低维投影，作为先验接入多种成像框架 | “只学 low-dimensional missing information”已不是空白；本项目重点应是因子化材料 recoverability |

NPN 的方法段以线性 y=Hx+n 为起点，其 prior 形式可进入 PnP、unrolling、DIP 和 diffusion。不能把它误述为已经完成任意三维 nonlinear Maxwell 的本任务，但也不能因应用领域不同而忽略它。

陈旭东书中 printed p.162 的 Fig.6.13 表示 current subspace 的几何关系；printed p.133 已有 current→total field→analytic contrast 的 BP 公式。这两处特别说明：不是加第三个字母或再做一个解析层就形成新论文。

## 3. Bayesian / information / balancing 组

LIS [R06,R07] 已按 likelihood 相对 prior 的影响建立低维分解；active subspaces [R08] 分析对数据失配敏感的方向；goal-oriented Bayesian approximation [R09] 关心任务 posterior 而非全参数。Balanced reduction for Bayesian inference [R10,R11] 已连接 reachability、observability 与推断。

因此 OPM 不能把注入/传播/观测的串联本身称作从未有过的信息理论。可测试的差异是：固定 J 的 nominal information 相同，但物理关联 perturbations 作用在不同 factors，导致不同的 recoverability margins 和干预结果。T0 明确限制了“比完整 Fisher 信息更多”的说法。

这里的 nuisance-profiled g 与 1/g² 是已有识别/partial regression 几何的 OPM 表达，不冒充原创 Fisher 定律。材料基变换、单位与 prior whitening 必须在比较中一致。

## 4. 直接成像 / data-driven ROM 组

Born、Rytov、EBA、BP、DBIM、CSI 的定位见 [R00]。Borcea 等 [R12] 用数据驱动 ROM 提取与 unknown propagator 相关的信息，并提供 data-to-Born 型处理。频域 ROM inverse scattering [R13] 继续研究相关模型。Baker 等 regularized LSL [R32] 明确提出 direct non-iterative ROM inversion，并讨论正交化内部基对未知势的弱依赖。

不能因为它们使用 Lanczos/Krylov 字样就忽略：它们不是单纯“更快求解同一个 GN”。本任务禁止 solver acceleration，但 direct inverse ROM 是必须审计的不同竞争路线。

本文 common-dual theorem 与这类 weak-state-dependence 思想概念相近，但目标不同：直接约束用于某组 material coordinates 的 measurement witnesses。是否形成比现有 ROM 理论更有辨识力的 Maxwell 结果，需要后续文献全文与实例共同确认。

## 5. Learned regularization / generative 组

PnP [R14]、RED 及其解释 [R18,R15]、DIP [R16] 已将网络作为不同形式的先验。DPS [R17] 与 score/SDE [R28] 在 likelihood 条件下做生成推断。SDPS [R19] 已用多分辨率 subspaces；diffusion-state projection [R20] 与本任务的 material-null projection 不是同一对象，但“projection + diffusion”不能当新颖口号。

Inverse CFM [R21,R22] 已研究条件 posterior 的摊销学习。2026 年的 SONAR [R23] 与 Fast and Faithful CFM [R24] 通过原始 arXiv 摘要检索进入候选审计；本轮未成功获取这两篇全文，所以只作 overlap warning，不据此给 theorem-level 重合判决。

Neumann-series neural operator [R26] 属于 forward/operator learning 近邻，不等于本任务的 prior-only decoder。把 OPM tensor 换成 transformer tokens 也不是机制贡献；要用 sample efficiency、OOD 与正确物理预算来证明收益。

## 6. 可以争取的三项贡献

**C1：factor-resolved material recoverability certificate。** 同时控制 noise amplification、nuisance attribution、结构化 factor perturbation、full-vs-ROM defect，解释“为什么弱”和“这种弱是否可信”。

**C2：finite-region two-sided one-shot condition。** 固定 D 满足 DJ(x)≈C 的条件与其 OPM residual 实现，直接给 material-coordinate one-shot error，而非 full GN step fidelity。该定理的证明本身是微积分/算子误差分析；论文价值取决于条件是否非空、可计算、比 generic bound 更有物理解释。

**C3：条件化 prior-safe decoder 与成本选择。** 在可认证 physics coordinates 上硬保护，在其余 eligible coordinates 上做低成本先验补全，给 finite-amplitude data budget 和端到端证据。结构形式借鉴已有 null-space learning，不能独立 claim first。

拟议论文主句可为：

> We study when three-dimensional Maxwell feedback admits stable, attributable material coordinates that can be decoded in one shot, and use factor-resolved uncertainty bounds to constrain learned completion to the remaining eligible directions.

这里的“study/propose”是当前适当表达；“demonstrate faster imaging”要等待项目实测。

## 7. 针对“是否有人已经完整做过”的回答

在本轮检索和读取的材料中，没有确认一篇同时具备以下全部环节的 exact match：Maxwell material injection/feedback/observation 分离；nuisance-aware material recoverability；full-vs-ROM credibility；finite-region common-dual one-shot；受保护的 prior-only completion；完整 time-to-image 判据。

这不构成未发表/未索引工作不存在的证明。尤其 nonlinear data-consistent learning、NPN、data-driven direct inverse ROM 和 2026 年的 null-space-aware papers，投稿前必须补全文对照表。当前应表述为 **a specifically formulated research opportunity with strong neighboring literature**，而不是首次发现 physics/prior split。

## 8. 检索范围与限制

查询组合覆盖：SOM/TSOM/SOM-Net/ICLM；material injection/propagation/observation；threefold inverse scattering；null-space/data-consistent/decomposition networks；LIS/active/goal-oriented/balanced inference；Born/DBIM/CSI；direct inverse ROM/LSL；PnP/RED/DIP；subspace diffusion/CFM/neural operators。

使用论文原文、arXiv 作者摘要、出版社和作者机构页面。第三方索引只帮助发现，不用其 AI 摘要替代方法内容。全文不可得的条目在 REFERENCES 中标明，不把筛查层级包装成全文审阅。
