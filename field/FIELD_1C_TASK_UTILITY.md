# FIELD-1C Task Utility Test

Status: implemented for task-level verification.

Goal:

```text
Stop judging the network field only by entropy and coverage.
Use the field signal to choose a real next network read target, then score the
choice against the next observed target quality.
```

Task:

```text
Given current multi-target network samples, choose which target should be used
for the next read window. The reward is measured from the next round's real
status, latency, headers, body hash, and error state.
```

Controls:

```text
fixed_first
fixed_cycle
prng_mean
prng_median
oracle_next_best as an upper bound, not a fair competitor
```

Verdicts:

```text
task_utility_strong: field choice beats fixed controls and PRNG mean in most batches.
task_utility_beats_fixed_only: field choice beats fixed controls but not PRNG mean.
no_task_utility: task-level improvement is not observed.
inconclusive: not enough samples.
```

Truth boundary:

```text
FIELD-1C can show task-level usefulness or failure for this specific routing task.
It does not prove CPU-free computation, spontaneous compute, or network supercompute.
```
