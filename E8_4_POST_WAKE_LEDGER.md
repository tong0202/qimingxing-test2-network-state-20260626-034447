# E8.4 统一醒后体检 ledger

## 中文名字

醒后体检历史账本。

## 这一步证明什么

E8.3 已经让三条主线低频唤醒路径都能写回 E8.2 醒后体检。

E8.4 要解决的问题是：不能只看 `states/e8-2-last-run.json`，因为 latest 会被下一次运行覆盖。

所以 E8.4 新增一个统一 ledger：

```text
states/e8-4-post-wake-ledger.json
states/e8-4-last-ledger-report.json
```

每次 E8.2 完成后，脚本会：

```text
读取已有 ledger
读取 states/e8-2-post-wake-snapshots/*.json
把历史 snapshot 回填成 ledger entry
把当前 E8.2 结果加入 ledger
按 run_id 去重
写回 ledger_hash
```

## 完成标准

```text
ledger 文件存在
entry_count >= 3
covered_workflows 至少包含：
- E7 Controlled Vitals Self Maintenance
- E7.1 External Wake Timer
- E7.3a HTTP Bridge Entry
最新 E8.2 运行后 ledger_entry_count 增加或保持去重后的正确数量
ledger_hash 校验通过
```

## 没证明什么

```text
它不是不可篡改数据库。
它不是区块链。
它不证明无 CPU 自唤醒。
它不证明自主进化。
它只是把已有醒后体检证据组织成统一可查的历史账本。
```

## 下一步

如果 E8.4 成立，下一步可以做：

```text
E8.5：ledger 查询器和状态摘要，让人不用打开大 JSON 也能看最近 N 次醒后体检。
```
