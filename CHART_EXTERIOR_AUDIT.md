# Chart-exterior audit

材料扰动严格分成 `chi-chi0 = W x + chi_outside_W`。W是固定质量正交32维实chart；本实验中的V_prior只是W内部的补空间，不包含chi_outside_W。

| scene | 原对象图内能量 | 原对象图外能量 | 有限幅度案例图内能量范围 |
|---|---:|---:|---|
| 2001 | 0.46491 | 0.53509 | 0.437996 – 0.664334 |
| 2003 | 0.489802 | 0.510198 | 0.486287 – 0.524213 |
| 2014 | 0.0576533 | 0.942347 | 0.0590951 – 0.169029 |
| 2009 | 0.133728 | 0.866272 | 0.134163 – 0.178295 |

这些比例是原对象相对已知背景的material energy，不是重建成功率。finite cases继承原材料并加W内扰动，因此覆盖会变化，但图外部分保持原样。audit共有4个原对象+32个finite labels，projection、orthogonality和能量identity一致。原始值见[CHART_EXTERIOR_RAW.csv](results/a22_r1/CHART_EXTERIOR_RAW.csv)及[JSON](results/a22_r1/CHART_EXTERIOR_RAW.json)。

完整finite材料向量未独立保存；这里按已保存的original_material与perturbation_coefficients生成规则核验，没有声称这是独立新full-wave证据。它只隔离已有chart外误差，不对图内split提供额外评分或使用truth选方向。

已有full-wave data仍包含原对象的chart-exterior材料。把它的能量排除出V_prior指标，不能消除它对测量和图内恢复的散射影响；这里没有生成W-only新labels来隔离这种污染。因此结果属于实际既有有限幅度/噪声/校准条件下的图内恢复，不是消除了所有图外nuisance的内在可识别性定理。

Gaussian chart只覆盖约46–49%，2014约5.8%，shell约13.4%；即使一个图内split有效也不能据此宣称完整原对象成像有效。图外能量不能被算作V_prior失败，任何完整图像主张需另行扩展材料chart并独立验证；本experiment不自动做这件事。
