# NLANG-1B compiled action materialization

## Goal

NLANG-1B executes the action_plan compiled by NLANG-1A.

The runner must stay thin:

```text
read remote F3 state
compile NLANG rules
verify selected action is low risk
materialize selected action
write proof ledger
```

The runner must not choose the next action with Python business logic.

## Input

```text
states/f3-loop-state.json
nlang/remote_f3_rules.nlang
```

## Expected current action

At the start of NLANG-1B, NLANG-1A compiled:

```text
selected_action=split
```

from real remote F3 state.

## Output

```text
states/nlang-1b-proof-ledger.json
states/nlang-1b-last-run.json
states/f2-scheduler-state.json
states/f2-scheduler-ledger.json
states/f2-capsules/scheduler_child.json
states/f3-loop-state.json
states/f3-loop-ledger.json
```

## Completion criteria

```text
remote F3 state hash verifies
NLANG compiler selects a low-risk action
thin materializer executes that selected action only
F2/F3 remote state is updated
proof ledger records rule, predicates, action_plan, writes, and hashes
```

## Boundary

NLANG-1B proves compiled-plan materialization over remote anchors.

It does not prove endpoint-free execution.
It does not prove CPU-free computation.
It does not prove spontaneous network compute.

## Completion evidence

```text
run_path=runs/latest_nlang_1b_materialize_result.json
ok=true
run_id=nlang_1b_local-20260628202419
remote_f3_state_hash_before=5deb8244675edcf6
compiled_selected_action=split
```

Selected rule:

```text
WHEN f3.child.retired == true AND f3.last_peer_check_cycle_count >= f3.lifecycle_cycle_count THEN split
```

Materialized transition:

```text
before_child.state=retired
before_child.retired=true
before_child.vitality=0

after_child.state=split_child
after_child.retired=false
after_child.vitality=65
after_child.capsule_hash=0783b869bf3e35e9
```

Remote hashes:

```text
f2_state_hash=74c9ab59d59c4fee
f2_ledger_hash=a73990719ee0be5d
f3_state_hash=853eac1c8ae2b1dc
f3_ledger_hash=3b64029660f2f563
proof_ledger_hash=5030a04f24a3ef11
f3_last_run_hash=ea85c800d5e6d37a
f3_report_hash=a32814572ba2e946
```

Meaning:

```text
NLANG-1B executed the low-risk split action selected by NLANG rules.
This is the first proof that NLANG output can be materialized into real remote F2/F3 state.
```
