# 复现合同

从仓库根目录运行；所有物理计算使用 complex128/float64。最小依赖为 Python≥3.10、NumPy、SciPy；真实 CUDA pilot 另需现有支持 complex128 的 PyTorch/CUDA 环境。图表使用 matplotlib。项目不安装 GPU infrastructure 或启动常驻服务。

```sh
export PYTHONPATH=src
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m unittest discover -s tests -v
python -m a20.cli algebra --device cpu --job reproduce-algebra-01
python -m a20.cli g0-real --device cuda --job reproduce-g0-01
python -m a20.cli replay --device cuda --job reproduce-replay-01
python -m a20.cli a1 --device cuda --job reproduce-a1-01
python -m a20.cli a2 --device cuda --job reproduce-a2-01
python -m a20.cli evaluate --device cpu --job reproduce-evaluate-01
```

每次重跑必须使用新的 job ID，保留旧失败成本。`runs/gpu.lock` 排他锁与 `results/jobs/*/job_receipt.json` 账本共同控制实验；不要删除旧 receipt 来绕过预算。主实验有 12 小时 GPU job 占用、2 小时累计进程 CPU 的硬上限，CUDA 中的主机 CPU 也计入 CPU。发生限额、缺参考或未过前置 gate 时，后续阶段保留 HOLD/NOT_RUN。

发布目录含本轮既有账本。独立复现应在新的拷贝中把**全部原 results 移至只读 prior_evidence**，在新 results 记录自己的完整成本；这是另一次研究运行，不能和本轮预算/结果混算。G0 本身不使用离线 truth。主 replay 必须通过真实 G0，并支付参考审核与可能的新受约束参考。

`data/runtime` 为在线运行白名单；`data/offline` 的 truth、held-out truth、旧 full steps/gradients 仅供独立评估。`BasisView` 不提供这些字段，种子只来自原采集、残差、独立探针和允许的先前已接受步。禁止向构基代码传入标签、full J/H、full current corrections。

A1 使用完整状态及近似 Jacobian；A2 在每一 trial 冻结 Z/W、使用自身 reduced state 的 B。所有接受和停止判断支付完整物理。病态 reduced core 的 frozen-test Petrov/full fallback 明确计数；无隐藏 jitter、伪逆、后剪裁求步或 solver acceleration。

可选远端传输脚本只是一条 SSH 作业的启动/读取工具；连接目标和私钥由私有环境提供。复现不需要项目作者的主机、账号或密钥。
