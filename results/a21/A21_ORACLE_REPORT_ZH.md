# A21 固定 rank 双侧 GN anatomy：科学报告

**T0：PASS。T1：LATE_GN_TWO_SIDED_FIDELITY_CONFIRMED。** 五个 iteration17 状态的35个主实验均有效；五态 BOTH_G 均通过有效尺度上的5% H-step目标，primal和匹配随机对照支持双侧任务信息的归因。该结论严格限定于五个历史暴露 Gaussian 对象的冻结受约束二次问题。成像质量、在线获取方法、部署收益和NN均未验证，实验已停止。

## 冻结问题和检查

冻结来源为 A20-R1 `3b3b17b5f4cf5d37b26602ead2dfe7c913b37e23`，物理执行源码为 `5c6bcb02bb4ab88f7b46f07bca4ca3f4e38a067c`。Maxwell、极化率、材料chart、白化、prior/LM、可行集、优化器和KKT门槛均复用原实现。每源64 receivers×2极化，共128个complex测量；packing为逐源 `[Re128,Im128]`，六源得到1536维实测量。材料为 `[Re27,Im27]` 共54维。

每态只付费生成一次full state/LU和full J；canonical原始 constrained `full_GN_reference_None` 步未被alpha缩放，五个保存参考均重新通过原KKT审核，**没有重解或覆盖参考**。first/middle/last（2001、2003、2013）真实pack/白化/材料metric/B/B*/L/L*/F/F*/receiver/Schur及tied-adjoint测试通过。完整137项本地测试及随包tiny validation通过，最终56项A21回归与3项报告allowance回归也通过。

[独立数组复核](INDEPENDENT_ARRAY_REVIEW.json)重新核对全部35套J/H/原始步/约束normal/乘子/缺陷向量、由已付费images重建JR、完整gap和solver-aware界；没有再跑Maxwell、QP或truth。所有参考H尺度为5.7973e-4–3.6324e-3，solver能量残差远低于它们；无参考分母需要用floor替代。

## 全部五态主结果

下表均为相对H_F-step误差 **百分比**；未使用floor改变分母。

| Parent/17 | BASE_G | PRIMAL_G | DUAL_G | BOTH_G | RANDOM_G | BOTH_PG | RANDOM_PG |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2001 | 269.506% | 262.002% | 80.6541% | 1.31144e-11% | 280.15% | 5.60304e-12% | 231.004% |
| 2005 | 449.688% | 420.884% | 98.6278% | 1.22916e-11% | 471.195% | 1.06456e-11% | 452.952% |
| 2003 | 146.157% | 144.315% | 48.9695% | 4.39562e-09% | 153.085% | 2.33448e-09% | 144.565% |
| 2007 | 336.452% | 282.041% | 100.783% | 1.50079e-11% | 340.221% | 8.12833e-12% | 228.043% |
| 2013 | 156.494% | 111.381% | 98.7314% | 1.23506e-11% | 165.821% | 4.42133e-12% | 144.231% |
| Median | 269.506% | 262.002% | 98.6278% | 1.31144e-11% | 280.15% | 8.12833e-12% | 228.043% |

BOTH_G最大相对误差为4.3956e-11（即4.3956e-9%），BOTH_PG为2.3345e-11。全部G实际trial/test/union rank=56/56/56，全部PG为56/56/62；G单基4.429688MiB，PG双基8.859375MiB。保护X/Y的真实独立新增rank各6、joint12，随机G12、随机PG两侧6/6完全匹配。未增加degree、补列或按结果选择删除方向。BASE_G重现原保存步的最坏相对差4.0584e-10，低于冻结1e-9门槛。

## 为什么primal capture不是GN-step fidelity

X_F描述沿正确材料步产生的六源完整Maxwell current响应；Y_F描述 **post-step residual** 被真实伴随传播回current空间的任务信息。这里保护的是L^{-1}B s_F和L^{-*}S* lift(Dᵀe_F)，而非旧KB材料注入。PRIMAL_G只知道正确响应，仍可能把post-step residual对其他材料方向的拉回算错；DUAL_G则反过来。

完整材料向量分解为 `eta_direct = rho_F + delta_d + JRᵀ delta_p`。delta_d是54维材料向量，不是一个标量配对；报告和NPZ保存全部分量及 `eta_pair=rho_F+delta_d+JRᵀdelta_p-rho_R`。PRIMAL_G的epsilon_P为1.25e-14–5.25e-14，却保留显著的dual defect；DUAL_G的epsilon_D为2.13e-14–1.96e-12，却保留放大的primal项。两种单侧方法五态都未达5%。

| Parent/17 | PRIMAL b_dual | PRIMAL b_primal | weighted solver/dual | BOTH_G HF abs error | raw HF bound | HF error/raw bound |
|---|---:|---:|---:|---:|---:|---:|
| 2001 | 0.00148192 | 8.22185e-18 | 8.04565e-15 | 9.35415e-17 | 1.44231e-16 | 0.648554 |
| 2005 | 0.00254691 | 1.33865e-17 | 5.91281e-14 | 9.55736e-17 | 2.08431e-16 | 0.458538 |
| 2003 | 0.00517114 | 2.09275e-17 | 3.04288e-11 | 1.59666e-13 | 2.55074e-13 | 0.625959 |
| 2007 | 0.00118429 | 1.09969e-17 | 2.72332e-14 | 8.70054e-17 | 1.1748e-16 | 0.740595 |
| 2013 | 0.00128889 | 2.65235e-17 | 1.53229e-14 | 1.58738e-16 | 2.38204e-16 | 0.666396 |

