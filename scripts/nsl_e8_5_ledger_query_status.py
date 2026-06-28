from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_l12_hourly_self_maintenance import (
    commit_hash_from_put,
    content_get,
    content_sha_from_put,
    fetch_json_url,
    gh_token,
    now,
    put_content,
    raw_url,
    run_owner,
    stable_hash,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

LEDGER_PATH = "states/e8-4-post-wake-ledger.json"
SUMMARY_PATH = "states/e8-5-ledger-status-summary.json"
RECENT_PATH = "states/e8-5-recent-post-wake.json"
LAST_RUN_PATH = "states/e8-5-last-run.json"
LAST_REPORT_PATH = "states/e8-5-last-report.json"


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def parse_time(value: Any) -> datetime | None:
    try:
        text = str(value or "").replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100, 2)


def compact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    owner = entry.get("owner") if isinstance(entry.get("owner"), dict) else {}
    health = entry.get("health") if isinstance(entry.get("health"), dict) else {}
    return {
        "run_id": entry.get("run_id"),
        "created_at": entry.get("created_at"),
        "ok": entry.get("ok"),
        "post_wake_ready": entry.get("post_wake_ready"),
        "workflow": owner.get("workflow"),
        "event_name": owner.get("event_name"),
        "owner_run_id": owner.get("run_id"),
        "state_hash": entry.get("state_hash"),
        "snapshot_hash": entry.get("snapshot_hash"),
        "entry_hash": entry.get("entry_hash"),
        "external_clock_pending": health.get("external_clock_pending"),
        "e7_latest_event_name": health.get("e7_latest_event_name"),
    }


def verify_entry(entry: dict[str, Any]) -> dict[str, Any]:
    expected = str(entry.get("entry_hash") or "")
    observed = stable_hash(entry, "entry_hash") if entry else ""
    return {
        "run_id": entry.get("run_id"),
        "ok": bool(expected and expected == observed),
        "expected": expected,
        "observed": observed,
    }


def latest_by_workflow(entries: list[dict[str, Any]]) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        owner = entry.get("owner") if isinstance(entry.get("owner"), dict) else {}
        workflow = str(owner.get("workflow") or "unknown")
        latest[workflow] = entry
    return {workflow: compact_entry(entry) for workflow, entry in sorted(latest.items())}


