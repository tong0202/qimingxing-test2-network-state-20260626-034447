# 测试2项目日志

## 2026-06-28 E8 网络体主体协议

本次主线校准：

```text
不再把核心问题写成“网络能不能替代 CPU”。
改为：“网络状态能不能成为主体表面，本机能不能退成镜面和调试窗口。”
```

完成内容：

- 新增本地执行器：`nsl_e8_network_body_protocol.py`
- 新增远端工作流：`nsl-e8-network-body-protocol.yml`
- 新增说明文档：`E8_NETWORK_BODY_PROTOCOL.md`
- 远端部署：
  - `scripts/nsl_e8_network_body_protocol.py`
  - `.github/workflows/nsl-e8-network-body-protocol.yml`
- 远端验证成功：
  - run: `28318640405`
  - event: `workflow_dispatch`
  - conclusion: `success`
  - remote run_id: `nsl-e8-workflow_dispatch-28318640405-attempt-1`

远端证据：

```text
states/e8-network-body-protocol.json
states/e8-network-body-map.json
states/e8-network-body-boundary.json
states/e8-last-run.json
states/e8-last-report.json
```

关键结果：

```text
network_body_ready=true
protocol_hash=87b4b03488bf6243
map_hash=b4e4a4a8ea11b56c
boundary_hash=901404709f6e6bb4
```

真实边界：

```text
E8 证明的是网络体主体协议可以被写入、校验和远端刷新。
E8 没有证明完全自由漂浮网络体、无审批自我改写、硬实时常驻、无限开放网络行动。
```

当前已知问题：

```text
最新 E5 schedule run 28317851758 只完成 1/3 轮，导致最新 E6 vitals bus 降级。
E8 已把 CURRENT_VITALS_DEGRADED=true 记录进协议状态。
下一步需要恢复当前 E5/E6 生命体征，同时观察 E8.1/E7.1 自然唤醒。
```

## 2026-06-28 E7.1 外部定时唤醒器

用户问题：

```text
做一个定时器到点自动运行不行吗？
```

处理结果：

- 新增工作流：`nsl-e7-1-external-wake-timer.yml`
- 远端路径：`.github/workflows/nsl-e7-1-external-wake-timer.yml`
- cron：`12,22,32,42,52 * * * *`
- 手动验证 run：`28320631705`
- 结果：`success`

远端 E7 写回：

```text
states/e7-last-run.json
run_id=nsl-e7-workflow_dispatch-28320631705-attempt-1
ok=true
maintenance_ok=true
executed_count=4
blocked_count=4
state_hash=93a652640773729a
```

修复记录：

```text
第一次 E7.1 timer 验证失败，因为 E6 当前生命体征不健康。
E5 最新 schedule/dispatch 在三轮循环上不稳定。
已修复 E5 Raw/CDN 稳定采样：释放后 3 次采样至少 2 次命中即可视为稳定。
E5 run 28320479159 恢复三轮成功。
E6 run 28320611461 恢复 bus_ok=true，并保留历史 E5 schedule 成功证据。
```

真实边界：

```text
E7.1 timer 已经证明“外部定时器通路可运行”。
但截至 2026-06-28T11:37:22Z，没有观察到 event=schedule。
所以还不能说自然到点自动运行已经完成。
```

## 2026-06-28 E7.2 Wake Capsule 反向唤醒 GitHub

用户想法：

```text
写一个胶囊程序反向启动 GitHub。
```

落地结构：

```text
states/e7-2-wake-capsule.json
-> nsl_e7_2_wake_capsule_bridge.py 校验胶囊
-> GitHub repository_dispatch
-> E7.2 Wake Capsule Dispatch Receiver
-> E7 自维护脚本
-> states/e7-last-run.json 写回
```

完成结果：

- bridge run_id: `nsl-e7-2-local-20260628123149`
- capsule_id: `e72cap-a850ab838a81e21a`
- capsule_hash: `8b7b0d5cc1c3ab10`
- validation_ok: `true`
- dispatch_ok: `true`
- receiver_ok: `true`
- receiver run: `28322322419`
- receiver event: `repository_dispatch`
- receiver conclusion: `success`

E7 写回：

```text
run_id=nsl-e7-repository_dispatch-28322322419-attempt-1
ok=true
maintenance_ok=true
executed_count=4
blocked_count=4
state_hash=63dd43777fb49a11
```

真实边界：

