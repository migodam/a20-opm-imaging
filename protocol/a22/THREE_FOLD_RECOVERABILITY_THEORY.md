# Three-fold recoverability：定义、正面结果与反例

## 0. 问题与尺度

令归一化材料参数为 x∈R^p，物理材料为 χ=χ₀+Cχ x。Cχ 必须由明确的单位、体素质量矩阵或基函数尺度给出；用 learned PCA/先验协方差作 Cχ 时，应注明模型已使用分布先验。

复数据先按实际实协方差 Γ_R 白化：

\[
d=\Gamma_R^{-1/2}\begin{bmatrix}\Re(y-F(\chi_0))\\\Im(y-F(\chi_0))\end{bmatrix}.
\]

proper complex noise 的实、虚部方差约定必须显式测试，不能漏掉 1/2。以下 J、A、O、P、M 默认已实化并白化；复算子的 `*` 是 Hermitian，实化后为 transpose。若用复式计算实参数梯度，最后要取相应实部。

冻结 full-wave map 为 J=S L⁻¹ B；整体 Galerkin current approximation 为

\[
R=Q(Q^*LQ)^{-1}Q^*,\quad A=SRB=OPM,
\]
\[
M=Q^*B,\quad P=(Q^*LQ)^{-1},\quad O=SQ.
\]

材料右侧尺度和数据白化已吸收到 B、S。Q 应在物理 current metric 中正交；这里的 Euclidean norm 只有完成此归一化后才有可比意义，不自动等于电磁能量。

### 0.1 Schur 实现不能漏掉 retained direct path

在正交 current coordinates [U,Z] 下，写

\[
L=\begin{bmatrix}L_{11}&L_{12}\\L_{21}&L_{22}\end{bmatrix},\quad
B=\begin{bmatrix}B_1\\B_2\end{bmatrix},\quad S=[S_1,S_2].
\]

令 Σ=L₂₂−L₂₁L₁₁⁻¹L₁₂，则

\[
J=S_1L_{11}^{-1}B_1+
(S_2-S_1L_{11}^{-1}L_{12})\Sigma^{-1}(B_2-L_{21}L_{11}^{-1}B_1).
\]

只分析第二项的三因子而忽略第一项，不是在分析完整 material-to-data map。两路径还存在 `2 Re<j_direct,j_feedback>` 的相干项。首轮建议把 retained U 包含在整体 Q 中；使用 Schur 接口时保留 direct term 和 interference token，并逐项验证等价性。

## T0. 精确线性统计信息不能由因子分解凭空增加

**命题。** 在相同参数化、噪声分布和可行材料类下，两个精确线性实验如果有同一个 J，则它们的 likelihood、可识别参数函数及相同 prior 下的 posterior 相同。给 J 换一种 M/P/O 分解，不会改变这些对象。

**证明。** 两实验都是 d=Jx+n，条件分布 p(d|x) 完全相同。任何估计器的风险只取决于此实验及损失；Bayes posterior 再乘同一个 prior 后亦相同。Gaussian、固定协方差时信息矩阵是 JᵀJ。证毕。

**意义。** OPM 不应声称胜过同一精确 J/Fisher 所包含的统计信息。它可能增加的是机制解释、结构化模型不确定性、干预预测和计算可用性。

## 1. Three-fold signature 应是什么

对单位材料方向 v 定义 a=Mv，z=Pa，j=Oz。若中间量非零，

\[
\alpha=\|a\|,\quad \beta=\|z\|/\|a\|,\quad
\gamma=\|j\|/\|z\|,
\quad \alpha\beta\gamma=\|Av\|.
\]

零分母时使用精确分支和 `undefined/zero` 标签，不用人为 eps 让零模看似有有限 gain。alpha/beta/gamma 是一个分解响应强度的 signature，不是三个彼此独立的必要阈值。

例如 M=diag(ε,1,1)、P=diag(1,ε,1)、O=diag(1,1,ε)，得到 A=εI。三个方向分别是 injection、propagation、observation contraction，但同噪声下统计强度相同。

