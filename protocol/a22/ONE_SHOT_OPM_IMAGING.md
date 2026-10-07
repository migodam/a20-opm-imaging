# One-shot OPM imaging：三种成像算法与有限幅度条件

## 1. 不能隐藏 background acquisition

OPM factors 一般依赖 χ₀、内部场 E₀、频率和几何。它们不是仅凭 y 就免费得到的固定字典。推荐提供两个部署入口：

**已知背景扰动成像：** χ₀ 已知，背景场与固定几何可缓存。可以存在强散射背景，只要求材料变化相对该背景满足后述条件。

**未知对象粗成像：** 先用 BP、Born/Tikhonov 或 EBA 得到廉价 χ₀，再构造一次 OPM。这个 pilot 的时间、数据依赖和误差都计入总体成本。BP 的 current→total field→contrast 三步不是新算法，见陈旭东著作 printed p.133, eqs.(6.25)–(6.30) [R00]。

在完全空背景 χ₀=0、normalized current formulation 中 L₀=I；此时 tangent 是 Born map。扩大 current polynomial degree 不会自动知道未知对象中的 multiple scattering。这个事实必须在代码和文章中直接显示。

## 2. 一个明确的有限幅度余项

考虑 normalized current equation

\[
j=X(E^{inc}+G_Dj),\quad X=\operatorname{diag}(\chi),
\]

多照明时按列或 block 堆叠。令 δX=X−X₀，L₀=I−X₀G_D、E₀=Einc+G_Dj₀，则

\[
\delta j=L_0^{-1}\delta X E_0+
L_0^{-1}\delta X G_D\delta j.
\]

置 u=L₀⁻¹δX E₀、T=L₀⁻¹δXG_D。若 t=||T||<1，

\[
\delta j=(I-T)^{-1}u,\quad
\|\delta y-Su\|\le \|S\|\frac{t}{1-t}\|u\|.
\]

**证明。** δj−u=(I−T)⁻¹Tu，应用 Neumann norm bound。证毕。

这是足够条件，不是 Maxwell one-shot 的必要条件；||T||≥1 时这个界失效，不等于真实解不存在。non-normal resolvent 会让界保守。实际材料离散化若使用 nonlinear polarizability，还需包含 α(χ) 的二阶余项，不能原样套用 δX 线性公式。

另一个更宽的条件是 common-dual theorem：即使整个 δy 明显非线性，只要用于恢复 coarse coordinates 的 D 抑制这些非线性分量，Dδy 仍可接近线性。前述 full-output 余项界与这个 task-specific 条件应同时比较。

## Algorithm A. Three-Fold One-Shot Tikhonov

输入：测量 y、噪声模型、几何、频率、一个可线上得到的背景 χ₀、材料模型 W。输出：χphys、uncertainty budget、split、status。

1. 计算 d=whiten(y−F(χ₀))；缓存合法时复用 F(χ₀)、E₀。
2. 按已冻结 degree≤1 的浅 O/P/M seeds 构造一次 Q，包含必要 retained part。
3. 用小矩阵 actions 构造 A W 与机制量，不构造 full J/H。
4. 按 SPLIT 文件选择 V_p 和 Dλ。
5. ahat=Dλd，χphys=χ₀+Cχ V_p ahat。
6. 返回 material confidence 和 residual diagnostics；不在不可信方向假装已经完成定量成像。

这是一轮小线性求解，不是外层 nonlinear GN loop。若使用有约束小 solve，应声明约束且保证真参数所属假设；无约束的精确谱误差常数不能不加修改地套到不可行的 constrained case。

## Algorithm B. Physics + Deterministic Prior Completion

运行 A。只有 A/B/C gates 通过、剩余误差主要位于 eligible complement 时，执行

\[
\widehat\chi=\chi_{phys}+C_\chi V_n\widehat b_\theta(t,\widehat a,\text{signature}).
\]

decoder 不修改 V_p，也不改变本样本的 frozen split。增加明确 amplitude limiter 和 physical feasibility projection in b coordinates。数据安全性按 DECODER 文件，不依赖口头的“正交所以安全”。

## Algorithm C. Physics + Conditional Prior Posterior

运行 A，并满足 posterior ambiguity 和 latent dimension gates 后，从 pθ(b|t,ahat,signature) 采样。返回 posterior mean/uncertainty 或多种可能结构，不能把每个样本当作更准确的确定性图像。本轮只保留接口，不训练。见 DIFFUSION 文件。

## Optional E. 一次 physics consistency correction

允许在 A 或 B 后进行最多一次 correction event。应先用真实 full-wave F 检查，不以同一 ROM residual 自证。需要 correction 时，可在小材料模型内用一次 Jacobian refresh/小 constrained solve，但必须记录其所有 forward、adjoint、RHS 和 operator actions。一次 event 常需要不止一次线性系统求解，不能写成“仅一次 full-wave solve”。

若只有反复 refresh/line search 才可用，应改名 few-shot/iterative 并记录真实次数，或者将该场景判为超出本路线适用范围。不要把多步算法藏在 encoder 内。

## T7. 多频共享 nuisance 带来的正面结果

对相同材料坐标、正确独立白化的频率 f，定义

