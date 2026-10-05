# ORACLE / OFFLINE / DIAGNOSTIC ONLY

此 oracle 只使用同一冻结 state 的已保存受约束 full-GN reference `s_F`，未更改 teacher、reference definition 或优化器。它不是 deployable algorithm、候选排名、runtime 赢家或 NN 训练目标。

normalized `s_F` 是材料 probe；六源 `K B s_F` 是待保护的 current block。raw M4 的压缩确实丢失目标信息，因此从第一个 late state 起触发 O3/P3/M6 degree3 保护组和同配置 random 控制。保护组 actual rank=56，与 baseline 一致；target source-rank 保留，没有补列或改 feedback depth。

|parent|FIXED H-error|raw oracle H-error|protected oracle H-error|protected random H-error|protected `J_m s_F` tangent error|
|---|---:|---:|---:|---:|---:|
|2001|269.5060%|267.5646%|366.1017%|213.2166%|0.0287410%|
|2005|449.6881%|386.8886%|478.2921%|536.5689%|0.0506824%|
|2003|146.1566%|153.2383%|174.0122%|147.9917%|0.3131406%|
|2007|336.4518%|312.7750%|380.3798%|356.7830%|0.0486763%|
|2013|156.4937%|157.1491%|172.3859%|179.9114%|0.0137507%|
|median|269.5060%|267.5646%|366.1017%|213.2166%|0.0486763%|

五个 late oracle 的材料 span、initial qM 和 final Z capture 都通过 `1−1e-8`，非零 target 无 floor 替代。保护组的六源 KB capture 在数值精度上为 1。负向质量现象因此不能归因于“oracle probe 被 M4 偷偷丢掉”；raw M4 的失败也没有被拿来直接判 KILL。

保护 oracle 没有任何 parent 达到相对 FIXED 降低≥50%；同配置 random 控制也没有提供 material localization 修复的证据。方向上的正向 tangent 却恢复得很好，说明**目标 current response 的捕获**与**整个 reduced GN 子问题产生正确更新**是不同命题。完整模型还需要正确的 residual pullback 和其它材料方向的曲率；本实验没有测定这几项各自的因果贡献。

正式 oracle Gate A 仍为 **HOLD**。late 质量数值为 FAIL，rank/捕获条件满足；但 early baseline 复现冲突触发了停止规则，要求的全十 state 保护/control 矩阵不完整。选择 **D — INCONCLUSIVE**，不绕过这一前置条件选择 C，也不声称 OPM 一般意义上无法表达正确 current。

full reference、oracle target 与 truth 的读取只在离线 evaluation/protected-oracle 路径。合法 FIXED/WIDE/CHEAP builders 收不到 full J/H、full gradient、teacher step 或 truth，runtime scope 拒绝 full tangent/adjoint。完整 costs、QP/KKT、norm/cosine 和失败记录在原始 JSONL。没有新增 full-gradient seed、M8 sweep、O/P sweep、degree>3 或 NN。
