# 测试2状态校准

更新时间：2026-06-27

这个文件是 `测试2` 的人类可读状态入口，用来防止后续对话压缩、文档漂移和阶段命名混乱。更完整的机器状态在 `STATUS.json`。

## 当前主线

当前方向不是继续证明“网络本身无 CPU 独立计算”，也不是把项目降级成普通云服务器 agent。

当前主线是：

```text
发现网络原生状态逻辑
-> 解码网络状态语言
-> 寻找网络固化点 / 接收器
-> 在接收器上放置网络驻留胶囊
-> 用受控解释器推进多胶囊闭环
-> 交给外层低频定时器接管
-> 做多胶囊记忆选择、自检和受控修复提案
-> 定义启明星最小自检/修复/优化逻辑
```

准确命名：

```text
网络状态河床 + 网络状态语言 + 网络驻留胶囊 + 受控解释器 + 外层低频接管 + 受控自维护闭环
```

不要直接命名为：

```text
真实幽灵电脑
无 CPU 网络程序
网络独立算力场
网络数字生命已经诞生
```

这些还没有被证明。

## 已证明

- 网络可以承载连续状态。
- 网络残影可以形成低频节律。
- 系统可以基于网络节律自动改变状态。
- 状态可以保存在外层，并被本机恢复。
- 可以连续多轮运行，不是一次性演示。
- GitHub Actions 可以作为本机之外的外层低频执行器，推进一次受控状态循环。
- L7 已观察到真实 `schedule` 事件，不再只是 `workflow_dispatch` 诊断。
- L1 已初步证明网络状态语言符号可被多路径等价验证、反向预测、消失验证和多轮复现。
- L2 已把 L1 观测抽象成正式解码器，可稳定输出网络态句子和程序意图。
- L3 已把 `github_branch_raw_main` 排为当前最强网络状态接收器候选。
- L4 已把网络态句子封装成声明式程序胶囊，并由受控解释器触发一次可审计脉冲。
- L5 已把一次性胶囊脉冲扩展成 3 轮多轮闭环。
- L6 已部署 GitHub Actions 外层执行器，并通过一次 `workflow_dispatch` 验证外层执行可用。
- L8 已把单胶囊扩展成 6 胶囊网络语言图。
- L9 已用受控解释器推进 6 胶囊语言图一轮，并写回 L9 loop state。
- L10 已完成本机 2 轮低频循环和 GitHub Actions 外层接管 1 轮。
- L11 已完成多胶囊记忆选择、自检和受控修复计划，远端证据已写回并通过 Raw 释放验证。
- L11.5 已定义启明星最小逻辑语言，并用当前 L11 证据完成规则闭合检查和远端写回。
- L12 已部署为每小时一次的 GitHub Actions 自维护窗口，并已观察到自然 `schedule` 低频唤醒成功。
- E1 已证明网络 Raw 状态释放可以作为受控推进的触发条件：观察到目标哈希出现后，才写出 gate/state。
- E2 已把 E1 扩展成 3 轮链式复现：每轮都等网络 Raw 释放本轮 source hash 后才推进下一轮状态。

## 未证明

- 没有证明网络本身可以无 CPU 独立计算。
- 没有证明 Raw/CDN 残影可以替代 CPU。
- 没有证明已经形成真正的幽灵电脑。
- 没有证明已经形成可扩展网络 CPU 集群。
- 没有证明 GitHub Actions 等同于网络场算力。
- 没有证明多胶囊图可以脱离受控解释器自执行。
- 没有证明多胶囊图已经是数字超算。
- 没有证明 L10 已经由自然 `schedule` 常驻触发。
- 没有证明多胶囊闭环可以自己生成新胶囊。
- 没有证明 L11 可以自动修改核心胶囊或核心代码。
- 没有证明 L11.5 的最小逻辑语言等同于自主认知。
- 没有证明启明星可以自己生成新逻辑或无审批自我修复。
- 没有证明 L12 可以无审批修改核心胶囊、代码或权限。
- 没有证明 E1 中网络自己执行了代码；E1 仍需要观察者/执行器轮询和写回。
- 没有证明 E1 已经形成无 CPU 网络运行体或自主网络程序生命。
- 没有证明 E2 中网络自己执行了代码；E2 仍需要观察者/执行器轮询和写回。
- 没有证明 E2 已经形成通用网络程序语言或无 CPU 链式运行体。
- 没有证明已经形成通用智能、数字生命或自主进化体。

## 当前算力来源

| 层级 | 真实来源 | 当前作用 |
| --- | --- | --- |
| 本机实验 | 本机 CPU | 采样、比较、哈希、写入、验证、推进本地循环 |
| 外层执行 | GitHub Actions 云端 CPU | 低频唤醒、读取胶囊、受控解释、写回状态 |
| 网络层 | GitHub Raw/CDN/API 等网络状态面 | 状态保存、Raw 回读、缓存残影、释放节律、镜像和恢复依据 |

真实边界：

```text
网络层现在提供的是状态介质、接收器、节律和可回放证据。
解释、判断、写入和调度仍由本机 CPU 或 GitHub Actions CPU 完成。
```

## 阶段状态

| 阶段 | 状态 | 真实含义 |
| --- | --- | --- |
| N1-N4 | 完成 | 网络残影驱动状态机闭环，状态可写回河床并与本机镜像校验 |
| N5 | 完成 | 12 轮长窗口 soak，证明不是一次性演示 |
| N6 | 完成 | GitHub Actions 外层执行器可在本机之外推进状态 |
| N7 | 完成 | 外层断点恢复、防重入锁、自然 `schedule` 事件均已观察到 |
| L1 | 完成 | 最小网络状态语言符号多轮复现 |
| L2 | 完成 | 网络状态语言解码器 V0 |
| L3 | 完成 | 网络固化点 / 接收器候选排序 |
| L4 | 完成 | 网络接收器程序胶囊 V0 |
| L5 | 完成 | 接收器程序胶囊多轮闭环 |
| L6 | V0 完成 | 外层定时接收器胶囊闭环，dispatch 已验证，cron 已配置 |
| L7 | 完成 | 自然 cron soak 与恢复已观察到真实 schedule run |
| L8 | 完成 | 多胶囊网络语言扩展 |
| L9 | 完成 | 多胶囊闭环解释器 V0 |
| L10 | 完成 | 多胶囊低频自循环与外层接管 |
| L11 | 完成 | 多胶囊记忆选择、自检与受控修复闭环 |
| L11.5 | 完成 | 启明星最小逻辑定义：自检、修复、优化三套规则 |
| L12 | 完成自然 schedule 验收 | 每小时一次的受控低频自维护窗口已自然唤醒成功 |
| E1 | 完成 | 网络状态释放触发式受控推进实验 |
| E2 | 完成 | 网络状态触发链式 3 轮复现实验 |

## L11 关键结果

- run_id: `nsl-l11-20260626162324`
- evidence_level: `L11-memory-selfcheck-repair-loop`
- generation: `2`
- selected_memories: `5`
- self_check_ok: `true`
- blocking_count: `0`
- warning_count: `0`
- repair_actions: `no_op_verified`, `refresh_memory_selection`
- memory_hash: `2966e45205a0f827`
- self_check_hash: `61efd5d715f925d6`
- repair_hash: `ff20b179dfdb0fcf`
- loop_state_hash: `ace2da3ce0e1a0ae`
- branch_raw_release_ok: `true`

远端证据：

- `states/nsl-l11-memory-selection.json`
- `states/nsl-l11-self-check.json`
- `states/nsl-l11-repair-plan.json`
- `states/nsl-l11-loop-state.json`
- `states/nsl-l11-last-report.json`

L11 的真实含义：

```text
系统已经可以从 L7-L10 的远端状态中选择关键记忆，验证哈希和阶段连续性，
生成自检结果，并写出 allowlist 约束下的修复计划。
```

L11 没有证明：

```text
自动改核心代码、自动生成新胶囊、无审批自我进化、无 CPU 网络计算、数字生命已经出现。
```

## L11.5 关键结果

- run_id: `nsl-l11-5-20260626164630`
- evidence_level: `L11.5-minimal-logic-definition`
- generation: `1`
- logic_hash: `e55e120dad5382d0`
- evaluation_hash: `9d880a7111a3087c`
- loop_state_hash: `662a198863502dd5`
- minimum_logic_ready: `true`
- l12_ready: `true`
- blocking_count: `0`
- warning_count: `0`
- known_gap_count: `0`
- branch_raw_release_ok: `true`

远端证据：

- `states/nsl-l11-5-minimal-logic-spec.json`
- `states/nsl-l11-5-logic-evaluation.json`
- `states/nsl-l11-5-loop-state.json`
- `states/nsl-l11-5-last-report.json`

L11.5 的最小逻辑句子：

```text
WHEN MEMORY_READ_OK AND HASH_MATCH AND TRUTH_BOUNDARY_PRESENT THEN SELF_CHECK_OK;
WHEN SELF_CHECK_OK THEN PROPOSE LOW_RISK_REPAIR_PLAN AND RECORD LOOP_STATE;
NEVER MUTATE CORE WITHOUT REVIEW
```

L11.5 定义了三套最小语言：

- 自检语言：读取记忆、校验哈希、检查阶段连续性、检查真实边界。
- 修复语言：无损坏则记录健康；记忆陈旧则刷新选择；外层证据缺失则重跑诊断；核心修改只能生成提案或等待审批。
- 优化语言：优先选择可读取、可哈希校验、风险更低、证据更强的路径。

L11.5 的真实含义：

