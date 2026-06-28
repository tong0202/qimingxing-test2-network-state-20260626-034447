# E8.3 统一醒后体检挂载层

## 中文名字

所有低频唤醒路径的醒后体检挂载。

## 这一步证明什么

E8.2 已经证明：外部唤醒之后可以自动做一次醒后体检，并写回低风险维护回执。

E8.3 要证明：这个体检不是只挂在 E7.3a HTTP bridge 后面，而是接到主要低频唤醒路径后面。

## 当前覆盖的路径

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

## 完成标准

必须至少验证：

```text
E7 workflow_dispatch 后，states/e8-2-last-run.json 写回 owner_workflow=E7 Controlled Vitals Self Maintenance。
E7.1 workflow_dispatch 后，states/e8-2-last-run.json 写回 owner_workflow=E7.1 External Wake Timer。
E7.3a repository_dispatch 后，states/e8-2-last-run.json 写回 owner_workflow=E7.3a HTTP Bridge Entry。
三条路径的 E8.2 都是 ok=true、post_wake_ready=true。
```

## 没证明什么

```text
没有证明第三方 Cloudflare 时钟已经接入。
没有证明无 CPU 自唤醒。
没有证明自主进化。
没有证明所有历史 L/E 工作流都已经统一挂载。
没有改变权限、密钥、核心代码自修改策略。
```

## 下一步

如果 E8.3 成立，下一步可以做：

```text
E8.4：统一醒后体检索引，把每次醒后体检追加到历史 ledger，避免只看 latest 文件。
```
