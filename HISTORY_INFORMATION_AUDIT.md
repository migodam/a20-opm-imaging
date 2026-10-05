# History 信息边界

冻结快照的 HISTORY 全部 **NOT_RUN_NO_OWN_ACCEPTED_TRAJECTORY**。iteration17 来自历史 trajectory，但没有恢复当前 FIXED/WIDE/CHEAP 算法自身真实上一 accepted step 的证据。没有把历史 full-GN、其它方法或 teacher 的步塞入 previous。

原 `reconstruct()` 接受后保存 `previous=alpha*step`，因此 frozen replay 的 previous=None 并不完整代表真实 history-aware algorithm。R1 保留默认旧行为；兼容 hook 使用不可变、复制的 `AcceptedHistory(parent, method, accepted_index, step)`，实 chart 坐标、索引从 1 开始。只有接受事件创建 token；拒绝 trial、NON_DESCENT 或 QP/core failure 不创建下一轮 history。owner、维度、有限性、索引和 material cache 都要核验。

FIXED/WIDE 将自身 previous 放入一个 M slot。CHEAP 的 task 与自身 previous 使用不同 slots；scaffold 不读 teacher。所有六源 B 注入仍在压缩前执行；metadata 保存 previous norm、owner、accepted index、slot 以及 qM/final-Z capture。alpha 缩放和拒绝步不更新已用 mocked-loop 测试验证。

真实闭环驱动在 `src/a20_r1/closed_loop.py`：从原初始化开始，三对象、原 18 outer/24 trials、A1 full-state、原 prior/LM/Armijo/KKT，独立 paid offline own-state references。它不借 FULL_GN trajectory 作为另一方法 history。online verifier 的 FullJacobian 不被 offline matrix 缓存暖化；诊断失败不回流 proposal。

**该闭环代码未执行成像。** Gate B FAIL，Gate A/C HOLD，无法启动 Phase2；三次 matched FIXED history ON/OFF ablation 也 NOT_RUN。mocked-loop/owner 测试不是 history 因果证据。本次不能确认或否定 H3，更不能选择 HISTORY-CONDITIONING CONFIRMED。
