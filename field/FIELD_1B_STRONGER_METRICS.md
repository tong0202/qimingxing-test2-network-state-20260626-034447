# FIELD-1B stronger independent field metrics

## Goal

FIELD-1B tests whether the network field signal remains useful under stronger conditions:

```text
more independent targets
latency bitstream
non-latency header/content bitstream
mixed bitstream
fixed and PRNG controls
```

## Why this exists

FIELD-1A beat fixed control but did not beat PRNG.
FIELD-1B should not repeat the same weak metric.

## Target classes

```text
GitHub API
GitHub Raw state
Cloudflare trace
Wikipedia landing page
```

## Metrics

```text
entropy
transition rate
state-machine coverage
final state
per-batch control comparison
```

## Verdicts

```text
strong_field_advantage: mixed or non-latency signal beats PRNG across most batches
field_signal_present_no_prng_advantage: signal beats fixed but not PRNG
latency_only_signal: only latency-derived stream works
inconclusive: no stable signal
```

## Boundary

FIELD-1B still does not prove CPU-free computation or network supercompute.
It only tests whether network field signals are useful under stronger metrics.

## Completion evidence

```text
run_path=runs/latest_field_1b_stronger_metrics_result.json
ok=true
rounds=5
batches=3
target_count=4
sample_count=60
```

Aggregate streams:

```text
latency_entropy=1.0
latency_coverage=24

non_latency_entropy=0.9968
non_latency_coverage=27

mixed_entropy=0.9871
mixed_coverage=25
```

Control comparison:

```text
beat_fixed_counts:
  latency=3/3
  non_latency=3/3
  mixed=3/3

beat_prng_counts:
  latency=2/3
  non_latency=1/3
  mixed=1/3
```

Verdict:

```text
field_signal_present_no_prng_advantage
```

Meaning:

```text
FIELD-1B strengthened FIELD-1A with more targets and non-latency streams.
The network field signal is present and beats fixed control.
It still does not prove a strong advantage over PRNG.
```
