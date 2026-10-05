# A20 Route A：实际后端与协议映射

复核日期：2026-10-05。本轮静态读取当前源码与已经保存的 G0 报告，没有新增实验。上游来源仍依 `vendor/a17/UPSTREAM_PROVENANCE.json` 声明：A17 EXCHANGE_R1 的 A9 内核及 A10 可行步快照；A16 问题历史 commit 为 `e17f9de3469964c8f4cd1b1c967d2e2f14b3d277`。该历史标识原样保留，本轮未重新验证上游来源或计算 hash。

以下“PASS”来自相应报告，函数表同时注明其验证范围。科学 gate 的解释与最终判断由主线程负责；本表没有把 G0 外推为 replay、G1 表征质量或 G2 总部署成本通过。

## 已保存的三层 G0 证据

| 报告 | 已记录结果与验证范围 | 尚不覆盖 |
|---|---|---|
| [`results/G0_LOCAL.json`](../results/G0_LOCAL.json)，最新 `attempt_007` | **26/26 PASS**。CPU 上 2³ cell 的真实 3D vector-Maxwell DenseDDA，小 current 维数 24；Gaussian 物料图表维数 6、voxel 实物料维数 16；3 sources、4 receiver positions，每频 48 个实数据分量，complex128/float64。覆盖 current 伴随、实物料 B 回拉、原生 jvp/vjp 等价、packing/whitening、Schur 与 Galerkin、frozen/moving 导数、A1/A2 区分、Gaussian/voxel 约束 KKT、core 拒绝与 fallback、缓存失效、在线 capability 拒绝及失败计费；还包含 tiny 两次更新 smoke。 | tiny 接口/数值完整性及 smoke 不能代替原六对象重建、总体速度、噪声鲁棒性或盲测。 |
| [`results/G0_REAL.json`](../results/G0_REAL.json) | **PASS，两个历史真实状态**：parents 2001、2005，均为 iteration 0。每状态 6 sources、64 receiver positions、128 个复 receiver channels；complex128/float64。报告阈值为伴随/等价误差 10⁻⁹、FD 平台 10⁻⁵；覆盖原生 J/伴随等价，L/F/S 与实 B 伴随，Schur operator/resolvent/伴随、reduced J 伴随、full 与 frozen reduced FD，以及 moving Galerkin 显式额外项和 frozen-test Petrov FD。 | 仅这两个已暴露历史状态；不是六对象 replay、非线性成像 fidelity 或速度证据，也没有原对象跨频 pilot。 |
| [`results/G0_ALGEBRA.json`](../results/G0_ALGEBRA.json) | **ALL ASSERTIONS PASSED**，20 次有限维 synthetic algebra 随机试验，以及协议既定反例。覆盖 Schur/resolvent、dual residual defect、GN stationarity/gap/bounds、degree innovation、unitary gauge 与 prior-safe restricted bound；two-sided moment 检查只对实际测试条件成立。 | 不含 Maxwell 成像数据；不是理论的普遍性证明或物理任务有效性验证。 |

G0_LOCAL 的最大配对伴随相对误差为 1.445×10⁻¹⁴，最大已报 FD 误差为 8.351×10⁻¹¹；Gaussian chart KKT relative 为 7.261×10⁻¹⁷，voxel 为 2.565×10⁻⁹。两个频率 0.9/1.25 的独立物理模型、共享物料与数据堆叠已在 **tiny** 测试内覆盖；它不能关闭真实对象跨频大规模 pilot 的缺口。

| G0_REAL 状态 | full FD 最低已报相对误差 | frozen reduced FD 最低已报相对误差 | moving Galerkin 省略 basis 导数项的相对误差 | 补齐额外项后的相对误差 |
|---|---:|---:|---:|---:|
| 2001 / iteration 0 | 1.594×10⁻¹¹ | 1.772×10⁻¹¹ | 3.002×10⁻⁴ | 1.616×10⁻¹¹ |
| 2005 / iteration 0 | 1.707×10⁻¹¹ | 2.434×10⁻¹¹ | 3.633×10⁻⁴ | 1.949×10⁻¹¹ |

