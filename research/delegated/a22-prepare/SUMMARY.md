# A22 portable screening preparation: source-only handoff

状态：IMPLEMENTED_SOURCE_ONLY / NOT_RUN。模块、配置生成函数和独立测试均未被导入、运行或语法编译检查。本 worker 没有打开 A17 NPZ、读取任何实验数组/真值、调用物理动作、启动测试、运行部署、访问远端或计算哈希。实际准备与测试仅由主线程计费执行。

## 所有权与接口

新增源码 `src/a22/prepare.py`，公开函数为 `prepare_screening(root, config, book) -> portable_config`。`root` 必须指向 implementation 目录；`config` 为原配置映射；`book` 必须提供 `span`。不修改 `assets.py`、核心算法或原 `configs/a22.json`，也不在导入时执行资产准备。输入配置保持原样，返回配置为独立副本。

函数只接受冻结顺序 `[2001, 2003, 2014, 2009]`，只调用四次 `assets.load_online_scene(scene_id, config=config, book=book)`。读取能力沿用现有 loader 的三成员白名单与其计量 span。该 loader 中的固定 patch 与 acquisition 几何构建属于已知几何计算，不构建或调用 Maxwell 物理适配器。准备模块不调用 `_source` 直接打开源归档，也不调用 offline loader、场景生成器或完整 NPZ 复制。

## 主线程调用后产生的文件（当前尚未产生）

- `data/a22/online/scene_2001.npz`
- `data/a22/online/scene_2003.npz`
- `data/a22/online/scene_2014.npz`
- `data/a22/online/scene_2009.npz`
- `data/a22/online/MANIFEST.json`
- `configs/a22_portable.json`

四个新 NPZ 只有 `points`、`data0`、`init`。它们来自 online scene 的明确属性，逐成员写出，不复制混合源归档，也不写真值、held truth、labels、旧 Q、旧 scale、Jacobian 或 Hessian。每个文件使用同目录临时文件与原子替换。四场景读取与布局验证全部成功后才开始写 bundle。

portable 的 `scene_sources` 只保留四个 scene ID；每项 `source` 为对应 `scene_ID.npz`，其余字段严格为原公开 geometry 白名单：`family, rotation, n, truth_n, edge, wavenumber, background, init, partial, source_split, receiver_count`。其他 geometry 字段不进入配置或 manifest。配置中的显式 offline payload/path 字段会在任何源读取或输出写入前被拒绝；这些检查不读取字段指向的文件。

## 路径与远端重定位

manifest 和 `portable_assets` 中记录相对于 implementation 的 `data/a22/online`。由于现有 `assets._source` 会按照当前工作目录解析相对 `asset_root`，返回/保存配置的 `paths.asset_root` 使用本地绝对路径 `root/data/a22/online`。主线程远端 CLI 必须在加载前把此字段重设为远端执行目录的 `root/data/a22/online`。本 worker 没有实现或执行部署，也没有编辑任何远端 CLI。输出路径解析后必须仍在 implementation root 内，以避免目录/文件符号链接逃逸。

## Manifest 与数据边界

manifest 明确记录 `truth_n=14`（公开生成几何中声明的 2744 个 truth cell）与 `solver_n=12`（1728 个 solver cell）。它将离散差异标为存在，说明 preparation 保留该差异，不把它改写为同网格数据；truth cell 数来自公开标量元数据，未读取 truth array，也未做新的真值物理仿真。

布局记录来自准备的三个在线数组：points `(1728,3)` float64，data0 `(6,128)` complex128，init `(1728,)` complex128；六个 illumination、64 个 receiver position、每位置两个 polarization，实数打包维度 1536，illumination-major，每 source 的 real channels 后接 imaginary channels；solver complex-current 维度 5184。材料 chart 在运行 loader 时按已知 points 重建为 32 个 real coordinate，前 16 real 后 16 imaginary，并不部署旧 chart。

所有场景保持 `historically_exposed_feasibility`，`blind_holdout=false`。manifest 写入 `offline_members_loaded=[]`、`offline_labels_deployed=false`、`source_archive_copied=false` 和 physics/hash 动作计数 0。准备模块不读 gate，也不推导任何实验成功判断；manifest 的 gate 状态为 `NOT_ASSESSED_BY_PREPARATION`。

## 独立测试源码

新增 `tests/test_a22_prepare.py`，3 个普通 unittest：

1. mock 在线 loader，检查四个 NPZ 的成员恰为白名单，源配置对象与原 a22.json 不变，scene_sources 只有四场景与公开 geometry 字段，并检查 manifest 布局、历史暴露和 14/12 差异。
2. 在其他工作目录调用现有 resolver，检查 portable 的绝对本地路径仍定位到正确在线资产。
3. 额外 screening ID 或 offline 配置字段在任何 loader 调用/输出写入前被拒绝。

测试只生成小型在线 fixture；真实 A17 loader 被 mock，测试不访问 A17/真值资产或物理引擎。worker 未执行测试，也未调用其他测试。预期由主线程计费执行的命令为 `PYTHONPATH=src python -m unittest discover -s tests -p test_a22_prepare.py`；这不是已完成验证。

## CPU 交接

`CPU_EVENTS.jsonl` / `CPU_RECEIPT.json` 使用独立 `a22-prepare` scope。记录源码/配置读取与写交接文件的 shell CPU，并为 3 次实现 shell 各保守预留 1s、2 次 apply_patch 各保守预留 5s。预留不是测量；报告生成末尾的未测尾部也由该 shell 预留覆盖。没有 preparation/test/physics/remote/hash runtime，所有数组加载与运行结果均为 NOT_RUN。主线程应在 A22 实现台账中只合并该 scope 一次，并另外计量未来的实际 prepare 调用。
