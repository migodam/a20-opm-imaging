# A22-R1 — 完整GPT阅读入口

结论：**CASE C — A2与A3相当。** 本文整合冻结协议、真实结果、失败记录与证据边界；不重新定义理论或门槛。

科学交付commit：`f6e904800b57c31aa9a047222d37ae60f00fe322`。公开分支：[a22-r1-subspace-separation](https://github.com/migodam/a20-opm-imaging/tree/a22-r1-subspace-separation)。

该筛查只有四个历史暴露scene；不可把2112 cases当独立对象。Full-J只作离线诊断，NN与扩展NOT_RUN。

---

原文件：[A22_R1_START_HERE.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/A22_R1_START_HERE.md)

# A22-R1 直接 physics/prior 分离实验

**裁决：CASE_C_A2_MATCHES_OR_BEATS_A3。** 在本筛查中，A2达到相对分离筛查阈值，而A3没有达到预注册15%的增量；不能把O/P/M标签宣称为构造该split所必需。停止NN，保留更简单的物理编码对照。

本实验只检验已知背景 `0.1+0.04i` 下、固定32维质量归一材料图中的分离。四个对象全部历史暴露；2001/2003是Gaussian，2014为非Gaussian/asymmetric分段材料，2009为多尺度shell。统计单位只有四个scene，不能把2112个noise/方向案例作为独立对象。没有NN、nonlinear GN/DBIM、新标签、rank/degree搜索或自动扩展。

主k=16的A3：S_sep场景中位数 **3.3994**，q_phys **0.354249**，q_prior **3.43921**，truth_phys **0.740968**。相对A2的等场景平均physics NRMSE改善 **0**；2000次四scene配对bootstrap区间 `[0.0, 2.220446049250313e-16]`。S1/S2/S3/S4：`{'S1': 'SUPPORT', 'S3': 'SUPPORT', 'S4': 'SUPPORT', 'S2': 'FAIL'}`。这些是screening SUPPORT/FAIL，没有formal PASS。

physics NRMSE中位数仍为 **0.535099**；相对分离不等于低绝对误差，不能据此宣称物理分支已经可靠成像。A2/A3在主k16是否选取相同候选集合：`True`，详见[projector audit](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/SPLIT_PROJECTOR_EQUALITY.csv)。若集合相同，零增量是同一投影的结果，不是四scene上的一般无效性证明。

| 方法 | physics NRMSE均值 | prior NRMSE均值 | S_sep中位数 | q_phys中位数 | q_prior中位数 | truth_phys中位数 |
|---|---:|---:|---:|---:|---:|---:|
| RANDOM | 0.995677 | 1.35788 | 2.14261 | 0.597327 | 2.41554 | 0.742074 |
| A1 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| A2 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| A3 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| FULL-J（仅离线） | 0.574034 | 1.66618 | 2.88516 | 0.425535 | 3.0886 | 0.741394 |

旧标量严格复现仍为FAILED：Mac104/2112、原Windows26/2112不匹配。Test A/B使用整组Windows共同向量，先重验同一个缓存quadratic、可行域、保存normal及原KKT；2112/2112有效。选择平台与这项处理在查看split结果前登记。参见[显式补充](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/REPRODUCTION_CONFLICT_ADDENDUM.md)和[source audit](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/research/delegated/a22-r1-cache-audit/PLATFORM_REPRODUCTION_AUDIT.md)。不能把本报告称为bitwise旧Stage A复现。

## 阅读顺序

1. [冻结协议](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/SUBSPACE_SEPARATION_PROTOCOL.md)及[split来源](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/SPLIT_DEFINITION_AUDIT.md)
2. [共同解误差定位](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/ONE_SHOT_ERROR_LOCALIZATION.md)
3. [真实受限分支](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/RESTRICTED_PHYSICS_BRANCH.md)
4. [图外能量](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/CHART_EXTERIOR_AUDIT.md)
5. [机器判决](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/GATE_DECISION.json)、[四scene指标](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/PER_SCENE_SPLIT_METRICS.csv)、[方法比较](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/SPLIT_COMPARISON.csv)
6. [费用](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/COST_SUMMARY.json)、[失败账本](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/FAILURE_LEDGER.jsonl)、[原始输出入口](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/REPLAY_SUMMARY.json)

## 证据边界

原理论包已经给出的是条件性的线性recoverability/attribution论证；本实验不重做理论。单元与identity tests验证实现，不能代替Maxwell实验。真实Maxwell证据来自既有32个clean有限幅度label与四个付费背景重建。full-J只在在线split全部冻结之后用于OFFLINE诊断。可部署证据仅限已知背景的缓存OPM及一次受约束材料解，未测未知背景或真正端到端time-to-image；rank32不构成部署加速。

保存2112个共同32D向量、21120个受限向量和42240条split指标。四个背景重建不可避免，因为旧缓存缺y0与完整descriptor映射；新full-wave label数为0，cache replay物理调用为0。费用以[COST_LEDGER](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/COST_LEDGER.jsonl)唯一inclusive receipts为准，失败/重跑没有删除，nested actions不重复加账。历史A22账本保持冻结。

## 图和复现

图A–F的PNG/SVG及原始数据在[figures](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/figures/A22_R1/PLOT_MANIFEST.json)。缓存入口、参数、seeds、source记录在[SOURCE_AND_COMMAND_MANIFEST](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/SOURCE_AND_COMMAND_MANIFEST.json)。运行 `PYTHONPATH=src python -B -m a22_r1.cli report --job a22-r1-report-NEW` 重新汇总现有缓存；不要重跑freeze或生成label。新的job名称必须唯一。

原始科学交付为本地。2026-10-08应用户“每一次都要网页链接”要求补齐独立公开分支；发布状态另见[发布回执](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/PUBLICATION_RECORD.json)。不扩展场景、不启动NN或下一阶段。冻结gate中的LOCAL_ONLY保留为当时历史状态。

计时细分见[CACHED_ONE_SHOT_RUNTIME](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/CACHED_ONE_SHOT_RUNTIME.md)；缓存kernel不能当完整部署加速。

## 本地代码与压缩证据

实现代码commit：`41194f4d5d0eb472f4785a81c4cd2467cc4581d7`。大型逐case原始记录保留在本地；Git保存其字节一致的gzip副本，完整向量另有NPZ。路径与实际字节数见[DELIVERY_MANIFEST](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/DELIVERY_MANIFEST.json)。report入口可以直接读gzip缓存。

---

原文件：[SUBSPACE_SEPARATION_PROTOCOL.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/SUBSPACE_SEPARATION_PROTOCOL.md)

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

---

原文件：[SPLIT_DEFINITION_AUDIT.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/SPLIT_DEFINITION_AUDIT.md)

# Split definition / information audit

所有方法都在原 `online_split_16.npz` 中 `[V_phys,V_prior]` 的有符号、完整32列基底上选列。材料W/体积metric、六源逐源Re/Im packing、known background、whitening与lambda固定。RANDOM用单个固定排列，k8/k16嵌套；没有dense k sweep。

A1/A2/A3原公式、原预算和descriptor不变。旧缓存没有32方向预算，因此只补全同一个候选池；冻结排序条件是amplitude0/noise1/nominal，不据恢复误差定条件、不拟合校准器。raw预算越小排名越前，按candidate index稳定打破并列。声明的有限材料prior半径仍在预算中，不能称为零先验测试。

在线builder只能读取已知几何/背景、合法测量/配置及OPM因子，拒读truth、full-J/H、full gradient、GN optimum、teacher。此处split不依据truth或full32恢复输出。全局online freeze后才读取旧label和fullJ到独立offline evaluator。OFFLINE_FULL_J以full-J regularized witness预算对同一32候选排序，明确不是deployable。没有为fullJ再生成任何数据。

完整indices、raw scores、scope、随机种子与cache来源在[SPLIT_FREEZE](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/SPLIT_FREEZE.json)、[OFFLINE freeze](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/OFFLINE_SPLIT_FREEZE.json)及相应NPZ。Window/Mac的offline浮点平台变体单独保留在platform_variants，不覆盖冻结online split。需要按候选frame限制解释结果，不能将OFFLINE诊断等同任意优化LIS。

Test A先读取整组固定共同解；Test B保持同一个物理目标/原lambda，仅限制解空间。拒读、预算、packing、noise方差1/2、零分母、QP失败与旧源码不变均有测试。任何正规新验证/训练要重新审计数据边界，本experiment不自动执行。

严格历史标量复现失败保留；explicit处理见[REPRODUCTION_CONFLICT_ADDENDUM](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/REPRODUCTION_CONFLICT_ADDENDUM.md)，在split指标之前提交，S1–S4与评分完全未改。

---

原文件：[ONE_SHOT_ERROR_LOCALIZATION.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/ONE_SHOT_ERROR_LOCALIZATION.md)

# One-shot共同解误差定位

**CASE_C_A2_MATCHES_OR_BEATS_A3。** 在本筛查中，A2达到相对分离筛查阈值，而A3没有达到预注册15%的增量；不能把O/P/M标签宣称为构造该split所必需。停止NN，保留更简单的物理编码对照。

本实验只检验已知背景 `0.1+0.04i` 下、固定32维质量归一材料图中的分离。四个对象全部历史暴露；2001/2003是Gaussian，2014为非Gaussian/asymmetric分段材料，2009为多尺度shell。统计单位只有四个scene，不能把2112个noise/方向案例作为独立对象。没有NN、nonlinear GN/DBIM、新标签、rank/degree搜索或自动扩展。

NRMSE使用投影真值范数，floor为1e-6并单独标记；q和能量比例使用原始能量，不加epsilon。S_sep是prior/physics NRMSE；q_phys<1表示物理子空间的误差份额低于信号份额，q_prior>1相反。逐case的S_sep²=q_prior/q_phys（floor不激活时）成立；逐scene平均后不能再对这些均值强行套同一等式。所有图内误差均与图外真值分开。

## Test A主比较，k=16

| 方法 | physics NRMSE均值 | prior NRMSE均值 | S_sep中位数 | q_phys中位数 | q_prior中位数 | truth_phys中位数 |
|---|---:|---:|---:|---:|---:|---:|
| RANDOM | 0.995677 | 1.35788 | 2.14261 | 0.597327 | 2.41554 | 0.742074 |
| A1 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| A2 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| A3 | 0.524722 | 1.79817 | 3.3994 | 0.354249 | 3.43921 | 0.740968 |
| FULL-J（仅离线） | 0.574034 | 1.66618 | 2.88516 | 0.425535 | 3.0886 | 0.741394 |

每case共同32D解只算一次，所有方法投影相同误差；不按方法换optimizer。noise draws先平均，再等权平均每scene的48个方向×幅度×noise×intervention条件。k8仅作固定稳健性检查，不选k。完整绝对误差、分母、fraction、floor和identity residual保存在原始JSONL。

| scene | 方法 | physics NRMSE | prior NRMSE | S_sep | q_phys | q_prior | truth_phys |
|---|---|---:|---:|---:|---:|---:|---:|
| 2001 | RANDOM | 0.517756 | 1.03975 | 2.02671 | 0.614221 | 2.50671 | 0.773226 |
| 2001 | A1 | 0.468869 | 1.30251 | 2.8828 | 0.514415 | 3.98843 | 0.845067 |
| 2001 | A2 | 0.468869 | 1.30251 | 2.8828 | 0.514415 | 3.98843 | 0.845067 |
| 2001 | A3 | 0.468869 | 1.30251 | 2.8828 | 0.514415 | 3.98843 | 0.845067 |
| 2001 | OFFLINE_FULL_J | 0.468869 | 1.30251 | 2.8828 | 0.514415 | 3.98843 | 0.845067 |
| 2003 | RANDOM | 0.643979 | 1.56776 | 2.44782 | 0.580433 | 3.46424 | 0.852799 |
| 2003 | A1 | 0.653623 | 2.05238 | 3.14159 | 0.599871 | 5.89915 | 0.924243 |
| 2003 | A2 | 0.653623 | 2.05238 | 3.14159 | 0.599871 | 5.89915 | 0.924243 |
| 2003 | A3 | 0.653623 | 2.05238 | 3.14159 | 0.599871 | 5.89915 | 0.924243 |
| 2003 | OFFLINE_FULL_J | 0.594459 | 1.50811 | 2.54639 | 0.494648 | 3.20467 | 0.810652 |
| 2014 | RANDOM | 1.87751 | 0.721918 | 0.398218 | 3.38375 | 0.480042 | 0.228403 |
| 2014 | A1 | 0.375069 | 1.67136 | 4.74373 | 0.125781 | 2.88999 | 0.604451 |
| 2014 | A2 | 0.375069 | 1.67136 | 4.74373 | 0.125781 | 2.88999 | 0.604451 |
| 2014 | A3 | 0.375069 | 1.67136 | 4.74373 | 0.125781 | 2.88999 | 0.604451 |
| 2014 | OFFLINE_FULL_J | 0.63148 | 1.68767 | 2.88752 | 0.356422 | 2.97253 | 0.672137 |
| 2009 | RANDOM | 0.943468 | 2.1021 | 2.25851 | 0.462782 | 2.32438 | 0.710921 |
| 2009 | A1 | 0.601328 | 2.16642 | 3.65722 | 0.194084 | 2.44846 | 0.636868 |
| 2009 | A2 | 0.601328 | 2.16642 | 3.65722 | 0.194084 | 2.44846 | 0.636868 |
| 2009 | A3 | 0.601328 | 2.16642 | 3.65722 | 0.194084 | 2.44846 | 0.636868 |
| 2009 | OFFLINE_FULL_J | 0.601328 | 2.16642 | 3.65722 | 0.194084 | 2.44846 | 0.636868 |

## A2/A3配对

| scene | A2 physics NRMSE | A3 physics NRMSE | A3相对改善 |
|---|---:|---:|---:|
| 2001 | 0.468869 | 0.468869 | 0 |
| 2003 | 0.653623 | 0.653623 | 0 |
| 2014 | 0.375069 | 0.375069 | 1.11022e-16 |
| 2009 | 0.601328 | 0.601328 | 0 |

主要点估计 `1-mean_scene(A3 NRMSEphys)/mean_scene(A2 NRMSEphys)=0`；四scene配对bootstrap95%区间 `[0.0, 2.220446049250313e-16]`。不是在2112案例上bootstrap。阈值15%不因区间或家族结果放宽。

冻结A2/A3在主k16的候选集合相同：`True`。逐scene/k的index、Jaccard和projector差在[SPLIT_PROJECTOR_EQUALITY](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/SPLIT_PROJECTOR_EQUALITY.csv)。排序顺序可不同，但Test A的子空间projector相同；bootstrap中的machine-level零差不能当作独立新场景上的等效性证明。当前有限幅度、噪声与校准条件下physics NRMSE绝对值仍较大。

旧标量严格复现仍为FAILED：Mac104/2112、原Windows26/2112不匹配。Test A/B使用整组Windows共同向量，先重验同一个缓存quadratic、可行域、保存normal及原KKT；2112/2112有效。选择平台与这项处理在查看split结果前登记。参见[显式补充](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/REPRODUCTION_CONFLICT_ADDENDUM.md)和[source audit](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/research/delegated/a22-r1-cache-audit/PLATFORM_REPRODUCTION_AUDIT.md)。不能把本报告称为bitwise旧Stage A复现。

## 限制

S_sep很大仍可能是两侧都不准确，必须与绝对NRMSE、q、signal coverage及Test B同时读。full-J按固定候选方向的regularized witness预算排序，不是按真值择优，也未旋转成一个任意最优LIS；其失败不能证明所有hard splits均不可能。图外材料属于chart-exterior，绝不作为图内V_prior失败。

---

原文件：[RESTRICTED_PHYSICS_BRANCH.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/RESTRICTED_PHYSICS_BRANCH.md)

# 受限physics-only分支

**CASE_C_A2_MATCHES_OR_BEATS_A3；NN与扩展仍为NOT_RUN。**

Test B对每个冻结split直接解 `min ||d-AW V_phys a||² + lambda||a||²`，`V_prior=0`。每方法显式使用原full-scene lambda，而不是重新由restricted A定标。Gaussian/voxel像素可行域仍由原32D mass chart映射：Re chi>=-0.5、Im chi>=0；original solver/SLSQP、exact redundant-row compression、active-equation检查、feasibility/KKT阈值保持原样。无post clipping、jitter、pinv或Maxwell fallback。

21120个受限QP，invalid `0`。原solver在active-KKT解上发出ill-conditioned matrix警告；不隐瞒，不改solver。所有返回的点仍通过原最终合同，详细结果见[NUMERICAL_AUDIT](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/NUMERICAL_AUDIT.json)及每case QP字段。

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

线性白化data residual、small-solve measured wall/CPU、prior coefficient leakage在[RESTRICTED_BRANCH_RUNTIME_AND_DATA.csv](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/RESTRICTED_BRANCH_RUNTIME_AND_DATA.csv)。完整nonlinear residual为NOT_RUN，未启动任何new nonlinear solve。受限分支在Mac上执行，common archive来自原Windows；差异及阈值保留见[补充](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/REPRODUCTION_CONFLICT_ADDENDUM.md)。

计时细分见[CACHED_ONE_SHOT_RUNTIME](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/CACHED_ONE_SHOT_RUNTIME.md)；缓存kernel不能当完整部署加速。

---

原文件：[CHART_EXTERIOR_AUDIT.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/CHART_EXTERIOR_AUDIT.md)

# Chart-exterior audit

材料扰动严格分成 `chi-chi0 = W x + chi_outside_W`。W是固定质量正交32维实chart；本实验中的V_prior只是W内部的补空间，不包含chi_outside_W。

| scene | 原对象图内能量 | 原对象图外能量 | 有限幅度案例图内能量范围 |
|---|---:|---:|---|
| 2001 | 0.46491 | 0.53509 | 0.437996 – 0.664334 |
| 2003 | 0.489802 | 0.510198 | 0.486287 – 0.524213 |
| 2014 | 0.0576533 | 0.942347 | 0.0590951 – 0.169029 |
| 2009 | 0.133728 | 0.866272 | 0.134163 – 0.178295 |

这些比例是原对象相对已知背景的material energy，不是重建成功率。finite cases继承原材料并加W内扰动，因此覆盖会变化，但图外部分保持原样。audit共有4个原对象+32个finite labels，projection、orthogonality和能量identity一致。原始值见[CHART_EXTERIOR_RAW.csv](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/CHART_EXTERIOR_RAW.csv)及[JSON](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/CHART_EXTERIOR_RAW.json)。

完整finite材料向量未独立保存；这里按已保存的original_material与perturbation_coefficients生成规则核验，没有声称这是独立新full-wave证据。它只隔离已有chart外误差，不对图内split提供额外评分或使用truth选方向。

已有full-wave data仍包含原对象的chart-exterior材料。把它的能量排除出V_prior指标，不能消除它对测量和图内恢复的散射影响；这里没有生成W-only新labels来隔离这种污染。因此结果属于实际既有有限幅度/噪声/校准条件下的图内恢复，不是消除了所有图外nuisance的内在可识别性定理。

Gaussian chart只覆盖约46–49%，2014约5.8%，shell约13.4%；即使一个图内split有效也不能据此宣称完整原对象成像有效。图外能量不能被算作V_prior失败，任何完整图像主张需另行扩展材料chart并独立验证；本experiment不自动做这件事。

---

原文件：[REPRODUCTION_CONFLICT_ADDENDUM.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/REPRODUCTION_CONFLICT_ADDENDUM.md)

# 缓存共同 QP 的复现冲突与显式处理

这项补充在任何 Test A split 指标或 Test B 受限解生成前登记。原 `SUBSPACE_SEPARATION_PROTOCOL.md`、配置、两次失败及其阈值完整保留，不把严格标量复现改判为通过。

## 发生了什么

Mac 的 2112 个共同解全部通过原 QP/KKT 合同，但 104 个案例超出冻结的旧标量复现容差。原 Windows/Python/NumPy/SciPy 环境复算后，2112 个解仍全部通过原合同，26 个案例超出该容差；最大完整材料误差差值为 `1.631117072381505e-7`，target coefficient 差值为零。两次均在 Test B 之前停止。缓存 AW 的元素与 NPY 布局相同，正则化公式及源代码保持不变。

小规模探针显示，完全相同 AW 元素的不同内存布局可以改变原 SLSQP 的迭代停止点；部分点的原/新 defect 都在原 `1e-8` KKT 门槛内，而标量差大于 `1e-8`。这不能证明旧与新目标不同，也不能证明所有差异已被唯一解释。旧 Stage A 没有保存全向量、完整 in-memory arithmetic 或梯度，因此不能复原旧停止点。

## 冻结处理

1. **严格历史标量复现仍为 FAILED。** 旧记录不覆盖，失败成本不删除。
2. 直接子空间实验只使用原 Windows 的整组共同解，路径固定为 `results/a22_r1/replay/20261007T164205Z_d1452c27461b/COMMON_32D_CASES.jsonl`。不逐案例挑平台、挑最小误差或再求共同解。
3. 在 Test A/B 前重新用缓存 AW/data、原 full-scene lambda、原约束及保存的 normal，检查每个共同解的 quadratic、可行性、stationarity 与原 KKT 合同。任一个不合法即停止；**不放宽 KKT、feasibility、score 或物理阈值**。
4. Test A 投影上述同一个共同解；Test B 用原 solver、同一个 lambda 和同一个可行域求受限解，Mac 平台单独注明。在线 split 和主 k/gates 不变。
5. 两个平台共同解都保留。报告明确区分“直接子空间诊断结果”与“历史标量严格重现失败”。此处理不能作为 bitwise Stage A 复现或正式独立验证的证据。

这是对额外实现复现检查与原求解容差之间冲突的显式处理，不是对科学筛选 S1–S4 的结果后修改。没有新的 full-wave label、Maxwell run、NN、排名校准、rank/degree 增加、fallback 或 nonlinear solve。

---

原文件：[CACHED_ONE_SHOT_RUNTIME.md](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/CACHED_ONE_SHOT_RUNTIME.md)

# 缓存one-shot时间记录

四个固定第一案例（direction0/amplitude0/noiseless/nominal），每个合法方法只计时一次，没有按耗时挑样本或增加repeat。这里只评估CPU缓存kernel，不是部署加速证据；主误差向量和S1–S4未改。

| 方法 | split中位耗时(ms) | 小QP中位耗时(ms) | 缓存读入+kernel中位耗时(ms) |
|---|---:|---:|---:|
| COMMON_32D | 0.0004 | 13.367 | 20.274 |
| RANDOM | 0.0424 | 3.896 | 10.890 |
| A1 | 0.0052 | 3.495 | 10.460 |
| A2 | 0.0046 | 3.460 | 10.425 |
| A3 | 0.0046 | 3.398 | 10.363 |

共享NPZ/cache读入只实际计费一次；独立归因的total列为每方法加回该实测读入，不能把该列横向相加当实际耗时。OS cache未flush，未核验cold deployment、noise编码、Q/descriptor重新构建或状态求解的端到端可比时间。离线full-J没有runtime claim。

本次OPM构建已有真实四scene收费记录（[online scene receipts](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/online/scene_2001.json)与其他scene同目录）：单scene原OPM构建约1.5–1.8秒，另外付费背景geometry/full forward、descriptor/identity等记录在各receipt中。核查构建仍rank32，没有新增full-wave label。不能拿上表的毫秒kernel当完整time-to-image。

cache replay完整网格wall为70.314607秒，含2112个common point验证、21120个受限解、42240条metrics及输出开销；它不是单个独立在线图像的部署耗时。所有失败/重跑/计时/审核都在[COST_LEDGER](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/COST_LEDGER.jsonl)，runtime额外20个小QP独立记录，不替换primary image。

原始测量：[CACHED_ONE_SHOT_RUNTIME.csv](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/CACHED_ONE_SHOT_RUNTIME.csv)；[summary](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/results/a22_r1/CACHED_ONE_SHOT_RUNTIME.json)。full-operator speedup / Gate T：NOT_ESTABLISHED。

---

## 冻结机器判决

```json
{
  "schema": "a22_r1.gates.v1",
  "status": "SCREENING_ONLY",
  "scientific_case": "CASE_C_A2_MATCHES_OR_BEATS_A3",
  "interpretation": "The frozen O/P/M labels do not add the required practical value over generic reduced recoverability.",
  "gates": {
    "S1": "SUPPORT",
    "S3": "SUPPORT",
    "S4": "SUPPORT",
    "S2": "FAIL"
  },
  "methods": {
    "RANDOM": {
      "method": "RANDOM",
      "k": 16,
      "Test_A_complete": true,
      "Test_B_complete": true,
      "Test_A_scene_medians": {
        "nrmse_phys": 0.7937234423036861,
        "nrmse_prior": 1.303754249112201,
        "s_sep": 2.142611944720552,
        "f_error_prior": 0.515242714714435,
        "f_truth_phys": 0.7420735714505924,
        "q_phys": 0.5973271522613572,
        "q_prior": 2.415542150111391
      },
      "restricted_over_common_scene_ratios": {
        "2001": 1.1578827685959805,
        "2003": 1.176338662935929,
        "2014": 1.08115629922133,
        "2009": 0.7030379847849701
      },
      "median_restricted_over_common": 1.1195195339086552,
      "S1": "SUPPORT",
      "S3": "SUPPORT",
      "S4": "SUPPORT",
      "useful_screening_split": true
    },
    "A1": {
      "method": "A1",
      "k": 16,
      "Test_A_complete": true,
      "Test_B_complete": true,
      "Test_A_scene_medians": {
        "nrmse_phys": 0.5350985948541005,
        "nrmse_prior": 1.8618704868458027,
        "s_sep": 3.399403242542215,
        "f_error_prior": 0.7223329225092681,
        "f_truth_phys": 0.740967592031865,
        "q_phys": 0.354249461266858,
        "q_prior": 3.439209632143813
      },
      "restricted_over_common_scene_ratios": {
        "2001": 0.9656790554525796,
        "2003": 1.0344078997473272,
        "2014": 1.0069556186927664,
        "2009": 0.8862702126968959
      },
      "median_restricted_over_common": 0.986317337072673,
      "S1": "SUPPORT",
      "S3": "SUPPORT",
      "S4": "SUPPORT",
      "useful_screening_split": true
    },
    "A2": {
      "method": "A2",
      "k": 16,
      "Test_A_complete": true,
      "Test_B_complete": true,
      "Test_A_scene_medians": {
        "nrmse_phys": 0.5350985948541005,
        "nrmse_prior": 1.8618704868458027,
        "s_sep": 3.399403242542215,
        "f_error_prior": 0.7223329225092681,
        "f_truth_phys": 0.740967592031865,
        "q_phys": 0.354249461266858,
        "q_prior": 3.439209632143813
      },
      "restricted_over_common_scene_ratios": {
        "2001": 0.9656790556611635,
        "2003": 1.0344078993461023,
        "2014": 1.0069556186927664,
        "2009": 0.8862702126266544
      },
      "median_restricted_over_common": 0.9863173371769649,
      "S1": "SUPPORT",
      "S3": "SUPPORT",
      "S4": "SUPPORT",
      "useful_screening_split": true
    },
    "A3": {
      "method": "A3",
      "k": 16,
      "Test_A_complete": true,
      "Test_B_complete": true,
      "Test_A_scene_medians": {
        "nrmse_phys": 0.5350985948541005,
        "nrmse_prior": 1.8618704868458027,
        "s_sep": 3.399403242542215,
        "f_error_prior": 0.7223329225092681,
        "f_truth_phys": 0.740967592031865,
        "q_phys": 0.354249461266858,
        "q_prior": 3.439209632143813
      },
      "restricted_over_common_scene_ratios": {
        "2001": 0.9656790555590847,
        "2003": 1.0344078996785577,
        "2014": 1.0069556186927664,
        "2009": 0.8862702125437711
      },
      "median_restricted_over_common": 0.9863173371259255,
      "S1": "SUPPORT",
      "S3": "SUPPORT",
      "S4": "SUPPORT",
      "useful_screening_split": true
    },
    "OFFLINE_FULL_J": {
      "method": "OFFLINE_FULL_J",
      "k": 16,
      "Test_A_complete": true,
      "Test_B_complete": true,
      "Test_A_scene_medians": {
        "nrmse_phys": 0.597893602878006,
        "nrmse_prior": 1.5978867144598285,
        "s_sep": 2.885161773164179,
        "f_error_prior": 0.6820018916420674,
        "f_truth_phys": 0.7413944110263825,
        "q_phys": 0.4255349981745455,
        "q_prior": 3.0886014649091376
      },
      "restricted_over_common_scene_ratios": {
        "2001": 0.9656790556935496,
        "2003": 0.9758529324630265,
        "2014": 0.9944692757176388,
        "2009": 0.8862702125664442
      },
      "median_restricted_over_common": 0.970765994078288,
      "S1": "SUPPORT",
      "S3": "SUPPORT",
      "S4": "SUPPORT",
      "useful_screening_split": true
    }
  },
  "bootstrap": {
    "resampling_unit": "scene",
    "expected_scene_cluster_count": 4,
    "scene_cluster_count": 4,
    "missing_scene_cluster_count": 0,
    "excess_scene_cluster_count": 0,
    "scene_ids": [
      2001,
      2003,
      2014,
      2009
    ],
    "n_resamples": 2000,
    "seed": 20261911,
    "confidence_level": 0.95,
    "interval_kind": "paired scene percentile bootstrap",
    "complete": true,
    "missing_a3_scene_count": 0,
    "missing_a2_scene_count": 0,
    "missing_paired_scene_count": 0,
    "missing_a3_scenes": [],
    "missing_a2_scenes": [],
    "mean_a3": 0.52472224435779,
    "mean_a2": 0.52472224435779,
    "mean_difference": 0.0,
    "relative_improvement_of_means": 0.0,
    "mean_paired_relative_improvement": 2.7755575615628914e-17,
    "median_paired_relative_improvement": 0.0,
    "mean_difference_ci95": [
      0.0,
      1.1102230246251565e-16
    ],
    "relative_improvement_of_means_ci95": [
      0.0,
      2.220446049250313e-16
    ],
    "undefined_relative_bootstrap_count": 0
  },
  "equal_scene_mean_A3_improvement_vs_A2": 0.0,
  "numerical_complete": true,
  "numerical_identity_unit_tests": "SEPARATE_EVIDENCE",
  "independent_scene_clusters": 4,
  "scenes": [
    2001,
    2003,
    2014,
    2009
  ],
  "historical_exposed": true,
  "primary_k": 16,
  "secondary_k": 8,
  "formal_validation": "NOT_RUN",
  "formal_PASS": false,
  "historical_scalar_reproduction": "FAILED_RETAINED_WITH_EXPLICIT_PRE_OUTCOME_ADDENDUM",
  "NN": "NOT_RUN",
  "expansion": "NOT_RUN",
  "nonlinear_reconstruction": "NOT_RUN",
  "deployment_acceleration": "NOT_ESTABLISHED",
  "publication": "LOCAL_ONLY",
  "next_action": "STOP_AND_REPORT",
  "raw_cases": 2112,
  "metric_rows": 42240,
  "restricted_solves": 21120,
  "invalid_restricted_QPs": 0,
  "NRMSE_floor_rows": 0,
  "frozen_QP_validation": {
    "feasibility_violation": 7.632783294297951e-16,
    "kkt_relative": 9.751508680986546e-09,
    "normal_cone_relative": 2.657940278647355e-16,
    "quadratic_relative_difference": 2.1345755180595088e-15
  },
  "explicit_protocol_conflict": "REPRODUCTION_CONFLICT_ADDENDUM.md",
  "primary_A2_A3_same_selected_index_sets": true
}
```

## 图A–F

图及原始绘图数据：[清单](https://github.com/migodam/a20-opm-imaging/blob/a22-r1-subspace-separation/figures/A22_R1/PLOT_MANIFEST.json)。

![A](https://raw.githubusercontent.com/migodam/a20-opm-imaging/a22-r1-subspace-separation/figures/A22_R1/A.png)

![B](https://raw.githubusercontent.com/migodam/a20-opm-imaging/a22-r1-subspace-separation/figures/A22_R1/B.png)

![C](https://raw.githubusercontent.com/migodam/a20-opm-imaging/a22-r1-subspace-separation/figures/A22_R1/C.png)

![D](https://raw.githubusercontent.com/migodam/a20-opm-imaging/a22-r1-subspace-separation/figures/A22_R1/D.png)

![E](https://raw.githubusercontent.com/migodam/a20-opm-imaging/a22-r1-subspace-separation/figures/A22_R1/E.png)

![F](https://raw.githubusercontent.com/migodam/a20-opm-imaging/a22-r1-subspace-separation/figures/A22_R1/F.png)