这些 moving-basis 对照保留了省略项造成的可测误差，不能据 frozen-basis FD 通过而删除 basis-motion 条件。Synthetic algebra 也保留了 delayed feedback、nonnormal resolvent、Galerkin breakdown、false weak 与 bias/variance 反例，不能把低 degree 的局部稳定性当成高 degree 或 full 模型保证。

## 物理定义

`vendor/a17/a9_engine.py` 的 `DenseDDA` 使用三维 dyadic Green（`dyadic_green`/`build_goff`），每个 cell 三个复电流分量。计算电流坐标 `c=p/sqrt(v)` 已将质量度量转为 Euclidean；`GS=sqrt(v)*receiver_operator(...)`，`GD=v*Goff`。

实际物料系数是 CM + radiation reaction 的 `polarizability(chi,v,k)`：α=3vχ/[χ+3−i3(k³/6π)vχ]，及其导数 dα/dχ。因而 F=diag(α repeated 3)Goff，L=I−F，b=diag(α)e_inc/sqrt(v)。应以当前核的系数/导数落实协议抽象 X，不能硬编码 `F=diag(χ)Goff`。

## 函数映射

| 协议契约 | 本地文件 / 函数 | 静态对应与待验证边界 |
|---|---|---|
| L/L*、F/F* | `src/a20/backend.py`：`Adapter._apply/apply_L/apply_L_adjoint/apply_F/apply_F_adjoint`；vendor `DenseDDA.L/A_matrix` | 复 current actions；F 由 I−L；作用按 RHS 计数 |
| S/S* | backend `Adapter.apply_S/apply_S_adjoint`；vendor `receiver_operator` | 原始物理接收 map GS；白化另施加 |
| full state | backend `Adapter.full_state`；vendor `DenseDDA.state` / `DDAState` | 状态以全 L 因子分解及各照明 RHS 求解；source residual 检查；按同物料缓存 |
| B | backend `Adapter.injection_factor/apply_B`；vendor `DDAState._tangent_rhs` | 状态自己的 exciting field × dα/dχ × 实物料增量 /sqrt(v)；包括 b′ 和 L′ 引起的注入 |
| REAL B* | backend `Adapter.apply_B_adjoint` / `MaterialChart.adjoint`；vendor `DDAState.vjp/real_material_gradient` | 复共轭回拉后映到全 Re/Im 物料坐标；不得将 complex current adjoint 当成复物料更新 |
| 物料尺度 | backend `MaterialChart.expand/adjoint/project`、`load_problem`；vendor `experiment_support.Tangent` | Gaussian Q 满足 v QᵀQ=I；voxel 以 1/sqrt(v) 展开；读取既有 chart |
| full J/Jᵀ | backend `Adapter.full_tangent_action/full_adjoint_action`；opm `FullJacobian` | state.jvp/vjp，真实物料图表与白化；小空间可缓存数据 Jacobian |
| 噪声及源堆叠 | backend `pack/unpack`、`Adapter.whiten` | 每 illumination 内 Re/Im 排列；白化在 real pack 后，伴随用 transpose；多源 P 已显式保留 |
| 多频 | backend `Adapter.full_state` 的 frequency 检查 | 单 adapter 只对应一个频率；另频须独立 Green/receiver adapter 再聚合。G0_LOCAL 已验证 tiny 两频共享物料堆叠与异模型拒绝；真实跨频大规模 pilot 未验证 |
| 全目标/约束 | backend `Adapter.full_objective/material_constraints` | whitened residual + 同物料先验，real χ≥−0.5、imag χ≥0；传入 state 必须同 χ |
| 精确 retained Schur | `src/a20/opm.py`：`SchurFeedback` 的 `R_U/F/F_adjoint/T/K` | 缓存 FU/F*U，retained core 可逆/稳定检查，empty U 合同；G0_LOCAL 与真实两状态已报等价/伴随通过，synthetic algebra 独立检查身份式 |
| O/P/M 种子 | opm `build_seeds` / backend `BasisView` | O=T* S*白化数据探针，P=Kb，M=KB物料探针；先包含各源再压缩；预算和原列范数有记录 |
| 混合 degree 空间 | opm `BlockStream/Hierarchy.at_degree` | O 走 F_eff*，P/M 走 F_eff；各流自己递推，再 joint orthogonalization；明确 joint core 非单 Hessenberg |
| Galerkin/备选投影 | opm `Projection` | 正常 W=Z；不安全时 QR(LZ) 定义 frozen-test Petrov，试探物料时冻结 W；无静默 pseudo-inverse |
| A1/A2 tangent | opm `ReducedJacobian`；backend `reduced_state`；imaging `reconstruct` | A1 用 B(c_full)，A2 用 B(c_m) 且 residual 同 reduced state；G0_LOCAL 覆盖两者差异、frozen 导数和 tiny loop，G0_REAL 验证 frozen reduced FD；原六对象 A1/A2 质量未由这些检查决定 |
| 共同约束二次模型 | `src/a20/material.py`：`constraint_map/solve_quadratic/kkt/full_quadratic_audit` | 已登记小 Gaussian 空间用可行直接 SPD 或 SLSQP 加经验证的 active-equation polish；voxel 用 L-BFGS-B bound quadratic。返回前检查 normal/KKT/可行性；G0_LOCAL 包含两种 chart 的 KKT 与 full-gap bounds |
| 成本 | backend `counters_and_timers`；`src/a20/costs.py`：`CostBook.span/receipt`；vendor `Counters` | process CPU、exclusive wall、各 RHS/因子分解/回退等；嵌套 wall 不能求和当总部署 wall |

