# Material physics / prior split：可归因的 block decomposition

## 1. 先声明“在哪个材料空间内”

所有投影以下均在归一化实材料坐标 x 中定义。令 W∈R^{p×k} 为正交材料模型，x=Wc+x_out，Wᵀx_out=0。首轮 k=32 或 64，而不是把完整 voxel space 悄悄换成小模型后仍声称完整材料可恢复。

在 W 内构造正交矩阵 [V_p,V_n]；为简洁记其提升后的 p 维基仍为 V_p,V_n。则

\[
\operatorname{Range}(W)=V_{\rm phys}\oplus V_{\rm rem},\quad
P_{\rm phys}=V_pV_p^T.
\]

完整材料空间还包含 W 的外部余项。只能在已经验证外部余项的数据影响可忽略、或有明确模型约束时，省略它。

**关键限制：** arbitrary full-space nuisance 下，线性可恢复的材料函数 vᵀx 必须满足 v∈Range(Aᵀ)。任意单个 voxel、wavelet 或 Gaussian 参数方向即使 ||Av|| 很大，也未必满足此条件。限制其他材料自由度是模型假设，不能称作完全不使用先验。

## 2. V_rem 不应自动全部喂给 NN

数学上可以保留用户要求的二分。操作上，补空间必须附带原因标签：

| 标签 | 含义 | 默认动作 |
|---|---|---|
| prior_eligible | 在可信物理模型和噪声水平下，确有弱约束或归因混淆 | 可评估 prior completion |
| model_unresolved | Q 漏失、背景错误、resolvent 失稳、模型偏差过大 | 拒绝或一次物理修正，不当作 prior |
| finite_amplitude_unvalidated | tangent 判据有效范围未覆盖待成像对象 | 扩大验证或拒绝 |
| outside_material_model | 不在 W 中，未检查其数据混淆 | 单列 truncation error |

这不是把科学目标改成 current selection，而是防止网络替错误 forward model 填坑。若只想输出两个名字，可令 V_prior=V_rem，但必须同时返回 eligibility mask；没有 mask 的“弱模都靠 NN”不成立。

## T5. Profiled one-shot reconstruction 与误差界

设在声明材料模型内

\[
d=A_p a_*+K b_*+e,\quad A_p=AV_p,\quad K=AV_n,
\]

其中 e 汇总噪声、full-vs-ROM 误差、非线性余项及外部模型影响。定义

\[
\Pi=I-KK^\dagger,\quad G=\Pi A_p,\quad s=\sigma_{\min}(G)>0.
\]

不需要估计 b_* 就能计算

\[
\widehat a=(G^TG+\lambda I)^{-1}G^T\Pi d=:D_\lambda d.
\]

于是

\[
\|\widehat a-a_*\|\le
\frac{\lambda}{s^2+\lambda}\|a_*\|
+\max_j\frac{\sigma_j(G)}{\sigma_j(G)^2+\lambda}\|e\|.
\]

λ=0 时简化为 ||ahat−a_*||≤||e||/s。

**证明。** 因 ΠK=0，代入后

\[
\widehat a-a_*= -\lambda(G^TG+\lambda I)^{-1}a_*
 +(G^TG+\lambda I)^{-1}G^T\Pi e.
\]

分别对 G 做 SVD，取两个算子的谱范数，且 ||Π||≤1，即得。证毕。

λ>0 的 shrinkage 也是显式偏差，不可因名称叫 physics branch 就称为“完全 prior-independent 真值”。硬阈值、材料尺度和有限 W 也都需要声明。

### 2.1 为什么原来的小 Tikhonov 公式不总够用

直接解 min_a ||d−A_p a||²+λ||a||² 的误差中还含

\[
(A_p^TA_p+\lambda I)^{-1}A_p^T Kb_*.
\]

若 prior 部分在数据中投影到 physics 部分，它会污染 a。可采用以下两种合法策略，而不是默默令 b_*=0：

- 使用上述 nuisance profiling；
- 用 near-null complement 或小 SVD 的数据正交性，并明确上界 cross-talk 与 ||b_*||。

