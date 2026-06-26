from __future__ import annotations

import base64
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


STATE_PATH = "states/ghost-state.json"
REPORT_PATH = "states/n6-last-run.json"
USER_AGENT = "qimingxing-n6-external-runner/0.1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha16(payload)


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


def decode_content(response: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if not response.get("ok") or not isinstance(response.get("payload"), dict):
        raise RuntimeError(f"content read failed: {response.get('error')}")
    payload = response["payload"]
    encoded = str(payload.get("content") or "")
    data = base64.b64decode("".join(encoded.split())).decode("utf-8")
    return json.loads(data), str(payload.get("sha") or "")


def put_content(path: str, value: dict[str, Any], message: str, sha: str | None = None) -> dict[str, Any]:
    content = base64.b64encode((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")
    payload: dict[str, Any] = {"message": message, "content": content, "branch": "main"}
    if sha:
        payload["sha"] = sha
    return api_request("PUT", f"/contents/{path}", payload)


def raw_url(ref: str, path: str = STATE_PATH) -> str:
    owner, repo = split_repo()
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def get_raw_json(ref: str, path: str = STATE_PATH) -> dict[str, Any]:
    request = Request(raw_url(ref, path), headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
            payload = json.loads(body.decode("utf-8"))
            return {
                "ok": True,
                "status": getattr(response, "status", None),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "generation": payload.get("generation"),
                "phase": payload.get("phase"),
                "state_signature": payload.get("state_signature"),
                "body_sha16": sha16(body),
                "canonical_sha16": canonical_hash(payload),
                "payload": payload,
                "headers": {
                    key: headers.get(key, "")
                    for key in ["cache-control", "etag", "x-cache", "x-served-by", "via", "expires", "age"]
                    if headers.get(key, "")
                },
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "generation": None,
            "phase": "",
            "state_signature": "",
            "body_sha16": "",
            "canonical_sha16": "",
            "payload": None,
            "headers": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def decide_phase(previous: dict[str, Any]) -> dict[str, str]:
    latest = ((previous.get("release_memory") or {}).get("latest_seconds"))
    if latest is None:
        return {"phase": "seed", "event": "cold_start", "reason": "no previous release memory"}
    latest = float(latest)
    if latest <= 180:
        return {"phase": "active", "event": "fast_release", "reason": "previous branch shadow released quickly"}
    if latest <= 330:
        return {"phase": "quiet", "event": "normal_release", "reason": "previous branch shadow released slowly but within budget"}
    return {"phase": "repair", "event": "slow_release", "reason": "previous branch shadow exceeded budget"}


def build_state(previous: dict[str, Any], decision: dict[str, str]) -> dict[str, Any]:
    generation = int(previous.get("generation") or 0) + 1
    previous_release = previous.get("release_memory") or {}
    seed = {
        "generation": generation,
        "previous_signature": previous.get("state_signature"),
        "decision": decision,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "created_at": now(),
    }
    return {
        "stage": "N6-externalized-ghost-state-machine",
        "created_at": now(),
        "generation": generation,
        "cycle_index": int(previous.get("cycle_index") or 0) + 1,
        "phase": decision["phase"],
        "event": decision["event"],
        "decision_reason": decision["reason"],
        "previous": {
            "generation": previous.get("generation"),
            "phase": previous.get("phase"),
            "state_signature": previous.get("state_signature"),
        },
        "release_memory": {
            "count": int(previous_release.get("count") or 0),
            "latest_seconds": previous_release.get("latest_seconds"),
            "mean_seconds": previous_release.get("mean_seconds"),
            "pending_current_release": True,
        },
        "executor": {
            "layer": "github_actions",
            "workflow": os.environ.get("GITHUB_WORKFLOW"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "actor": os.environ.get("GITHUB_ACTOR"),
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "server_url": os.environ.get("GITHUB_SERVER_URL"),
        },
        "network_role": {
            "N6": "GitHub Actions reads, decides, writes back, waits for Raw release, and records the release from outside the local machine",
        },
        "state_signature": canonical_hash(seed),
        "truth_boundary": "N6 is externalized execution on GitHub Actions. It is still physical cloud CPU, not network-only computation.",
    }


def verify_commit(commit_hash: str, expected_generation: int, expected_signature: str) -> dict[str, Any]:
    samples = []
    for index in range(3):
        sample = get_raw_json(commit_hash)
        sample["index"] = index + 1
        sample["sampled_at"] = now()
        samples.append(sample)
        if index < 2:
            time.sleep(1)
    return {
        "ok": all(
            item.get("generation") == expected_generation and item.get("state_signature") == expected_signature
            for item in samples
        ),
        "generations": [item.get("generation") for item in samples],
        "x_cache": [(item.get("headers") or {}).get("x-cache", "") for item in samples],
        "samples": samples,
    }


def wait_for_branch_release(expected_generation: int, expected_signature: str, duration: float, interval: float) -> dict[str, Any]:
    started = time.perf_counter()
    max_samples = max(1, int(duration // interval) + 1)
    samples = []
    release_after = None
    for index in range(1, max_samples + 1):
        branch = get_raw_json("main")
        elapsed = round(time.perf_counter() - started, 2)
        released = branch.get("generation") == expected_generation and branch.get("state_signature") == expected_signature
        samples.append(
            {
                "index": index,
                "sampled_at": now(),
                "elapsed_since_write": elapsed,
                "branch": branch,
                "released": released,
            }
        )
        if released:
            release_after = elapsed
            break
        if index < max_samples:
            time.sleep(interval)
    return {
        "released": release_after is not None,
        "release_after_seconds": release_after,
        "branch_generations": [item["branch"].get("generation") for item in samples],
        "branch_signatures": [item["branch"].get("state_signature") for item in samples],
        "branch_x_cache": [(item["branch"].get("headers") or {}).get("x-cache", "") for item in samples],
        "samples": samples,
    }


def finalize_state(state: dict[str, Any], release_after: float, current_sha: str) -> tuple[dict[str, Any], dict[str, Any]]:
    previous_memory = state.get("release_memory") or {}
    old_count = int(previous_memory.get("count") or 0)
    old_mean = previous_memory.get("mean_seconds")
    values = []
    if old_count and old_mean is not None:
        values = [float(old_mean)] * old_count
    values.append(float(release_after))
    state = dict(state)
    state["release_memory"] = {
        "count": old_count + 1,
        "latest_seconds": float(release_after),
        "mean_seconds": round(statistics.mean(values), 3),
        "pending_current_release": False,
    }
    state["self_release"] = {"release_after_seconds": float(release_after), "observed_at": now()}
    state["state_signature"] = canonical_hash(
        {
            "generation": state["generation"],
            "phase": state["phase"],
            "event": state["event"],
            "release_after": release_after,
            "run_id": os.environ.get("GITHUB_RUN_ID"),
        }
    )
    response = put_content(
        STATE_PATH,
        state,
        f"N6 finalize external ghost state cycle {state['generation']}",
        current_sha,
    )
    return state, response


def main() -> int:
    duration = float(os.environ.get("N6_DURATION_SECONDS", "600"))
    interval = float(os.environ.get("N6_INTERVAL_SECONDS", "15"))
    started_at = now()

    current_response = get_content(STATE_PATH)
    previous, previous_sha = decode_content(current_response)
    decision = decide_phase(previous)
    next_state = build_state(previous, decision)
    write_response = put_content(
        STATE_PATH,
        next_state,
        f"N6 external ghost state cycle {next_state['generation']}",
        previous_sha,
    )
    if not write_response.get("ok"):
        print(json.dumps({"ok": False, "stage": "write", "error": write_response}, ensure_ascii=False, indent=2))
        return 1

    write_payload = write_response["payload"]
    commit_hash = ((write_payload.get("commit") or {}).get("sha")) or ""
    content_sha = ((write_payload.get("content") or {}).get("sha")) or ""
    commit_verify = verify_commit(commit_hash, int(next_state["generation"]), str(next_state["state_signature"]))
    release = wait_for_branch_release(int(next_state["generation"]), str(next_state["state_signature"]), duration, interval)
    if release.get("released"):
        final_state, finalize_response = finalize_state(next_state, float(release["release_after_seconds"]), content_sha)
    else:
        final_state = next_state
        finalize_response = {"ok": False, "error": "branch Raw did not release; finalize skipped"}

    report = {
        "ok": bool(write_response.get("ok") and commit_verify.get("ok") and release.get("released") and finalize_response.get("ok")),
        "stage": "N6-externalized-execution",
        "started_at": started_at,
        "finished_at": now(),
        "previous_generation": previous.get("generation"),
        "next_generation": next_state.get("generation"),
        "decision": decision,
        "write": {
            "ok": write_response.get("ok"),
            "status": write_response.get("status"),
            "commit_hash": commit_hash,
            "content_sha": content_sha,
        },
        "commit_verify": commit_verify,
        "branch_release": release,
        "finalize": {
            "ok": finalize_response.get("ok"),
            "status": finalize_response.get("status"),
            "error": finalize_response.get("error"),
        },
        "final_state": final_state,
        "truth_boundary": "This proves external execution on GitHub Actions, not network-only computation.",
    }

    report_sha = None
    existing_report = get_content(REPORT_PATH)
    if existing_report.get("ok") and isinstance(existing_report.get("payload"), dict):
        report_sha = existing_report["payload"].get("sha")
    report_response = put_content(REPORT_PATH, report, f"N6 external run report {report['next_generation']}", report_sha)
    report["report_write"] = {"ok": report_response.get("ok"), "status": report_response.get("status"), "error": report_response.get("error")}

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
