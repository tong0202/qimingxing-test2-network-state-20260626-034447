# NLANG-1C Remote Workflow Materializer

Status: implemented for remote workflow verification.

Goal:

```text
Run the thin NLANG materializer inside GitHub Actions, then write independent
NLANG-1C proof evidence to remote state.
```

What this proves:

```text
The compiled NLANG action_plan can be materialized by a remote workflow runner,
not only by a local Python process on the current PC.
```

What this does not prove:

```text
CPU-free execution.
Endpoint-free execution.
Spontaneous network compute.
Network supercompute.
```

Evidence paths:

```text
runs/latest_nlang_1c_remote_materialize_result.json
states/nlang-1c-last-run.json
states/nlang-1c-proof-ledger.json
states/f2-scheduler-state.json
states/f3-loop-state.json
states/f2-capsules/scheduler_child.json
```

Workflow:

```text
.github/workflows/nlang-1c-remote-materializer.yml
```

Acceptance:

```text
1. GitHub Actions workflow_dispatch starts the workflow.
2. The workflow runs nlang/nlang_1c_remote_materializer.py.
3. states/nlang-1c-last-run.json is written by the remote workflow.
4. states/nlang-1c-proof-ledger.json contains the selected action, before/after child state, and hashes.
5. Result truth_boundary keeps the hard limit: remote runner yes, CPU-free no.
```
