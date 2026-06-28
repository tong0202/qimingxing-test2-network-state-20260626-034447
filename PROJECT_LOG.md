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
