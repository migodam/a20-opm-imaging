# A22-R1 冻结实验协议

本实验直接检验固定 32 维材料图中的物理/先验分离，不再拟合方向误差。来源为 A22 commit `4dd4a9fa69d4272f35a6b93d8455f77cb139187b`；原 A22 的 PARTIAL 判决、代码、输入和账本保留。对象顺序固定为 2001、2003、2014、2009，均为历史暴露数据。所有定义在 R1 重建与恢复输出生成前冻结。

## 同一基底与同一评分公式

W 是原体积正交 32 维实材料图。所有 split 共用旧 `online_split_16.npz` 中 `[V_phys,V_prior]` 的完整、有固定符号的 AW-SVD 坐标，不另学基底。A1/A2/A3 对这同一组 32 个方向调用原 `direction_descriptor` 和 `predict_budget`，不改公式、不重新校准。排名使用原 raw coefficient budget，较小为较可靠，稳定以原列号打破并列。

原预测依赖幅度、噪声及 intervention，历史缓存只保存 8 个方向、其中 4 个方向的预算。R1 明确固定排序条件为 **amplitude=0、noise_level=1、nominal**：原声明材料先验半径仍在预算内，没有新增扰动半径。这个选择由已知背景/配置确定，不读取真实材料能量、误差或测量来选 split。原 8 个方向及已保存预算用来核对原实现。适用范围是这一冻结条件；不据恢复结果改排序条件。

RANDOM 用 `SeedSequence([20261910,scene_id])` 的单一排列，取前 k 列，k=8/16 嵌套。OFFLINE_FULL_J 在在线 split 全部冻结后读取旧同背景 JF，对同一方向使用原 full-J regularized witness budget：`h=JF(JF^T JF+lambda I)^-1 v`，`score=sqrt(||h||²+(rho_declared||JF^T h-v||)²)`。它不是可部署方法，也不是按 truth 最优挑选的子空间。

## 缓存缺口及唯一允许的物理工作

原缓存包含 AW、MW、PMW、有限标签、noise seeds、材料系数、冻结约束/regularization，可复用这些数据。完整 32 维解缺失本身不触发 Maxwell 重跑。但缓存没有背景预测 `y0`，不能恢复 `D(d-y0)`；也没有 Q、IR、LH_Q、背景 exciting state 及两侧残差映射，不能由 8 个方向的范数推出完整 A2/A3 排序。局部缓存审计未找到这些量；不能用 projected background 偷换完整背景。

因此最多付费重建 **四个已知均匀背景** 及原 U8/O4/P4/M4 degree1 描述子。先核验原 AW、六源布局、白化、基底与预算；不构造新扰动标签、不调用 truth-state forward。实际 rank 仍必须为32，core/adjoint/feasibility/KKT 门槛不变。模型不一致立即保留失败、停止判决。

## 两个测试

Test A：对每个原案例只求一次原 32 维受约束 one-shot 解，所有 split 投影这同一个误差。Test B：在各 V_phys 中求解，V_prior=0；直接调用原材料 QP，显式传入完整 AW 的原 lambda，避免旧 basis 入口默认重新定标 lambda。没有投影后裁剪、隐藏 ridge、伪逆、full fallback 或 nonlinear reconstruction。QP/KKT 失败保留，不能筛掉后授予通过。

全部 2112 案例按原 noise/calibration/seed 重放。保存完整 common/restricted 系数，并与旧 signed target error、完整材料误差及 target coefficient 核对。容差为 `1e-8*max(1,原量尺度)`，同时保存原始差值与 KKT；这只是小矩阵/平台复算一致性，不重新定义旧数值门槛。

## 指标、统计与门槛

主要 k=16；k=8 只作稳健性检查，不选择最优 k。物理范数为材料质量范数，等于此图中欧氏系数范数。NRMSE 使用原 `1e-6` norm floor并报告触发标记；能量分数/q 的零分母保持 undefined，不能通过 epsilon 变成通过。

先对每个 `(scene,direction,amplitude,noise,intervention)` 的 draws 平均，再等权平均该场景48个条件；最后四场景等权。零噪声的单次 draw 不因低/高噪声各16次而被降权。配对 bootstrap 只重采样四个 scene，2000次，seed20261911；不把2112案例视为独立对象。

- S1：Test A 的场景均值之中位数 `S_sep>=2, q_phys<=0.7, q_prior>=1.3`。
- S2：A3 相对 A2 的等场景平均 NRMSE_phys 改善 `>=15%`。用户给出的替代“正点估计/无明显不利家族”条件只作描述，不用它放宽这个冻结数值入口。
- S3：Test A 场景均值 `f_truth_phys` 中位数 `>=0.35`。
- S4：每景 Test B/Test A 的 NRMSE_phys 均值比，再取中位数 `<=1.25`。

任何病例缺失、QP失败、undefined主指标、严重floor依赖或缓存不一致，均不能制造正式 PASS。四个暴露场景最多产生 screening SUPPORT；不训练 NN、不扩展队列。

W 外真值单独报告，绝不并入图内 V_prior。除 ratio/q 外同时展示绝对 NRMSE，避免把“两边都很差”称为可靠物理重建。只报告原可查构基历史费用、此次重建费用、split/小QP/cached one-shot 时间；不从 rank 宣称部署加速。

## 解释与停止

解释优先级预先固定：A3 全部 screening 条件成立为 CASE A；若 A2 本身支持分离且 A3 未取得15%增量为 CASE C；否则若 OFFLINE split 支持分离而 A3不支持为 CASE B；其余有效完整实验为 CASE D（限定本场景、图与固定候选坐标）。数值无效/缺失时单独保留 INCOMPLETE，不强行给出硬分解死亡结论。

R1 自限 CPU1800秒、GPU相关占用600秒，且旧 A22 GPU1350.71388秒继续计入32400秒总上限。所有验证、失败、重跑、汇总和源代码工作保留费用；source工作保守 allowance单独标识，不伪装为 measured CPU。新 full-wave labels 上限为0，已知背景重建上限为4。完成四场景后停止，本地交付，不自动发布。
