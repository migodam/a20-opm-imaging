# A20-R1 复现与信息边界

## 版本与环境

原冻结 A20 commit：`e29f345ae5aea170a18cca1b79defe57e878ab29`。真实物理运行源码 commit：`5231aea98f6945a77c4f83f030a57248065695ef`。release 完整公开 commit 另由 `results/a20_r1/PUBLICATION.json` 记录；报告布局和 transport 错误展示的后续修改不代表重跑物理。原报告和 v0.1 release 均保留。

实际 CUDA 环境：已有 Windows Python 3.10.9、NumPy 2.2.6、SciPy 1.15.3、PyTorch 2.6.0+cu124，RTX 4060 Laptop 8GB。模型/优化器使用 complex128/float64。复现可使用已有 CPU 或 CUDA 环境，不需要作者的账号、私钥、主机地址或新调度服务。图另需 Matplotlib；macOS 冷字体枚举失败已留账，最终图使用已有字体缓存。私人字体缓存不随包附入。

## 先读保存证据

`results/a20_r1/anatomy/rows.jsonl` 是原始测量；`steps/` 保存有效 reduced steps，`failed_steps/` 保存首个 early baseline 的失败复现步。`results/replay/` 包含原 A20 已付费的 constrained full references 和基线，不重新优化它们。full tangent 只在独立离线审核中计算并计费，不送给合法 builder。

`results/jobs/r1-anatomy-01/manifest.json` 冻结参数、费用起点和 source 身份；job receipt 的 FAILED 表示 baseline guard 按协议终止。`ANATOMY_SUMMARY.json` 记录 31 次真实候选构造、30 OK、1 FAILED、29 NOT_RUN。`REGISTERED_GATES.json` 为自动门槛证据；根 `GATE_DECISION.json` 添加主线程最终科学审查，不改原始数值。

原始 row 的 `legal_candidate` 是通用“无 oracle seed”标记，不能代替注册候选名单。PROTECTED-RANDOM 使用合法随机 probes，但其角色为离线匹配控制，**不参与 Gate B/C 或最终方法选择**。自动 gate 仅允许 WIDE-M/CHEAP-TASK，HISTORY 没有合法快照轨迹。报告另附显式 evidence-source classification；原始记录不回写。未访问 early rows 中的通用 `MISSING_OR_INVALID_EXISTING_REFERENCE` 表示没有本次审核记录，并非发现保存参考失效。只有实际审核的六个 references 可称本次审核有效。

## 本地测试和汇总

在独立拷贝内操作，保留原 evidence 和费用。设置：

```sh
export PYTHONPATH=src
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
python -B tools/r1_integrity.py
python -B -m a20_r1.cli report --device cpu --job r1-reader-report-01
```

测试保存新的 attempt/log/CPU receipt；report 读取已付费 JSONL，生成 CSV/图，不读取 NPZ、不运行 Maxwell。两者计入累计费用，job ID 不可复用。自动 report 会把根 gate 标为 `PARENT_REVIEW_PENDING`；科学解释参考随包最终审查，不能把重汇总当新实验或自动批准。

本包 96 项完整测试通过（原 31 项、R1 65 项），覆盖六源压缩丢失、block 保护、共享 RNG、cheap gradient reduced pullback、oracle provenance、accepted owner/index/缩放、拒绝步不更新 history、缓存失效、零范数/reference、QP 与预算拒绝。最终图另做结构回归和真实渲染观察。nonempty retained-U 的严格真实 replay 未被早期“exact legacy”合成回归覆盖；该测试缺口保留，unit PASS 不能抵消真实 baseline conflict。

## 物理入口与停止状态

`python -B -m a20_r1.cli preflight --device cpu --job r1-reader-preflight-01` 可检查拷贝冻结输入。物理 anatomy/closed-loop 入口有预算、锁、信息边界及 gates；存在入口不表示当前允许继续。本次 frozen matrix 已按 baseline guard 停止，anatomy 拒绝覆盖已有 state/method 输出，closed-loop 没有合法 winner。**不得删除失败输出、用历史 step 替换新 proposal、放宽 1e-9 门槛或另起 job 绕过停止。** 独立复现实验应另行注册协议/预算，原包保持只读，结果不能混作本次完成数据。

GPU 使用原共享锁 `D:/AI/A20_OPM_IMAGING/runs/gpu.lock`；R1 根为 `D:/AI/A20_OPM_IMAGING_R1`。SSH transport 只从私人环境变量读连接配置，不随公开包保存。现有 GPU 作业或锁会阻止启动，没有后台守护服务。

## 累计计费与互斥动作

起点 CPU 5292.784926 秒、GPU 5375.9374196 秒，不重置。原限制 CPU 7200/GPU 43200；R1 CPU 1500/GPU 4800；Phase1 CPU 600/GPU 1200、Phase2 CPU 900/GPU 3600 秒，禁止借款。失败、参考审核、绘图、重试、包审计和公开发布全部计费；最终 totals 在 `results/a20_r1/BUDGET_FINAL.json`。

CPU inclusive receipts 计 imports、child 和失败；不能精测的管理/发布费用用明确保守 allowance。GPU 是持锁作业占用墙钟，非 kernel time。`COST_LEDGER.jsonl` 的 nested events 描述 attribution，**不可叠加 parent/child CPU 或 GPU**；费用按 job receipts/external registry 唯一 scope 求和。共享实际费用和独立冷部署归因同时报告，归因不是额外账单。

部署向量定义中 F/F*/L/L*、full solve RHS、full-state L/Goff RHS 互斥，`Maxwell_matvec_rhs` 等聚合计数不重复加入。receiver、LU、offline audit 另列。basis wall/rank 不能替代完整 closed-loop deployment gate；本次无部署结果。

在线输入 `data/runtime`；truth/旧标签 `data/offline`；full reference/oracle 只走独立离线诊断。合法 FIXED/WIDE/CHEAP builder 不读取 full J/H、full gradient、reference、truth 或 teacher。可公开 offline labels 仍是标签，不给在线算法读取权，不构成盲测。完整 schema/index 见 `docs/PUBLIC_PACKAGE_INDEX.md`。
