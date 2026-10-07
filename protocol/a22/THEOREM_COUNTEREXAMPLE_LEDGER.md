# Theorem / counterexample / evidence ledger

研究日期：2026-10-07。`PROVED` 表示按给出的假设完成有限维推导，不表示已具有论文 novelty；`VERIFIED_TINY` 表示代码 sanity check，不表示 Maxwell 成像 gate 通过。

## 1. 正面结果

| ID | 结论 | 假设 | 状态与位置 |
|---|---|---|---|
| T0 | 相同 J 的精确线性实验不会因为 OPM 分解而增加统计信息 | 同参数、noise、prior/可行类 | PROVED；THEORY |
| T1 | nuisance-profiled sensitivity g 决定最小无偏线性方差 1/g² | 固定线性模型，明确 nuisance | PROVED + VERIFIED_TINY；THEORY |
| T2 | factor finite perturbation 的双向 witness error bound | ||P||ε_P<1，声明的 factor uncertainty sets | PROVED + VERIFIED_TINY；THEORY |
| T3 | J−A=O_R L⁻¹ I_R | RLR=R | PROVED + VERIFIED_TINY + 8-dipole check；THEORY |
| T4 | common dual condition DJ(x)=C ⇔ fixed linear one-shot exact recovery on convex region | C¹、固定 D、开凸区域 | PROVED + VERIFIED_TINY；TWO_SIDED |
| T5 | profiled Tikhonov 的 physics-coordinate error bound | block stability、nuisance profiling、模型余项有界 | PROVED + VERIFIED_TINY；SPLIT |
| T6 | prior-only correction 的材料保护与有限幅度数据预算 | orthogonal material split、weak full response、Jacobian Lipschitz | PROVED + counterexample checked；DECODER |
| T7 | 独立多频、共同 nuisance 下 profiled information 不减 | 共同材料参数及 nuisance、正确 whitening | PROVED + VERIFIED_TINY；ONE_SHOT |
| T8 | 固定 OPM 线性 Gaussian 模型的 compressed data statistic | fixed factors 与固定 noise covariance | PROVED + VERIFIED_TINY；ENCODER |
| T9 | 低维 posterior completion 需要材料 manifold/conditional covariance 的额外结构 | 正则条件或 finite second moments | PROPOSITION/standard dimension argument；DIFFUSION |

## 2. 必须保留的反例

**C1：same information / distinct causes。** A=εI 可由三个不同 weak factors 产生。杀死“三因子提供额外静态 Fisher”的说法；保留结构化鲁棒性研究。

**C2：bright but aliased。** A=[[1,1],[0,ε]]。两个坐标都 forward-strong，但单独系数不稳。杀死逐列 norm thresholding。

**C3：gauge dependence。** T=diag(100,0.1,2) 改变 raw injection norm 而不改变产品。杀死不带 metric 的跨坐标机制比较。

**C4：ROM null / full bright。** full J=I₂，Q=e₁。第二方向 reduced response 为 0，full response 为 1。杀死“Q 看不到 ⇒ measurement 不知道 ⇒ NN 来补”。

**C5：linear-safe / nonlinear-unsafe。** f(a,b)=a+b²，在 b=0 处 b 方向 tangent-null，但 b=0.5 改变数据 0.25。杀死仅凭 tangent nullspace 的 finite-amplitude data consistency。

**C6：phys-coordinate bias cannot be repaired by prior-only NN。** f(x)=x/(1−0.4x)，x*=1，background=0。J₀=1，但 one-shot xhat=5/3；若全部维度锁为 physics，prior branch 没有任何修复能力。

**C7：low-rank OPM / large complement。** p=16384、real information rank≤128 时，线性补空间至少 16256 维。此为算术反例，不代表项目实际 rank。

**C8：individual good directions / bad span。** A=[1,1]，每列 norm 为 1，但 span{e₁,e₂} 含 null direction e₁−e₂。必须 block certify。

**C9：local null / globally identifiable。** f(x)=x³ 在 0 处 J=0，仍一一对应。small/local zero derivative 不能证明全局必须依赖 prior；它说明局部 Lipschitz 稳定性不足。

**C10：non-normal feedback。** K=[[1,−k],[0,1]] 的 eigenvalues 恒为 1，inverse norm 随 k 增大。不能用 eigenvalues 代替 resolvent/inf-sup 检查。

**C11：intersection of row spaces is not a common witness。** 非恒定非零 scalar J(x) 的 row space 相同，但不存在固定 h 使 hJ(x)=1。

**C12：物理投影保护不等于材料真实性。** NN 不修改 V_phys 只保证锁定原估计；原估计有误差时，它也锁定这个误差。

## 3. 已运行数值摘要

固定 seed=20261007。完整原始结果见 `verification/results.json`。

- 随机复矩阵 two-sided defect identity relative error：约 5.03×10⁻¹⁶。
- alias example predicted coefficient variance：1.000001；100000 次噪声样本 empirical variance：约 0.997955。
- finite factor perturbation 的 actual/bound：约 0.1483。
- 两频单独 profile sensitivity 均为 0，联合为 √2。
- 八粒子三维向量模型材料导数 central-difference relative error：约 7.32×10⁻¹¹。
- 该模型 two-sided defect relative error：约 2.33×10⁻¹⁵。
- 同一 tiny model 的 reduced J relative error 约 15.8%；这说明 identity 精确不代表 approximation 足够准确。
- 四个有限幅度的 physics-coordinate errors 均在检查的 bound 内；该检查的 RHS 使用已知 full derivative/truth 作验证，不是未经成本核算的 online certificate。

## 4. 目前不能写进摘要的 claims

不能写：one-shot imaging 已加速、phys/prior error 已分离、sample complexity 已严格改善、diffusion 已必要、OPM decomposition 为首次、全部 directions 可由三 norm 正确分类、tiny model 等于三维 continuum validation。

可以写进研究计划：提出并推导了面向 one-shot material coordinates 的 OPM structured recoverability conditions；给出可复现反例；下一步验证其增量预测价值与端到端成本。

## 5. 补充结果与检查

T10（PROVED + VERIFIED_TINY）：Maxwell task-curvature identity 与 reduced primal/dual residual bound，见 ONE_SHOT_OPM_IMAGING.md。它把 common-dual 条件具体化为伴随场–材料变化–反馈场的配对，不要求整个散射数据都近线性。

补充脚本 verification/verify_additional.py 已验证 T5 的三个 λ、T6 安全半径、T8 likelihood decomposition、T10 task-curvature identity/bounds 与完整 Schur direct+feedback assembly。数值见 additional_results.json；它们仍不属于项目级 imaging gates。