若完整补空间让 Range(K) 覆盖所有数据，则 Π=0，没有可无先验恢复的这种目标坐标。此时可以改成可识别的材料线性组合，但不能把真实的 non-identifiability 通过加 regularization 隐藏。

## 3. 稳定性是 block 性质

逐个方向通过 α/β/γ 阈值，不保证其 span 可恢复。例如 A=[1,1]，e₁和 e₂ 都强，但 e₁−e₂ 是 null direction。每次形成 V_p 都要重新检查 s、D 的噪声增益、DA V_n 与 DJ−V_pᵀ 的误差预算。

固定 D、V_p、V_n 后，跨状态稳定性直接用 `TWO_SIDED_RECOVERABILITY.md` 的 common-dual theorem 检查；这比每个场景重新取一个看起来漂亮的子空间更接近可部署 one-shot。若每次都重算 basis，报告 material projector 的 principal angles 与 rank 跳变；接近谱阈值的模式设缓冲区，不强制二元翻转。

## 4. 七种构造方式的裁决

| 用户要求的方法 | 实际对象 | 裁决 |
|---|---|---|
| three-fold thresholding | normalized α,β,γ, attribution, ROM/curvature budget | 只能做诊断和筛查；不能单独形成最终 span |
| joint generalized eigenproblem | 小空间中 signal covariance 与声明 uncertainty penalty | 候选生成器；仍需 block/witness 认证，不把手调加权叫物理定律 |
| block SVD | [M W; P M W; A W]，分块无量纲化 | 提供机制坐标；不能把 current units 和 data units 原样堆叠 |
| distributional stable subspace | 固定 W、跨背景的 witness error | 推荐第二阶段；均值好不代表每个场景有保证 |
| two-sided task coordinates | 目标函数 C 与小 witness space，控制 DA−C | 首选核心；与 one-shot 目标直接对应 |
| frequency-consistent directions | 联合白化多频，共同 nuisance | 推荐；见多频定理，不把各频独立 profile 后直接相加 |
| posterior-calibrated directions | prior-whitened/LIS 或经验 conditional covariance | 强 baseline 与 prior-latent 选择；标明 prior dependence |

小 SVD of A W 是诚实且便宜的初始化和基线：取若干右奇异向量得到候选 V_p，并不等于本工作只做 SVD。OPM 的保留资格取决于它能否进一步筛除“名义强但物理不稳”的方向，或预测跨模型、跨背景失败。

## 5. Material bases 的执行优先级

第一：固定 multiscale wavelet/patch basis，兼有位置和尺度解释，避免 Gaussian-family bias。第二：现有 Gaussian parameter tangent，作为代码验证和与旧结果连接的专用模型。第三：低频 Fourier 加少量局部细节，检验所谓 coarse/detail split 是否真的存在。

Voxel canonical axes 用作诊断，不默认每个像素可独立恢复。PCA 只在 train scenes 上拟合，并记录已引入分布先验。edge/detail basis 可在第二阶段用，但从 truth edges 构造线上 basis 属于泄漏。低频不自动 physics，高频不自动 prior。

## 6. 一个最小可实现构造

固定 χ₀、W 和浅 Q → 计算 M W、P M W、A W → small SVD 初始化 → 形成 r∈{4,8,16} 候选 V_p → 用完整 W 内 complement 做 profiling/检查数据正交性 → 构造 D → 计算 OPM 双向误差预算 → 删去不合格的材料坐标或降低声明适用域 → 返回 split、projector、witness、eligibility 与失败原因。

不得使用真值、full-GN step、测试集最优 rank 来确定线上 split。相同 K 的 numerical rank threshold 必须由噪声与预注册数值容差共同确定，并对 threshold perturbation 做敏感性检查。

## 7. 误差分离的非平凡检验

同时报告 absolute task error 与单位维度/真值能量归一化的 projected error，避免把极小 r 或几乎无真值能量的 V_p 选出来制造成功。比较同 rank 的随机基、A-SVD、prior-LIS 与 OPM-witness 基。只有 V_p 内误差小且有实用任务覆盖，才存在值得锁定的 physics branch。

相关已知框架：SOM/TSOM [R00]、LIS [R06,R07]、active subspaces [R08]、goal-oriented Bayesian reduction [R09]。这些是最近邻，不是可忽略的背景。
