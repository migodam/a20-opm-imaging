# 复现合同

从仓库根目录运行；所有物理计算使用 complex128/float64。最小依赖为 Python≥3.10、NumPy、SciPy；真实 CUDA pilot 另需现有支持 complex128 的 PyTorch/CUDA 环境。图表使用 matplotlib。项目不安装 GPU infrastructure 或启动常驻服务。

发布 ZIP 通常不含 `.git`。CLI 的 `source_commit` 优先读取发布方部署的 `configs/SOURCE_COMMIT.txt`，其次读取 Git HEAD；两者均不可用时记录 `UNVERSIONED_SOURCE_ARCHIVE`，仍可执行。部署 stamp 声明该发布资产的 A20 来源身份，不等于对解压后文件的内容验证；不要自行填造 stamp。`backend_declared_historical_commit` 另指保留的 A17/A9 后端来源，不能当作本次 A20 源码或实验身份。本流程不做新的 hash 检查。

先在**独立新拷贝**中隔离发布资产自带的全部 `results`；下段只执行一次，原证据随后作为只读参考，不用于本次 gate 或预算。这是另一次研究运行。不要在当前研究目录执行，也不要在新运行开始后再次移动、删除或清空账本、失败记录及阶段输出以重置预算。

```sh
export PYTHONPATH=src
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1

python - <<'PY'
from pathlib import Path
prior = Path("prior_evidence/published_results")
if prior.exists() or Path("runs/gpu.lock").exists():
    raise SystemExit("Use a fresh independent copy; do not reset an active run")
prior.parent.mkdir(exist_ok=True)
if Path("results").exists():
    Path("results").rename(prior)
else:
    prior.mkdir()  # also marks initialization when the source copy has no results
Path("results/tests").mkdir(parents=True)
PY
```

本地 G0 必须使用 `tests/run_integrity.py`，然后用 `tests/summarize_integrity.py` 汇总。两者固定写入仓库的 `results/tests`；runner 支持 `--cpu-cap` 和 `--pattern`，summarizer 没有输出目录参数。直接运行 `unittest` 不会生成 CLI 所需的 gate 回执。下段运行完整默认 suite，保留各次失败，摘要为 PASS 后把报告复制到 **`results/G0_LOCAL.json`**；同时将本次检查及汇总的实测进程 CPU 登记到 CLI 已读取的外部账本。runner 原有每次默认 30 秒、全部尝试累计 120 秒的 CPU 限制不变。

该本地 runner 和下面的 CPU 包装使用 POSIX `resource`，在 macOS/Linux 执行。本轮也是先在 macOS 完成本地 G0/代数，再把同一源码、根 gate 及全部已付成本部署到 Windows CUDA 主机；两个主机仍共用一份预算。Windows 上不要把缺少 `resource` 的失败当成物理 G0 失败或跳过本地 gate，可复用上述已完成的本地流程及传输其回执。Linux CUDA 则可在同一主机依顺序完成各阶段。

每次重试先更换 `local_job`；不要删旧 receipt。以下代码只生成本地 gate，不执行真实六对象物理。

```sh
python - <<'PY'
import time
started_wall = time.perf_counter()
import json, resource, shutil, subprocess, sys
from pathlib import Path

local_job = "reproduce-local-01"
ledger = Path("results/EXTERNAL_CPU_RECEIPTS.json")
rows = json.loads(ledger.read_text()) if ledger.exists() else []
if any(row.get("receipt_id") == local_job for row in rows):
    raise SystemExit("Use a new local_job and retain all prior receipts")
gate = Path("results/G0_LOCAL.json")
gate.unlink(missing_ok=True)  # revoke a stale derived gate; keep all test evidence
status = "FAILED"
try:
    subprocess.run([sys.executable, "tests/run_integrity.py"], check=True)
    subprocess.run([sys.executable, "tests/summarize_integrity.py"], check=True)
    report = Path("results/tests/G0_LOCAL.json")
    if json.loads(report.read_text())["status"] != "PASS":
        raise RuntimeError("G0_LOCAL_NOT_PASSED")
    shutil.copyfile(report, gate)
    status = "PASS"
finally:
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    rows.append({"receipt_id": local_job, "status": status,
                 "scope": "local G0 runner, all child attempts and summary in this invocation",
                 "process_cpu_seconds": time.process_time() + children.ru_utime + children.ru_stime,
                 "measurement": "self and waited children, sampled before ledger write",
                 "wall_seconds": time.perf_counter() - started_wall})
    ledger.write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n")
PY
```

