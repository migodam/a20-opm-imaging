# A22 交付源码审查摘要

状态：SOURCE_ONLY。只读取当前 `src/a22/*.py`、`configs/a22.json`、`configs/a22_portable.json` 与 `results/a22/PREREGISTRATION.json`。未读取数组、物理结果、job 日志、SSH 私有配置、主报告或协议证明正文；未导入项目模块，未运行测试、分析、物理、绘图、报告、训练、远程或哈希检查。

父线程提供的进展是“首场景目前 337 条记录，四场景 screening 尚未完成”。本审查没有复核这些记录，也不从部分记录判断相关性、MAE、覆盖、预算可信度或 gate。完整源码接口索引见同目录 `SOURCE_INTERFACE_MAP.md`。

## 普通发现

1. 五个用户指定入口均有实现：`build_anchor`、`build_opm`、`material_features`、`build_split`、`evaluate_recovery`。第五入口调用共享 `constrained_material_solve`；下层 QP 不是另一个用户接口。源码入口与返回布局已逐项列出。
2. 当前固定配置是 U8/O4/P4/M4、degree1、current rank cap32；实际 rank 可因正交化而 deflate。材料图为 16 个几何空间基的实部/虚部共 32 个实坐标，不是 32 个复坐标。已知背景为 0.1+0.04i，观测为 6×128 complex / 1536 packed real。
3. 在线数据白名单是 points/data0/init；material chart 与 acquisition 由公开 geometry 构造。在线 anchor 来自实际公开已知背景。descriptor/context、固定方向与所有预算先冻结，再读取独立 offline 原对象材料、构造有限 Maxwell 标签与 full-J 基线。离线 truth 与标签不进入 online portable config。
4. descriptor 的源代码公式、函数位置、输入与预算分项已列出；明确区分 profiled witness 与 regularized witness、原始增益与 attribution、unstructured 与 paired ROM/nonlinearity/factor/W-external 分项。`certificate_type=empirical_indicator`、`full_model_uniform_certificate=False` 是当前预测输出契约，校准不改变它。
5. 保留两种离散 provenance：旧 data0 的 truth-generation n14；原保存 truth 被离线 loader 校验为 solver n12 材料；新有限标签在 n12 做 full Maxwell。旧观测不能代替新的“同网格精确标签”。本任务未读取任何实际材料数组。
6. 统计先按 scene/scope/direction/amplitude/noise_level/intervention 合并 noise draws，再进行每方法单一非负 scale；screen 用 LOSO，formal 只 fit development。场景是 bootstrap 单元，A1/A2/A3 使用共同完整单元；full_J/full_J_total 是独立 offline 基线。原始报告的 raw reducer 仍仅提供未校准描述图，不能替代 canonical statistics。
7. 普通 discovery 差异已获父线程授权修正，独立 source scope `a22-report-discovery`：raw report 默认优先 `results/a22/stage_a`；statistical helper 默认优先 `results/a22/statistics/STATISTICS_EVIDENCE.json`。保留 A22 范围校验、旧合法 fallback 与缺失 NOT_RUN。新增 3 个 discovery fixture 源码，未运行。没有改 reducer、statistics、CLI、gate、物理算法或主报告。
8. CLI `report` 仍只调用 raw generator；statistics、statistical plots、cost summary 需父线程显式 metered 调用。`one-shot`/`train` 分支即使入口前提满足，当前仍抛出 CONDITIONAL_IMPLEMENTATION_NOT_FROZEN_YET。offline truth loader 当前只接受四个 screening ID，扩展场景/训练配置的存在不等于其输入或实现已经齐备。
9. 输出索引仅从 write 路径与 source schema 得出；除已读取的 PREREGISTRATION 外，不宣称列出的文件已存在或其状态已通过。cost summary 的 job/external receipt 权威、nested span 不叠加、CPU/GPU 独立、generic Maxwell aggregate 不重复计入动作的区别已列出。

## 未确认事项

- 本任务没有读取实际 job/environment/outcome/receipt，因此精确历史启动命令、active process、远端部署状态、实际 counters、已完成场景、失败原因和可用预算均 NOT_VERIFIED。文档命令表是当前 CLI 支持形式，不是已执行记录。
- 当前 A22 配置只给 family 字符串；两 Gaussian 的实际强度参数、shell 的具体多尺度对象结构需原对象说明，本任务不读取。保留历史 exposed 标志，不称盲 holdout。
- 提供理论的正文有效性、实际验证 PASS、Maxwell 结果、预算覆盖或 prior 是否包含对象的数值，均未在此任务中判断。
- 后续输出存在性、四场景完整性、24 场景 formal 证据、训练缓存合法性和科学 gate 留给父线程；本摘要没有 gate 结果或最终科学结论。

## 费用边界

本 scope 的 CPU_RECEIPT.json 仅计源码/config/预注册读取和普通文档写入。声明每次实现 shell 1 秒保守预留，覆盖未测量的 shell 启动/序列化；已测 Python CPU 单独列出，不把预留叫作实测。默认 discovery 的源码修改与测试源码另在 `research/delegated/a22-report-discovery/CPU_RECEIPT.json` 计费，未重复计入这里。
