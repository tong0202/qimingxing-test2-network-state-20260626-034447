# F2 lifecycle-driven self-scheduler

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
