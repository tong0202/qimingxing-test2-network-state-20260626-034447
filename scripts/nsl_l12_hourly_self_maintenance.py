from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
USER_AGENT = "qimingxing-test2-nsl-l12-hourly-self-maintenance/0.1"

SCHEDULE_CRON = "17 * * * *"
LOGIC_SPEC_PATH = "states/nsl-l11-5-minimal-logic-spec.json"
LOGIC_EVALUATION_PATH = "states/nsl-l11-5-logic-evaluation.json"
LOGIC_LOOP_STATE_PATH = "states/nsl-l11-5-loop-state.json"
L11_MEMORY_PATH = "states/nsl-l11-memory-selection.json"
L11_SELF_CHECK_PATH = "states/nsl-l11-self-check.json"
L11_REPAIR_PATH = "states/nsl-l11-repair-plan.json"
L12_LOCK_PATH = "states/nsl-l12-hourly-self-maintenance-lock.json"
L12_STATE_PATH = "states/nsl-l12-hourly-self-maintenance-state.json"
L12_LAST_RUN_PATH = "states/nsl-l12-last-run.json"
L12_RUN_PREFIX = "states/nsl-l12-hourly-runs"

SOURCE_PATHS = [
    {"id": "l11_5_logic_spec", "path": LOGIC_SPEC_PATH, "hash_field": "logic_hash", "required": True},
    {"id": "l11_5_logic_evaluation", "path": LOGIC_EVALUATION_PATH, "hash_field": "evaluation_hash", "required": True},
    {"id": "l11_5_loop_state", "path": LOGIC_LOOP_STATE_PATH, "hash_field": "state_hash", "required": True},
    {"id": "l11_memory_selection", "path": L11_MEMORY_PATH, "hash_field": "memory_hash", "required": True},
    {"id": "l11_self_check", "path": L11_SELF_CHECK_PATH, "hash_field": "self_check_hash", "required": True},
    {"id": "l11_repair_plan", "path": L11_REPAIR_PATH, "hash_field": "repair_hash", "required": True},
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import hashlib

    return hashlib.sha256(raw).hexdigest()[:16]


def stable_hash(value: dict[str, Any], field: str) -> str:
    clone = json.loads(json.dumps(value, ensure_ascii=False))
    clone[field] = ""
    return canonical_hash(clone)


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def gh_token() -> str:
    env_token = os.environ.get("GITHUB_TOKEN")
    if env_token:
        return env_token
    completed = subprocess.run(["gh", "auth", "token"], text=True, capture_output=True, timeout=30)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "gh auth token failed")
    return completed.stdout.strip()


def api_request(
    owner: str,
    repo: str,
    method: str,
    route: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"https://api.github.com/repos/{owner}/{repo}{route}",
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=35) as response:
            raw = response.read()
            payload_out = json.loads(raw.decode("utf-8")) if raw else {}
            return {
                "ok": True,
                "status": getattr(response, "status", None),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "payload": payload_out,
                "error": "",
            }
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "payload": raw,
            "error": f"HTTPError: {exc.code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def decode_content(response: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not response.get("ok") or not isinstance(response.get("payload"), dict):
        return None, ""
    payload = response["payload"]
    sha = str(payload.get("sha") or "")
    encoded = str(payload.get("content") or "")
    if not encoded:
        return None, sha
    try:
        data = base64.b64decode("".join(encoded.split())).decode("utf-8")
        return json.loads(data), sha
    except Exception:
        return None, sha


def content_get(owner: str, repo: str, path: str, token: str) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    response = api_request(owner, repo, "GET", f"/contents/{quote(path)}?ref=main", token)
    payload, sha = decode_content(response)
    return payload, sha, response


