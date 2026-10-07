# A22 源码接口与交付索引

本文件是 2026-10-07 当前源码/config/预注册的普通索引，不判断理论有效性、实验支持程度或 gate。五接口名称保持用户计划。数值公式仅转录当前实现，未新增证明或设计。父线程报告首场景 337 条记录、四场景 screening 未完成；这些部分记录没有被本任务读取或分析。

## 1. 先读布局与数据边界

`root` 指 implementation。材料变化采用已知网格上的 16 个固定实空间基，8 个 octant 均值与8 个局部 x-sign detail；物理基记作 `Q_s`，满足 `volume * Q_s.T @ Q_s = I16`。材料向量 `x` 是 `[16 real,16 imaginary]`，通过 `chart.expand(x)` 得到 N 个复材料值。因此“32 实材料图”包含 32 个实自由度。

| 对象 | 当前源码布局 | 源码依据 |
|---|---|---|
| solver material/mesh | n12，N=1728；points (1728,3)，chi/init/truth (1728,) complex | [assets.py:120](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/assets.py:120>)、[offline_assets.py:47](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/offline_assets.py:47>) |
| current | n=3N=5184 complex；当前单位 dipole/sqrt(volume) | [online.py:263](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:263>) |
| observations | 6 sources，64 receiver positions×2 channels=128 complex/source；data0 (6,128) | [assets.py:223](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/assets.py:223>) |
| packed real observations | 1536；source-major，每源 real channels 后接 imaginary channels | [online.py:263](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:263>) |
| material coordinate W | 默认 I32；material_features 接受 finite real p×32、W.T W=I32 | [online.py:299](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:299>) |
| current basis Q | (5184,q) complex，q≤32 可 deflate；U8 包含在 Q 中 | [online.py:340](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:340>) |
| MW / PMW | (6,q,32) complex | [online.py:307](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:307>) |
| AW | (1536,32) real-whitened；保留所有六个源块 | [online.py:314](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:314>) |
| offline full J | (1536,32) real；仅在 online freeze 后建立/重放 | [evaluate.py:564](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/evaluate.py:564>) |

旧观测的生成网格声明为 n14；保存的原对象 truth 成员由独立 loader 校验为 n12 solver 材料；新有限标签是在 n12 求解。三者的角色分别是历史观测、离线对象中心、同网格有限标签，不得把旧 data0 当作新有限标签的精确同网格值。见 [PREREGISTRATION.json:9](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/PREREGISTRATION.json:9>)、[offline_assets.py:94](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/offline_assets.py:94>)。

## 2. 用户指定五接口

| 接口 | 入口与主要调用者 | 输入→输出 | 边界与失败行为 |
|---|---|---|---|
| `build_anchor` | [online.py:220](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:220>)；Stage A / health 调用 | OnlineScene 或 label-free Problem、fixed config、book → Anchor(adapter,state,chi,provenance,cache_key,cost) | 验证 fixed patch32、六源、init 与公开背景一致；只在 χbg=0.1+0.04i 做 paid full forward。noise RMS 来自背景预测，不是 observed data / truth。非法背景、布局、噪声尺度拒绝。 |
| `build_opm` | [online.py:340](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:340>)；Stage A 调用 | Anchor+config → OPMModel(view,feedback,hierarchy,projection,basis,MW,PMW,AW,provenance,cost) | U8/O4/P4/M4、degree1 一次构造；独立固定 probes、r=0 builder view，禁止 measured-residual 默认替换。Galerkin，禁止 Petrov/full fallback 与 data-dependent Q；core failure 直接传播。 |
| `material_features` | [online.py:286](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:286>)；build_opm 内部与验证调用 | OPMModel、可选 W → MaterialFeatures(MW,PMW,AW,W,signatures,provenance,cost) | compressed B + 同一个 reduced LU 的 primal/core actions + S；不读取 J/H。anchor/material/geometry/chart/whitening/config 的 exact equality 变化拒绝缓存。零分母 branch 保留 undefined。 |
| `build_split` | [core.py:55](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/core.py:55>)；Stage A ranks4/8/16 | features/AW、declared_uncertainty、config、rank → MaterialSplit(Vp,Vrem,D,rank,status,certificate,eligibility) | AW 的 SVD 候选与完整 complement block 检查；Vp 32×r、Vrem 32×(32−r)、D r×1536。INVALID_BLOCK 或 TANGENT_CANDIDATE；full_model_certified=False，剩余 eligibility 为 finite_amplitude_unvalidated，不视为已完成物理/先验分离证据。 |
| `evaluate_recovery` | [evaluate.py:430](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/evaluate.py:430>)；每个有限观测 case 调用 | OPMModel、complex observation、config、book、可选 basis → coefficient solution 与 qp/data_residual/material_normal audit | d=white(pack(obs−background_prediction))，用 AW 或 AW@basis 做同一受约束材料求解；不读 truth/full J；one_material_subproblem=True，correction_events=0。 |