如果 P 可逆，`ker(PM)=ker(M)`：feedback 不会额外制造精确 null dimension；它可以严重压缩、放大、混合，或者使响应对模型误差敏感。必须区分“小 propagation gain”和“resolvent 不稳”。non-normality 要看 singular/resolvent 或指定扰动响应，不能只看 eigenvalues。

### 1.1 Gauge 检查

对非正交坐标变化 z=Tz′，M′=T⁻¹M、P′=T⁻¹PT、O′=OT，产品不变但 raw factor norms 一般改变。必须同时传递 metric `G′=T*GT`。在固定物理 metric 下，unitary current coordinate 变化不改变上述 signature；任意重新缩放内部状态并保持 Euclidean norm 不变，则所谓“weak mechanism”没有不变意义。

## T1. Nuisance-profiled recoverability 定理

令 x=t v+N b，其中 v 为单位目标方向，N 张成必须允许同时变化的 nuisance space。定义

\[
K=AN,\quad \Pi=I-KK^\dagger,\quad
q=\Pi Av,\quad g(v\mid N)=\|q\|.
\]

1. t 存在对任意 b 无偏的线性估计，当且仅当 g>0。
2. 白噪声 covariance=I 时，最小方差无偏线性 witness 为
\[
h=q/g^2,\quad h^TAv=1,\quad h^TAN=0,\quad\operatorname{Var}(h^T d)=g^{-2}.
\]
3. 有界噪声 ||n||≤ν 下，无限制 nuisance 且目标幅度范围容许最坏二点构造时，最优最坏绝对误差为 ν/g。

**证明。** nuisance 无偏要求 h∈Range(K)⊥。于是 hᵀAv=hᵀq。Cauchy–Schwarz 给 `||h||≥1/||q||`，等号在上述 h 取到。g=0 时 Av∈Range(K)，改变 t 可由 b 精确抵消，故不可识别。最坏误差上界是 ν||h||；下界取目标间距 2ν/g，并选 nuisance 抵消 Av 的 Range(K) 分量，使两均值距离恰为 2ν，它们可以被半径 ν 的噪声球隐藏。证毕。

这个结论针对声明的 nuisance 类，不把其他参数固定为真值。若限制 b 的幅度或使用 prior，风险会改变。

### 1.2 OPM 形式与第四个诊断

\[
g=\alpha\beta\gamma_N,\qquad
\gamma_N=\|\Pi OP Mv\|/\|PMv\|.
\]

也可保留普通 γ，并加入 attribution ratio

\[
\eta_{\rm attr}=\|\Pi Av\|/\|Av\|\in[0,1].
\]

于是 `g=alpha beta gamma eta_attr`。这不是无根据的线性加权，而是由估计误差得到的精确分解。

反例 A=[[1,1],[0,ε]]：两列 norm 都约为 1，但恢复第一坐标且允许第二坐标未知时，g=ε/√(1+ε²)。ε=10⁻³、noise std=10⁻³，单独看响应会误以为误差约 10⁻³，真实系数标准差约 1。

## T2. Factor-structured finite perturbation bound

用小矩阵 K₀ 表示 nominal reduced propagation equation，P=K₀⁻¹。考虑

\[
A'= (O+\Delta O)(K_0+\Delta K)^{-1}(M+\Delta M),
\]

且 ||ΔM||≤ε_M、||ΔK||≤ε_P、||ΔO||≤ε_O，`||P|| ε_P<1`。这些是已声明的 uncertainty sets，不能由同一张重建图的观感反推。

固定 x 和 witness h，令 z=PMx、w=PᵀOᵀh，

\[
\bar z(x)=\frac{\|z\|+\|P\|\epsilon_M\|x\|}{1-\|P\|\epsilon_P}.
\]

则有包含高阶交叉作用的有限扰动界

