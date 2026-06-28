
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_l12_hourly_self_maintenance import (
    acquire_global_lock,
    commit_hash_from_put,
    content_get,
    content_sha_from_put,
    fetch_json_url,
    gh_token,
    now,
    put_content,
    raw_url,
    release_global_lock,
    run_owner,
    stable_hash,
    wait_for_branch_release,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

E6_LAST_RUN_PATH = "states/e6-last-run.json"
E6_LAST_REPORT_PATH = "states/e6-last-report.json"
E6_BUS_STATE_PATH = "states/e6-lowfreq-vitals-bus-state.json"
E7_STATE_PATH = "states/e7-controlled-self-maintenance-state.json"
E7_PLAN_PATH = "states/e7-maintenance-plan.json"
E7_ACTIONS_PATH = "states/e7-maintenance-actions.json"
E7_LAST_RUN_PATH = "states/e7-last-run.json"
E7_LAST_REPORT_PATH = "states/e7-last-report.json"
E7_SNAPSHOT_PREFIX = "states/e7-maintenance-snapshots"

LOW_RISK_ALLOWLIST = {
    "record_vitals_health",
    "refresh_vitals_snapshot",
    "record_noop_repair",
    "record_next_wakeup_hint",
}
MEDIUM_RISK_ACTIONS = {
    "request_e6_rerun",
    "request_e5_rerun",
    "refresh_missing_remote_evidence",
}
HIGH_RISK_ACTIONS = {
    "modify_core_capsule",
    "change_workflow_schedule",
    "delete_remote_state",
    "change_permissions",
}

SOURCE_SPECS = [
    {"id": "e6_last_run", "path": E6_LAST_RUN_PATH, "hash_field": "last_run_hash", "required": True},
    {"id": "e6_last_report", "path": E6_LAST_REPORT_PATH, "hash_field": "report_hash", "required": True},
    {"id": "e6_bus_state", "path": E6_BUS_STATE_PATH, "hash_field": "state_hash", "required": True},
    {"id": "e7_previous_state", "path": E7_STATE_PATH, "hash_field": "state_hash", "required": False},
]


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def verify_hash(payload: dict[str, Any] | None, field: str) -> dict[str, Any]:
    if not field:
        return {"required": False, "ok": True, "field": "", "expected": "", "observed": ""}
    if not payload:
        return {"required": True, "ok": False, "field": field, "expected": "", "observed": ""}
    expected = str(payload.get(field) or "")
    observed = stable_hash(payload, field)
    return {
        "required": True,
        "ok": bool(expected and expected == observed),
        "field": field,
        "expected": expected,
        "observed": observed,
    }


def sample_source(owner: str, repo: str, spec: dict[str, Any]) -> dict[str, Any]:
    sample = fetch_json_url(raw_url(owner, repo, "main", spec["path"]), f"e7-{spec['id']}")
    payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else None
    return {
        "id": spec["id"],
        "path": spec["path"],
        "required": bool(spec.get("required")),
        "read_ok": bool(sample.get("ok") and payload),
        "status": sample.get("status"),
        "elapsed_ms": sample.get("elapsed_ms"),
        "hash_verify": verify_hash(payload, str(spec.get("hash_field") or "")),
        "truth_boundary_present": bool(payload and payload.get("truth_boundary")),
        "summary": summarize_payload(spec["id"], payload),
        "error": sample.get("error"),
        "payload": payload,
    }


def summarize_payload(source_id: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    if source_id == "e6_last_run":
        vitals = payload.get("vitals") or {}
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": ((payload.get("owner") or {}).get("event_name")),
            "generation": payload.get("generation"),
            "state_hash": payload.get("state_hash"),
            "bus_ok": vitals.get("bus_ok"),
            "e5_schedule_observed": vitals.get("e5_schedule_observed"),
            "global_lock_released": vitals.get("global_lock_released"),
        }
    if source_id == "e6_last_report":
        vitals = payload.get("vitals") or {}
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "generation": payload.get("generation"),
            "source_count": payload.get("source_count"),
            "bus_ok": vitals.get("bus_ok"),
            "report_hash": payload.get("report_hash"),
        }
    if source_id == "e6_bus_state":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "state_hash": payload.get("state_hash"),
            "bus_ok": ((payload.get("vitals") or {}).get("bus_ok")),
        }
    if source_id == "e7_previous_state":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "state_hash": payload.get("state_hash"),
            "maintenance_ok": payload.get("maintenance_ok"),
        }
    return {"keys": sorted(payload.keys())[:12]}


