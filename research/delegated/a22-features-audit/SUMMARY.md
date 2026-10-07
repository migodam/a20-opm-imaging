# A22 features/evaluate implementation audit: source-only handoff

状态：SOURCE_REVIEW_AND_PATCHES_ONLY / NOT_RUN。本 worker 只读源码与少量配置元数据，未导入/编译检查目标模块，未执行 unittest、数值实验、Maxwell、SSH、GPU、远端请求或哈希，也未打开实验数组/真值文件。下面的修补是普通实现与记录边界修补，不是科学有效性、region certificate 或 gate 评估。

## 当前所有权交接

最初授权范围为 `src/a22/features.py`、`src/a22/evaluate.py`、`tests/test_a22_features.py`。收到根线程接管科学范围修正的通知后，worker 已停止修改前两个模块。后续仅更新测试 fixture 与本交接目录。根线程正在管理 actual-object offline label 中心、declared object-prior、W-external 和 forecast region；本记录描述 worker 的实现修补，不覆盖根线程的后续科学修改。不触碰 CLI、core、online、assets、budget、其他代理文件或已有测试。

## 已修补的明确实现问题

1. `A22BudgetBook.action_guard` 是 `@contextmanager`。旧 finite label 与 full-J 分支只是调用该函数，未进入 `with`，因此其 guard、preflight、role 和 generation counters 不会运行。worker 将两处改为包围实际动作的 `with book.action_guard(...)`。full-forward/tangent 的已有内部 span 保留，未改 cap、stage、方向数或振幅数。
2. split metric row 显式传 `full_model_certified=False`，又展开包含相同键的 `split.certificate`，会发生重复关键字 TypeError。删除重复的显式参数，保留 certificate 中的真实值。
3. `_dual_residual` 已算 reduced adjoint coefficient，旧 `direction_descriptor` 为系数范数又做一次同样的 adjoint core solve。worker 让私有 helper 同时返回 coefficient，并复用它；不改 descriptor 数学公式。根线程已确认该复用正确。每方向的第二次 reduced solve 不再请求，合法 L*/S*/B* residual actions 保留。
4. descriptor 旧代码先直接除以 direction norm；zero/wrong-layout/nonfinite 会产生无效值，complex input 还可能被 float 转换丢弃 imaginary 部分。新增 real、finite、shape、nonzero 检查，均在动作 span 与 normalize 前拒绝；不改合法方向选择。
5. 旧代码在 full-J benchmark 之后才生成 forecasts，与“forecasts 在 full-J/labels 前冻结”的声明不一致。worker 新增 `_frozen_direction_cases` 与 `_freeze_budget_rows`，仅在原 `direction` stage 内提前计算相同注册方向/振幅/噪声/干预组合的预算缓存，保存 `frozen_online_budgets.json` 后再进入离线 full-J guard。direction selection、预测调用数、finite label 调用数与 stage caps 不变。根线程现在可按新的 actual-object 科学范围调整这些 cases/labels。
6. scene summary 再次调用 `anchor.state.source_residual()`，这是额外 L × current 的物理矩阵请求，原处没有 RHS 成本计数。worker 新增 `_anchor_summary_backward_residual`：优先读取 `anchor.provenance['source_backward_residual']` 的已计费数值；若现有 anchor 不提供，就在专属 span 计量 `full_state_backward_residual_L_rhs=P`，并标记 origin。未修改 anchor 实现。如果根线程在 online.py 暴露首次诊断数值，可消除这次额外请求。
7. 补充 canonical `scene_metrics.csv`（含 failure 分支），保留已有 `scene_manifest.csv`；metric rows 标记 `full_J_scope='OFFLINE benchmark only'` 与 forecasts-before-full-J 状态。未改 gate 输入或推导 PASS。

## 静态 shape/packing/capability 检查

从现有公开实现读到：B(identity32) 为 `(P,n,32)`；PMW/MW 为 `(P,q,32)`；IR 的 einsum 为 `(P,n,32)`；known L*Q 为 `(n,q)`；whitened h 通过 per-source real-then-imag unpack 得到 `(P,m)`，S* 产生 `(n,P)`，adjoint core coefficient 为 `(q,P)`，psi/defect 的返回布局为 `(P,n)`。B* 使用 real material pullback；`Projection.solve(adjoint=True)` 使用 conjugate-transposed core。worker 未发现这些路径的静态 transpose/conjugation 不匹配；tiny 运行回归仍未执行。

