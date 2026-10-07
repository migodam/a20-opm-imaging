# A22 统计证据模块

状态：实现已保存，AST 语法检查通过；统计运行、19 个 unittest、SSH 和 GPU 均未执行。Gate A 和路线判断由父线程 Codex 决定。

实现文件：`Gaussian/A22/three_fold_opm/implementation/src/a22/statistics.py`。测试文件：`tests/test_a22_statistics.py`。另仅在本 worker 原有 transport 文件中加入 `configs/a22_portable.json` 白名单；冻结的 `configs/a22.json` 仍保留，旧 `data/runtime` 仍不部署。没有修改 features/core/reporting 或其它 agent 文件。

## 接口

- `analyze_direction_metrics(csv_path, config, *, mode='screen', scene_manifest=None, bootstrap_repetitions=None, seed=None, output_dir=None)` 读取规范方向 CSV，返回证据，可选保存输出。
- `analyze_rows(rows, config, ...)` 对同样的输入字典行进行纯统计分析。输入兼容 reporting 的字段别名和 deployable/oracle_only/unclassified 判别。
- `aggregate_direction_rows(...)`、`fit_nonnegative_scale(pairs)`、`paired_scene_bootstrap(scene_mae, repetitions=2000, seed=...)`、`failure_auc(...)` 和 `write_statistics(...)` 可独立使用。

`primary_incrementality` 指向 deployable / 全家族 / 全噪声的 held-out 分支。主要字段为 `absolute_MAE_improvement`、`relative_MAE_improvement`、对应 `*_95_percent_interval`、`improvement_probability`、`paired_scenes`、`missing_scene_ids`。正差表示 A3 的 MAE 更低；没有 Gate PASS/FAIL reducer。

## 固定统计规则

同 scene/scope/direction/amplitude/noise_level/intervention 的多个 noise draw 先取平均，再用于拟合和评估。每方法只有一个非负乘数，最小化绝对 coefficient-error 的无截距平方损失；不筛除异常点、不加入更多参数。原始和校准后的 MAE、Spearman、经验预算覆盖分别保留。全部预测为零时 scale 不可识别，校准量保持缺失，原始数值仍报告。

screen 按配置冻结的四场景做 leave-one-scene-out。formal 按配置 development 拟合；calibration、evaluation 和 development 描述表复用完全相同的参数。calibration 不二次调参。未出现在冻结列表中的场景单独审计，不加入拟合/正式评估。

每场景、每家族和 noise-zero/noise-positive 分支均报告。Spearman 少于三个聚合单元或秩恒定时为 UNDEFINED。失败、无效、缺预测或缺必需分组字段的单元保留审计，不计为有效覆盖成功。`coverage` 是观测平均误差是否不超过预算的经验比例，不是概率证书；`coverage_all_attempted_units` 是确认覆盖数除以全部尝试单元，未确认项不被称为测得的违反。证书、状态、历史暴露、feature/label 来源原样记录。

A0–A3 都使用同容量单标量校准。`pred_full_J` 等列存在时另报告 `full_J`，明确标记 `offline_full_J`，不会混进 A3 对 A1/A2 的可部署比较。

paired bootstrap 默认 2000 次，同一组场景索引同时重采样三个方法，先在每场景共同完整有效单元上计算 MAE，再等权合并场景。每次重采样重新选择 `min(mean MAE_A1, mean MAE_A2)` 作为较强基线；报告绝对/相对改善、95% 分位区间和严格改善概率。基线 MAE 为零时相对改善缺失，不填零。至少两个有效场景才生成区间。区间以已经保存的 LOSO/development 拟合为条件，未包含重新训练参数的不确定性，不是 p 值。

Failure AUC 只采用明确提供的 failure/failure_label/recovery_failure 或 success 标签，不从观测误差事后创造阈值。混合 noise draw 的正负类保留为 failure fraction，用加权 ROC AUC 避免任意多数表决。没有正负两类时保持 UNDEFINED。每场景报告 AUC；家族/噪声汇总另给等场景 AUC 均值及按场景平衡的 pooled AUC，均为描述证据。

## 输出

`STATISTICS_EVIDENCE.json`、`PAIRED_SCENE_BOOTSTRAP.json`、`STATISTICS_INPUT_AUDIT.json`，以及 `per_scene_statistics.csv`、`calibration_scales.csv`、`statistics_summary.csv`。缺失 CSV 或不可读输入保持明确来源状态，不制造零值结果。

新增成本：`CPU_RECEIPT.json` 的独立 scope，保守计 15 秒 CPU、0 GPU。此前 budget/transport 的 30 秒和边界补丁的 5 秒不重复登记，也没有预付未来统计运行或 unittest 的 CPU。
