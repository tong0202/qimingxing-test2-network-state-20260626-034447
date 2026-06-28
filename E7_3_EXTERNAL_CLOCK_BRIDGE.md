# E7.3 外部时钟桥接方案

## 中文名字

外部时钟唤醒桥。

## 目标

把 E7.2 的 Wake Capsule 桥接器改造成可以被外部 HTTP 定时器叫醒的入口。

结构是：

```text
外部 HTTP 时钟
-> GitHub repository_dispatch: qmx_e7_3_bridge_tick
-> E7.3a HTTP Bridge Entry
-> scripts/nsl_e7_2_wake_capsule_bridge.py
-> 写入并校验 Wake Capsule
-> GitHub repository_dispatch: qmx_e7_wake_capsule
-> E7.2 Wake Capsule Dispatch Receiver
-> E7 低风险自维护
-> states/e7-last-run.json 写回
```

## E7.3a 证明什么

证明桥接器已经不需要人在命令行里输入参数。

外部调用方只需要发一个 HTTP `repository_dispatch` 事件：

```text
event_type = qmx_e7_3_bridge_tick
```

之后胶囊生成、胶囊验证、E7.2 反向唤醒、E7 写回都由远端工作流自己完成。

## E7.3a 不证明什么

它不证明第三方时钟已经接入。

如果这一步是用本机 `gh api` 手动打的 HTTP 请求，只能证明 HTTP 入口可用，不能算自然唤醒。

## E7.3b 外部时钟怎么接

外部时钟源需要能定时发送一个 HTTP POST 到 GitHub API：

```text
POST https://api.github.com/repos/tong0202/qimingxing-test2-network-state-20260626-034447/dispatches
```

请求头：

```text
Accept: application/vnd.github+json
Authorization: Bearer <只放在外部平台密钥区的 GitHub PAT>
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

请求体：

```json
{
  "event_type": "qmx_e7_3_bridge_tick",
  "client_payload": {
    "clock": "external-clock",
    "stage": "E7.3b",
    "intent": "wake_bridge_without_manual_operator"
  }
}
```

可选平台：

- `cron-job.org`：创建定时 HTTP POST，把 PAT 放在 Header 里。
- `UptimeRobot`：如果账号支持自定义 POST 和 Header，可以直接打 GitHub dispatch；如果只支持 GET/简单监控，需要中转 Worker。
- `Cloudflare Worker Cron`：把 PAT 放进 Worker Secret，由 Cron Trigger 定时调用 GitHub dispatch。

## E7.3c 完成标准

必须同时满足：

- 出现 `E7.3a HTTP Bridge Entry` 的远端 run。
- run 的事件是 `repository_dispatch`。
- 这个 run 不是本机手动 `gh api` 触发，而是来自第三方时钟源。
- 随后出现 `E7.2 Wake Capsule Dispatch Receiver` 的 `repository_dispatch` run。
- `states/e7-last-run.json` 写回，并且：

```text
ok=true
maintenance_ok=true
executed_count=4
blocked_count=4
owner_event_name=repository_dispatch
```

## 安全边界

外部平台只能持有最小权限令牌，令牌不能写进仓库文件和日志。

E7.3 仍然不是无 CPU 自唤醒。它证明的是：

```text
第三方时钟可以叫醒网络中的 Wake Capsule 桥；
桥可以再叫醒 GitHub 上的 E7 自维护循环；
状态可以写回网络接收器。
```

它没有证明胶囊自己凭空执行，也没有证明完全自由漂浮的网络生命已经完成。
