# A22 实现与验证报告

Stage A 四场景筛查已完成。Gate A 为 **PARTIAL**，按预注册停止扩展、one-shot 成像和 NN。完整 24 场景实验、Stage B/C 的条件性驱动均未执行；不能把本地接口和测试通过称为整条路线成功。

## 冻结来源与计算模型

工作分支为 `a22-three-fold-opm`，基于 A21 commit `8aa2d5d03c8fc41bda508c2e173a45fa2fea956a`。八份原理论文件与三个 route 的副本保存在 `protocol/a22/`；母目录理论、A17–A21 原代码及账本保持冻结。A22 使用独立 `src/a22` 和账本，未修改 DenseDDA/Maxwell solver，未调用旧 `reconstruct()` 或 A21 oracle cache loader。

部署假设是已知实际背景 `0.1+0.04i` 的材料扰动成像。材料图包含 8 个粗八分块、8 个中心化局部 x 细节，共 16 个与 truth 无关的空间基，分别用于实部和虚部，形成 32 个实自由度。空间基满足 `v QχᵀQχ=I16`，因此系数欧氏范数等于图内的体积加权材料范数。W 外材料不属于 `V_prior`，另行记录。

电流采用原 `dipole/sqrt(v)` 单位。固定 `U8/O4/P4/M4`、degree1、总 current rank 上限32；四场景实际 rank 均32。六源先汇集再压缩，O 探针显式使用固定随机数，构基残差置零，不由 noisy measurement 替换。Galerkin core 使用原尺度与条件门槛；失败直接留账，无 Petrov/full fallback、Maxwell 伪逆或隐藏 jitter。

六源各有128复通道，逐源 `[Re128, Im128]` 打包，总1536实数据。proper complex Gaussian 噪声满足实、虚方差各 `σc²/2`；`σc=0.01×已知背景预测数据RMS`，白化为 `sqrt(2)/σc`。旧 `1/problem.scale` 仅保留为历史目标归一化，不用于此次噪声尺度。

## 五个接口

| 接口 | 实现 | 职责 |
|---|---|---|
| `build_anchor` | `src/a22/online.py` | 付费构造已知背景完整状态、噪声参考与 provenance |
| `build_opm` | 同上 | 固定浅层 O/P/M 与 Schur feedback，返回实际 rank 和成本 |
| `material_features` | 同上 | 用压缩 B、小核及接收像形成六源 MW/PMW 和1536×32实 AW |
| `build_split` | `src/a22/core.py` | 构造图内候选 `V_phys/V_prior`、读出 D 和 block 审核；有限幅度未验证时保留未解决状态 |
| `evaluate_recovery` | `src/a22/evaluate.py` | measurement 减背景、白化、一次受约束材料 QP；不读取 truth/full J |

下层 `constrained_material_solve` 保持原约束、显式 Tikhonov 正则化、SLSQP/active-equation 路径及原 KKT/可行性容差 `1e-8`。原3456条逐单元不等式在此固定图中只有32种完全相同的 `(系数行,下界)`；仅在优化器输入中精确去重，最终可行性、法向、互补性和 KKT 仍按全部原约束审核。没有近似合并或事后裁剪。等价性记录见 `results/a22/EXACT_CONSTRAINT_EQUIVALENCE.json`。

公式—函数、配置、种子和成本来源详见 [源码映射](research/delegated/a22-delivery-audit/SOURCE_INTERFACE_MAP.md)。

## 信息边界与有限幅度范围

在线资产白名单仅含 geometry、选定 measurement、init；构建视图拒绝 truth、teacher、full J/H、GN optimum 和 oracle currents。所有方向、预测和预算先冻结，再打开独立的 `data/a22/offline_eval`。full-J/SVD 对照只在 OFFLINE 评估器中建立，未进入在线特征、选方向或基底。

有限标签的中心是原对象材料，目标和全部31维 complement nuisance 同时变化；在线 anchor 始终为公开已知背景。旧 data0 生成网格为 n14，保存材料与新标签求解网格为 n12；旧观测不作为新同网格标签。四个原对象及其变体均标记历史暴露。

T10 实现包含实际 Clausius–Mossotti/辐射反作用的 `a''=-18vc/(3+cχ)^3`，其中 `c=1-i·3k³v/(6π)`，并检查区域分母与充分 resolvent 裕度。背景/局部分量的代数界不能自动覆盖原对象及 W 外成分。全部预测仍标记 `empirical_indicator`、`full_model_uniform_certificate=False`；校准不使其成为严格证书。

## 实现验证

| 证据 | 保存结果 | 范围 |
|---|---|---|
| 单元与 tiny fixture | `a22-unit-013`：130 PASS，0失败/错误/跳过 | packing、白化、metric/gauge、nuisance profiling、block、QP/KKT、隔离、缓存、预算与监控 |
| 两份随包 verification | `a22-cuda-validate-002`：均 PASS | 原协议代数与小规模数值验证，未重做证明 |
| 实际 DenseDDA 健康检查 | CPU/CUDA 均 PASS | 4³单元、原六源/128通道、伴随、导数、直接通路和 Schur/Galerkin |
| 实际两侧缺陷恒等式 | 相对残差 `9.1632e-15` | 小网格实现一致性 |
| 实际极化率二阶导数 | 有限差分相对误差 `2.6784e-11` | 包含物理非线性余项，不是全域成像证书 |

具体记录位于 `results/a22/unit_validation/`、`validation/`、`validation_cuda/`。失败版本也保留。后加报告 discovery fixture 曾因 macOS `/var` 与 `/private/var` 路径别名失败，规范化 fixture 后全部通过；这不涉及物理代码。

## 运行、恢复与未执行部分

XINAN 使用既有 Python3.10.9、NumPy2.2.6、SciPy1.15.3、PyTorch2.6.0+cu124、RTX4060 Laptop/8GB，complex128/float64。共享 A20 GPU 锁保护单一作业。每个失败、重跑、参考、验证和计时保留费用，不重置额度。

screen001/002 因 Windows 监控读取 `PermissionError` 中断，209与337条阶段记录分别归档。screen003 使用 native `FILE_SHARE_READ|WRITE|DELETE` 快照读取，正常完成，0次读取冲突。原始两个错误记录未保存具体函数/errno，根因精度缺口保留。续跑重新付费构基，AW 与原值差0，科学 provenance、方向、预算与缓存严格核对；保留终止性 INVALID 行，不为失败挑选重跑。

Stage B/C 的完整条件驱动未冻结、未实现、未运行；CLI 明确拒绝前置 gate 未通过的调用。已有一次材料求解接口不是完成的 split-image pipeline。24场景扩展的输入、独立新seed接线和训练缓存也未执行。没有训练任何 NN、启动 nonlinear reconstruction、增加 degree/rank 或发布。