\[
g_{stack}^2=\min_b\sum_f\|J_fv+K_fb\|^2.
\]

由于对每个共同 b，逐项均不小于对应独立最小值，

\[
g_{stack}^2\ge\sum_f\min_{b_f}\|J_fv+K_fb_f\|^2.
\]

增加一个独立正确建模的频率也不能降低 g_stack²。证明只需非负项与最小值的定义。

例如 J₁=[1,1]、J₂=[1,−1]，目标为第一系数，第二系数是共同 nuisance。每个频率独立都无法归因，但两频联合 g=√2。这是频率解除归因混淆，不是简单“多一个奇异值”。

有色跨频噪声需联合 whitening；材料色散必须用共享物理色散参数，不能把不同频率的 χ 当成相同变量。若高频模型偏差增大，实际成像风险可以变差，尽管理想信息不减。

## 3. 一次/多次构造与 continuation 的区别

同时堆叠多频并一次求解，仍可叫 one-shot。低频重建→更新背景→高频重建属于 few-shot continuation；可以比较，但不得与一次构造混淆。本轮固定最多两个 frequency blocks，不搜索 polynomial degree。

location、support、coarse Fourier/wavelet coefficients 都是候选任务，不预设它们必然 physics-supported。强非线性案例中 support indicator 有用不代表 permittivity 已定量恢复。报告 qualitative 与 quantitative 两类指标。

## 4. 数据依赖的置信度

当 χ₀、Q 或 split 由同一噪声测量自适应产生时，固定 D 的 covariance `DDᵀ` 只是 conditional/frozen 近似。真实 coverage 需要重新运行整个 pipeline 的 noise resampling、独立 data partition 或带选择效应的校准。不能只冻结一个由 noisy y 得到的 Q 后把所有误差归因到最后线性层。

## 5. 与其他 one-shot 思路的关系

Born/Rytov/EBA/BP 是必要基线 [R00]。Data-driven inverse ROM 已有将 nonlinear scattering data 转为近似 Born data 的路径 [R12]；不能把“ROM 不用于每步 GN，而用于成像”本身当成新观点。这里优先验证的是物理材料坐标的 recoverability 与保护边界，而非发明所有 noniterative imaging。

## T10. Maxwell task-curvature bound：为什么某些坐标可比整个数据更线性

这给 common-dual 条件一个直接的 Maxwell feedback 解释。仍使用本文件第2节的 normalized current equation，δj=u+L₀⁻¹δXG_Dδj，u=L₀⁻¹δX E₀。对任意固定 measurement witness h，令

\[
\psi=L_0^{-*}S^*h.
\]

则非线性余项在该 witness 上有精确 identity：

\[
h^*[\delta y-J_0\delta\chi]
=\psi^*\delta X G_D\delta j.
\]

**证明。** 将 δj−u=L₀⁻¹δXG_Dδj 左乘 h*S，并把 L₀⁻¹移到伴随侧。证毕。

若 t=||L₀⁻¹δXG_D||<1，则

\[
|h^*(\delta y-J_0\delta\chi)|
\le\|G_D^*\delta X^*\psi\|
\frac{\|u\|}{1-t}.
\]

相比把整个 data remainder 再乘 ||h||，这里保留了 **adjoint field、material perturbation 与 feedback redistribution 的配对**。若这些作用在 witness 可见方向上很弱，目标材料坐标可以保持近线性，即使其他数据通道的非线性很大。这不是仅凭 ||P|| 大小作判断。

### 廉价 residual-certified 版本

取 Q 构造的 R，定义

\[
u_R=R\delta X E_0,\qquad \psi_R=R^*S^*h,
\]
\[
r_M=\delta X E_0-L_0u_R,\qquad r_O=S^*h-L_0^*\psi_R.
\]

若 full L₀ 有可信 inf-sup lower bound α_L>0，且

\[
\bar t=\|\delta XG_D\|/\alpha_L<1,
\]

则

\[
|h^*(\delta y-J_0\delta\chi)|
\le
\left(\|G_D^*\delta X^*\psi_R\|
+\frac{\|\delta XG_D\|\|r_O\|}{\alpha_L}\right)
\frac{\|u_R\|+\|r_M\|/\alpha_L}{1-\bar t}.
\]

**证明。** u−u_R=L₀⁻¹r_M，ψ−ψ_R=L₀^{-*}r_O；分别界定 ||u|| 与 ||G_D*δX*ψ||，再用 t≤tbar。证毕。

多个 physics coordinates 可逐 witness 给界后用平方和形成 block bound，也可直接使用 adjoint-field matrix 的算子范数。它只需要 reduced solutions、原算子 actions 与已声明常数，不要求显式 full J/H。

δX 对未知真值不可直接获得；线上必须对可行 perturbation set 求包络，或用已校准区域给 empirical indicator。用真实 δX 代入只能作为验证标签。α_L 与材料区域包络仍可能保守，这是应测量的 certificate availability 问题，而不是忽略的免费常数。

本结论为本轮从 Maxwell current identity 推导的 task-specific sufficient bound；不声明这一类伴随误差估计首次出现。其价值在于把 one-shot 的有限幅度失效进一步定位到 O/P/M 双向配对，而非回到每一步GN。
