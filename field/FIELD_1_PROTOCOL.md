# FIELD-1 network tide drive feasibility V0

## Goal

Test whether network state/tide can provide a real drive signal.

FIELD-1 does not assume success.
It records either positive evidence or failure evidence.

## Signal sources

Initial measurable signals:

```text
fetch latency
status code
payload size
ETag or missing ETag
Last-Modified or missing Last-Modified
read order jitter
multi-path timing difference
```

## Required controls

```text
fixed control: constant zero/one pattern
pseudo-random control: local deterministic PRNG with fixed seed
network signal: sampled from actual network requests
```

## Minimal proof

FIELD-1 must show:

```text
network samples were collected
network samples were encoded into a bitstream
the bitstream drove a minimal state machine
the same task was run with fixed and PRNG controls
results were compared
advantage, neutrality, or failure was recorded
```

## What counts as useful evidence

Positive evidence:

```text
network signal produces repeatable structure not explained by fixed/PRNG controls
network signal improves a task metric across repeated trials
network signal carries a stable external condition usable by NLANG predicates
```

Negative evidence:

```text
network signal is indistinguishable from control
network signal is too noisy to encode
network signal is slower or worse than local PRNG for the tested task
```

## Boundary

FIELD-1 does not prove CPU-free computation.
It only tests whether network tide can become a real drive input.

