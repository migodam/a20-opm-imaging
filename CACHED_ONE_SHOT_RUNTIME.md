# 缓存one-shot时间记录

四个固定第一案例（direction0/amplitude0/noiseless/nominal），每个合法方法只计时一次，没有按耗时挑样本或增加repeat。这里只评估CPU缓存kernel，不是部署加速证据；主误差向量和S1–S4未改。

| 方法 | split中位耗时(ms) | 小QP中位耗时(ms) | 缓存读入+kernel中位耗时(ms) |
|---|---:|---:|---:|
| COMMON_32D | 0.0004 | 13.367 | 20.274 |
| RANDOM | 0.0424 | 3.896 | 10.890 |
| A1 | 0.0052 | 3.495 | 10.460 |
| A2 | 0.0046 | 3.460 | 10.425 |
| A3 | 0.0046 | 3.398 | 10.363 |

共享NPZ/cache读入只实际计费一次；独立归因的total列为每方法加回该实测读入，不能把该列横向相加当实际耗时。OS cache未flush，未核验cold deployment、noise编码、Q/descriptor重新构建或状态求解的端到端可比时间。离线full-J没有runtime claim。

本次OPM构建已有真实四scene收费记录（[online scene receipts](results/a22_r1/online/scene_2001.json)与其他scene同目录）：单scene原OPM构建约1.5–1.8秒，另外付费背景geometry/full forward、descriptor/identity等记录在各receipt中。核查构建仍rank32，没有新增full-wave label。不能拿上表的毫秒kernel当完整time-to-image。

cache replay完整网格wall为70.314607秒，含2112个common point验证、21120个受限解、42240条metrics及输出开销；它不是单个独立在线图像的部署耗时。所有失败/重跑/计时/审核都在[COST_LEDGER](results/a22_r1/COST_LEDGER.jsonl)，runtime额外20个小QP独立记录，不替换primary image。

原始测量：[CACHED_ONE_SHOT_RUNTIME.csv](results/a22_r1/CACHED_ONE_SHOT_RUNTIME.csv)；[summary](results/a22_r1/CACHED_ONE_SHOT_RUNTIME.json)。full-operator speedup / Gate T：NOT_ESTABLISHED。
