# F3 low-frequency multi-run self-scheduler loop

## Goal

F3 makes F the mainline.

F2 proved that a scheduler can choose low-risk lifecycle actions from state in one run.
F3 tests whether that scheduler can continue across multiple wake windows.

## Mainline rule

```text
F series is now the mainline.
L series is auxiliary infrastructure: network state language, controlled interpreter, low-frequency base.
E series is auxiliary infrastructure: external wake, post-wake health check, ledger, status summary.
F series owns the product direction: capsule lifecycle, self-scheduling, self-repair, controlled self-regeneration.
```

## Remote state paths

```text
states/f3-loop-capsule.json
states/f3-loop-state.json
states/f3-loop-ledger.json
states/f3-last-run.json
states/f3-last-report.json
```

F3 also updates the F2 scheduler body state:

```text
states/f2-scheduler-state.json
states/f2-scheduler-ledger.json
states/f2-capsules/scheduler_child.json
```

## How F3 works

Each wake window executes one scheduler action:

```text
read F1 lifecycle state
read previous F3 loop state
read current F2 scheduler state
score one low-risk lifecycle action
execute exactly one selected action
write F2 scheduler state
write F3 loop state
append F3 loop ledger
write last-run and last-report
```

## Candidate actions

```text
split: create the next scheduler child when no active child exists
decay: reduce active child vitality
retire: retire child after vitality reaches threshold
peer_check: verify the source F1 lifecycle state after a lifecycle cycle ends
observe: fallback read-only event
```

## Completion criteria

```text
local control run passes
remote GitHub Actions workflow exists
at least four remote wake windows run successfully
the selected actions differ because previous windows changed remote state
F3 state_hash, ledger_hash, last_run_hash, and report_hash verify
F3 records F as mainline and L/E as auxiliary
```

## What F3 proves

```text
The scheduler can persist state across multiple wake windows.
A later wake can choose a different action because an earlier wake changed the remote state.
F has become the active mainline, while L/E are supporting layers.
```

## What F3 does not prove

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove self-executing capsules without an external runner.
It does not prove fully autonomous digital life.
It does not prove unreviewed high-risk self-mutation.
It is still a controlled low-frequency loop over mutable remote anchors.
```
