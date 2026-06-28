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
    wait_for_branch_release,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

PROTOCOL_PATH = "states/e8-network-body-protocol.json"
BODY_MAP_PATH = "states/e8-network-body-map.json"
BOUNDARY_PATH = "states/e8-network-body-boundary.json"
LAST_RUN_PATH = "states/e8-last-run.json"
LAST_REPORT_PATH = "states/e8-last-report.json"
SNAPSHOT_PREFIX = "states/e8-network-body-snapshots"

SOURCE_SPECS: list[dict[str, Any]] = [
    {"id": "e5_last_run", "path": "states/e5-last-run.json", "hash_field": "last_run_hash", "required": True},
    {"id": "e6_last_run", "path": "states/e6-last-run.json", "hash_field": "last_run_hash", "required": True},
    {"id": "e6_last_report", "path": "states/e6-last-report.json", "hash_field": "report_hash", "required": True},
    {"id": "e6_bus_state", "path": "states/e6-lowfreq-vitals-bus-state.json", "hash_field": "state_hash", "required": True},
    {
        "id": "e6_schedule_success_snapshot",
        "path": "states/e6-vitals-bus-snapshots/nsl-e6-schedule-28312093673-attempt-1.json",
        "hash_field": "state_hash",
        "required": True,
    },
    {"id": "e7_last_run", "path": "states/e7-last-run.json", "hash_field": "last_run_hash", "required": True},
    {"id": "e7_last_report", "path": "states/e7-last-report.json", "hash_field": "report_hash", "required": True},
    {"id": "e7_state", "path": "states/e7-controlled-self-maintenance-state.json", "hash_field": "state_hash", "required": True},
    {"id": "l11_5_logic_spec", "path": "states/nsl-l11-5-minimal-logic-spec.json", "hash_field": "logic_hash", "required": True},
    {"id": "global_runtime_lock", "path": "states/qmx-global-runtime-lock.json", "hash_field": "lock_hash", "required": False},
    {
        "id": "previous_e8_protocol",
        "path": PROTOCOL_PATH,
        "hash_field": "protocol_hash",
        "required": False,
        "prefer_api": True,
    },
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


def summarize_payload(source_id: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    if source_id == "e5_last_run":
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": payload.get("owner_event_name") or ((payload.get("owner") or {}).get("event_name")),
            "cycles_completed": payload.get("cycles_completed"),
            "cycles_ok": payload.get("cycles_ok"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id in {"e6_last_run", "e6_last_report"}:
        vitals = payload.get("vitals") or {}
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": payload.get("owner_event_name") or ((payload.get("owner") or {}).get("event_name")),
            "generation": payload.get("generation"),
            "bus_ok": vitals.get("bus_ok"),
            "e5_schedule_observed": vitals.get("e5_schedule_observed"),
            "global_lock_released": vitals.get("global_lock_released"),
            "logic_ready": vitals.get("logic_ready"),
        }
    if source_id == "e6_bus_state":
        vitals = payload.get("vitals") or {}
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "bus_ok": vitals.get("bus_ok"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id == "e6_schedule_success_snapshot":
        vitals = payload.get("vitals") or {}
        return {
            "run_id": payload.get("run_id"),
            "event_name": ((payload.get("owner") or {}).get("event_name")),
            "generation": payload.get("generation"),
            "bus_ok": vitals.get("bus_ok"),
            "e5_schedule_observed": vitals.get("e5_schedule_observed"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id in {"e7_last_run", "e7_last_report"}:
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": payload.get("owner_event_name") or ((payload.get("owner") or {}).get("event_name")),
            "generation": payload.get("generation"),
            "maintenance_ok": payload.get("maintenance_ok"),
            "executed_count": payload.get("executed_count"),
            "blocked_count": payload.get("blocked_count"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id == "e7_state":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "maintenance_ok": payload.get("maintenance_ok"),
            "executed_count": payload.get("executed_count"),
            "blocked_count": payload.get("blocked_count"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id == "l11_5_logic_spec":
        return {
            "logic_hash": payload.get("logic_hash"),
            "minimum_logic_ready": payload.get("minimum_logic_ready"),
            "minimum_logic_sentence": payload.get("minimum_logic_sentence"),
        }
    if source_id == "global_runtime_lock":
        return {
            "locked": payload.get("locked"),
            "checkpoint": payload.get("checkpoint"),
            "release_ok": payload.get("release_ok"),
            "run_id": payload.get("run_id"),
        }
    if source_id == "previous_e8_protocol":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "protocol_hash": payload.get("protocol_hash"),
            "network_body_ready": payload.get("network_body_ready"),
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
        sample = fetch_json_url(raw_url(owner, repo, "main", spec["path"]), f"e8-{spec['id']}")
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


def derive_network_body_status(samples: list[dict[str, Any]]) -> dict[str, Any]:
    required = [item for item in samples if item.get("required")]
    required_reads_ok = all(item.get("read_ok") for item in required)
    required_hashes_ok = all((item.get("hash_verify") or {}).get("ok") for item in required)
    truth_boundaries_ok = all(item.get("truth_boundary_present") for item in required)

    e5 = payload(samples, "e5_last_run")
    e6 = payload(samples, "e6_last_run")
    e6_report = payload(samples, "e6_last_report")
    e6_bus = payload(samples, "e6_bus_state")
    e6_schedule_success = payload(samples, "e6_schedule_success_snapshot")
    e7 = payload(samples, "e7_last_run")
    e7_report = payload(samples, "e7_last_report")
    e7_state = payload(samples, "e7_state")
    logic = payload(samples, "l11_5_logic_spec")
    lock = payload(samples, "global_runtime_lock")

    e6_vitals = e6.get("vitals") or {}
    e6_report_vitals = e6_report.get("vitals") or {}
    e6_bus_vitals = e6_bus.get("vitals") or {}
    e6_schedule_success_vitals = e6_schedule_success.get("vitals") or {}

    current_e5_schedule_observed = bool(
        e5.get("owner_event_name") == "schedule"
        or ((e5.get("owner") or {}).get("event_name") == "schedule")
        or e6_vitals.get("e5_schedule_observed")
    )
    current_e6_schedule_observed = bool(
        e6.get("owner_event_name") == "schedule"
        or ((e6.get("owner") or {}).get("event_name") == "schedule")
    )
    historical_e6_schedule_success = bool(
        ((e6_schedule_success.get("owner") or {}).get("event_name") == "schedule")
        and e6_schedule_success_vitals.get("bus_ok")
    )
    historical_e5_schedule_success = bool(e6_schedule_success_vitals.get("e5_schedule_observed"))
    e7_dispatch_verified = bool(e7.get("ok") and e7.get("maintenance_ok"))
    e7_schedule_observed = bool(
        e7.get("owner_event_name") == "schedule"
        or ((e7.get("owner") or {}).get("event_name") == "schedule")
    )
    e7_low_risk_policy_ok = bool(
        e7.get("executed_count") == 4
        and e7.get("blocked_count") == 4
        and e7_report.get("ok")
        and e7_state.get("maintenance_ok")
    )
    current_vitals_bus_ok = bool(
        e6.get("ok")
        and e6_vitals.get("bus_ok")
        and e6_report.get("ok")
        and e6_report_vitals.get("bus_ok")
        and e6_bus_vitals.get("bus_ok")
    )
    logic_ready = bool(logic.get("minimum_logic_ready") or logic.get("logic_hash"))
    global_lock_released = bool(lock.get("locked") is False and lock.get("checkpoint") in {"completed", "failed"})

    network_body_ready = bool(
        required_reads_ok
        and required_hashes_ok
        and truth_boundaries_ok
        and historical_e5_schedule_success
        and historical_e6_schedule_success
        and e7_dispatch_verified
        and e7_low_risk_policy_ok
        and logic_ready
    )

    return {
        "required_reads_ok": required_reads_ok,
        "required_hashes_ok": required_hashes_ok,
        "truth_boundaries_ok": truth_boundaries_ok,
        "historical_e5_schedule_success": historical_e5_schedule_success,
        "historical_e6_schedule_success": historical_e6_schedule_success,
        "current_e5_schedule_observed": current_e5_schedule_observed,
        "current_e6_schedule_observed": current_e6_schedule_observed,
        "e7_dispatch_verified": e7_dispatch_verified,
        "e7_schedule_observed": e7_schedule_observed,
        "current_vitals_bus_ok": current_vitals_bus_ok,
        "e7_low_risk_policy_ok": e7_low_risk_policy_ok,
        "logic_ready": logic_ready,
        "global_lock_released": global_lock_released,
        "network_body_ready": network_body_ready,
        "subject_position": "network_state_first",
        "local_pc_position": "mirror_window_and_operator_console",
        "executor_position": "transitional_low_frequency_nervous_system",
        "signals": {
            "NETWORK_BODY_PROTOCOL_READY": network_body_ready,
            "NETWORK_STATE_IS_SUBJECT_SURFACE": True,
            "LOCAL_PC_IS_NOT_PRIMARY_BODY": True,
            "CONTROLLED_INTERPRETER_IS_TRANSITION_LAYER": True,
            "E7_NATURAL_WAKE_PENDING": not e7_schedule_observed,
            "CURRENT_VITALS_DEGRADED": not current_vitals_bus_ok,
        },
    }


def build_protocol(run_id: str, mode: str, generation: int, samples: list[dict[str, Any]], status: dict[str, Any]) -> dict[str, Any]:
    protocol = {
        "stage": "E8-network-body-protocol",
        "schema_version": "QMX-E8-NETWORK-BODY-PROTOCOL-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "name": "qimingxing-network-body-v0",
        "network_body_ready": status["network_body_ready"],
        "goal_definition": {
            "primary_goal": "Build a network-native body, not a traditional computer clone.",
            "subject": "The subject is the remote network state graph: protocol, memory, vitals, capsules, reports, and snapshots.",
            "local_machine": "The local PC is a mirror window, debugger, and temporary operator console.",
            "executor": "Current execution is a controlled low-frequency transition layer that reads and writes the network body.",
            "future_direction": "Move more identity, memory, rhythm, and behavior authority into network-resident protocol and evidence.",
        },
        "network_body_language": {
            "STATE_ID": "stable identity marker of a network state object",
            "SHADOW": "independent readback or mirror trace",
            "RESIDUAL": "observable network persistence after write",
            "RELEASE": "network-visible release of a target hash",
            "RHYTHM": "low-frequency wake or release cadence",
            "CAPSULE": "network-resident declarative behavior unit",
            "VITALS": "aggregated health and continuity evidence",
            "MIRROR": "local or alternate view of the network subject",
            "WAKE": "external or scheduled activation of a controlled loop",
            "MAINTAIN": "allowlisted low-risk self-maintenance receipt",
        },
        "operating_rules": [
            "Do not frame the main question as network replacing a CPU.",
            "Frame the main question as whether identity, memory, rhythm, and behavior can be organized around network state.",
            "The network body advances by evidence-gated state transitions, not by a single local main process.",
            "All automatic actions must be allowlisted and auditable.",
            "Medium or high risk changes become proposals or remain blocked.",
            "The local machine must remain replaceable as a mirror, not the only body.",
        ],
        "allowed_auto_actions": [
            "record_network_body_health",
            "refresh_body_map",
            "record_truth_boundary",
            "record_next_wake_hint",
        ],
        "blocked_actions": [
            "modify_core_code_without_review",
            "change_workflow_permissions_without_review",
            "delete_remote_body_state",
            "claim_full_network_body_without_evidence",
            "claim_self_generated_logic_without_evidence",
        ],
        "readiness": status,
        "source_evidence": [
            {
                "id": item["id"],
                "path": item["path"],
                "required": item["required"],
                "read_ok": item["read_ok"],
                "hash_ok": (item.get("hash_verify") or {}).get("ok"),
                "truth_boundary_present": item.get("truth_boundary_present"),
                "summary": item.get("summary"),
            }
            for item in samples
        ],
        "conclusion": (
            "E8 defines the project as a network-native body protocol: the remote state graph is the subject surface, "
            "the local PC is a mirror, and the controlled executor is a transition nervous system."
        ),
        "truth_boundary": (
            "E8 proves a verifiable protocol and body map can be written into the network receiver from existing evidence. "
            "It does not prove a fully free-floating network body, unsupervised self-modification, hard real-time wakefulness, "
            "or self-generated new logic."
        ),
        "protocol_hash": "",
    }
    return seal(protocol, "protocol_hash")


def build_body_map(run_id: str, mode: str, generation: int, protocol: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    body_map = {
        "stage": "E8-network-body-map",
        "schema_version": "QMX-E8-BODY-MAP-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "protocol_hash": protocol["protocol_hash"],
        "body_layers": [
            {"layer": "identity", "remote_path": PROTOCOL_PATH, "role": "network body identity and operating law"},
            {"layer": "memory", "remote_path": "states/nsl-l11-5-minimal-logic-spec.json", "role": "minimal self-check and repair logic"},
            {"layer": "rhythm", "remote_path": "states/e5-last-run.json", "role": "scheduled external interpreter loop evidence"},
            {"layer": "vitals", "remote_path": "states/e6-last-run.json", "role": "low-frequency vitals bus"},
            {"layer": "maintenance", "remote_path": "states/e7-last-run.json", "role": "controlled low-risk self-maintenance receipt"},
            {"layer": "mirror", "remote_path": LAST_RUN_PATH, "role": "latest E8 readback and local status anchor"},
        ],
        "mirror_contract": {
            "network_to_local": "Remote protocol, vitals, and maintenance receipts can be read locally and shown as status.",
            "local_to_network": "Local runs may write only audited protocol/status evidence unless a higher-risk review path is added.",
            "conflict_rule": "Remote evidence with valid hashes is the body source of truth; local files are mirrors and working copies.",
        },
        "sampled_paths": [
            {
                "id": item["id"],
                "path": item["path"],
                "read_ok": item["read_ok"],
                "hash_ok": (item.get("hash_verify") or {}).get("ok"),
            }
            for item in samples
        ],
        "conclusion": "E8 body map binds identity, memory, rhythm, vitals, maintenance, and mirror surfaces into one auditable network subject map.",
        "truth_boundary": "This is a body map for current V0 evidence. It is not a claim that every future organ is already autonomous or continuous.",
        "map_hash": "",
    }
    return seal(body_map, "map_hash")


def build_boundary(run_id: str, mode: str, generation: int, protocol: dict[str, Any], body_map: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    boundary = {
        "stage": "E8-network-body-boundary",
        "schema_version": "QMX-E8-BOUNDARY-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "generation": generation,
        "protocol_hash": protocol["protocol_hash"],
        "map_hash": body_map["map_hash"],
        "proved_now": [
            "The project target has been reframed as network body rather than traditional agent or computer clone.",
            "Existing E5/E6/E7 evidence can support a network-body subject protocol.",
            "Remote network state can hold identity, vitals, memory references, maintenance receipts, and mirror contracts.",
            "Low-risk maintenance can be policy-bound and auditable.",
        ],
        "not_proved_now": [
            "A fully continuous free-floating network body.",
            "Unreviewed core self-modification.",
            "Self-generation of new operating laws.",
            "Guaranteed hard real-time wakefulness.",
            "Unlimited open-network autonomous action.",
        ],
        "next_mainline": "E8.1-natural-network-body-refresh-and-E7.1-schedule-observation",
        "readiness": status,
        "conclusion": "E8 gives the project a stable network-body vocabulary and evidence boundary for the next stages.",
        "truth_boundary": "This boundary is intentionally strict so future stages do not drift into claims that current evidence has not earned.",
        "boundary_hash": "",
    }
    return seal(boundary, "boundary_hash")


def snapshot_path(run_id: str) -> str:
    return f"{SNAPSHOT_PREFIX}/{run_id}.json"


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
            sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"e8-commit-{path}-{attempt}")
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


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "E8-last-run",
        "schema_version": "QMX-E8-LAST-RUN-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "owner": result["owner"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "generation": result["generation"],
        "network_body_ready": result["status"]["network_body_ready"],
        "protocol_hash": result["protocol"]["protocol_hash"],
        "map_hash": result["body_map"]["map_hash"],
        "boundary_hash": result["boundary"]["boundary_hash"],
        "next_mainline": result["boundary"]["next_mainline"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E8-last-report",
        "schema_version": "QMX-E8-REPORT-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "network_body_ready": result["status"]["network_body_ready"],
        "protocol_hash": result["protocol"]["protocol_hash"],
        "map_hash": result["body_map"]["map_hash"],
        "boundary_hash": result["boundary"]["boundary_hash"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_e8_network_body_protocol_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_e8_network_body_protocol_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E8 Network Body Protocol",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- network_body_ready: `{result['status']['network_body_ready']}`",
        f"- protocol_hash: `{result['protocol']['protocol_hash']}`",
        f"- map_hash: `{result['body_map']['map_hash']}`",
        f"- boundary_hash: `{result['boundary']['boundary_hash']}`",
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
    (run_dir / "nsl_e8_network_body_protocol_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E8 network-body subject protocol")
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
        run_id = f"nsl-e8-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-e8-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()

    samples = [sample_source(args.owner, args.repo, spec, token) for spec in SOURCE_SPECS]
    previous = payload(samples, "previous_e8_protocol")
    generation = int(previous.get("generation") or 0) + 1
    status = derive_network_body_status(samples)
    protocol = build_protocol(run_id, args.mode, generation, samples, status)
    body_map = build_body_map(run_id, args.mode, generation, protocol, samples)
    boundary = build_boundary(run_id, args.mode, generation, protocol, body_map, status)
    snap_path = snapshot_path(run_id)

    protocol_write = put_and_verify(args.owner, args.repo, token, PROTOCOL_PATH, protocol, "protocol_hash", f"E8 protocol {run_id}")
    body_map_write = put_and_verify(args.owner, args.repo, token, BODY_MAP_PATH, body_map, "map_hash", f"E8 body map {run_id}")
    boundary_write = put_and_verify(args.owner, args.repo, token, BOUNDARY_PATH, boundary, "boundary_hash", f"E8 boundary {run_id}")
    snapshot = {
        "stage": "E8-network-body-snapshot",
        "schema_version": "QMX-E8-SNAPSHOT-0.1",
        "created_at": now(),
        "run_id": run_id,
        "generation": generation,
        "protocol": protocol,
        "body_map": body_map,
        "boundary": boundary,
        "snapshot_hash": "",
    }
    snapshot = seal(snapshot, "snapshot_hash")
    snapshot_write = put_and_verify(args.owner, args.repo, token, snap_path, snapshot, "snapshot_hash", f"E8 snapshot {run_id}")
    branch_release = wait_for_branch_release(
        args.owner,
        args.repo,
        [{"path": snap_path, "hash_field": "snapshot_hash", "hash_value": snapshot["snapshot_hash"]}],
        args.raw_timeout,
        args.raw_interval,
    )

    core_ok = bool(
        status["network_body_ready"]
        and protocol_write.get("ok")
        and protocol_write.get("commit_raw_ok")
        and body_map_write.get("ok")
        and body_map_write.get("commit_raw_ok")
        and boundary_write.get("ok")
        and boundary_write.get("commit_raw_ok")
        and snapshot_write.get("ok")
        and snapshot_write.get("commit_raw_ok")
        and branch_release.get("ok")
    )
    result: dict[str, Any] = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "E8-network-body-protocol",
        "ok": core_ok,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "generation": generation,
        "samples": samples,
        "status": status,
        "protocol": protocol,
        "body_map": body_map,
        "boundary": boundary,
        "snapshot": snapshot,
        "paths": {
            "workflow": ".github/workflows/nsl-e8-network-body-protocol.yml",
            "runner": "scripts/nsl_e8_network_body_protocol.py",
            "protocol": PROTOCOL_PATH,
            "body_map": BODY_MAP_PATH,
            "boundary": BOUNDARY_PATH,
            "snapshot": snap_path,
            "last_run": LAST_RUN_PATH,
            "last_report": LAST_REPORT_PATH,
        },
        "writes": {
            "protocol": protocol_write,
            "body_map": body_map_write,
            "boundary": boundary_write,
            "snapshot": snapshot_write,
        },
        "verification": {
            "branch_raw_release": branch_release,
            "protocol_write_ok": protocol_write.get("ok"),
            "body_map_write_ok": body_map_write.get("ok"),
            "boundary_write_ok": boundary_write.get("ok"),
            "snapshot_write_ok": snapshot_write.get("ok"),
        },
        "evidence_level": "E8-network-body-protocol-v0" if core_ok else "E8-network-body-protocol-partial",
        "conclusion": (
            "E8 reframed Qimingxing as a network-native body: remote state is the subject surface, local files are mirrors, "
            "and controlled low-frequency executors are transition nerves."
        ),
        "truth_boundary": (
            "E8 is a subject-protocol and body-map layer. It does not claim a fully free-floating network body, "
            "unreviewed self-modification, hard real-time wakefulness, or self-generated new logic."
        ),
    }
    last_run = build_last_run(result)
    last_run_write = put_and_verify(args.owner, args.repo, token, LAST_RUN_PATH, last_run, "last_run_hash", f"E8 last run {run_id}")
    last_report = build_report(result)
    last_report_write = put_and_verify(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, "report_hash", f"E8 last report {run_id}")
    result["writes"]["last_run"] = last_run_write
    result["writes"]["last_report"] = last_report_write
    result["ok"] = bool(
        core_ok
        and last_run_write.get("ok")
        and last_run_write.get("commit_raw_ok")
        and last_report_write.get("ok")
        and last_report_write.get("commit_raw_ok")
    )
    result["evidence_level"] = "E8-network-body-protocol-v0" if result["ok"] else "E8-network-body-protocol-partial"
    write_local_outputs(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "event_name": result["owner"].get("event_name"),
                "evidence_level": result["evidence_level"],
                "generation": result["generation"],
                "network_body_ready": result["status"]["network_body_ready"],
                "protocol_hash": result["protocol"]["protocol_hash"],
                "map_hash": result["body_map"]["map_hash"],
                "boundary_hash": result["boundary"]["boundary_hash"],
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