第五接口的下层是 [constrained_material_solve](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/core.py:112>)，它不是另一个用户入口：使用一般 real basis 的原材料不等式约束、SPD quadratic、必要时 SLSQP 与 active-equation KKT 检查。KKT/feasibility 失败抛 QPFailure，Stage A 保留 INVALID_QP、空 true_error 和原失败。没有 post-clipping、额外 jitter 或 pseudoinverse rescue。`basis` 是声明的材料限制，不是更改材料边界。

## 3. descriptor 公式到函数

为避免字母冲突，`Q` 是 current basis，`Q_s` 是空间材料基。`P=(Q*LQ)^−1` 是 reduced propagation，`M=Q*B` 是注入，`O` 是 packed/whitened `SQ`，`A=OPMW` 对应 AW。`*` 为 complex adjoint；实 packed 空间用 transpose。下面是源码的计算式与字段对应，不是理论证明。

| 实现对象/公式 | 函数与字段 | 解释/边界 |
|---|---|---|
| M W；P M W；A=white(pack(SQ PMW)) | [material_features](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/online.py:286>)：MW/PMW/AW | 所有源块保持 complex 到 data pack；三 fold factors 来源相同已知 anchor。 |
| α=||MWv||；β=||PMWv||/α；γ=||Av||/||PMWv|| | [direction_descriptor:176](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:176>)；也有每 canonical 列 signatures | directional factors。零注入/零传播为 None 或 NaN+branch，不补 ε 分母。明亮响应本身不代表可归属。 |
| N=orthogonal complement(v)，qv=(I−ΠAN)Av，g=||qv||；h_profile=qv/g² | [profiled_witness](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/core.py:11>) | 完整 nuisance numerical range；attribution=g/||Av||。g 为零/不可辨识时 h=None；不删“噪声弱模态”来增大 attribution。 |
| λ=tikhonov_relative·σmax(A)²；h=A(A.T A+λI)⁻¹v | [build_descriptor_context:91](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:91>)、[direction_descriptor:172](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:172>) | A1–A3 共用 regularized witness h。它与无 ridge 的 h_profile 分开记录；h0=Av/(||Av||²+λ) 为 A0 使用。 |
| IR=B−LQPMW；LH_Q=L*Q | [build_descriptor_context:45](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:45>) | 缓存 primal/dual residual actions，不是 full tangent 或 full adjoint solve。real→complex map norm 通过实/虚拼接求范数。 |
| coeff=P*Q*S_white*h；ψ=Q coeff；dual=S_white*h−L*Q coeff | [_dual_residual](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:102>) | 共用 reduced LU adjoint；direction_descriptor 复用 coeff，不重复同一 adjoint core 请求。核验 B*ψ 与 A.T h 的 real packed transpose identity。 |
| bg Neumann margin：αL=1−sqrt(||F||1||F||∞)，仅 αL>0 时保存正值 | [build_descriptor_context:64](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:64>) | αL 与注入 α 分开。缺正 margin 时 None；预测 divisor=1 是显式 empirical indicator 分支，不能解释成 αL=1 的证明。 |
| ρ0=0.25·sqrt(volume·N)；η=0.35；ρpert=|a|sqrt(1+η²) | [build_descriptor_context:73](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:73>)、[predict_budget:223](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:223>) | prior 是声明 pointwise 尺度，不读 realized object/truth norm；实际对象是否满足只在 offline audit 记录。 |
| back=A.T h−v；bias=ρ0||back||+|a|(|back.T v|+η||N.T back||) | [direction_descriptor:174](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:174>)、[predict_budget:229](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:229>) | target/nuisance attribution bias 与噪声 SD 分开。 |
| IR-radius=ρ0||IR||R+|a|(||IRv||+η||IRN||R) | [predict_budget:231](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:231>) | R 后缀表示 real material domain 的 operator norm，不是全模型误差标签。 |
| ROM2=||h||·Odef·IR-radius/divisor；ROM3=||dual||·IR-radius/divisor | [predict_budget:234](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:234>) | unstructured_ROM_budget / paired_ROM_budget；两者保留同一 noise/bias 与 declared region 输入。 |
| CM/radiation second derivative：a''=−18vc/(3+cχ)³，c=1−i3k³v/(6π) | [_polar_remainder_radius](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:113>) | 计算显式 denominator region 与 polarizability second term/feedback term；若 region pole 或 resolvent premise缺失则 None/empirical 状态，不隐藏一个常数。 |
| source amplitude5% / receiver gain3%；structured M/O factor budgets | [direction_descriptor:194](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:194>)、[predict_budget:243](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:243>) | descriptor 不知道 evaluator 的实际 calibration signs。物理 readout/source transform 的实际 signs 在 [_calibrate_data](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/evaluate.py:377>)。 |
| voxel pullback outside=g−Hspatial Hspatial.T g | [direction_descriptor:184](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:184>) | 已知 anchor 注入 factor + B* voxel action；W_external_witness_norm 不从 truth residual 定义。 |
| ext2=||h||·||Swhite||·voxelB·ρ0/divisor；ext3=(||outside||+voxelB·||dual||/divisor)ρ0 | [predict_budget:245](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:245>) | 显式 W-external budget；intervention 分支乘 1.0815。不把 W 外材料并入 Vprior。 |
| A0=sqrt((ell||h0||)²+((ρ0+|a|)λ/(||Av||²+λ))²)；A1=sqrt((ell||h||)²+bias²) | [predict_budget:258](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:258>) | A0 总响应/ridge baseline；A1 common witness + noise/attribution baseline。 |
| A2/A3=sqrt(noise²+(bias+ROM+nonlinear+factor+external)²) | [predict_budget:261](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/features.py:261>) | 分别用 unstructured/paired 分项。`certificate_type=empirical_indicator`；`full_model_uniform_certificate=False`；region_model_components_valid 单独记录。 |

