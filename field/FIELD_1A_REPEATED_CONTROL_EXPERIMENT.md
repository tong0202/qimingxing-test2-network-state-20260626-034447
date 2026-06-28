# FIELD-1A repeated control experiment

## Goal

Run repeated network tide sampling and compare it with fixed and pseudo-random controls.

FIELD-1 only proved that network samples can be collected and encoded.
FIELD-1A asks whether the network signal shows usable drive properties.

## What is measured

```text
bit balance
transition rate
state-machine coverage
state-machine final state
comparison against fixed control
comparison against deterministic PRNG control
```

## Verdict levels

```text
signal_absent: sampling failed or all useful values are missing
drive_signal_present: network bits differ from fixed control and drive the state machine
beats_fixed_only: network signal beats fixed control but not PRNG
beats_prng_control: network signal beats both fixed and PRNG on the measured task
inconclusive: data exists but advantage is not stable enough
```

## Boundary

FIELD-1A does not prove CPU-free computation.
It does not prove a network supercomputer.
It only tests whether network tide is a usable drive input under the current metric.

## Completion evidence

```text
run_path=runs/latest_field_1a_repeated_control_result.json
ok=true
rounds=8
batches=3
sample_count=48
sample_ok_rate=1.0 in each batch
```

Aggregate metrics:

```text
network_entropy=0.995
network_transition_rate=0.5319
network_coverage=17

fixed_entropy=0.0
fixed_transition_rate=0.0
fixed_coverage=8

prng_entropy=1.0
prng_transition_rate=0.5745
prng_coverage=15
```

Verdict:

```text
verdict=repeated_metric_beats_fixed_only
beats_fixed_batches=3/3
beats_prng_batches=0/3
signal_batches=3/3
```

Meaning:

```text
FIELD-1A proves a measurable repeated network drive signal under the current metric.
It beats fixed control.
It does not beat PRNG control.
```

Next:

```text
FIELD-1B: add more independent targets, longer runs, and non-latency-derived tasks.
Goal: test whether the field signal has stable usefulness beyond randomness-like drive.
```
