# 缓存共同 QP 的复现冲突与显式处理

这项补充在任何 Test A split 指标或 Test B 受限解生成前登记。原 `SUBSPACE_SEPARATION_PROTOCOL.md`、配置、两次失败及其阈值完整保留，不把严格标量复现改判为通过。

## 发生了什么

Mac 的 2112 个共同解全部通过原 QP/KKT 合同，但 104 个案例超出冻结的旧标量复现容差。原 Windows/Python/NumPy/SciPy 环境复算后，2112 个解仍全部通过原合同，26 个案例超出该容差；最大完整材料误差差值为 `1.631117072381505e-7`，target coefficient 差值为零。两次均在 Test B 之前停止。缓存 AW 的元素与 NPY 布局相同，正则化公式及源代码保持不变。

小规模探针显示，完全相同 AW 元素的不同内存布局可以改变原 SLSQP 的迭代停止点；部分点的原/新 defect 都在原 `1e-8` KKT 门槛内，而标量差大于 `1e-8`。这不能证明旧与新目标不同，也不能证明所有差异已被唯一解释。旧 Stage A 没有保存全向量、完整 in-memory arithmetic 或梯度，因此不能复原旧停止点。

## 冻结处理

1. **严格历史标量复现仍为 FAILED。** 旧记录不覆盖，失败成本不删除。
2. 直接子空间实验只使用原 Windows 的整组共同解，路径固定为 `results/a22_r1/replay/20261007T164205Z_d1452c27461b/COMMON_32D_CASES.jsonl`。不逐案例挑平台、挑最小误差或再求共同解。
3. 在 Test A/B 前重新用缓存 AW/data、原 full-scene lambda、原约束及保存的 normal，检查每个共同解的 quadratic、可行性、stationarity 与原 KKT 合同。任一个不合法即停止；**不放宽 KKT、feasibility、score 或物理阈值**。
4. Test A 投影上述同一个共同解；Test B 用原 solver、同一个 lambda 和同一个可行域求受限解，Mac 平台单独注明。在线 split 和主 k/gates 不变。
5. 两个平台共同解都保留。报告明确区分“直接子空间诊断结果”与“历史标量严格重现失败”。此处理不能作为 bitwise Stage A 复现或正式独立验证的证据。

这是对额外实现复现检查与原求解容差之间冲突的显式处理，不是对科学筛选 S1–S4 的结果后修改。没有新的 full-wave label、Maxwell run、NN、排名校准、rank/degree 增加、fallback 或 nonlinear solve。
