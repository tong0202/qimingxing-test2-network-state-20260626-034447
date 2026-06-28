# F2 lifecycle-driven self-scheduler

## Status

```text
completed V0
local control run verified
remote GitHub Actions run verified
```

## Goal

F2 tests whether the capsule system can choose the next low-risk lifecycle event from remote state.

This is different from F1. F1 runs a fixed lifecycle chain. F2 reads the current F1 lifecycle state, scores candidate events, chooses one event per tick, executes it, and records the decisions.

## Remote state paths

```text
states/f2-scheduler-capsule.json
states/f2-capsules/scheduler_child.json
states/f2-scheduler-state.json
states/f2-scheduler-ledger.json
states/f2-last-run.json
states/f2-last-report.json
```

## Inputs

```text
states/f1-lifecycle-state.json
states/f1-lifecycle-registry.json
states/f1-capsules/repair_capsule_child.json
```

## Candidate actions

```text
split: create an active scheduler child when no active child exists
decay: reduce child vitality when active vitality is above threshold
retire: retire child when vitality reaches threshold
peer_check: verify source F1 state, registry, and child hash
sleep: place memory shadow into sleeping state
wake: wake memory shadow from sleeping state
observe: fallback read-only event
```

## Completion criteria

```text
read and verify F1 lifecycle state
write scheduler capsule
score candidate events each tick
select actions from current scheduler state
execute selected low-risk actions
write scheduler state with state_hash
append scheduler ledger with ledger_hash
write last-run and last-report
verify all final hashes
```

## What F2 proves

```text
The next lifecycle event can be selected from state and policy.
The scheduler records candidates, selected action, reason, and execution evidence.
The scheduler can change its next choice after its own state changes.
```

## What F2 does not prove

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove self-executing capsules.
It does not prove fully autonomous digital life.
It is still external-runner scheduling over mutable remote anchors.
```

## Completion evidence

Local control run:

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

Remote GitHub Actions run:

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

Next recommended stage:

```text
F3: low-frequency multi-run self-scheduling loop.
Goal: let the completed F2 scheduler run across multiple low-frequency windows,
preserve its previous state, and prove that later runs make different choices
because earlier runs changed the network state.
```
