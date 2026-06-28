# F1 capsule lifecycle layer

## Goal

F1 turns the F0 rebuild proof into a lifecycle layer.

The capsule is no longer only a file that can be rebuilt. It now has recorded lifecycle events:

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

## Remote state paths

```text
states/f1-capsules/<role>.json
states/f1-capsules/repair_capsule_child.json
states/f1-lifecycle-registry.json
states/f1-lifecycle-state.json
states/f1-lifecycle-ledger.json
states/f1-last-run.json
states/f1-last-report.json
```

## Completion criteria

```text
birth: seed five lifecycle capsules
sleep: move memory_capsule into sleeping state
wake: move memory_capsule back to awake state
peer_check: verify all five main capsules
repair: delete and rebuild rule_capsule through quorum
split: create repair_capsule_child from repair_capsule
decay: reduce child vitality and mark decayed
retire: mark child retired with vitality 0
state: write lifecycle state with state_hash
ledger: append run entry with ledger_hash
last-run/report: write final evidence
```

## What F1 proves

```text
Capsules can carry lifecycle state in remote anchors.
Lifecycle transitions can be written and hash-verified.
A lifecycle chain can include repair and split, not only passive storage.
The run leaves a state file, ledger entry, last-run, and last-report.
```

## What F1 does not prove

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove self-executing capsules.
It does not prove fully autonomous digital life.
It proves lifecycle transitions over mutable remote anchors.
```
