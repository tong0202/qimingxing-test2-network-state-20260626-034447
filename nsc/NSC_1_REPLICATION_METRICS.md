# NSC-1 Replication And Split Metrics

Status: implemented for multi-batch replication.

Goal:

```text
Repeat NSC-0 across multiple batches, then separate the weak edge into four
questions:

1. Coupling: does real network input couple to state changes more than controls?
2. Recovery: does real input repair disturbance better than controls?
3. Convergence: does real input move closer to the target better than controls?
4. Temporal order: does the real sequence beat shuffled and reversed real input?
```

Protocol:

```text
Each batch uses the same NSC-0 state body, goal, transducer, and perturbation.
Controls are fixed, PRNG, shuffled_real, and reversed_real.
PRNG and shuffle seeds change by batch.
```

Metric interpretation:

```text
strong_stable: real wins at least 70 percent of batches and average margin is at least 5 percent.
weak_stable: real wins at least 60 percent of batches and average margin is positive.
unstable_or_negative: otherwise.
```

Truth boundary:

```text
NSC-1 tests repeatability of the NSC-0 weak edge.
It does not prove CPU-free computation, endpoint-free execution, faster-than-CPU
compute, or a stable network compute law by itself.
```

Latest V0 result:

```text
run_id=nsc_1_replication_metrics-20260628212502
batches=5
rounds_per_batch=8
verdict=nsc_1_no_stable_edge

effective_state_work: win_rate=0.2 mean_margin_rate=-0.031545
convergence:          win_rate=0.0 mean_margin_rate=-0.078309
recovery:             win_rate=0.0 mean_margin_rate=-0.074298
coupling:             win_rate=0.2 mean_margin_rate=-0.257237
temporal_order:       win_rate=0.2 mean_margin_rate=-0.028264
```

Meaning:

```text
NSC-0's weak edge did not survive this stricter replication.
The current transducer and metric set do not show a stable network-state compute
law. NSC should continue only as an experimental research branch unless a
stronger repeatable effect appears.
```
