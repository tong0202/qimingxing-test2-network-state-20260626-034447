# Dual foundation: NLANG and FIELD

## Status

```text
foundation contract created
NLANG and FIELD are separated
neither foundation is proven complete yet
F4 must not claim final basis until both tracks have evidence
```

## Why this file exists

F0-F3 proved a remote capsule lifecycle over mutable network anchors.
That is useful, but it is not enough for the original goal.

The next real foundation has two legs:

```text
NLANG: make network language formal, compilable, and proof-driven.
FIELD: test whether network state/tide can provide a real drive signal, not just stored data.
```

Do not merge these into one large script.

## Track A: NLANG

Purpose:

```text
Network language decides what should happen.
The material runner only compiles, verifies, and writes the result.
```

Required proof:

```text
formal grammar exists
rules can be parsed
predicates can be evaluated from network state evidence
compiler emits an action_plan
action_plan includes proof inputs and risk level
runner no longer owns the main decision logic
```

Not proven yet:

```text
network language as the true decision layer
network language compiling real network-state conditions into material actions
```

## Track B: FIELD

Purpose:

```text
Network tide/state provides the drive signal.
The signal must be measurable, encodable, reproducible, and useful beyond guesswork.
```

Required proof:

```text
multi-path network signals can be sampled
signals can be encoded into a bitstream/state vector
fixed and pseudo-random controls exist
network signal can drive a minimal state machine
results can be compared against controls
advantage or failure is recorded honestly
```

Not proven yet:

```text
network tide can provide useful spontaneous compute
network tide can drive a compiler without material decision logic
```

## Relationship to F

```text
F remains the product mainline.
NLANG and FIELD are foundation prerequisites.
F4 should only use what NLANG and FIELD have actually proven.
```

## Routing rule

```text
No new monolith files.
NLANG files stay under nlang/.
FIELD files stay under field/.
F files stay at the stage level and call the separated modules when needed.
```

