# Time-to-image：只比较达到同一质量目标的端到端成本

## 1. 本轮没有实测加速结论

本包只有 CPU tiny verification，没有用户仓库的 Full GN、OPM-GN 或 RTX 4060 成像计时。上传任务中的 late-state fidelity collapse 是背景证据，不自动证明 outer iteration count 已增大，更不证明新方案已经更快。

## 2. 正确成本账本

\[
T_{shot}=T_{pilot}+T_{background}+T_Q+T_{material\ basis}
+T_{diagnostics}+T_{small\ solve}+T_{decode}+T_{check}+T_{fallback}.
\]

iterative 方法应按真实迭代求和：

\[
T_{iter}=T_{init}+\sum_{k=1}^{N_{outer}}
(T_{state,k}+T_{tangent,k}+T_{solve,k}+T_{line\ search,k})
+T_{final\ check}.
\]

只有各步成本近似恒定时才简写 N_outer×T_step。line-search 额外 forward evaluations、Q refresh 与失败 steps 都不能省略。

一个 Full GN 与 OPM-GN 的近似 break-even 条件是 N_R/N_F < T_F,step/T_R,step；还要加上两者不同的 initialization/refresh 成本。它说明 per-step savings 可能被 outer inflation 抵消，而不是证明这种抵消已经发生。

## 3. 必须区分四种计时

**Cold start**：新背景/几何，没有可用缓存。**Warm start**：合法复用背景、算子或材料基。**Marginal inference**：固定 encoder 后每幅图成本。**Amortized cost**：离线预计算/训练成本除以实际处理图像数后加线上成本。

若 NN 离线成本 T_train、单图节省 ΔT，则仅就计算成本需要图像数超过 T_train/ΔT 才摊销；该算式不包括数据制作和人工成本。文章应同时报训练与数据生成，不只报 network forward milliseconds。

## 4. 统一 acceptable image 定义

用预注册任务质量阈值、data discrepancy 和材料可行性联合定义 success。默认候选可见 GO_NO_GO_GATES，实际阈值须在 test set 开封前冻结。

记录：达到阈值的首次时间 T_hit，最终 error，截止时 success/failure，total wall time，forward/adjoint solves 与 RHS，G/S/B actions，outer iterations、line-search trials、non-descent/rejected steps、GPU peak memory。

未达标不能被赋予一个很短的 time-to-image 后参与平均。报告 success rate、成功样本的 p50/p90、全部样本的时间–成功率曲线，以及有明确 timeout cost 的 expected time-to-acceptable-image。不同方法到达不同精度时，使用 error-versus-time Pareto 曲线，不报一个误导 speedup。

## 5. 最小 iterative-ROM 风险审计

优先找已有可比 logs；不足时挑最多 6 个分层 scenes（weak/moderate/strong，各 2 个），相同初始图、数据、regularization、constraints、stopping tolerances 与硬时限，比较 Full GN 与 OPM-GN。

每个方法记录实际 N_outer 和 line-search failures。若 OPM 每步便宜但总成本更高/更常失败，将 iterative OPM-ROM 降为 secondary baseline。若日志不足或运行达到预算上限，状态是 NOT_ESTABLISHED，不把未完成当成已证明的 failure。

Full GN 与 DBIM 不必人为分成两个重复基线：只有仓库中它们确为不同实现/目标函数时分别比较，并记录定义。SOM/CSI 等作为背景与算法定位，不为本轮新增完整重实现 campaign。

## 6. 第一轮预算

所有数值预算是上限，而不是已经消费或预计必能完成的时间。单台 RTX 4060 的新 GPU-associated wall time 设硬停止 9 小时，预留 1 小时不执行，保证不超过用户的 10 小时边界。

| 环节 | 新 GPU 占用时间上限 |
|---|---:|
| 4-scene screening 与数据/算子健康检查 | 0.5 h |
| 缓存 features、small-basis diagnostics | 1.0 h |
| 有限幅度与 noise direction tests | 2.0 h |
| one-shot headroom 与真实数据检查 | 1.5 h |
| 最多 6-scene runtime audit | 2.0 h |
| gates 通过后才允许小 MLP pilot | 1.5 h |
| 日志/异常预留 | 0.5 h |

若每次 full-wave evaluation 比预期慢，按顺序缩减样本/标记 PARTIAL，不自动降低 solver accuracy 来赶预算。不新增大数据集；NN 只用已有合法 cache，缓存不足则不训练。文献与小矩阵证明检查不需要 GPU。

## 7. Route verdict

Primary 是 one-shot 的质量–成本 pilot；不是预先宣布它击败 Full GN。若仅在近 truth 的 oracle anchor 上省时，部署结论为 NO-GO。若一次物理修正后稳定有益，则可保留 honestly named two-shot route。若必须恢复大量 nonlinear iterations，则本轮 fast one-shot framing 未通过。