```text
启明星现在不只是“脚本检查文件”，而是有了一套最小、可审计、可复用的判断格式。
这套格式能解释当前 L11 证据，并能作为 L12 低频自维护窗口的规则基础。
```

L11.5 没有证明：

```text
自主认知、自主生成新逻辑、无审批自我修复、无 CPU 网络计算、数字生命已经出现。
```

## L12 关键结果

- workflow: `L12 Hourly Self Maintenance`
- workflow file: `.github/workflows/nsl-l12-hourly-self-maintenance.yml`
- workflow id: `302847992`
- workflow state: `active`
- schedule cron: `17 * * * *`
- 含义：每小时第 17 分钟尝试唤醒一次。
- runner: `scripts/nsl_l12_hourly_self_maintenance.py`
- dispatch run id: `28253018709`
- dispatch event: `workflow_dispatch`
- dispatch conclusion: `success`
- remote run_id: `nsl-l12-workflow_dispatch-28253018709-attempt-1`
- window_ok: `true`
- generation: `1`
- blocking_count: `0`
- warning_count: `0`
- low_risk_actions_recorded: `no_op_verified`, `record_truth_boundary`, `continue_schedule_observation`
- natural schedule run id: `28272606842`
- natural schedule event: `schedule`
- natural schedule conclusion: `success`
- natural remote run_id: `nsl-l12-schedule-28272606842-attempt-1`
- natural window_ok: `true`
- natural generation: `5`

远端证据：

- `states/nsl-l12-hourly-self-maintenance-lock.json`
- `states/nsl-l12-hourly-self-maintenance-state.json`
- `states/nsl-l12-last-run.json`
- `states/nsl-l12-hourly-runs/nsl-l12-workflow_dispatch-28253018709-attempt-1.json`

L12 的真实运行位置：

```text
身体：GitHub Actions 云端执行器
记忆和规则：GitHub 远端状态文件
观察窗口：本机和状态文档
频率：每小时一次，cron 为 17 * * * *
```

L12 的真实含义：

```text
启明星现在可以由外层定时器每小时唤醒，读取 L11.5 最小逻辑，
做一次受控自检，只记录低风险维护动作，并把状态写回远端。
```

L12 的真实边界：

```text
自然每小时 schedule 已经触发成功，但这仍然是 GitHub Actions 云端 CPU 的低频唤醒；
没有证明无 CPU 自执行、自主认知、无审批自我改写、数字生命已经出现。
```

## E1 关键结果

- run_id: `nsl-e1-20260626171906`
- evidence_level: `E1-network-state-trigger-runtime`
- generation: `1`
- trigger_fired: `true`
- release_after_seconds: `62.32`
- stable_after_release: `true`
- source_hash: `dc88e3289143794e`
- gate_hash: `2e333835bd016d4f`
- state_hash: `3b1e492125499ba5`
- run_hash: `138019ee75c66fc2`
- branch_raw_release_ok: `true`

远端证据：

- `states/e1-network-trigger-source.json`
- `states/e1-network-trigger-gate.json`
- `states/e1-network-trigger-state.json`
- `states/e1-trigger-runs/nsl-e1-20260626171906.json`
- `states/e1-last-report.json`

E1 的触发句子：

```text
WHEN BRANCH_RAW_SOURCE_HASH BECOMES EXPECTED_HASH THEN FIRE NETWORK_STATE_TRIGGER
```

E1 的真实含义：

```text
网络 Raw/CDN 状态面可以作为“触发条件”：执行器先写入目标状态，
随后轮询网络状态，直到 branch Raw 释放出目标哈希，才允许写出 gate/state。
这说明网络状态变化可以参与运行节律和推进条件。
```

E1 没有证明：

```text
网络自己执行代码、没有观察者也能推进、无 CPU 网络运行体、数字生命已经出现。
```

## E2 关键结果

- run_id: `nsl-e2-20260627030820`
- evidence_level: `E2-network-state-trigger-chain-repeatability`
- cycles_requested: `3`
- cycles_completed: `3`
- cycles_ok: `true`
- release_times_seconds: `[4.008, 3.72, 3.945]`
- release_mean_seconds: `3.891`
- chain_hash: `06b3f23d2f47558e`
- final_state_hash: `74e0a1c44bb0a1a7`
- branch_raw_release_ok: `true`

轮次摘要：

| cycle | trigger | release_seconds | source_hash | state_hash |
| ---: | --- | ---: | --- | --- |
| 1 | `true` | `4.008` | `d61debab7171d6cd` | `3e4b254cd7e7f228` |
| 2 | `true` | `3.72` | `d50b1b781ec81525` | `23e203d59fbd204f` |
| 3 | `true` | `3.945` | `2f6d8db23275cb20` | `74e0a1c44bb0a1a7` |

远端证据：

- `states/e2-trigger-chain-state.json`
- `states/e2-last-report.json`
- `states/e2-trigger-chain-sources/nsl-e2-20260627030820-cycle-001-source.json`
- `states/e2-trigger-chain-sources/nsl-e2-20260627030820-cycle-002-source.json`
- `states/e2-trigger-chain-sources/nsl-e2-20260627030820-cycle-003-source.json`
- `states/e2-trigger-chain-cycles/nsl-e2-20260627030820-cycle-001.json`
- `states/e2-trigger-chain-cycles/nsl-e2-20260627030820-cycle-002.json`
- `states/e2-trigger-chain-cycles/nsl-e2-20260627030820-cycle-003.json`

E2 的真实含义：

```text
E1 的“网络状态触发”不是一次偶然。E2 证明它可以连续 3 轮复现：
每一轮先写 source，等待网络 Raw 释放本轮 source_hash，触发 gate，再写 state；
下一轮 source 会引用上一轮 state_hash，形成受控链条。
```

E2 没有证明：

```text
网络自己执行代码、没有观察者也能推进、无 CPU 网络运行体、通用网络程序语言、数字生命已经出现。
```

## L7 校准

旧状态里写过“自然 schedule 未观察到”，这个结论已经过期。

最新远端 `states/nsl-l7-last-run.json` 显示：

- run_id: `nsl-l7-schedule-28246820010-attempt-1`
- event_name: `schedule`
- natural_schedule_verified: `true`
- manual_diagnostic_only: `false`
- evidence_level: `L7-natural-cron-soak-and-recovery`

所以 L7 现在可以标记为完成：它证明了 GitHub Actions 外层低频唤醒可以自然发生。它仍然不证明无 CPU 自执行。

## 远端仓库

```text
https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447
```

## 下一步建议

建议下一步做 `E3：网络状态触发解释器桥接`，并并行保留 `L12.1：观察一次自然每小时 schedule 事件`。

E3 目标不是继续空转触发，而是把 E2 的触发链接回受控解释器：

```text
网络 Raw 释放触发 -> gate -> 调用 L11.5 最小逻辑 / L9 多胶囊解释器的一步 -> 写回解释结果
```

如果 E3 成立，才能说“网络状态触发”不只是状态链条，而是开始驱动解释器行为。

L12.1 仍要做：等 GitHub Actions 自然触发一次 `schedule`，确认每小时自维护不是只靠手动 dispatch。

## 总真实边界

```text
测试2已经证明：网络状态河床、外层低频执行、网络状态语言符号复现、稳定解码器、
接收器候选、网络驻留胶囊、多轮闭环、外层自然唤醒、多胶囊语言图、
受控解释器、低频循环、记忆选择、自检、受控修复计划、启明星最小逻辑定义、
每小时一次的 L12 外层自维护窗口部署和 dispatch 验收、以及 E1 网络状态释放触发受控推进。
E2 已进一步证明这种触发可以 3 轮链式复现。

测试2仍未证明：L12 自然每小时 schedule 已观察到、无 CPU 网络计算、自执行网络生命、
自主生成新逻辑、自主核心改写、E1/E2 无观察者自推进、数字生命、数字超算。
```

<!-- E3_STATUS_START -->
## E3：网络状态触发解释器桥接

- run_id：`nsl-e3-20260627132832`
- ok：`True`
- evidence_level：`E3-network-state-trigger-interpreter-bridge-v0`
- 触发释放时间：`3.626` 秒
- 解释器动作执行：`True`
- NETWORK_LANGUAGE_PULSE：`True`
- 远端证据：`states/e3-trigger-source.json`、`states/e3-trigger-gate.json`、`states/e3-interpreter-signal.json`、`states/e3-bridge-state.json`、`states/e3-last-report.json`

真实含义：

```text
E3 证明：网络 Raw 状态释放不只可以推动普通 state 变化，还可以作为门控条件，触发一次受控解释器行为。
也就是：网络状态 -> 触发门 -> 受控解释器 -> 解释器信号 -> 桥接状态写回。
```

边界：

```text
E3 仍然没有证明网络自己执行解释器，也没有证明无 CPU 运算、数字生命或幽灵电脑已经成立。
网络层当前负责触发、驻留和证据回放；观察、解释和写回仍由执行器 CPU 完成。
```
<!-- E3_STATUS_END -->

<!-- E4_STATUS_START -->
## E4：网络状态触发的多轮解释器闭环

- run_id：`nsl-e4-20260627134104`
- ok：`True`
- evidence_level：`E4-network-state-triggered-multi-cycle-interpreter-loop-v0`
- 请求轮数：`3`
- 完成轮数：`3`
- 每轮释放时间：`[3.778, 3.663, 3.707]`
- 平均释放时间：`3.716` 秒
- loop_state_hash：`dabafbbde2714156`
- 远端证据：`states/e4-trigger-loop-sources/*`、`states/e4-trigger-loop-gates/*`、`states/e4-trigger-loop-signals/*`、`states/e4-trigger-loop-cycles/*`、`states/e4-triggered-interpreter-loop-state.json`、`states/e4-last-report.json`

