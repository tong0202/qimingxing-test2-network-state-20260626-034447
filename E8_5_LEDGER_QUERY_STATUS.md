# E8.5 ledger query/status summary

## Plain name

Post-wake ledger query layer.

## What this stage proves

E8.4 created a unified post-wake ledger. E8.5 adds a compact query/status layer above it, so later checks do not need to manually open the full ledger JSON.

Remote status files:

```text
states/e8-5-ledger-status-summary.json
states/e8-5-recent-post-wake.json
states/e8-5-last-run.json
states/e8-5-last-report.json
```

## What the summary shows

```text
entry_count: total ledger entries
ready_count: ready entries
ready_rate_percent: ready ratio
recent_entries: latest N post-wake checks
latest_by_workflow: latest check per wake path
workflow_counts: source workflow counts
event_counts: trigger event counts
status_level: healthy / healthy_with_known_gaps / degraded
alerts: explicit known gaps
```

## Completion criteria

```text
read states/e8-4-post-wake-ledger.json
ledger_hash verified
all entry_hash values verified
summary writeback succeeded
recent writeback succeeded
last-run / last-report writeback succeeded
remote declared hashes match local recomputation
```

## Latest remote evidence

```text
workflow=E8.5 Ledger Query Status
run=28330036818
event=workflow_dispatch
conclusion=success
run_id=nsl-e8-5-workflow_dispatch-28330036818-attempt-1
status_level=healthy_with_known_gaps
status_text=healthy_with_recorded_history_gap
entry_count=11
ready_count=10
recent_count=8
recent_ready_count=8
ledger_hash_ok=true
entry_hashes_ok=true
alerts=["history_contains_partial_entries"]
summary_hash=c443a08bf5d9b020 verified=true
recent_hash=d0cb710671b071bb verified=true
last_run_hash=e3e816d0c4ec3c53 verified=true
report_hash=a047df3cd9ddd4bc verified=true
```

## What it does not prove

```text
E8.5 is a query and summary layer only.
It does not run maintenance actions.
It is not tamper-proof storage.
It does not prove CPU-free self-wake.
It does not prove autonomous evolution.
```

## Next step

```text
E8.6: connect the E8.5 summary to a lightweight dashboard or CLI status entry.
Goal: show recent post-wake checks, health trend, and known gaps without opening JSON files.
```
