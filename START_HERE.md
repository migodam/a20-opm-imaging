# A20 Route A：OPM 材料成像

这是一个有固定预算和前置 gates 的三维矢量 Maxwell deterministic imaging pilot。当前处于实现和 G0 验证阶段；本页将在真实实验结束后写入实际结果，不能把任务书的 proposed thresholds 当成完成的结果。

先读 `protocol/CODEX_ROUTE_A_OPM_IMAGING.md`、`protocol/GO_NO_GO_GATES.md`、`configs/frozen.json`。实际后端是保存的 A17/A9 DenseDDA，complex128/float64；6 个历史暴露 parent 对象，各 replay 两个 states。

运行入口见 [复现合同](docs/REPRODUCE.md)，公式与函数见 [后端映射](docs/BACKEND_MAP.md)，冲突处理见 [协议记录](docs/PROTOCOL_CONFLICTS.md)，近邻证据见 [文献审计](docs/CLOSEST_PRIOR_AUDIT.md)。在线输入与离线真值/参考分别位于 `data/runtime` 与 `data/offline`。

GPU 累计上限 12 小时，CPU 累计上限 2 小时；失败、重跑、参考、计时和审核全部计账。没有训练 NN，也没有修改 Maxwell solver 或启动 PCG/GMRES acceleration。
