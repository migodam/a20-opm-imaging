# Prior-only neural decoder：硬保护与有限幅度安全性

## 1. 模型

冻结本次样本的 material split 与 physics estimate，令

\[
\widehat x=V_p\widehat a+V_n b_\theta(z_{enc}).
\]

若 prior eligible directions 只有 V_n 的一部分，再用 eligibility mask 或小基 V_e⊂V_n。其余 model-unresolved directions 不能由一个 generative branch 自动获得真实性保证。

第一版选择 deterministic MLP。建议候选是 input→128→128→q，或 input→256→128→q；参数量、训练时长和数据量都纳入公平比较。这是实验默认值，不是已经调出的最优结构。

输出可以是标准化 coefficient residual，但最终始终经过明确的 V_n mapping，不能在后面再接 unrestricted image residual。χ₀ 与 Cχ 的定义沿用 THEORY 文件。

## T6a. 材料分量的精确保护

若 V_pᵀV_n=0，则对任意 bθ，

\[
V_p^T\widehat x=\widehat a.
\]

证明只有一行：左乘 V_pᵀ，利用正交性。该结果与 NN 是否训练良好无关。

这是 **coordinate preservation**，不是“该坐标已是真值”。在平方误差下，

\[
\|\widehat x-x_*\|^2
=\|\widehat a-a_*\|^2+\|b_\theta-b_*\|^2
\]

在声明的完整 split 内成立；若有 W 外部残差，再加其平方范数。因此 prior-only decoder 的误差下限包含已锁定的 physics error。Gate C 不通过时训练更强 NN 不能突破这个下限。

## T6b. 有限幅度 data-consistency budget

以下在已经归一化材料坐标和白化数据空间内写 F。设 J 的 Lipschitz 常数为 K_J，整个连接路径位于该界适用的区域。令 physics image 为 x_p，OPM linearization anchor 为 x₀，h=V_n b，||J(x₀)−A||≤ε_R。则

\[
\|F(x_p+h)-F(x_p)\|
\le a\|b\|+\frac{K_J}{2}\|b\|^2,
\]

\[
a=\|A V_n\|+\epsilon_R+K_J\|x_p-x_0\|.
\]

**证明。** Taylor 积分余项给 `F(xp+h)−F(xp)=J(xp)h+r`，||r||≤K_J||h||²/2。J(xp)=A+[J(x₀)−A]+[J(xp)−J(x₀)]，逐项上界后使用 ||h||=||b||。证毕。

若能获得仅在 V_n 上的 ROM bound，用 ||(J−A)V_n|| 代替全局 ε_R，会更紧。更进一步可针对实际 b 用双向 residual bound，但必须保留其可信度标签。

给允许增加的数据误差 τ_add≥0，可取

\[
\|b\|\le r_{max}=\frac{2\tau_{add}}{a+\sqrt{a^2+2K_J\tau_{add}}}
\]

在分母非零时。这与解二次不等式等价，数值上避免两个接近量相减。若 K_J=0 且 a>0，rmax=τ_add/a。a=K_J=0 时数据约束不再限制幅度，但材料可行域和定理适用区域仍限制它。

必须考虑已有 residual：`||F(xp)−y||+τ_add` 才是最终保守 discrepancy bound。不能只证明新 correction 的数据变化小，就称最终数据一致。

**反例。** F(a,b)=a+b²，在 b=0 处 prior direction 一阶完全不可见，b=0.5 却改变数据 0.25。硬锁定 a 并不能消除这个变化。验证代码包含此例。

## 2. 材料可行性不能破坏硬保护

独立逐 voxel clipping、positivity activation 或重新归一化通常不与 P_phys 对易，因此可能改写 physics coordinates。应在 b 坐标内处理约束：

\[
\min_b\|b-b_\theta\|^2\quad
\text{s.t. }\chi_0+C_\chi(V_p\widehat a+V_nb)\in\mathcal C,
\quad \|b\|\le r_{max}.
\]

线性 box constraints 时是小 QP/凸可行投影。若无可行 b，说明当前冻结 physics estimate 与约束冲突，应该返回失败或启动一次物理修正，而不是偷偷修改 a。涉及 Gaussian shape 等非线性材料参数时，可行域处理需相应改变。

## 3. 训练目标与数据来源

监督标签为 b_*=V_nᵀx_*。主 loss 用 coefficient error，配合物理单位对应的材料误差。不能用 `V_nᵀ(x_*−x_phys)` 的简化写法掩盖基不正交或 anchor 改变；先统一坐标。

缓存可用时加入实际 nonlinear data consistency loss；没有真实 forward evaluation 时，只能称 reduced-data loss。不得以“physics-informed loss”宣称已经验证真实 Maxwell consistency。物理保护由结构保证，不依赖加大一个软 penalty。

train/validation/test 按 scene 分割；同一对象的噪声 realizations、频率和近邻参数不能跨分割。PCA、standardization、rank thresholds、classifier calibration 都只在 train/validation 上拟合。

## 4. 必须有的比较

同一个 physics encoder 和同一批训练场景下，比较 whole-material MLP、prior-only MLP、physics image + unrestricted residual decoder，以及 small A-SVD split + 相同 prior decoder。另保留 physics-only。

同时控制模型容量和训练时间，避免 prior-only 使用更少参数而 whole-image baseline 被故意设得过小。样本效率用至少两个训练集规模；第一轮可使用已有缓存 32/64/128 个独立场景，数量不足时只报告 pilot，不制造有统计效力的曲线。

输出指标：完整图像误差、projected physics/prior error、真实数据 discrepancy、physics coordinate drift、support false positives、OOD geometry/material performance、总 time-to-image。所谓 hallucination rate 需有明确判据，不把所有错误统一叫 hallucination。

## 5. Hallucination 与 uncertainty 的边界

建议把指标分成：protected-coordinate violation；在真值已知 simulation 中的 false support/material artifacts；measurement-inconsistent correction；在弱空间内虽数据一致但无证据支持的结构。最后一类不能仅凭 residual 自动识别，需 truth-based evaluation 或 calibrated posterior uncertainty。

NN 不修改 V_p 能降低一种特定风险，但绝不保证 V_prior 的预测为真。若任务要求可信报告，应把 prior-completed 区域/坐标与 physics-supported 部分分别输出，而不是视觉上混成一个无差别 certainty map。

## 6. 文献边界

线性 null-space network 已经严格实现数据不变的 learned correction [R01]；非线性 data-consistent networks [R02]、DDN [R03] 与 NPN [R04] 也直接相关。因此本架构形式不是独立 novelty。OPM 的潜在贡献必须来自可计算的 material split、模型可信度、有限幅度安全预算，以及实验中的真实优势。