```text
胶囊不是自执行进程。
胶囊不能凭空启动 GitHub。
胶囊是网络中的唤醒意图。
桥接器仍然是主动执行者。
```

## 2026-06-28 E7.3 外部时钟唤醒桥

用户要求：
```text
E7.3a：把 bridge 改成无人工参数、可被 HTTP/定时器调用
E7.3b：接一个外部时钟源，比如 cron-job.org / UptimeRobot / Cloudflare Worker Cron
E7.3c：观察一次非手动触发，确认 e7-last-run.json 出现 repository_dispatch 写回
```

已完成 E7.3a：
- 新增工作流：`nsl-e7-3a-http-bridge-entry.yml`
- 远端路径：`.github/workflows/nsl-e7-3a-http-bridge-entry.yml`
- 触发事件：`repository_dispatch` / `qmx_e7_3_bridge_tick`
- 说明文档：`E7_3_EXTERNAL_CLOCK_BRIDGE.md`
- E7.3a run：`28323063883`
- E7.3a result：`success`

链路证据：
```text
qmx_e7_3_bridge_tick
-> E7.3a HTTP Bridge Entry
-> nsl_e7_2_wake_capsule_bridge.py
-> Wake Capsule
-> qmx_e7_wake_capsule
-> E7.2 Wake Capsule Dispatch Receiver
-> E7 self-maintenance
-> states/e7-last-run.json
```

桥接器写回：
```text
states/e7-2-last-run.json
run_id=nsl-e7-2-repository_dispatch-28323063883-attempt-1
ok=true
capsule_id=e72cap-b8c821a391cd97fc
capsule_hash=e4eae2d2e57746c4
validation_ok=true
dispatch_ok=true
receiver_ok=true
receiver_workflow_run_id=28323069603
```

E7 写回：
```text
states/e7-last-run.json
run_id=nsl-e7-repository_dispatch-28323069603-attempt-1
ok=true
maintenance_ok=true
executed_count=4
blocked_count=4
state_hash=bdb477cf9da88b28
```

真实边界：
```text
E7.3a 这次是手动 HTTP repository_dispatch 测试，只证明 HTTP 入口和无参数桥接器可运行。
E7.3b 还没有接第三方时钟。
E7.3c 还没有观察到非手动第三方触发。
不能把这一步说成完全自动常驻，也不能说成无 CPU 自唤醒。
```

## 2026-06-28 E7.3b Cloudflare Worker Cron 模板

已准备本地模板：
```text
cloudflare/e7_3_clock_worker/worker.js
cloudflare/e7_3_clock_worker/wrangler.toml
cloudflare/e7_3_clock_worker/README.md
```

用途：
```text
Cloudflare Cron 到点运行 Worker。
Worker 调用 GitHub repository_dispatch: qmx_e7_3_bridge_tick。
GitHub 进入 E7.3a HTTP Bridge Entry。
```

安全要求：
```text
GitHub token 只能放 Cloudflare Secret：GITHUB_TOKEN。
不能写进仓库、文档、日志或聊天。
```

当前真实状态：
```text
模板已写好，worker.js 已通过 node --check。
还没有部署到 Cloudflare。
还没有观察到 Cloudflare 非手动定时触发。
所以 E7.3b/E7.3c 仍然 pending。
```

## 2026-06-28 E8.2 外部唤醒后的自检/自维护增强

用户决定：
```text
暂时跳过 Cloudflare，继续做 E8：外部唤醒后的自检/自维护能力增强。
```

落地内容：
```text
新增 nsl_e8_2_post_wake_self_maintenance.py
新增 nsl-e8-2-post-wake-self-maintenance.yml
新增 E8_2_POST_WAKE_SELF_MAINTENANCE.md
修改 nsl-e7-3a-http-bridge-entry.yml，让 E7.3a bridge 后自动运行 E8.2
```

独立验证：
```text
workflow=E8.2 Post Wake Self Maintenance
run=28327426266
event=workflow_dispatch
conclusion=success
post_wake_ready=true
executed_count=4
queued_count=1
blocked_count=2
```

E7.3a 链路验证：
```text
E7.3a run=28327487602
event=repository_dispatch
conclusion=success
E7.2 receiver run=28327492295
E7 writeback=nsl-e7-repository_dispatch-28327492295-attempt-1
E8.2 writeback=nsl-e8-2-repository_dispatch-28327487602-attempt-1
```

