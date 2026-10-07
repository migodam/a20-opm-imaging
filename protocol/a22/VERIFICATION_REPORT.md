# 已执行 verification：范围、数值与复现

## 范围

运行环境为本对话的 CPU 数值环境；依赖 NumPy 与 SciPy，不使用 GPU、不训练模型、不连接用户本地研究目录。seed=20261007。

从本包根目录运行：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python verification/verify_theory.py
```

输出写回 verification/results.json。代码使用 assert 验证关键 identity、导数和界；随机 toy cases 的结果只检查实现，不替代一般数学证明。

## Algebra checks

| 检查 | 实际结果 |
|---|---:|
| Two-sided defect relative error | 5.0314e-16 |
| RLR=R relative error | 2.5731e-16 |
| two-sided defect actual/bound | 0.34490 |
| factor finite-perturbation actual/bound | 0.14831 |
| gauge product error | 0 |
| gauge raw injection norm ratio | 0.01 |
| gauge metric-corrected norm error | 0 |
| two-frequency joint profile sensitivity | 1.41421 |
| common-dual nonlinear example one-shot max error | 0 |

alias example 的两列 norm 约为1，profile g≈0.001。noise std=0.001 时理论 coefficient variance=1.000001，100000次噪声抽样 empirical variance≈0.997955。该例验证检测强度与可归因精度不是同一量。

其余反例包括：finite-amplitude prior leakage；Born-anchor scalar one-shot 错误；ROM-null/full-bright；中间 Gram 不可共同正交对角化的例子。它们的确切参数与输出均保留在脚本/JSON中。

## 三维矢量 coupled-dipole 检查

8个等向性极化粒子位于 (±0.09,±0.09,±0.09)，长度按背景波长归一化，k=2π，每粒子volume=0.08³。采用 radiation-corrected Clausius–Mossotti polarizability，3个illumination、6个receiver，各receiver保留3个矢量分量。

复 current dimension=24；堆叠复data dimension=54；known-background浅OPM rank=18。材料是8个实参数，带固定0.03i耗散。它是具有vector Green coupling的粒子模型，不是网格收敛后的连续介质三维Maxwell成像验证。

| 检查 | 实际结果 |
|---|---:|
| material tangent central-difference relative error | 7.3156e-11 |
| two-sided defect relative error | 2.3335e-15 |
| reduced tangent relative error | 0.15818 |

reduced tangent 误差约15.8%，不是一个“高精度ROM已通过”的结果。identity 精确与approximation准确是两件事。

取4个physics coordinates，对同一单位材料方向的4档幅度：

| amplitude | physics coefficient error | 验证用误差上界 |
|---:|---:|---:|
| 0.005 | 1.82903e-4 | 1.09845e-3 |
| 0.02 | 7.34171e-4 | 4.47712e-3 |
| 0.08 | 3.02265e-3 | 1.92550e-2 |
| 0.32 | 1.59594e-2 | 9.94582e-2 |

这些 upper bounds 使用已知full derivative与truth perturbation，仅验证公式。线上只有在得到合法、成本可接受的误差envelope后才可声称有certificate。

## 不代表什么

没有验证项目级 recoverability correlation、physics/prior error separation、one-shot support headroom、NN sample-efficiency、OOD robustness、posterior multimodality或GPU time-to-image。不得将这些 tiny tests 写成 Gate A/B/C PASS。

## 补充代数测试

第二脚本 verification/verify_additional.py，seed=20261008，输出 additional_results.json。T5 的 λ=0/0.01/0.5 下 actual/bound 分别约0.11425/0.22750/0.60498，nuisance leakage 均小于7e-16。T8 compressed likelihood identity relative error≈1.54e-16，完整Schur assembly relative error≈2.16e-16。T6的二次例子在r=0.173205时恰达到τ_add=0.03。

## T10 的补充检查

第二脚本还包含 seed=20261010 的 normalized-current 随机复矩阵测试：task-curvature identity relative error 为3.61e-14；真实 witness nonlinear error 为0.0141477，精确配对上界为0.0585160，reduced primal/dual residual 上界为0.178649。actual/bound 分别为0.24177与0.07919。此处是随机矩阵代数测试，不是额外的 Maxwell 场景；full inf-sup 常数和指定材料扰动只作为验证输入，未证明可在线免费获得。
