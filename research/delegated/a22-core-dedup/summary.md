已完成本地 SLSQP 输入的精确重复约束去重。仅修改 `src/a22/core.py` 与 `tests/test_a22_core.py`；未修改 evaluate、CLI、协议、scientific config 或当前远端执行代码。父线程决定是否在验证后使用。

去重只在受约束 SLSQP 分支执行：对拼接后的 `[C | lower]` 使用 `np.unique(axis=0, return_index=True)`，按首次出现索引排序恢复原顺序，再把对应行传给原 `LinearConstraint`。不使用舍入、近似比较、归一化或容差合并。同系数不同行下界，以及哪怕只差一个浮点 ULP 的行/下界，都会保留。

完整原始 `C` 和 `lower` 始终保留。直接 SPD 解的可行性判断、最终 `_normal`、非负乘子、complementarity、full KKT、active-equation 修复均继续用完整约束。目标函数、H、g、lambda、初始化、SLSQP options、可行性和 KKT 容差没有改变。结果新增 `original_inequality_count` 和 `solver_inequality_count`；直接 SPD 分支后者为 0，表示没有向 SLSQP 提交不等式，SLSQP 分支则记录实际去重输入数。

新增 3 个局部矩阵 unittest：严格凸解析最优解 `[.25,.75]` 与未去重 SLSQP 参考比较、原始完整约束的 multipliers/normal/complementarity/KKT 审计；精确重复之外的 near-duplicate 行与不同 lower 原样到达 solver；直接 SPD 分支完整审计及计数。prepared core tests 总数为 16。最终 AST 检查通过；这些测试、物理计算、SSH 和 GPU 均未执行，不作运行时间改善或实际实验验证结论。

`CPU_RECEIPT.json` 是新的独立源代码工作 scope，保守计 3.0 秒 CPU、0 GPU；观察到的 AST 进程 CPU 为 0.031871 秒。仅登记本 scope 一次，不重复既有 worker 或远端 screening 费用。
