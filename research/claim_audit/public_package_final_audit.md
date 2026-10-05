# 最终公开包静态审计

结论分类为 COMPLETE_AT_FINAL_WORKING_TREE_SNAPSHOT。仅核对当前仓库的文件、数据键、凭据候选与文档；未执行物理、SSH、网络、SHA 或重新计算科学 gate。历史预最终清单保留在 public_package_audit.json。

- 工作树普通文件 1274；tracked 320、非忽略 untracked 950、ignored 4。公开候选普通文件 1270；新审计三件输出在此快照之后生成。
- 351 个最终文本文件共 69,087,879 字节完整读到 EOF。replay.jsonl 17,124,397 字节、cost.jsonl 10,699,916 字节完整扫描，无前缀截断、读失败或读后大小变化。
- 912 个 NPZ、1080 个成员键：runtime 18 个、offline 标签 6 个、结果数组 888 个。只读键名，runtime 白名单/标签越界和持久 full-J/H/Green/LU 键候选均为 0。
- 凭据/私钥/带认证 URL/非占位凭据配置候选 0；第三方全文及持久矩阵缓存文件名候选 0。两处外部环境连接引用位于 tools/remote_jobs.py，未报告变量值。
- 7 个最终入口/报告/索引文档的包内链接问题 0，过时等待真实数据/结果语句候选 0。当前文档包含 runtime/offline 隔离、历史 Q/support 与未知形状限制、held receiver geometry 缺失 NOT_RUN 和第三方全文边界。
- A1/A2 的 QUALITY_GATE.json 是空对象：EMPTY_PLACEHOLDER_NO_SCIENTIFIC_FLAG。阶段标志仅从 GATE_DECISION.json 现有字段抄录；G0/REPRESENTATION 状态也只抄录，不重算或作科学判断。历史失败枚举没有覆盖当前顶层状态。
- 2 个 ignored matplotlib 字体缓存、ignored SOURCE_COMMIT 元数据与 private release note 均不在公开候选集合；其路径及分类在 JSON 中。
- 本地绝对路径来源/隐私上下文保留在 39 个文件、24494 处；不计作凭据，发布者需自行决定是否保留。报告只给路径、数量、分类，不给匹配文本。
- publication receipt 的 PENDING 按父任务指示作为预期发布前状态；未执行发布。执行失败 0。

tests/review_replay_interface.py 的历史敏感字段候选已分类为 NON_SECRET_FIXTURE_PLACEHOLDER_DECLARATION，属于非秘密 fixture/占位声明；当前完整扫描的凭据候选为 0。报告不含其值。

科学与访问限制：NPZ 键名检查不能证明数组数值语义；未反序列化不透明二进制。外部 URL 未联网验证。实验状态仅来自保存文件，未借此确认物理、性能、新颖性或 gate。后续公开 receipt 或文件内容发生变动时，本快照不覆盖这些变动。

详细路径/数量/分类及保存的 phase/G0 标志见 public_package_final_audit.json；CPU 与所有实际尝试见 public_package_final_audit_receipt.json。

父任务补充的来源分类：唯一 phase heatmap PDF 属于本轮自生成研究图，主线程已完成视觉检查，分类 GENERATED_RESEARCH_FIGURE，不列为第三方论文全文。此项为父任务提供的来源说明；本 worker 未重新扫描文件或作视觉/科学验收。A1/A2 空 QUALITY_GATE 对象仍为占位，最终阶段状态以 GATE_DECISION.json 为准。