`direction_descriptor` 对 zero / complex / wrong shape / nonfinite v 在动作前拒绝。[choose_directions](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/core.py:187>) 只看小 AW/canonical patches 与小 AW 的 SVD：强/弱响应、高/低 attribution、coarse/detail、SVD 控制；不看 truth/recovery label。

## 4. 在线/离线隔离与冻结顺序

1. `load_online_scene` 逐成员读取 points/data0/init；不读 truth/held_truth/scene_json/old chart/old objective scale。[OnlineScene](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/assets.py:52>) 禁止直接访问 offline 名字。[prepare_screening](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/prepare.py:156>) 只部署这三成员与公开 geometry，保留 exposed/mesh/layout manifest。
2. known background anchor → fixed OPM → descriptor context → directions/descriptors → online_factors / online_provenance / frozen_online_directions / frozen_online_budgets。`RestrictedBuilderView` 只开放 F/F*、L/L*、S/S*、B/B*、forcing 与 geometry receiver；full_state/full tangent/full adjoint/J/H/truth 的 builder 属性拒绝。原始内部 Adapter 仍供受限模块的已知 anchor操作使用，不宣称是独立安全进程隔离。
3. freeze 完成后，[load_evaluation_truth](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/offline_assets.py:214>) 通过 offline role guard 读取单成员独立 `data/a22/offline_eval/scene_ID.npz`。在线 config 没有标签路径。该 bundle 可被显式 evaluator transfer，不能说离线标签永远未部署，也不能并入 online whitelist。
4. offline 原对象 center χobj，注册有限 perturbation 为 χobj+chart.expand(a(v+ηn))。base_coeff=chart.project(χobj−χbg)，真 coefficient target=base_coeff+perturbation；W-external remainder 单独审计。[finite_label](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/evaluate.py:333>) 直接 `adapter.model.state(chi)`，不把另一对象材料激活为 online projection operator；full forward/LU/receiver/Goff/backward residual 和 new data generation 均计费。
5. full J 在 paid known anchor上生成，保存 OFFLINE_J_benchmark；hF/htotal 只用于离线 benchmark预测，绝不替代冻结 A0–A3。`pred_full_J` 和 `pred_full_J_total` 统计域均 offline_full_J，不进入正式 A3 vs A1/A2 增量比较。
6. evaluator 给 observation，`evaluate_recovery` 仅做 deployable共同 QP；evaluator 才把 solution 与 true_coeff 比较并写 `true_error=abs(v.T(solution−true_coeff))` 与 relative_true_error。row 同时保留 deployable feature provenance 与 offline label provenance；label 是离线并不自动把在线 predictor变成oracle。
7. resume 验证保存 online freeze、factors、anchor cache contract、directions、budget 与 case identity，然后才重放 offline J/label cache。失败/INVALID_QP 保留，cache hit不推测成新 physics；旧 legacy cache 明确标记。[evaluate.py:59](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/evaluate.py:59>)、[evaluate.py:167](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/evaluate.py:167>)。

