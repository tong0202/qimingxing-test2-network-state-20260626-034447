# E8.5 ledger 查询器和状态摘要

## 中文名字

醒后体检账本查询器。

## 这一步证明什么

E8.4 已经有统一 ledger，但 ledger 很大，不适合每次人工打开。

E8.5 把 ledger 转成轻量摘要：

```text
states/e8-5-ledger-status-summary.json
states/e8-5-recent-post-wake.json
states/e8-5-last-run.json
states/e8-5-last-report.json
```

## 摘要会显示什么

```text
entry_count：账本总记录数
ready_count：ready 记录数
ready_rate_percent：ready 比例
recent_entries：最近 N 次醒后体检
latest_by_workflow：每条唤醒路径的最近一次体检
workflow_counts：来源路径统计
event_counts：触发事件统计
status_level：healthy / healthy_with_known_gaps / degraded
alerts：需要注意的情况
```

## 完成标准

```text
能读取 states/e8-4-post-wake-ledger.json
ledger_hash 校验通过
entry_hash 全部校验通过
summary 写回成功
recent 写回成功
last-run / last-report 写回成功
```

## 没证明什么

```text
E8.5 只是查询和摘要层。
它不执行自维护动作。
它不是不可篡改数据库。
它不证明无 CPU 自唤醒。
它不证明自主进化。
```

## 下一步

如果 E8.5 成立，下一步可以做：

```text
E8.6：把 E8.5 摘要接入一个简单 Dashboard，让人不用看 JSON。
```
