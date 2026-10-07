# Two-sided recoverability 与有限区域 one-shot 定理

## 1. 从 A21 借什么，不借什么

上传任务给定 A21：对冻结 quadratic，同时匹配 primal optimum action 与 post-step residual 的 dual action，可以恢复 full GN optimum。这是本轮的背景机制，不是本轮 online 特征。

本轮不使用未知 s_F、e_F。我们把目标换为可直接解释的材料坐标 `vᵀx`，寻找从 measurements 返回该坐标的低增益 witness h。

## 2. Backward attribution 的正确目标

在固定线性模型中

\[
A^Th=M^TP^TO^Th.
\]

若 `Aᵀh=v`，则 `hᵀd` 是 vᵀx 的无偏估计。这个条件同时排除了其他材料方向的污染，不只要求一条大能量反传路径。

在 `x=t v+Nb` 的模型中，条件变成

\[
h^TAv=1,\qquad N^TA^Th=0.
\]

给定 q=ΠAv，T1 的最小方差 h=q/||q||² 可用两个小 reduced solves 实现：一次 forward propagation z=PMv，一次 adjoint propagation w=PᵀOᵀh。

### 2.1 “Overlap”解释成立到什么程度

\[
\langle Mv,P^TO^Tq\rangle=\|q\|^2.
\]

这说明归因后的测量响应与材料激发的 dual pullback 存在精确配对。可以定义夹角，但归一化夹角本身不是 recoverability：极弱的响应也可能夹角为零。最终必须同时控制 magnitude、noise amplification 和 nuisance orthogonality。

不是两个独立传感通道提供了双倍信息。Aᵀ由 A 决定；two-sided 的价值是检查 reverse attribution 和 approximation fidelity。

## T4. Common-dual finite-region one-shot theorem

设真实白化 forward map f 在开凸区域 K 上 C¹，x₀∈K。令 C∈R^{r×p} 表示需要恢复的材料坐标，D∈R^{r×m} 是固定数据解码器。

**精确形式。** 下述两个条件等价：

\[
D[f(x)-f(x_0)]=C(x-x_0)\quad\forall x\in K;
\]
\[
D J(x)=C\quad\forall x\in K.
\]

**证明。** 从第一式对 x 求导得到第二式。反之沿 `x₀+t(x−x₀)` 积分，

\[
D[f(x)-f(x_0)]=\int_0^1 DJ(x_0+t\Delta x)\Delta x\,dt=C\Delta x.
\]

证毕。常微积分即可证明；此处的价值是它给出了“何时固定物理 decoder 能绕过 nonlinear GN”的精确设计条件，不将此基本证明包装成全新数学工具。

**近似形式。** 若在 K 内有 uniform bound

\[
\|DJ(x)-C\|\le\epsilon_C,
\]

则 `ahat=Dd` 满足

\[
\|\hat a-C\Delta x\|\le
\epsilon_C\|\Delta x\|+\|D\|\nu.
\]

若 `Δx=V_phys a+V_rem b` 且 C=V_physᵀ，又有

\[
\|DJ(x)V_{\rm phys}-I\|\le\eta_p,
\quad \|DJ(x)V_{\rm rem}\|\le\eta_n,
\]

则更细的界为

\[
\|\hat a-a\|\le\eta_p\|a\|+\eta_n\|b\|+\|D\|\nu.
\]

### 3.1 这是一个正面结果，不要求全图弱散射

例子 `f(a,b)=(a,b+b³)` 可以高度非线性，但 D=[1,0]、C=[1,0] 给出 a 的精确 one-shot recovery。一般 Maxwell 问题不一定具有精确结构，但这提示应研究 `DJ(x)` 的稳定性，而不是要求整个 J(x) 稳定。

因此，不能把“全波非线性”直接当作 one-shot 不可能的理由。应该检验所选材料坐标的 backward attribution 是否跨状态保持稳定。

另一方面，这一定理仅刻画固定线性 decoder；它不否定可能存在的非线性解析逆、data-driven ROM inversion 或其他 nonlinear one-shot 方法。

## 4. OPM 条件化版本

对 D 的第 i 行 h_iᵀ，跨状态条件为

\[
M(x)^TP(x)^TO(x)^Th_i\approx c_i,
\]

还需加上 full-vs-ROM defect 和材料参数化误差。可把近似误差拆成：

- M 变化：材料扰动激发的位置/场分布变了；
- P 变化：内部反馈重新放大、旋转或抵消；
- O 变化：几何/频率/接收系统改变；
- ROM 漏失：current representation 并未包含真实双向路径。

T2 给出结构化 perturbation envelope，T3 给出遗漏路径 envelope。它们可以共同组成 η_p、η_n 的 upper bound；若预算来自独立验证集，则只能称为 distributional calibration，不能称为 uniform theorem certificate。

## 5. “共同见证”比逐场景 LIS 更严格

每个 x 都有 `v∈Range(J(x)ᵀ)`，并不保证存在同一个 h，使 `J(x)ᵀh=v` 对所有 x 同时成立。逐状态恢复可能需要不同的数据组合。

最小反例：标量 J(x) 随 x 变化且非恒定。每个 J(x) 非零，但固定 h 不可能同时满足 hJ(x)=1。由此可知，跨物体公共可恢复空间的定义需要 common decoder，不能只取各自 row space 的交集。

分布版本可最小化

\[
\mathbb E_{x\sim\mu}\|D J(x)-C\|_F^2+\lambda\|D\|_F^2.
\]

这在缓存 state ensemble 上可以廉价形成比较基线，但 μ 是明确的训练/设计分布，不能声称对任意新材料成立。训练、验证、测试必须按 scene/geometry 切分，而不是按同一物体的方向切分。

## 6. 数据依赖的 Q、basis、witness

固定模型的 Gaussian variance `||h||²` 和充分统计量结论不能原样搬到 `h(y),Q(y)`。同一份噪声参与选空间和估计，会产生 selection bias。

首轮优先使用固定已知背景/geometry 的 Q。若用 BP(y) 构建背景：

1. 将整条 algorithm 纳入外层 noise replication 和 coverage calibration；
2. 或用独立 pilot measurements 构造背景/Q，另一批 measurements 估计坐标；
3. deterministic noise-norm bound 对任意选出的 h 仍成立，但 state、模型及余项 bounds 必须在对应区域统一有效。

不能把第一种 empirical calibration 标记成第二种条件独立定理。

## 7. 与原 A21 的准确连接

A21 匹配特定 optimum 与 residual 的双向 action；本轮匹配目标材料函数与 measurement witness 的双向 action。前者保证 frozen optimization solution，后者保证 coefficient attribution，并通过 T4 延伸到有限区域的 one-shot reconstruction。两者共享“primal support 不等于 inverse attribution”的思想，但目的、数据依赖性、验收指标不同。
