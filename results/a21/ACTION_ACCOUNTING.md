# A21 动作与费用口径

物理执行只有 `a21-anatomy-01`，CPU267.359375秒、GPU占用281.661815秒。其 inclusive receipt 是执行时间的权威；嵌套 span 秒数不再相加。实际费用、保守 allowance 与失败一起计入独立 A21 budget，再加冻结历史 carry。

| 互斥 full-solve RHS 来源 | 数量 |
|---|---:|
| 五个 full states，六源各一次 | 30 |
| 五态 full-J，54材料方向×六源 | 1620 |
| 三个真实验证态追加 JVP | 36 |
| 三个真实验证态追加 VJP | 36 |
| 六源 primal oracle ×五态 | 30 |
| 六源 adjoint oracle ×五态 | 30 |
| 总 full RHS | **1782** |

receipt 中 `full_tangent_RHS=1656` 已含1620+36，`full_adjoint_RHS=36` 是验证VJP；`full_oracle_RHS=60` 已含primal30+adjoint30，不能再次把三个oracle counter相加。原 backend/native solver 对应同一组solve，也不能算第二份费用。

| primitive Maxwell vector actions | 数量 |
|---|---:|
| F | 163 |
| F* | 103 |
| L | 631 |
| L* | 171 |
| primitive合计 | **1068** |

`Maxwell_matvec_rhs=1068` 是上述aggregate，不能再加入。原full-state保存的 `full_state_backward_residual_L_rhs=30` 与 `full_state_Goff_rhs=30` 另列，是状态输出/残差审核的真实额外vector工作。将互斥primitive、full solve及这两类state工作汇总为2910个向量任务可用于检查完整性；不同任务成本不同，本实验没有把这个数当作速度收益。

receiver工作保留 `S_actions=481`、`S_adjoint_actions=153`，以及full-state receiver30、full-tangent receiver1656、full-adjoint receiver36；原state/切线内部receiver计数与外部Adapter receiver计数按既有分类报告。full LU恰好5次。投影factorization40次=5次baseline画像构建+35次主臂core。主 reduced QP恰好35次，没有reference repair。QR、projection、QP、cache写入、物理setup及接受历史均在797个cost events中留账。

全部35臂共享每态raw bank、LD/SD/DHB及X/Y。arm局部full RHS为0不意味着oracle免费：共享准备全部已经在同一物理job计费。CPU独立saved-array review另重建35个缓存small-core批次（35×324=11340 reduced RHS）并做小型Hessian诊断；该工作无Maxwell/full RHS/优化器调用，CPU单列于 `a21-local-array-review-01`。

三个原代码直接counter不进入cost event逐事件求和：L_upload_bytes=2149908480、operator_transfer_bytes=177168384、material_optimizer_iterations=1893。它们在inclusive receipt中保留；这是已有实现口径，无费用被删去。

本地完整验证、后续回归、报告、失败压缩归档和新STORED归档、文件审核、保守setup/metadata allowance分别留receipt。一次只读辅助计数断言失败未测得自身CPU，按14秒soft cap保守计费；其scope总14.147201秒只加一次。CPU是在GPU job中实际消耗的267.359375秒，不因为使用GPU而免计CPU。

预算权威见 [BUDGET_FINAL.json](BUDGET_FINAL.json) 和 [external scopes](external_cpu_receipts.json)。旧A20/R1账本不扫描重计、不重置、不覆写。
