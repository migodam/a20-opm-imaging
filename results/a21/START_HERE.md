# A21：固定 rank 的双侧 GN anatomy

状态：实现及本地 T0 已通过；真实五-state anatomy 尚待执行。科学结论尚未作出。

来源为 A20-R1 `3b3b17b5f4cf5d37b26602ead2dfe7c913b37e23`。对象固定为 2001、2005、2003、2007、2013，各 iteration17；均为历史暴露对象。原 A20/R1 结果、参考与账本不改写。

本实验只比较 rank56 的 BASE_G、PRIMAL_G、DUAL_G、BOTH_G、RANDOM_G；五态 Galerkin 一致性通过后才运行 BOTH_PG、RANDOM_PG。全部 oracle currents 是 OFFLINE DIAGNOSTIC ONLY，不能解释为可部署算法或速度收益。

- [Backend 接线](A21_BACKEND_MAPPING.md)
- [数值约定及 allowance](A21_NUMERICAL_CONVENTIONS.md)
- [原执行合同](../../protocol/a21/CODEX_TWO_SIDED_ANATOMY.md)
- [完整本地 T0](validation/T0.json)：137 项原有及新增测试、随包 tiny validation 通过。
- [最终新增测试](../jobs/a21-local-targeted-02/result.json)：56 项 A21 测试通过，包括跨阶段顺序、缓存和失败计费。
- [当前独立预算](BUDGET_CURRENT.json)

新增 CPU/GPU 各不超过1200秒，继承原累计 CPU5606.616051秒、GPU5661.778859秒。计费以 inclusive job receipts 和唯一外部 scope 为准；嵌套动作不是额外加总的 CPU。测试产生的历史账本追加输出保存在本目录 `validation/a21-local-validate-01/legacy_test_actions/`，原账本恢复冻结内容。

只运行 five-state anatomy，完成后停止。degree 增加、NN、nonlinear reconstruction、solver acceleration 均 NOT_RUN。