## 5. 固定配置与可复现 seed 索引

依据 [a22.json](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/configs/a22.json>)、[a22_portable.json](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/configs/a22_portable.json>)、[PREREGISTRATION.json](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/results/a22/PREREGISTRATION.json>)。`source_freeze` 是现有 provenance 字段，本任务不验证 Git、生成 digest 或对其哈希。

| 项目 | 当前值/来源 |
|---|---|
| source/base identity | source_freeze=8aa2d5d03c8fc41bda508c2e173a45fa2fea956a；CLI环境另外注明 frozen Git base plus saved A22 source |
| precision / background | complex128/float64；0.1+0.04i |
| shallow/current/material | U8/O4/P4/M4，degree1，qmax32；材料32 real，no Petrov/full fallback、no data-dependent Q |
| four screening scenes | 2001、2003（family=gaussian），2014（asymmetric），2009（shell）；历史 exposed |
| descriptors/finite cases | 8 descriptor directions；screen finite4 / expansion finite3；amplitude fractions0.2、1.0；physical max0.25；feasible fraction0.8；nuisance fraction0.35 |
| noise | proper complex Gaussian；levels0、1、3；reference fraction0.01；nonzero16 draws，zero noise单draw；reference取known background predicted RMS，white sqrt2/sigma |
| solve/split | tikhonov_relative1e−4；split ranks4、8、16；Reχ≥−0.5，Imχ≥0；feasibility/KKT rtol1e−8；qp_maxiter200；physical correction_events0 |
| descriptor prior/center | declared pointwise prior0.25；known-anchor analytic W-external injection budget；finite_label_center=original_scene_material_OFFLINE_ONLY |
| master seed | 20261007 |
| O/M fixed probes | SeedSequence([master_seed, scene_id])；与 observed residual无关 |
| nuisance perturbation | SeedSequence([master_seed, scene_id, direction_id,511]) |
| observation noise | SeedSequence([master_seed,scene_id,direction_id,amplitude_level,draw,661])；seed不含intervention或noise_level，标准噪声配对后缩放 |
| bootstrap | 2000 repetitions，seed取master_seed；paired scene resampling |
| health fixture RNG | run_backend_health 固定20261007；tiny n4，64 cells、6 sources、128 channels/source、32 real material，不是项目 n12 screening |
| decoder plan only | hidden128/128，lr0.001，weight_decay1e−5，epochs200，patience20，batch8；seeds202610071/072/073；train_sizes6/9；此配置不证明训练实现或执行 |
| formal registered IDs | development=[2001,2003,2005,2013,2014,2016,2009,2010,2011]；calibration=[2007,2020,2012]；evaluation=[2002,2004,2006,2008,2021,2022,2023,2024,2031,2032,2033,2034] |
| dormant new-scene recipe seeds | 2020…2024 与2031…2034 的各自 seed为20261007拼接scene ID；配置/recipe不等于已生成资产 |
| budget | GPU occupation总32400s；screen_health1800、features3600、direction7200、image5400、runtime7200、train5400、exception1800s；new generation F cap192；book teacher cap9；CPU计费但无campaign CPU cap |
| gate parameters / outcome | config含A/B/C/D/T thresholds与phase prerequisites；仅参数，不抄成结果。本文件不评判是否满足。预注册明确four-scene screening不等于formal PASS。 |

