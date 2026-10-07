# Early exit：先做可审计的规则，再考虑 classifier

## 1. 三档计算不是三种物理真相

用户希望 easy→physics-only，medium→small decoder，hard→posterior。这个策略还需要第四个出口：**模型不可信/超出适用域→abstain 或一次 physics correction**。大 residual、强 nonlinearity 和 OOD 不能自动解释为 posterior multimodality。

建议第一版用规则，不训练 classifier：

- Physics accepted：目标误差预算通过，必要任务覆盖非零，model-validity 和独立数据检查通过。
- Prior eligible：physics 已可靠，但剩余材料误差/uncertainty 经验证集中于 eligible complement。
- Posterior eligible：仅在 diffusion 文件所有启动条件满足后才可启用；本轮关闭。
- Model failure：背景、ROM、曲率、材料支持或 geometry 超域；拒绝或一次 correction。

## 2. 最小输入与标签

输入可包含 witness error budget、attribution ratio、||P||及 reduced equation condition、two-sided primal/dual residual norms、physics coefficient norm、frequency disagreement、orthogonal data residual、检测到的 geometry/material domain flags。

不能输入 truth、full GN 最终误差、oracle state 或测试集挑出的最佳 route。它们可以仅用于离线标签：某 route 在完整 benchmark 中是否达到事先定义 acceptable image。

“physics_only”标签不能只看 data residual，因为 weak/prior directions 的图像错误可能很大。标签同时满足任务误差和数据一致性；部署时只是预测此事件，不是验证了真实图像。

## 3. 有标签后再训练成本敏感 classifier

可先用 logistic regression 或两层小 MLP；按照 expected loss + latency penalty 选择 route：

\[
\widehat r(z)=\arg\min_r\{\widehat{\mathbb E}[\ell_r\mid z]+\mu T_r\}.
\]

对不满足安全预算的路线设置不可用，而不是让 classifier 用概率覆盖物理拒绝。posterior route 的 admissibility 是外部 gate，不由一个 softmax 训练出来。

训练和 calibration 按 scene 分割。小样本报告置信区间；零误判不等于风险为零。例如 n 个独立接受样本中零次失败时，一侧 95% 二项上限为 1−0.05^{1/n}。该式直接由 (1−p)^n=0.05 得到，避免把少量样本上的“100%可靠”当保证。

## 4. 期望成本

若 route k 的选择概率为 π_k，

\[
E[T]=T_{encoder}+T_{classifier}+\sum_k\pi_kT_k+E[T_{check}+T_{fallback}].
\]

和不分类的 fixed-route 策略比较时必须计入 encoder 与 gate diagnostics；若所有 easy cases 也跑一次昂贵 full-wave check，可能吃掉早退收益。区分 guaranteed conservative route 与 empirically calibrated fast route，不能混用其可靠性声明。

## 5. 首轮判定

如果规则已经能完成路线分配，不训练 classifier。若规则过于保守但 data labels 充分，再检查学习器是否降低 expected time-to-acceptable-image 且不增加 false accept。classifier 不能挽救完全没有 one-shot headroom 的 backbone。
