# NLANG-1 formal language and compiler V0

## Goal

Define a small network language that can be parsed, verified, and compiled.

The first target is not a general programming language.
The first target is a proof-driven rule language:

```text
WHEN <predicate> [AND <predicate>...] THEN <action>
```

## Predicate form

```text
source.path.field == value
source.path.field != value
source.path.field > number
source.path.field >= number
source.path.field < number
source.path.field <= number
```

Examples:

```text
WHEN f3.child.retired == true AND f3.last_peer_check_cycle_count < f3.lifecycle_cycle_count THEN peer_check
WHEN f3.child.retired == true AND f3.last_peer_check_cycle_count >= f3.lifecycle_cycle_count THEN split
WHEN f3.child.vitality > 35 THEN decay
WHEN f3.child.vitality <= 35 THEN retire
```

## Compile output

The compiler must emit:

```text
selected_rule
matched_predicates
unmatched_predicates
action_plan
risk_level
required_reads
required_writes
proof
truth_boundary
```

## Risk levels

```text
low: read state, write scoped state, append ledger
medium: repair or regenerate scoped capsule
high: new permissions, new external target, code mutation, deletion outside scope
```

NLANG-1 allows only low-risk action plans.

## Completion criteria

```text
sample rules parse
sample state compiles to one selected action
compiler proof explains why selected rule won
compiler proof explains why unselected rules did not win
compiler emits JSON action_plan
```

## Boundary

NLANG-1 does not prove endpoint-free execution.
It does not prove spontaneous network compute.
It only moves decision logic from Python code into a formal network language layer.