portable asset_root 是当前本地绝对 `root/data/a22/online`；[portable_config](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/cli.py:60>) 在执行 root 上重定位。remote_root/shared_lock_root 的配置字符串是 D:/AI/A22_THREE_FOLD_OPM 与 D:/AI/A20_OPM_IMAGING；本审查未连远端或确认部署。

## 6. 实际 CLI 入口与命令形式

[cli.py:69](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/cli.py:69>) 支持以下形式。它们是源码核对的入口模板，**不是本任务已执行记录，也不是精确历史启动命令**。当前 active job/PID/env/outcome 未读；是否执行与何时执行由父线程控制。每个新进程须用新的 `a22-...` job identity，原 receipt不覆盖。

在 implementation 工作目录，源码接受：

```text
PYTHONPATH=src python -m a22.cli preflight --root . --device cpu --job a22-preflight-UNIQUE
PYTHONPATH=src python -m a22.cli prepare --root . --device cpu --job a22-prepare-UNIQUE
PYTHONPATH=src python -m a22.cli prepare-evaluation --root . --device cpu --job a22-eval-assets-UNIQUE
PYTHONPATH=src python -m a22.cli unit --root . --device cpu --job a22-unit-UNIQUE --pattern test_a22_*.py
PYTHONPATH=src python -m a22.cli validate --root . --device cpu --job a22-health-UNIQUE
PYTHONPATH=src python -m a22.cli descriptor-validate --root . --device cpu --job a22-descriptor-health-UNIQUE
PYTHONPATH=src python -m a22.cli screen --root . --device cpu --job a22-screen-UNIQUE
PYTHONPATH=src python -m a22.cli screen-resume --root . --device cpu --job a22-resume-UNIQUE
PYTHONPATH=src python -m a22.cli report --root . --device cpu --job a22-report-UNIQUE
```

CUDA 执行的同一源码形式（public paths取自config，不含SSH凭据）：

```text
python -m a22.cli screen-resume --root D:/AI/A22_THREE_FOLD_OPM --device cuda --job a22-resume-UNIQUE --lock-root D:/AI/A20_OPM_IMAGING
```

需由启动环境设置 `PYTHONPATH` 以找到 src。CLI记录 OMP_NUM_THREADS / OPENBLAS_NUM_THREADS / MKL_NUM_THREADS / VECLIB_MAXIMUM_THREADS，但其实际值本任务未读取，不能在此声称已设为1。`A22_BUDGET_STAGE` 可显式指定计费stage；`A22_JOB_WALL_ORIGIN` 可包含launcher wall起点，这些仅是源码接口。

- preflight/prepare/prepare-evaluation 不启动 physics；prepare-evaluation 是明确离线标签capability。
- unit/validate/descriptor-validate 在执行时会进行各自验证工作和计费；本任务均未执行。validate CPU输出目录拒绝覆盖；CUDA验证按job分目录。
- screen/screen-resume 使用四IDs；pilot 在 source入口读取 positive SCREENING_DECISION，才尝试 formal IDs。当前 evaluator truth loader只接受四IDs，后续scene inputs/route尚需父线程另行落实；不从配置列表推断已有资产。
- one-shot/train 先检查 frozen PASS prerequisites，随后当前代码仍抛 CONDITIONAL_IMPLEMENTATION_NOT_FROZEN_YET。不能把CLI选项或decoder config当作阶段已实现/已运行。
- report 仅调用 raw generate_reports；不自动调用 statistics、statistical plots 或 cost export。以下均是 parent-owned metered API，源码提供但本任务不调用：

```python
analyze_direction_metrics(root/'results/a22/stage_a/direction_metrics.csv', config,
    mode='screen', scene_manifest=root/'results/a22/stage_a/scene_metrics.csv',
    output_dir=root/'results/a22/statistics')
generate_statistical_plots(root, saved_statistics_evidence)
export_cost_csv(root)
```

这段展示接口连线，不自动决定 missing scene/data是否可分析，不写gate。`generate_reports` 会写主report documents，最终中文科学内容由父线程另行重写。

## 7. 输出索引（写路径，不是存在性/成功证明）

除 PREREGISTRATION 已读取，其余路径只根据源码写操作列出。未打开实际NPZ、CSV结果、receipt或图片。缺少文件/字段保留 NOT_RUN、UNDEFINED 或 NOT_MEASURED。

