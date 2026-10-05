# G0 测试证据清单

此页仅整理已保存证据。现有状态为 **G0_LOCAL: PASS**、**G0_ALGEBRA: ALL ASSERTIONS PASSED**、**G0_REAL: PASS**；未重跑测试、重新计算 gate 或改变科学结论。

| 证据层 | 实际大小、精度与采集 | 保存结果 |
|---|---|---|
| 供给有限维代数 | 20 random trials；独立 synthetic 矩阵。manifest 声明 complex128/float64，报告未记录矩阵尺寸 | ALL ASSERTIONS PASSED；不是 Maxwell benchmark |
| tiny 实核测试 | 2×2×2 合成问题，8 voxels/24 current，chart p=6、voxel p=16；3 sources、4 receivers、每源 8 complex channels；complex128/float64、CPU | 26/26；最后 attempt_007 |
| 原尺寸 CUDA G0 | 两个历史 parent 2001/2005 的 iteration 0；N=1728，三分量 current=5184；6 sources、64 receivers、每源 128 complex channels；complex128/float64；NVIDIA GeForce RTX 4060 Laptop GPU | 两状态 PASS；g0-real-02 |

**多频范围：**实际 multi-frequency test 是 tiny 合成观测上 k=0.9/1.25 两个 DenseDDA 模型的显式 concatenate/sum。原尺寸保存的 model_init 记录均为 **单一 k=2**。没有 production 多频 driver 或真实多频数据测试。

原尺寸尺寸来自 G0_REAL 的 native model_init 事件，5184=3×1728；不读取 runtime 数组。原尺寸状态范围不是六对象完整成像或 12-state replay。

## 类别到测试的映射

下表标量来自最新保存的 cases。定性异常断言通过不等于误差为零；遗漏导数项造成的非零差是对照结果。未在原尺寸 G0 记录的检查明确保留为缺口。

