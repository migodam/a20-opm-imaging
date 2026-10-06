# A21 真实交付完整性只读审计

冻结引擎 `5c6bcb02bb4ab88f7b46f07bca4ca3f4e38a067c`；记录 job `a21-anatomy-01`。审计只读取真实五态结果、NPZ 数组头、缓存 provenance 和成本账本，并新增本文件及唯一 CPU receipt。没有运行 Maxwell、QP、测试、SVD 或重新计算科学指标，没有改动源码或结果。

完整性检查结果：**PASS，附直接计数口径说明**。`rows.jsonl` 共 35 条，每个 state/arm 键只有一个终态，35 条均为 `OK`；五个共享 NPZ/JSON 缓存和 35 个诊断 NPZ 均存在。summary 保存 35 格，T0 为 `PASS`。这些是交付事实，不构成最终科学判断。

## 状态、秩和内存

| 状态 | 唯一终态臂 | G trial/test/union | BOTH_PG trial/test/union | RANDOM_PG trial/test/union | G 基内存 MiB | PG 双基内存 MiB | shared cache MiB |
|---|---:|---|---|---|---:|---:|---:|
| 2001/17 | 7 | 56/56/56 | 56/56/62 | 56/56/62 | 4.429688 | 8.859375 | 33.181042 |
| 2005/17 | 7 | 56/56/56 | 56/56/62 | 56/56/62 | 4.429688 | 8.859375 | 33.181042 |
| 2003/17 | 7 | 56/56/56 | 56/56/62 | 56/56/62 | 4.429688 | 8.859375 | 33.181103 |
| 2007/17 | 7 | 56/56/56 | 56/56/62 | 56/56/62 | 4.429688 | 8.859375 | 33.181034 |
| 2013/17 | 7 | 56/56/56 | 56/56/62 | 56/56/62 | 4.429688 | 8.859375 | 33.181049 |

rank 为执行时保存在终态记录中的实际数值；trial/test 列数及内存另用 NPZ 头和 complex128 itemsize 独立核对。union rank 本次未重新作 SVD。G 运行时仅存一份公共 trial/test 基；NPZ 为明确记录同时保留 Z/W，不能把磁盘两份当成 G 运行时双基内存。全部 Z/W 为 `(5184,56)`；G 单基为 4,644,864 bytes，PG 双基为 9,289,728 bytes。全部 raw-coordinate transform 形状与共享 bank width 一致。

## 随机对照的实际新增 rank

| 状态 | oracle X/Y/XY 相对 U | BOTH_G / RANDOM_G | BOTH_PG trial/test | RANDOM_PG trial/test | 新增 rank / frozen seeds |
|---|---|---|---|---|---|
| 2001/17 | 6/6/12 | 12/12 | 6/6 | 6/6 | MATCH |
| 2005/17 | 6/6/12 | 12/12 | 6/6 | 6/6 | MATCH |
| 2003/17 | 6/6/12 | 12/12 | 6/6 | 6/6 | MATCH |
| 2007/17 | 6/6/12 | 12/12 | 6/6 | 6/6 | MATCH |
| 2013/17 | 6/6/12 | 12/12 | 6/6 | 6/6 | MATCH |

采用 `trial_QR/test_QR.independent_protected_added_rank` 实际独立新增数，不仅检查申请列数。每态 seeds 均为 `[20261006,parent,17,2101/2102/2103]`，G、PG-trial、PG-test 的命名空间不同。全部 G 记录为 Galerkin，全部 PG 为 Petrov；所有缓存均记未修复 full reference、未读 truth/labels、未启用 fallback。

## 缓存与诊断数组

五个 cache NPZ 的 44 个必需键和 35 个 diagnostic NPZ 的 42 个必需键全部存在。核对了 JF/JR `(1536,54)`、HF/Lambda `(54,54)`、Q `(1728,27)`、X/Y/forcing `(5184,6)`、U `(5184,8)`、baseline `(5184,56)`，以及 D/LD/SD/DHB/DHDL 的对应 shared-bank 维度。缓存均没有 dense L 或 raw S，metadata 为 `dense_L_persisted:false` 和 `raw_S_persisted:false`。

