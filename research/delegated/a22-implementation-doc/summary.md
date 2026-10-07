# A22 实现文档草稿交接

已写 `A22_IMPLEMENTATION_REPORT_DRAFT.md`，中文、仅说明实现事实和证据边界。五接口为 `build_anchor/build_opm/material_features/build_split/evaluate_recovery`；第五接口明确调用底层 `constrained_material_solve`，未替换用户命名。

覆盖固定 32 实材料度量、六源实化和 proper complex Gaussian 白化、固定浅层 O/P/M 与直接通路、online/offline 能力隔离、对象中心有限标签与背景 anchor 的区别、T10 极化率二阶项及缺失区域稳定性前提、精确重复约束去重和原 KKT 审核、终止失败保留与缓存重放计费。

测试数字保留待主线程填写的占位。仅引用已保存实现健康摘要的覆盖范围，不汇总研究结果，不认定任何科学门槛；Stage B/C 的完整条件路径明确为未实现、未运行，主线程最终审查定稿。

本次只读所需配置、预注册、相关 a22 源码、既有接口/恢复摘要及保存的 unit/CUDA health 摘要。未执行测试、物理、数值分析、SSH、私钥读取或哈希检查；未改主报告和源码。独立计费范围见 `CPU_RECEIPT.json`，scope 为 `a22-implementation-report-draft-documentation`。
