from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_f0_capsule_quorum_rebuild import (
    ROLE_ORDER as F0_ROLE_ORDER,
    ROLE_SPECS as F0_ROLE_SPECS,
    collect_alive_capsules,
    core_hash,
    delete_json,
    quorum_votes,
    verify_capsule,
    wait_for_missing,
)
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

CAPSULE_DIR = "states/f1-capsules"
REGISTRY_PATH = "states/f1-lifecycle-registry.json"
STATE_PATH = "states/f1-lifecycle-state.json"
LEDGER_PATH = "states/f1-lifecycle-ledger.json"
LAST_RUN_PATH = "states/f1-last-run.json"
LAST_REPORT_PATH = "states/f1-last-report.json"

ROLE_ORDER = list(F0_ROLE_ORDER)
SPLIT_CHILD_ROLE = "repair_capsule_child"
SPLIT_CHILD_PATH = f"{CAPSULE_DIR}/{SPLIT_CHILD_ROLE}.json"


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def run_id_for(mode: str) -> str:
    event = os.environ.get("GITHUB_EVENT_NAME") or mode
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        return f"nsl-f1-{event}-{run_number}-attempt-{attempt}"
    return "nsl-f1-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def role_path(role: str) -> str:
    return f"{CAPSULE_DIR}/{role}.json"


def put_json(owner: str, repo: str, token: str, path: str, value: dict[str, Any], message: str) -> dict[str, Any]:
    _, sha, existing = content_get(owner, repo, path, token)
    response = put_content(owner, repo, path, value, message, token, sha)
    return {
        "path": path,
        "existing_status": existing.get("status"),
        "ok": bool(response.get("ok")),
        "status": response.get("status"),
        "error": response.get("error"),
        "commit_hash": commit_hash_from_put(response),
        "content_sha": content_sha_from_put(response),
    }


def verify_remote_hash(owner: str, repo: str, token: str, path: str, field: str) -> dict[str, Any]:
    payload, _, response = content_get(owner, repo, path, token)
    declared = ""
    computed = ""
    if isinstance(payload, dict):
        declared = str(payload.get(field) or "")
        computed = stable_hash(payload, field)
    return {
        "path": path,
        "ok": bool(response.get("ok") and declared and declared == computed),
        "status": response.get("status"),
        "hash_field": field,
        "declared": declared,
        "computed": computed,
        "error": response.get("error"),
    }


def append_event(events: list[dict[str, Any]], event: dict[str, Any]) -> dict[str, Any]:
    sealed = seal(event, "event_hash")
    events.append(sealed)
    return sealed


def build_core(spec: dict[str, str], generation: int) -> dict[str, Any]:
    role = spec["role"]
    return {
        "role": role,
        "kind": spec["kind"],
        "generation": generation,
        "capsule_id": f"f1cap-{role}",
        "path": role_path(role),
        "duty": spec["duty"],
        "network_language": {
            "family": "QMX-F1-CAPSULE-LIFECYCLE",
            "rule": spec["rule"],
            "allowed_action": spec["allowed_action"],
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
        },
        "lifecycle_contract": {
            "allowed_events": ["birth", "sleep", "wake", "peer_check", "repair", "split", "decay", "retire"],
            "state_machine": "born -> awake/sleeping -> peer_checked -> repaired/split -> decayed -> retired",
        },
    }


def make_peer_manifest(cores: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "roles": [
            {
                "role": role,
                "path": role_path(role),
                "capsule_id": f"f1cap-{role}",
                "expected_core_hash": core_hash(core),
            }
            for role, core in cores.items()
        ],
        "quorum_threshold": 3,
        "total_capsules": len(cores),
        "vote_basis": "alive capsules witness expected_core_hash for the missing role",
    }


