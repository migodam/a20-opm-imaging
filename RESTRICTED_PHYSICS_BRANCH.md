# 受限physics-only分支

**CASE_C_A2_MATCHES_OR_BEATS_A3；NN与扩展仍为NOT_RUN。**

Test B对每个冻结split直接解 `min ||d-AW V_phys a||² + lambda||a||²`，`V_prior=0`。每方法显式使用原full-scene lambda，而不是重新由restricted A定标。Gaussian/voxel像素可行域仍由原32D mass chart映射：Re chi>=-0.5、Im chi>=0；original solver/SLSQP、exact redundant-row compression、active-equation检查、feasibility/KKT阈值保持原样。无post clipping、jitter、pinv或Maxwell fallback。

21120个受限QP，invalid `0`。原solver在active-KKT解上发出ill-conditioned matrix警告；不隐瞒，不改solver。所有返回的点仍通过原最终合同，详细结果见[NUMERICAL_AUDIT](results/a22_r1/NUMERICAL_AUDIT.json)及每case QP字段。

| 方法 | restricted/common median scene ratio | S4 |
|---|---:|---|
| RANDOM | 1.11952 | SUPPORT |
| A1 | 0.986317 | SUPPORT |
| A2 | 0.986317 | SUPPORT |
| A3 | 0.986317 | SUPPORT |
| OFFLINE_FULL_J | 0.970766 | SUPPORT |

S4按每scene restricted physics NRMSE均值 / common projection physics NRMSE均值，再取四scene中位数；不是把所有draw视为独立数据或先筛掉失败。Test B的prior NRMSE=1源于prior被置零，不能拿其S_sep或q当作Test A分离证据。

## Test B主表（用于实际分支误差）

| 方法 | physics NRMSE均值 | prior NRMSE均值 | S_sep中位数 | q_phys中位数 | q_prior中位数 | truth_phys中位数 |
|---|---:|---:|---:|---:|---:|---:|
| RANDOM | 1.01255 | 1 | 1.45359 | 0.809445 | 1.64566 | 0.742074 |
| A1 | 0.509877 | 1 | 2.09648 | 0.572277 | 2.25773 | 0.740968 |
| A2 | 0.509877 | 1 | 2.09648 | 0.572277 | 2.25773 | 0.740968 |
| A3 | 0.509877 | 1 | 2.09648 | 0.572277 | 2.25773 | 0.740968 |
| FULL-J（仅离线） | 0.548452 | 1 | 1.80804 | 0.65144 | 2.1091 | 0.741394 |

线性白化data residual、small-solve measured wall/CPU、prior coefficient leakage在[RESTRICTED_BRANCH_RUNTIME_AND_DATA.csv](results/a22_r1/RESTRICTED_BRANCH_RUNTIME_AND_DATA.csv)。完整nonlinear residual为NOT_RUN，未启动任何new nonlinear solve。受限分支在Mac上执行，common archive来自原Windows；差异及阈值保留见[补充](REPRODUCTION_CONFLICT_ADDENDUM.md)。

计时细分见[CACHED_ONE_SHOT_RUNTIME](CACHED_ONE_SHOT_RUNTIME.md)；缓存kernel不能当完整部署加速。