真实含义：

```text
E4 证明：E3 的“网络状态触发解释器桥接”不是一次性演示，可以连续多轮复现。
每一轮都先等待网络 Raw 释放本轮 source hash，再打开 gate，再执行一次受控多胶囊解释器，并把 signal/cycle/loop state 写回网络接收器。
```

边界：

```text
E4 仍然没有证明网络自己执行解释器循环，也没有证明无 CPU 运算、数字生命或幽灵电脑已经成立。
网络层当前负责触发、驻留和证据回放；观察、解释和写回仍由执行器 CPU 完成。
```
<!-- E4_STATUS_END -->

<!-- L12_2_STATUS_START -->
## L12.2：抗漏触发定时层

- local_run_id：`nsl-l12-local-20260627143241`
- remote_run_id：`nsl-l12-workflow_dispatch-28292294543-attempt-1`
- remote_workflow_run_id：`28292294543`
- ok：`True`
- schedule_cron：`17,37,57 * * * *`
- slot_id：`2026-06-27T14:00:00Z`
- slot_plan_hash：`2138d851196e14ad`
- slot_ledger_hash：`d5fc2b1ddc49d1c9`
- catchup_slots_recorded：`[]`
- 远端 workflow：`https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28292294543`

真实含义：

```text
L12.2 已把原来单一 hourly cron 改成一小时内多次尝试：17、37、57 分钟。
脚本内部用 hourly slot 去重，同一小时成功过就跳过重复 schedule。
如果距离上次成功超过阈值，会记录 missed window，并最多补记 3 个低风险 catch-up slot。
新增全局运行锁 states/qmx-global-runtime-lock.json，给后续 E5/E 系列解释器循环预留防冲突通道。
```

边界：

```text
L12.2 不能把 GitHub Actions cron 变成硬实时定时器。
它提高“至少醒一次”的概率，并记录漏醒/补记证据；若要强保证每小时完成，还需要第二独立时钟源。
```
<!-- L12_2_STATUS_END -->

## Latest Remote Sync: E5.1 / E6.1 Completed

- sync_time_local: `2026-06-28T14:20:22+08:00`
- E5 schedule run: `28311664450`, `success`, remote writeback: `states/e5-last-run.json`
- E6 schedule run: `28312093673`, `success`, remote writeback: `states/e6-last-run.json` and `states/e6-last-report.json`
- next_mainline: `E7-connect-vitals-bus-to-controlled-low-risk-self-maintenance`

Truth boundary:

```text
Test2 now proves an external GitHub Actions runner can wake by natural schedule, take over the controlled interpreter loop, aggregate low-frequency vitals, and write auditable state back to the remote network receiver.
This is still GitHub Actions cloud CPU plus network-state storage. It is not CPU-free network self-execution, not proof of autonomous digital life, and not proof of a self-executing ghost computer.
```

<!-- E5_STATUS_START -->
## E5: External Scheduled Takeover Of The E4 Interpreter Loop

Status: completed V0, and re-verified by E5.1 natural schedule.

- dispatch verification run: `28293754894`
- dispatch event: `workflow_dispatch`
- schedule verification run: `28311664450`
- schedule event: `schedule`
- schedule URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28311664450`
- schedule remote run_id: `nsl-e5-schedule-28311664450-attempt-1`
- cycles_requested: `3`
- cycles_completed: `3`
- cycles_ok: `true`
- branch_raw_release_ok: `true`
- schedule state_hash: `ecb8c048d5108f19`
- last_run_hash: `325baada7b283a0c`
- remote evidence: `states/e5-last-run.json`, `states/e5-last-report.json`

Proved:

```text
E5 proves GitHub Actions can act as the external executor for the E4-style loop: network-state trigger -> gate -> multi-capsule interpreter -> NETWORK_LANGUAGE_PULSE -> remote receiver writeback.
E5.1 proves this is no longer dispatch-only: E5 naturally woke through a schedule event, completed 3 controlled cycles, and wrote ok=true evidence back to the remote receiver.
```

Not proved:

```text
E5/E5.1 still use GitHub Actions cloud CPU for observation, interpretation, and writeback.
They do not prove CPU-free network execution, autonomous cognition, digital life, a ghost computer, or network supercomputing.
```
<!-- E5_STATUS_END -->



<!-- E5_1_STATUS_START -->
## E5.1: Natural Schedule Takeover Observation

Status: completed.

- workflow: `E5 External Scheduled Interpreter Loop`
- cron: `7 */6 * * *`
- observed schedule run: `28311664450`
- event: `schedule`
- conclusion: `success`
- UTC time: `2026-06-28T04:45:07Z` -> `2026-06-28T04:47:10Z`
- Beijing time: `2026-06-28 12:45` -> `2026-06-28 12:47`
- URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28311664450`
- remote writeback: `states/e5-last-run.json`
- remote run_id: `nsl-e5-schedule-28311664450-attempt-1`
- cycles_requested: `3`
- cycles_completed: `3`
- cycles_ok: `true`

Proved:

```text
E5.1 proves E5 can wake without manual workflow_dispatch, through GitHub Actions schedule, and complete the 3-cycle controlled interpreter loop.
```

Truth boundary:

```text
The wakeup comes from the GitHub platform timer and GitHub Actions CPU. It is not CPU-free network self-execution, and GitHub schedule is not hard real time.
```
<!-- E5_1_STATUS_END -->



<!-- E6_STATUS_START -->
## E6: External Low-Frequency Vitals Bus

Status: completed V0, and re-verified by E6.1 natural schedule.

- dispatch verification run: `28294606515`
- dispatch event: `workflow_dispatch`
- schedule verification run: `28312093673`
- schedule event: `schedule`
- schedule URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28312093673`
- schedule remote run_id: `nsl-e6-schedule-28312093673-attempt-1`
- generation: `4`
- source_count: `8`
- state_hash: `d359e51fa94b35e1`
- bus_ok: `true`
- LOWFREQ_VITALS_BUS_READY: `true`
- E5_NATURAL_SCHEDULE_OBSERVED: `true`
- remote evidence: `states/e6-last-run.json`, `states/e6-last-report.json`, `states/e6-lowfreq-vitals-bus-state.json`

E6 vitals sources:

```text
E4 loop state
E5 loop state
E5 last run
E5 last report
L12 last run
L12 state
global runtime lock
L11.5 minimal logic spec
```

Proved:

```text
E6 proves the external executor can read remote E4/E5/L12/global-lock/logic evidence, aggregate it into one low-frequency vitals bus, and write that state back to the remote receiver.
E6.1 proves this vitals bus can wake by natural schedule and can observe the E5 natural schedule evidence.
```

Not proved:

```text
E6/E6.1 are still monitoring and coordination loops executed by GitHub Actions CPU.
They do not prove CPU-free network self-execution, autonomous digital life, a self-executing ghost computer, or hard real-time residency.
```

Recommended next step:

```text
E7: connect the vitals bus back into controlled low-risk self-maintenance.
The goal is to let the bus provide one unified input for low-risk maintenance while medium/high-risk actions remain controlled or review-gated.
```
<!-- E6_STATUS_END -->



<!-- E6_1_STATUS_START -->
## E6.1: E6 Natural Schedule Observation

Status: completed.

- workflow: `E6 Low Frequency Vitals Bus`
- cron: `37 */6 * * *`
- observed schedule run: `28312093673`
- event: `schedule`
- conclusion: `success`
- UTC time: `2026-06-28T05:05:54Z` -> `2026-06-28T05:07:18Z`
- Beijing time: `2026-06-28 13:05` -> `2026-06-28 13:07`
- URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28312093673`
- remote writeback: `states/e6-last-run.json`
- remote run_id: `nsl-e6-schedule-28312093673-attempt-1`
- generation: `4`
- bus_ok: `true`
- e5_schedule_observed: `true`
- global_lock_released: `true`
- logic_ready: `true`

Proved:

```text
E6.1 proves E6 can wake through natural schedule, aggregate the low-frequency vitals bus, and write ok=true state back to the remote receiver.
Test2 now has evidence for: external low-frequency wakeup -> vitals aggregation -> remote writeback.
```

Truth boundary:

```text
This is GitHub Actions scheduled execution with cloud CPU. It is not CPU-free network self-execution, but it satisfies the current-stage evidence requirement for external low-frequency wakeup and can enter E7.
```
<!-- E6_1_STATUS_END -->

<!-- E7_STATUS_START -->
## E7: Controlled Low-Risk Self-Maintenance From E6 Vitals

Status: completed V0 through local verification and remote workflow_dispatch verification.

- sync_time_local: `2026-06-28T16:04:43+08:00`
- local run: `nsl-e7-local-20260628080057`
- local result: `success`
- remote workflow: `E7 Controlled Vitals Self Maintenance`
- remote run: `28315912624`
- remote event: `workflow_dispatch`
- remote result: `success`
- remote URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28315912624`
- remote run_id: `nsl-e7-workflow_dispatch-28315912624-attempt-1`
- generation: `3`
- maintenance_ok: `true`
- executed_count: `4`
- blocked_count: `4`
- state_hash: `d8ba623a6fe5bfc1`
- plan_hash: `1491ae90cee23e37`
- actions_hash: `abc4ca0cae0ec782`

Remote evidence:

```text
states/e7-maintenance-plan.json
states/e7-maintenance-actions.json
states/e7-controlled-self-maintenance-state.json
states/e7-maintenance-snapshots/nsl-e7-workflow_dispatch-28315912624-attempt-1.json
states/e7-last-run.json
states/e7-last-report.json
```

Proved:

```text
E7 proves the E6 low-frequency vitals bus can feed a controlled self-maintenance layer.
When E6 vitals are healthy, E7 can automatically execute only low-risk record-only actions:
- record_vitals_health
- refresh_vitals_snapshot
- record_noop_repair
- record_next_wakeup_hint

