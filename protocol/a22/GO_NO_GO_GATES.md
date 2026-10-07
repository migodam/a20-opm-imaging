# GO / NO-GO gates：当前状态、建议阈值与路线裁决

## 0. 本轮当前状态

| 项目 | 状态 |
|---|---|
| 有限维定理与证明 | 已完成本包所列推导 |
| 小矩阵与八粒子 vector checks | 已运行；见原始 JSON |
| Gate A recoverability prediction | NOT_RUN on project scenes |
| Gate B physics/prior separation | NOT_RUN on project scenes |
| Gate C one-shot headroom | NOT_RUN on project scenes |
| Gate D prior-only NN advantage | BLOCKED by A/B/C |
| Gate E diffusion necessity | NOT_ESTABLISHED；训练禁止 |
| End-to-end acceleration | NOT_MEASURED |

不是把所有尚无数据的结论都判 false，也不是因为定理成立就判 gates true。

## 1. 阈值如何使用

以下数值是 **建议的 pilot 预注册阈值，不是结果或理论常数**。可根据实际任务精度在 development 阶段调整一次，然后冻结。不同任务不能机械共用同一个 support/error 标准。

### Gate A — prediction 与 mechanism value

基础要求：部署可得的 signature 能预测实际 coefficient recovery difficulty，而非仅拟合同一小矩阵的 singular value。建议 scene-wise rank correlation median≥0.5。

增量要求：在有限幅度/模型扰动测试中，相对 A1/A2 强基线，OPM 增量 features 的 held-out prediction MAE 降低至少 15%，并用 scene-cluster interval 检查提升方向。样本不足或 interval 跨零标记 PARTIAL，不宣称独立增量已经确认。

固定精确线性模型下“无法超越完整 J”不是 failure，因为 T0 已说明不应超越。若机制量在应该有差异的干预/失配测试中也没有增量价值，则 **kill OPM-specific recoverability claim**，保留标准 SVD/NSN 混合成像作为已有技术路线，不包装成新论文。

### Gate B — separation 必须非平凡

建议比较同 rank baseline，要求 accepted physics coordinates 的 relative error≤0.2；per-coordinate 标准化 error 明显小于 complement，例如 ratio≤0.5。还要求保留至少 r=4 或明确非平凡任务维数，并有足够任务/真值能量覆盖。

relative denominator 太小时改用预声明绝对材料尺度；同时展示未归一化 error。若主要误差仍在 V_p，不能锁它再让 NN 补余项。若所有非平凡 split 都失败，**kill protected prior-only decomposition in this regime**。

### Gate C — practical one-shot headroom

在可部署 anchor 上而非 oracle late state 上，physics image 必须达到预定任务阈值。例如 coarse coefficient relative error≤0.3，或 support IoU≥0.5 且 location error≤0.15 wavelength；这些是候选定义，应按实际成像任务固定一个主标准。

同时报告真实 nonlinear data discrepancy。一个 support indicator 通过，不等于 quantitative permittivity 通过。若需要多次 GN 才产生有用 backbone，one-shot architecture 当前 NO-GO；允许诚实比较一次 correction 的 two-shot variant。

### Gate D — prior-only 的实际优势

same encoder、same training scenes、similar capacity/cost，对 whole-image NN 至少一项有清晰收益：样本效率、真实数据一致性、OOD、hallucination 指标或 time-to-image。建议选择单个 primary，例如 test data-consistency violations 降低≥20%，同时 material error 不劣化超过5%；或相同error用更少训练场景。

不要事后从很多指标中挑一个显著结果。若仅结构性 protected drift=0 但图像更差、data更差、时间更长，不足以判这条 architecture 实用成功。

### Gate E — generative necessity

需要合法 posterior ambiguity/任务相关uncertainty、低维 residual latent 证据、deterministic/简单 UQ baseline 不足。误差平台本身不是 diffusion 许可证。本轮没有这些证据，保持 OFF。

### Gate T — time-to-image

必须在同质量 success 标准下有端到端优势。建议 pilot 目标≥2× median time reduction 且 success rate 不降低；未满足不等于不存在任何科研价值，但不能写 fast-imaging 的强性能结论。warm/cold、offline成本与failures分开报告。

## 2. Killed routes

立即停止：继续扩大 OPM degree、用 full J/H 作为 online encoder、把 oracle s_F/e_F 放进线上模型、用逐方向norm阈值替代block稳定性、ROM-null直接送NN、无限制全图NN偷偷修复锁定physics、先训练diffusion再找ambiguity、只报per-GN-step速度。

有条件停止：在合法 deployment anchors 下普遍没有one-shot headroom；OPM相对profiled小SVD没有机制/鲁棒性增量；prior-only相对公平whole-imagebaseline没有优势；加上诊断后time-to-image无收益。

保留为独立背景：A17 mechanism/current exchange；A21 oracle two-sided GN。它们不因本轮路线失败而被否定，也不被强行塞回新NN论文。

## 3. 最终路线

PRIMARY：one-shot OPM + nuisance-aware、model-aware、finite-amplitude material recoverability。

SECONDARY：只在前置 gates 后运行的 deterministic prior coefficients。

HIGH-RISK：prior latent posterior/flow，仅理论。

OPTIONAL：规则 early exit、小 classifier、一次 full-wave consistency correction。

执行文件 A→B→C 是带 gate 的顺序流程，不是三个都必须无条件跑完的 campaign。