def put_content(owner: str, repo: str, path: str, value: dict[str, Any], message: str, token: str, sha: str = "") -> dict[str, Any]:
    content = base64.b64encode((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")
    payload: dict[str, Any] = {"message": message, "content": content, "branch": "main"}
    if sha:
        payload["sha"] = sha
    return api_request(owner, repo, "PUT", f"/contents/{quote(path)}", token, payload)


def commit_hash_from_put(response: dict[str, Any]) -> str:
    payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
    commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
    return str(commit.get("sha") or "")


def content_sha_from_put(response: dict[str, Any]) -> str:
    payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
    return str(content.get("sha") or "")


def raw_url(owner: str, repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def fetch_json_url(url: str, label: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            headers = {key.lower(): value for key, value in response.headers.items()}
            return {
                "ok": True,
                "label": label,
                "status": getattr(response, "status", None),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "headers": headers,
                "payload": payload,
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "label": label,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "headers": {},
            "payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def verify_hash(payload: dict[str, Any] | None, field: str) -> dict[str, Any]:
    if not field:
        return {"required": False, "ok": True, "field": "", "observed": "", "expected": ""}
    if not payload:
        return {"required": True, "ok": False, "field": field, "observed": "", "expected": ""}
    expected = str(payload.get(field) or "")
    observed = stable_hash(payload, field)
    return {"required": True, "ok": bool(expected and expected == observed), "field": field, "observed": observed, "expected": expected}


def sample_remote(owner: str, repo: str, item: dict[str, Any]) -> dict[str, Any]:
    sample = fetch_json_url(raw_url(owner, repo, "main", item["path"]), f"l12-{item['id']}")
    payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else None
    return {
        "id": item["id"],
        "path": item["path"],
        "required": bool(item.get("required")),
        "read_ok": bool(sample.get("ok") and payload),
        "status": sample.get("status"),
        "elapsed_ms": sample.get("elapsed_ms"),
        "hash_verify": verify_hash(payload, str(item.get("hash_field") or "")),
        "truth_boundary_present": bool(payload and payload.get("truth_boundary")),
        "summary": summarize_source(item["id"], payload),
        "error": sample.get("error"),
        "payload": payload,
    }


def summarize_source(source_id: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    if source_id == "l11_5_logic_spec":
        return {
            "logic_hash": payload.get("logic_hash"),
            "minimum_logic_sentence": payload.get("minimum_logic_sentence"),
            "low_risk_actions": ((payload.get("action_policy") or {}).get("low_risk_auto_recordable") or []),
        }
    if source_id == "l11_5_logic_evaluation":
        return {
            "evaluation_hash": payload.get("evaluation_hash"),
            "minimum_logic_ready": payload.get("minimum_logic_ready"),
            "l12_ready": payload.get("l12_ready"),
            "blocking_count": payload.get("blocking_count"),
        }
    if source_id == "l11_5_loop_state":
        return {
            "generation": payload.get("generation"),
            "state_hash": payload.get("state_hash"),
            "l12_ready": payload.get("l12_ready"),
        }
    if source_id == "l11_memory_selection":
        return {"selected_count": payload.get("selected_count"), "memory_hash": payload.get("memory_hash")}
    if source_id == "l11_self_check":
        return {
            "ok": payload.get("ok"),
            "blocking_count": payload.get("blocking_count"),
            "warning_count": payload.get("warning_count"),
            "self_check_hash": payload.get("self_check_hash"),
        }
    if source_id == "l11_repair_plan":
        return {
            "ok": payload.get("ok"),
            "actions": [item.get("action") for item in payload.get("actions") or []],
            "repair_hash": payload.get("repair_hash"),
        }
    return {"keys": sorted(payload.keys())[:12]}


def run_owner(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "actor": os.environ.get("GITHUB_ACTOR"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "sha": os.environ.get("GITHUB_SHA"),
        "local": not bool(os.environ.get("GITHUB_ACTIONS")),
    }


def lock_active(lock: dict[str, Any] | None) -> bool:
    if not lock or lock.get("locked") is not True:
        return False
    expires_at = parse_time(lock.get("expires_at"))
    return bool(expires_at and datetime.now(timezone.utc) < expires_at)


def acquire_lock(owner: str, repo: str, token: str, run_id: str, mode: str, ttl_seconds: int) -> dict[str, Any]:
    previous, sha, _ = content_get(owner, repo, L12_LOCK_PATH, token)
    if lock_active(previous):
        return {"ok": False, "skipped": True, "active_lock": previous, "write": {}}
    lock = {
        "stage": "L12-hourly-self-maintenance-lock",
        "schema_version": "QMX-L12-LOCK-0.1",
        "locked": True,
        "checkpoint": "running",
        "run_id": run_id,
        "owner": run_owner(mode),
        "created_at": now(),
        "updated_at": now(),
        "expires_at": future(ttl_seconds),
        "ttl_seconds": ttl_seconds,
        "previous_lock_recovered": bool(previous and previous.get("locked") is True),
        "lock_hash": "",
        "truth_boundary": "This lock prevents overlapping L12 hourly self-maintenance windows. It is not autonomous network self-execution.",
    }
    lock = seal(lock, "lock_hash")
    write = put_content(owner, repo, L12_LOCK_PATH, lock, f"L12 lock acquire {run_id}", token, sha)
    return {"ok": bool(write.get("ok")), "skipped": False, "lock": lock, "write": write}


def release_lock(owner: str, repo: str, token: str, run_id: str, ok: bool) -> dict[str, Any]:
    lock, sha, _ = content_get(owner, repo, L12_LOCK_PATH, token)
    if not lock or lock.get("run_id") != run_id:
        return {"ok": False, "reason": "lock_not_owned"}
    released = dict(lock)
    released.update(
        {
            "locked": False,
            "checkpoint": "completed" if ok else "failed",
            "updated_at": now(),
            "released_at": now(),
            "release_ok": ok,
            "lock_hash": "",
        }
    )
    released = seal(released, "lock_hash")
    write = put_content(owner, repo, L12_LOCK_PATH, released, f"L12 lock release {run_id}", token, sha)
    return {"ok": bool(write.get("ok")), "status": write.get("status"), "error": write.get("error")}


def action_policy_from_spec(spec: dict[str, Any]) -> dict[str, set[str]]:
    policy = spec.get("action_policy") or {}
    return {
        "low": set(policy.get("low_risk_auto_recordable") or []),
        "medium": set(policy.get("medium_risk_self_review_then_record") or []),
        "high": set(policy.get("high_risk_requires_human_approval") or []),
    }


def evaluate_window(owner: str, repo: str) -> dict[str, Any]:
    sources = [sample_remote(owner, repo, item) for item in SOURCE_PATHS]
    payload_by_id = {item["id"]: item.get("payload") for item in sources if isinstance(item.get("payload"), dict)}
    spec = payload_by_id.get("l11_5_logic_spec") or {}
    l11_eval = payload_by_id.get("l11_5_logic_evaluation") or {}
    repair_plan = payload_by_id.get("l11_repair_plan") or {}
    policy = action_policy_from_spec(spec)
    low = policy["low"]
    medium = policy["medium"]
    high = policy["high"]

    required = [item for item in sources if item["required"]]
    planned_actions = [
        {"action": "no_op_verified", "risk": "low", "reason": "required memories are readable and hash-verified"},
        {"action": "record_truth_boundary", "risk": "low", "reason": "keep proof boundaries visible in every L12 window"},
        {"action": "continue_schedule_observation", "risk": "low", "reason": "hourly window records external wakeup continuity"},
    ]
    l11_actions = [str(item.get("action") or "") for item in repair_plan.get("actions") or []]
    l11_action_records = []
    for action in l11_actions:
        if action in low:
            risk = "low"
        elif action in medium:
            risk = "medium"
        elif action in high:
            risk = "high"
        else:
            risk = "unknown"
        l11_action_records.append({"action": action, "risk": risk, "covered": risk != "unknown"})

    planned_action_records = []
    for item in planned_actions:
        action = item["action"]
        item = dict(item)
        item["allowed_by_l11_5"] = action in low
        planned_action_records.append(item)

    checks = [
        {
            "id": "required_sources_read",
            "ok": all(item["read_ok"] for item in required),
            "severity": "blocking",
            "meaning": "L12 必须能读取 L11.5 逻辑、L11.5 评估、L11 状态证据。",
        },
        {
            "id": "required_hashes_match",
            "ok": all((item["hash_verify"] or {}).get("ok") for item in required),
            "severity": "blocking",
            "meaning": "所有带哈希的远端证据必须一致。",
        },
        {
            "id": "l11_5_logic_ready",
            "ok": bool(l11_eval.get("minimum_logic_ready") and l11_eval.get("l12_ready")),
            "severity": "blocking",
            "meaning": "L12 只能基于已经通过的 L11.5 最小逻辑运行。",
        },
        {
            "id": "planned_actions_low_risk",
            "ok": all(item["allowed_by_l11_5"] and item["risk"] == "low" for item in planned_action_records),
            "severity": "blocking",
            "meaning": "L12 当前窗口只允许自动记录低风险动作。",
            "details": planned_action_records,
        },
        {
            "id": "l11_actions_covered",
            "ok": bool(l11_action_records) and all(item["covered"] and item["risk"] in {"low", "medium"} for item in l11_action_records),
            "severity": "warning",
            "meaning": "L11 旧修复计划必须能被 L11.5 动作策略解释。",
            "details": l11_action_records,
        },
        {
            "id": "no_high_risk_auto_action",
            "ok": all(item["risk"] != "high" for item in planned_action_records + l11_action_records),
            "severity": "blocking",
            "meaning": "L12 不自动执行高风险动作。",
        },
    ]
    blocking_count = sum(1 for item in checks if item["severity"] == "blocking" and not item["ok"])
    warning_count = sum(1 for item in checks if item["severity"] == "warning" and not item["ok"])
    window = {
        "stage": "L12-hourly-self-maintenance-window",
        "schema_version": "QMX-L12-WINDOW-0.1",
        "created_at": now(),
        "schedule_cron": SCHEDULE_CRON,
        "sources": [{key: value for key, value in item.items() if key != "payload"} for item in sources],
        "checks": checks,
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "planned_actions": planned_action_records,
        "l11_repair_actions_observed": l11_action_records,
        "low_risk_actions_recorded": [item["action"] for item in planned_action_records if item["allowed_by_l11_5"]],
        "window_ok": blocking_count == 0,
        "window_hash": "",
        "truth_boundary": (
            "L12 is an hourly controlled self-maintenance window. It records low-risk maintenance only; "
            "it does not autonomously mutate core capsules, code, permissions, or prove CPU-free network life."
        ),
    }
    return seal(window, "window_hash")


def build_state(run_id: str, mode: str, generation: int, window: dict[str, Any], previous_state: dict[str, Any] | None) -> dict[str, Any]:
    history = list((previous_state or {}).get("history") or [])[-12:]
    if previous_state:
        history.append(
            {
                "generation": previous_state.get("generation"),
                "run_id": previous_state.get("run_id"),
                "state_hash": previous_state.get("state_hash"),
                "window_hash": previous_state.get("window_hash"),
                "window_ok": previous_state.get("window_ok"),
            }
        )
    state = {
        "stage": "L12-hourly-self-maintenance-state",
        "schema_version": "QMX-L12-STATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "generation": generation,
        "owner": run_owner(mode),
        "schedule_cron": SCHEDULE_CRON,
        "window_hash": window["window_hash"],
        "window_ok": window["window_ok"],
        "blocking_count": window["blocking_count"],
        "warning_count": window["warning_count"],
        "low_risk_actions_recorded": window["low_risk_actions_recorded"],
        "previous": {
            "generation": (previous_state or {}).get("generation"),
            "state_hash": (previous_state or {}).get("state_hash"),
        },
        "history": history,
        "state_hash": "",
        "truth_boundary": "L12 records controlled hourly self-maintenance state. It is not autonomous cognition or CPU-free network computation.",
    }
    return seal(state, "state_hash")


def put_and_verify(owner: str, repo: str, token: str, path: str, value: dict[str, Any], hash_field: str, message: str) -> dict[str, Any]:
    _, sha, _ = content_get(owner, repo, path, token)
    write = put_content(owner, repo, path, value, message, token, sha)
    commit_hash = commit_hash_from_put(write)
    sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"l12-commit-{path}") if commit_hash else {}
    payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
    observed_hash = str(payload.get(hash_field) or "")
    expected_hash = str(value.get(hash_field) or "")
    return {
        "path": path,
        "ok": bool(write.get("ok")),
        "status": write.get("status"),
        "error": write.get("error"),
        "commit_hash": commit_hash,
        "content_sha": content_sha_from_put(write),
        "commit_raw_ok": bool(sample.get("ok") and observed_hash == expected_hash),
        "expected_hash": expected_hash,
        "observed_hash": observed_hash,
    }


def wait_for_branch_release(owner: str, repo: str, expected: list[dict[str, str]], timeout_seconds: int, interval_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    observations: list[dict[str, Any]] = []
    latest_by_path: dict[str, dict[str, Any]] = {}
    while time.time() < deadline:
        all_ok = True
        round_items: list[dict[str, Any]] = []
        for item in expected:
            sample = fetch_json_url(raw_url(owner, repo, "main", item["path"]), f"l12-branch-{item['path']}")
            payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
            observed_hash = str(payload.get(item["hash_field"]) or "")
            ok = bool(sample.get("ok") and observed_hash == item["hash_value"])
            all_ok = all_ok and ok
            record = {
                "path": item["path"],
                "ok": ok,
                "status": sample.get("status"),
                "elapsed_ms": sample.get("elapsed_ms"),
                "hash_field": item["hash_field"],
                "observed_hash": observed_hash,
                "expected_hash": item["hash_value"],
                "headers": sample.get("headers") or {},
                "error": sample.get("error"),
            }
            latest_by_path[item["path"]] = record
            round_items.append(record)
        observations.append({"at": now(), "all_ok": all_ok, "items": round_items})
        if all_ok:
            return {"ok": True, "timed_out": False, "observations": observations[-10:], "latest_by_path": latest_by_path}
        time.sleep(interval_seconds)
    return {"ok": False, "timed_out": True, "observations": observations[-10:], "latest_by_path": latest_by_path}


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_l12_hourly_self_maintenance_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_l12_hourly_self_maintenance_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# L12：每小时受控低频自维护窗口",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- mode: `{result['mode']}`",
        f"- event_name: `{result['owner'].get('event_name')}`",
        f"- schedule_cron: `{SCHEDULE_CRON}`",
        f"- generation: `{result['generation']}`",
        f"- window_hash: `{result['window']['window_hash']}`",
        f"- state_hash: `{result['state']['state_hash']}`",
        f"- blocking_count: `{result['window']['blocking_count']}`",
        f"- warning_count: `{result['window']['warning_count']}`",
        "",
        "## 检查",
        "",
        "| check | ok | severity |",
        "| --- | --- | --- |",
    ]
    for item in result["window"]["checks"]:
        lines.append(f"| `{item['id']}` | `{item['ok']}` | `{item['severity']}` |")
    lines.extend(["", "## 边界", "", result["truth_boundary"], ""])
    (run_dir / "nsl_l12_hourly_self_maintenance_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="L12 hourly controlled self-maintenance window")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--lock-ttl-seconds", type=int, default=2700)
    parser.add_argument("--raw-timeout", type=int, default=240)
    parser.add_argument("--raw-interval", type=float, default=8.0)
    args = parser.parse_args()

    event = os.environ.get("GITHUB_EVENT_NAME") or "local"
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        run_id = f"nsl-l12-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-l12-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()
    lock = acquire_lock(args.owner, args.repo, token, run_id, args.mode, args.lock_ttl_seconds)
    if lock.get("skipped"):
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "L12-hourly-self-maintenance-window",
            "ok": True,
            "skipped": True,
            "reason": "active_lock",
            "active_lock": lock.get("active_lock"),
            "truth_boundary": "L12 skipped because another controlled window is active.",
        }
        write_local_outputs(run_dir, result | {"mode": args.mode, "owner": run_owner(args.mode), "generation": 0, "window": {"checks": [], "blocking_count": 0, "warning_count": 0, "window_hash": ""}, "state": {"state_hash": ""}})
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0

    release: dict[str, Any] = {}
    try:
        window = evaluate_window(args.owner, args.repo)
        previous_state, state_sha, _ = content_get(args.owner, args.repo, L12_STATE_PATH, token)
        generation = int((previous_state or {}).get("generation") or 0) + 1
        state = build_state(run_id, args.mode, generation, window, previous_state)
        run_path = f"{L12_RUN_PREFIX}/{run_id}.json"
        maintenance_run = {
            "stage": "L12-hourly-self-maintenance-run",
            "schema_version": "QMX-L12-RUN-0.1",
            "created_at": now(),
            "run_id": run_id,
            "owner": run_owner(args.mode),
            "schedule_cron": SCHEDULE_CRON,
            "window": window,
            "state_hash": state["state_hash"],
            "run_hash": "",
            "truth_boundary": window["truth_boundary"],
        }
        maintenance_run = seal(maintenance_run, "run_hash")

        run_write = put_and_verify(args.owner, args.repo, token, run_path, maintenance_run, "run_hash", f"L12 hourly run {run_id}")
        state_write = put_content(args.owner, args.repo, L12_STATE_PATH, state, f"L12 hourly state {run_id}", token, state_sha)
        state_commit = commit_hash_from_put(state_write)
        state_sample = fetch_json_url(raw_url(args.owner, args.repo, state_commit, L12_STATE_PATH), "l12-state-commit") if state_commit else {}
        state_payload = state_sample.get("payload") if isinstance(state_sample.get("payload"), dict) else {}
        state_commit_raw_ok = bool(state_sample.get("ok") and state_payload.get("state_hash") == state["state_hash"])
        _, last_sha, _ = content_get(args.owner, args.repo, L12_LAST_RUN_PATH, token)
        last_run = {
            "stage": "L12-last-run",
            "schema_version": "QMX-L12-LAST-RUN-0.1",
            "created_at": now(),
            "run_id": run_id,
            "event_name": event,
            "schedule_cron": SCHEDULE_CRON,
            "window_ok": window["window_ok"],
            "generation": generation,
            "run_path": run_path,
            "window_hash": window["window_hash"],
            "state_hash": state["state_hash"],
            "run_hash": maintenance_run["run_hash"],
            "last_run_hash": "",
            "truth_boundary": "L12 last-run record proves one controlled hourly window execution, not CPU-free network life.",
        }
        last_run = seal(last_run, "last_run_hash")
        last_write = put_content(args.owner, args.repo, L12_LAST_RUN_PATH, last_run, f"L12 last run {run_id}", token, last_sha)
        last_commit = commit_hash_from_put(last_write)
        last_sample = fetch_json_url(raw_url(args.owner, args.repo, last_commit, L12_LAST_RUN_PATH), "l12-last-run-commit") if last_commit else {}
        last_payload = last_sample.get("payload") if isinstance(last_sample.get("payload"), dict) else {}
        last_commit_raw_ok = bool(last_sample.get("ok") and last_payload.get("last_run_hash") == last_run["last_run_hash"])

        release = release_lock(args.owner, args.repo, token, run_id, window["window_ok"])
        expected = [
            {"path": run_path, "hash_field": "run_hash", "hash_value": maintenance_run["run_hash"]},
            {"path": L12_STATE_PATH, "hash_field": "state_hash", "hash_value": state["state_hash"]},
            {"path": L12_LAST_RUN_PATH, "hash_field": "last_run_hash", "hash_value": last_run["last_run_hash"]},
        ]
        branch_release = wait_for_branch_release(args.owner, args.repo, expected, args.raw_timeout, args.raw_interval)
        ok = bool(
            window["window_ok"]
            and run_write.get("ok")
            and run_write.get("commit_raw_ok")
            and state_write.get("ok")
            and state_commit_raw_ok
            and last_write.get("ok")
            and last_commit_raw_ok
            and release.get("ok")
            and branch_release.get("ok")
        )
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "L12-hourly-self-maintenance-window",
            "ok": ok,
            "mode": args.mode,
            "owner": run_owner(args.mode),
            "generation": generation,
            "schedule_cron": SCHEDULE_CRON,
            "paths": {
                "workflow": ".github/workflows/nsl-l12-hourly-self-maintenance.yml",
                "runner": "scripts/nsl_l12_hourly_self_maintenance.py",
                "lock": L12_LOCK_PATH,
                "state": L12_STATE_PATH,
                "last_run": L12_LAST_RUN_PATH,
                "run": run_path,
            },
            "window": window,
            "state": state,
            "last_run": last_run,
            "writes": {
                "run": run_write,
                "state": {
                    "ok": state_write.get("ok"),
                    "status": state_write.get("status"),
                    "error": state_write.get("error"),
                    "commit_hash": state_commit,
                    "content_sha": content_sha_from_put(state_write),
                    "commit_raw_ok": state_commit_raw_ok,
                    "expected_hash": state["state_hash"],
                    "observed_hash": state_payload.get("state_hash"),
                },
                "last_run": {
                    "ok": last_write.get("ok"),
                    "status": last_write.get("status"),
                    "error": last_write.get("error"),
                    "commit_hash": last_commit,
                    "content_sha": content_sha_from_put(last_write),
                    "commit_raw_ok": last_commit_raw_ok,
                    "expected_hash": last_run["last_run_hash"],
                    "observed_hash": last_payload.get("last_run_hash"),
                },
                "lock_release": release,
            },
            "verification": {
                "branch_raw_release_ok": branch_release.get("ok"),
                "branch_raw_release": branch_release,
            },
            "evidence_level": "L12-hourly-self-maintenance-window" if ok else "L12-hourly-self-maintenance-window-partial",
            "conclusion": (
                "L12 成立：每小时自维护窗口可以读取 L11.5 逻辑，执行受控低风险记录，并写回远端状态。"
                if ok
                else "L12 部分成立：窗口已运行，但至少一个自检、写回、锁释放或 Raw 释放环节未通过。"
            ),
            "truth_boundary": (
                "L12 runs on GitHub Actions cloud CPU once per hour by schedule. "
                "It is not CPU-free network execution, autonomous cognition, or unreviewed self-modification."
            ),
        }
        write_local_outputs(run_dir, result)
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "ok": ok,
                    "mode": args.mode,
                    "event_name": event,
                    "schedule_cron": SCHEDULE_CRON,
                    "generation": generation,
                    "window_ok": window["window_ok"],
                    "blocking_count": window["blocking_count"],
                    "warning_count": window["warning_count"],
                    "branch_raw_release_ok": branch_release.get("ok"),
                    "truth_boundary": result["truth_boundary"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0 if ok else 1
    except Exception:
        release = release_lock(args.owner, args.repo, token, run_id, False)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