远端写回：
```text
states/e8-2-last-run.json
ok=true
post_wake_ready=true
generation=4
self_check_hash=e7ab7be1dc79e2e5
state_hash=c7fdd887fb4f18ba
```

真实含义：
```text
这一步证明外部唤醒之后可以自动进入醒后体检和低风险维护回执。
它把“叫醒成功”推进到“叫醒后能检查自己、记录状态、排队中风险、阻断高风险”。
```

真实边界：
```text
E8.2 仍然由 GitHub Actions CPU 执行。
它不证明无 CPU 自唤醒、自主进化、完全自由漂浮网络体或无限开放行动。
Cloudflare 第三方时钟仍然是后续增强项，不是当前主线阻塞项。
```

## 2026-06-28 E8.3 统一醒后体检挂载层

目标：
```text
把 E8.2 醒后体检接到所有当前主线低频唤醒路径。
```

修改内容：
```text
nsl-e7-vitals-self-maintenance.yml：E7 后追加 E8.2 step
nsl-e7-1-external-wake-timer.yml：E7.1 timer 后追加 E8.2 step
nsl-e7-3a-http-bridge-entry.yml：之前已接 E8.2，继续作为第三条路径验证
新增 E8_3_UNIFIED_POST_WAKE_HOOKS.md
```

验证 1：E7 主自维护路径
```text
workflow=E7 Controlled Vitals Self Maintenance
run=28327664693
event=workflow_dispatch
conclusion=success
E8.2 run_id=nsl-e8-2-workflow_dispatch-28327664693-attempt-1
post_wake_ready=true
snapshot_hash=658af50947688928
```

验证 2：E7.1 timer 路径
```text
workflow=E7.1 External Wake Timer
run=28327721521
event=workflow_dispatch
conclusion=success
E8.2 run_id=nsl-e8-2-workflow_dispatch-28327721521-attempt-1
post_wake_ready=true
snapshot_hash=25a5775649c2e3a7
```

验证 3：E7.3a HTTP bridge 路径
```text
workflow=E7.3a HTTP Bridge Entry
run=28327754547
event=repository_dispatch
conclusion=success
E7.2 receiver run=28327784647
E8.2 run_id=nsl-e8-2-repository_dispatch-28327754547-attempt-1
post_wake_ready=true
snapshot_hash=fc4a698e8cdded1f
```

真实含义：
```text
当前主线低频唤醒路径醒来后，已经都能自动留下 E8.2 醒后体检回执。
这把“能醒”推进到“醒后能审查自己并记录维护状态”。
```

真实边界：
```text
E8.3 只覆盖当前主线三条低频路径。
它没有证明 Cloudflare 第三方时钟、无 CPU 自唤醒、自主进化或所有历史 L/E 工作流统一挂载。
```

## 2026-06-29 E8.4 统一醒后体检 ledger

目标：
```text
把 E8.2 醒后体检从 latest/snapshot 升级为统一历史账本。
```

落地内容：
```text
修改 nsl_e8_2_post_wake_self_maintenance.py
新增 E8_4_POST_WAKE_LEDGER.md
新增远端 states/e8-4-post-wake-ledger.json
新增远端 states/e8-4-last-ledger-report.json
```

ledger 逻辑：
```text
读取已有 ledger
扫描 states/e8-2-post-wake-snapshots/*.json
回填历史 snapshot
加入当前 E8.2 结果
按 run_id 去重
写回 ledger_hash
```

本地创建验证：
```text
run_id=nsl-e8-2-local-20260628160746
ok=true
ledger_entry_count=8
ledger_hash=07d73b6f5d094e77
```

远端追加验证：
```text
workflow=E7.1 External Wake Timer
run=28328169814
event=workflow_dispatch
conclusion=success
E8.2 run_id=nsl-e8-2-workflow_dispatch-28328169814-attempt-1
post_wake_ready=true
```

当前 ledger：
```text
entry_count=9
ready_count=8
covered_workflows=E7 / E7.1 / E7.3a / E8.2
covered_events=repository_dispatch / workflow_dispatch
latest_entry=nsl-e8-2-workflow_dispatch-28328169814-attempt-1
ledger_hash=34238b68d7462312
ledger_hash_verified=true
report_hash=417ec672bf93a8ca
```

真实含义：
```text
现在每次醒后体检不只覆盖 latest 文件，还会进入统一历史账本。
后续可以按 ledger 查询最近 N 次醒后状态、来源路径和健康趋势。
```

