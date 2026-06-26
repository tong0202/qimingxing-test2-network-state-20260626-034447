from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


CAPSULE_PATH = "states/nsl-l4-receiver-capsule.json"
LOOP_STATE_PATH = "states/nsl-l6-scheduled-loop-state.json"
LAST_RUN_PATH = "states/nsl-l6-last-run.json"
CYCLE_PREFIX = "states/nsl-l6-scheduled-cycles"
USER_AGENT = "qimingxing-test2-nsl-l6-scheduled-receiver-loop/0.1"
ALLOWED_ACTIONS = {"emit_program_pulse"}
FORBIDDEN_PROGRAM_KEYS = {"cmd", "code", "command", "eval", "exec", "javascript", "powershell", "python", "shell"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha16(payload)


def stable_hash(value: dict[str, Any], field: str) -> str:
    copy = json.loads(json.dumps(value, ensure_ascii=False))
    copy[field] = ""
    return canonical_hash(copy)


def verify_stored_hash(value: dict[str, Any] | None, field: str) -> bool:
    if not value:
        return True
    return value.get(field) == stable_hash(value, field)


def split_repo() -> tuple[str, str]:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        raise RuntimeError("GITHUB_REPOSITORY is missing")
    owner, name = repo.split("/", 1)
    return owner, name


def token() -> str:
    value = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not value:
        raise RuntimeError("GITHUB_TOKEN is missing")
    return value


def api_request(method: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    owner, repo = split_repo()
    url = f"https://api.github.com/repos/{owner}/{repo}{route}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token()}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return {
                "ok": True,
                "status": getattr(response, "status", None),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "payload": parsed,
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


def get_content(path: str) -> dict[str, Any]:
    return api_request("GET", f"/contents/{path}?ref=main")


def decode_content(response: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not response.get("ok") or not isinstance(response.get("payload"), dict):
        return None, ""
    payload = response["payload"]
    encoded = str(payload.get("content") or "")
    if not encoded:
        return None, str(payload.get("sha") or "")
    data = base64.b64decode("".join(encoded.split())).decode("utf-8")
    return json.loads(data), str(payload.get("sha") or "")


def put_content(path: str, value: dict[str, Any], message: str, sha: str = "") -> dict[str, Any]:
    content = base64.b64encode((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")
    payload: dict[str, Any] = {"message": message, "content": content, "branch": "main"}
    if sha:
        payload["sha"] = sha
    return api_request("PUT", f"/contents/{path}", payload)


def content_sha_from_put(response: dict[str, Any]) -> str:
    payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
    return str(content.get("sha") or "")


def commit_hash_from_put(response: dict[str, Any]) -> str:
    payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
    commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
    return str(commit.get("sha") or "")


def raw_url(path: str, ref: str = "main") -> str:
    owner, repo = split_repo()
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def fetch_json_url(url: str, label: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
            payload = json.loads(body.decode("utf-8"))
            return {
                "ok": True,
                "label": label,
                "url": url,
                "status": getattr(response, "status", None),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "generation": payload.get("generation"),
                "state_signature": payload.get("state_signature"),
                "stage": payload.get("stage"),
                "body_sha16": sha16(body),
                "canonical_sha16": canonical_hash(payload),
                "headers": {
                    key: headers.get(key, "")
                    for key in ["cache-control", "etag", "x-cache", "x-served-by", "via", "expires", "age"]
                    if headers.get(key, "")
                },
                "payload": payload,
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "label": label,
            "url": url,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "generation": None,
            "state_signature": "",
            "stage": "",
            "body_sha16": "",
            "canonical_sha16": "",
            "headers": {},
            "payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def contains_forbidden_keys(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_PROGRAM_KEYS:
                found.append(str(key))
            found.extend(contains_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(contains_forbidden_keys(child))
    return sorted(set(found))


def validate_capsule(capsule: dict[str, Any]) -> dict[str, Any]:
    program = capsule.get("program") or {}
    action = (program.get("allowed_action") or {}).get("type")
    forbidden = contains_forbidden_keys(program)
    expected_hash = capsule.get("capsule_hash")
    sealed = json.loads(json.dumps(capsule, ensure_ascii=False))
    sealed["capsule_hash"] = ""
    observed_hash = canonical_hash(sealed)
    checks = {
        "schema_ok": capsule.get("schema_version") == "NSL-L4-CAPSULE-0.1",
        "intent_ok": program.get("intent") == "ADVANCE_AFTER_RELEASE",
        "sentence_stable": bool(program.get("sentence_stability")),
        "action_allowlisted": action in ALLOWED_ACTIONS,
        "no_forbidden_keys": not forbidden,
        "hash_ok": expected_hash == observed_hash,
        "receiver_candidate": capsule.get("receiver", {}).get("name") == "github_branch_raw_main",
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "forbidden_keys": forbidden,
        "expected_hash": expected_hash,
        "observed_hash": observed_hash,
    }


def run_owner() -> dict[str, Any]:
    return {
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "actor": os.environ.get("GITHUB_ACTOR"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "server_url": os.environ.get("GITHUB_SERVER_URL"),
        "sha": os.environ.get("GITHUB_SHA"),
    }


def build_cycle_pulse(
    run_id: str,
    cycle_index: int,
    generation: int,
    pulse_path: str,
    capsule: dict[str, Any],
    capsule_read: dict[str, Any],
    validation: dict[str, Any],
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_hash = previous_state.get("state_hash") if previous_state else None
    pulse = {
        "stage": "L6-external-scheduled-receiver-capsule-loop-pulse",
        "created_at": now(),
        "run_id": run_id,
        "cycle_index": cycle_index,
        "generation": generation,
        "state_signature": f"{run_id}-cycle-{cycle_index:03d}",
        "executor": "github_actions_scheduled_or_dispatch",
        "owner": run_owner(),
        "capsule_id": capsule.get("capsule_id"),
        "capsule_generation": capsule.get("generation"),
        "capsule_path": CAPSULE_PATH,
        "pulse_path": pulse_path,
        "previous_loop_state_hash": previous_hash,
        "capsule_read": {
            "ok": capsule_read.get("ok"),
            "status": capsule_read.get("status"),
            "elapsed_ms": capsule_read.get("elapsed_ms"),
            "headers": capsule_read.get("headers") or {},
            "body_sha16": capsule_read.get("body_sha16"),
            "canonical_sha16": capsule_read.get("canonical_sha16"),
        },
        "capsule_validation": {
            "ok": validation.get("ok"),
            "checks": validation.get("checks") or {},
            "forbidden_keys": validation.get("forbidden_keys") or [],
        },
        "decoded_sentence": (capsule.get("program") or {}).get("decoded_sentence"),
        "nsl_rule": (capsule.get("program") or {}).get("nsl_rule"),
        "action": {
            "type": "emit_program_pulse",
            "meaning": "L6 外层定时执行器中的一次受控胶囊脉冲。",
        },
        "pulse_hash": "",
        "truth_boundary": "This pulse is emitted by GitHub Actions after reading the network-resident capsule. It is external scheduled CPU execution, not CPU-free network computation.",
    }
    pulse["pulse_hash"] = stable_hash(pulse, "pulse_hash")
    return pulse


def build_loop_state(
    run_id: str,
    cycle_index: int,
    generation: int,
    capsule: dict[str, Any],
    previous_state: dict[str, Any] | None,
    pulse: dict[str, Any],
    pulse_path: str,
) -> dict[str, Any]:
    previous_hash = previous_state.get("state_hash") if previous_state else None
    prior_history = list((previous_state or {}).get("history") or [])[-30:]
    prior_history.append(
        {
            "cycle_index": cycle_index,
            "generation": generation,
            "pulse_path": pulse_path,
            "pulse_hash": pulse.get("pulse_hash"),
            "capsule_id": capsule.get("capsule_id"),
            "executor_run_id": os.environ.get("GITHUB_RUN_ID"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "created_at": pulse.get("created_at"),
        }
    )
    state = {
        "stage": "L6-external-scheduled-receiver-capsule-loop",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "state_signature": f"{run_id}-loop-state-{generation:03d}",
        "executor": "github_actions_scheduled_or_dispatch",
        "owner": run_owner(),
        "capsule": {
            "path": CAPSULE_PATH,
            "id": capsule.get("capsule_id"),
            "generation": capsule.get("generation"),
            "hash": capsule.get("capsule_hash"),
            "receiver": capsule.get("receiver"),
        },
        "previous": {
            "generation": previous_state.get("generation") if previous_state else None,
            "state_hash": previous_hash,
        },
        "latest_pulse": {
            "path": pulse_path,
            "hash": pulse.get("pulse_hash"),
            "cycle_index": cycle_index,
        },
        "history": prior_history,
        "loop_rule": "GITHUB ACTIONS TIMER -> READ CAPSULE FROM BRANCH RAW -> VALIDATE -> EMIT UNIQUE PULSE -> UPDATE LOOP STATE",
        "state_hash": "",
        "truth_boundary": "L6 proves external scheduled/dispatch execution of the receiver-capsule loop. GitHub Actions CPU still performs interpretation and writes.",
    }
    state["state_hash"] = stable_hash(state, "state_hash")
    return state


def run_cycle(run_id: str, cycle_index: int) -> dict[str, Any]:
    capsule_read = fetch_json_url(raw_url(CAPSULE_PATH), f"l6-cycle-{cycle_index}-capsule-raw")
    capsule = capsule_read.get("payload") if isinstance(capsule_read.get("payload"), dict) else {}
    validation = validate_capsule(capsule)

    previous_state_response = get_content(LOOP_STATE_PATH)
    previous_state, state_sha = decode_content(previous_state_response)
    previous_state_hash_ok = verify_stored_hash(previous_state, "state_hash")
    previous_generation = int((previous_state or {}).get("generation") or 0)
    generation = previous_generation + 1
    continuity_ok = bool(previous_state_hash_ok and generation == previous_generation + 1)

    run_key = str(os.environ.get("GITHUB_RUN_ID") or run_id)
    attempt = str(os.environ.get("GITHUB_RUN_ATTEMPT") or "1")
    pulse_path = f"{CYCLE_PREFIX}/{run_id}-cycle-{cycle_index:03d}-run-{run_key}-attempt-{attempt}.json"
    pulse = build_cycle_pulse(run_id, cycle_index, generation, pulse_path, capsule, capsule_read, validation, previous_state)
    _, pulse_sha = decode_content(get_content(pulse_path))
    pulse_write = put_content(pulse_path, pulse, f"L6 scheduled receiver capsule pulse {run_id} cycle {cycle_index}", pulse_sha)
    pulse_commit = commit_hash_from_put(pulse_write)
    pulse_commit_raw = fetch_json_url(raw_url(pulse_path, pulse_commit), f"l6-cycle-{cycle_index}-pulse-commit") if pulse_commit else {}
    pulse_commit_raw_ok = bool(
        pulse_commit_raw.get("ok")
        and pulse_commit_raw.get("generation") == generation
        and pulse_commit_raw.get("state_signature") == pulse.get("state_signature")
    )

    loop_state = build_loop_state(run_id, cycle_index, generation, capsule, previous_state, pulse, pulse_path)
    state_write = put_content(LOOP_STATE_PATH, loop_state, f"L6 scheduled receiver capsule loop state {run_id} generation {generation}", state_sha)
    state_api, _ = decode_content(get_content(LOOP_STATE_PATH))
    state_api_verify_ok = bool(
        state_api
        and state_api.get("generation") == generation
        and state_api.get("state_hash") == loop_state.get("state_hash")
        and verify_stored_hash(state_api, "state_hash")
    )

    ok = bool(
        capsule_read.get("ok")
        and validation.get("ok")
        and continuity_ok
        and pulse_write.get("ok")
        and pulse_commit_raw_ok
        and state_write.get("ok")
        and state_api_verify_ok
    )
    return {
        "cycle_index": cycle_index,
        "generation": generation,
        "ok": ok,
        "capsule_read": {
            "ok": capsule_read.get("ok"),
            "status": capsule_read.get("status"),
            "elapsed_ms": capsule_read.get("elapsed_ms"),
            "headers": capsule_read.get("headers") or {},
            "generation": capsule_read.get("generation"),
            "state_signature": capsule_read.get("state_signature"),
            "body_sha16": capsule_read.get("body_sha16"),
            "canonical_sha16": capsule_read.get("canonical_sha16"),
        },
        "capsule_validation": validation,
        "previous_state": {
            "lookup_status": previous_state_response.get("status"),
            "generation": previous_generation,
            "state_hash_ok": previous_state_hash_ok,
            "state_hash": (previous_state or {}).get("state_hash"),
        },
        "continuity_ok": continuity_ok,
        "pulse_path": pulse_path,
        "pulse_hash": pulse.get("pulse_hash"),
        "pulse_write": {
            "ok": pulse_write.get("ok"),
            "status": pulse_write.get("status"),
            "error": pulse_write.get("error"),
            "commit_hash": pulse_commit,
            "content_sha": content_sha_from_put(pulse_write),
        },
        "pulse_commit_raw_verify": {
            "ok": pulse_commit_raw_ok,
            "sample": pulse_commit_raw,
        },
        "loop_state_path": LOOP_STATE_PATH,
        "state_hash": loop_state.get("state_hash"),
        "state_write": {
            "ok": state_write.get("ok"),
            "status": state_write.get("status"),
            "error": state_write.get("error"),
            "commit_hash": commit_hash_from_put(state_write),
            "content_sha": content_sha_from_put(state_write),
        },
        "state_api_verify": {
            "ok": state_api_verify_ok,
            "generation": state_api.get("generation") if state_api else None,
            "state_hash": state_api.get("state_hash") if state_api else None,
        },
    }


def cycle_summary(cycle: dict[str, Any]) -> dict[str, Any]:
    return {
        "cycle_index": cycle.get("cycle_index"),
        "generation": cycle.get("generation"),
        "ok": cycle.get("ok"),
        "capsule_raw_ok": cycle.get("capsule_read", {}).get("ok"),
        "validation_ok": cycle.get("capsule_validation", {}).get("ok"),
        "continuity_ok": cycle.get("continuity_ok"),
        "pulse_write_ok": cycle.get("pulse_write", {}).get("ok"),
        "pulse_commit_raw_ok": cycle.get("pulse_commit_raw_verify", {}).get("ok"),
        "state_write_ok": cycle.get("state_write", {}).get("ok"),
        "state_api_verify_ok": cycle.get("state_api_verify", {}).get("ok"),
    }


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except Exception:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.environ.get(name, str(default))))
    except Exception:
        return default


def main() -> int:
    run_key = str(os.environ.get("GITHUB_RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    attempt = str(os.environ.get("GITHUB_RUN_ATTEMPT") or "1")
    run_id = f"nsl-l6-gh-{run_key}-attempt-{attempt}"
    cycles_requested = env_int("L6_CYCLES", 1)
    cycle_delay = env_float("L6_CYCLE_DELAY_SECONDS", 0.0)

    cycles = []
    for cycle_index in range(1, cycles_requested + 1):
        cycles.append(run_cycle(run_id, cycle_index))
        if cycle_index < cycles_requested and cycle_delay:
            time.sleep(cycle_delay)

    summaries = [cycle_summary(cycle) for cycle in cycles]
    cycles_ok = sum(1 for item in summaries if item["ok"])
    ok = bool(cycles and cycles_ok == len(cycles))
    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "L6-external-scheduled-receiver-capsule-loop",
        "ok": ok,
        "executor": "github_actions_scheduled_or_dispatch",
        "owner": run_owner(),
        "cycles_requested": cycles_requested,
        "cycle_delay_seconds": cycle_delay,
        "capsule_path": CAPSULE_PATH,
        "loop_state_path": LOOP_STATE_PATH,
        "last_run_path": LAST_RUN_PATH,
        "cycle_prefix": CYCLE_PREFIX,
        "cycles": cycles,
        "cycle_summaries": summaries,
        "aggregate": {
            "cycle_count": len(cycles),
            "cycles_ok": cycles_ok,
            "all_capsule_raw_ok": all(item["capsule_raw_ok"] for item in summaries),
            "all_validation_ok": all(item["validation_ok"] for item in summaries),
            "all_continuity_ok": all(item["continuity_ok"] for item in summaries),
            "all_pulse_write_ok": all(item["pulse_write_ok"] for item in summaries),
            "all_state_write_ok": all(item["state_write_ok"] for item in summaries),
            "final_generation": cycles[-1]["generation"] if cycles else None,
            "final_state_hash": cycles[-1]["state_hash"] if cycles else None,
        },
        "evidence_level": "L6-external-scheduled-receiver-capsule-loop" if ok else "L6-external-scheduled-loop-partial",
        "conclusion": (
            "L6 成立：外层 GitHub Actions 执行器已从网络驻留胶囊 Raw 读回、校验、写入唯一 pulse，并更新远端 loop state。"
            if ok
            else "L6 部分成立：外层执行器运行了，但至少一个校验环节未通过。"
        ),
        "truth_boundary": "L6 proves external scheduled/dispatch execution of the receiver-capsule loop. GitHub Actions CPU still performs interpretation and writes; this is not CPU-free network computation.",
    }
    _, last_sha = decode_content(get_content(LAST_RUN_PATH))
    report_write = put_content(LAST_RUN_PATH, result, f"L6 scheduled receiver capsule loop report {run_id}", last_sha)
    result["remote_report_write"] = {
        "ok": report_write.get("ok"),
        "status": report_write.get("status"),
        "error": report_write.get("error"),
        "content_sha": content_sha_from_put(report_write),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if ok and report_write.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
