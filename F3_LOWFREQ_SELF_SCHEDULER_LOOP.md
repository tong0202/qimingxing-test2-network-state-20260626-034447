# F3 low-frequency multi-run self-scheduler loop

## Status

```text
completed V0
local control runs verified
multiple remote wake windows verified
F is recorded as mainline
L/E are recorded as auxiliary infrastructure
```

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

## Completion evidence

Local control run:

```text
run_id=nsl-f3-local-20260628190050
ok=true
selected_actions=split,decay,retire,peer_check
window_count=4
lifecycle_cycle_count=1
f3_state_hash=bcf610f70b42bbe3
f3_ledger_hash=443b1d709a3f6a63
```

Remote wake windows:

```text
28332753245 -> split      window_count=5  lifecycle_cycle_count=1
28332772614 -> decay      window_count=6  lifecycle_cycle_count=1
28332794329 -> retire     window_count=7  lifecycle_cycle_count=2
28332816490 -> split      window_count=8  lifecycle_cycle_count=2
28332895658 -> retire     window_count=10 lifecycle_cycle_count=3
28332909221 -> peer_check window_count=11 lifecycle_cycle_count=3 last_peer_check_cycle_count=3
```

Final remote state:

```text
latest_run_id=nsl-f3-workflow_dispatch-28332909221-attempt-1
workflow_run_id=28332909221
workflow_conclusion=success
selected_actions=peer_check
window_count=11
lifecycle_cycle_count=3
last_peer_check_cycle_count=3
f3_state_hash=5deb8244675edcf6
f3_ledger_hash=ac724939ff7593ad
```

Hash verification:

```text
last_run_hash=1f41f72f190ec76a verified=true
report_hash=ea0a66731e6b0399 verified=true
f3_state_hash=5deb8244675edcf6 verified=true
f3_ledger_hash=ac724939ff7593ad verified=true
f3_capsule_hash=6b1137757b7f05f6 verified=true
f3_capsule_core_hash=1fe4708dc7e0233b verified=true
f2_state_hash=f009d59fa0932b1f verified=true
f2_ledger_hash=fac5d6cb37a6f76a verified=true
f2_child_hash=8f2584b54ec860b7 verified=true
```

Engineering correction:

```text
The first four remote wake windows proved continuity, but window 8 selected split
because F3 only checked whether the F1 state hash had already been peer-checked.
The policy was tightened with last_peer_check_cycle_count so every completed
lifecycle cycle needs its own peer_check before the next clean cycle.
The corrected policy was verified by retire -> peer_check across two remote runs.
```

Next recommended stage:

```text
F4: controlled capsule self-maintenance and regeneration loop.
Goal: let the F mainline choose low-risk repair/regeneration tasks from F3 ledger evidence,
while keeping medium/high-risk changes behind review gates.
```
