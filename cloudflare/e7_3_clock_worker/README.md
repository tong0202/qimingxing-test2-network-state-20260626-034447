# E7.3 Cloudflare Worker Cron

## 这是什么

这是启明星 E7.3b 的外部时钟源模板。

它每 10 分钟由 Cloudflare Cron 自动运行一次，然后调用 GitHub：

```text
Cloudflare Worker Cron
-> GitHub repository_dispatch: qmx_e7_3_bridge_tick
-> E7.3a HTTP Bridge Entry
-> E7.2 Wake Capsule bridge
-> E7 self-maintenance
-> states/e7-last-run.json
```

## 需要你自己放的密钥

不要把 GitHub token 写进这个目录。

在 Cloudflare Worker 的 Variables and Secrets 里添加：

```text
GITHUB_TOKEN = 你的 GitHub fine-grained PAT
QMX_WORKER_TEST_TOKEN = 你自己随便生成的一段测试口令，可选
```

GitHub PAT 最小权限：

```text
Repository: tong0202/qimingxing-test2-network-state-20260626-034447
Contents: Read and write
Metadata: Read
```

`repository_dispatch` 官方要求 `Contents: write`。

## 网页部署简版

1. 打开 Cloudflare Dashboard。
2. 进入 Workers & Pages。
3. Create application。
4. 选择 Worker。
5. 创建一个名字，例如 `qimingxing-e7-3-clock`。
6. 打开 Worker 的代码编辑器。
7. 把 `worker.js` 的内容粘进去并部署。
8. 进入 Settings -> Variables and Secrets。
9. 添加 Secret：`GITHUB_TOKEN`。
10. 进入 Triggers -> Cron Triggers。
11. 添加 cron：`*/10 * * * *`。
12. 保存后等待下一次定时触发。

## 验收

Cloudflare 触发后，GitHub 应出现：

```text
E7.3a HTTP Bridge Entry
event=repository_dispatch
conclusion=success
```

随后应出现：

```text
E7.2 Wake Capsule Dispatch Receiver
event=repository_dispatch
conclusion=success
```

最终远端状态应写回：

```text
states/e7-last-run.json
ok=true
maintenance_ok=true
executed_count=4
blocked_count=4
owner_event_name=repository_dispatch
```

## 真实边界

这证明的是第三方外部时钟可以非手动叫醒启明星的桥接链路。

它不证明无 CPU 自唤醒，也不证明胶囊自己凭空执行。