def count_by(entries: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        owner = entry.get("owner") if isinstance(entry.get("owner"), dict) else {}
        value = str(owner.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def derive_status_level(
    ledger_hash_ok: bool,
    entry_hashes_ok: bool,
    entry_count: int,
    ready_count: int,
    recent_ready_count: int,
    recent_count: int,
    latest_ready: bool,
    latest_age_hours: float | None,
) -> tuple[str, list[str]]:
    alerts: list[str] = []
    if not ledger_hash_ok:
        alerts.append("ledger_hash_mismatch")
    if not entry_hashes_ok:
        alerts.append("entry_hash_mismatch")
    if entry_count == 0:
        alerts.append("ledger_empty")
    if not latest_ready:
        alerts.append("latest_post_wake_not_ready")
    if ready_count < entry_count:
        alerts.append("history_contains_partial_entries")
    if recent_count and recent_ready_count < recent_count:
        alerts.append("recent_window_contains_partial_entries")
    if latest_age_hours is not None and latest_age_hours > 24:
        alerts.append("latest_entry_older_than_24h")

    if not ledger_hash_ok or not entry_hashes_ok or not latest_ready or entry_count == 0:
        return "degraded", alerts
    if alerts:
        return "healthy_with_known_gaps", alerts
    return "healthy", alerts


def build_summary(run_id: str, mode: str, ledger: dict[str, Any], recent_limit: int) -> dict[str, Any]:
    entries = ledger.get("entries") if isinstance(ledger.get("entries"), list) else []
    entries = [entry for entry in entries if isinstance(entry, dict)]
    entry_checks = [verify_entry(entry) for entry in entries]
    ledger_hash_ok = bool(ledger.get("ledger_hash") and ledger.get("ledger_hash") == stable_hash(ledger, "ledger_hash"))
    entry_hashes_ok = all(item["ok"] for item in entry_checks) if entry_checks else False
    ready_entries = [entry for entry in entries if entry.get("post_wake_ready") is True]
    not_ready_entries = [entry for entry in entries if entry.get("post_wake_ready") is not True]
    recent_entries = entries[-recent_limit:] if recent_limit > 0 else []
    latest_entry = entries[-1] if entries else {}
    latest_time = parse_time(latest_entry.get("created_at")) if latest_entry else None
    latest_age_hours = (
        round((datetime.now(timezone.utc) - latest_time).total_seconds() / 3600, 3) if latest_time else None
    )
    recent_ready_count = sum(1 for entry in recent_entries if entry.get("post_wake_ready") is True)
    status_level, alerts = derive_status_level(
        ledger_hash_ok=ledger_hash_ok,
        entry_hashes_ok=entry_hashes_ok,
        entry_count=len(entries),
        ready_count=len(ready_entries),
        recent_ready_count=recent_ready_count,
        recent_count=len(recent_entries),
        latest_ready=bool(latest_entry.get("post_wake_ready")),
        latest_age_hours=latest_age_hours,
    )
    summary = {
        "stage": "E8.5-ledger-status-summary",
        "schema_version": "QMX-E8.5-SUMMARY-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "ledger_path": LEDGER_PATH,
        "ledger_hash": ledger.get("ledger_hash"),
        "ledger_hash_ok": ledger_hash_ok,
        "entry_hashes_ok": entry_hashes_ok,
        "entry_count": len(entries),
        "ready_count": len(ready_entries),
        "not_ready_count": len(not_ready_entries),
        "ready_rate_percent": pct(len(ready_entries), len(entries)),
        "recent_limit": recent_limit,
        "recent_count": len(recent_entries),
        "recent_ready_count": recent_ready_count,
        "recent_ready_rate_percent": pct(recent_ready_count, len(recent_entries)),
        "status_level": status_level,
        "status_text": {
            "healthy": "healthy",
            "healthy_with_known_gaps": "healthy_with_recorded_history_gap",
            "degraded": "degraded_needs_check",
        }[status_level],
        "alerts": alerts,
        "latest_entry": compact_entry(latest_entry) if latest_entry else {},
        "latest_age_hours": latest_age_hours,
        "workflow_counts": count_by(entries, "workflow"),
        "event_counts": count_by(entries, "event_name"),
        "latest_by_workflow": latest_by_workflow(entries),
        "not_ready_entries": [compact_entry(entry) for entry in not_ready_entries[-10:]],
        "recent_entries": [compact_entry(entry) for entry in recent_entries],
        "query_hints": {
            "recent_entries": "最近 N 次醒后体检，默认 8 条。",
            "latest_by_workflow": "每条唤醒路径的最近一次醒后体检。",
            "not_ready_entries": "历史中未完全 ready 的记录，用于审计而不是隐藏。",
        },
        "plain_summary": (
            f"ledger_entries={len(entries)}; ready_entries={len(ready_entries)}; "
            f"recent_entries={len(recent_entries)}; recent_ready={recent_ready_count}; "
            f"status={status_level}."
        ),
        "truth_boundary": (
            "E8.5 is a query and summary layer over the mutable E8.4 ledger. It improves readability and monitoring, "
            "but it is not a new executor, not a tamper-proof database, and not proof of CPU-free wakefulness."
        ),
        "summary_hash": "",
    }
    return seal(summary, "summary_hash")


def build_recent(run_id: str, mode: str, summary: dict[str, Any]) -> dict[str, Any]:
    recent = {
        "stage": "E8.5-recent-post-wake",
        "schema_version": "QMX-E8.5-RECENT-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "summary_hash": summary["summary_hash"],
        "recent_limit": summary["recent_limit"],
        "recent_count": summary["recent_count"],
        "recent_ready_count": summary["recent_ready_count"],
        "status_level": summary["status_level"],
        "entries": summary["recent_entries"],
        "recent_hash": "",
    }
    return seal(recent, "recent_hash")


def put_and_verify(owner: str, repo: str, token: str, path: str, value: dict[str, Any], hash_field: str, message: str) -> dict[str, Any]:
    if hash_field:
        value[hash_field] = ""
        value[hash_field] = stable_hash(value, hash_field)
    write: dict[str, Any] = {}
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        _, sha, _ = content_get(owner, repo, path, token)
        write = put_content(owner, repo, path, value, f"{message} attempt {attempt}", token, sha)
        attempts.append(
            {
                "attempt": attempt,
                "ok": bool(write.get("ok")),
                "status": write.get("status"),
                "error": write.get("error"),
                "commit_hash": commit_hash_from_put(write),
            }
        )
        if write.get("ok"):
            break
        time.sleep(2.0 * attempt)

    commit_hash = commit_hash_from_put(write)
    expected_hash = str(value.get(hash_field) or "")
    observed_hash = ""
    commit_raw_ok = False
    commit_attempts: list[dict[str, Any]] = []
    if commit_hash:
        for attempt in range(1, 5):
            sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"e8-5-commit-{path}-{attempt}")
            payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
            observed_hash = str(payload.get(hash_field) or "")
            commit_raw_ok = bool(sample.get("ok") and observed_hash == expected_hash)
            commit_attempts.append(
                {
                    "attempt": attempt,
                    "ok": commit_raw_ok,
                    "status": sample.get("status"),
                    "observed_hash": observed_hash,
                    "error": sample.get("error"),
                }
            )
            if commit_raw_ok:
                break
            time.sleep(1.5 * attempt)
    contents_api_verify_ok = False
    contents_api_observed_hash = ""
    if not commit_raw_ok:
        api_payload, _, _ = content_get(owner, repo, path, token)
        if isinstance(api_payload, dict):
            contents_api_observed_hash = str(api_payload.get(hash_field) or "")
            contents_api_verify_ok = bool(contents_api_observed_hash == expected_hash)
            commit_raw_ok = contents_api_verify_ok
    return {
        "path": path,
        "ok": bool(write.get("ok")),
        "status": write.get("status"),
        "error": write.get("error"),
        "commit_hash": commit_hash,
        "content_sha": content_sha_from_put(write),
        "commit_raw_ok": commit_raw_ok,
        "verification_source": "commit_raw" if commit_attempts and commit_attempts[-1].get("ok") else ("contents_api_fallback" if contents_api_verify_ok else "unverified"),
        "contents_api_verify_ok": contents_api_verify_ok,
        "contents_api_observed_hash": contents_api_observed_hash,
        "expected_hash": expected_hash,
        "observed_hash": observed_hash,
        "write_attempts": attempts,
        "commit_attempts": commit_attempts,
    }


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "E8.5-last-run",
        "schema_version": "QMX-E8.5-LAST-RUN-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "owner": result["owner"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "status_level": result["summary"]["status_level"],
        "entry_count": result["summary"]["entry_count"],
        "ready_count": result["summary"]["ready_count"],
        "recent_ready_count": result["summary"]["recent_ready_count"],
        "summary_hash": result["summary"]["summary_hash"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E8.5-last-report",
        "schema_version": "QMX-E8.5-REPORT-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "status_level": result["summary"]["status_level"],
        "status_text": result["summary"]["status_text"],
        "entry_count": result["summary"]["entry_count"],
        "ready_count": result["summary"]["ready_count"],
        "alerts": result["summary"]["alerts"],
        "summary_hash": result["summary"]["summary_hash"],
        "recent_hash": result["recent"]["recent_hash"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_e8_5_ledger_query_status_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_e8_5_ledger_query_status_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E8.5 Ledger Query Status",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- status_level: `{result['summary']['status_level']}`",
        f"- entry_count: `{result['summary']['entry_count']}`",
        f"- ready_count: `{result['summary']['ready_count']}`",
        f"- recent_ready_count: `{result['summary']['recent_ready_count']}`",
        "",
        result["summary"]["plain_summary"],
        "",
        "## Truth Boundary",
        "",
        result["truth_boundary"],
        "",
    ]
    (run_dir / "nsl_e8_5_ledger_query_status_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E8.5 ledger query and status summary")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--recent-limit", type=int, default=8)
    args = parser.parse_args()

    import os

    event = os.environ.get("GITHUB_EVENT_NAME") or "local"
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        run_id = f"nsl-e8-5-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-e8-5-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()

    ledger, _, ledger_response = content_get(args.owner, args.repo, LEDGER_PATH, token)
    if not isinstance(ledger, dict):
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "E8.5-ledger-query-status",
            "ok": False,
            "owner": run_owner(args.mode),
            "repo": args.repo,
            "ledger_read": {
                "path": LEDGER_PATH,
                "ok": False,
                "status": ledger_response.get("status"),
                "error": ledger_response.get("error"),
            },
            "evidence_level": "E8.5-ledger-query-status-missing-ledger",
            "conclusion": "E8.5 could not read the E8.4 ledger.",
            "truth_boundary": "E8.5 cannot summarize missing ledger evidence.",
        }
        write_local_outputs(run_dir, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 1

    summary = build_summary(run_id, args.mode, ledger, args.recent_limit)
    recent = build_recent(run_id, args.mode, summary)
    core_ok = bool(summary["ledger_hash_ok"] and summary["entry_hashes_ok"] and summary["entry_count"] > 0)
    result: dict[str, Any] = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "E8.5-ledger-query-status",
        "ok": core_ok,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "summary": summary,
        "recent": recent,
        "paths": {
            "runner": "scripts/nsl_e8_5_ledger_query_status.py",
            "ledger": LEDGER_PATH,
            "summary": SUMMARY_PATH,
            "recent": RECENT_PATH,
            "last_run": LAST_RUN_PATH,
            "last_report": LAST_REPORT_PATH,
        },
        "writes": {},
        "evidence_level": "E8.5-ledger-query-status-v0" if core_ok else "E8.5-ledger-query-status-partial",
        "conclusion": "E8.5 turns the E8.4 post-wake ledger into a compact queryable status summary.",
        "truth_boundary": (
            "E8.5 is a query and summary layer. It does not execute actions, does not create a tamper-proof store, "
            "and does not prove CPU-free wakefulness or autonomous evolution."
        ),
    }
    summary_write = put_and_verify(args.owner, args.repo, token, SUMMARY_PATH, summary, "summary_hash", f"E8.5 summary {run_id}")
    recent_write = put_and_verify(args.owner, args.repo, token, RECENT_PATH, recent, "recent_hash", f"E8.5 recent {run_id}")
    result["writes"]["summary"] = summary_write
    result["writes"]["recent"] = recent_write
    result["ok"] = bool(core_ok and summary_write.get("ok") and summary_write.get("commit_raw_ok") and recent_write.get("ok") and recent_write.get("commit_raw_ok"))
    result["evidence_level"] = "E8.5-ledger-query-status-v0" if result["ok"] else "E8.5-ledger-query-status-partial"
    last_run = build_last_run(result)
    last_run_write = put_and_verify(args.owner, args.repo, token, LAST_RUN_PATH, last_run, "last_run_hash", f"E8.5 last run {run_id}")
    last_report = build_report(result)
    last_report_write = put_and_verify(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, "report_hash", f"E8.5 last report {run_id}")
    result["last_run"] = last_run
    result["last_report"] = last_report
    result["writes"]["last_run"] = last_run_write
    result["writes"]["last_report"] = last_report_write
    result["ok"] = bool(result["ok"] and last_run_write.get("ok") and last_run_write.get("commit_raw_ok") and last_report_write.get("ok") and last_report_write.get("commit_raw_ok"))
    result["evidence_level"] = "E8.5-ledger-query-status-v0" if result["ok"] else "E8.5-ledger-query-status-partial"
    write_local_outputs(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "event_name": result["owner"].get("event_name"),
                "evidence_level": result["evidence_level"],
                "status_level": summary["status_level"],
                "status_text": summary["status_text"],
                "entry_count": summary["entry_count"],
                "ready_count": summary["ready_count"],
                "recent_ready_count": summary["recent_ready_count"],
                "summary_hash": summary["summary_hash"],
                "truth_boundary": result["truth_boundary"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
