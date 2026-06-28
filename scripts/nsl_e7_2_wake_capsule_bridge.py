from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
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

EVENT_TYPE = "qmx_e7_wake_capsule"
TARGET_WORKFLOW = ".github/workflows/nsl-e7-2-wake-capsule-dispatch.yml"
WORKFLOW_FILE = "nsl-e7-2-wake-capsule-dispatch.yml"

CAPSULE_PATH = "states/e7-2-wake-capsule.json"
BRIDGE_STATE_PATH = "states/e7-2-wake-bridge-state.json"
LAST_RUN_PATH = "states/e7-2-last-run.json"
LAST_REPORT_PATH = "states/e7-2-last-report.json"
SNAPSHOT_PREFIX = "states/e7-2-wake-capsule-snapshots"


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


def future(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=float(seconds))).isoformat()


def past(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=float(seconds))).isoformat()


def snapshot_path(run_id: str) -> str:
    return f"{SNAPSHOT_PREFIX}/{run_id}.json"


def build_wake_capsule(run_id: str, mode: str, owner: str, repo: str, ttl_seconds: int) -> dict[str, Any]:
    nonce = "e72-" + uuid.uuid4().hex
    capsule = {
        "stage": "E7.2-wake-capsule",
        "schema_version": "QMX-E7.2-WAKE-CAPSULE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "capsule_id": "e72cap-" + nonce[-16:],
        "capsule_type": "qmx_network_wake_intent",
        "target": "E7-controlled-low-risk-self-maintenance",
        "target_repo": f"{owner}/{repo}",
        "event_type": EVENT_TYPE,
        "receiver_workflow": TARGET_WORKFLOW,
        "wake_after": past(5),
        "expires_at": future(ttl_seconds),
        "ttl_seconds": ttl_seconds,
        "risk_level": "low",
        "allowed_action": "run_e7_controlled_self_maintenance",
        "nonce": nonce,
        "one_time": True,
        "direct_body_execution": False,
        "client_payload": {
            "capsule_path": CAPSULE_PATH,
            "requested_stage": "E7.2",
            "intent": "wake_e7_from_network_capsule",
        },
        "policy": {
            "allowed_event_types": [EVENT_TYPE],
            "allowed_targets": ["E7-controlled-low-risk-self-maintenance"],
            "allowed_actions": ["run_e7_controlled_self_maintenance"],
            "blocked_actions": [
                "modify_core_code",
                "change_permissions",
                "delete_remote_state",
                "execute_capsule_body_directly",
            ],
        },
        "conclusion": "This capsule is a network-resident wake intent. A bridge may validate it and trigger GitHub repository_dispatch.",
        "truth_boundary": (
            "The wake capsule does not execute by itself. It becomes active only when an external bridge reads, validates, "
            "and dispatches it to GitHub."
        ),
        "capsule_hash": "",
    }
    return seal(capsule, "capsule_hash")


def validate_capsule(capsule: dict[str, Any] | None, expected_repo: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "ok": bool(ok), "detail": detail})

    if not capsule:
        return {"ok": False, "checks": [{"id": "capsule_present", "ok": False, "detail": "missing capsule"}]}

    observed_hash = stable_hash(capsule, "capsule_hash")
    expected_hash = str(capsule.get("capsule_hash") or "")
    now_dt = datetime.now(timezone.utc)
    wake_after = parse_time(capsule.get("wake_after"))
    expires_at = parse_time(capsule.get("expires_at"))

    add("hash_ok", bool(expected_hash and expected_hash == observed_hash), f"expected={expected_hash} observed={observed_hash}")
    add("capsule_type_ok", capsule.get("capsule_type") == "qmx_network_wake_intent", str(capsule.get("capsule_type")))
    add("event_type_ok", capsule.get("event_type") == EVENT_TYPE, str(capsule.get("event_type")))
    add("target_ok", capsule.get("target") == "E7-controlled-low-risk-self-maintenance", str(capsule.get("target")))
    add("target_repo_ok", capsule.get("target_repo") == expected_repo, str(capsule.get("target_repo")))
    add("risk_level_ok", capsule.get("risk_level") == "low", str(capsule.get("risk_level")))
    add("allowed_action_ok", capsule.get("allowed_action") == "run_e7_controlled_self_maintenance", str(capsule.get("allowed_action")))
    add("one_time_ok", capsule.get("one_time") is True, str(capsule.get("one_time")))
    add("no_direct_body_execution", capsule.get("direct_body_execution") is False, str(capsule.get("direct_body_execution")))
    add("wake_window_open", bool(wake_after and wake_after <= now_dt), str(capsule.get("wake_after")))
    add("not_expired", bool(expires_at and now_dt <= expires_at), str(capsule.get("expires_at")))
    add("truth_boundary_present", bool(capsule.get("truth_boundary")), "truth boundary present")

    return {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "observed_hash": observed_hash,
        "expected_hash": expected_hash,
    }


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
            sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"e7-2-commit-{path}-{attempt}")
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