真实边界：
```text
E8.4 是可审计状态账本，不是不可篡改数据库，也不是区块链。
它不证明无 CPU 自唤醒、自主进化或完全自由漂浮网络体。
```

## 2026-06-29 E8.5 ledger query/status summary

Goal:
```text
Turn the E8.4 post-wake ledger into compact queryable status files.
Avoid judging the system by manually opening the full ledger JSON every time.
```

Implemented:
```text
script=scripts/nsl_e8_5_ledger_query_status.py
workflow=.github/workflows/nsl-e8-5-ledger-query-status.yml
doc=E8_5_LEDGER_QUERY_STATUS.md
summary=states/e8-5-ledger-status-summary.json
recent=states/e8-5-recent-post-wake.json
last_run=states/e8-5-last-run.json
last_report=states/e8-5-last-report.json
```

Remote evidence:
```text
workflow=E8.5 Ledger Query Status
run=28330036818
event=workflow_dispatch
conclusion=success
run_id=nsl-e8-5-workflow_dispatch-28330036818-attempt-1
```

Status summary:
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

Truth meaning:
```text
Post-wake history can now be queried and summarized by an external workflow.
The system keeps the old not-ready history as a known gap instead of hiding it.
```

Truth boundary:
```text
E8.5 is not a tamper-proof database.
E8.5 is not a new executor.
E8.5 does not perform self-maintenance actions.
E8.5 does not prove CPU-free self-wake, autonomous evolution, or fully floating network life.
It only turns the post-wake ledger into a queryable, summarized, hash-verifiable state layer.
```

## 2026-06-29 F0 capsule quorum rebuild

Goal:
```text
Test whether a remote capsule network can survive the loss of one capsule file.
```

Implemented:
```text
script=scripts/nsl_f0_capsule_quorum_rebuild.py
workflow=.github/workflows/nsl-f0-capsule-quorum-rebuild.yml
doc=F0_CAPSULE_QUORUM_REBUILD.md
capsules=states/f0-capsules/<role>.json
registry=states/f0-capsule-registry.json
ledger=states/f0-rebuild-ledger.json
last_run=states/f0-last-run.json
last_report=states/f0-last-report.json
```

Local control run:
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