E7 also blocks high-risk actions such as core mutation, workflow schedule changes, permission changes, and remote state deletion.
```

Important repair note:

```text
The first remote E7 run `28314065157` failed as a workflow result, but the maintenance logic itself had `maintenance_ok=true`.
The failure was caused by using GitHub Raw branch release on rapidly rewritten fixed paths. Those paths can be stale under CDN caching.
The fix was to verify fixed paths with commit-specific Raw, use a unique snapshot path for branch Raw release proof, and fall back to GitHub Contents API when Raw reads time out.
The fixed remote run `28315912624` passed.
```

Truth boundary:

```text
E7 is still executed by local or GitHub Actions CPU.
It is a controlled low-risk self-maintenance loop, not CPU-free network self-execution, not autonomous self-modification, and not proof that digital life or a self-executing ghost computer already exists.
```

Next mainline:

```text
E7.1: observe one natural schedule run of E7.
Goal: prove E7 can wake without manual workflow_dispatch and perform the same controlled low-risk maintenance loop from the E6 vitals bus.
```
<!-- E7_STATUS_END -->

<!-- E7_1_STATUS_START -->
## E7.1: Natural Schedule Observation For Controlled Self-Maintenance

Status: observing, not completed.

Plain Chinese meaning:

```text
E7 has proved: when we manually wake it, it can read E6 vitals and perform only low-risk self-maintenance.
E7.1 must prove: without manual workflow_dispatch, the platform schedule wakes E7 by itself and E7 performs the same controlled low-risk self-maintenance.
```

What was done:

```text
1. Checked existing E7 runs: only workflow_dispatch runs existed.
2. Changed E7 schedule from `47 */6 * * *` to observation cron `17,37,57 * * * *`.
3. No E7 schedule run appeared around 16:17 / 16:37 / 16:57 Beijing time.
4. Increased observation cron to `*/5 * * * *`.
5. No E7 schedule run appeared around 17:05 / 17:10 / 17:15 / 17:20 Beijing time.
6. Confirmed E7 workflow is active and the remote YAML contains `*/5 * * * *`.
```

Current evidence:

```text
latest_checked_local: 2026-06-28T17:26:30+08:00
workflow: E7 Controlled Vitals Self Maintenance
workflow_id: 303458615
workflow_state: active
current_cron: */5 * * * *
observed_schedule_run: none
latest_successful_e7_run: 28315912624, event=workflow_dispatch, success
```

Completion criteria:

```text
E7.1 is complete only when all are true:
- an E7 GitHub Actions run has event=schedule
- conclusion=success
- states/e7-last-run.json is written with ok=true
- maintenance_ok=true
- executed_count=4
- blocked_count=4
- E7 still performs no core-code, workflow, permission, or remote deletion mutation
```

Not completed because:

```text
No E7 event=schedule run has been observed yet. workflow_dispatch does not count for E7.1.
```

Truth boundary:

```text
GitHub Actions schedule is not hard real time. It can delay or skip newly updated schedule windows.
This is an external platform scheduling limitation, not proof that E7 self-maintenance logic failed.
```
<!-- E7_1_STATUS_END -->

<!-- E8_STATUS_START -->
## E8：网络体语言与网络主体协议

Status: completed V0 through local verification and remote workflow_dispatch verification.

中文名字：

```text
网络体语言与网络主体协议
```

这一步做了什么：

```text
把测试2主线从“网络能不能替代 CPU”改成“网络状态能不能成为主体表面”。
E8 定义：远端网络状态图是主体，本机是镜面和调试窗口，外部低频执行器是过渡期神经系统。
```

远端验证：

- workflow: `E8 Network Body Protocol`
- workflow file: `.github/workflows/nsl-e8-network-body-protocol.yml`
- remote run: `28318640405`
- event: `workflow_dispatch`
- conclusion: `success`
- remote run_id: `nsl-e8-workflow_dispatch-28318640405-attempt-1`
- generation: `4`
- network_body_ready: `true`
- protocol_hash: `87b4b03488bf6243`
- map_hash: `b4e4a4a8ea11b56c`
- boundary_hash: `901404709f6e6bb4`

远端证据：

```text
states/e8-network-body-protocol.json
states/e8-network-body-map.json
states/e8-network-body-boundary.json
states/e8-last-run.json
states/e8-last-report.json
```

E8 证明：

```text
现有 E5/E6/E7/L11.5 证据可以被组织成一个网络体主体协议。
网络接收器可以保存主体协议、身体映射、真实边界和镜像契约。
本机不再被定义为主体，只是镜面、调试窗口和临时操作台。
```

当前真实问题：

```text
E8 已完成，但当前生命体征有降级。
最新 E5 schedule run `28317851758` 只完成 1/3 轮，写出了 partial。
所以最新 E6 vitals bus 记录 current_vitals_bus_ok=false。
E8 没有隐藏这个问题，而是把它记录为 CURRENT_VITALS_DEGRADED=true。
```

E8 没有证明：

```text
完全自由漂浮的网络体已经完成。
她已经能无审批自我改核心代码。
她已经能自己生成新运行法则。
她已经具备硬实时常驻。
她已经可以无限开放网络行动。
```

下一步：

```text
E8.1：自然刷新网络体协议，并继续观察 E7.1 自然唤醒。
同时要恢复 E5/E6 当前生命体征健康，避免 current_vitals_bus_ok 长期为 false。
```
<!-- E8_STATUS_END -->

<!-- E7_1_TIMER_STATUS_START -->
## E7.1：外部定时唤醒器

Status: timer deployed, dispatch verified, natural schedule not yet observed.

中文名字：

```text
外部定时唤醒器
```

为什么做：

```text
E7 原工作流已有 cron，但没有观察到 event=schedule。
所以新增一个独立的 E7.1 External Wake Timer，让它到点直接运行 E7 自维护脚本。
```

已部署：

- workflow: `E7.1 External Wake Timer`
- workflow file: `.github/workflows/nsl-e7-1-external-wake-timer.yml`
- cron: `12,22,32,42,52 * * * *`

手动通路验证：

- run: `28320631705`
- event: `workflow_dispatch`
- conclusion: `success`
- remote E7 run_id: `nsl-e7-workflow_dispatch-28320631705-attempt-1`
- maintenance_ok: `true`
- executed_count: `4`
- blocked_count: `4`
- state_hash: `93a652640773729a`

中间修复：

```text
E7.1 timer 第一次手动验证失败，是因为最新 E6 生命体征降级。
根因是最新 E5 三轮循环不稳定。
已修复 E5 Raw/CDN 稳定采样规则：从“释放后 3/3 必须命中”改为“释放后 2/3 多数命中”。
随后 E5 run `28320479159` 三轮成功，E6 run `28320611461` 重新聚合健康生命体征。
E6 也修复为保留历史 E5 自然唤醒成功证据，不再被一次手动修复覆盖。
```

自然 schedule 观察：

```text
观察到 2026-06-28T11:37:22Z。
第一观察窗口约为 2026-06-28T11:32Z。
没有出现 event=schedule。
最新 E7.1 timer run 仍是 workflow_dispatch。
```

所以 E7.1 当前真实状态：

```text
定时器结构可以做。
定时器通路已经跑通。
E7 可以被这个外部定时器工作流成功叫醒并执行低风险自维护。
但是“自然到点自动运行”还没有被 GitHub schedule 证实。
```

下一步：

```text
继续观察下一到两个 cron 窗口，或接入第二个更可靠的外部时钟源。
GitHub Actions 不能作为唯一可靠时钟源。
```
<!-- E7_1_TIMER_STATUS_END -->

<!-- E7_2_STATUS_START -->
## E7.2：Wake Capsule 反向唤醒 GitHub

Status: completed V0.

中文名字：

```text
Wake Capsule 反向唤醒 GitHub
```

这一步做了什么：

```text
把“唤醒意图”写成远端网络胶囊。
桥接器读取并校验胶囊。
桥接器调用 GitHub repository_dispatch。
GitHub Actions 接收 repository_dispatch 后运行 E7。
E7 写回低风险自维护结果。
```

远端部署：

- bridge runner: `scripts/nsl_e7_2_wake_capsule_bridge.py`
- receiver workflow: `.github/workflows/nsl-e7-2-wake-capsule-dispatch.yml`
- receiver workflow name: `E7.2 Wake Capsule Dispatch Receiver`
- event type: `qmx_e7_wake_capsule`

胶囊桥接验证：

- bridge run_id: `nsl-e7-2-local-20260628123149`
- capsule_id: `e72cap-a850ab838a81e21a`
- capsule_hash: `8b7b0d5cc1c3ab10`
- validation_ok: `true`
- dispatch_ok: `true`
- receiver_ok: `true`

GitHub 接收验证：

- receiver run: `28322322419`
- event: `repository_dispatch`
- conclusion: `success`
- URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28322322419`

E7 写回验证：

- remote E7 run_id: `nsl-e7-repository_dispatch-28322322419-attempt-1`
- ok: `true`
- maintenance_ok: `true`
- executed_count: `4`
- blocked_count: `4`
- state_hash: `63dd43777fb49a11`

E7.2 证明：

