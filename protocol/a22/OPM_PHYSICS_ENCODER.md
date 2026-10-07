# OPM as physics encoder：充分统计量、token 与部署成本

## 1. 把静态算子与测量内容分开

单独给网络 {O,P,M} 并不是编码了本次测量：这些量在固定背景/几何下对所有对象可能相同。至少要输入测量在该物理通道中的投影 t，以及 physics coefficients、剩余 residual 信息。

推荐第一版的输入为

\[
z_{enc}=[t,\widehat a,\text{recoverability signature},
\text{geometry/frequency descriptor},\text{failure mask}].
\]

signature 包括 attribution、two-sided ROM residual、propagation stability 与 amplitude validity；不使用 truth 或 full-GN step。

## T8. 固定 OPM 线性模型下的充分统计量

设 d=A x+n，n~N(0,I)，固定 Z 有正交列且 Range(A)⊂Range(Z)。令 t=Zᵀd，则

\[
\|d-Ax\|^2=\|t-Z^TAx\|^2+\|(I-ZZ^T)d\|^2.
\]

第二项与 x 无关，故 t 是该线性 Gaussian 模型中关于 x 的充分统计量。

**证明。** Ax∈Range(Z)，正交分解无交叉项；代入 Gaussian likelihood，因子分解即得。证毕。

可由 O（含 Schur direct path）做 thin QR 得到 Z，不必构造 full J。若直接使用仅 forward seed 的小数据子空间，应检查是否遗漏 A 的 range。关于精确 nonlinear full-wave 模型，上述充分性不自动成立；被丢弃的 residual 可能携带 material 信息。

实际可保留 orthogonal residual norm 与几个固定随机/物理 residual probes 用于模型失效诊断。这些 probes 不是证明完整 nonlinear sufficiency 的替代品。

## 2. O/P/M × degree tokens 的物理含义

首轮 degree 固定 0 或 1；已有 degree2 只作缓存对照，不开启扩大 degree 路线。每个 seed token 可记录 family provenance、degree、物理归一化 norm、复系数实/虚部、receiver coupling、material coupling、feedback residual 及所用尺度。

**family label 是生成来源，不是任意正交旋转下的内禀标签。** QR/SVD 的符号、复相位、简并子空间旋转会让 naive coefficient NN 学习随机 gauge。推荐：固定 QR convention 并对参考基 Procrustes 对齐；或输入 projector/bilinear invariants；简并 clusters 按块处理。允许读者检查 gauge unit test。

对任意测量 witness h，保存 primal z=PMv 与 dual w=PᵀOᵀh 的 paired diagnostics，而不是只有 norm token。相干 direct/feedback cancellation 用 `Re<d_direct,d_feedback>` 与各自 norm 表示；只给两者能量会丢掉抵消机制。

## 3. Injection-weak 的命名检查

小 ||Q*Bv|| 可能是 full injection 真弱，也可能只是 Q 覆盖不到。增加廉价 `||Bv||` 和投影残差 `||(I−QQ*)Bv||`；使用非 Euclidean metric 时替换成对应正交投影。后者大时标签是 representation miss，不应直接叫 material prior necessity。最终依然以 two-sided full-vs-ROM defect 控制，而不是只按 injection coverage 判好坏。

## 4. 网络形式比较

| Decoder | 何时有理由使用 | 本轮选择 |
|---|---|---|
| 小 MLP | 固定 k、固定坐标次序、少量 geometry features | 第一选择，2–3 层即可作为实验候选 |
| set encoder/小 transformer | 可变 transmitter/receiver 数量、token permutation | 只有固定 MLP 因输入形式明确受限时再测试 |
| convolutional decoder | voxel-like spatial residual 且坐标固定 | 作为公平 whole-image/residual baseline；不自动 prior-safe |
| graph decoder | 明确不规则网格/邻接结构 | 首轮无必要 |
| operator decoder | 跨几何/网格泛化确为 primary target | 需要独立大实验，不在本轮预算内 |

OPM 替代 generic encoder 的价值应由消融回答：同 decoder、同 train scenes、近似同参数量，比较 raw-data compression、BP image、small A-SVD statistic、OPM statistic + fingerprints。若只加入更多 features 获胜，不足以证明物理 factorization 的必要性。

## 5. Cheap 的完整计数

记录背景场 RHS、B/B* actions、S/S* actions、G_D/G_D* actions、Q construction、orthogonalization、small matrix factorization、W construction 和 encoder time。在线不能计算 full H 或每个 full J column 再声称 encoder cheap。

离线固定几何可预计算的部分独立列出；新 geometry 的 cold-start 必须重新计入。用真实未知场景 F 的 oracle field 构造 Q 仅可作上界实验，不能混进部署结果。

## 6. 文献位置

physics/backprojection encoder 已见于 SOM-Net [R05]、BP-based learned imaging [R25]；范围/零空间分支已见于 NSN/DDN/NPN [R01,R03,R04]。OPM 的待验证差异是机制化的 recoverability/robustness descriptor 与 frozen material-coordinate protection，而不是泛称“物理 encoder 加神经 decoder”。
