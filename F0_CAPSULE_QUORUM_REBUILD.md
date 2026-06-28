# F0 capsule quorum rebuild experiment

## Goal

F0 tests whether a remote capsule network can survive the loss of one capsule file.

The test is not a metaphor-only check. The runner writes five capsules to a remote GitHub anchor, deletes one target capsule, confirms that it is missing, asks the remaining capsules to vote on the expected target hash, and rebuilds the missing capsule when quorum passes.

## Capsule roles

```text
identity_capsule: identity and continuity root
memory_capsule: memory root and ledger pointer
rule_capsule: low-risk policy and rebuild policy
peer_capsule: peer list, quorum threshold, expected hashes
repair_capsule: recovery receipt rules
```

Default disappearance target:

```text
rule_capsule
```

## Remote state paths

```text
states/f0-capsules/<role>.json
states/f0-capsule-registry.json
states/f0-rebuild-ledger.json
states/f0-last-run.json
states/f0-last-report.json
```

## Completion criteria

```text
seed five capsules to the remote anchor
verify all capsule hashes
delete the target capsule file
confirm target read returns missing
read the four alive capsules
collect at least 3 matching votes for the target expected_core_hash
rebuild the missing target capsule from the registry blueprint
verify rebuilt core_hash and capsule_hash
write F0 ledger, last-run, and last-report
```

## What F0 proves

```text
A capsule body can be stored as remote network state.
One capsule can disappear from the remote anchor.
Alive peer capsules can witness the expected identity of the missing capsule.
The missing capsule can be rebuilt after quorum passes.
The rebuild leaves ledger evidence.
```

## What F0 does not prove

```text
It does not prove endpoint-free existence.
It does not prove CPU-free network computation.
It does not prove tamper-proof storage.
It does not prove fully autonomous digital life.
It proves self-repair over mutable remote anchors.
```
