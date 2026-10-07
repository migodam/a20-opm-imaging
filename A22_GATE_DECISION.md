# A22 科学判定：PARTIAL，停止

**停止24场景扩展、one-shot physics 成像和 prior decoder。** 四场景筛查完整，但结构化描述子未显示预注册要求的增量价值。结果保留为 PARTIAL，不制造 PASS，也不将条件定理判为已被推翻。

| Gate | 状态 | 依据 |
|---|---|---|
| 实现验证 | PASS | 130项单元验证及两份随包 verification/真实 tiny backend 检查通过 |
| A screening | **PARTIAL** | 中位rho0.5069，但MAE改善−0.1263%，95%区间跨零；不满足扩展入口 |
| A 完整24场景 | NOT_RUN | screening没有正向增量信号，不扩展 |
| B 物理/先验分离 | NOT_RUN | A非正式PASS；候选split未获有限幅度成像验证 |
| C 有用one-shot结构 | NOT_RUN | 未进入Stage B；coarse coefficient主门槛未评估 |
| D prior-only decoder | NOT_RUN | A/B/C未全部PASS；没有训练任何NN |
| T 部署成本 | **NOT_ESTABLISHED** | 缺同质量的端到端对照；不从低rank推出速度收益 |

冻结 screening 的正向入口是 A3 场景中位 Spearman≥0.5 且相对较强 A1/A2 的 LOSO MAE改善≥15%。clear-negative 定义为rho<0.5且改善区间上界≤0；两者均未满足，因此按预注册的其它分支判PARTIAL并停止。四场景 screening 永远不能授予正式 Gate A PASS。权威机器记录为 [GATE_DECISION.json](results/a22/GATE_DECISION.json) 与 [SCREENING_DECISION.json](results/a22/SCREENING_DECISION.json)。

A2 MAE为0.0375231，A3为0.0375705；A3−A2的变化不能支持结构化 recoverability descriptor 更准确。绝对改善95%区间 `[−0.0061458,+0.0018125]`，bootstrap以4个场景为paired cluster，条件于已保存的校准，不是2112个独立样本。

## 五类证据

| 类别 | 已完成的内容 | 科学边界 |
|---|---|---|
| 理论包已有命题 | 原文冻结保留 | 未重新做理论；实验不代替条件证明 |
| 数值身份/单元验证 | packing/adjoint/metric/两侧/极化率/KKT/隔离/预算 | 支持实现一致性，不授予成像GO |
| 实际Maxwell实验 | 四对象、32 clean标签、2112恢复案例 | 历史暴露、known-background、固定32维图的经验筛查 |
| OFFLINE/oracle | full-J/SVD式比较、原材料审计 | 未用truth-state/late-GN oracle作在线方法；未跑新的oracle construction |
| Deployable online | 仅known-background/probe/residual动作构基与冻结预测 | 证明信息来源合规；尚无one-shot图像质量或部署收益证据 |

四对象均超出声明逐点先验，asymmetric/shell 的 W 能量覆盖很低。这些事实限定当前经验指标和材料模型的适用性；不把宽 raw budget 的100%覆盖包装成严格证书，不通过扩大rank/degree/先验或网络救场延续实验。

本地代码、配置、输入、原始结果、表图、失败与费用全部保留。后续路线条件驱动仍未冻结，研究状态不是三阶段全部实施成功。The experiment stopped at local delivery. The completed evidence is subsequently shared on an independent A22 public branch following the user's link request. Scientific gates remain unchanged; no follow-on stage is started. The original LOCAL_ONLY manifest is preserved as a historical record.
