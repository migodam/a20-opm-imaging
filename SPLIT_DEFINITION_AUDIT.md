# Split definition / information audit

所有方法都在原 `online_split_16.npz` 中 `[V_phys,V_prior]` 的有符号、完整32列基底上选列。材料W/体积metric、六源逐源Re/Im packing、known background、whitening与lambda固定。RANDOM用单个固定排列，k8/k16嵌套；没有dense k sweep。

A1/A2/A3原公式、原预算和descriptor不变。旧缓存没有32方向预算，因此只补全同一个候选池；冻结排序条件是amplitude0/noise1/nominal，不据恢复误差定条件、不拟合校准器。raw预算越小排名越前，按candidate index稳定打破并列。声明的有限材料prior半径仍在预算中，不能称为零先验测试。

在线builder只能读取已知几何/背景、合法测量/配置及OPM因子，拒读truth、full-J/H、full gradient、GN optimum、teacher。此处split不依据truth或full32恢复输出。全局online freeze后才读取旧label和fullJ到独立offline evaluator。OFFLINE_FULL_J以full-J regularized witness预算对同一32候选排序，明确不是deployable。没有为fullJ再生成任何数据。

完整indices、raw scores、scope、随机种子与cache来源在[SPLIT_FREEZE](results/a22_r1/SPLIT_FREEZE.json)、[OFFLINE freeze](results/a22_r1/OFFLINE_SPLIT_FREEZE.json)及相应NPZ。Window/Mac的offline浮点平台变体单独保留在platform_variants，不覆盖冻结online split。需要按候选frame限制解释结果，不能将OFFLINE诊断等同任意优化LIS。

Test A先读取整组固定共同解；Test B保持同一个物理目标/原lambda，仅限制解空间。拒读、预算、packing、noise方差1/2、零分母、QP失败与旧源码不变均有测试。任何正规新验证/训练要重新审计数据边界，本experiment不自动执行。

严格历史标量复现失败保留；explicit处理见[REPRODUCTION_CONFLICT_ADDENDUM](REPRODUCTION_CONFLICT_ADDENDUM.md)，在split指标之前提交，S1–S4与评分完全未改。