## 公式—函数对应

记 retained 正交 current basis 为 U，补空间投影为 Π=I−UU*；Γ=U*LU=I−U*FU。数据白化记为 W_y；投影 test basis 记为 V，避免与白化混淆。所有实物料方向 s 均由 `MaterialChart.expand` 转回 χ 的复增量，current 空间仍用复共轭伴随。

| 公式 / 操作 | 函数落点与实际合同 |
|---|---|
| R_U=UΓ⁻¹U*；F_eff=ΠFΠ+ΠFUΓ⁻¹U*FΠ | `opm.SchurFeedback.__init__/R_U/F/F_adjoint`。Γ 经 singular-value 与 condition 双重安全检查才做 LU；补空间 actions 使用实际 F/F*，不以对角物料 χ 替代 polarizability。 |
| T=(I−R_U L)Π；K=Π(I−L R_U)；L⁻¹=R_U+T(I_Π−F_eff)⁻¹K | `SchurFeedback.T/T_adjoint/K/K_adjoint` 与精确 Schur 构造；I_Π 表示补空间单位算子。这个身份式依赖 retained core 可逆，不能解释为任何 degree 下的精确 full 解。 |
| O=orth{T*S*unpack(W_yᵀΩ_y)}；P=orth{K[b_ℓ]_ℓ}；M=orth{K[B_ℓΩ_χ]_ℓ} | `opm.build_seeds`，动作由 `backend.BasisView` 提供。Ω_y 含 measured residual 及独立数据探针，Ω_χ 为实物料探针，可包含先前 accepted step；各源先展开，再按 O/P/M 预算压缩。`seed_provenance` 记录 requested/actual rank、原列范数和 deflation。 |
| Z_m=orth span{U, (F_eff*)ᵏO, F_effᵏP, F_effᵏM：0≤k≤m} | `opm.BlockStream/Hierarchy.at_degree`。三个流分别递推，再联合正交化；joint core 没有单一 Hessenberg 声明。 |
| R_{Z,V}=Z(V*LZ)⁻¹V*；通常 V=Z | `opm.Projection.apply/adjoint/solve`。Galerkin core 不安全时显式采用 V=qr(LZ) 的 frozen-test Petrov；trial 物料上更新 L/core，固定 Z/V。命名 fallback 与计费保留，不静默使用 pseudo-inverse。 |
| A1：r=r_full；J_m s=W_y pack[S R_{Z,V} B(c_full)s] | `imaging.reconstruct` 的 mode 分支传 full state 给 `ReducedJacobian`。这是 full-state tangent 的投影近似；其一般值不是 reduced state map 的导数。 |
| A2：c_m=R_{Z,V}b；r_m=W_y pack(Sc_m−data)；J_m s=W_y pack[S R_{Z,V} B(c_m)s] | `backend.Adapter.reduced_state` 与 `opm.ReducedJacobian`。子问题固定 Z/V 时为该 reduced map 的一致导数；seed 首次由 `imaging.zero_state` 的 incident/zero-current bootstrap，之后由前一 frozen space 在当前物料刷新，不把 full-current correction 注入 seeds。basis-motion 情况另需显式导数项。 |
| min_{χ+expand(s)∈C} ½‖r+Js‖²+ℓᵀs+½λ‖s‖²，H=JᵀJ+λI，g=Jᵀr+ℓ；C={Re χ≥−0.5, Im χ≥0} | 所有 FULL_GN/OPM/SOM/KRYLOV 经 `imaging.reconstruct → material.solve_quadratic`，采用同一约束、先验/LM policy 与 KKT 接受条件；r/J 按各自已登记 full/A1/A2 模型代入。不是先解无约束后裁剪。 |
| Hs+g+n_C(s)=0；normal 来自非负 active multipliers | `material.kkt/constraint_map` 记录 stationarity、violation、complementarity；`solve_quadratic` 未满足登记 tolerance 则抛 `QPFailure` 并保留失败 metadata。 |
| ‖s_m−s_*‖_H/‖s_*‖_H、full quadratic gap、‖q+n‖/√λ 与 ‖q+n‖²/(2λ) | `material.full_quadratic_audit`。参考 H-energy 过小则 relative error 为 missing；约束 normal 情形使用误差/目标 gap 上界，不能把无约束 equality 当成约束 equality。 |

