# A21 复现与执行记录

原冻结代码：`3b3b17b5f4cf5d37b26602ead2dfe7c913b37e23`；实际五态物理执行代码：`5c6bcb02bb4ab88f7b46f07bca4ca3f4e38a067c`。独立数组审计为 `136c155`；最终图表报告为 `a981d50`。完整commit在各job receipt及 [冻结manifest](A21_FROZEN_MANIFEST.json)。报告修复只更改记录/显示，不更改物理、QP、gate、配置或数据。

冻结输入为五个 `data/runtime/<parent>/problem.npz`、`state_17.npz`、原 `results/replay/replay.jsonl` 和它明确引用的五个raw constrained reference及五个baseline步。ID顺序2001、2005、2003、2007、2013；没有offline label或truth输入。源与合同可在 `protocol/a21/` 及 `configs/a21.json` 找到。

所有运行使用单BLAS线程、complex128/float64。XINAN：Python3.10.9、NumPy2.2.6、SciPy1.15.3、Torch2.6.0+cu124、CUDA12.4、RTX4060 Laptop 8188MiB。完整环境见 [RUNTIME_ENVIRONMENT.json](RUNTIME_ENVIRONMENT.json) 和各manifest/receipt。

本地Python路径相对仓库为 `../../.venv_nn/bin/python`。以下为实际执行命令的可读形式；实际完整参数保存在 `results/jobs/a21-*/manifest.json`、`job_receipt.json`。复现需独立工作副本和唯一jobID，保留已完成实验的不可变文件，预算沿用累计receipt。

```sh
export PYTHONPATH=src
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export MPLCONFIGDIR=.mplconfig
../../.venv_nn/bin/python -B -m a21.cli preflight --job a21-local-preflight-01 --device cpu
../../.venv_nn/bin/python -B -m a21.cli validate --job a21-local-validate-01 --device cpu
../../.venv_nn/bin/python -B -m a21.cli validate --job a21-local-targeted-02 --device cpu --test-pattern 'test_a21_*.py'
```

远端代码在 `D:/AI/A21_TWO_SIDED_ANATOMY`，Python为 `D:/python/python.exe`；共用原 `D:/AI/A20_OPM_IMAGING/runs/gpu.lock`。SSH配置从忽略的private文件或既有A20连接环境读取，不进入结果包。部署仅允许源码、协议、冻结配置及上面的运行输入，不发送truth/offline labels/旧账本。

```sh
python3 tools/a21_remote_jobs.py deploy
python3 tools/a21_remote_jobs.py run --stage preflight --job a21-xinan-preflight-01 --device cpu
python3 tools/a21_remote_jobs.py run --stage anatomy --job a21-anatomy-01 --device cuda --phase all
python3 tools/a21_remote_jobs.py pull
```

物理启动前，在忽略的 `configs/A21_SOURCE_COMMIT.txt` 保存实际代码commit；preflight/manifest明确区分原来源与执行源码。all阶段先验证first/middle/last，准备每态一次，固定父对象顺序完成25个G臂，一致性全部通过后才执行10个cache-only PG臂。没有重建各臂Maxwell工作区。冻结raw arrays见 `anatomy/caches/`、`anatomy/diagnostics/`。

```sh
../../.venv_nn/bin/python -B -m a21.cli validate --job a21-local-report-regression-03 --device cpu --test-pattern 'test_a21_report_allowance.py'
../../.venv_nn/bin/python -B tools/a21_review.py --job a21-local-array-review-01
../../.venv_nn/bin/python -B -m a21.cli report --job a21-local-report-final-02 --device cpu
```

CLI report生成自动初审，最终科学判断由Codex阅读完整向量、对照、curvature、normal及solver defects后写入GATE_DECISION和中文报告。初审状态保留，不被当成自动科学批准。首次报告/图表快照保存在 `report_attempts/`。失效bound、full KKT或adjoint会停止；本次这些停止条件均未触发。

没有运行T2、非线性成像、NN、degree扩展、solver acceleration或A21公开发布。
