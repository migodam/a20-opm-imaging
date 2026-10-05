# A20 Route A：实际后端与协议映射

静态审阅日期：2026-10-05。审阅时本地 commit：`UNBORN_HEAD`。`git rev-parse --verify HEAD` 未成功，因此本轮不能提供已经提交的 A20 HEAD；主线程提交后应补记。上游来源依 `vendor/a17/UPSTREAM_PROVENANCE.json` 声明：A17 EXCHANGE_R1 的 A9 内核及 A10 可行步快照；A16 问题 commit 为 `e17f9de3469964c8f4cd1b1c967d2e2f14b3d277`。历史来源记录已读，本轮未重新验证上游来源，未进行 hash 检查。

该表只定位函数和静态契约。本 worker 没有运行 G0、replay 或重建测试；“有函数”不等于“已验证”。源码由主线程同时开发，最终以主线程提交版本为准。

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
| 多频 | backend `Adapter.full_state` 的 frequency 检查 | 单 adapter 只对应一个频率；另频须独立 Green/receiver adapter 再聚合。本轮未验证跨频 composite |
| 全目标/约束 | backend `Adapter.full_objective/material_constraints` | whitened residual + 同物料先验，real χ≥−0.5、imag χ≥0；传入 state 必须同 χ |
| 精确 retained Schur | `src/a20/opm.py`：`SchurFeedback` 的 `R_U/F/F_adjoint/T/K` | 缓存 FU/F*U，retained core 可逆/稳定检查，empty U 合同；静态与公式对应，未运行相等性测试 |
| O/P/M 种子 | opm `build_seeds` / backend `BasisView` | O=T* S*白化数据探针，P=Kb，M=KB物料探针；先包含各源再压缩；预算和原列范数有记录 |
| 混合 degree 空间 | opm `BlockStream/Hierarchy.at_degree` | O 走 F_eff*，P/M 走 F_eff；各流自己递推，再 joint orthogonalization；明确 joint core 非单 Hessenberg |
| Galerkin/备选投影 | opm `Projection` | 正常 W=Z；不安全时 QR(LZ) 定义 frozen-test Petrov，试探物料时冻结 W；无静默 pseudo-inverse |
| A1/A2 tangent | opm `ReducedJacobian`；backend `reduced_state` | 调用方所传 state 决定 B(j_full) 或 B(j_m)；A2 frozen basis/test 的更新策略需由 runner 与 G0 验证 |
| 共同约束二次模型 | `src/a20/material.py`：`constraint_map/solve_quadratic/kkt/full_quadratic_audit` | 直接 SPD 可行解或 SLSQP/L-BFGS-B 约束求解，带 normal、可行性及 KKT residual；没有验证其实际通过 |
| 成本 | backend `counters_and_timers`；`src/a20/costs.py`：`CostBook.span/receipt`；vendor `Counters` | process CPU、exclusive wall、各 RHS/因子分解/回退等；嵌套 wall 不能求和当总部署 wall |

## 旧 post-projection 与当前合同的冲突

`vendor/a17/experiment_support.step` 解无约束 GN 的 CG；`vendor/a17/feasible_step.project_step` 随后以 Euclidean 距离投影到被动物料集合。该函数自己标注 `projection_optimality_certified=False`，原证书只覆盖投影前 proposal。即便投影精确，它也不是一般 H 度量的约束 GN 最优步，不能套用协议 T8 的完整 KKT 等式/界作为已满足条件。

A20 `material.solve_quadratic` 将相同物料边界放在二次模型内部，并在返回前检查 normal/KKT 与可行性；这一调用与旧 post-projection 应在 full GN、OPM 及普通 ROM 对照中一致采用。这里只记录落实路径，未替代 G0。

静态发现一个需要 G0 小 voxel 案例覆盖的实现边界：`constraint_map` 对 voxel 返回 A=None，而当前 `solve_quadratic` 的 d≤128 分支仍出现 A@unconstrained。可能导致 TypeError；已通知主线程，本 worker 未改代码。主线程修复后应以最终源码/测试更新该条。

## 本轮未核验

未测试伴随、Schur 等价、有限差分、跨频聚合、KKT、core fallback、种子泄露防护或 GPU 路径；未评价 G0/G1/G2/G3。没有读取或更改任何实验结果，也未以源码存在性宣告科学 gate 完成。