| 请求类别 | 实际 tiny 测试名 | 本地观测 | 原尺寸覆盖及边界 |
|---|---|---|
| L/F/S 复杂伴随 | [test_complex_current_adjoints_and_metric](../tests/test_backend_integrity.py#L106) | L/F/S max 1.856177e-15 | tiny 与两个原尺寸状态均有伴随记录。 |
| B 实材料坐标伴随与压缩 B | [test_real_material_B_adjoint_batched_and_compressed](../tests/test_backend_integrity.py#L120) | B 伴随 0；compressed B 2.128024e-16 | 原尺寸有 B 实伴随；压缩/批方向显式等价仅 tiny。 |
| 原 jvp/vjp 与 adapter、独立因子作用等价 | [test_original_jvp_vjp_equal_adapter_and_factored_actions](../tests/test_backend_integrity.py#L139) | native 两项 0；独立因子 1.363533e-16 | 原尺寸 adapter/native 等价为 0；独立 L^-1 B / S 因子核对有 tiny 记录。 |
| 完整 tangent 与 objective 有限差分 | [test_full_tangent_and_full_objective_finite_difference](../tests/test_backend_integrity.py#L158) | tangent 2.719601e-11；objective 两项 max 1.915175e-11 | 原尺寸只记录 full tangent FD 曲线；objective/非零 prior FD 仅 tiny。 |
| 冻结 Galerkin 导数、native reduced 等价 | [test_fixed_galerkin_reduced_state_derivative_and_native_equivalence](../tests/test_backend_integrity.py#L241) | FD 3.042624e-11 | 原尺寸 frozen_reduced_FD 完整曲线保留；native reduced jvp/vjp 显式等价仅 tiny。 |
| 冻结 test 的 Petrov 导数 | [test_frozen_petrov_derivative_and_moving_least_squares_term](../tests/test_backend_integrity.py#L259) | FD 4.836210e-11 | 两个原尺寸状态也有固定 test Petrov FD。 |
| 移动 Galerkin 的显式基底导数项 | [test_moving_galerkin_basis_requires_explicit_basis_derivative](../tests/test_backend_integrity.py#L300) | 正确 FD 3.726566e-11；遗漏项差 2.103437e-02 | 原尺寸有正确 extra terms FD 与遗漏项非零差；遗漏项不是通过检查的误差。 |
| 移动 LS 的 residual 项与冻结 Petrov 的区分 | [test_frozen_petrov_derivative_and_moving_least_squares_term](../tests/test_backend_integrity.py#L259) | 正确 FD 8.350215e-11；遗漏项差 5.803792e-02 | 原尺寸 G0 未记录 moving-LS residual extra term 测试。 |
| A1/A2 tangent 合同区分 | [test_A1_full_state_tangent_distinguished_from_A2_derivative](../tests/test_backend_integrity.py#L328) | A2 FD 3.042624e-11；A1/A2 差 2.003156e-02 | tiny 对照显示 A1 tangent 与 A2 derivative 有非零差；没有原尺寸同名 G0 检查。 |
| Schur/Galerkin、resolvent 与伴随 | [test_exact_schur_actions_adjoint_resolvent_and_galerkin_equivalence](../tests/test_backend_integrity.py#L358) | Schur/Galerkin 5.986093e-16 | 原尺寸有 Schur 算子、resolvent 与反馈伴随；empty U 仅 tiny。 |
| 多源 Re/Im packing 与批探针 | [test_packing_whitening_multiple_sources_and_probe_columns](../tests/test_backend_integrity.py#L178) | 显式 packing/inverse/probe/batch 均 0 | tiny 显式 packing 四项为 0；原尺寸是六源作用/伴随，不另记录逐元素 packing 等价。 |
| 多频 stacking 与共用材料 pullback | [test_multi_frequency_stack_uses_distinct_physics_shared_material](../tests/test_backend_integrity.py#L198) | stack 伴随 2.817533e-16 | 仅 tiny k=0.9/1.25 两个真实 DenseDDA 核的显式 concatenate/sum；没有 production 多频 driver 或真实多频数据。 |
| 白化与其转置配对 | [test_packing_whitening_multiple_sources_and_probe_columns](../tests/test_backend_integrity.py#L178) | 非对角白化作用 0；伴随 1.885943e-16 | 非对角实映射为合成 tiny 测试；数据范数归一化不等于校准噪声协方差。 |
| 材料物理 metric 与实 gauge | [test_material_metric_and_real_gauge_covariance](../tests/test_backend_integrity.py#L220) | 材料 gauge J 4.458904e-16 | 原尺寸仅 saved chart/physical step 展开误差 0，未记录材料 gauge 或小 voxel KKT。 |
| 投影伴随与 current unitary gauge | [test_projection_complex_adjoint_and_current_unitary_gauge](../tests/test_backend_integrity.py#L340) | gauge 作用/state/tangent max 5.508074e-16 | Galerkin 与 Petrov 的 current gauge 都是 tiny；独立代数报告另有 unitary gauge 身份。 |
| 零 seed、零预算、empty Z/零 Jacobian | [test_seed_zero_budgets_and_zero_deflated_blocks](../tests/test_backend_integrity.py#L392) | empty projection/J 零作用；qualitative assertions PASS | 实核 fixture 上检验空投影与 J 矩阵/作用/伴随为零；原尺寸 G0 未做空基底。 |
| nested O/P/M streams、deflation 与 breakdown | [test_real_physical_hierarchy_nested_streams_and_breakdown](../tests/test_backend_integrity.py#L434) | nested prefix 三项 0 | tiny 记录 degree 0/1/2 prefix 为 0 与真实核 breakdown；原尺寸记录 degree 1/rank 32 的三独立 recurrence。 |
| 奇异及绝对尺度过小 core、命名 Petrov fallback | [test_singular_and_absolute_small_cores_rejected_and_fallback_named](../tests/test_backend_integrity.py#L459) | 拒绝/命名 fallback assertions PASS；sigma 是结构值，不是精度误差 | tiny 包括 condition=1 但绝对尺度不足的拒绝及计费 fallback；原尺寸未记录此类人为边界。 |
| 受约束 chart/voxel KKT 与 full-gap bounds | [test_constrained_chart_quadratic_KKT_and_full_gap_bound](../tests/test_backend_integrity.py#L485)<br>[test_tiny_voxel_quadratic_KKT_and_constraints](../tests/test_backend_integrity.py#L518) | chart KKT 7.260671e-17；voxel KKT 2.564998e-09 | 边界已知解、可行性、KKT 与受约束 upper bounds 均 tiny；G0_REAL 没有原尺寸 QP/KKT 结果。 |
| offline/teacher 字段和在线 loader/capability 拒绝 | [test_online_payload_and_basis_capability_reject_offline_fields](../tests/test_backend_integrity.py#L537) | deny assertions PASS；合法 chart 还原误差 0 | tiny loader 实际拒绝含 teacher/truth/full J/H/reference/unregistered 的 NPZ；capability 拒绝字段。不是 OS 文件隔离证明。 |
| 材料刷新与缓存失效 | [test_material_refresh_invalidates_projection_and_cached_reduced_matrix](../tests/test_backend_integrity.py#L567) | fresh trial 与 source cache 两项 0；拒绝 assertions PASS | tiny 检查 stale Projection/J matrix 拒绝与同材料 source 选择；原尺寸没有单独 negative-cache 检查。 |
| full API 的材料、reduced state、频率/几何 owner guards | [test_full_tangent_and_adjoint_refuse_wrong_material_state](../tests/test_backend_integrity.py#L591)<br>[test_full_physics_contract_refuses_native_and_adapter_reduced_states](../tests/test_backend_integrity.py#L598)<br>[test_full_physics_rejects_foreign_frequency_and_geometry_models](../tests/test_backend_integrity.py#L613) | 异常拒绝 assertions PASS；无标量误差 | 上述异常合同为 tiny assertions；B/B* foreign owner guard 位于 test_full_physics_rejects_foreign_frequency_and_geometry_models，没有原尺寸同名拒绝检查。 |
| 预算拒绝与失败 action 成本 | [test_budget_rejection_and_failed_action_accounting](../tests/test_backend_integrity.py#L636) | CPU_LIMIT 拒绝；FAILED action CPU>0，排他 wall 不重复累计 | tiny 用已有 CPU 超限拒绝 Adapter、并注入计费失败；远端实际 failed launch 是保守 allowance，不是精确 CPU 测量。 |
| FULL_GN/A1/A2 两次更新 smoke | [test_tiny_two_update_nonlinear_full_A1_A2_smoke](../tests/test_backend_integrity.py#L657) | 三方法 tiny smoke assertions PASS | 仅 tiny max_updates=2；本项没有六对象成像质量、部署速度或 NN 训练证据。 |
| 供给代数身份及反例 regression | [test_frozen_protocol_algebra_and_counterexample_regressions](../tests/test_backend_integrity.py#L679) | 20 random trials；saved status ALL ASSERTIONS PASSED | 独立 synthetic finite-dimensional checks；不当作 Maxwell 状态、盲留出、成像质量或速度。 |

## 数值摘要

tiny 最新报告的最大配对伴随相对误差为 **1.444538e-14**，最大正确 FD 相对误差为 **8.350215e-11**。Schur/Galerkin 等价误差 5.986093e-16；chart KKT 7.260671e-17，voxel KKT 2.564998e-09。这些 maxima 不包含故意遗漏项的对照差，也不混入独立代数报告。

| 原尺寸保存指标 | 两状态的最大值 |
|---|---|
| 伴随/等价 checks | 6.225983e-13 |
| Full tangent FD：全部记录 h 的最大误差 | 8.610676e-08 |
| Full tangent FD：每状态最佳 h 后取最大 | 1.707039e-11 |
| Frozen reduced FD：全部记录 h 的最大误差 | 7.316122e-08 |
| Frozen reduced FD：每状态最佳 h 后取最大 | 2.434450e-11 |
| 正确 moving Galerkin extra terms FD | 1.949055e-11 |
| Frozen test Petrov FD | 2.279445e-11 |
| Schur/Galerkin resolvent 等价 | 1.068132e-15 |

原尺寸 FD 的 h=10^-3、10^-4、10^-5、10^-6 四点曲线完整保留在 JSON；上表同时给全部步长最大值和最佳步长摘要，不把二者混称。原尺寸 moving Galerkin 遗漏项对照差分别为 2001: 3.002061e-04, 2005: 3.633017e-04。

有限维代数报告中身份误差最大值为 6.408396e-15；frozen basis FD 为 3.091430e-10。两侧 moment 的 k=0..5 最大误差为 6.161292e-15，k=6..8 则保存了 6.050333e-01, 1.005236e+00, 8.240530e-01。不将更高阶未精确匹配或 bound ratio 当作通过身份检查的精度误差。

## 失败、重试与成本

本地保留七轮，包含 5 次失败 occurrence；最新同名测试全部 PASS。它们是历史实现/接口失败，不能从成本或证据中删除。

| 本地 attempt | 保存状态与通过数 | inclusive CPU 秒 | wall 秒 |
|---|---|---:|---:|
| [attempt_001](../results/tests/attempt_001/receipt.json) | FAIL 21/23 | 0.438793 | 0.882527 |
| [attempt_002](../results/tests/attempt_002/receipt.json) | FAIL 23/24 | 0.426790 | 0.657069 |
| [attempt_003](../results/tests/attempt_003/receipt.json) | FAIL 24/25 | 0.392014 | 0.397352 |
| [attempt_004](../results/tests/attempt_004/receipt.json) | PASS 26/26 | 0.398751 | 0.403717 |
| [attempt_005](../results/tests/attempt_005/receipt.json) | PASS 26/26 | 0.399274 | 0.404775 |
| [attempt_006](../results/tests/attempt_006/receipt.json) | FAIL 25/26 | 0.410364 | 0.395776 |
| [attempt_007](../results/tests/attempt_007/receipt.json) | PASS 26/26 | 0.403322 | 0.436853 |

| 历史失败 | 测试及保存的末行信息 |
|---|---|
| attempt_001 ERROR | test_constrained_chart_quadratic_KKT_and_full_gap_bound：   File "/Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A20/opm-imaging-route-a/src/a20/material.py", line 106, in _solve_quadratic     raise error a20.material.QPFailure: Constrained QP did not meet registered KKT/feasibility tolerance |
| attempt_001 FAIL | test_full_tangent_and_adjoint_refuse_wrong_material_state： subtest failure; see retained suite |
| attempt_002 ERROR | test_constrained_chart_quadratic_KKT_and_full_gap_bound：   File "/Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A20/opm-imaging-route-a/src/a20/material.py", line 106, in _solve_quadratic     raise error a20.material.QPFailure: Constrained QP did not meet registered KKT/feasibility tolerance |
| attempt_003 FAIL | test_full_physics_contract_refuses_native_and_adapter_reduced_states： subtest failure; see retained suite |
| attempt_006 ERROR | test_seed_zero_budgets_and_zero_deflated_blocks：     coeff = self.projection.solve(b.transpose(1, 0, 2).reshape(self.projection.Z.shape[1], -1))                                   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ValueError: cannot reshape array of size 0 into shape (0,newaxis) |

KKT 历史 failure 保存了 SLSQP success=true 但 kkt_relative=4.118801e-08 的结果。最新保存解使用同目标的 validated active equations polish，chart KKT=7.260671e-17；这里仅转录结果，不重新裁决算法。

| 原尺寸 job | 保存状态 | charged CPU 秒 | GPU occupation 秒 | 测量口径 |
|---|---|---:|---:|---|
| [g0-real-01](../results/jobs/g0-real-01/job_receipt.json) | FAILED_LAUNCH / result FAILED_LAUNCH | 501.975000 | 501.975000 | conservative charged allowance from PID-file creation until verified ended; no process receipt exists |
| [g0-real-02](../results/jobs/g0-real-02/job_receipt.json) | COMPLETE / result PASS | 171.906250 | 185.846899 | recorded CLI inclusive process CPU and job GPU occupancy |

g0-real-01 没有 Python/physics manifest，保存的 scientific_status 为 NOT_RUN；其 501.975 秒 CPU 与 GPU 都是保守计费 allowance，不能冒称精确实测。g0-real-02 为随后保留旧成本的新 job。

本地全部尝试累计 CPU 2.869308 秒；独立 algebra job CPU 0.139742 秒。上述测试与 G0 jobs 的列举账单合计 CPU 676.890300 秒，其中包含 failed-launch allowance。此数不是整个 A20 campaign 总账；不得再叠加 prior_cpu 或嵌套 case/row spans。

## 明确缺口

- Original-size G0 covers only parents 2001/2005 at iteration 0 and k=2. It does not record six-parent imaging, all 12 replay states, nonlinear quality or deployment speed.
- Two-frequency coverage uses tiny synthetic observations and real DenseDDA kernels at k=.9/1.25, with explicit stack and summed pullback. No production multifrequency driver or real multifrequency dataset has a saved G0 test.
- Original-size G0 has no named moving-LS residual-term, empty Z, forced unsafe core, gauge rotation, negative-cache, owner-refusal, forced budget-boundary or KKT check. The relevant saved evidence is tiny tests, mapped individually above.
- Known-boundary chart p=6 and voxel p=16 KKT checks are tiny. No original-size voxel quadratic/KKT result is present in these G0 receipts.
- Non-diagonal real whitening is a tiny constructed map. Real data uses measured-data norm normalization; no calibrated noise covariance claim.
- Tiny field/capability and NPZ whitelist rejection checks exist. They are not a proof of OS-level file isolation or arbitrary malicious source-code access prevention.
- The original-size manifest labels historically_exposed_feasibility; these are not a newly blind holdout.
- Current test line locations are an inventory of present test source. Local attempt receipts record commands/env but no immutable test/source revision stamp. The CUDA job has a declared source_commit. No new content-hash check was performed.

可逐项读取 [机器清单](../results/tests/G0_EVIDENCE_INVENTORY.json)、[本地报告](../results/tests/G0_LOCAL.json)、[代数报告](../results/G0_ALGEBRA.json)、[原尺寸报告](../results/G0_REAL.json) 与 [本次整理 CPU 回执](../results/tests/G0_EVIDENCE_INVENTORY_RECEIPT.json)。此页及 JSON 没有新增物理、测试、SSH、hash 或 gate judgment。

## 后续离线 gate 回归

在上述 G0 证据形成后，另执行五项无物理 reference-completeness 回归，均 PASS（`results/tests/REFERENCE_GATE_REGRESSION.json`）。它们检查缺参考与真实 QP 失败同时出现时的 HOLD/FAIL 区分，以及重复、缺 state 的拒绝；不增加原26项物理/代数 suite的历史计数，不替代原尺寸 voxel KKT 验证。当前复现 runner 默认发现所有 `test_*.py`，因此新拷贝还会发现这五项检查。
