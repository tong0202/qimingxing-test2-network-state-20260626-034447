# NLANG-1A remote F3 compile experiment

## Goal

Connect the NLANG compiler to the real remote F3 state.

NLANG-1 used a sample state.
NLANG-1A reads:

```text
states/f3-loop-state.json
```

from the remote GitHub network anchor, maps it into NLANG state, and compiles the next low-risk action from network-language rules.

## Expected meaning

```text
Python is no longer choosing the next action directly in this experiment.
Python reads remote state, parses NLANG rules, and emits an action_plan.
The selected action must be explained by matched predicates.
```

## Remote input

```text
remote_repo=tong0202/qimingxing-test2-network-state-20260626-034447
remote_path=states/f3-loop-state.json
```

## Completion criteria

```text
remote F3 state is fetched
remote state_hash verifies
remote F3 state is mapped into NLANG input state
network-language rules compile to one low-risk action_plan
compiler proof records matched and unmatched predicates
result is written to runs/latest_nlang_1a_remote_f3_compile_result.json
```

## Boundary

NLANG-1A does not execute the action.
It proves remote-state compilation only.

It does not prove endpoint-free execution.
It does not prove spontaneous network compute.
It does not prove that the material runner has been reduced to a full thin materializer yet.

## Completion evidence

```text
run_path=runs/latest_nlang_1a_remote_f3_compile_result.json
ok=true
remote_path=states/f3-loop-state.json
remote_state_hash=5deb8244675edcf6
remote_state_hash_ok=true
remote_run_id=nsl-f3-workflow_dispatch-28332909221-attempt-1
selected_action=split
risk_level=low
```

Selected rule:

```text
WHEN f3.child.retired == true AND f3.last_peer_check_cycle_count >= f3.lifecycle_cycle_count THEN split
```

Meaning:

```text
NLANG-1A did not use sample state.
It read the real F3 remote state and compiled the next action from NLANG rules.
```

Next:

```text
NLANG-1B: let a thin materializer execute the compiled action_plan and write proof.
```
