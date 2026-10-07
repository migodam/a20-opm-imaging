# A22 命令、环境与固定随机性

源码基线：A21 `8aa2d5d03c8fc41bda508c2e173a45fa2fea956a`；分支 `a22-three-fold-opm`。最终本地 commit 由 Git 记录。完整科学配置是 `configs/a22.json`，重定位资产路径用 `configs/a22_portable.json`。没有重新检查 SHA256。

XINAN 实际环境：Python3.10.9、NumPy2.2.6、SciPy1.15.3、PyTorch2.6.0+cu124、RTX4060 Laptop/8GB。精度 complex128/float64。实际启动器固定 OMP/OPENBLAS/MKL/NUMEXPR threads=1。

## 已执行命令的入口与记录

每条命令使用唯一 job ID；不要覆盖已有receipt。下列为对应实际作业的可复核CLI入口，远程transport还承担共享锁、队列检查、child CPU尾段与硬预算停止。连接配置在仓库外，未复制凭据。准确environment/outcome/receipt保存在 `results/jobs/a22-*/`，transport记录在 `results/a22/transport/`。

```sh
PYTHONPATH=src python -m a22.cli unit --job a22-unit-013
PYTHONPATH=src python -m a22.cli validate --job a22-cuda-validate-002 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python -m a22.cli screen --job a22-cuda-screen-001 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python -m a22.cli screen-resume --job a22-cuda-screen-002 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python -m a22.cli screen-resume --job a22-cuda-screen-003 --device cuda --root D:/AI/A22_THREE_FOLD_OPM --lock-root D:/AI/A20_OPM_IMAGING
PYTHONPATH=src python tools/a22_screen_decision.py --job a22-screen-statistics-001
PYTHONPATH=src python tools/a22_evidence_audit.py --job a22-evidence-audit-002
PYTHONPATH=src MPLBACKEND=Agg python tools/a22_render_outputs.py --job a22-render-001
```

上列 job ID 是历史记录，直接重用将拒绝。复现需复制干净输出、使用新ID并保留原收费上限；GPU物理作业须经现有transport/共同锁启动。`tools/a22_preserve_attempt.py`、`a22_remote_jobs.py stop/pull` 保留了两次中断与锁清理，不把缓存重放当成新物理标签。

## Seed与案例生成

master seed：**20261007**；bootstrap seed：**20261909**，repetitions=2000。场景顺序 `[2001,2003,2014,2009]`。实际 probe provenance、8个候选方向、完整预算均在 `stage_a/scene_*/online_provenance.json`、`frozen_online_directions.json`、`frozen_online_budgets.json` 冻结。

固定配置 U8/O4/P4/M4、degree1、material dimension32、current cap32。幅度 fractions `[0.2,1.0]`、pointwise max0.25、feasible fraction0.8、nuisance fraction0.35；方向来自online AW，筛查前4个方向做有限标签。

noise levels `[0,1,3]`，零噪声1次，非零各16次。每行的 `noise_seed` 是完整 `SeedSequence` 输入，见 `direction_metrics.csv/jsonl`；nominal/calibration成对共享seed。proper complex noise实虚各方差 `σc²/2`，尺度来自背景预测。物理干预通过相同六源/receiver布局的确定性线性变换实现，不采用独立随机factor噪声。

九个注册新场景未生成，24场景划分未执行。NN seeds只存在未执行配置中，不代表模型或训练记录。Stage B/C gate被拒绝；不要通过复现命令自动启动这些阶段。