| 写路径 | 写入者 / 用途 |
|---|---|
| configs/a22_portable.json；data/a22/online/MANIFEST.json；scene_ID.npz | prepare_screening；每场景仅points/data0/init+公开geometry；不复制mixed archive |
| data/a22/offline_eval/MANIFEST.json；scene_ID.npz | prepare_offline_screening；仅truth成员，OFFLINE_EVALUATOR_ONLY、exposed、n12/n14 provenance |
| results/a22/PREREGISTRATION.json | parent冻结的范围、标签/online/prior/mesh/calibration说明；本任务已读取，不裁定entry rule |
| results/a22/stage_a/progress.jsonl | per-scene STARTED event；不等于 COMPLETE |
| results/a22/stage_a/direction_metrics.jsonl、csv | percase forecast/true_error/provenance/status；resume保留原attempt；INVALID_QP目标为空 |
| results/a22/stage_a/split_metrics.jsonl、csv | ranks4/8/16 tangent candidate block证据；不是physical/complement恢复结果 |
| results/a22/stage_a/scene_metrics.jsonl、csv；scene_manifest.csv；RUN_SUMMARY.json | per-scene COMPLETE/FAILED与计数/条件；source存在writer，不宣称当前全四完成 |
| stage_a/scene_ID/online_factors.npz | AW/MW/PMW + known-anchor cache contract（material/mesh/chart/source/receiver/white/config/layout）；无objecttruth |
| stage_a/scene_ID/online_provenance.json；frozen_online_directions.json；frozen_online_budgets.json | 冻结online factors/方向/预算及label/J未读说明 |
| stage_a/scene_ID/online_split_RANK.npz | V_phys、V_prior、D |
| stage_a/scene_ID/OFFLINE_material_model_audit.json | actual object中心是否在declared prior；W-external/material norm/retained energy及mesh区别；仅offline |
| stage_a/scene_ID/OFFLINE_J_benchmark.npz | JF+known-anchor contract；offline基线，不能部署给predictor |
| stage_a/scene_ID/OFFLINE_label_dD_aL.npz | clean_data/truecoeff/perturbcoeff/originalmaterial/direction/nuisance/amplitude/backwardresidual+contract；受限evaluator cache |
| stage_a/scene_ID/calibration_dD_aL.json；resume_audits/UUID/ | evaluator signs与immutable freeze/cache重放诊断；不输入predictor |
| results/a22/statistics/STATISTICS_EVIDENCE.json；PAIRED_SCENE_BOOTSTRAP.json；STATISTICS_INPUT_AUDIT.json | write_statistics caller选此canonical目录；完整noise聚合/fit/heldsplit/evidence/missing/pairedscene信息 |
| results/a22/statistics/per_scene_statistics.csv；calibration_scales.csv；statistics_summary.csv | per-scene calibrated Spearman/MAE、single scale、equal-scene summary；raw_*分项保留 |
| results/a22/reporting/rawdata；EXPECTED_METRICS_SCHEMA.json；SUPPLIED_EVIDENCE.json；FIGURE/REPORT_MANIFEST | raw generator源副本、schema、描述性指标、source coverage；不重新决定gate |
| figures/a22/*.png、svg | raw uncalibrated diagnostic figures与B/C显式status cards；无假测量 |
| results/a22/reporting/statistical/rawdata；SUPPLIED_STATISTICS_EVIDENCE.json；facet_STATISTICAL_FIGURE_MANIFEST | separate helper读取已保存statistics，不re-fit/score/bootstrap；noise-zero/positive、scope、split显式facets |
| figures/a22/statistical/*.png、svg | calibrated groupedunits、savedper-scene MAE/Spearman、savedpairedsceneCI；full_J与full_J_total分别offline图 |
| results/a22/validation/HEALTH.json；theory/verify_*/execution.json/stdout.txt | CPU provided verifier+tiny DenseDDA health；拒绝覆盖；不是continuum/project acceptance |
| results/a22/validation_cuda/JOB/HEALTH.json；validation/descriptor_health/JOB.json | CUDA tiny健康与descriptor identity/remainder/QP检查；不是四项目scene筛选结果 |
| results/a22/unit_validation/unit_tests/JOB.log、json | unit / tiny fixture日志；不等于scientific acceptance |
| results/jobs/a22-JOB/accounting_started.json；accounting_checkpoint.json；environment.json；cost.jsonl；outcome.json；job_receipt.json | job含失败的inclusive费用、source/env、动作span与最终receipt；checkpoint明确running，不冒充final |
| results/a22/JOB_LEDGER.jsonl；COST_LEDGER.jsonl；FAILURE_LEDGER.jsonl；external_cpu_receipts.json | mirrored/registeredcampaign记录；失败、unsafe rejection、cachehit保留 |
| results/a22/cost_ledger.csv；ACTION_ACCOUNTING.json | export_cost_csv只汇总原记录；不推测A0/A1/A2独立deployment费用 |
| A22_IMPLEMENTATION_REPORT.md；A22_RESULTS_LEDGER.md；A22_GATE_DECISION.md；STAGE_A_REPORT.md；GATE_REPORT.md | raw generator默认root写；最终科学中文内容由父线程写；本任务不编辑 |
| results/a22/GATE_DECISION.json；SCREENING_DECISION.json | parent authority inputs；本任务未读/未写/未derive结果 |

