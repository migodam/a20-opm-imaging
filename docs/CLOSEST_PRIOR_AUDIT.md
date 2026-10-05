# A20 Route A：有界最近先例证据审计

审计日期：2026-10-05。范围冻结为协议 R04、R05，并补 R06 摘要作两侧矩匹配背景。本文件交付文献事实与声称边界；最终 novelty、机制有效性及 G0–G3 判断由主线程 Codex 负责。

## 检索及访问状态

使用 scholarqa-research 的 Evidence QA 流程。两条精确标题查询的 snippets/papers 四个操作全部返回 HTTP 429，未形成候选集；没有扩展文献网络。随后 ScholarQA `verify` 对三个预定 arXiv ID 成功解析 3/3，`unresolved_ids=[]`。身份核验与声称核验分别进行：R04/R05 由 arXiv 原文定位，R06 仅为摘要级证据。原始响应、查询、访问缺口及 CSV 证据账本在 `research/claim_audit/`。

R04 的 Semantic Scholar 年份为 2013；arXiv 同时登记 2015 年期刊版本及 DOI。两者是版本/发表年份差异，不能把本次读过的 2013 原文说成已核对期刊所有内容。[R04 版本记录](https://arxiv.org/abs/1311.0922)

## 目的—机制—评价 facets

| 文献 | 目的 | 机制 | 评价与限界 | 证据 |
|---|---|---|---|---|
| [R04](https://arxiv.org/html/1311.0922) | 降低非线性 DOT 反演的前向/Jacobian 成本 | 参数/频率 solved snapshots 的左右投影；固定全局基；插值点导数匹配 | 四个二维合成重建；组内复用基；大系统求解计数。无 Maxwell 结论 | A：§2.1、§3、§4 |
| [R05](https://arxiv.org/pdf/2003.10938) | 监测 ROM 失真并减少扩基求解 | 随机组合源估计；拒绝/扩基；TREGS 条件模型；残差驱动更新 | 二维/三维 DOT，主要成本为到 1.1 噪声残差的全阶求解数；未重跑 | A：§3–§6 |
| [R06](https://arxiv.org/abs/2212.08589) | 数据驱动的两侧矩匹配 | 线性系统时域样本与渐近匹配 | benchmark；不是 A20 幂链命题的逐条证明 | B：摘要 |

## 可以引用的碰撞，不能越过的边界

R04 的 Theorem 1 已建立符合 span 包含及可逆条件的前向、参数及频率导数匹配。其 §5 将 tangential interpolation 列作后续扩展，当前实现是 full-matrix interpolation；“首次 reduced forward + GN/Jacobian”没有此证据支持。[R04，§3.3 与 §5](https://arxiv.org/html/1311.0922)

R05 §4.1 明确把放松一阶条件的概率扩展留待后续；§5 讨论样本数和检测概率。因此其随机模型监测不能直接当成 A20 全物料 Jacobian/KKT 的确定性证书，也不能引用为已完成该随机算法所有收敛证明。[R05，§4.1 与 §5](https://arxiv.org/pdf/2003.10938)

## 经典代数与 Maxwell 实证的分界

A20 协议的 `C_s F_eff^k B_s` 有限幂等式依赖准确左右 span 包含；对应形式变量 z 在零点的局部矩匹配。z 不是自动等同于物理频率/物料对比度，有限矩匹配也不保证 z=1 的任务误差。R04 的频率/参数插值和 R06 的渐近不同插值点匹配提供相邻机制，不可将其假设直接移植。此项是协议与已定位先例的对照说明，不是本 worker 的新证明或全球优先权判断。

R04 的 B 是已知照明端口；A20 的 B 是物料导数注入。映射须保留 `B=b′−L′j`、真实物料回拉、噪声白化及当前坐标度量。现有 DDA 后端的物料作用经 polarizability α(χ) 实现，不能直接以 diag(χ) 替换。

A20 尚需由自己的 G1/G2 结果证明：独立三维矢量 Maxwell 最终物料重建、对同约束 full GN 的质量、对等 rank/action 通用 ROM 的差异，以及含构基、白化、因子分解、审计、刷新、失败回退的总部署成本。文献的求解计数不能代替该墙钟目标。G3 还需完整物料/KKT 审计与全目标接受；相邻 degree 平台不足以停止。以上都保持“待实证”，本审计不关闭任何实验 gate。

## 无法验证项

没有独立复现实验，没有核对 R04 期刊正文的版本差异，没有审计所有概率证明。R05 的 PDF 文本可读，但截图工具不可用，因此未视觉验证公式、图或表。R06 全文与后来期刊版本未在本轮读取。HTTP 429 意味着检索覆盖受限；本文件不是全面或系统优先权检索。

## 已验证身份

- R04：Eric de Sturler、Serkan Gugercin、Misha E. Kilmer、Saifon Chaturantabut、Christopher Beattie、Meghan O’Connell；arXiv 2013，SIAM J. Sci. Comput. 37(3), B495–B517 (2015)；[DOI](https://doi.org/10.1137/130946320)。
- R05：Drayton Munster、Eric de Sturler；[arXiv:2003.10938 (2020)](https://arxiv.org/abs/2003.10938)。
- R06：Junyu Mao、Giordano Scarciotti；[arXiv:2212.08589 (2022)](https://arxiv.org/abs/2212.08589)。