def build_capsule(run_id: str, generation: int, core: dict[str, Any], peer_manifest: dict[str, Any]) -> dict[str, Any]:
    role = core["role"]
    capsule = {
        "stage": "F1-capsule-lifecycle",
        "schema_version": "QMX-F1-CAPSULE-0.1",
        "created_by_run_id": run_id,
        "created_at": now(),
        "updated_at": now(),
        "generation": generation,
        "role": role,
        "path": role_path(role),
        "core": core,
        "core_hash": core_hash(core),
        "peer_manifest": peer_manifest,
        "lifecycle": {
            "state": "born",
            "birth_run_id": run_id,
            "wake_count": 0,
            "sleep_count": 0,
            "peer_check_count": 0,
            "repair_count": 0,
            "split_count": 0,
            "decay_count": 0,
            "retired": False,
            "vitality": 100,
            "age_ticks": 0,
            "last_event": "birth",
            "last_event_at": now(),
        },
        "safety": {
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
            "allowed_write_prefixes": [CAPSULE_DIR, "states/f1-"],
        },
        "truth_boundary": (
            "F1 capsules have lifecycle state stored in a remote anchor. "
            "They still require an external runner to be read, changed, and written."
        ),
        "capsule_hash": "",
    }
    return seal(capsule, "capsule_hash")