Remote GitHub Actions run:
```text
workflow=F0 Capsule Quorum Rebuild
run=28331218212
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

Truth meaning:
```text
F0 moves the project from single remote state toward self-repairing capsule anchors.
The subject is no longer only one file: it can be represented by a capsule set whose members witness and rebuild a missing member.
```

Truth boundary:
```text
F0 is still remote-anchor self-repair.
It is not endpoint-free existence.
It is not CPU-free computation.
It is not tamper-proof storage.
It is not autonomous digital life.
```

## 2026-06-29 F1 capsule lifecycle layer

Goal:
```text
Turn the F0 rebuild proof into a capsule lifecycle layer.
```

Implemented:
```text
script=scripts/nsl_f1_capsule_lifecycle.py
workflow=.github/workflows/nsl-f1-capsule-lifecycle.yml
doc=F1_CAPSULE_LIFECYCLE.md
capsules=states/f1-capsules/<role>.json
child=states/f1-capsules/repair_capsule_child.json
registry=states/f1-lifecycle-registry.json
state=states/f1-lifecycle-state.json
ledger=states/f1-lifecycle-ledger.json
last_run=states/f1-last-run.json
last_report=states/f1-last-report.json
```

Lifecycle events:
```text
birth
sleep
wake
peer_check
repair
split
decay
retire
```

Local control run:
```text
run_id=nsl-f1-local-20260628182013
ok=true
repair_ok=true
split_ok=true
decay_ok=true
retire_ok=true
final_child_state=retired
final_child_retired=true
final_child_vitality=0
state_hash=d335925a2a39f6de
ledger_hash=54c0b3b39c7a55b8
```

Remote GitHub Actions run:
```text
workflow=F1 Capsule Lifecycle
run=28331684924
event=workflow_dispatch
conclusion=success
run_id=nsl-f1-workflow_dispatch-28331684924-attempt-1
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
```

Engineering correction:
```text
The first remote F1 run failed because GitHub main-branch reads lagged immediately after writes.
The script was fixed to wait for each critical hash before judging an event.
```

Truth meaning:
```text
F1 upgrades capsules from rebuildable remote files into lifecycle-bearing remote state units.
The capsule set can now record birth, sleep, wake, peer-check, repair, split, decay, and retire.
```

Truth boundary:
```text
F1 is still lifecycle over mutable remote anchors.
It is not endpoint-free existence.
It is not CPU-free computation.
It is not self-executing capsules.
It is not autonomous digital life.
```

## F2 lifecycle-driven self-scheduler

Status: completed V0.

Purpose:
```text
Move from fixed lifecycle replay to state-driven low-risk scheduling.
F2 reads the current F1 lifecycle state, scores candidate lifecycle events,
selects one event per tick, executes it, and records decision evidence.
```

Local control run:
```text
run_id=nsl-f2-local-20260628183914
ok=true
selected_actions=split,decay,retire,peer_check
decision_count=4
state_hash=a279361bee5d9b56
ledger_hash=96dc20b599a635a6
raw_state_check_ok=true
```

Remote GitHub Actions run:
```text
workflow=F2 Lifecycle Self Scheduler
run=28332198894
event=workflow_dispatch
conclusion=success
run_id=nsl-f2-workflow_dispatch-28332198894-attempt-1
selected_actions=split,decay,retire,peer_check
decision_count=4
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
scheduler_child_hash=7a056362f7e86f9c verified=true
```

Truth meaning:
```text
F2 proves the remote capsule layer can choose next low-risk lifecycle events from state.
The run did not simply replay F1. It selected split, then decay, then retire, then peer_check
because the scheduler state changed after each tick.
```

Truth boundary:
```text
F2 is still scheduling over mutable remote anchors with an external runner.
It is not endpoint-free existence.
It is not CPU-free computation.
It is not self-executing capsules.
It is not autonomous digital life.
```

## F3 low-frequency multi-run self-scheduler loop

Status: completed V0.

Mainline decision:
```text
F series is now the mainline.
L series is auxiliary infrastructure.
E series is auxiliary infrastructure.
```

Purpose:
```text
F3 proves that F2 self-scheduling can continue across wake windows.
Each wake runs one low-risk lifecycle action, writes state, and leaves the next wake
to choose from the new remote state.
```

Remote wake sequence:
```text
28332753245 -> split      window_count=5  lifecycle_cycle_count=1
28332772614 -> decay      window_count=6  lifecycle_cycle_count=1
28332794329 -> retire     window_count=7  lifecycle_cycle_count=2
28332816490 -> split      window_count=8  lifecycle_cycle_count=2
28332895658 -> retire     window_count=10 lifecycle_cycle_count=3
28332909221 -> peer_check window_count=11 lifecycle_cycle_count=3 last_peer_check_cycle_count=3
```

Latest remote run:
```text
workflow=F3 Low Frequency Self Scheduler Loop
run=28332909221
event=workflow_dispatch
conclusion=success
run_id=nsl-f3-workflow_dispatch-28332909221-attempt-1
selected_actions=peer_check
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
f2_state_hash=f009d59fa0932b1f verified=true
f2_ledger_hash=fac5d6cb37a6f76a verified=true
```

Engineering correction:
```text
Initial remote continuity was valid, but peer_check was tied only to F1 hash change.
F3 was tightened with last_peer_check_cycle_count, so each completed lifecycle cycle
can require its own peer_check before cleanly opening the next cycle.
The correction was verified by remote retire -> peer_check.
```

Truth meaning:
```text
F3 turns the capsule scheduler into a low-frequency, state-continuous loop.
It is a real step toward a controlled network-resident lifecycle body.
```

Truth boundary:
```text
F3 still uses GitHub Actions or local CPU as the external runner.
It is not endpoint-free.
It is not CPU-free.
It is not a fully autonomous digital life.
It is not unreviewed high-risk self-mutation.
```

## Dual foundation: NLANG and FIELD

Status: created, not complete.

Reason:
```text
The project cannot walk on one leg.
NLANG is needed so network language becomes a real compiler input.
FIELD is needed so network tide/state can be tested as a drive signal.
Both must be separated and proven before stronger ghost-computer claims.
```

Separation:
```text
nlang/ contains language, grammar, compiler, and action_plan proof logic.
field/ contains network tide sampling, bitstream encoding, controls, and feasibility probes.
F stage files must not absorb both tracks into a large monolith.
```

Created files:
```text
DUAL_FOUNDATION_NLANG_FIELD.md
nlang/NLANG_1_SPEC.md
nlang/nlang_compiler_v0.py
nlang/sample_rules.nlang
nlang/sample_state.json
field/FIELD_1_PROTOCOL.md
field/field_signal_probe_v0.py
field/targets.json
```

NLANG smoke:
```text
run_path=runs/latest_nlang_1_compiler_result.json
ok=true
selected_action=peer_check
risk_level=low
fix=right-side state path resolution was added after the first smoke exposed a semantic bug
```

FIELD smoke:
```text
run_path=runs/latest_field_1_signal_probe_result.json
ok=true
sample_count=4
network_bits=1,1,1,1
controls=fixed_bits,prng_bits
```

Truth meaning:
```text
The two-track foundation is now explicit and separated.
The smoke tests prove the files are executable and the first minimal signals exist.
```

Truth boundary:
```text
This does not prove the dual foundation is complete.
NLANG has not yet driven real remote capsule actions.
FIELD has not yet shown useful spontaneous compute or advantage over controls.
F4 must wait or consume only the parts that are actually proven.
```

## NLANG-1A and FIELD-1A

Status: completed V0, foundation still not complete.

NLANG-1A:
```text
run_path=runs/latest_nlang_1a_remote_f3_compile_result.json
ok=true
remote_state_hash=5deb8244675edcf6
remote_state_hash_ok=true
remote_run_id=nsl-f3-workflow_dispatch-28332909221-attempt-1
selected_action=split
selected_rule=WHEN f3.child.retired == true AND f3.last_peer_check_cycle_count >= f3.lifecycle_cycle_count THEN split
```

Meaning:
```text
NLANG-1A connected the compiler to real remote F3 state.
The selected action came from network-language rules, not sample state.
It did not execute the action yet.
```

FIELD-1A:
```text
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