仅在上述报告 PASS 后运行代数审核；再确认 `results/G0_ALGEBRA.json` 的 `status` 为 `ALL ASSERTIONS PASSED`，才进入真实 G0：

```sh
python -m a20.cli algebra --device cpu --job reproduce-algebra-01
python -m a20.cli g0-real --device cuda --job reproduce-g0-01
```

`g0-real` 会检查根目录的本地和代数报告，并写入 `results/G0_REAL.json`。本地 G0 使用小型合成问题；真实 G0 的独立审核可核对已保存的材料坐标及物理步展开，这些离线参考不进入在线构基。只有真实报告的 `status` 为 PASS 才能执行 replay。

新运行的首次 replay 应从空 `results/replay` 开始，不传 `--parents` 或 `--iterations`，一次执行冻结的六 parent × 两个状态，即全部 12 states：

```sh
python -m a20.cli replay --device cuda --job reproduce-replay-01
```

检查该 job 的 `result.json` 与 representation gate，再进入符合资格的 A1；只有完整 A1 OPM quality survivor 才进入 A2。以下是各阶段调用，不是无条件连续执行的批处理：

```sh
python -m a20.cli a1 --device cuda --job reproduce-a1-01
python -m a20.cli a2 --device cuda --job reproduce-a2-01
python -m a20.cli evaluate --device cpu --job reproduce-evaluate-01
```

`evaluate` 只汇总已有证据，不能补齐缺失实验。replay 的重复 state/degree 记录会严格 HOLD；不要先跑 subset 再在同一输出目录跑整套，也不要自动丢弃失败。部分 replay 后的继续或重跑需要显式 canonical cohort/attempt manifest，当前 CLI 不会自动解决这些重复记录。

条件噪声与 timing 只在完整 OPM 非线性质量证据过 gate、且预算仍允许时调用；CLI 在 A1/A2 合格候选中按既定规则选择方法。没有 survivor 时保留 NOT_RUN：

```sh
python -m a20.cli noise --device cuda --job reproduce-noise-01
python -m a20.cli timing --device cuda --job reproduce-timing-01
```

现有条件噪声阶段在两个冻结 stress parent 上使用 1%/3%、每级三个配对 draw，FULL_GN 与 chosen 方法共最多 24 次 attempt，失败和重试也占 cap。现有 warm helper 对六 parent 各做一次 FULL_GN/chosen 配对，最多 12 次 attempt；只保留静态几何和 receiver SVD 缓存，预填充、失败与实际启动的每次运行均全额计费，并保留 cold/warm 分账及预填充分摊记录。这是历史暴露数据上的描述性 pilot，不给出总体置信结论。A20 没有规定五次 timing 重复；42 是主矩阵新增条件上限，已授权的 warm 重复不增加新条件，但仍消耗全部预算。helper 执行完成也不自行裁决 G2。

每次 CLI 重跑必须使用新的 `--job` ID，保留旧失败成本。`runs/gpu.lock` 排他锁与 `results/jobs/*/job_receipt.json`、`results/EXTERNAL_CPU_RECEIPTS.json` 账本共同控制实验；不要删除旧 receipt 来绕过预算。主实验有 12 小时 GPU job 占用、2 小时累计进程 CPU 的硬上限，CUDA 中的主机 CPU 也计入 CPU。本地检查之外的准备、传输等 CPU 成本也应实测登记；不能把未知成本记成零。发生限额、缺参考或未过前置 gate 时，后续阶段保留 HOLD/NOT_RUN。主 replay 必须支付参考审核与可能的新受约束参考。

`data/runtime` 为在线运行白名单；`data/offline` 的 truth、held-out truth、旧 full steps/gradients 仅供独立评估。`BasisView` 不提供这些字段，种子只来自原采集、残差、独立探针和允许的先前已接受步。禁止向构基代码传入标签、full J/H、full current corrections。

A1 使用完整状态及近似 Jacobian；A2 在每一 trial 冻结 Z/W、使用自身 reduced state 的 B。所有接受和停止判断支付完整物理。病态 reduced core 的 frozen-test Petrov/full fallback 明确计数；无隐藏 jitter、伪逆、后剪裁求步或 solver acceleration。

可选远端传输脚本只是一条 SSH 作业的启动/读取工具；连接目标和私钥由私有环境提供。复现不需要项目作者的主机、账号或密钥。