完整诊断包含 real J/H/r/ell/Lambda、raw steps、delta_p/d、amplified_primal、eta_sum/direct/pair、rho_F/R、normals、multipliers、slacks 和 active indices；并保留 Z/W 与 T_Z/T_W。核对范围为数组头、形状、dtype 与 payload 字节长度，不声称读取全部元素或重算数值恒等式。

## 共享 RHS 和原账本

| 状态 | full state / LU | 初始 full J RHS | 追加 validation JVP/VJP RHS | oracle primal/adjoint RHS | reduced QP |
|---|---|---:|---|---|---:|
| 2001/17 | 1/1 | 324 | 12/12 | 6/6 | 7 |
| 2005/17 | 1/1 | 324 | 0/0 | 6/6 | 7 |
| 2003/17 | 1/1 | 324 | 12/12 | 6/6 | 7 |
| 2007/17 | 1/1 | 324 | 0/0 | 6/6 | 7 |
| 2013/17 | 1/1 | 324 | 12/12 | 6/6 | 7 |

所有 RHS、calls、QP 以及 protected/cache 操作的成本 event 原子 counters 求和与 anatomy job receipt 逐键一致。三个辅助 counter 例外：`L_upload_bytes=2149908480`、`operator_transfer_bytes=177168384` 被原 backend 直接计入 `book.counts`（`src/a20/backend.py:154,167`），`material_optimizer_iterations=1893` 被原 material solver 直接计入（`src/a20/material.py:136`），均没有对应 event counter；这是现有记录口径，不能用 cost event 单独重建全部辅助计数。总计 5 full states、5 full LU、30 state-forward RHS、1620 原始 full-J RHS、36 validation JVP RHS、36 validation VJP RHS，以及 60 独立 oracle RHS（30 primal + 30 adjoint）。Oracle counters 和 native solve 指向同一批 oracle solves，没有作为 120 RHS 再次相加。35 arm 的局部成本均无 full-state/full-RHS counter；全部共享 operator image 建立一次/state后被臂复用。共有 797 cost events、35 reduced QPs、0 full-reference repairs；物理 job ledger 唯一一条。

实际 physical job inclusive CPU 为 267.359375 s，GPU 占用为 281.661815 s；本审计不叠加 nested span 秒数。

| 原账本路径 | 与 A20-R1 原包的比较 |
|---|---|
| `results/JOB_LEDGER.jsonl` | BYTE_IDENTICAL |
| `results/BUDGET_FINAL.json` | BYTE_IDENTICAL |
| `results/a20_r1/JOB_LEDGER.jsonl` | BYTE_IDENTICAL |
| `results/a20_r1/BUDGET_FINAL.json` | BYTE_IDENTICAL |
| `results/a20_r1/BUDGET_CURRENT.json` | BYTE_IDENTICAL |
| `results/a20_r1/ACTION_COST.jsonl` | BYTE_IDENTICAL |

另外 36 个共同历史 job receipt/cost/manifest/result 文件与 A20-R1 原包逐字节相同；本次没有写旧账本。原包存在但交付副本未带的文件标为 `NOT_COPIED`，不能宣称该副本已独立核验。比较为直接读取字节，不计算 hash。A21 新成本单列于 `results/a21/JOB_LEDGER.jsonl` 和 `results/a21/COST_LEDGER.jsonl`，历史 carry 仍为 CPU 5606.616051 s、GPU 5661.778859 s。

## 问题与边界

未发现缺失、重复、shape/memory、随机新增 rank 或 RHS 账目冲突。两个传输 byte counter 和一个 optimizer-iteration counter 仅见于 receipt，是原代码的直接计数方式；本次没有重写记录或对它们推断免费传输/优化。科学解释及最终 gate 留给主线程。

一次只读 accounting follow-up 因断言遗漏第三个直接计数 counter 而提前退出；错误证据与其未单独测得的 CPU 均计入唯一 receipt，使用该进程 14 s soft CPU cap 作为保守计费。未跑物理或测试，也未重写结果。

本次唯一 CPU 计费 receipt：`research/delegated/a21-engine/REAL_OUTPUT_AUDIT_CPU_RECEIPT.json`。