def build_capsules(run_id: str, generation: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cores = {spec["role"]: build_core(spec, generation) for spec in F0_ROLE_SPECS}
    peer_manifest = make_peer_manifest(cores)
    capsules = [build_capsule(run_id, generation, cores[role], peer_manifest) for role in ROLE_ORDER]
    blueprints = {capsule["role"]: capsule for capsule in capsules}
    registry = {
        "stage": "F1-capsule-lifecycle-registry",
        "schema_version": "QMX-F1-REGISTRY-0.1",
        "created_by_run_id": run_id,
        "created_at": now(),
        "generation": generation,
        "capsule_count": len(capsules),
        "quorum_threshold": peer_manifest["quorum_threshold"],
        "roles": [
            {
                "role": capsule["role"],
                "path": capsule["path"],
                "expected_core_hash": capsule["core_hash"],
                "birth_capsule_hash": capsule["capsule_hash"],
            }
            for capsule in capsules
        ],
        "rebuild_blueprints": blueprints,
        "truth_boundary": (
            "F1 registry stores lifecycle blueprints and quorum roots in a mutable remote anchor. "
            "It is not tamper-proof storage."
        ),
        "registry_hash": "",
    }
    return capsules, seal(registry, "registry_hash")


def transition_capsule(capsule: dict[str, Any], event: str, state: str, run_id: str, updates: dict[str, Any] | None = None) -> dict[str, Any]:
    clone = json.loads(json.dumps(capsule, ensure_ascii=False))
    lifecycle = clone.setdefault("lifecycle", {})
    lifecycle["state"] = state
    lifecycle["last_event"] = event
    lifecycle["last_event_at"] = now()
    lifecycle["age_ticks"] = int(lifecycle.get("age_ticks") or 0) + 1
    if event == "sleep":
        lifecycle["sleep_count"] = int(lifecycle.get("sleep_count") or 0) + 1
    elif event == "wake":
        lifecycle["wake_count"] = int(lifecycle.get("wake_count") or 0) + 1
    elif event == "peer_check":
        lifecycle["peer_check_count"] = int(lifecycle.get("peer_check_count") or 0) + 1
    elif event == "repair":
        lifecycle["repair_count"] = int(lifecycle.get("repair_count") or 0) + 1
    elif event == "split":
        lifecycle["split_count"] = int(lifecycle.get("split_count") or 0) + 1
    elif event == "decay":
        lifecycle["decay_count"] = int(lifecycle.get("decay_count") or 0) + 1
        lifecycle["vitality"] = max(0, int(lifecycle.get("vitality") or 0) - 35)
    elif event == "retire":
        lifecycle["retired"] = True
        lifecycle["vitality"] = 0
    if updates:
        lifecycle.update(updates)
    clone["updated_at"] = now()
    clone["updated_by_run_id"] = run_id
    return seal(clone, "capsule_hash")


def read_capsule(owner: str, repo: str, token: str, role: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    payload, _, response = content_get(owner, repo, role_path(role), token)
    return payload, response


def collect_f1_alive(owner: str, repo: str, token: str, target_role: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    alive: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        if role == target_role:
            continue
        payload, response = read_capsule(owner, repo, token, role)
        check = verify_capsule(payload)
        check["path"] = role_path(role)
        check["read_status"] = response.get("status")
        checks.append(check)
        if check["ok"] and isinstance(payload, dict):
            alive.append(payload)
    return alive, checks


def peer_check_all(owner: str, repo: str, token: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        payload, response = read_capsule(owner, repo, token, role)
        check = verify_capsule(payload)
        check["path"] = role_path(role)
        check["read_status"] = response.get("status")
        checks.append(check)
    return {
        "ok": all(item.get("ok") for item in checks),
        "checked_count": len(checks),
        "checks": checks,
    }


def build_split_child(parent: dict[str, Any], run_id: str) -> dict[str, Any]:
    parent_core = parent.get("core") if isinstance(parent.get("core"), dict) else {}
    core = {
        "role": SPLIT_CHILD_ROLE,
        "kind": "repair_child",
        "generation": parent.get("generation"),
        "capsule_id": f"f1cap-{SPLIT_CHILD_ROLE}",
        "path": SPLIT_CHILD_PATH,
        "duty": "child repair capsule produced by split event",
        "parent": {
            "role": parent.get("role"),
            "path": parent.get("path"),
            "core_hash": parent.get("core_hash"),
            "capsule_hash": parent.get("capsule_hash"),
        },
        "network_language": {
            "family": "QMX-F1-CAPSULE-LIFECYCLE",
            "rule": "WHEN parent repair capsule splits THEN hold child repair continuity",
            "allowed_action": "hold_child_repair_continuity",
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
        },
        "lifecycle_contract": parent_core.get("lifecycle_contract") or {},
    }
    child = {
        "stage": "F1-capsule-lifecycle",
        "schema_version": "QMX-F1-CAPSULE-0.1",
        "created_by_run_id": run_id,
        "created_at": now(),
        "updated_at": now(),
        "generation": parent.get("generation"),
        "role": SPLIT_CHILD_ROLE,
        "path": SPLIT_CHILD_PATH,
        "core": core,
        "core_hash": core_hash(core),
        "peer_manifest": parent.get("peer_manifest"),
        "lifecycle": {
            "state": "split_child",
            "birth_run_id": run_id,
            "wake_count": 0,
            "sleep_count": 0,
            "peer_check_count": 0,
            "repair_count": 0,
            "split_count": 0,
            "decay_count": 0,
            "retired": False,
            "vitality": 65,
            "age_ticks": 1,
            "parent_role": parent.get("role"),
            "parent_capsule_hash": parent.get("capsule_hash"),
            "last_event": "split",
            "last_event_at": now(),
        },
        "safety": parent.get("safety"),
        "truth_boundary": "The split child is a remote state child capsule, not an independent self-executing process.",
        "capsule_hash": "",
    }
    return seal(child, "capsule_hash")


def append_ledger(owner: str, repo: str, token: str, run_id: str, mode: str, run_entry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, sha, _ = content_get(owner, repo, LEDGER_PATH, token)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    sealed_entry = seal(run_entry, "entry_hash")
    entries = [item for item in entries if isinstance(item, dict) and item.get("run_id") != run_id]
    entries.append(sealed_entry)
    entries = entries[-100:]
    ledger = {
        "stage": "F1-capsule-lifecycle-ledger",
        "schema_version": "QMX-F1-LEDGER-0.1",
        "updated_at": now(),
        "owner": run_owner(mode),
        "entry_count": len(entries),
        "latest_run_id": run_id,
        "entries": entries,
        "truth_boundary": "This lifecycle ledger is mutable remote state, not tamper-proof storage.",
        "ledger_hash": "",
    }
    ledger = seal(ledger, "ledger_hash")
    write = put_content(owner, repo, LEDGER_PATH, ledger, f"F1 lifecycle ledger {run_id}", token, sha)
    return ledger, {
        "path": LEDGER_PATH,
        "ok": bool(write.get("ok")),
        "status": write.get("status"),
        "error": write.get("error"),
        "commit_hash": commit_hash_from_put(write),
        "content_sha": content_sha_from_put(write),
    }


def write_local(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "nsl_f1_capsule_lifecycle_result.json"
    report_path = run_dir / "nsl_f1_capsule_lifecycle_report.md"
    latest_path = RUNS / "latest_nsl_f1_capsule_lifecycle_result.json"
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    result_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# F1 capsule lifecycle report",
                "",
                f"run_id: `{result.get('run_id')}`",
                f"ok: `{result.get('ok')}`",
                f"events: `{result.get('lifecycle_summary', {}).get('event_count')}`",
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


def build_state(run_id: str, mode: str, generation: int, events: list[dict[str, Any]], capsule_status: dict[str, Any]) -> dict[str, Any]:
    state = {
        "stage": "F1-capsule-lifecycle-state",
        "schema_version": "QMX-F1-STATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "event_order": [event["event"] for event in events],
        "event_count": len(events),
        "capsule_status": capsule_status,
        "truth_boundary": (
            "F1 records capsule lifecycle transitions in remote state. "
            "It does not make capsules self-executing or endpoint-free."
        ),
        "state_hash": "",
    }
    return seal(state, "state_hash")


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "F1-last-run",
        "schema_version": "QMX-F1-LAST-RUN-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "generation": result["generation"],
        "event_order": result["lifecycle_summary"]["event_order"],
        "event_count": result["lifecycle_summary"]["event_count"],
        "repair_ok": result["repair"]["ok"],
        "split_ok": result["split"]["ok"],
        "decay_ok": result["decay"]["ok"],
        "retire_ok": result["retire"]["ok"],
        "state_hash": result["state"]["state_hash"],
        "ledger_hash": result["ledger"]["ledger_hash"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_last_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "F1-last-report",
        "schema_version": "QMX-F1-REPORT-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "event_order": result["lifecycle_summary"]["event_order"],
        "repair_quorum": result["repair"]["quorum"],
        "split_child": result["split"].get("child_role"),
        "final_child_state": result["retire"].get("final_state"),
        "state_hash": result["state"]["state_hash"],
        "ledger_hash": result["ledger"]["ledger_hash"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def main() -> int:
    parser = argparse.ArgumentParser(description="F1 capsule lifecycle experiment")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--repair-target", default="rule_capsule", choices=ROLE_ORDER)
    parser.add_argument("--raw-check", action="store_true")
    args = parser.parse_args()

    token = gh_token()
    run_id = run_id_for(args.mode)
    run_dir = RUNS / run_id
    previous_registry, _, _ = content_get(args.owner, args.repo, REGISTRY_PATH, token)
    generation = int((previous_registry or {}).get("generation") or 0) + 1
    events: list[dict[str, Any]] = []

    capsules, registry = build_capsules(run_id, generation)
    seed_writes = [put_json(args.owner, args.repo, token, capsule["path"], capsule, f"F1 birth {capsule['role']} {run_id}") for capsule in capsules]
    registry_write = put_json(args.owner, args.repo, token, REGISTRY_PATH, registry, f"F1 registry {run_id}")
    seed_checks = [verify_remote_hash(args.owner, args.repo, token, capsule["path"], "capsule_hash") for capsule in capsules]
    registry_check = verify_remote_hash(args.owner, args.repo, token, REGISTRY_PATH, "registry_hash")
    birth_ok = bool(all(item.get("ok") for item in seed_writes) and registry_write.get("ok") and all(item.get("ok") for item in seed_checks) and registry_check.get("ok"))
    append_event(
        events,
        {
            "event": "birth",
            "created_at": now(),
            "run_id": run_id,
            "ok": birth_ok,
            "capsule_count": len(capsules),
            "registry_hash": registry["registry_hash"],
            "event_hash": "",
        },
    )

    memory_payload, memory_response = read_capsule(args.owner, args.repo, token, "memory_capsule")
    sleeping_memory = transition_capsule(memory_payload or {}, "sleep", "sleeping", run_id)
    sleep_write = put_json(args.owner, args.repo, token, role_path("memory_capsule"), sleeping_memory, f"F1 sleep memory_capsule {run_id}")
    sleep_check = verify_remote_hash(args.owner, args.repo, token, role_path("memory_capsule"), "capsule_hash")
    sleep_ok = bool(memory_response.get("ok") and sleep_write.get("ok") and sleep_check.get("ok"))
    append_event(
        events,
        {
            "event": "sleep",
            "created_at": now(),
            "run_id": run_id,
            "ok": sleep_ok,
            "role": "memory_capsule",
            "state": "sleeping",
            "capsule_hash": sleeping_memory["capsule_hash"],
            "event_hash": "",
        },
    )

    memory_payload, memory_response = read_capsule(args.owner, args.repo, token, "memory_capsule")
    awake_memory = transition_capsule(memory_payload or {}, "wake", "awake", run_id)
    wake_write = put_json(args.owner, args.repo, token, role_path("memory_capsule"), awake_memory, f"F1 wake memory_capsule {run_id}")
    wake_check = verify_remote_hash(args.owner, args.repo, token, role_path("memory_capsule"), "capsule_hash")
    wake_ok = bool(memory_response.get("ok") and wake_write.get("ok") and wake_check.get("ok"))
    append_event(
        events,
        {
            "event": "wake",
            "created_at": now(),
            "run_id": run_id,
            "ok": wake_ok,
            "role": "memory_capsule",
            "state": "awake",
            "capsule_hash": awake_memory["capsule_hash"],
            "event_hash": "",
        },
    )

    peer_check = peer_check_all(args.owner, args.repo, token)
    append_event(
        events,
        {
            "event": "peer_check",
            "created_at": now(),
            "run_id": run_id,
            "ok": peer_check["ok"],
            "checked_count": peer_check["checked_count"],
            "event_hash": "",
        },
    )

    target_role = args.repair_target
    target_path = role_path(target_role)
    expected_role = next(item for item in registry["roles"] if item["role"] == target_role)
    expected_core_hash = expected_role["expected_core_hash"]
    delete_result = delete_json(args.owner, args.repo, token, target_path, f"F1 repair simulate missing {target_role} {run_id}")
    missing_wait = wait_for_missing(args.owner, args.repo, token, target_path)
    alive, alive_checks = collect_f1_alive(args.owner, args.repo, token, target_role)
    quorum = quorum_votes(alive, target_role, expected_core_hash, int(registry["quorum_threshold"]))
    blueprint = registry["rebuild_blueprints"][target_role]
    repaired = transition_capsule(blueprint, "repair", "repaired", run_id, {"repaired_from": "registry_blueprint"})
    repair_write: dict[str, Any] = {}
    repair_check: dict[str, Any] = {}
    if missing_wait.get("ok") and quorum["ok"] and verify_capsule(blueprint).get("ok"):
        repair_write = put_json(args.owner, args.repo, token, target_path, repaired, f"F1 repair {target_role} {run_id}")
        repair_check = verify_remote_hash(args.owner, args.repo, token, target_path, "capsule_hash")
    repair_ok = bool(delete_result.get("ok") and missing_wait.get("ok") and quorum["ok"] and repair_write.get("ok") and repair_check.get("ok"))
    repair = {
        "ok": repair_ok,
        "target_role": target_role,
        "delete_status": delete_result.get("status"),
        "confirmed_missing": bool(missing_wait.get("ok")),
        "alive_count": len(alive),
        "quorum": {
            "ok": quorum["ok"],
            "threshold": quorum["threshold"],
            "agree_count": quorum["agree_count"],
        },
        "repaired_core_hash": repaired.get("core_hash"),
        "repaired_capsule_hash": repaired.get("capsule_hash"),
    }
    append_event(
        events,
        {
            "event": "repair",
            "created_at": now(),
            "run_id": run_id,
            "ok": repair_ok,
            "target_role": target_role,
            "confirmed_missing": bool(missing_wait.get("ok")),
            "agree_count": quorum["agree_count"],
            "threshold": quorum["threshold"],
            "repaired_capsule_hash": repaired.get("capsule_hash"),
            "event_hash": "",
        },
    )

    repair_parent, repair_parent_response = read_capsule(args.owner, args.repo, token, "repair_capsule")
    split_parent = transition_capsule(repair_parent or {}, "split", "awake", run_id, {"last_child_role": SPLIT_CHILD_ROLE})
    split_parent_write = put_json(args.owner, args.repo, token, role_path("repair_capsule"), split_parent, f"F1 split parent repair_capsule {run_id}")
    child = build_split_child(split_parent, run_id)
    child_write = put_json(args.owner, args.repo, token, SPLIT_CHILD_PATH, child, f"F1 split child {run_id}")
    child_check = verify_remote_hash(args.owner, args.repo, token, SPLIT_CHILD_PATH, "capsule_hash")
    split_ok = bool(repair_parent_response.get("ok") and split_parent_write.get("ok") and child_write.get("ok") and child_check.get("ok"))
    split = {
        "ok": split_ok,
        "parent_role": "repair_capsule",
        "child_role": SPLIT_CHILD_ROLE,
        "child_path": SPLIT_CHILD_PATH,
        "child_core_hash": child["core_hash"],
        "child_capsule_hash": child["capsule_hash"],
    }
    append_event(
        events,
        {
            "event": "split",
            "created_at": now(),
            "run_id": run_id,
            "ok": split_ok,
            "parent_role": "repair_capsule",
            "child_role": SPLIT_CHILD_ROLE,
            "child_capsule_hash": child["capsule_hash"],
            "event_hash": "",
        },
    )

    child_payload, child_response = content_get(args.owner, args.repo, SPLIT_CHILD_PATH, token)[0::2]
    decayed_child = transition_capsule(child_payload or {}, "decay", "decayed", run_id)
    decay_write = put_json(args.owner, args.repo, token, SPLIT_CHILD_PATH, decayed_child, f"F1 decay child {run_id}")
    decay_check = verify_remote_hash(args.owner, args.repo, token, SPLIT_CHILD_PATH, "capsule_hash")
    decay_ok = bool(child_response.get("ok") and decay_write.get("ok") and decay_check.get("ok"))
    decay = {
        "ok": decay_ok,
        "child_role": SPLIT_CHILD_ROLE,
        "state": "decayed",
        "vitality": decayed_child["lifecycle"]["vitality"],
        "child_capsule_hash": decayed_child["capsule_hash"],
    }
    append_event(
        events,
        {
            "event": "decay",
            "created_at": now(),
            "run_id": run_id,
            "ok": decay_ok,
            "child_role": SPLIT_CHILD_ROLE,
            "state": "decayed",
            "vitality": decayed_child["lifecycle"]["vitality"],
            "event_hash": "",
        },
    )

    child_payload, child_response_tuple_sha, child_response = content_get(args.owner, args.repo, SPLIT_CHILD_PATH, token)
    retired_child = transition_capsule(child_payload or {}, "retire", "retired", run_id)
    retire_write = put_json(args.owner, args.repo, token, SPLIT_CHILD_PATH, retired_child, f"F1 retire child {run_id}")
    retire_check = verify_remote_hash(args.owner, args.repo, token, SPLIT_CHILD_PATH, "capsule_hash")
    retire_ok = bool(child_response.get("ok") and retire_write.get("ok") and retire_check.get("ok") and retired_child["lifecycle"]["retired"])
    retire = {
        "ok": retire_ok,
        "child_role": SPLIT_CHILD_ROLE,
        "final_state": retired_child["lifecycle"]["state"],
        "retired": retired_child["lifecycle"]["retired"],
        "vitality": retired_child["lifecycle"]["vitality"],
        "child_capsule_hash": retired_child["capsule_hash"],
    }
    append_event(
        events,
        {
            "event": "retire",
            "created_at": now(),
            "run_id": run_id,
            "ok": retire_ok,
            "child_role": SPLIT_CHILD_ROLE,
            "state": "retired",
            "retired": True,
            "event_hash": "",
        },
    )

    capsule_status: dict[str, Any] = {}
    for role in ROLE_ORDER + [SPLIT_CHILD_ROLE]:
        path = SPLIT_CHILD_PATH if role == SPLIT_CHILD_ROLE else role_path(role)
        payload, _, response = content_get(args.owner, args.repo, path, token)
        check = verify_capsule(payload)
        lifecycle = payload.get("lifecycle") if isinstance(payload, dict) and isinstance(payload.get("lifecycle"), dict) else {}
        capsule_status[role] = {
            "path": path,
            "read_status": response.get("status"),
            "hash_ok": check.get("ok"),
            "state": lifecycle.get("state"),
            "retired": lifecycle.get("retired"),
            "vitality": lifecycle.get("vitality"),
            "capsule_hash": payload.get("capsule_hash") if isinstance(payload, dict) else "",
        }

    state = build_state(run_id, args.mode, generation, events, capsule_status)
    state_write = put_json(args.owner, args.repo, token, STATE_PATH, state, f"F1 lifecycle state {run_id}")
    state_check = verify_remote_hash(args.owner, args.repo, token, STATE_PATH, "state_hash")
    run_entry = {
        "stage": "F1-lifecycle-ledger-entry",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "generation": generation,
        "event_order": [event["event"] for event in events],
        "event_hashes": [event["event_hash"] for event in events],
        "event_count": len(events),
        "all_events_ok": all(event.get("ok") for event in events),
        "state_hash": state["state_hash"],
        "entry_hash": "",
    }
    ledger, ledger_write = append_ledger(args.owner, args.repo, token, run_id, args.mode, run_entry)

    raw_child_check: dict[str, Any] = {}
    if args.raw_check and retire_write.get("commit_hash"):
        sample = fetch_json_url(raw_url(args.owner, args.repo, str(retire_write["commit_hash"]), SPLIT_CHILD_PATH), "f1-retired-child-raw")
        payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
        raw_child_check = {
            "ok": bool(sample.get("ok") and payload.get("capsule_hash") == retired_child["capsule_hash"]),
            "status": sample.get("status"),
            "observed_capsule_hash": payload.get("capsule_hash"),
            "expected_capsule_hash": retired_child["capsule_hash"],
            "error": sample.get("error"),
        }

    event_order = [event["event"] for event in events]
    core_ok = bool(
        all(event.get("ok") for event in events)
        and state_write.get("ok")
        and state_check.get("ok")
        and ledger_write.get("ok")
        and all(item.get("hash_ok") for item in capsule_status.values())
    )
    if args.raw_check:
        core_ok = bool(core_ok and raw_child_check.get("ok"))
    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "F1-capsule-lifecycle",
        "ok": core_ok,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "generation": generation,
        "paths": {
            "capsules": CAPSULE_DIR,
            "registry": REGISTRY_PATH,
            "state": STATE_PATH,
            "ledger": LEDGER_PATH,
            "last_run": LAST_RUN_PATH,
            "last_report": LAST_REPORT_PATH,
        },
        "seed": {
            "writes": seed_writes,
            "checks": seed_checks,
            "registry_write": registry_write,
            "registry_check": registry_check,
        },
        "events": events,
        "peer_check": peer_check,
        "repair": repair,
        "split": split,
        "decay": decay,
        "retire": retire,
        "state": {
            "state_hash": state["state_hash"],
            "write": state_write,
            "verify": state_check,
        },
        "ledger": {
            "ledger_hash": ledger["ledger_hash"],
            "entry_count": ledger["entry_count"],
            "write": ledger_write,
        },
        "raw_child_check": raw_child_check,
        "lifecycle_summary": {
            "event_order": event_order,
            "event_count": len(events),
            "all_events_ok": all(event.get("ok") for event in events),
            "capsule_status": capsule_status,
        },
        "evidence_level": "F1-capsule-lifecycle-v0" if core_ok else "F1-capsule-lifecycle-partial",
        "conclusion": "F1 defines and verifies a minimal remote capsule lifecycle chain: birth, sleep, wake, peer_check, repair, split, decay, and retire.",
        "truth_boundary": (
            "F1 proves lifecycle state transitions over mutable remote anchors. It does not prove endpoint-free existence, "
            "CPU-free network computation, self-executing capsules, or fully autonomous digital life."
        ),
    }
    last_run = build_last_run(result)
    last_report = build_last_report(result)
    last_run_write = put_json(args.owner, args.repo, token, LAST_RUN_PATH, last_run, f"F1 last run {run_id}")
    last_report_write = put_json(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, f"F1 last report {run_id}")
    result["last_run"] = last_run
    result["last_report"] = last_report
    result["writes"] = {"last_run": last_run_write, "last_report": last_report_write}
    result["ok"] = bool(result["ok"] and last_run_write.get("ok") and last_report_write.get("ok"))
    result["evidence_level"] = "F1-capsule-lifecycle-v0" if result["ok"] else "F1-capsule-lifecycle-partial"
    write_local(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "evidence_level": result["evidence_level"],
                "event_order": event_order,
                "repair_ok": repair["ok"],
                "split_ok": split["ok"],
                "decay_ok": decay["ok"],
                "retire_ok": retire["ok"],
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
