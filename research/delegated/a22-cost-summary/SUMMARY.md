# A22 cost summary: source-only handoff

状态：IMPLEMENTED_SOURCE_ONLY；worker 未调用 summarize_costs/export_cost_csv，未运行测试、模块导入/语法检查、物理、SSH、GPU 或哈希，也未打开 NPZ/实验数组。仅查看 A22 会计文件清单、小型 JSON/JSONL header 与 budget 源码以确认字段。根线程随后报告其独立计费测试共 95 PASS、包含本模块测试；此运行不是 worker receipt 的成本或独立验证，也不能用于任何科学 gate。

## 新增源码与 API

- `src/a22/cost_summary.py`
- `tests/test_a22_cost_summary.py`（3 项 stdlib 小型会计 fixture）
- `summarize_costs(root) -> dict`：只读会计记录，不写任何输入/输出，不参与预算执行。
- `export_cost_csv(root) -> dict`：调用一次 summarize，然后原子写 `results/a22/cost_ledger.csv` 与 `results/a22/ACTION_ACCOUNTING.json`，返回 summary 与 output 路径。worker 未调用；当前这两个输出不是 worker 生成的。

模块只有 stdlib 依赖，无任何 Maxwell、Adapter、NumPy、SSH、GPU、数据加载或 gate API。没有修改其它模块。

## 权威与去重规则

只枚举 `results/jobs/a22-*` 的 job 目录。每个目录若存在 `job_receipt.json`，只以该最终 receipt 作为 job 资源/动作汇总权威；否则使用 `accounting_checkpoint.json`，明确 `live_checkpoint=true`/PROVISIONAL。最终 receipt 与 checkpoint 不重复计费。没有 receipt 的 job 保留 missing row 与 NOT_MEASURED；即使存在 span，也不将 span CPU 提升为 job 总成本。

每个 job 的 `cost.jsonl` 保留逐行 span 记录，包括 FAILED/TIMEOUT/CANCELLED/BUDGET_REFUSED、error、expected UnsafeCore 和 cache hit。span CPU/wall/exclusive CPU/wall 只描述原记录，resource_additive=false，不叠加到 receipt 总资源。重复 event_id 保留为 duplicate row。FAILED expected unsafe core 保持 FAILED，不改成成功。

外部 registry 支持 `results/a22/external_cpu_receipts.json`、同名 JSONL 以及同名目录中的 JSON/JSONL。按原记录 scope 去重；完全相同的重复 scope 保留 duplicate row 但只计一次。冲突 scope 的所有候选保留，并撤销该 scope 的汇总权威，标记 ACCOUNTING_ISSUES/NOT_MEASURED，绝不猜选一个成本。reference receipt 的路径仅保留，不打开或重复记账。

排除 a20/a21 job 目录、显式非 A22 campaign、mismatched job_id 和明确旧 A20/A21 scope。输入路径必须仍在 root 内。历史项目根 COST_LEDGER 与 A22 全局镜像 COST/JOB/FAILURE ledgers 不读取，避免对同一 receipt/span 再汇总。若根线程需要镜像账本中只存在于全局的独立 refusal event 详情，应以该原记录另作诊断；本模块不会推测 missing job receipts 的资源金额。

## CSV 与 JSON 内容

CSV 每行保留 record_type、job_id/scope、event/id、phase/stage/role、原 status/accounting_status、source/line、resource_additive/action_total_authority、duration/wall/exclusive wall、process CPU/exclusive CPU、GPU occupation、measurement、scene/method/rank、错误与 expected-unsafe 标志、原 cache hit 计数、stage GPU map、原 counters JSON。

动作列保留互斥 F/F*/L/L* vectors、B/B* 与额外 voxel B*、compressed-B current columns、S/S*、full forward/tangent/adjoint calls/RHS、full/retained/projected LU、full-state/health residual 与 receiver RHS、new data-generation F、new teacher label、cache hit、reduced-core RHS。aliases 是同一原变量的选择，不相加；冲突 aliases 原样在 counter_alias_conflicts_json 暴露，供主线程判断。

`Maxwell_matvec_rhs_aggregate` 单独列出，永不再加到 F+F*+L+L* 的 recorded vector sum。full solver RHS 和其它诊断 RHS 也不添加到该互斥四类 sum。保留原 counts/counters 可检查单位，不自动转换 request/call/RHS 或推测 FLOPs。

只有权威 receipt/external counts 进入 action_accounting；span counters 不再加一次。每个动作字段提供 explicit_record_count / unrecorded_record_count / recorded_sum，缺项为 NOT_MEASURED。部分显式数据保留 recorded subtotal 与 PARTIAL 状态，不把缺项补零。

CPU、GPU、wall 分成独立 resource_totals；没有 CPU+GPU 综合资源数。CPU 优先使用原 process_cpu_seconds（已经包含原 book 定义的 controller/child），不再把 child CPU 加一次。external 的 conservative charge/status/measurement 保留，不能将其展示为纯实测 CPU。wall 的不同 recorded inclusive charge 之和不是并行 campaign elapsed，也不是部署 latency。

ACTION_ACCOUNTING 含汇总、authority snapshots、failed/cache records、provenance、缺项与 policy，不重复嵌入全量 span rows。CSV 是逐条原记录入口。统计与 Gate 明确 NOT_ASSESSED_BY_COST_SUMMARY，A0/A1/A2 独立 deployment cost 明确 NOT_MEASURED；不从共享 cache 或 predictor 名称分摊费用。

## 三项测试源码

1. final receipt 覆盖 checkpoint；A20/A21 与全局镜像不重复/混入，nested span 不叠加资源，external duplicate 只计一次，generic Maxwell 不重复计入四类向量，FAILED expected UnsafeCore 与 cache hit 保留。
2. live checkpoint 为 PROVISIONAL；external scope 冲突保留 recorded subtotal，整体金额 NOT_MEASURED。
3. missing receipt 不用 nested span CPU 冒充 job 总成本；CSV/JSON export 显式缺项、独立资源与未测 predictor 部署费用。

未来主线程的单独计费测试命令为 `PYTHONPATH=src python -m unittest discover -s tests -p test_a22_cost_summary.py`。worker 未执行该命令。根线程已通知其整体测试完成，source 在该通知后保持不变。

## CPU 交接

独立 scope `a22-cost-summary`：2 次会计 schema/source-read shell 加 1 次交接 shell，分别记录 own/child process CPU；每 shell 明确保守预留 1s。一次 apply_patch 写模块/测试，明确非测量预留 5s。总预留 8s 是未测工具服务、启动与 receipt 尾部的记账 allowance，不是运行成本。此 scope 只应合并一次入 A22 implementation ledger；主线程的测试、export 和未来部署/物理工作在其它 receipt 中计费。
