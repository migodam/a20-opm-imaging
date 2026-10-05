# A20-R1 公式与实现

材料坐标是原保存 chart 中的实坐标。`Q` 满足原体积加权正交关系；实、虚部次序、current 度量和六源白化/packing 全部复用 A20。没有重新计算 chart 或修改 Maxwell 方程。

|物理/数学对象|实现与边界|
|---|---|
|Maxwell 状态、极化率、L/L*、S/S*、B/B*|`src/a20/backend.py`、`vendor/a17/a9_engine.py`，保持 source freeze|
|精确 Schur root K 和反馈 F/F*|`src/a20/opm.py:SchurFeedback`，原定义、方向及门槛|
|独立 O/P/M streams、联合正交化|原 `Hierarchy` / `BlockStream`；R1 仅提供 seed blocks|
|一材料方向的六源 KB block|`src/a20_r1/seeds.py:source_target_block`；六源全部注入，压缩前不得取单源|
|共享合法 probe bank|`paired_probe_bank`：原 M4 后 O4 的 RNG 抽样精确保留，M12 extras 使用独立固定 RNG|
|任务梯度 g_m = J_m^T r + ell|`build_model` 中 fresh `ReducedJacobian.pullback`；付费 FIXED scaffold，task probe 为归一化 −g_m|
|受保护 target block|先对完整六源 block 在 retained U 的补空间正交化，再填剩余 M slots；不补列凑 current rank|
|材料约束二次子问题|原 `src/a20/material.py:solve_quadratic`；lambda、ell、约束和 KKT 1e-8 不变|
|H = J_F^T J_F + lambda I|只在 `anatomy`/闭环 offline evaluator 中取得 FullJacobian；不传入合法 builder|
|relative H-step error|原 `_evaluate_full_step`：sqrt((||J_F(s_m−s_F)||²+lambda||s_m−s_F||²)/(||J_F s_F||²+lambda||s_F||²))|
|full quadratic gap|直接评价受约束二次目标之差；不把它强行等同于一半 H-error energy|
|材料、initial qM 和 final Z capture|平方投影能量比例；零/floor 分母记缺失，不替换成假 coverage|
|闭环 history|`AcceptedHistory` + `OwnPolicy`，只携带同对象/同方法已接受的 alpha×step，含 accepted index|
|真实接受/停止|原 `reconstruct` 的 full-objective Armijo、full-KKT、LM 时序；新增兼容 hooks 的默认行为保留|
|费用/预算|`R1Book` 在原累计账本上叠加 R1 和 Phase1/2 hard caps；失败与离线审核也计费|

合法路径执行时拒绝 `full_forward`、`full_tangent`、`full_adjoint` teacher 调用。A1 的已有 full state 与 full-objective/full-KKT 审核在外部付费；其 full gradient/reference 不进入 seed policy。ORACLE-M 和 PROTECTED-ORACLE 的 reference 参数是显式离线能力，不能进入闭环候选。

冻结快照没有可验证的本算法 accepted history，因此 HISTORY 快照实验是 NOT_RUN。闭环实现从原初始化自然产生 history；只有冻结 A/B/C 通过才允许实际启动。