def dispatch_capsule(owner: str, repo: str, token: str, capsule: dict[str, Any], run_id: str) -> dict[str, Any]:
    payload = {
        "event_type": EVENT_TYPE,
        "client_payload": {
            "capsule_id": capsule["capsule_id"],
            "capsule_hash": capsule["capsule_hash"],
            "capsule_path": CAPSULE_PATH,
            "bridge_run_id": run_id,
            "nonce": capsule["nonce"],
            "intent": "wake_e7_from_network_capsule",
        },
    }
    response = api_request(owner, repo, "POST", "/dispatches", token, payload)
    return {
        "ok": bool(response.get("ok") and response.get("status") in {200, 201, 202, 204}),
        "status": response.get("status"),
        "elapsed_ms": response.get("elapsed_ms"),
        "error": response.get("error"),
        "payload": payload,
        "response_payload": response.get("payload"),
    }


def poll_receiver_run(owner: str, repo: str, token: str, started_at: datetime, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    latest: dict[str, Any] = {}
    while time.time() < deadline:
        response = api_request(
            owner,
            repo,
            "GET",
            f"/actions/workflows/{WORKFLOW_FILE}/runs?event=repository_dispatch&per_page=10",
            token,
        )
        runs = []
        if isinstance(response.get("payload"), dict):
            runs = response["payload"].get("workflow_runs") or []
        candidates: list[dict[str, Any]] = []
        for item in runs:
            created_at = parse_time(item.get("created_at"))
            if created_at and created_at >= started_at - timedelta(seconds=20):
                candidates.append(item)
        if candidates:
            latest = candidates[0]
            if latest.get("status") == "completed":
                return {
                    "ok": latest.get("conclusion") == "success",
                    "found": True,
                    "completed": True,
                    "workflow_run_id": latest.get("id"),
                    "status": latest.get("status"),
                    "conclusion": latest.get("conclusion"),
                    "event": latest.get("event"),
                    "html_url": latest.get("html_url"),
                    "created_at": latest.get("created_at"),
                    "updated_at": latest.get("updated_at"),
                }
        time.sleep(5.0)
    return {
        "ok": False,
        "found": bool(latest),
        "completed": latest.get("status") == "completed" if latest else False,
        "workflow_run_id": latest.get("id") if latest else None,
        "status": latest.get("status") if latest else None,
        "conclusion": latest.get("conclusion") if latest else None,
        "event": latest.get("event") if latest else None,
        "html_url": latest.get("html_url") if latest else None,
        "timed_out": True,
    }


def build_bridge_state(
    run_id: str,
    mode: str,
    capsule: dict[str, Any],
    validation: dict[str, Any],
    dispatch: dict[str, Any],
    receiver: dict[str, Any],
) -> dict[str, Any]:
    state = {
        "stage": "E7.2-wake-capsule-bridge-state",
        "schema_version": "QMX-E7.2-BRIDGE-STATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "capsule_id": capsule.get("capsule_id"),
        "capsule_hash": capsule.get("capsule_hash"),
        "capsule_path": CAPSULE_PATH,
        "event_type": EVENT_TYPE,
        "validation_ok": validation.get("ok"),
        "dispatch_ok": dispatch.get("ok"),
        "receiver_ok": receiver.get("ok"),
        "receiver_workflow_run_id": receiver.get("workflow_run_id"),
        "receiver_event": receiver.get("event"),
        "receiver_conclusion": receiver.get("conclusion"),
        "bridge_ok": bool(validation.get("ok") and dispatch.get("ok") and receiver.get("ok")),
        "conclusion": "E7.2 bridge validated a network wake capsule and used it to trigger GitHub repository_dispatch.",
        "truth_boundary": (
            "The bridge is the active executor. The capsule is network-resident wake intent, not a self-executing process."
        ),
        "state_hash": "",
    }
    return seal(state, "state_hash")


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "E7.2-last-run",
        "schema_version": "QMX-E7.2-LAST-RUN-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "owner": result["owner"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "capsule_id": result["capsule"]["capsule_id"],
        "capsule_hash": result["capsule"]["capsule_hash"],
        "validation_ok": result["validation"]["ok"],
        "dispatch_ok": result["dispatch"]["ok"],
        "receiver_ok": result["receiver"]["ok"],
        "receiver_workflow_run_id": result["receiver"].get("workflow_run_id"),
        "receiver_event": result["receiver"].get("event"),
        "receiver_conclusion": result["receiver"].get("conclusion"),
        "bridge_state_hash": result["bridge_state"]["state_hash"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E7.2-last-report",
        "schema_version": "QMX-E7.2-REPORT-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "capsule_id": result["capsule"]["capsule_id"],
        "capsule_hash": result["capsule"]["capsule_hash"],
        "validation": result["validation"],
        "dispatch": {
            "ok": result["dispatch"]["ok"],
            "status": result["dispatch"]["status"],
            "error": result["dispatch"]["error"],
        },
        "receiver": result["receiver"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_e7_2_wake_capsule_bridge_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_e7_2_wake_capsule_bridge_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E7.2 Wake Capsule Bridge",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- capsule_id: `{result['capsule']['capsule_id']}`",
        f"- capsule_hash: `{result['capsule']['capsule_hash']}`",
        f"- validation_ok: `{result['validation']['ok']}`",
        f"- dispatch_ok: `{result['dispatch']['ok']}`",
        f"- receiver_ok: `{result['receiver']['ok']}`",
        f"- receiver_workflow_run_id: `{result['receiver'].get('workflow_run_id')}`",
        "",
        "## Truth Boundary",
        "",
        result["truth_boundary"],
        "",
    ]
    (run_dir / "nsl_e7_2_wake_capsule_bridge_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E7.2 wake capsule bridge")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--ttl-seconds", type=int, default=900)
    parser.add_argument("--receiver-timeout", type=int, default=240)
    parser.add_argument("--raw-timeout", type=int, default=120)
    parser.add_argument("--raw-interval", type=float, default=4.0)
    args = parser.parse_args()

    import os

    event = os.environ.get("GITHUB_EVENT_NAME") or "local"
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        run_id = f"nsl-e7-2-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-e7-2-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()
    started_at = datetime.now(timezone.utc)

    capsule = build_wake_capsule(run_id, args.mode, args.owner, args.repo, args.ttl_seconds)
    capsule_write = put_and_verify(args.owner, args.repo, token, CAPSULE_PATH, capsule, "capsule_hash", f"E7.2 wake capsule {run_id}")
    snapshot = {
        "stage": "E7.2-wake-capsule-snapshot",
        "schema_version": "QMX-E7.2-SNAPSHOT-0.1",
        "created_at": now(),
        "run_id": run_id,
        "capsule": capsule,
        "snapshot_hash": "",
    }
    snapshot = seal(snapshot, "snapshot_hash")
    snap_path = snapshot_path(run_id)
    snapshot_write = put_and_verify(args.owner, args.repo, token, snap_path, snapshot, "snapshot_hash", f"E7.2 wake capsule snapshot {run_id}")
    branch_release = wait_for_branch_release(
        args.owner,
        args.repo,
        [{"path": snap_path, "hash_field": "snapshot_hash", "hash_value": snapshot["snapshot_hash"]}],
        args.raw_timeout,
        args.raw_interval,
    )

    remote_capsule, _, _ = content_get(args.owner, args.repo, CAPSULE_PATH, token)
    validation = validate_capsule(remote_capsule, f"{args.owner}/{args.repo}")
    dispatch = dispatch_capsule(args.owner, args.repo, token, capsule, run_id) if validation.get("ok") else {"ok": False, "status": None, "error": "validation_failed"}
    receiver = poll_receiver_run(args.owner, args.repo, token, started_at, args.receiver_timeout) if dispatch.get("ok") else {"ok": False, "found": False, "error": "dispatch_failed"}

    bridge_state = build_bridge_state(run_id, args.mode, capsule, validation, dispatch, receiver)
    bridge_write = put_and_verify(args.owner, args.repo, token, BRIDGE_STATE_PATH, bridge_state, "state_hash", f"E7.2 bridge state {run_id}")

    core_ok = bool(
        capsule_write.get("ok")
        and capsule_write.get("commit_raw_ok")
        and snapshot_write.get("ok")
        and snapshot_write.get("commit_raw_ok")
        and branch_release.get("ok")
        and validation.get("ok")
        and dispatch.get("ok")
        and receiver.get("ok")
        and bridge_write.get("ok")
        and bridge_write.get("commit_raw_ok")
    )
    result: dict[str, Any] = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "E7.2-wake-capsule-bridge",
        "ok": core_ok,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "capsule": capsule,
        "validation": validation,
        "dispatch": dispatch,
        "receiver": receiver,
        "bridge_state": bridge_state,
        "paths": {
            "receiver_workflow": TARGET_WORKFLOW,
            "bridge_runner": "scripts/nsl_e7_2_wake_capsule_bridge.py",
            "capsule": CAPSULE_PATH,
            "bridge_state": BRIDGE_STATE_PATH,
            "snapshot": snap_path,
            "last_run": LAST_RUN_PATH,
            "last_report": LAST_REPORT_PATH,
        },
        "writes": {
            "capsule": capsule_write,
            "snapshot": snapshot_write,
            "bridge_state": bridge_write,
        },
        "verification": {
            "branch_raw_release": branch_release,
        },
        "evidence_level": "E7.2-wake-capsule-reverse-github-dispatch-v0" if core_ok else "E7.2-wake-capsule-reverse-github-dispatch-partial",
        "conclusion": (
            "E7.2 proved a network wake capsule can be validated by a bridge and used to trigger GitHub repository_dispatch."
            if core_ok
            else "E7.2 ran, but capsule validation, dispatch, receiver workflow, or writeback did not fully pass."
        ),
        "truth_boundary": (
            "The wake capsule is network-resident intent. It does not execute by itself; a bridge still performs the active dispatch."
        ),
    }
    last_run = build_last_run(result)
    last_run_write = put_and_verify(args.owner, args.repo, token, LAST_RUN_PATH, last_run, "last_run_hash", f"E7.2 last run {run_id}")
    last_report = build_report(result)
    last_report_write = put_and_verify(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, "report_hash", f"E7.2 last report {run_id}")
    result["writes"]["last_run"] = last_run_write
    result["writes"]["last_report"] = last_report_write
    result["ok"] = bool(core_ok and last_run_write.get("ok") and last_run_write.get("commit_raw_ok") and last_report_write.get("ok") and last_report_write.get("commit_raw_ok"))
    result["evidence_level"] = "E7.2-wake-capsule-reverse-github-dispatch-v0" if result["ok"] else "E7.2-wake-capsule-reverse-github-dispatch-partial"
    write_local_outputs(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "evidence_level": result["evidence_level"],
                "capsule_id": capsule["capsule_id"],
                "capsule_hash": capsule["capsule_hash"],
                "validation_ok": validation.get("ok"),
                "dispatch_ok": dispatch.get("ok"),
                "receiver_ok": receiver.get("ok"),
                "receiver_workflow_run_id": receiver.get("workflow_run_id"),
                "receiver_event": receiver.get("event"),
                "receiver_conclusion": receiver.get("conclusion"),
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