def source_by_id(samples: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    for sample in samples:
        if sample.get("id") == source_id:
            return sample
    return {}


def derive_health(samples: list[dict[str, Any]]) -> dict[str, Any]:
    required = [item for item in samples if item.get("required")]
    required_reads_ok = all(item.get("read_ok") for item in required)
    required_hashes_ok = all((item.get("hash_verify") or {}).get("ok") for item in required)
    truth_boundaries_ok = all(item.get("truth_boundary_present") for item in required)

    e6_last = source_by_id(samples, "e6_last_run").get("payload") or {}
    e6_report = source_by_id(samples, "e6_last_report").get("payload") or {}
    e6_bus = source_by_id(samples, "e6_bus_state").get("payload") or {}
    e6_vitals = e6_last.get("vitals") or {}
    e6_signals = e6_vitals.get("signals") or {}
    e6_owner = e6_last.get("owner") or {}

    e6_last_ok = bool(e6_last.get("ok") and e6_vitals.get("bus_ok"))
    e6_report_ok = bool(e6_report.get("ok") and (e6_report.get("vitals") or {}).get("bus_ok"))
    e6_bus_ok = bool((e6_bus.get("vitals") or {}).get("bus_ok"))
    e6_schedule_observed = bool(e6_owner.get("event_name") == "schedule")
    e5_schedule_observed = bool(e6_vitals.get("e5_schedule_observed") or e6_signals.get("E5_NATURAL_SCHEDULE_OBSERVED"))
    global_lock_released = bool(e6_vitals.get("global_lock_released") or e6_signals.get("GLOBAL_RUNTIME_LOCK_RELEASED"))
    logic_ready = bool(e6_vitals.get("logic_ready"))

    maintenance_ready = bool(
        required_reads_ok
        and required_hashes_ok
        and truth_boundaries_ok
        and e6_last_ok
        and e6_report_ok
        and e6_bus_ok
        and e5_schedule_observed
        and global_lock_released
        and logic_ready
    )
    return {
        "required_reads_ok": required_reads_ok,
        "required_hashes_ok": required_hashes_ok,
        "truth_boundaries_ok": truth_boundaries_ok,
        "e6_last_ok": e6_last_ok,
        "e6_report_ok": e6_report_ok,
        "e6_bus_state_ok": e6_bus_ok,
        "e6_schedule_observed": e6_schedule_observed,
        "e5_schedule_observed": e5_schedule_observed,
        "global_lock_released": global_lock_released,
        "logic_ready": logic_ready,
        "maintenance_ready": maintenance_ready,
        "signals": {
            "CONTROLLED_SELF_MAINTENANCE_READY": maintenance_ready,
            "E6_VITALS_HEALTHY": bool(e6_last_ok and e6_report_ok and e6_bus_ok),
            "NATURAL_WAKE_CHAIN_OBSERVED": bool(e6_schedule_observed and e5_schedule_observed),
            "NO_CORE_MUTATION_ALLOWED": True,
            "ONLY_LOW_RISK_ACTIONS_EXECUTABLE": True,
        },
    }


def build_plan(run_id: str, mode: str, generation: int, samples: list[dict[str, Any]], health: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    if health["maintenance_ready"]:
        actions.extend(
            [
                {
                    "id": "e7-low-001",
                    "action": "record_vitals_health",
                    "risk": "low",
                    "auto_execute": True,
                    "reason": "E6 vitals bus is healthy and hash-verified.",
                    "allowed_by": "LOW_RISK_ALLOWLIST",
                },
                {
                    "id": "e7-low-002",
                    "action": "refresh_vitals_snapshot",
                    "risk": "low",
                    "auto_execute": True,
                    "reason": "Write an auditable E7 snapshot so future wakeups can read one maintenance state.",
                    "allowed_by": "LOW_RISK_ALLOWLIST",
                },
                {
                    "id": "e7-low-003",
                    "action": "record_noop_repair",
                    "risk": "low",
                    "auto_execute": True,
                    "reason": "No repair is required; record a no-op repair receipt instead of changing core state.",
                    "allowed_by": "LOW_RISK_ALLOWLIST",
                },
                {
                    "id": "e7-low-004",
                    "action": "record_next_wakeup_hint",
                    "risk": "low",
                    "auto_execute": True,
                    "reason": "Record that the next E7 window may continue from the latest E6 generation.",
                    "allowed_by": "LOW_RISK_ALLOWLIST",
                },
            ]
        )
    else:
        actions.append(
            {
                "id": "e7-medium-001",
                "action": "request_e6_rerun",
                "risk": "medium",
                "auto_execute": False,
                "reason": "E6 vitals are not fully healthy; request a controlled rerun proposal instead of mutating state.",
                "allowed_by": "MEDIUM_RISK_REVIEW_REQUIRED",
            }
        )

    blocked_actions = [
        {
            "action": action,
            "risk": "high",
            "auto_execute": False,
            "reason": "E7 is not allowed to modify core capsules, schedules, permissions, or delete remote state.",
        }
        for action in sorted(HIGH_RISK_ACTIONS)
    ]
    low_risk_auto_count = sum(1 for item in actions if item.get("risk") == "low" and item.get("auto_execute"))
    medium_review_count = sum(1 for item in actions if item.get("risk") == "medium")
    plan = {
        "stage": "E7-maintenance-plan",
        "schema_version": "QMX-E7-PLAN-0.1",
        "created_at": now(),
        "run_id": run_id,
        "generation": generation,
        "owner": run_owner(mode),
        "source_summary": [
            {
                "id": item["id"],
                "path": item["path"],
                "read_ok": item["read_ok"],
                "hash_verify": item["hash_verify"],
                "summary": item["summary"],
            }
            for item in samples
        ],
        "health": health,
        "policy": {
            "low_risk_allowlist": sorted(LOW_RISK_ALLOWLIST),
            "medium_risk_review_required": sorted(MEDIUM_RISK_ACTIONS),
            "high_risk_blocked": sorted(HIGH_RISK_ACTIONS),
            "direct_core_mutation_allowed": False,
            "direct_workflow_mutation_allowed": False,
            "direct_permission_mutation_allowed": False,
        },
        "actions": actions,
        "blocked_actions": blocked_actions,
        "low_risk_auto_count": low_risk_auto_count,
        "medium_review_count": medium_review_count,
        "high_risk_blocked_count": len(blocked_actions),
        "plan_ok": bool(health["maintenance_ready"] and low_risk_auto_count > 0),
        "truth_boundary": (
            "E7 plans only controlled low-risk maintenance from E6 vitals. It does not modify core capsules, code, schedules, permissions, "
            "or prove CPU-free network self-execution."
        ),
        "plan_hash": "",
    }
    return seal(plan, "plan_hash")


def execute_low_risk_actions(run_id: str, mode: str, plan: dict[str, Any]) -> dict[str, Any]:
    receipts: list[dict[str, Any]] = []
    for action in plan.get("actions") or []:
        name = str(action.get("action") or "")
        risk = str(action.get("risk") or "")
        auto_execute = bool(action.get("auto_execute"))
        allowed = bool(name in LOW_RISK_ALLOWLIST and risk == "low" and auto_execute)
        receipt = {
            "action_id": action.get("id"),
            "action": name,
            "risk": risk,
            "auto_execute": auto_execute,
            "executed": allowed,
            "result": "executed_low_risk_record_only" if allowed else "not_executed",
            "reason": action.get("reason"),
            "created_at": now(),
        }
        receipts.append(receipt)
    actions_payload = {
        "stage": "E7-maintenance-actions",
        "schema_version": "QMX-E7-ACTIONS-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "plan_hash": plan.get("plan_hash"),
        "receipts": receipts,
        "executed_count": sum(1 for item in receipts if item.get("executed")),
        "blocked_count": len(plan.get("blocked_actions") or []),
        "medium_review_count": int(plan.get("medium_review_count") or 0),
        "all_executed_actions_low_risk": all((not item.get("executed")) or item.get("risk") == "low" for item in receipts),
        "core_mutation_performed": False,
        "workflow_mutation_performed": False,
        "permission_mutation_performed": False,
        "truth_boundary": (
            "E7 action execution is record-only low-risk maintenance. It writes health receipts and no-op repair records, not core code or permission changes."
        ),
        "actions_hash": "",
    }
    return seal(actions_payload, "actions_hash")


def build_state(
    run_id: str,
    mode: str,
    generation: int,
    health: dict[str, Any],
    plan: dict[str, Any],
    actions: dict[str, Any],
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    state = {
        "stage": "E7-controlled-self-maintenance-state",
        "schema_version": "QMX-E7-STATE-0.1",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "owner": run_owner(mode),
        "health": health,
        "plan_hash": plan.get("plan_hash"),
        "actions_hash": actions.get("actions_hash"),
        "maintenance_ok": bool(
            health.get("maintenance_ready")
            and plan.get("plan_ok")
            and actions.get("all_executed_actions_low_risk")
            and not actions.get("core_mutation_performed")
            and not actions.get("workflow_mutation_performed")
            and not actions.get("permission_mutation_performed")
        ),
        "executed_count": actions.get("executed_count"),
        "blocked_count": actions.get("blocked_count"),
        "previous": {
            "generation": (previous_state or {}).get("generation"),
            "state_hash": (previous_state or {}).get("state_hash"),
            "run_id": (previous_state or {}).get("run_id"),
        },
        "conclusion": "E7 connected E6 vitals to controlled low-risk self-maintenance receipts.",
        "truth_boundary": (
            "E7 is controlled low-risk self-maintenance executed by local or GitHub Actions CPU. "
            "It does not prove autonomous self-modification, CPU-free network execution, or digital life."
        ),
        "state_hash": "",
    }
    return seal(state, "state_hash")


def put_and_verify(owner: str, repo: str, token: str, path: str, value: dict[str, Any], hash_field: str, message: str) -> dict[str, Any]:
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
            sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"e7-commit-{path}-{attempt}")
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
    return {
        "path": path,
        "ok": bool(write.get("ok")),
        "status": write.get("status"),
        "error": write.get("error"),
        "commit_hash": commit_hash,
        "content_sha": content_sha_from_put(write),
        "commit_raw_ok": commit_raw_ok,
        "expected_hash": expected_hash,
        "observed_hash": observed_hash,
        "write_attempts": attempts,
        "commit_attempts": commit_attempts,
    }


def snapshot_path(run_id: str) -> str:
    return f"{E7_SNAPSHOT_PREFIX}/{run_id}.json"


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "E7-last-run",
        "schema_version": "QMX-E7-LAST-RUN-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "owner": result["owner"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "generation": result["generation"],
        "maintenance_ok": result["state"]["maintenance_ok"],
        "executed_count": result["actions"]["executed_count"],
        "blocked_count": result["actions"]["blocked_count"],
        "state_hash": result["state"]["state_hash"],
        "plan_hash": result["plan"]["plan_hash"],
        "actions_hash": result["actions"]["actions_hash"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_last_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E7-last-report",
        "schema_version": "QMX-E7-REPORT-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "generation": result["generation"],
        "health": result["health"],
        "remote_paths": result["paths"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_e7_vitals_self_maintenance_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_e7_vitals_self_maintenance_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E7 Controlled Vitals Self-Maintenance",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- maintenance_ok: `{result['state']['maintenance_ok']}`",
        f"- executed_count: `{result['actions']['executed_count']}`",
        f"- blocked_count: `{result['actions']['blocked_count']}`",
        f"- state_hash: `{result['state']['state_hash']}`",
        "",
        "## Health",
        "",
    ]
    for key, value in result["health"].items():
        if key != "signals":
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Truth Boundary", "", result["truth_boundary"], ""])
    (run_dir / "nsl_e7_vitals_self_maintenance_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E7 controlled low-risk self-maintenance from E6 vitals")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--global-lock-ttl-seconds", type=int, default=900)
    parser.add_argument("--raw-timeout", type=int, default=180)
    parser.add_argument("--raw-interval", type=float, default=6.0)
    args = parser.parse_args()

    import os

    event = os.environ.get("GITHUB_EVENT_NAME") or "local"
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        run_id = f"nsl-e7-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-e7-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()
    global_release: dict[str, Any] = {}
    try:
        samples = [sample_source(args.owner, args.repo, spec) for spec in SOURCE_SPECS]
        previous_state = source_by_id(samples, "e7_previous_state").get("payload") or {}
        generation = int((previous_state or {}).get("generation") or 0) + 1
        health = derive_health(samples)

        global_lock = acquire_global_lock(args.owner, args.repo, token, run_id, args.mode, args.global_lock_ttl_seconds)
        if global_lock.get("skipped"):
            result = {
                "run_id": run_id,
                "created_at": now(),
                "stage": "E7-controlled-vitals-self-maintenance",
                "ok": True,
                "skipped": True,
                "reason": "active_global_lock",
                "owner": run_owner(args.mode),
                "evidence_level": "E7-controlled-self-maintenance-skipped",
                "truth_boundary": "E7 skipped because another controlled runtime window is active.",
            }
            write_local_outputs(run_dir, {**result, "health": health, "state": {"maintenance_ok": False, "state_hash": ""}, "actions": {"executed_count": 0, "blocked_count": 0}})
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0

        plan = build_plan(run_id, args.mode, generation, samples, health)
        actions = execute_low_risk_actions(run_id, args.mode, plan)
        state = build_state(run_id, args.mode, generation, health, plan, actions, previous_state)
        snap_path = snapshot_path(run_id)

        plan_write = put_and_verify(args.owner, args.repo, token, E7_PLAN_PATH, plan, "plan_hash", f"E7 maintenance plan {run_id}")
        actions_write = put_and_verify(args.owner, args.repo, token, E7_ACTIONS_PATH, actions, "actions_hash", f"E7 maintenance actions {run_id}")
        state_write = put_and_verify(args.owner, args.repo, token, E7_STATE_PATH, state, "state_hash", f"E7 maintenance state {run_id}")
        snapshot_write = put_and_verify(args.owner, args.repo, token, snap_path, state, "state_hash", f"E7 maintenance snapshot {run_id}")

        expected_release = [
            {"path": E7_PLAN_PATH, "hash_field": "plan_hash", "hash_value": plan["plan_hash"]},
            {"path": E7_ACTIONS_PATH, "hash_field": "actions_hash", "hash_value": actions["actions_hash"]},
            {"path": E7_STATE_PATH, "hash_field": "state_hash", "hash_value": state["state_hash"]},
            {"path": snap_path, "hash_field": "state_hash", "hash_value": state["state_hash"]},
        ]
        branch_release = wait_for_branch_release(args.owner, args.repo, expected_release, args.raw_timeout, args.raw_interval)
        core_ok = bool(
            state["maintenance_ok"]
            and plan_write.get("ok")
            and plan_write.get("commit_raw_ok")
            and actions_write.get("ok")
            and actions_write.get("commit_raw_ok")
            and state_write.get("ok")
            and state_write.get("commit_raw_ok")
            and snapshot_write.get("ok")
            and snapshot_write.get("commit_raw_ok")
            and branch_release.get("ok")
        )
        result: dict[str, Any] = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "E7-controlled-vitals-self-maintenance",
            "ok": core_ok,
            "owner": run_owner(args.mode),
            "repo": args.repo,
            "generation": generation,
            "samples": samples,
            "health": health,
            "plan": plan,
            "actions": actions,
            "state": state,
            "paths": {
                "workflow": ".github/workflows/nsl-e7-vitals-self-maintenance.yml",
                "runner": "scripts/nsl_e7_vitals_self_maintenance.py",
                "plan": E7_PLAN_PATH,
                "actions": E7_ACTIONS_PATH,
                "state": E7_STATE_PATH,
                "snapshot": snap_path,
                "last_run": E7_LAST_RUN_PATH,
                "last_report": E7_LAST_REPORT_PATH,
            },
            "writes": {
                "global_lock_acquire": global_lock.get("write"),
                "plan": plan_write,
                "actions": actions_write,
                "state": state_write,
                "snapshot": snapshot_write,
            },
            "verification": {
                "branch_raw_release": branch_release,
                "plan_write_ok": plan_write.get("ok"),
                "actions_write_ok": actions_write.get("ok"),
                "state_write_ok": state_write.get("ok"),
                "snapshot_write_ok": snapshot_write.get("ok"),
            },
            "evidence_level": "E7-controlled-low-risk-self-maintenance-v0" if core_ok else "E7-controlled-low-risk-self-maintenance-partial",
            "conclusion": (
                "E7 connected E6 low-frequency vitals to controlled low-risk self-maintenance receipts and remote writeback."
                if core_ok
                else "E7 ran, but one or more health, policy, writeback, or Raw release checks did not pass."
            ),
            "truth_boundary": (
                "E7 is controlled low-risk self-maintenance executed by local or GitHub Actions CPU. "
                "It records health and no-op repair receipts only; it does not modify core code, workflows, permissions, or prove CPU-free network self-execution."
            ),
        }
        last_run = build_last_run(result)
        last_run_write = put_and_verify(args.owner, args.repo, token, E7_LAST_RUN_PATH, last_run, "last_run_hash", f"E7 last run {run_id}")
        last_report = build_last_report(result)
        last_report_write = put_and_verify(args.owner, args.repo, token, E7_LAST_REPORT_PATH, last_report, "report_hash", f"E7 last report {run_id}")
        global_release = release_global_lock(args.owner, args.repo, token, run_id, result["ok"])
        result["writes"]["last_run"] = last_run_write
        result["writes"]["last_report"] = last_report_write
        result["writes"]["global_lock_release"] = global_release
        result["ok"] = bool(
            core_ok
            and last_run_write.get("ok")
            and last_run_write.get("commit_raw_ok")
            and last_report_write.get("ok")
            and last_report_write.get("commit_raw_ok")
            and global_release.get("ok")
        )
        result["evidence_level"] = "E7-controlled-low-risk-self-maintenance-v0" if result["ok"] else "E7-controlled-low-risk-self-maintenance-partial"
        write_local_outputs(run_dir, result)
        print(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "ok": result["ok"],
                    "event_name": result["owner"].get("event_name"),
                    "evidence_level": result["evidence_level"],
                    "generation": result["generation"],
                    "maintenance_ok": result["state"]["maintenance_ok"],
                    "executed_count": result["actions"]["executed_count"],
                    "blocked_count": result["actions"]["blocked_count"],
                    "state_hash": result["state"]["state_hash"],
                    "branch_raw_release_ok": result["verification"]["branch_raw_release"].get("ok"),
                    "truth_boundary": result["truth_boundary"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0 if result["ok"] else 1
    except Exception:
        release_global_lock(args.owner, args.repo, token, run_id, False)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