PRIMAL的加权solver项最多只是dual项的3.05e-11；其法锥allowance对1e-3量级H-error亦可忽略。因此该反例不能用优化器误差或数值normal救场来解释。BOTH_G同时消除两项，匹配随机替换没有恢复步。

**基线失败并非只有dual问题。** 基线的放大primal项在2001、2005、2007、2013的HR逆范数中更大；2003则dual更大。双侧保护支持“响应和残差拉回都必须保真”，不能把全部基线误差改写成单一dual原因。

## 曲率、normal与solver-aware界

所有H_F/H_R对称且SPD；各态固定Lambda最小特征值为3.43e-5。使用对称广义特征值beta，而非当前core条件数替代材料曲率；所有35臂的实测绝对H-error甚至都低于原始solver-aware界，最大error/bound=0.740595。数值normal allowance和floating allowance仍独立保存，不参与降低误差或改变5%目标。

| Parent/17 | HF min | HF max | cond HF | BOTH_G mu | BOTH_G beta | sF H norm | full/reduced active |
|---|---:|---:|---:|---:|---:|---:|---|
| 2001 | 0.000285675 | 9.00226 | 31512.3 | 0.000419984 | 2.82187 | 0.000713271 | 2/2 |
| 2005 | 0.000263653 | 17.9702 | 68158.4 | 0.000273581 | 3.02797 | 0.000777554 | 2/2 |
| 2003 | 0.000176286 | 1.32346 | 7507.45 | 0.00036437 | 2.65674 | 0.00363239 | 10/10 |
| 2007 | 0.000250764 | 17.168 | 68462.8 | 0.000244138 | 2.4085 | 0.00057973 | 1/1 |
| 2013 | 0.000264461 | 18.8257 | 71185.4 | 0.000280123 | 2.26117 | 0.00128526 | 3/3 |

按冻结约定计算 `b_R=sqrt(eta_pairᵀ HR^{-1} eta_pair)`、`B_F=sqrt(beta)b_R`；normal来自独立活跃约束NNLS，n=-Aᵀmu，未用n=-gradient抹去缺陷。可行性、互补性、乘子符号和正定性逐套核对。完整gap直接计算并核验 `qF(sR)-qF(sF)=0.5||sR-sF||HF²-nFᵀ(sR-sF)+rhoFᵀ(sR-sF)`。BOTH臂直接gap约1e-20，包含微小负数，这是减去近等二次目标的舍入尺度，已原样保留；不能解释为超过full optimum。

### 逐态解释

- **2001**：PRIMAL的dual仍大；DUAL去掉dual后仍有80.65%误差。BASE有两项部分抵消（Euclidean cancellation≈0.714），仍未保真；BOTH保留2个full活跃约束，恢复原步。
- **2005**：BASE放大primal在HR逆范数中约为dual的3.3倍；PRIMAL改正响应却仍有420.88%误差，DUAL仍98.63%。BOTH恢复2个活跃约束；约6.8e4的HF条件数需显式报告，却没有违反bound。
- **2003**：BASE的加权dual大于加权primal。原参考含10个活跃约束，PRIMAL/DUAL各12；BOTH恢复10。原参考rho_F≈2.409e-14导致BOTH最明显的数值误差，但仅1.597e-13绝对H-error，受原始2.551e-13界覆盖，仍远低于5%。
- **2007**：BASE/DUAL没有活跃约束，full参考为1；PRIMAL变为2，BOTH恢复1。DUAL消除pullback defect后仍100.78%，显示放大primal不能忽略；不存在core、KKT或分母失效。
- **2013**：BASE放大primal远大于dual，DUAL仍98.73%；PRIMAL保留dual则111.38%。BOTH恢复full的3个活跃约束，误差回到数值尺度。

所有状态均可判，缺失/invalid/reference repair均为0。current core最坏条件数890.664仍通过原安全门；没有Petrov自动切换、full fallback、jitter或伪逆。Petrov两个oracle臂同样通过，但union rank62及双倍基内存必须和G分开；其优势尚未建立。

## 费用、失败与交付

[COST_LEDGER](COST_LEDGER.jsonl)、[JOB_LEDGER](JOB_LEDGER.jsonl)、[失败](FAILURE_LEDGER.jsonl)和[最终预算](BUDGET_FINAL.json)记录所有验证、错误、传输和报告。物理job CPU267.359375秒、GPU占用281.661815秒；共享full-J1620 RHS、验证JVP36/VJP36、oracle primal30/adjoint30、full state30 RHS，共1782 full solve RHS；F/F*/L/L*各163/103/631/171，aggregate1068不能再叠加。这些是offline机制实验成本，不是部署速度测试。原full-state L/Goff各30 RHS、receiver、LU、QR和QP分账见[动作解释](ACTION_ACCOUNTING.md)。

五份共享缓存和35套诊断向量均已保存，物理job只有35个主QP；没有full-reference repair或物理重跑。压缩archive首次超过25秒CPU上限，失败及25.953125秒CPU保留；重新用唯一命名STORED archive转移已存在结果，没有重跑实验。报告层absolute allowance接线冲突和只读账本核对脚本的一次失败也单列。原A20/R1账本与源码未改动；旧early复现冲突及voxel reference失败保留。

[图表](figures/)及[rawdata](rawdata/)包括全部五态误差/界、加权stationarity、曲率、normal work和双基内存。各项指标、余下完整向量及六源capture在[A21_METRICS.csv](A21_METRICS.csv)、[per_state](per_state/)和缓存中。

结论是冻结受约束GN任务的**双侧保真机制得到验证**，并非在线算法或非线性成像已完成。T2、degree扩展、NN、nonlinear reconstruction、solver acceleration和发布均NOT_RUN；完成五-state anatomy后停止。
