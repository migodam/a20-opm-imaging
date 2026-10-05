# Late-state seed anatomy：结果与有效范围

正式四选一结论为 **D — INCONCLUSIVE**。五个 Gaussian parents 的 late endpoint 已完成，但第一 early-state baseline 未通过冻结复现门槛，协议要求停止判决。不能据此宣称材料瓶颈被确认、history 因果被确认，或正式执行 representation KILL。

## 已完成的主结果

固定对象 2001、2005、2003、2007、2013，iteration17，六种方法各五次，共 30 个有效 QP。全部 actual current rank=56，六 illumination 同时注入；没有 full fallback、Petrov 或 empty-U fallback。原参考的 late KKT 最大 1.67986e-11；本次 30 个 reduced QP 的 KKT 最大 9.02584e-9，均满足原 1e-8 门槛。参考 H-norm 在 5.79730e-4 至 3.63239e-3，远高于冻结 1e-12 floor。

|方法|late median relative H-error|相对 FIXED median 的下降|final-Z KB-reference capture median|reference-direction tangent error median|
|---|---:|---:|---:|---:|
|FIXED-DEEP|269.5060%|—|0.189730|683.6001%|
|WIDE-M|209.5953%|22.2298%|0.310707|1016.0053%|
|CHEAP-TASK|235.1696%|12.7405%|0.206105|706.4082%|
|HISTORY|NOT_RUN|无自身 accepted trajectory|—|—|
|ORACLE-M：OFFLINE DIAGNOSTIC ONLY|267.5646%|0.7204%|0.486396|763.9789%|
|PROTECTED-ORACLE：OFFLINE DIAGNOSTIC ONLY|366.1017%|恶化 35.8417%|1.000000|0.0486763%|
|PROTECTED-RANDOM：同配置离线控制|213.2166%|20.8862%|0.216253|748.2907%|

数值是五个已暴露对象的描述性中位数，不是盲测或推广性证据。原始精度、逐 parent 结果、绝对 H-error、直接 quadratic gap、full stationarity/KKT、material cosine、H-angle、norm ratios、full-objective slope 和 one-step truth diagnostic 均在 `results/a20_r1/anatomy/rows.jsonl` / `results/a20_r1/report/ANATOMY_RAW.csv`。truth 只用于离线诊断，不参与 primary gate 或 seed 构造。

## 信息在哪里丢失

原 M4 oracle 虽然包含正确材料方向，但六源 KB block 的 qM 能量捕获只有 0.339894–0.554010。material-span capture 接近 1，不能代表压缩后的 current excitation 完整。因此 raw oracle 失败不能直接判 representation 死亡。

保护组把 qM 与 final-Z 的六源 KB capture 恢复至数值精度上的 1。与此同时，`J_m s_F` 对 `J_F s_F` 的误差降至 median 0.0486763%。**正确方向上的正向切线可以被保住，但优化后的 GN 步依然很差。** 这比单看 H-error 更明确地分开了输入压缩与整个二次模型的 fidelity。

一条方向上的正向等价不保证 minimizer 等价。full step 的受约束 stationarity 使用

`J_F^T (r + J_F s_F) + lambda s_F + ell + n_F = 0`。

即使 `J_m s_F ≈ J_F s_F`，也不能推出 `J_m^T(r + J_m s_F) ≈ J_F^T(r + J_F s_F)`。其它材料方向、残差上的 pullback、normal matrix 和 conditioning 仍可能有误差。该解释是由已测量结果和方程作出的推断；本实验没有另做 O/P sweep 或 full-gradient 诊断来定位这些项。不能把 forward capture 通过等同于完整 reduced GN 模型通过，也不能把失败提升为“任意 OPM current 空间都无法表达正确方向”的定理。

## 停止原因与缺失

第六个 state（2001/0）的新 FIXED-DEEP step 相对历史 step 误差 1.670492e-6 >1e-9。其 relative H-error 为 1.3247119927%，历史为 1.3247070235%；差异很小，但冻结的精确复现条件确实不满足。两次模型 QP 都通过原 KKT。这是 **baseline 复现冲突**，不是把本次 QP 当作优化器失败。

本次实际构造/求解 31 个候选：30 OK，1 baseline FAILED；其余 29 个记 NOT_RUN。另有十个 HISTORY 快照 NOT_RUN。只审计了实际访问的六个已有 full references，未运行的四个 early references 保留未审状态，未重生成 teacher。

原 replay 对 retained U 多一次 SVD 正交化，原 imaging/R1 直接使用 receiver U。这是确认的实现接线差异；它或 SLSQP 的有限精度敏感性是否导致失配，尚无因果证明。未在看到结果后调整 gauge、KKT 或复现容差，未追加物理重跑。`SOURCE_CONFLICTS.md` 保存具体审计。

## 门槛与研究动作

- Gate A：late protected oracle 的质量条件实测 FAIL；正式 A=HOLD，因为 baseline guard 停止且 protected early/control 矩阵未完成。
- Gate B：WIDE-M 与 CHEAP-TASK 的五对象 late cohorts 均完整、均 FAIL；既未达到 50%，也未降低 70%。
- Gate C：HOLD，缺少有效完整 early cohort；不拿历史 early 中位数冒充本次候选结果。
- Phase2、history ablation、部署 GO、NN：NOT_RUN。不存在合法 winner，不能启动 nonlinear imaging 或 NN。

这组数据反对“仅加一个理想材料方向就会修复 late GN 更新”的简单解释；完整机制裁决仍被冻结复现门槛阻断。正式结论保持 D，不以负向描述性结果替代已注册的裁决条件。

图 A–D 和额外 capture-certification 图位于 `figures/a20_r1/`；CSV 保留 NOT_RUN/FAILED，绘图不填造 early 数据。