每种方法的 nonlinear acceptance 与 stopping 都由 `imaging.reconstruct` 付费计算 full objective、full gradient 和共同 full KKT；A2 采用 reduced 子问题没有免除这些费用。函数映射只说明实现路径，不预判 G1/G2 是否达到登记门槛。

## 旧 post-projection 与当前合同的冲突

`vendor/a17/experiment_support.step` 解无约束 GN 的 CG；`vendor/a17/feasible_step.project_step` 随后以 Euclidean 距离投影到被动物料集合。该函数自己标注 `projection_optimality_certified=False`，原证书只覆盖投影前 proposal。即便投影精确，它也不是一般 H 度量的约束 GN 最优步，不能套用协议 T8 的完整 KKT 等式/界作为已满足条件。

A20 `material.solve_quadratic` 将物料边界放在二次模型内部，并在返回前检查 normal/KKT 与可行性；FULL_GN、OPM 及普通 ROM 对照共用该入口。G0_LOCAL 已报 Gaussian 和 voxel 两种 chart 的约束检查通过。旧 proposal 的投影前证书仍不能移植到投影后步骤。

## 本轮实验覆盖与缺口

六对象12 states的replay已完成尝试；degree/rank/action观测前沿及合规paired bootstrap见[replay报告](../REPLAY_REPORT.md)。voxel参考与部分QP失败保留，完整H-step gate为HOLD，当前实现进阶NO_GO；不得从G0或有限子集推断成像成功。真实对象跨频大规模pilot、A1/A2成像fidelity、含全物理与refresh/acceptance/stop的总部署成本，以及噪声/held-receiver/warm-timing均没有完成。本文不从G0推出degree必然单调改善或总体加速。

本次更新只读取既有报告与源码，不改源码、协议、测试或 results，不新增物理计算。历史失败与 costs 原件仍由原报告保留；GPU 大规模路径不在本文所引 G0_LOCAL 的 CPU tiny 验证范围内。