\[
|h^T(A'-A)x|\le
\epsilon_M\|w\|\|x\|
+(\epsilon_P\|w\|+\epsilon_O\|h\|)\bar z(x).
\]

**证明。** 设 z′=(K₀+ΔK)⁻¹(M+ΔM)x。由 K₀(z′−z)=ΔM x−ΔK z′，

`hᵀ(A′−A)x=wᵀΔM x−wᵀΔK z′+hᵀΔO z′`。

Neumann resolvent bound 给 ||z′||≤zbar；对三个项用 Cauchy–Schwarz 即得。此推导没有把交叉项默默删去。证毕。

### 2.1 它为何可能比 total gain 更有用

在 A=εI 的例子中，同样大小的绝对 ΔM 扰动可以主要影响 injection-weak 方向；同样大小的 ΔO 扰动则可以主要影响 observation-weak 方向。这是“同 Fisher、不同脆弱性”的可检验预测。

但物理误差常同时改变多个 factors，例如几何变化会影响 S、G、E。因此应先从真实扰动参数推导关联变化，再把独立 factor norm bounds 当保守包络；不能把人为独立矩阵噪声当作 Maxwell 真实性能证据。

### 2.2 Recoverability certificate / score

设 ||x||≤ρ，非线性与外部模型误差的数据余项分别有界 b_nl、b_out。对于目标 vᵀx，定义

\[
\mathcal B(h,v)=
\rho\|A^Th-v\|+\nu\|h\|
+\rho E_{\rm ROM}(h)+\rho E_{\rm fac}(h)
+\|h\|(b_{\rm nl}+b_{\rm out}).
\]

这里 E_fac 用 T2 的单位球界；E_ROM 用 T3 或其他合法的 full-vs-ROM bound。**同一个误差不得同时计入两个预算。**

\[
\mathcal B_*(v)=\inf_{h\in\mathcal H_{\rm cheap}}\mathcal B(h,v),\qquad
R(v)=\tau_v/\mathcal B_*(v).
\]

τ_v 是预声明的材料容差。R≥1 表示 sufficient acceptance，不是 posterior probability；界太保守造成拒绝不等于该方向真的不可恢复。向量 signature 应同时返回 noise、attribution、M/P/O uncertainty、ROM、nonlinearity 各分量。

固定这些常数与廉价 witness 空间后，常用 norm-envelope 形式是凸的，可做小 SOCP；第一轮也可只评估解析 least-squares witnesses，避免依赖额外优化包。

## T3. Two-sided ROM defect：防止把 ROM-weak 当 physics-weak

只要 RLR=R，定义

\[
I_R=B-LRB,\quad O_R=S-SRL.
\]

则

\[
J-A=O_RL^{-1}I_R.
\]

**证明。** 展开右侧：SL⁻¹B−SRB−SRB+SRLRB；最后一项由 RLR=R 化为 SRB。证毕。

若 full L 的 inf-sup lower bound 为 α_L>0，则

\[
|h^T(J-A)x|\le
\frac{\|O_R^Th\|\,\|I_Rx\|}{\alpha_L}.
\]

复变量采用对应 Hermitian pairing；实参数版本取实部后仍受同一绝对值界控制。

这只需 primal residual 与 adjoint residual 的算子动作，并不需要显式 full J/H。但是得到可信 α_L 或可靠的替代 envelope 不是免费步骤。仅用几个随机 probes 的观测最大值不构成 deterministic norm upper bound；需单独标记 empirical/probabilistic/certified。

## 3. 本轮真正的理论目标

T0/T1 是标准统计识别几何的具体化，T3 是既有 Galerkin defect 结构。新的论文候选组织方式是：T2 的 factor 机制 + T3 的模型可信度 + common-dual finite-region theorem，共同控制 one-shot 材料坐标，而不是控制每一步 GN。详见 `TWO_SIDED_RECOVERABILITY.md`。

### 补充：operator-coordinate gauge 与 raw Galerkin matrices

上文 similarity 变换针对同一 reduced equation 在新的状态坐标中的表示。若直接替换 Galerkin trial/test basis 为 Q′=QT，raw matrices 的变换实际上是 M′=T*M、K′=T*KT、O′=OT；其产品仍不变，但 K′⁻¹ 不是简单 similarity。把 test-coordinate mass/Riesz map 一并转换后才得到上面的 state-coordinate 形式。工程中首选物理 metric 下正交 Q，不应把这两种坐标约定混用。