默认 discovery 已在独立source scope修复：[reporting.py:534](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/reporting.py:534>) 的raw四CSV/manifest优先stage_a，其次旧screening与root；[reporting.py:722](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/reporting.py:722>) 的canonical helper优先statistics artifact，其次旧screening/root。保留原A22 path guard与缺失NOT_RUN。`tests/test_a22_report_discovery.py` 新3项fixture未执行；不改reducer/statistics/CLI/gate。

## 8. 证据类别不能相互替代

| 类别 | 当前source如何区分 | 本文不能据此声称 |
|---|---|---|
| supplied theory正文/证明 | verification入口名称来自 `validation._run_provided`；本任务不读proof正文 | 定理已审查有效、统一证书成立 |
| provided verifier / unit / identity | supplied toy counts、原协议结果preserved；pack/adjoint/cache/core/KKT/tinyfixture路径 | 项目对象已可恢复、gate通过、Maxwell大网格覆盖 |
| paid tiny Maxwell health | [validation.py:188](</Volumes/migodam's-external-brain/Research/Inv_SLAM/Gaussian/A22/three_fold_opm/implementation/src/a22/validation.py:188>) tiny n4 DenseDDA；明确 scientific_gates_adjudicated=False | n12四scene screening / continuum acceptance |
| actual finite Maxwell evaluation | original material+nuisance、same solver grid、fullstate residual、paidofflineF/LU；线上预算先冻结 | 仅行存在就证明四scene完成或forecast覆盖 |
| offline full-J benchmark | JF来自knownanchor；full_J/full_J_total method_scope=offline_full_J | 增量predictor在线可获取、部署费用、正式A3 baseline win |
| empirical deployable forecast | AW/residual actions、declared priors、component indicators；输出full_model_uniform_certificate=False | 校准后成为full nonlinear uniform certificate |
| statistical evidence | noise mean units、LOSO/development scale、equal-scene统计、pairedscenebootstrap；fit不在bootstrap重跑 | pooleddraws是独立scene、CI覆盖retraining uncertainty、少量scene自动formal PASS |
| accounting evidence | finalreceipt/uniqueexternal可加；span描述工作；CPU/GPU独立；F/F*/L/L*互斥与generic aggregate分开 | span墙时可叠到job、Maxwell aggregate是额外动作、历史A20/A21可充A22预算、A0/A1/A2独立费用已测 |

source中存在 `region_model_components_valid` 与局部 deterministic_bound 分项，也始终给project预算标 empirical_indicator。actualobject是否被declared0.25prior涵盖、region resolvent是否正、有限误差是否被预算覆盖，需要实际offline审计与完整结果；本文未读取这些值，不作结论。

## 9. 保留的不确定项

- exact historical process command、active PID、deployment、实际threadenv/counters/failures/remainingGPU：未读job/远端，NOT_VERIFIED。
- 四scene完整性与parent所述337条进展：未查结果；没有从部分记录分析。
- Gaussian强度、2009具体nested multiscale结构：当前公开source family strings未包含完整材料参数；未读原对象说明。
- offline truth loader目前只接受四screeningIDs；full24注册split与newscene/decoder配置不说明已有资产/训练cache。
- CLI one-shot/train未冻结实现；report仅raw dispatch；统计/成本/统计图需parent计费显式调用。
- 此文仅为接口交付索引；最终理论/科学/gate判断与主中文报告由parent负责。
