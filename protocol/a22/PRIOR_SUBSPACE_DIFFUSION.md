# Prior-subspace posterior：理论规格，不启动训练

本轮状态：**NO-GO for diffusion/flow training**。没有生成训练 campaign；不新增 full-resolution U-Net 或大数据集。

## 1. 什么时候 probabilistic completion 才有价值

首先必须证明 one-shot physics 有实用 headroom，且 remaining ambiguity 确实存在于合法材料支持内。局部 small singular values、一次 optimizer 失败或 deterministic MLP 达到误差平台，都不能单独证明 multimodality。

合法 ambiguity witness 应包含：两种或多种实际不同的可行材料，在真实 full-wave/noise likelihood 下难以区分；差别对待预测任务有实质影响；不是由于 forward mismatch、非法 generator parameters 或未收敛的求解器造成。

单峰但显著 uncertainty 也可需要概率输出，不过第一步应比较 conditional Gaussian、低秩 covariance head 或小 ensemble；不是所有 posterior 都值得 diffusion。任务原文允许“deterministic ceiling”作为触发线索，本规格把它保留为诊断线索，而不是充分启动条件。

## T9a. 线性补空间未必低维

若 p 维材料仅 r 个 independent physics coordinates 被确定，线性补空间维数是 p−r。OPM current rank 小不使这个维数变小。若每个 current representation 有 q 个复自由度，单个对应 real material-to-data map 的 rank 至多 2q；多照明和多频堆叠需按实际 block 总维数重新计数。

因此本路线里的“q≪p 的 prior latent”必须另有证据，不能把 current q 和 prior q 使用同一符号混淆。以下记 prior latent dimension 为 d_z。

## T9b. 分布支持下的 conditional fiber dimension

假设合法材料分布位于一个 d 维 C¹ manifold M 上，physics coordinate map c(x)=V_pᵀx 在局部的切向 rank 恒为 r_M。由 constant-rank 局部坐标形式，固定 c 的 fiber 维数为 d−r_M。

**解释/证明。** 在局部坐标中 c 只有 r_M 个独立坐标约束，剩下 d−r_M 个坐标可变化。这个结论提供低维 conditional prior 的可能性，但 manifold 本身是材料分布假设，不是 Maxwell 赋予的压缩性。存在噪声时 fiber 变成有厚度的区域；跨分支可出现多个 fibers。

## T9c. 可实测的 dimension proxy

令 m(z)=E[b|z]，conditional residual covariance 的平均为

\[
\overline C=E[(b-m(z))(b-m(z))^T].
\]

对固定 d_z 维正交输出子空间，最优平均线性压缩误差为

\[
\min_{U^TU=I}\ E\|(I-UU^T)(b-m(z))\|^2
=\sum_{j>d_z}\lambda_j(\overline C).
\]

**证明。** 左侧为 tr(Cbar)−tr(UᵀCbar U)，由特征分解最大化保留的 trace。证毕。

这只是固定线性 residual latent 的误差 proxy，不是一般 diffusion sample-complexity theorem。m(z) 的有限样本估计误差必须交叉验证；不能用训练残差很小证明真实 conditional dimension 很低。

## 2. 五类模型的选择

| 方法 | 本任务的合理定位 | 风险/成本 |
|---|---|---|
| DDPM | 成熟的 conditional latent denoising baseline | 常需多次网络求值；与 time-to-image 目标冲突时不优先 |
| score/SDE model | 需要 posterior score 与多尺度噪声机制时 | likelihood guidance 常引入 forward/adjoint 成本 |
| rectified flow | 小 latent 中较少 ODE evaluations 的候选 | 不能未经测试承诺单步 sampling 或正确 calibration |
| conditional flow matching | 从联合 (b,z) 样本摊销 conditional posterior | 需要真实 conditional variability 和足量数据，防 variance collapse |
| conditional normalizing flow | d_z 小、希望显式 density/快速采样 | 表达多模态与条件稳定性需验证，可能比 diffusion 更合适 |

方法基础见 DDPM/score/flow matching/rectified flow [R27–R30]；inverse-problem CFM 见 [R21,R22]。在本任务的预算和输出结构下，若将来通过 gates，优先比较小 conditional normalizing flow 与小 conditional flow matching，而非默认 DDPM。

## 3. Conditional flow matching 的最小数学接口

设 z 是 frozen physics encoding，b₁ 是真实 prior coefficients，b₀~N(0,I)，路径 b_t=(1−t)b₀+t b₁。可训练

\[
\mathcal L_{CFM}=E\|u_\theta(t,b_t,z)-(b_1-b_0)\|^2,
\]

并积分 db_t/dt=uθ(t,b_t,z)。这是一种标准 CFM 选择，不是本轮原创算法。采样 b 后仍须遵守 DECODER 中的保护/数据预算；事后硬裁剪会改变目标分布，应把它纳入训练分布或显式说明 resulting posterior approximation。

本文件不给训练步数/GPU campaign，因为前置 scientific gates 未通过。

## 4. Posterior 不能只用图像好看来检验

必要输出：held-out conditional coverage、spread–error relation、posterior predictive discrepancy、合法材料比例、多样性与模式覆盖；小模型可用可信 reference posterior 做对照。data consistency 不能替代 posterior calibration。

严格锁定 ahat 并只对 b 采样，近似的是 p(b|y, a=ahat)，不一定是完整 p(a,b|y)。若 physics uncertainty 不可忽略，需传播 a 的测量不确定性；这不同于允许 NN 任意改变物理均值。

条件均值在平方损失下已最优。若 b_* 和另一个 posterior sample 条件独立，sample 的期望平方误差为 2 tr(C)，而 posterior mean 为 tr(C)。所以 diffusion 的正当目的不是必然提高单图 MSE，而是表达不可消除的多解性与校准风险。

## 5. 近邻与启动门槛

SDPS 已经研究 subspace diffusion，但其 subspace 是空间分辨率/多尺度结构，并非本任务的 material recoverability complement [R19]。NPN 也将 null-space-aware prior 接入 diffusion [R04]。必须把这些当近邻，不能宣称“只在 subspace 用 diffusion”本身新颖。

将来的启动条件：Gate A/B/C/D 有证据；真实 ambiguity 合法且任务相关；d_z 的 residual tail 足够小；小 deterministic/单峰 UQ baseline 明确不足；新的训练预算经用户单独批准。任何一项未满足，本文件维持 theory-only。
