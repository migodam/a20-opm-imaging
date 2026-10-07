已完成 FULL_J_TOTAL 的纯统计扩展。只修改 `src/a22/statistics.py` 和 `tests/test_a22_statistics.py`；未修改 physics、budget、CLI、scientific config 或其它 agent 文件。已有 `full_J` 输出名称保留；新常量 `FULL_J_TOTAL` 的 method string 为 `full_J_total`，检测规范列 `pred_full_J_total` 及独立别名。两者均标记为 `offline_full_J`，不会相互覆盖。

父线程提供的来源语义：`pred_full_J_total` 是 offline total response/sensitivity ridge baseline，`pred_full_J` 是 offline nuisance-profiled full-J witness。本模块仅消费预测字段，并未读取 full-J 矩阵或科学 labels。新比较项沿用已有的 draw 平均、有效性要求、每方法单一非负无截距乘数、screen LOSO、formal development-only 拟合、calibration/evaluation 不调参，以及 scene/family/noise-zero 分支统计。字段不存在时不生成该比较项，缺失 draw 保留审计并使该方法对应聚合单元不可用。

正式 `paired_scene_bootstrap` 与 `primary_incrementality` 仍明确只使用 A1、A2、A3。两个离线 full-J 比较项都不参与更强 A1/A2 基线选择，也不会因自身缺测删掉可用的在线配对。该规则未改变。

新增 3 个合成 unittest：多个 draw 先平均再拟合（单元拟合得 scale 4，而原始 draw 拟合会得 3.2）、同容量离线标签及 LOSO/family/noise 分支、formal calibration/evaluation 无法改变 development scale、total 单个 draw 缺失不影响 profiled witness 或在线配对。Screen 和 formal 均比较新增列前后的完整 bootstrap/primary 结果，要求正式增量证据完全相同。统计测试总数为 22。

最终 AST 检查通过；统计、unit tests、SSH、physics、GPU 均 NOT_RUN。已通知 `a22_asset_inventory` 使用 method string `full_J_total`、离线 scope 及上述 source-only 语义；reporting schema/图由该 agent 维护。新独立 `CPU_RECEIPT_FULL_J_TOTAL.json` 保守计 3.0 秒 CPU、0 GPU，仅登记一次；不重复既有 15 秒 statistics 或其它 worker/remote 费用。