Meaning:
```text
FIELD-1A found repeated metric-bound network drive signal.
It beats fixed control but does not beat PRNG control.
This is evidence for signal, not proof of spontaneous useful compute.
```

Truth boundary:
```text
NLANG-1A has not materialized the action_plan.
FIELD-1A has not proven PRNG advantage, CPU-free computation, or network supercompute.
Next work should be NLANG-1B and FIELD-1B, not F4 yet.
```

## NLANG-1B and FIELD-1B

Status: completed V0.

NLANG-1B:
```text
run_path=runs/latest_nlang_1b_materialize_result.json
ok=true
run_id=nlang_1b_local-20260628202419
compiled_selected_action=split
proof_ledger_hash=5030a04f24a3ef11
```

Materialized transition:
```text
before_child=retired vitality=0
after_child=split_child retired=false vitality=65
after_child_hash=0783b869bf3e35e9
f2_state_hash=74c9ab59d59c4fee
f3_state_hash=853eac1c8ae2b1dc
```

Meaning:
```text
NLANG-1B is the first proof that NLANG compiler output can be materialized into real remote F2/F3 state.
The runner still exists, but it followed the compiled action_plan instead of choosing the action itself.
```

FIELD-1B:
```text
run_path=runs/latest_field_1b_stronger_metrics_result.json
ok=true
rounds=5
batches=3
target_count=4
sample_count=60
verdict=field_signal_present_no_prng_advantage
```

Meaning:
```text
FIELD-1B strengthened the signal test with more targets and non-latency streams.
The signal beats fixed control across latency, non-latency, and mixed streams.
It still does not prove strong PRNG advantage.
```

Truth boundary:
```text
NLANG-1B does not prove endpoint-free or CPU-free execution.
FIELD-1B does not prove spontaneous compute or network supercompute.
Next work should be NLANG-1C remote workflow materializer and FIELD-1C task-level utility.
```


## 2026-06-29 NLANG-1C / FIELD-1C

NLANG-1C completed by remote GitHub Actions workflow.

```text
workflow=https://github.com/tong0202/qimingxing-test2-network-state-20260626-034447/actions/runs/28335410602
run_id=nlang_1c_remote_external-20260628204412
action=decay
before_child=split_child vitality=65
after_child=decayed vitality=30
f3_state_hash=8b3648b4b8593d09
proof_ledger_hash=ef59ffc0d73482e5
```

FIELD-1C completed a task-level utility benchmark.

```text
run_id=field_1c_task_utility-20260628204404
verdict=no_task_utility
mixed_score=24.4514
fixed_best=27.225039
prng_mean_total=33.693668
remote_state_hash=3247a781feae12e6
```

Truth boundary:

```text
NLANG-1C proves remote workflow materialization over mutable anchors.
FIELD-1C produced a negative task-utility result.
Neither result proves endpoint-free execution, CPU-free computation, or network supercompute.
```
