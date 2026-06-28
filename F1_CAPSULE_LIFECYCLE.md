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

## Latest evidence

Local control run:

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

Remote GitHub Actions run:

```text
workflow=F1 Capsule Lifecycle
run=28331684924
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
last_run_hash=1cbddd4683028f85 verified=true
report_hash=3b55864b657482ab verified=true
registry_hash=d44a0ac3e0432961 verified=true
retired_child_hash=2285be267c4541ad verified=true
```

Engineering note:

```text
The first remote F1 run failed because GitHub main-branch reads lagged immediately after writes.
The fix was to wait for each critical hash to appear before judging the lifecycle event.
This is a real network-anchor constraint, not a conceptual failure.
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