context 的 paid known-background full L、GS、Goff 以及合法 anchor injection factor 是 residual/bound 输入；它们不等于 full material tangent/Jacobian 或 full material adjoint solve。context/direction/predict 代码不调用 full_tangent_action、full_adjoint_action 或 offline loader。full J 仍只在 evaluator benchmark 路径产生，保存至 `OFFLINE_J_benchmark.npz`，online factor 文件只含 AW/MW/PMW；预测端不接收 JF、finite label 或 true error。根线程接管后的合法 injection factor 新接口也保持已知 anchor 依赖。

finite amplitude raw label 在同一振幅内被 nominal/intervention 和多 noise draw 复用，校准是 exact source/receiver multiplication，没有第二次 Maxwell forward。worker 没有增加一个 finite forward 请求。screening=True 的 campaign 仍会对其配置 IDs 重跑，只有 expansion 分支会依据已有 COMPLETE scene JSONL 跳过；没有擅自加入 resume、标签复用策略或修改请求预算。所有失败/重试应继续由主线程 guard 和 A22 ledger 计费。

`_append` / JSON writer 使用 `plain`，会将 nonfinite scalar 转为 null；CSV 只取 scalar 字段，dict/array provenance 不会混入 scalar metric 列。小型 benchmark linear solves/SVD 和文件写入有 inclusive job CPU/wall 记账，个别操作没有单独 span 的问题不等于总成本遗漏。没有更改这些字段/算法。

## 根线程提供的科学范围纠正（未由 worker 判定）

根线程指出旧 finite labels 只从 uniform known background 加 patch，没有使用四个对象真实材料；family 差别当时只来自 geometry。actual original-object truth 的离线中心与独立 offline 文件，以及 declared object-prior/W-external/CM second term 的数学与 region 范围，全部由根线程修正。worker 未读取 truth、未改 scientific center、未评判这些预算是否支持研究 claim。根线程明确保持 online anchor/probes/features label-free，并将预算的 uniform certificate 限制保留为 false/indicator。

## 新测试源码（3 项，尚未运行）

`tests/test_a22_features.py` 使用 6 个 source、16 个 mock cell（48 个 complex current）、2 个 mock observation channel、2 维 reduced current basis、32 个 real material coordinate 的小矩阵；真实 Maxwell/A17 资产不参与。固定合成 injection factor `(P,N,3)` 与 volume-orthonormal real material Q 供根线程新增合法接口使用。配置显式给出 `.25` declared prior，仅为 fixture 参数，没有科学范围接受结论。

- Residual shapes、独立 complex inner-product 对照 source-major real packing、reduced real adjoint identity，以及每方向只一次 reduced adjoint solve。prediction 不再请求额外 view/projection/injection-factor action。
- poison `truth/full_J/recovery_labels` 配置改变不改变 descriptor/forecast；model/anchor/adapter/state/view/projection 等守卫在任何 full tangent、full adjoint、full-J/H 或 label 字段访问时直接失败。这样 online feature 测试不需要构建任何离线 benchmark。
- zero、complex、nonfinite、wrong-layout direction 在动作前被拒绝。

这些是普通实现与边界回归，不测试 gate 阈值、不验证 CM/region 新数学，也不锁定旧 uniform-background finite label 的科学假设。预期由主线程计费执行 `PYTHONPATH=src python -m unittest discover -s tests -p test_a22_features.py`；worker 没有调用它或其他测试。

## 成本交接

独立 scope `a22-features-audit`；CPU_EVENTS/CPU_RECEIPT 记录 4 个 source-read shell 加 1 个交接 shell 的测量，显式保守 shell 预留 5s，以及 3 次 apply_patch 的非测量预留 15s。预留覆盖未测工具服务/启动和 receipt 尾部，不是实测实验 CPU。没有 runtime/test/physics/SSH/GPU/data-load 成本事件。此 scope 只应合并一次入 A22 实现台账；根线程后续科学修补和未来测试/实验须各自计费。
