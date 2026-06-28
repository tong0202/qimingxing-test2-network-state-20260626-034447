from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_l12_hourly_self_maintenance import (
    api_request,
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
    wait_for_branch_release,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

SELF_CHECK_PATH = "states/e8-2-post-wake-self-check.json"
PLAN_PATH = "states/e8-2-maintenance-plan.json"
ACTIONS_PATH = "states/e8-2-maintenance-actions.json"
STATE_PATH = "states/e8-2-post-wake-state.json"
LAST_RUN_PATH = "states/e8-2-last-run.json"
LAST_REPORT_PATH = "states/e8-2-last-report.json"
SNAPSHOT_PREFIX = "states/e8-2-post-wake-snapshots"
LEDGER_PATH = "states/e8-4-post-wake-ledger.json"
LEDGER_REPORT_PATH = "states/e8-4-last-ledger-report.json"

LOW_RISK_ALLOWLIST = {
    "record_post_wake_chain_health",
    "record_external_clock_status",
    "refresh_network_body_checkpoint",
    "record_next_wakeup_hint",
}

MEDIUM_RISK_QUEUE = {
    "configure_cloudflare_worker_cron",
    "add_second_clock_source",
    "increase_schedule_observation_window",
}

HIGH_RISK_BLOCKLIST = {
    "modify_core_code",
    "change_workflow_permissions",
    "delete_remote_state",
    "store_secret_in_repo",
    "unreviewed_self_mutation",
}

SOURCE_SPECS: list[dict[str, Any]] = [
    {"id": "e7_2_last_run", "path": "states/e7-2-last-run.json", "hash_field": "last_run_hash", "required": True},
    {"id": "e7_2_bridge_state", "path": "states/e7-2-wake-bridge-state.json", "hash_field": "state_hash", "required": True},
    {"id": "e7_last_run", "path": "states/e7-last-run.json", "hash_field": "last_run_hash", "required": True},
    {"id": "e7_last_report", "path": "states/e7-last-report.json", "hash_field": "report_hash", "required": True},
    {"id": "e8_last_run", "path": "states/e8-last-run.json", "hash_field": "last_run_hash", "required": True},
    {"id": "e8_protocol", "path": "states/e8-network-body-protocol.json", "hash_field": "protocol_hash", "required": True},
    {"id": "e6_last_run", "path": "states/e6-last-run.json", "hash_field": "last_run_hash", "required": False},
    {"id": "previous_e8_2_state", "path": STATE_PATH, "hash_field": "state_hash", "required": False, "prefer_api": True},
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


def owner_event(payload: dict[str, Any]) -> str:
    return str(payload.get("owner_event_name") or ((payload.get("owner") or {}).get("event_name") or ""))


def summarize_payload(source_id: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    if source_id == "e7_2_last_run":
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": owner_event(payload),
            "validation_ok": payload.get("validation_ok"),
            "dispatch_ok": payload.get("dispatch_ok"),
            "receiver_ok": payload.get("receiver_ok"),
            "receiver_event": payload.get("receiver_event"),
            "receiver_conclusion": payload.get("receiver_conclusion"),
        }
    if source_id == "e7_2_bridge_state":
        return {
            "run_id": payload.get("run_id"),
            "bridge_ok": payload.get("bridge_ok"),
            "event_name": owner_event(payload),
            "validation_ok": payload.get("validation_ok"),
            "dispatch_ok": payload.get("dispatch_ok"),
            "receiver_ok": payload.get("receiver_ok"),
            "receiver_workflow_run_id": payload.get("receiver_workflow_run_id"),
        }
    if source_id in {"e7_last_run", "e7_last_report"}:
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": owner_event(payload),
            "generation": payload.get("generation"),
            "maintenance_ok": payload.get("maintenance_ok"),
            "executed_count": payload.get("executed_count"),
            "blocked_count": payload.get("blocked_count"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id in {"e8_last_run", "e8_protocol"}:
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "generation": payload.get("generation"),
            "network_body_ready": payload.get("network_body_ready"),
            "protocol_hash": payload.get("protocol_hash"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id == "e6_last_run":
        vitals = payload.get("vitals") or {}
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": owner_event(payload),
            "generation": payload.get("generation"),
            "bus_ok": vitals.get("bus_ok"),
            "e5_schedule_observed": vitals.get("e5_schedule_observed"),
            "logic_ready": vitals.get("logic_ready"),
        }
    if source_id == "previous_e8_2_state":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "post_wake_ready": payload.get("post_wake_ready"),
            "state_hash": payload.get("state_hash"),
        }
    return {"keys": sorted(payload.keys())[:12]}


def sample_source(owner: str, repo: str, spec: dict[str, Any], token: str) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    sample: dict[str, Any] = {}
    source = "branch_raw"
    if spec.get("prefer_api"):
        payload, _, api_response = content_get(owner, repo, spec["path"], token)
        source = "contents_api_fallback"
        if payload:
            sample = {
                "ok": True,
                "status": api_response.get("status"),
                "elapsed_ms": api_response.get("elapsed_ms"),
                "error": "",
            }
    if not payload:
        sample = fetch_json_url(raw_url(owner, repo, "main", spec["path"]), f"e8-2-{spec['id']}")
        payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else None
        source = "branch_raw"
    if not payload and not spec.get("prefer_api"):
        payload, _, api_response = content_get(owner, repo, spec["path"], token)
        source = "contents_api_fallback"
        if payload:
            sample = {
                "ok": True,
                "status": api_response.get("status"),
                "elapsed_ms": api_response.get("elapsed_ms"),
                "error": "",
            }
    return {
        "id": spec["id"],
        "path": spec["path"],
        "required": bool(spec.get("required")),
        "source": source,
        "read_ok": bool(sample.get("ok") and payload),
        "status": sample.get("status"),
        "elapsed_ms": sample.get("elapsed_ms"),
        "hash_verify": verify_hash(payload, str(spec.get("hash_field") or "")),
        "truth_boundary_present": bool(payload and payload.get("truth_boundary")),
        "summary": summarize_payload(spec["id"], payload),
        "error": sample.get("error"),
        "payload": payload,
    }


def source_by_id(samples: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    for sample in samples:
        if sample.get("id") == source_id:
            return sample
    return {}


def payload(samples: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    item = source_by_id(samples, source_id)
    return item.get("payload") if isinstance(item.get("payload"), dict) else {}


def derive_post_wake_health(samples: list[dict[str, Any]]) -> dict[str, Any]:
    required = [item for item in samples if item.get("required")]
    required_reads_ok = all(item.get("read_ok") for item in required)
    required_hashes_ok = all((item.get("hash_verify") or {}).get("ok") for item in required)
    truth_boundaries_ok = all(item.get("truth_boundary_present") for item in required)

    e7_2_last = payload(samples, "e7_2_last_run")
    bridge = payload(samples, "e7_2_bridge_state")
    e7 = payload(samples, "e7_last_run")
    e7_report = payload(samples, "e7_last_report")
    e8 = payload(samples, "e8_last_run")
    e8_protocol = payload(samples, "e8_protocol")
    e6 = payload(samples, "e6_last_run")
    e6_vitals = e6.get("vitals") or {}

    bridge_chain_ok = bool(
        e7_2_last.get("ok")
        and e7_2_last.get("validation_ok")
        and e7_2_last.get("dispatch_ok")
        and e7_2_last.get("receiver_ok")
        and e7_2_last.get("receiver_event") == "repository_dispatch"
        and e7_2_last.get("receiver_conclusion") == "success"
        and bridge.get("bridge_ok")
    )
    e7_latest_event = owner_event(e7)
    e7_current_health_ok = bool(
        e7.get("ok")
        and e7.get("maintenance_ok")
        and int(e7.get("executed_count") or 0) >= 4
        and int(e7.get("blocked_count") or 0) >= 4
    )
    e7_latest_is_repository_dispatch = e7_latest_event == "repository_dispatch"
    e7_writeback_ok = bool(
        e7_current_health_ok
        and (e7_latest_is_repository_dispatch or bridge_chain_ok)
    )
    e7_report_ok = bool(e7_report.get("ok") and e7_report.get("truth_boundary"))
    network_body_ok = bool(e8.get("ok") and e8.get("network_body_ready") and e8_protocol.get("network_body_ready"))
    lowfreq_vitals_context_ok = bool(e6.get("ok") and e6_vitals.get("bus_ok"))
    external_clock_pending = True

    post_wake_ready = bool(
        required_reads_ok
        and required_hashes_ok
        and truth_boundaries_ok
        and bridge_chain_ok
        and e7_writeback_ok
        and e7_report_ok
        and network_body_ok
    )
    return {
        "required_reads_ok": required_reads_ok,
        "required_hashes_ok": required_hashes_ok,
        "truth_boundaries_ok": truth_boundaries_ok,
        "bridge_chain_ok": bridge_chain_ok,
        "e7_current_health_ok": e7_current_health_ok,
        "e7_latest_event_name": e7_latest_event,
        "e7_latest_is_repository_dispatch": e7_latest_is_repository_dispatch,
        "e7_latest_overwritten_by_schedule": bool(e7_latest_event == "schedule" and bridge_chain_ok),
        "e7_writeback_ok": e7_writeback_ok,
        "e7_report_ok": e7_report_ok,
        "network_body_ok": network_body_ok,
        "lowfreq_vitals_context_ok": lowfreq_vitals_context_ok,
        "external_clock_pending": external_clock_pending,
        "post_wake_ready": post_wake_ready,
        "signals": {
            "POST_WAKE_SELF_CHECK_READY": post_wake_ready,
            "HTTP_BRIDGE_WAKE_CHAIN_HEALTHY": bridge_chain_ok,
            "E7_REPOSITORY_DISPATCH_WRITEBACK_OK": e7_writeback_ok,
            "E7_LATEST_OVERWRITTEN_BY_SCHEDULE": bool(e7_latest_event == "schedule" and bridge_chain_ok),
            "NETWORK_BODY_PROTOCOL_PRESENT": network_body_ok,
            "THIRD_PARTY_CLOCK_STILL_PENDING": external_clock_pending,
            "NO_SECRET_IN_REPO_REQUIRED": True,
            "NO_CORE_MUTATION_ALLOWED": True,
        },
    }


def build_self_check(run_id: str, mode: str, generation: int, samples: list[dict[str, Any]], health: dict[str, Any]) -> dict[str, Any]:
    self_check = {
        "stage": "E8.2-post-wake-self-check",
        "schema_version": "QMX-E8.2-SELF-CHECK-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "health": health,
        "sources": [
            {
                "id": item["id"],
                "path": item["path"],
                "source": item["source"],
                "read_ok": item["read_ok"],
                "hash_ok": (item.get("hash_verify") or {}).get("ok"),
                "truth_boundary_present": item.get("truth_boundary_present"),
                "summary": item.get("summary"),
            }
            for item in samples
        ],
        "plain_chinese_meaning": (
            "外部唤醒后，系统自动读取桥接器、E7 自维护和 E8 网络体协议证据，"
            "确认唤醒链、写回链和真实边界是否健康。"
        ),
        "truth_boundary": (
            "E8.2 is a post-wake self-check and controlled maintenance receipt. It does not perform core mutation, "
            "does not store secrets, and does not prove CPU-free self-wakefulness."
        ),
        "self_check_hash": "",
    }
    return seal(self_check, "self_check_hash")


def build_plan(run_id: str, mode: str, generation: int, health: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = [
        {
            "id": "e8-2-low-001",
            "action": "record_post_wake_chain_health",
            "risk": "low",
            "auto_execute": True,
            "allowed_by": "LOW_RISK_ALLOWLIST",
            "reason": "Record whether E7.3a -> E7.2 -> E7 writeback chain is healthy.",
        },
        {
            "id": "e8-2-low-002",
            "action": "record_external_clock_status",
            "risk": "low",
            "auto_execute": True,
            "allowed_by": "LOW_RISK_ALLOWLIST",
            "reason": "Cloudflare is intentionally skipped for now; record it as pending without blocking mainline.",
        },
        {
            "id": "e8-2-low-003",
            "action": "refresh_network_body_checkpoint",
            "risk": "low",
            "auto_execute": True,
            "allowed_by": "LOW_RISK_ALLOWLIST",
            "reason": "Refresh a post-wake state checkpoint for later recovery and audit.",
        },
        {
            "id": "e8-2-low-004",
            "action": "record_next_wakeup_hint",
            "risk": "low",
            "auto_execute": True,
            "allowed_by": "LOW_RISK_ALLOWLIST",
            "reason": "Keep the next mainline visible after context compression.",
        },
    ]
    actions.extend(
        [
            {
                "id": "e8-2-medium-001",
                "action": "configure_cloudflare_worker_cron",
                "risk": "medium",
                "auto_execute": False,
                "queue_for_review": True,
                "reason": "Requires external account setup and a secret token; cannot be done safely by writing repo files.",
            },
            {
                "id": "e8-2-high-001",
                "action": "store_secret_in_repo",
                "risk": "high",
                "auto_execute": False,
                "blocked": True,
                "reason": "Secrets must never be written to repo, docs, logs, or chat.",
            },
            {
                "id": "e8-2-high-002",
                "action": "unreviewed_self_mutation",
                "risk": "high",
                "auto_execute": False,
                "blocked": True,
                "reason": "Current safety model permits low-risk record-only maintenance only.",
            },
        ]
    )
    plan = {
        "stage": "E8.2-maintenance-plan",
        "schema_version": "QMX-E8.2-PLAN-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "post_wake_ready": health["post_wake_ready"],
        "allowed_low_risk_actions": sorted(LOW_RISK_ALLOWLIST),
        "queued_medium_risk_actions": sorted(MEDIUM_RISK_QUEUE),
        "blocked_high_risk_actions": sorted(HIGH_RISK_BLOCKLIST),
        "actions": actions,
        "completion_standard": [
            "Bridge chain evidence is readable and hash verified.",
            "E7 repository_dispatch writeback is ok=true.",
            "Only low-risk record actions are auto-executed.",
            "Cloudflare remains a pending enhancement, not a blocker.",
        ],
        "truth_boundary": (
            "This plan can record and classify post-wake maintenance evidence. It cannot configure external accounts "
            "or modify high-risk core behavior without review."
        ),
        "plan_hash": "",
    }
    return seal(plan, "plan_hash")


def build_actions(run_id: str, mode: str, generation: int, plan: dict[str, Any], self_check: dict[str, Any]) -> dict[str, Any]:
    executed = []
    queued = []
    blocked = []
    for action in plan["actions"]:
        if action.get("risk") == "low" and action.get("auto_execute") and action.get("action") in LOW_RISK_ALLOWLIST:
            executed.append({**action, "executed": True, "result": "recorded"})
        elif action.get("risk") == "medium":
            queued.append({**action, "executed": False, "result": "queued_for_human_or_later_controlled_path"})
        else:
            blocked.append({**action, "executed": False, "result": "blocked_by_policy"})
    actions = {
        "stage": "E8.2-maintenance-actions",
        "schema_version": "QMX-E8.2-ACTIONS-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "self_check_hash": self_check["self_check_hash"],
        "plan_hash": plan["plan_hash"],
        "executed_count": len(executed),
        "queued_count": len(queued),
        "blocked_count": len(blocked),
        "executed": executed,
        "queued": queued,
        "blocked": blocked,
        "actions_ok": len(executed) == 4 and len(blocked) >= 2,
        "truth_boundary": (
            "E8.2 action execution means writing audit receipts only. It does not mutate core code, workflows, permissions, or secrets."
        ),
        "actions_hash": "",
    }
    return seal(actions, "actions_hash")


def build_state(
    run_id: str,
    mode: str,
    generation: int,
    self_check: dict[str, Any],
    plan: dict[str, Any],
    actions: dict[str, Any],
) -> dict[str, Any]:
    state = {
        "stage": "E8.2-post-wake-state",
        "schema_version": "QMX-E8.2-STATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "post_wake_ready": self_check["health"]["post_wake_ready"],
        "self_check_hash": self_check["self_check_hash"],
        "plan_hash": plan["plan_hash"],
        "actions_hash": actions["actions_hash"],
        "executed_count": actions["executed_count"],
        "queued_count": actions["queued_count"],
        "blocked_count": actions["blocked_count"],
        "next_mainline": "E8.3: make post-wake self-check run automatically after every external wake path and keep third-party clock as optional hardening.",
        "truth_boundary": (
            "E8.2 strengthens the post-wake audit and low-risk self-maintenance loop. It is not autonomous evolution, "
            "not CPU-free execution, and not a completed free-floating network body."
        ),
        "state_hash": "",
    }
    return seal(state, "state_hash")


def snapshot_path(run_id: str) -> str:
    return f"{SNAPSHOT_PREFIX}/{run_id}.json"


def list_snapshot_paths(owner: str, repo: str, token: str) -> dict[str, Any]:
    response = api_request(owner, repo, "GET", f"/contents/{SNAPSHOT_PREFIX}?ref=main", token)
    payload_out = response.get("payload")
    paths: list[str] = []
    if response.get("ok") and isinstance(payload_out, list):
        for item in payload_out:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "")
            if item.get("type") == "file" and path.endswith(".json"):
                paths.append(path)
    return {
        "ok": bool(response.get("ok") and isinstance(payload_out, list)),
        "status": response.get("status"),
        "error": response.get("error"),
        "paths": sorted(paths),
        "count": len(paths),
    }


def compact_health(health: dict[str, Any]) -> dict[str, Any]:
    return {
        "post_wake_ready": health.get("post_wake_ready"),
        "bridge_chain_ok": health.get("bridge_chain_ok"),
        "e7_current_health_ok": health.get("e7_current_health_ok"),
        "e7_latest_event_name": health.get("e7_latest_event_name"),
        "e7_latest_overwritten_by_schedule": health.get("e7_latest_overwritten_by_schedule"),
        "network_body_ok": health.get("network_body_ok"),
        "external_clock_pending": health.get("external_clock_pending"),
    }


def build_ledger_entry(
    run_id: str,
    created_at: str,
    owner: dict[str, Any],
    generation: int,
    post_wake_ready: bool,
    state_hash: str,
    self_check_hash: str,
    plan_hash: str,
    actions_hash: str,
    snapshot_path_value: str,
    snapshot_hash: str,
    health: dict[str, Any],
    source: str,
    ok: bool | None = None,
    last_run_hash: str = "",
    report_hash: str = "",
) -> dict[str, Any]:
    entry = {
        "schema_version": "QMX-E8.4-LEDGER-ENTRY-0.1",
        "run_id": run_id,
        "created_at": created_at,
        "source": source,
        "ok": ok,
        "post_wake_ready": post_wake_ready,
        "generation": generation,
        "owner": {
            "workflow": owner.get("workflow"),
            "event_name": owner.get("event_name"),
            "run_id": owner.get("run_id"),
            "run_attempt": owner.get("run_attempt"),
            "actor": owner.get("actor"),
            "sha": owner.get("sha"),
        },
        "state_hash": state_hash,
        "self_check_hash": self_check_hash,
        "plan_hash": plan_hash,
        "actions_hash": actions_hash,
        "last_run_hash": last_run_hash,
        "report_hash": report_hash,
        "snapshot_path": snapshot_path_value,
        "snapshot_hash": snapshot_hash,
        "health": compact_health(health),
        "entry_hash": "",
    }
    return seal(entry, "entry_hash")


def ledger_entry_from_snapshot(snapshot: dict[str, Any], path: str) -> dict[str, Any] | None:
    state = snapshot.get("state") if isinstance(snapshot.get("state"), dict) else {}
    self_check = snapshot.get("self_check") if isinstance(snapshot.get("self_check"), dict) else {}
    plan = snapshot.get("plan") if isinstance(snapshot.get("plan"), dict) else {}
    actions = snapshot.get("actions") if isinstance(snapshot.get("actions"), dict) else {}
    if not state:
        return None
    run_id = str(state.get("run_id") or snapshot.get("run_id") or "")
    if not run_id:
        return None
    return build_ledger_entry(
        run_id=run_id,
        created_at=str(state.get("created_at") or snapshot.get("created_at") or ""),
        owner=state.get("owner") if isinstance(state.get("owner"), dict) else {},
        generation=int(state.get("generation") or snapshot.get("generation") or 0),
        post_wake_ready=bool(state.get("post_wake_ready")),
        state_hash=str(state.get("state_hash") or ""),
        self_check_hash=str(state.get("self_check_hash") or self_check.get("self_check_hash") or ""),
        plan_hash=str(state.get("plan_hash") or plan.get("plan_hash") or ""),
        actions_hash=str(state.get("actions_hash") or actions.get("actions_hash") or ""),
        snapshot_path_value=path,
        snapshot_hash=str(snapshot.get("snapshot_hash") or ""),
        health=self_check.get("health") if isinstance(self_check.get("health"), dict) else {},
        source="snapshot_backfill",
        ok=None,
    )


def ledger_entry_from_result(
    result: dict[str, Any],
    last_run: dict[str, Any],
    last_report: dict[str, Any],
    snap_path: str,
) -> dict[str, Any]:
    return build_ledger_entry(
        run_id=result["run_id"],
        created_at=result["created_at"],
        owner=result["owner"],
        generation=int(result["generation"]),
        post_wake_ready=bool(result["health"]["post_wake_ready"]),
        state_hash=str(result["state"]["state_hash"]),
        self_check_hash=str(result["self_check"]["self_check_hash"]),
        plan_hash=str(result["plan"]["plan_hash"]),
        actions_hash=str(result["actions"]["actions_hash"]),
        snapshot_path_value=snap_path,
        snapshot_hash=str(result["snapshot"]["snapshot_hash"]),
        health=result["health"],
        source="current_result",
        ok=bool(result["ok"]),
        last_run_hash=str(last_run.get("last_run_hash") or ""),
        report_hash=str(last_report.get("report_hash") or ""),
    )


def sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda item: (str(item.get("created_at") or ""), str(item.get("run_id") or "")))


def build_ledger(owner: str, repo: str, token: str, result: dict[str, Any], last_run: dict[str, Any], last_report: dict[str, Any], snap_path: str) -> dict[str, Any]:
    existing_ledger, _, _ = content_get(owner, repo, LEDGER_PATH, token)
    entries_by_run: dict[str, dict[str, Any]] = {}
    if isinstance(existing_ledger, dict):
        for entry in existing_ledger.get("entries") or []:
            if isinstance(entry, dict) and entry.get("run_id"):
                entries_by_run[str(entry["run_id"])] = entry

    listing = list_snapshot_paths(owner, repo, token)
    backfill_read_count = 0
    for path in listing.get("paths") or []:
        snapshot_payload, _, _ = content_get(owner, repo, str(path), token)
        if not isinstance(snapshot_payload, dict):
            continue
        entry = ledger_entry_from_snapshot(snapshot_payload, str(path))
        if entry:
            entries_by_run.setdefault(str(entry["run_id"]), entry)
            backfill_read_count += 1

    current_entry = ledger_entry_from_result(result, last_run, last_report, snap_path)
    entries_by_run[str(current_entry["run_id"])] = current_entry
    entries = sort_entries(list(entries_by_run.values()))
    covered_workflows = sorted({str((entry.get("owner") or {}).get("workflow") or "") for entry in entries if (entry.get("owner") or {}).get("workflow")})
    covered_events = sorted({str((entry.get("owner") or {}).get("event_name") or "") for entry in entries if (entry.get("owner") or {}).get("event_name")})
    workflow_counts: dict[str, int] = {}
    for entry in entries:
        workflow = str((entry.get("owner") or {}).get("workflow") or "unknown")
        workflow_counts[workflow] = workflow_counts.get(workflow, 0) + 1

    ledger = {
        "stage": "E8.4-post-wake-ledger",
        "schema_version": "QMX-E8.4-LEDGER-0.1",
        "created_at": now(),
        "updated_by_run_id": result["run_id"],
        "entry_count": len(entries),
        "ready_count": sum(1 for entry in entries if entry.get("post_wake_ready") is True),
        "covered_workflows": covered_workflows,
        "covered_events": covered_events,
        "workflow_counts": workflow_counts,
        "latest_entry": entries[-1] if entries else {},
        "entries": entries,
        "backfill": {
            "snapshot_listing_ok": listing.get("ok"),
            "snapshot_count_seen": listing.get("count"),
            "snapshot_read_count": backfill_read_count,
            "existing_ledger_entry_count": len((existing_ledger or {}).get("entries") or []) if isinstance(existing_ledger, dict) else 0,
        },
        "truth_boundary": (
            "E8.4 is a mutable GitHub state ledger rebuilt from immutable per-run snapshots and the current result. "
            "It improves auditability but is not a tamper-proof database and does not prove CPU-free wakefulness."
        ),
        "ledger_hash": "",
    }
    return seal(ledger, "ledger_hash")


def build_ledger_report(result: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E8.4-ledger-report",
        "schema_version": "QMX-E8.4-REPORT-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "entry_count": ledger["entry_count"],
        "ready_count": ledger["ready_count"],
        "covered_workflows": ledger["covered_workflows"],
        "covered_events": ledger["covered_events"],
        "latest_entry_run_id": (ledger.get("latest_entry") or {}).get("run_id"),
        "ledger_hash": ledger["ledger_hash"],
        "conclusion": "E8.4 records post-wake self-check receipts into a unified deduplicated ledger.",
        "truth_boundary": ledger["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


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
            sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"e8-2-commit-{path}-{attempt}")
            payload_out = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
            observed_hash = str(payload_out.get(hash_field) or "")
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


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "E8.2-last-run",
        "schema_version": "QMX-E8.2-LAST-RUN-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "owner": result["owner"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "generation": result["generation"],
        "post_wake_ready": result["health"]["post_wake_ready"],
        "executed_count": result["actions"]["executed_count"],
        "queued_count": result["actions"]["queued_count"],
        "blocked_count": result["actions"]["blocked_count"],
        "self_check_hash": result["self_check"]["self_check_hash"],
        "state_hash": result["state"]["state_hash"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E8.2-last-report",
        "schema_version": "QMX-E8.2-REPORT-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "post_wake_ready": result["health"]["post_wake_ready"],
        "health": result["health"],
        "self_check_hash": result["self_check"]["self_check_hash"],
        "plan_hash": result["plan"]["plan_hash"],
        "actions_hash": result["actions"]["actions_hash"],
        "state_hash": result["state"]["state_hash"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_e8_2_post_wake_self_maintenance_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_e8_2_post_wake_self_maintenance_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E8.2 Post Wake Self Maintenance",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- post_wake_ready: `{result['health']['post_wake_ready']}`",
        f"- executed_count: `{result['actions']['executed_count']}`",
        f"- queued_count: `{result['actions']['queued_count']}`",
        f"- blocked_count: `{result['actions']['blocked_count']}`",
        "",
        "## Meaning",
        "",
        result["conclusion"],
        "",
        "## Truth Boundary",
        "",
        result["truth_boundary"],
        "",
    ]
    (run_dir / "nsl_e8_2_post_wake_self_maintenance_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E8.2 post-wake self-check and controlled maintenance")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--raw-timeout", type=int, default=180)
    parser.add_argument("--raw-interval", type=float, default=6.0)
    args = parser.parse_args()

    import os

    event = os.environ.get("GITHUB_EVENT_NAME") or "local"
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        run_id = f"nsl-e8-2-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-e8-2-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()

    samples = [sample_source(args.owner, args.repo, spec, token) for spec in SOURCE_SPECS]
    previous = payload(samples, "previous_e8_2_state")
    generation = int(previous.get("generation") or 0) + 1
    health = derive_post_wake_health(samples)
    self_check = build_self_check(run_id, args.mode, generation, samples, health)
    plan = build_plan(run_id, args.mode, generation, health)
    actions = build_actions(run_id, args.mode, generation, plan, self_check)
    state = build_state(run_id, args.mode, generation, self_check, plan, actions)
    snap_path = snapshot_path(run_id)

    self_check_write = put_and_verify(args.owner, args.repo, token, SELF_CHECK_PATH, self_check, "self_check_hash", f"E8.2 self check {run_id}")
    plan_write = put_and_verify(args.owner, args.repo, token, PLAN_PATH, plan, "plan_hash", f"E8.2 plan {run_id}")
    actions_write = put_and_verify(args.owner, args.repo, token, ACTIONS_PATH, actions, "actions_hash", f"E8.2 actions {run_id}")
    state_write = put_and_verify(args.owner, args.repo, token, STATE_PATH, state, "state_hash", f"E8.2 state {run_id}")
    snapshot = {
        "stage": "E8.2-post-wake-snapshot",
        "schema_version": "QMX-E8.2-SNAPSHOT-0.1",
        "created_at": now(),
        "run_id": run_id,
        "generation": generation,
        "self_check": self_check,
        "plan": plan,
        "actions": actions,
        "state": state,
        "snapshot_hash": "",
    }
    snapshot = seal(snapshot, "snapshot_hash")
    snapshot_write = put_and_verify(args.owner, args.repo, token, snap_path, snapshot, "snapshot_hash", f"E8.2 snapshot {run_id}")
    branch_release = wait_for_branch_release(
        args.owner,
        args.repo,
        [{"path": snap_path, "hash_field": "snapshot_hash", "hash_value": snapshot["snapshot_hash"]}],
        args.raw_timeout,
        args.raw_interval,
    )

    core_ok = bool(
        health["post_wake_ready"]
        and actions.get("actions_ok")
        and self_check_write.get("ok")
        and self_check_write.get("commit_raw_ok")
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
        "stage": "E8.2-post-wake-self-maintenance",
        "ok": core_ok,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "generation": generation,
        "samples": samples,
        "health": health,
        "self_check": self_check,
        "plan": plan,
        "actions": actions,
        "state": state,
        "snapshot": snapshot,
        "paths": {
            "workflow": ".github/workflows/nsl-e8-2-post-wake-self-maintenance.yml",
            "runner": "scripts/nsl_e8_2_post_wake_self_maintenance.py",
            "self_check": SELF_CHECK_PATH,
            "plan": PLAN_PATH,
            "actions": ACTIONS_PATH,
            "state": STATE_PATH,
            "snapshot": snap_path,
            "last_run": LAST_RUN_PATH,
            "last_report": LAST_REPORT_PATH,
            "ledger": LEDGER_PATH,
            "ledger_report": LEDGER_REPORT_PATH,
        },
        "writes": {
            "self_check": self_check_write,
            "plan": plan_write,
            "actions": actions_write,
            "state": state_write,
            "snapshot": snapshot_write,
        },
        "verification": {"branch_raw_release": branch_release},
        "evidence_level": "E8.2-post-wake-self-maintenance-v0" if core_ok else "E8.2-post-wake-self-maintenance-partial",
        "conclusion": (
            "E8.2 proves the external wake path can be followed by an auditable post-wake self-check and low-risk "
            "maintenance receipt, while keeping third-party clock setup as a pending enhancement instead of a blocker."
        ),
        "truth_boundary": (
            "E8.2 is still executed by local or GitHub Actions CPU. It strengthens post-wake self-check and controlled "
            "maintenance records; it does not prove CPU-free wakefulness, autonomous evolution, or unrestricted self-modification."
        ),
    }
    last_run = build_last_run(result)
    last_run_write = put_and_verify(args.owner, args.repo, token, LAST_RUN_PATH, last_run, "last_run_hash", f"E8.2 last run {run_id}")
    last_report = build_report(result)
    last_report_write = put_and_verify(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, "report_hash", f"E8.2 last report {run_id}")
    result["writes"]["last_run"] = last_run_write
    result["writes"]["last_report"] = last_report_write
    result["ok"] = bool(
        core_ok
        and last_run_write.get("ok")
        and last_run_write.get("commit_raw_ok")
        and last_report_write.get("ok")
        and last_report_write.get("commit_raw_ok")
    )
    result["evidence_level"] = "E8.2-post-wake-self-maintenance-v0" if result["ok"] else "E8.2-post-wake-self-maintenance-partial"
    ledger = build_ledger(args.owner, args.repo, token, result, last_run, last_report, snap_path)
    ledger_write = put_and_verify(args.owner, args.repo, token, LEDGER_PATH, ledger, "ledger_hash", f"E8.4 ledger {run_id}")
    ledger_report = build_ledger_report(result, ledger)
    ledger_report_write = put_and_verify(args.owner, args.repo, token, LEDGER_REPORT_PATH, ledger_report, "report_hash", f"E8.4 ledger report {run_id}")
    result["ledger"] = ledger
    result["ledger_report"] = ledger_report
    result["writes"]["ledger"] = ledger_write
    result["writes"]["ledger_report"] = ledger_report_write
    result["ok"] = bool(
        result["ok"]
        and ledger_write.get("ok")
        and ledger_write.get("commit_raw_ok")
        and ledger_report_write.get("ok")
        and ledger_report_write.get("commit_raw_ok")
    )
    result["evidence_level"] = "E8.2-post-wake-self-maintenance-v0+E8.4-ledger" if result["ok"] else "E8.2-post-wake-self-maintenance-partial"
    write_local_outputs(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "event_name": result["owner"].get("event_name"),
                "evidence_level": result["evidence_level"],
                "generation": result["generation"],
                "post_wake_ready": result["health"]["post_wake_ready"],
                "executed_count": result["actions"]["executed_count"],
                "queued_count": result["actions"]["queued_count"],
                "blocked_count": result["actions"]["blocked_count"],
                "state_hash": result["state"]["state_hash"],
                "ledger_entry_count": (result.get("ledger") or {}).get("entry_count"),
                "ledger_hash": (result.get("ledger") or {}).get("ledger_hash"),
                "branch_raw_release_ok": result["verification"]["branch_raw_release"].get("ok"),
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