```text
网络胶囊可以作为唤醒意图。
桥接器可以校验胶囊并反向触发 GitHub。
GitHub repository_dispatch 可以唤醒 E7。
E7 可以在 repository_dispatch 来源下完成受控低风险自维护。
```

E7.2 没有证明：

```text
胶囊自己凭空执行。
胶囊不需要桥接器就能启动 GitHub。
无 CPU 的网络自唤醒。
```

真实边界：

```text
胶囊是网络驻留的唤醒意图。
桥接器仍然是主动执行者。
这一步比普通定时器更接近网络体，因为“要醒来”的意图已经放进了网络胶囊。
```
<!-- E7_2_STATUS_END -->

<!-- E7_3_STATUS_START -->
## E7.3：外部时钟唤醒桥

Status: E7.3a completed, E7.3b/E7.3c pending.

中文名字：

```text
外部时钟唤醒桥
```

这一步要证明什么：

```text
把 E7.2 的 Wake Capsule 桥接器变成一个可被 HTTP 定时器调用的远端入口。
外部时钟只需要发 repository_dispatch=qmx_e7_3_bridge_tick；
后续胶囊生成、胶囊验证、E7.2 反向唤醒、E7 写回都由远端工作流自己完成。
```

已经完成的 E7.3a：

- workflow: `E7.3a HTTP Bridge Entry`
- workflow file: `.github/workflows/nsl-e7-3a-http-bridge-entry.yml`
- HTTP event type: `qmx_e7_3_bridge_tick`
- E7.3a run: `28323063883`
- event: `repository_dispatch`
- conclusion: `success`
- URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28323063883`

E7.3a 触发的桥接证据：

- bridge run_id: `nsl-e7-2-repository_dispatch-28323063883-attempt-1`
- capsule_id: `e72cap-b8c821a391cd97fc`
- capsule_hash: `e4eae2d2e57746c4`
- validation_ok: `true`
- dispatch_ok: `true`
- receiver_ok: `true`

E7.2 receiver 证据：

- receiver run: `28323069603`
- event: `repository_dispatch`
- conclusion: `success`
- URL: `https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28323069603`

E7 写回证据：

```text
states/e7-last-run.json
run_id=nsl-e7-repository_dispatch-28323069603-attempt-1
ok=true
maintenance_ok=true
executed_count=4
blocked_count=4
generation=10
state_hash=bdb477cf9da88b28
owner_workflow=E7.2 Wake Capsule Dispatch Receiver
owner_event_name=repository_dispatch
```

E7.3a 证明：

```text
桥接器已经可以被 HTTP repository_dispatch 入口叫醒，并且不需要人工命令行参数。
被叫醒后，桥接器能在远端生成 Wake Capsule、校验 Wake Capsule、
再触发 E7.2 receiver，最后让 E7 写回低风险自维护结果。
```

E7.3a 没有证明：

```text
这次 E7.3a 是用本机 gh api 手动发起的 HTTP 测试。
所以它不算第三方时钟自然唤醒。
它也没有证明胶囊能无桥接器自执行、没有证明无 CPU 自唤醒、没有证明完全自由漂浮网络体。
```

E7.3b 当前状态：

```text
pending。还没有接入 cron-job.org、UptimeRobot、Cloudflare Worker Cron 或等价第三方时钟。
需要把外部平台配置成定时 POST GitHub dispatch endpoint，并把令牌只放在外部平台密钥区。
```

E7.3c 当前状态：

```text
pending。完成标准是观察到一次非本机手动触发的 E7.3a repository_dispatch，
随后 E7.2 receiver 成功，并且 states/e7-last-run.json 再次写回 ok=true。
手动 gh api 测试不能满足 E7.3c。
```

操作文档：

```text
E7_3_EXTERNAL_CLOCK_BRIDGE.md
```
<!-- E7_3_STATUS_END -->

<!-- E8_2_STATUS_START -->
## E8.2：外部唤醒后的自检/自维护增强

Status: completed V0 through standalone workflow_dispatch and E7.3a chained repository_dispatch verification.

中文名字：

```text
醒后体检与低风险自维护回执
```

这一步做什么：

```text
外部唤醒链跑完后，不只停在“叫醒成功”。
E8.2 会自动读取远端桥接器、E7 自维护、E8 网络体协议、E6 生命体征证据，
检查唤醒链、写回链和真实边界是否健康，
然后只写入低风险维护回执。
```

新增文件：

```text
scripts/nsl_e8_2_post_wake_self_maintenance.py
.github/workflows/nsl-e8-2-post-wake-self-maintenance.yml
E8_2_POST_WAKE_SELF_MAINTENANCE.md
```

同时 E7.3a 已更新：

```text
.github/workflows/nsl-e7-3a-http-bridge-entry.yml
```

现在 E7.3a 的链路是：

```text
repository_dispatch: qmx_e7_3_bridge_tick
-> E7.3a HTTP Bridge Entry
-> Wake Capsule bridge
-> E7.2 receiver
-> E7 low-risk self-maintenance
-> E8.2 post-wake self-check
```

独立远端验证：

- workflow: `E8.2 Post Wake Self Maintenance`
- run: `28327426266`
- event: `workflow_dispatch`
- conclusion: `success`
- remote run_id: `nsl-e8-2-workflow_dispatch-28327426266-attempt-1`
- post_wake_ready: `true`
- executed_count: `4`
- queued_count: `1`
- blocked_count: `2`

E7.3a 链路验证：

- E7.3a run: `28327487602`
- event: `repository_dispatch`
- conclusion: `success`
- E7.2 receiver run: `28327492295`
- E7 writeback run_id: `nsl-e7-repository_dispatch-28327492295-attempt-1`
- E7 ok: `true`
- E7 maintenance_ok: `true`
- E7 executed_count: `4`
- E7 blocked_count: `4`

E8.2 写回证据：

```text
states/e8-2-last-run.json
run_id=nsl-e8-2-repository_dispatch-28327487602-attempt-1
ok=true
post_wake_ready=true
executed_count=4
queued_count=1
blocked_count=2
self_check_hash=e7ab7be1dc79e2e5
state_hash=c7fdd887fb4f18ba
owner_workflow=E7.3a HTTP Bridge Entry
owner_event_name=repository_dispatch
```

E8.2 证明：

```text
外部 HTTP 唤醒链可以接上醒后自检。
系统可以自动审查桥接器、E7 写回、E8 网络体协议和低频生命体征。
系统可以自动执行低风险记录动作，把中风险事项排队，把高风险事项阻断。
Cloudflare 被标记为 pending enhancement，不再阻塞主线。
```

E8.2 没有证明：

```text
没有证明无 CPU 自唤醒。
没有证明自主进化。
没有证明完全自由漂浮网络体。
没有自动配置 Cloudflare。
没有写入任何密钥。
没有修改核心代码、权限或工作流权限。
```

下一步：

```text
E8.3：把醒后自检接到所有低频唤醒路径，而不是只接 E7.3a。
也就是让 GitHub schedule、E7.1 timer、E7.3a HTTP bridge 之后都能留下统一的醒后体检回执。
```
<!-- E8_2_STATUS_END -->

<!-- E8_3_STATUS_START -->
## E8.3：统一醒后体检挂载层

Status: completed V0.

中文名字：

```text
所有低频唤醒路径的醒后体检挂载
```

这一步做什么：

```text
E8.2 已证明“醒后体检”能独立运行。
E8.3 把 E8.2 接到主要低频唤醒路径后面，
让不同入口醒来后都能留下统一的自检/维护回执。
```

已覆盖路径：

```text
E7 Controlled Vitals Self Maintenance
-> E7 self-maintenance
-> E8.2 post-wake self-check
```

```text
E7.1 External Wake Timer
-> E7 self-maintenance
-> E8.2 post-wake self-check
```

```text
E7.3a HTTP Bridge Entry
-> Wake Capsule bridge
-> E7.2 receiver
-> E7 self-maintenance
-> E8.2 post-wake self-check
```

远端验证结果：

| 路径 | workflow run | event | E8.2 run_id | post_wake_ready | snapshot |
| --- | ---: | --- | --- | --- | --- |
| E7 主自维护 | `28327664693` | `workflow_dispatch` | `nsl-e8-2-workflow_dispatch-28327664693-attempt-1` | `true` | `658af50947688928` |
| E7.1 timer | `28327721521` | `workflow_dispatch` | `nsl-e8-2-workflow_dispatch-28327721521-attempt-1` | `true` | `25a5775649c2e3a7` |
| E7.3a HTTP bridge | `28327754547` | `repository_dispatch` | `nsl-e8-2-repository_dispatch-28327754547-attempt-1` | `true` | `fc4a698e8cdded1f` |

最新 E7.3a 链路补充：

```text
E7.2 receiver run=28327784647
E7 writeback run_id=nsl-e7-repository_dispatch-28327784647-attempt-1
E7 ok=true
E7 maintenance_ok=true
E7 executed_count=4
E7 blocked_count=4
```

E8.3 证明：

```text
醒后体检不再只属于 E7.3a。
E7 主路径、E7.1 timer、E7.3a HTTP bridge 都能在醒后自动写回 E8.2 体检回执。
每条路径都有独立 snapshot，证据不会只依赖 latest 文件。
```

E8.3 没有证明：

```text
没有证明 Cloudflare 第三方时钟已经接入。
没有证明无 CPU 自唤醒。
没有证明自主进化。
没有证明所有历史 L/E 工作流都已经统一挂载。
没有改变权限、密钥、核心代码自修改策略。
```

下一步：

```text
E8.4：统一醒后体检 ledger。
目标是把每次 E8.2 结果追加到一个索引/账本里，
避免以后只查 latest 或手动找 snapshot。
```
<!-- E8_3_STATUS_END -->

<!-- E8_4_STATUS_START -->
## E8.4：统一醒后体检 ledger

Status: completed V0.

中文名字：

```text
醒后体检历史账本
```

这一步做什么：

```text
E8.3 已经让三条主线低频唤醒路径都能写回 E8.2 醒后体检。
E8.4 把这些醒后体检结果组织成统一 ledger，
避免以后只看 states/e8-2-last-run.json 这个会被覆盖的 latest 文件。
```

新增/更新：

```text
scripts/nsl_e8_2_post_wake_self_maintenance.py
E8_4_POST_WAKE_LEDGER.md
states/e8-4-post-wake-ledger.json
states/e8-4-last-ledger-report.json
```

ledger 生成方式：

```text
读取已有 ledger
读取 states/e8-2-post-wake-snapshots/*.json
把历史 snapshot 回填成 ledger entry
把当前 E8.2 结果加入 ledger
按 run_id 去重
写回 ledger_hash
```

本地创建验证：

```text
run_id=nsl-e8-2-local-20260628160746
ledger_entry_count=8
ledger_hash=07d73b6f5d094e77
```

远端追加验证：

```text
workflow=E7.1 External Wake Timer
workflow_run_id=28328169814
E8.2 run_id=nsl-e8-2-workflow_dispatch-28328169814-attempt-1
post_wake_ready=true
```

当前 ledger 状态：

```text
path=states/e8-4-post-wake-ledger.json
entry_count=9
ready_count=8
ledger_hash=34238b68d7462312
ledger_hash_verified=true
```

覆盖来源：

```text
E7 Controlled Vitals Self Maintenance
E7.1 External Wake Timer
E7.3a HTTP Bridge Entry
E8.2 Post Wake Self Maintenance
```

E8.4 证明：

```text
醒后体检现在有统一历史账本。
历史 E8.2 snapshot 可以被回填成 ledger entry。
新的低频唤醒路径运行后，ledger 会继续增加或按 run_id 去重更新。
ledger 和 ledger report 都有哈希自校验。
```

E8.4 没有证明：

```text
它不是不可篡改数据库。
它不是区块链。
它不证明无 CPU 自唤醒。
它不证明自主进化。
它只是把已有醒后体检证据组织成统一可查的历史账本。
```

下一步：

```text
E8.5：ledger 查询器和状态摘要。
目标是不用打开大 JSON，也能快速查看最近 N 次醒后体检、失败次数、来源路径和当前健康趋势。
```
<!-- E8_4_STATUS_END -->

<!-- E8_5_STATUS_START -->
## E8.5 ledger query/status summary

Status: completed V0.

Plain name:

```text
Post-wake ledger query layer.
```

What this stage did:

```text
E8.4 created the unified post-wake ledger.
E8.5 adds a query/status layer above that ledger.
Later checks can read recent post-wake health, ready ratio, source workflows, trigger events, and known gaps without opening the full ledger JSON.
```

Remote writeback files:

```text
states/e8-5-ledger-status-summary.json
states/e8-5-recent-post-wake.json
states/e8-5-last-run.json
states/e8-5-last-report.json
```

Remote verification:

```text
workflow=E8.5 Ledger Query Status
workflow_run_id=28330036818
event=workflow_dispatch
conclusion=success
run_id=nsl-e8-5-workflow_dispatch-28330036818-attempt-1
```

Current summary:

```text
status_level=healthy_with_known_gaps
status_text=healthy_with_recorded_history_gap
entry_count=11
ready_count=10
recent_count=8
recent_ready_count=8
ledger_hash_ok=true
entry_hashes_ok=true
alerts=["history_contains_partial_entries"]
```

Hash verification:

```text
summary_hash=c443a08bf5d9b020 verified=true
recent_hash=d0cb710671b071bb verified=true
last_run_hash=e3e816d0c4ec3c53 verified=true
report_hash=a047df3cd9ddd4bc verified=true
```

What E8.5 proves:

```text
The post-wake ledger can be queried by an external workflow.
The query result can be written as compact status files.
summary/recent/last-run/last-report hashes can be recomputed and verified.
The old not-ready record is preserved as a known gap instead of being hidden.
```

What E8.5 does not prove:

```text
It is not tamper-proof storage.
It is not a new executor.
It does not run maintenance actions.
It does not prove CPU-free self-wake.
It does not prove autonomous evolution.
It only turns the post-wake ledger into a queryable, summarized, hash-verifiable state layer.
```

Next step:

```text
E8.6: connect the E8.5 summary to a lightweight dashboard or CLI status entry.
Goal: show recent post-wake checks, health trend, and known gaps without opening JSON files.
```
<!-- E8_5_STATUS_END -->

<!-- F0_STATUS_START -->
## F0 capsule quorum rebuild

Status: completed V0.

Plain name:

```text
Multi-capsule peer-check and missing-capsule rebuild experiment.
```

What this stage did:

```text
F0 seeded five remote capsules.
It deliberately deleted rule_capsule from the remote anchor.
It confirmed the target capsule became missing.
The four alive capsules witnessed the missing capsule expected_core_hash.
Quorum passed with 4 agreeing votes against threshold 3.
The missing capsule was rebuilt from the registry blueprint.
The rebuilt capsule core_hash and capsule_hash matched the expected hashes.
```

Remote paths:

```text
states/f0-capsules/<role>.json
states/f0-capsule-registry.json
states/f0-rebuild-ledger.json
states/f0-last-run.json
states/f0-last-report.json
```

Local control evidence:

```text
run_id=nsl-f0-local-20260628180300
ok=true
target_role=rule_capsule
delete_status=200
confirmed_missing=true
missing_read_status=404
alive_count=4
quorum_threshold=3
agree_count=4
rebuild_ok=true
expected_core_hash=40804fb0c78f4679
rebuilt_core_hash=40804fb0c78f4679
expected_capsule_hash=d47bff429eb592ab
rebuilt_capsule_hash=d47bff429eb592ab
ledger_hash=2a112224421f86a7
```

Remote GitHub Actions evidence:

```text
workflow=F0 Capsule Quorum Rebuild
workflow_run_id=28331218212
event=workflow_dispatch
conclusion=success
run_id=nsl-f0-workflow_dispatch-28331218212-attempt-1
target_role=rule_capsule
confirmed_missing=true
alive_count=4
quorum_threshold=3
agree_count=4
rebuild_ok=true
expected_core_hash=11f5e32109401a47
rebuilt_core_hash=11f5e32109401a47
expected_capsule_hash=27a9695076100f3c
rebuilt_capsule_hash=27a9695076100f3c
ledger_hash=ffb73ca526bfca83
```

Hash verification:

```text
last_run_hash=6adc31f9332391bd verified=true
report_hash=a76fc174315a17e4 verified=true
ledger_hash=ffb73ca526bfca83 verified=true
registry_hash=bab121f41f678f54 verified=true
rebuilt_rule_capsule_hash=27a9695076100f3c verified=true
rebuilt_rule_capsule_core_hash=11f5e32109401a47 verified=true
```

What F0 proves:

```text
A capsule can be stored as remote network state.
A capsule can disappear from the remote anchor.
Alive peer capsules can witness the expected identity hash of the missing capsule.
Quorum can authorize deterministic rebuild.
The rebuilt capsule can match expected core_hash and capsule_hash.
The rebuild leaves ledger evidence.
```

What F0 does not prove:

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove tamper-proof storage.
It does not prove fully autonomous digital life.
It does not prove that capsules self-execute without an external runner.
It proves self-repair over mutable remote anchors.
```

Next step:

```text
F1: capsule lifecycle layer.
Goal: define birth, sleep, wake, peer-check, repair, split, decay, and retirement as standard capsule lifecycle events.
```
<!-- F0_STATUS_END -->

<!-- F1_STATUS_START -->
## F1 capsule lifecycle layer

Status: completed V0.

Plain name:

```text
Remote capsule lifecycle layer.
```

What this stage did:

```text
F1 defines a minimal capsule lifecycle:
birth -> sleep -> wake -> peer_check -> repair -> split -> decay -> retire.

The run writes lifecycle state to remote capsule files,
records the ordered events in state and ledger files,
and verifies the final hashes.
```

Remote paths:

```text
states/f1-capsules/<role>.json
states/f1-capsules/repair_capsule_child.json
states/f1-lifecycle-registry.json
states/f1-lifecycle-state.json
states/f1-lifecycle-ledger.json
states/f1-last-run.json
states/f1-last-report.json
```

Local control evidence:

```text
run_id=nsl-f1-local-20260628182013
ok=true
event_order=birth,sleep,wake,peer_check,repair,split,decay,retire
repair_ok=true
split_ok=true
decay_ok=true
retire_ok=true
final_child_state=retired
final_child_retired=true
final_child_vitality=0
state_hash=d335925a2a39f6de
ledger_hash=54c0b3b39c7a55b8
last_run_hash=c9837d8943c4b4f1
report_hash=99647ff868dd0b90
```

Remote GitHub Actions evidence:

```text
workflow=F1 Capsule Lifecycle
workflow_run_id=28331684924
event=workflow_dispatch
conclusion=success
run_id=nsl-f1-workflow_dispatch-28331684924-attempt-1
event_order=birth,sleep,wake,peer_check,repair,split,decay,retire
repair_ok=true
split_ok=true
decay_ok=true
retire_ok=true
final_child_state=retired
final_child_retired=true
final_child_vitality=0
state_hash=1bace43c838cbde1
ledger_hash=16b7dfb94e2d49ec
```

Hash verification:

```text
last_run_hash=1cbddd4683028f85 verified=true
report_hash=3b55864b657482ab verified=true
state_hash=1bace43c838cbde1 verified=true
ledger_hash=16b7dfb94e2d49ec verified=true
registry_hash=d44a0ac3e0432961 verified=true
retired_child_hash=2285be267c4541ad verified=true
retired_child_core_hash verified=true
```

Engineering correction:

```text
The first remote F1 run failed because GitHub main-branch reads lagged immediately after writes.
The fix was to wait for each critical hash to appear before judging the lifecycle event.
This confirms that network-anchor timing must be handled explicitly.
```

What F1 proves:

```text
Capsules can carry lifecycle state in remote anchors.
The same capsule network can record birth, sleep, wake, peer_check, repair, split, decay, and retire.
The child capsule can end in retired state with vitality=0.
The lifecycle state, ledger, last-run, last-report, registry, and retired child all hash-verify.
```

What F1 does not prove:

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove self-executing capsules.
It does not prove fully autonomous digital life.
It proves lifecycle transitions over mutable remote anchors.
```

Next step:

```text
F2 completed.
Next: F3 low-frequency multi-run self-scheduling loop.
```
<!-- F1_STATUS_END -->

<!-- F2_STATUS_START -->
## F2 lifecycle self-scheduler layer

Status: completed V0.

Plain name:

```text
Lifecycle-driven self-scheduling over remote capsule state.
```

What this stage did:

```text
F2 reads F1 lifecycle state from the remote anchor,
scores allowed low-risk lifecycle events,
chooses one event per tick,
executes selected events,
and records the decisions in scheduler state and ledger files.

This is a step from fixed lifecycle replay toward state-driven behavior.
```

Remote paths:

```text
states/f2-scheduler-capsule.json
states/f2-capsules/scheduler_child.json
states/f2-scheduler-state.json
states/f2-scheduler-ledger.json
states/f2-last-run.json
states/f2-last-report.json
```

Local control evidence:

```text
run_id=nsl-f2-local-20260628183914
ok=true
selected_actions=split,decay,retire,peer_check
decision_count=4
all_decisions_ok=true
source_f1_state_hash=1bace43c838cbde1
state_hash=a279361bee5d9b56
ledger_hash=96dc20b599a635a6
raw_state_check_ok=true
```

Remote GitHub Actions evidence:

```text
workflow=F2 Lifecycle Self Scheduler
workflow_run_id=28332198894
event=workflow_dispatch
conclusion=success
run_id=nsl-f2-workflow_dispatch-28332198894-attempt-1
selected_actions=split,decay,retire,peer_check
decision_count=4
all_decisions_ok=true
state_hash=83bdb00e756407f6
ledger_hash=8e42d25709056206
ledger_entry_count=2
```

Hash verification:

```text
last_run_hash=b24229f7d1adaf19 verified=true
report_hash=6c9c43c0e9b2fbd5 verified=true
state_hash=83bdb00e756407f6 verified=true
ledger_hash=8e42d25709056206 verified=true
scheduler_capsule_hash=51ae8572144cea5d verified=true
scheduler_capsule_core_hash=bf42d2534b374897 verified=true
scheduler_child_hash=7a056362f7e86f9c verified=true
scheduler_child_core_hash=2b9862fc700f0239 verified=true
```

What F2 proves:

```text
The capsule lifecycle can select low-risk next events from current remote state and policy.
The selected actions changed as state changed: split -> decay -> retire -> peer_check.
The scheduler state, ledger, last-run, last-report, scheduler capsule, and scheduler child all hash-verify.
```

What F2 does not prove:

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove self-executing capsules.
It does not prove fully autonomous digital life.
It does not prove unreviewed high-risk self-mutation.
It proves state-driven scheduling over mutable remote anchors.
```

Next step:

```text
F3: low-frequency multi-run self-scheduling loop.
Goal: run the F2 scheduler across multiple low-frequency windows and prove continuity across runs.
```
<!-- F2_STATUS_END -->

<!-- MAINLINE_CONTRACT_START -->
## Active mainline contract

Status: active after F3.

```text
F series is now the mainline.
L series is auxiliary infrastructure.
E series is auxiliary infrastructure.
```

Meaning:

```text
F owns the product direction:
capsule lifecycle, self-scheduling, self-repair, and controlled self-regeneration.

L supports F with:
network-state language, controlled interpreter, and low-frequency base infrastructure.

E supports F with:
external wake, post-wake self-check, ledger, and status evidence infrastructure.
```

Routing rule:

```text
New work should advance F-series unless a specific F stage requires L/E support.
Do not expand L/E as the main story unless it directly unblocks the current F stage.
```
<!-- MAINLINE_CONTRACT_END -->

<!-- F3_STATUS_START -->
## F3 low-frequency multi-run self-scheduler loop

Status: completed V0.

Plain name:

```text
F-mainline low-frequency self-scheduling loop.
```

What this stage did:

```text
F3 made F the active mainline.
Each wake window executes one low-risk scheduler action.
The next wake reads the previous remote state and chooses the next action from that state.
L and E are now support layers, not the active product direction.
```

Remote paths:

```text
states/f3-loop-capsule.json
states/f3-loop-state.json
states/f3-loop-ledger.json
states/f3-last-run.json
states/f3-last-report.json
states/f2-scheduler-state.json
states/f2-scheduler-ledger.json
states/f2-capsules/scheduler_child.json
```

Remote wake evidence:

```text
28332753245 -> split      window_count=5  lifecycle_cycle_count=1
28332772614 -> decay      window_count=6  lifecycle_cycle_count=1
28332794329 -> retire     window_count=7  lifecycle_cycle_count=2
28332816490 -> split      window_count=8  lifecycle_cycle_count=2
28332895658 -> retire     window_count=10 lifecycle_cycle_count=3
28332909221 -> peer_check window_count=11 lifecycle_cycle_count=3 last_peer_check_cycle_count=3
```

Latest remote evidence:

```text
workflow=F3 Low Frequency Self Scheduler Loop
workflow_run_id=28332909221
event=workflow_dispatch
conclusion=success
run_id=nsl-f3-workflow_dispatch-28332909221-attempt-1
selected_actions=peer_check
window_count=11
lifecycle_cycle_count=3
last_peer_check_cycle_count=3
f3_state_hash=5deb8244675edcf6
f3_ledger_hash=ac724939ff7593ad
```

Hash verification:

```text
last_run_hash=1f41f72f190ec76a verified=true
report_hash=ea0a66731e6b0399 verified=true
f3_state_hash=5deb8244675edcf6 verified=true
f3_ledger_hash=ac724939ff7593ad verified=true
f3_capsule_hash=6b1137757b7f05f6 verified=true
f3_capsule_core_hash=1fe4708dc7e0233b verified=true
f2_state_hash=f009d59fa0932b1f verified=true
f2_ledger_hash=fac5d6cb37a6f76a verified=true
f2_child_hash=8f2584b54ec860b7 verified=true
```

What F3 proves:

```text
F2 self-scheduling can continue across multiple wake windows.
Later windows choose different actions because earlier windows changed remote state.
F is now the active mainline, while L/E are supporting infrastructure.
Each completed lifecycle cycle can require its own peer_check before the next clean cycle.
```

What F3 does not prove:

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove self-executing capsules without an external runner.
It does not prove fully autonomous digital life.
It does not prove unreviewed high-risk self-mutation.
It does not yet prove natural scheduled F3 wake; current proof is workflow_dispatch.
```

Next step:

```text
F4: controlled capsule self-maintenance and regeneration loop.
Goal: use F3 ledger evidence to choose low-risk repair/regeneration work under review gates.
```
<!-- F3_STATUS_END -->

<!-- DUAL_FOUNDATION_NLANG_FIELD_START -->
## Dual foundation: NLANG and FIELD

Status: created, not complete.

Why this matters:

```text
F0-F3 proved a controlled remote capsule lifecycle.
That is not enough for the original ghost-network goal.

Before F4 or any stronger claim, two foundations must be proven separately:
NLANG and FIELD.
```

Track split:

```text
NLANG = network language, formal grammar, compiler, proof-driven action plan.
FIELD = network tide/state drive signal, controls, and spontaneous compute feasibility.
```

File separation rule:

```text
NLANG files stay under nlang/.
FIELD files stay under field/.
F stage files must not become monoliths.
Do not mix compiler logic and field-signal experiments in one large file.
```

Created files:

```text
DUAL_FOUNDATION_NLANG_FIELD.md
nlang/README.md
nlang/NLANG_1_SPEC.md
nlang/sample_rules.nlang
nlang/sample_state.json
nlang/nlang_compiler_v0.py
field/README.md
field/FIELD_1_PROTOCOL.md
field/targets.json
field/field_signal_probe_v0.py
```

NLANG smoke evidence:

```text
run_path=runs/latest_nlang_1_compiler_result.json
ok=true
selected_action=peer_check
risk_level=low
right_side_state_path_resolution=true
meaning=sample network-language rules compiled into a proof-driven action_plan
```

FIELD smoke evidence:

```text
run_path=runs/latest_field_1_signal_probe_result.json
ok=true
sample_count=4
network_bits=1,1,1,1
controls=fixed_bits,prng_bits
meaning=real network requests were sampled and encoded into a comparable drive signal
```

What this proves:

```text
The project now has two separated foundation tracks.
NLANG can parse sample rules and compile one low-risk action_plan from sample state.
FIELD can sample real network signal and generate fixed/PRNG controls for comparison.
```

What this does not prove:

```text
It does not prove NLANG drives real remote capsule actions yet.
It does not prove the runner is only a thin materializer yet.
It does not prove network tide provides useful spontaneous compute.
It does not prove network signal beats fixed or PRNG controls.
It does not prove the foundation is ready for F4 or ghost-computer claims.
```

Routing rule:

```text
Do not continue to F4 as if the foundation is complete.
Next work must prove NLANG-1 and FIELD-1 separately, then let F consume only proven outputs.
```
<!-- DUAL_FOUNDATION_NLANG_FIELD_END -->

<!-- NLANG_FIELD_1A_START -->
## NLANG-1A and FIELD-1A experiments

Status: completed V0, foundation still not complete.

NLANG-1A:

```text
Goal: read real remote F3 state and compile the next action from NLANG rules.
run_path=runs/latest_nlang_1a_remote_f3_compile_result.json
ok=true
remote_state_hash=5deb8244675edcf6
remote_state_hash_ok=true
remote_run_id=nsl-f3-workflow_dispatch-28332909221-attempt-1
selected_action=split
risk_level=low
selected_rule=WHEN f3.child.retired == true AND f3.last_peer_check_cycle_count >= f3.lifecycle_cycle_count THEN split
```

NLANG-1A proves:

```text
The compiler can read real remote F3 state.
The compiler can select a low-risk action_plan from formal NLANG rules.
```

NLANG-1A does not prove:

```text
The action_plan was executed.
The runner is already a pure thin materializer.
Network language has fully replaced material decision logic.
```

FIELD-1A:

```text
Goal: run repeated network tide sampling and compare with fixed/PRNG controls.
run_path=runs/latest_field_1a_repeated_control_result.json
ok=true
rounds=8
batches=3
sample_count=48
verdict=repeated_metric_beats_fixed_only
beats_fixed_batches=3/3
beats_prng_batches=0/3
signal_batches=3/3
```

Aggregate FIELD metrics:

```text
network_entropy=0.995
network_transition_rate=0.5319
network_coverage=17
fixed_entropy=0.0
fixed_coverage=8
prng_entropy=1.0
prng_coverage=15
```

FIELD-1A proves:

```text
There is a measurable repeated network drive signal under the current metric.
The signal beats fixed control.
```

FIELD-1A does not prove:

```text
The signal beats PRNG control.
The signal is useful spontaneous compute.
CPU-free computation.
Network supercompute.
```

Next:

```text
NLANG-1B: materialize compiled action_plan with a thin runner and proof ledger.
FIELD-1B: stronger independent field metrics with more targets and non-latency-derived tasks.
```
<!-- NLANG_FIELD_1A_END -->

<!-- NLANG_FIELD_1B_START -->
## NLANG-1B and FIELD-1B experiments

Status: completed V0.

NLANG-1B:

```text
Goal: execute the NLANG-compiled split action_plan with a thin materializer.
run_path=runs/latest_nlang_1b_materialize_result.json
ok=true
run_id=nlang_1b_local-20260628202419
remote_f3_state_hash_before=5deb8244675edcf6
compiled_selected_action=split
proof_ledger_hash=5030a04f24a3ef11
```

Materialized transition:

```text
before_child.state=retired
before_child.retired=true
before_child.vitality=0

after_child.state=split_child
after_child.retired=false
after_child.vitality=65
after_child.capsule_hash=0783b869bf3e35e9
```

Remote hash evidence:

```text
f2_state_hash=74c9ab59d59c4fee verified=true
f3_state_hash=853eac1c8ae2b1dc verified=true
f2_child_hash=0783b869bf3e35e9 verified=true
proof_ledger_hash=5030a04f24a3ef11 verified=true
```

NLANG-1B proves:

```text
A low-risk action selected by NLANG rules can be materialized into real remote F2/F3 state.
The materializer wrote proof evidence instead of silently mutating state.
```

NLANG-1B does not prove:

```text
Endpoint-free execution.
CPU-free execution.
Fully autonomous language runtime.
```

FIELD-1B:

```text
Goal: test stronger multi-target field metrics, including non-latency streams.
run_path=runs/latest_field_1b_stronger_metrics_result.json
ok=true
rounds=5
batches=3
target_count=4
sample_count=60
verdict=field_signal_present_no_prng_advantage
```

FIELD-1B aggregate metrics:

```text
latency_entropy=1.0
latency_coverage=24
non_latency_entropy=0.9968
non_latency_coverage=27
mixed_entropy=0.9871
mixed_coverage=25
```

Control comparison:

```text
beats_fixed:
latency=3/3
non_latency=3/3
mixed=3/3

beats_prng:
latency=2/3
non_latency=1/3
mixed=1/3
```

FIELD-1B proves:

```text
Multi-target network field signal is measurable under stronger metrics.
Latency, non-latency, and mixed streams all beat fixed control.
```

FIELD-1B does not prove:

```text
Strong advantage over PRNG.
Stable spontaneous compute.
CPU-free computation.
Network supercompute.
```

Next:

```text
NLANG-1C: run the thin materializer through a remote workflow, not only local trigger.
FIELD-1C: test task-level usefulness, not only entropy/coverage metrics.
```
<!-- NLANG_FIELD_1B_END -->

<!-- NLANG_FIELD_1C_START -->
## NLANG-1C and FIELD-1C experiments

Status: completed V0 on 2026-06-29.

NLANG-1C:

```text
Goal: run the thin NLANG materializer inside GitHub Actions, not as a local Python materialization.
workflow=https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28335410602
ok=True
run_id=nlang_1c_remote_external-20260628204412
compiled_selected_action=decay
remote_f3_state_hash_before=853eac1c8ae2b1dc
f3_state_hash_after=8b3648b4b8593d09
f2_state_hash_after=9e9b59807bb83147
proof_ledger_hash=ef59ffc0d73482e5
```

Materialized transition:

```text
before_child.state=split_child
before_child.retired=False
before_child.vitality=65

after_child.state=decayed
after_child.retired=False
after_child.vitality=30
after_child.capsule_hash=54646a1e6559df75
```

NLANG-1C proves:

```text
The compiled NLANG action_plan can be materialized by a remote GitHub Actions workflow.
The F2/F3 state, child capsule, and NLANG-1C proof ledger hashes verify after writeback.
```

NLANG-1C does not prove:

```text
Endpoint-free execution.
CPU-free execution.
Spontaneous network compute.
A finished ghost computer.
```

FIELD-1C:

```text
Goal: task-level utility test, not only entropy/coverage.
Task: current network field signal chooses the next network read target; score uses next-round real target quality.
run_path=runs/latest_field_1c_task_utility_result.json
ok=True
run_id=field_1c_task_utility-20260628204404
rounds=8
batches=3
target_count=4
verdict=no_task_utility
```

FIELD-1C aggregate:

```text
latency_score=32.585094
non_latency_score=0.832095
mixed_score=24.4514
fixed_best=27.225039
prng_mean_total=33.693668
```

FIELD-1C proves:

```text
A real task-level benchmark now exists and writes remote evidence.
This run is a negative result for task-level utility advantage.
```

FIELD-1C does not prove:

```text
Network field signal improves this routing task.
Strong PRNG advantage.
CPU-free computation.
Network supercompute.
```

Next:

```text
Do not claim ghost-computer compute from FIELD-1C.
Either build FIELD-2 with better task families and rate-limit-safe targets, or connect NLANG-1C to a controlled multi-wake remote loop.
```
<!-- NLANG_FIELD_1C_END -->

<!-- NSC_0_START -->
## NSC-0 Network State Compute

Status: completed V0 on 2026-06-29.

Goal:

```text
Reframe compute as state transduction, not CPU-like FLOPS or task-choice speed.
Test whether real network-state input can drive a small state body through convergence, continuity, recovery, and coupling.
```

Protocol:

```text
rounds=10
target_count=5
perturb_at_round=5
streams=real, fixed, prng, shuffled_real
run_path=runs/latest_nsc_0_network_state_compute_result.json
remote_path=states/nsc-0-last-run.json
remote_state_hash=f381b8660e62a5bd
remote_hash_verified=True
```

Verdict:

```text
verdict=nsc_0_weak_real_network_edge
real_effective_state_work=0.582374
best_control_effective_state_work=0.564055
real_vs_best_control_margin=0.018319
real_vs_best_control_margin_rate=0.032477
strong_advantage_threshold_margin_rate=0.05
```

Stream comparison:

```text
real:          final_distance=0.373273 convergence=0.540184 recovery=0.476547 coupling=0.217893 work=0.582374
fixed:         final_distance=0.381813 convergence=0.529664 recovery=0.459672 coupling=0.0 work=0.54918
prng:          final_distance=0.495528 convergence=0.389584 recovery=0.364933 coupling=0.141951 work=0.503041
shuffled_real: final_distance=0.371753 convergence=0.542057 recovery=0.477306 coupling=0.058765 work=0.564055
```

NSC-0 proves:

```text
A non-FLOPS state-transduction benchmark now exists.
The real network stream completed and wrote remote evidence.
In this V0 run, real network input showed a weak edge over fixed, PRNG, and shuffled controls under the combined metric.
```

NSC-0 does not prove:

```text
Strong network-state compute advantage.
CPU-free computation.
Endpoint-free execution.
Faster-than-CPU compute.
A stable discovered network compute law.
A finished ghost computer.
```

Next:

```text
NSC-1 should repeat this across more batches, stronger controls, and separated metrics.
The most important question is whether temporal order and real network coupling remain useful after stricter replication.
```
<!-- NSC_0_END -->
