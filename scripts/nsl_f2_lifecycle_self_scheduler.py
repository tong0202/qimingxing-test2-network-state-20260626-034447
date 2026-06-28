from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_f0_capsule_quorum_rebuild import core_hash, verify_capsule
from nsl_f1_capsule_lifecycle import put_json, seal, wait_for_hash
from nsl_l12_hourly_self_maintenance import (
    content_get,
    fetch_json_url,
    gh_token,
    now,
    raw_url,
    run_owner,
    stable_hash,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

F1_STATE_PATH = "states/f1-lifecycle-state.json"
F1_REGISTRY_PATH = "states/f1-lifecycle-registry.json"
F1_CHILD_PATH = "states/f1-capsules/repair_capsule_child.json"

SCHEDULER_CAPSULE_PATH = "states/f2-scheduler-capsule.json"
SCHEDULER_CHILD_PATH = "states/f2-capsules/scheduler_child.json"
STATE_PATH = "states/f2-scheduler-state.json"
LEDGER_PATH = "states/f2-scheduler-ledger.json"
LAST_RUN_PATH = "states/f2-last-run.json"
LAST_REPORT_PATH = "states/f2-last-report.json"

ALLOWED_ACTIONS = {"split", "decay", "retire", "peer_check", "sleep", "wake", "observe"}


def run_id_for(mode: str) -> str:
    event = os.environ.get("GITHUB_EVENT_NAME") or mode
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        return f"nsl-f2-{event}-{run_number}-attempt-{attempt}"
    return "nsl-f2-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def read_json_content(owner: str, repo: str, token: str, path: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    payload, _, response = content_get(owner, repo, path, token)
    return payload, response


def build_scheduler_capsule(run_id: str, source_f1_state_hash: str) -> dict[str, Any]:
    core = {
        "role": "lifecycle_scheduler",
        "kind": "scheduler",
        "capsule_id": "f2cap-lifecycle-scheduler",
        "path": SCHEDULER_CAPSULE_PATH,
        "source_f1_state_hash": source_f1_state_hash,
        "duty": "choose the next low-risk lifecycle event from remote lifecycle state",
        "network_language": {
            "family": "QMX-F2-LIFECYCLE-SELF-SCHEDULER",
            "rule": "WHEN lifecycle state changes THEN score low-risk candidate events and execute one selected event",
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
        },
        "policy": {
            "max_ticks_per_run": 4,
            "high_risk_actions": ["arbitrary_code", "delete_unscoped_anchor", "external_secret_use"],
            "default_budget": "low_risk_only",
        },
    }
    capsule = {
        "stage": "F2-lifecycle-self-scheduler",
        "schema_version": "QMX-F2-SCHEDULER-CAPSULE-0.1",
        "created_by_run_id": run_id,
        "created_at": now(),
        "updated_at": now(),
        "role": "lifecycle_scheduler",
        "path": SCHEDULER_CAPSULE_PATH,
        "core": core,
        "core_hash": core_hash(core),
        "safety": {
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
            "allowed_write_prefixes": ["states/f2-"],
            "allowed_actions": sorted(ALLOWED_ACTIONS),
        },
        "truth_boundary": "The scheduler capsule chooses and writes low-risk lifecycle events; it is not self-executing without an external runner.",
        "capsule_hash": "",
    }
    return seal(capsule, "capsule_hash")


def bootstrap_scheduler_state(run_id: str, f1_state: dict[str, Any]) -> dict[str, Any]:
    capsule_status = f1_state.get("capsule_status") if isinstance(f1_state.get("capsule_status"), dict) else {}
    memory_status = capsule_status.get("memory_capsule") if isinstance(capsule_status.get("memory_capsule"), dict) else {}
    child_status = capsule_status.get("repair_capsule_child") if isinstance(capsule_status.get("repair_capsule_child"), dict) else {}
    child_retired = bool(child_status.get("retired", True))
    child_vitality = int(child_status.get("vitality") if child_status.get("vitality") is not None else 0)
    return {
        "scheduler_generation": 1,
        "created_by_run_id": run_id,
        "source_f1_state_hash": f1_state.get("state_hash"),
        "source_f1_event_order": f1_state.get("event_order") or [],
        "memory_shadow_state": str(memory_status.get("state") or "unknown"),
        "child": {
            "exists": bool(child_status),
            "state": str(child_status.get("state") or "missing"),
            "retired": child_retired,
            "vitality": child_vitality,
            "capsule_hash": str(child_status.get("capsule_hash") or ""),
        },
        "last_peer_check_hash": "",
        "total_scheduler_ticks": 0,
        "last_selected_action": "",
    }


def normalize_previous_state(previous: dict[str, Any] | None, run_id: str, f1_state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(previous, dict):
        return bootstrap_scheduler_state(run_id, f1_state)
    state = json.loads(json.dumps(previous, ensure_ascii=False))
    return {
        "scheduler_generation": int(state.get("scheduler_generation") or 1) + 1,
        "created_by_run_id": state.get("created_by_run_id") or run_id,
        "source_f1_state_hash": f1_state.get("state_hash"),
        "source_f1_event_order": f1_state.get("event_order") or [],
        "memory_shadow_state": str(state.get("memory_shadow_state") or "unknown"),
        "child": state.get("child") if isinstance(state.get("child"), dict) else {"exists": False, "state": "missing", "retired": True, "vitality": 0, "capsule_hash": ""},
        "last_peer_check_hash": str(state.get("last_peer_check_hash") or ""),
        "total_scheduler_ticks": int(state.get("total_scheduler_ticks") or 0),
        "last_selected_action": str(state.get("last_selected_action") or ""),
    }


def score_candidates(scheduler_state: dict[str, Any], f1_state: dict[str, Any], actions_this_run: list[str]) -> list[dict[str, Any]]:
    child = scheduler_state.get("child") if isinstance(scheduler_state.get("child"), dict) else {}
    child_exists = bool(child.get("exists"))
    child_retired = bool(child.get("retired"))
    child_vitality = int(child.get("vitality") or 0)
    memory_state = str(scheduler_state.get("memory_shadow_state") or "unknown")
    f1_state_hash = str(f1_state.get("state_hash") or "")
    last_peer_hash = str(scheduler_state.get("last_peer_check_hash") or "")
    candidates: list[dict[str, Any]] = []

    def add(action: str, score: int, reason: str) -> None:
        candidates.append({"action": action, "score": score, "reason": reason, "allowed": action in ALLOWED_ACTIONS})

    if (not child_exists or child_retired) and "split" not in actions_this_run:
        add("split", 95, "no active scheduler child exists")
    if child_exists and not child_retired and child_vitality > 35:
        add("decay", 90, "active child vitality is above decay threshold")
    if child_exists and not child_retired and child_vitality <= 35:
        add("retire", 92, "active child vitality reached retirement threshold")
    if last_peer_hash != f1_state_hash:
        add("peer_check", 80, "source F1 state hash has not been peer-checked by F2")
    if memory_state == "sleeping":
        add("wake", 70, "memory shadow is sleeping")
    if memory_state != "sleeping" and "sleep" not in actions_this_run:
        add("sleep", 60, "memory shadow can enter a low-risk rest state")
    add("observe", 10, "fallback observation if no stronger lifecycle event applies")
    return sorted(candidates, key=lambda item: (-int(item["score"]), str(item["action"])))


def build_child(run_id: str, source_f1_state_hash: str) -> dict[str, Any]:
    core = {
        "role": "scheduler_child",
        "kind": "scheduled_child",
        "capsule_id": "f2cap-scheduler-child",
        "path": SCHEDULER_CHILD_PATH,
        "source_f1_state_hash": source_f1_state_hash,
        "duty": "hold a scheduled child lifecycle state selected by the scheduler",
        "network_language": {
            "family": "QMX-F2-LIFECYCLE-SELF-SCHEDULER",
            "rule": "WHEN scheduler selects split THEN create scheduler child state",
            "allowed_action": "scheduled_split",
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
        },
    }
    child = {
        "stage": "F2-lifecycle-self-scheduler-child",
        "schema_version": "QMX-F2-CHILD-0.1",
        "created_by_run_id": run_id,
        "created_at": now(),
        "updated_at": now(),
        "role": "scheduler_child",
        "path": SCHEDULER_CHILD_PATH,
        "core": core,
        "core_hash": core_hash(core),
        "lifecycle": {
            "state": "split_child",
            "retired": False,
            "vitality": 65,
            "age_ticks": 1,
            "last_event": "split",
            "last_event_at": now(),
        },
        "truth_boundary": "F2 scheduler child is a remote state child, not an independent self-executing process.",
        "capsule_hash": "",
    }
    return seal(child, "capsule_hash")


def transition_child(child: dict[str, Any], run_id: str, action: str) -> dict[str, Any]:
    clone = json.loads(json.dumps(child, ensure_ascii=False))
    lifecycle = clone.setdefault("lifecycle", {})
    lifecycle["last_event"] = action
    lifecycle["last_event_at"] = now()
    lifecycle["age_ticks"] = int(lifecycle.get("age_ticks") or 0) + 1
    if action == "decay":
        lifecycle["state"] = "decayed"
        lifecycle["vitality"] = max(0, int(lifecycle.get("vitality") or 0) - 35)
    elif action == "retire":
        lifecycle["state"] = "retired"
        lifecycle["retired"] = True
        lifecycle["vitality"] = 0
    clone["updated_at"] = now()
    clone["updated_by_run_id"] = run_id
    return seal(clone, "capsule_hash")


def execute_action(
    owner: str,
    repo: str,
    token: str,
    run_id: str,
    action: str,
    scheduler_state: dict[str, Any],
    f1_state: dict[str, Any],
) -> dict[str, Any]:
    if action == "split":
        child = build_child(run_id, str(f1_state.get("state_hash") or ""))
        write = put_json(owner, repo, token, SCHEDULER_CHILD_PATH, child, f"F2 split scheduler child {run_id}")
        verify = wait_for_hash(owner, repo, token, SCHEDULER_CHILD_PATH, "capsule_hash", child["capsule_hash"])
        scheduler_state["child"] = {
            "exists": True,
            "state": child["lifecycle"]["state"],
            "retired": False,
            "vitality": child["lifecycle"]["vitality"],
            "capsule_hash": child["capsule_hash"],
        }
        return {"ok": bool(write.get("ok") and verify.get("ok")), "action": action, "write": write, "verify": verify, "child_hash": child["capsule_hash"]}

    if action in {"decay", "retire"}:
        payload, response = read_json_content(owner, repo, token, SCHEDULER_CHILD_PATH)
        if not isinstance(payload, dict):
            return {"ok": False, "action": action, "error": "scheduler_child_missing", "read_status": response.get("status")}
        child = transition_child(payload, run_id, action)
        write = put_json(owner, repo, token, SCHEDULER_CHILD_PATH, child, f"F2 {action} scheduler child {run_id}")
        verify = wait_for_hash(owner, repo, token, SCHEDULER_CHILD_PATH, "capsule_hash", child["capsule_hash"])
        lifecycle = child.get("lifecycle") or {}
        scheduler_state["child"] = {
            "exists": True,
            "state": lifecycle.get("state"),
            "retired": lifecycle.get("retired"),
            "vitality": lifecycle.get("vitality"),
            "capsule_hash": child["capsule_hash"],
        }
        return {"ok": bool(response.get("ok") and write.get("ok") and verify.get("ok")), "action": action, "write": write, "verify": verify, "child_hash": child["capsule_hash"]}

    if action == "peer_check":
        registry, registry_response = read_json_content(owner, repo, token, F1_REGISTRY_PATH)
        child, child_response = read_json_content(owner, repo, token, F1_CHILD_PATH)
        state_hash_ok = bool(f1_state.get("state_hash") and f1_state.get("state_hash") == stable_hash(f1_state, "state_hash"))
        registry_hash_ok = bool(isinstance(registry, dict) and registry.get("registry_hash") == stable_hash(registry, "registry_hash"))
        child_check = verify_capsule(child)
        scheduler_state["last_peer_check_hash"] = str(f1_state.get("state_hash") or "")
        return {
            "ok": bool(state_hash_ok and registry_response.get("ok") and registry_hash_ok and child_response.get("ok") and child_check.get("ok")),
            "action": action,
            "state_hash_ok": state_hash_ok,
            "registry_hash_ok": registry_hash_ok,
            "child_hash_ok": child_check.get("ok"),
        }

    if action == "sleep":
        scheduler_state["memory_shadow_state"] = "sleeping"
        return {"ok": True, "action": action, "memory_shadow_state": "sleeping"}

    if action == "wake":
        scheduler_state["memory_shadow_state"] = "awake"
        return {"ok": True, "action": action, "memory_shadow_state": "awake"}

    return {"ok": True, "action": "observe", "observed_f1_state_hash": f1_state.get("state_hash")}


def append_decision(decisions: list[dict[str, Any]], tick: int, candidates: list[dict[str, Any]], selected: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    decision = {
        "tick": tick,
        "created_at": now(),
        "candidates": candidates,
        "selected_action": selected["action"],
        "selected_score": selected["score"],
        "selected_reason": selected["reason"],
        "execution_ok": execution.get("ok"),
        "execution": execution,
        "decision_hash": "",
    }
    sealed = seal(decision, "decision_hash")
    decisions.append(sealed)
    return sealed


def build_state(
    run_id: str,
    mode: str,
    source_f1_state: dict[str, Any],
    scheduler_capsule_hash: str,
    scheduler_state: dict[str, Any],
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    state = {
        "stage": "F2-lifecycle-self-scheduler-state",
        "schema_version": "QMX-F2-STATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "source": {
            "f1_state_path": F1_STATE_PATH,
            "f1_state_hash": source_f1_state.get("state_hash"),
            "f1_event_order": source_f1_state.get("event_order") or [],
        },
        "scheduler_capsule_hash": scheduler_capsule_hash,
        "scheduler_generation": scheduler_state.get("scheduler_generation"),
        "memory_shadow_state": scheduler_state.get("memory_shadow_state"),
        "child": scheduler_state.get("child"),
        "total_scheduler_ticks": scheduler_state.get("total_scheduler_ticks"),
        "selected_actions": [item["selected_action"] for item in decisions],
        "decision_count": len(decisions),
        "decisions": decisions,
        "truth_boundary": "F2 chooses low-risk lifecycle events from remote state; it is not self-executing without an external runner.",
        "state_hash": "",
    }
    return seal(state, "state_hash")


def append_ledger(owner: str, repo: str, token: str, run_id: str, mode: str, entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, sha, _ = content_get(owner, repo, LEDGER_PATH, token)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    sealed_entry = seal(entry, "entry_hash")
    entries = [item for item in entries if isinstance(item, dict) and item.get("run_id") != run_id]
    entries.append(sealed_entry)
    entries = entries[-100:]
    ledger = {
        "stage": "F2-lifecycle-self-scheduler-ledger",
        "schema_version": "QMX-F2-LEDGER-0.1",
        "updated_at": now(),
        "owner": run_owner(mode),
        "entry_count": len(entries),
        "latest_run_id": run_id,
        "entries": entries,
        "truth_boundary": "This scheduler ledger is mutable remote state, not tamper-proof storage.",
        "ledger_hash": "",
    }
    ledger = seal(ledger, "ledger_hash")
    write = put_json(owner, repo, token, LEDGER_PATH, ledger, f"F2 scheduler ledger {run_id}")
    return ledger, write


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "F2-last-run",
        "schema_version": "QMX-F2-LAST-RUN-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "selected_actions": result["selected_actions"],
        "decision_count": result["decision_count"],
        "all_decisions_ok": result["all_decisions_ok"],
        "state_hash": result["state"]["state_hash"],
        "ledger_hash": result["ledger"]["ledger_hash"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_last_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "F2-last-report",
        "schema_version": "QMX-F2-REPORT-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "source_f1_state_hash": result["source_f1_state_hash"],
        "selected_actions": result["selected_actions"],
        "decision_count": result["decision_count"],
        "all_decisions_ok": result["all_decisions_ok"],
        "state_hash": result["state"]["state_hash"],
        "ledger_hash": result["ledger"]["ledger_hash"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "nsl_f2_lifecycle_self_scheduler_result.json"
    report_path = run_dir / "nsl_f2_lifecycle_self_scheduler_report.md"
    latest_path = RUNS / "latest_nsl_f2_lifecycle_self_scheduler_result.json"
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    result_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# F2 lifecycle self-scheduler report",
                "",
                f"run_id: `{result.get('run_id')}`",
                f"ok: `{result.get('ok')}`",
                f"selected_actions: `{','.join(result.get('selected_actions') or [])}`",
                f"state_hash: `{result.get('state', {}).get('state_hash')}`",
                "",
                "Truth boundary:",
                "",
                "```text",
                str(result.get("truth_boundary") or ""),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="F2 lifecycle-driven self scheduler")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--ticks", type=int, default=4)
    parser.add_argument("--raw-check", action="store_true")
    args = parser.parse_args()

    token = gh_token()
    run_id = run_id_for(args.mode)
    run_dir = RUNS / run_id
    f1_state, f1_state_response = read_json_content(args.owner, args.repo, token, F1_STATE_PATH)
    if not isinstance(f1_state, dict):
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "F2-lifecycle-self-scheduler",
            "ok": False,
            "error": "missing_f1_lifecycle_state",
            "f1_state_status": f1_state_response.get("status"),
            "truth_boundary": "F2 cannot schedule without F1 lifecycle state.",
        }
        write_local(run_dir, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 1
    f1_state_hash_ok = bool(f1_state.get("state_hash") and f1_state.get("state_hash") == stable_hash(f1_state, "state_hash"))
    previous_state, _, _ = content_get(args.owner, args.repo, STATE_PATH, token)
    scheduler_state = normalize_previous_state(previous_state, run_id, f1_state)
    scheduler_capsule = build_scheduler_capsule(run_id, str(f1_state.get("state_hash") or ""))
    scheduler_write = put_json(args.owner, args.repo, token, SCHEDULER_CAPSULE_PATH, scheduler_capsule, f"F2 scheduler capsule {run_id}")
    scheduler_check = wait_for_hash(args.owner, args.repo, token, SCHEDULER_CAPSULE_PATH, "capsule_hash", scheduler_capsule["capsule_hash"])

    decisions: list[dict[str, Any]] = []
    actions_this_run: list[str] = []
    for tick in range(1, max(1, args.ticks) + 1):
        candidates = score_candidates(scheduler_state, f1_state, actions_this_run)
        selected = next(item for item in candidates if item.get("allowed"))
        execution = execute_action(args.owner, args.repo, token, run_id, selected["action"], scheduler_state, f1_state)
        append_decision(decisions, tick, candidates, selected, execution)
        actions_this_run.append(str(selected["action"]))
        scheduler_state["total_scheduler_ticks"] = int(scheduler_state.get("total_scheduler_ticks") or 0) + 1
        scheduler_state["last_selected_action"] = str(selected["action"])

    scheduler_state["source_f1_state_hash"] = f1_state.get("state_hash")
    state = build_state(run_id, args.mode, f1_state, scheduler_capsule["capsule_hash"], scheduler_state, decisions)
    state_write = put_json(args.owner, args.repo, token, STATE_PATH, state, f"F2 scheduler state {run_id}")
    state_check = wait_for_hash(args.owner, args.repo, token, STATE_PATH, "state_hash", state["state_hash"])
    selected_actions = [item["selected_action"] for item in decisions]
    all_decisions_ok = all(item.get("execution_ok") for item in decisions)
    run_entry = {
        "stage": "F2-scheduler-ledger-entry",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "source_f1_state_hash": f1_state.get("state_hash"),
        "selected_actions": selected_actions,
        "decision_hashes": [item["decision_hash"] for item in decisions],
        "decision_count": len(decisions),
        "all_decisions_ok": all_decisions_ok,
        "state_hash": state["state_hash"],
        "entry_hash": "",
    }
    ledger, ledger_write = append_ledger(args.owner, args.repo, token, run_id, args.mode, run_entry)
    ledger_check = wait_for_hash(args.owner, args.repo, token, LEDGER_PATH, "ledger_hash", ledger["ledger_hash"])
    raw_state_check: dict[str, Any] = {}
    if args.raw_check and state_write.get("commit_hash"):
        sample = fetch_json_url(raw_url(args.owner, args.repo, str(state_write["commit_hash"]), STATE_PATH), "f2-state-commit-raw")
        payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
        raw_state_check = {
            "ok": bool(sample.get("ok") and payload.get("state_hash") == state["state_hash"]),
            "status": sample.get("status"),
            "observed_state_hash": payload.get("state_hash"),
            "expected_state_hash": state["state_hash"],
            "error": sample.get("error"),
        }

    core_ok = bool(
        f1_state_hash_ok
        and scheduler_write.get("ok")
        and scheduler_check.get("ok")
        and all_decisions_ok
        and state_write.get("ok")
        and state_check.get("ok")
        and ledger_write.get("ok")
        and ledger_check.get("ok")
    )
    if args.raw_check:
        core_ok = bool(core_ok and raw_state_check.get("ok"))
    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "F2-lifecycle-self-scheduler",
        "ok": core_ok,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "paths": {
            "scheduler_capsule": SCHEDULER_CAPSULE_PATH,
            "scheduler_child": SCHEDULER_CHILD_PATH,
            "state": STATE_PATH,
            "ledger": LEDGER_PATH,
            "last_run": LAST_RUN_PATH,
            "last_report": LAST_REPORT_PATH,
        },
        "source_f1_state_hash": f1_state.get("state_hash"),
        "source_f1_state_hash_ok": f1_state_hash_ok,
        "scheduler_capsule": {
            "capsule_hash": scheduler_capsule["capsule_hash"],
            "write": scheduler_write,
            "verify": scheduler_check,
        },
        "decisions": decisions,
        "selected_actions": selected_actions,
        "decision_count": len(decisions),
        "all_decisions_ok": all_decisions_ok,
        "state": {"state_hash": state["state_hash"], "write": state_write, "verify": state_check},
        "ledger": {"ledger_hash": ledger["ledger_hash"], "entry_count": ledger["entry_count"], "write": ledger_write, "verify": ledger_check},
        "raw_state_check": raw_state_check,
        "evidence_level": "F2-lifecycle-self-scheduler-v0" if core_ok else "F2-lifecycle-self-scheduler-partial",
        "conclusion": "F2 proves a low-risk scheduler can choose lifecycle events from remote lifecycle state instead of replaying a fixed full chain.",
        "truth_boundary": (
            "F2 is state-driven scheduling over mutable remote anchors. It does not prove endpoint-free existence, "
            "CPU-free network computation, self-executing capsules, or fully autonomous digital life."
        ),
    }
    last_run = build_last_run(result)
    last_report = build_last_report(result)
    last_run_write = put_json(args.owner, args.repo, token, LAST_RUN_PATH, last_run, f"F2 last run {run_id}")
    last_report_write = put_json(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, f"F2 last report {run_id}")
    result["last_run"] = last_run
    result["last_report"] = last_report
    result["writes"] = {"last_run": last_run_write, "last_report": last_report_write}
    result["ok"] = bool(result["ok"] and last_run_write.get("ok") and last_report_write.get("ok"))
    result["evidence_level"] = "F2-lifecycle-self-scheduler-v0" if result["ok"] else "F2-lifecycle-self-scheduler-partial"
    write_local(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "evidence_level": result["evidence_level"],
                "selected_actions": selected_actions,
                "decision_count": len(decisions),
                "state_hash": state["state_hash"],
                "ledger_hash": ledger["ledger_hash"],
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
