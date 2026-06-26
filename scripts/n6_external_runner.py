from __future__ import annotations

import base64
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


STATE_PATH = "states/ghost-state.json"
REPORT_PATH = "states/n6-last-run.json"
LOCK_PATH = "states/n7-run-lock.json"
USER_AGENT = "qimingxing-n7-external-runner/0.2"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def future(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=float(seconds))).isoformat()


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


def maybe_decode_content(response: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not response.get("ok") or not isinstance(response.get("payload"), dict):
        return None, ""
    return decode_content(response)


def put_content(path: str, value: dict[str, Any], message: str, sha: str | None = None) -> dict[str, Any]:
    content = base64.b64encode((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")
    payload: dict[str, Any] = {"message": message, "content": content, "branch": "main"}
    if sha:
        payload["sha"] = sha
    return api_request("PUT", f"/contents/{path}", payload)


def run_owner() -> dict[str, Any]:
    return {
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "actor": os.environ.get("GITHUB_ACTOR"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "server_url": os.environ.get("GITHUB_SERVER_URL"),
    }


def state_fingerprint(state: dict[str, Any], state_sha: str) -> dict[str, Any]:
    return {
        "generation": state.get("generation"),
        "phase": state.get("phase"),
        "state_signature": state.get("state_signature"),
        "content_sha": state_sha,
    }


def lock_is_active(lock: dict[str, Any] | None) -> bool:
    return bool(lock and lock.get("locked") is True)


def lock_is_expired(lock: dict[str, Any] | None) -> bool:
    if not lock:
        return True
    expires_at = parse_time(lock.get("expires_at"))
    if expires_at is None:
        return True
    return datetime.now(timezone.utc) >= expires_at


def lock_same_owner(lock: dict[str, Any] | None) -> bool:
    if not lock:
        return False
    owner = lock.get("owner") or {}
    return (
        str(owner.get("run_id") or "") == str(os.environ.get("GITHUB_RUN_ID") or "")
        and str(owner.get("run_attempt") or "") == str(os.environ.get("GITHUB_RUN_ATTEMPT") or "")
    )


def append_lock_event(lock: dict[str, Any], event: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    updated = dict(lock)
    events = list(updated.get("events") or [])[-12:]
    entry = {"at": now(), "event": event}
    if details:
        entry.update(details)
    events.append(entry)
    updated["events"] = events
    updated["updated_at"] = now()
    return updated


def build_lock(
    state: dict[str, Any],
    state_sha: str,
    ttl_seconds: float,
    checkpoint: str,
    target_generation: int | None = None,
    previous_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generation = int(state.get("generation") or 0)
    lock = {
        "stage": "N7-external-breakpoint-recovery-and-anti-reentry",
        "locked": True,
        "checkpoint": checkpoint,
        "owner": run_owner(),
        "created_at": now(),
        "updated_at": now(),
        "expires_at": future(ttl_seconds),
        "generation_before": generation,
        "target_generation": int(target_generation if target_generation is not None else generation + 1),
        "state_before": state_fingerprint(state, state_sha),
        "truth_boundary": "This is a state-level lock for external GitHub Actions execution. It is not hardware-free computation.",
        "events": [],
    }
    if previous_lock:
        lock["previous_lock"] = {
            "checkpoint": previous_lock.get("checkpoint"),
            "owner": previous_lock.get("owner"),
            "created_at": previous_lock.get("created_at"),
            "expires_at": previous_lock.get("expires_at"),
            "target_generation": previous_lock.get("target_generation"),
            "locked": previous_lock.get("locked"),
        }
        lock["events"] = list(previous_lock.get("events") or [])[-8:]
    return append_lock_event(lock, checkpoint)


def write_report(report: dict[str, Any]) -> dict[str, Any]:
    existing_report = get_content(REPORT_PATH)
    report_sha = None
    if existing_report.get("ok") and isinstance(existing_report.get("payload"), dict):
        report_sha = existing_report["payload"].get("sha")
    generation = report.get("next_generation") or report.get("generation") or report.get("target_generation") or "safe"
    response = put_content(REPORT_PATH, report, f"N7 external run report {generation}", report_sha)
    report["report_write"] = {"ok": response.get("ok"), "status": response.get("status"), "error": response.get("error")}
    return report


def read_lock() -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    response = get_content(LOCK_PATH)
    lock, lock_sha = maybe_decode_content(response)
    return lock, lock_sha, response


def put_lock(lock: dict[str, Any], lock_sha: str, message: str) -> dict[str, Any]:
    return put_content(LOCK_PATH, lock, message, lock_sha or None)


def safe_exit(report: dict[str, Any], exit_code: int = 0) -> int:
    report = write_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


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
        "stage": "N7-externalized-ghost-state-machine-with-lock",
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
            "N7": "GitHub Actions reads, claims a state lock, decides, writes back, waits for Raw release, finalizes, and prevents duplicate external mutation",
        },
        "state_signature": canonical_hash(seed),
        "truth_boundary": "N7 is externalized execution on GitHub Actions with checkpoint recovery and anti-reentry. It is still physical cloud CPU, not network-only computation.",
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
        f"N7 finalize external ghost state cycle {state['generation']}",
        current_sha,
    )
    return state, response


def content_sha_from_put(response: dict[str, Any]) -> str:
    if not response.get("ok") or not isinstance(response.get("payload"), dict):
        return ""
    return str(((response.get("payload") or {}).get("content") or {}).get("sha") or "")


def commit_hash_from_put(response: dict[str, Any]) -> str:
    if not response.get("ok") or not isinstance(response.get("payload"), dict):
        return ""
    return str(((response.get("payload") or {}).get("commit") or {}).get("sha") or "")


def main() -> int:
    duration = float(os.environ.get("N6_DURATION_SECONDS", "600"))
    interval = float(os.environ.get("N6_INTERVAL_SECONDS", "15"))
    lock_ttl = float(os.environ.get("N7_LOCK_TTL_SECONDS", str(max(duration + 300, 900))))
    retry_ttl = float(os.environ.get("N7_RETRY_LOCK_TTL_SECONDS", "300"))
    started_at = now()

    current_response = get_content(STATE_PATH)
    previous, previous_sha = decode_content(current_response)
    existing_lock, lock_sha, lock_read_response = read_lock()
    stale_lock_clear: dict[str, Any] | None = None

    if lock_is_active(existing_lock) and not lock_is_expired(existing_lock) and not lock_same_owner(existing_lock):
        return safe_exit(
            {
                "ok": True,
                "safe_exit": True,
                "stage": "N7-blocked-by-active-lock",
                "started_at": started_at,
                "finished_at": now(),
                "lock": existing_lock,
                "state": state_fingerprint(previous, previous_sha),
                "truth_boundary": "A different external run owns the riverbed lock. This proves anti-reentry, not network-only computation.",
            },
            0,
        )

    if lock_is_active(existing_lock) and lock_is_expired(existing_lock):
        target_generation = int((existing_lock or {}).get("target_generation") or -1)
        current_generation = int(previous.get("generation") or 0)
        pending_release = bool((previous.get("release_memory") or {}).get("pending_current_release"))
        if current_generation == target_generation and pending_release:
            recovery_lock = build_lock(
                previous,
                previous_sha,
                lock_ttl,
                "recovery_claimed",
                target_generation=target_generation,
                previous_lock=existing_lock,
            )
            lock_response = put_lock(recovery_lock, lock_sha, f"N7 claim recovery lock {target_generation}")
            if not lock_response.get("ok"):
                return safe_exit(
                    {
                        "ok": False,
                        "stage": "N7-recovery-lock-acquire-failed",
                        "started_at": started_at,
                        "finished_at": now(),
                        "lock_write": lock_response,
                        "state": state_fingerprint(previous, previous_sha),
                        "truth_boundary": "The recovery lock could not be acquired, so the external runner refused to mutate state.",
                    },
                    1,
                )

            recovery_lock_sha = content_sha_from_put(lock_response)
            recovery_duration = float(os.environ.get("N7_RECOVERY_DURATION_SECONDS", str(min(duration, 180))))
            release = wait_for_branch_release(
                current_generation,
                str(previous.get("state_signature")),
                recovery_duration,
                interval,
            )
            if release.get("released"):
                lock_created_at = parse_time((existing_lock or {}).get("created_at"))
                observed_release = float(release["release_after_seconds"])
                if lock_created_at:
                    observed_release = max(
                        observed_release,
                        round((datetime.now(timezone.utc) - lock_created_at).total_seconds(), 3),
                    )
                recovery_state = dict(previous)
                recovery_state["n7_recovery"] = {
                    "recovered_from_lock": True,
                    "previous_lock_created_at": (existing_lock or {}).get("created_at"),
                    "previous_lock_expires_at": (existing_lock or {}).get("expires_at"),
                    "observed_release_seconds": observed_release,
                    "recovered_at": now(),
                }
                final_state, finalize_response = finalize_state(recovery_state, observed_release, previous_sha)
                checkpoint = "recovery_completed" if finalize_response.get("ok") else "recovery_finalize_failed"
                finished_lock = append_lock_event(
                    recovery_lock,
                    checkpoint,
                    {
                        "finalize_ok": finalize_response.get("ok"),
                        "target_generation": target_generation,
                        "observed_release_seconds": observed_release,
                    },
                )
                finished_lock["checkpoint"] = checkpoint
                finished_lock["locked"] = not bool(finalize_response.get("ok"))
                finished_lock["completed_at"] = now() if finalize_response.get("ok") else None
                finished_lock["expires_at"] = now() if finalize_response.get("ok") else future(retry_ttl)
                lock_done_response = put_lock(
                    finished_lock,
                    recovery_lock_sha,
                    f"N7 recovery {checkpoint} {target_generation}",
                )
                return safe_exit(
                    {
                        "ok": bool(finalize_response.get("ok") and lock_done_response.get("ok")),
                        "stage": "N7-breakpoint-recovery",
                        "started_at": started_at,
                        "finished_at": now(),
                        "generation": target_generation,
                        "recovered": True,
                        "branch_release": release,
                        "finalize": {
                            "ok": finalize_response.get("ok"),
                            "status": finalize_response.get("status"),
                            "error": finalize_response.get("error"),
                        },
                        "lock_update": {
                            "ok": lock_done_response.get("ok"),
                            "status": lock_done_response.get("status"),
                            "error": lock_done_response.get("error"),
                        },
                        "final_state": final_state,
                        "truth_boundary": "N7 recovered an unfinished GitHub Actions state write. This is external checkpoint recovery, not hardware-free execution.",
                    },
                    0 if finalize_response.get("ok") and lock_done_response.get("ok") else 1,
                )

            retry_lock = append_lock_event(
                recovery_lock,
                "recovery_release_timeout",
                {"target_generation": target_generation, "retry_after_seconds": retry_ttl},
            )
            retry_lock["checkpoint"] = "recovery_release_timeout"
            retry_lock["locked"] = True
            retry_lock["expires_at"] = future(retry_ttl)
            lock_retry_response = put_lock(retry_lock, recovery_lock_sha, f"N7 recovery release timeout {target_generation}")
            return safe_exit(
                {
                    "ok": False,
                    "stage": "N7-recovery-release-timeout",
                    "started_at": started_at,
                    "finished_at": now(),
                    "generation": target_generation,
                    "branch_release": release,
                    "lock_update": {
                        "ok": lock_retry_response.get("ok"),
                        "status": lock_retry_response.get("status"),
                        "error": lock_retry_response.get("error"),
                    },
                    "truth_boundary": "The external state remained pending; N7 kept a short retry lock instead of advancing a new generation.",
                },
                1,
            )

        cleared_lock = append_lock_event(
            existing_lock or {},
            "stale_lock_cleared",
            {
                "current_generation": current_generation,
                "target_generation": target_generation,
                "pending_release": pending_release,
            },
        )
        cleared_lock["checkpoint"] = "stale_lock_cleared"
        cleared_lock["locked"] = False
        cleared_lock["cleared_at"] = now()
        cleared_lock["expires_at"] = now()
        clear_response = put_lock(cleared_lock, lock_sha, f"N7 clear stale lock {target_generation}")
        stale_lock_clear = {
            "ok": clear_response.get("ok"),
            "status": clear_response.get("status"),
            "error": clear_response.get("error"),
            "previous_lock": existing_lock,
        }
        existing_lock, lock_sha, lock_read_response = read_lock()

    lock_to_write = build_lock(previous, previous_sha, lock_ttl, "lock_acquired")
    lock_response = put_lock(lock_to_write, lock_sha, f"N7 acquire external lock {lock_to_write['target_generation']}")
    if not lock_response.get("ok"):
        return safe_exit(
            {
                "ok": False,
                "stage": "N7-lock-acquire-failed",
                "started_at": started_at,
                "finished_at": now(),
                "lock_read": {
                    "ok": lock_read_response.get("ok"),
                    "status": lock_read_response.get("status"),
                    "error": lock_read_response.get("error"),
                },
                "lock_write": lock_response,
                "state": state_fingerprint(previous, previous_sha),
                "truth_boundary": "N7 refused to mutate the riverbed state because the lock write failed.",
            },
            1,
        )

    active_lock = lock_to_write
    active_lock_sha = content_sha_from_put(lock_response)

    state_check_response = get_content(STATE_PATH)
    state_after_lock, state_after_lock_sha = decode_content(state_check_response)
    unchanged_after_lock = (
        state_after_lock_sha == previous_sha
        and state_after_lock.get("generation") == previous.get("generation")
        and state_after_lock.get("state_signature") == previous.get("state_signature")
    )
    if not unchanged_after_lock:
        unlocked = append_lock_event(
            active_lock,
            "state_changed_after_lock",
            {
                "before": state_fingerprint(previous, previous_sha),
                "after": state_fingerprint(state_after_lock, state_after_lock_sha),
            },
        )
        unlocked["checkpoint"] = "state_changed_after_lock"
        unlocked["locked"] = False
        unlocked["expires_at"] = now()
        unlock_response = put_lock(unlocked, active_lock_sha, "N7 release lock because state changed")
        return safe_exit(
            {
                "ok": True,
                "safe_exit": True,
                "stage": "N7-state-changed-after-lock",
                "started_at": started_at,
                "finished_at": now(),
                "lock_update": {
                    "ok": unlock_response.get("ok"),
                    "status": unlock_response.get("status"),
                    "error": unlock_response.get("error"),
                },
                "before": state_fingerprint(previous, previous_sha),
                "after": state_fingerprint(state_after_lock, state_after_lock_sha),
                "truth_boundary": "Another writer changed the state after lock acquisition; this run exited without advancing.",
            },
            0,
        )

    previous = state_after_lock
    previous_sha = state_after_lock_sha
    decision = decide_phase(previous)
    next_state = build_state(previous, decision)
    write_response = put_content(
        STATE_PATH,
        next_state,
        f"N7 external ghost state cycle {next_state['generation']}",
        previous_sha,
    )
    if not write_response.get("ok"):
        failed_lock = append_lock_event(
            active_lock,
            "state_write_failed",
            {"target_generation": next_state.get("generation"), "write_status": write_response.get("status")},
        )
        failed_lock["checkpoint"] = "state_write_failed"
        failed_lock["locked"] = False
        failed_lock["expires_at"] = now()
        lock_fail_response = put_lock(failed_lock, active_lock_sha, f"N7 release lock after write failure {next_state['generation']}")
        return safe_exit(
            {
                "ok": False,
                "stage": "N7-state-write-failed",
                "started_at": started_at,
                "finished_at": now(),
                "previous_generation": previous.get("generation"),
                "next_generation": next_state.get("generation"),
                "write": write_response,
                "lock_update": {
                    "ok": lock_fail_response.get("ok"),
                    "status": lock_fail_response.get("status"),
                    "error": lock_fail_response.get("error"),
                },
                "truth_boundary": "The external runner acquired the N7 lock but refused to continue after the state write failed.",
            },
            1,
        )

    write_payload = write_response["payload"]
    commit_hash = ((write_payload.get("commit") or {}).get("sha")) or ""
    content_sha = ((write_payload.get("content") or {}).get("sha")) or ""
    written_lock = append_lock_event(
        active_lock,
        "state_written",
        {
            "target_generation": next_state.get("generation"),
            "commit_hash": commit_hash,
            "content_sha": content_sha,
        },
    )
    written_lock["checkpoint"] = "state_written"
    written_lock["write"] = {
        "commit_hash": commit_hash,
        "content_sha": content_sha,
        "target_generation": next_state.get("generation"),
    }
    lock_written_response = put_lock(written_lock, active_lock_sha, f"N7 checkpoint state written {next_state['generation']}")
    if lock_written_response.get("ok"):
        active_lock = written_lock
        active_lock_sha = content_sha_from_put(lock_written_response)

    commit_verify = verify_commit(commit_hash, int(next_state["generation"]), str(next_state["state_signature"]))
    release = wait_for_branch_release(int(next_state["generation"]), str(next_state["state_signature"]), duration, interval)
    if release.get("released"):
        final_state, finalize_response = finalize_state(next_state, float(release["release_after_seconds"]), content_sha)
    else:
        final_state = next_state
        finalize_response = {"ok": False, "error": "branch Raw did not release; finalize skipped"}

    if release.get("released") and finalize_response.get("ok"):
        final_lock = append_lock_event(
            active_lock,
            "completed",
            {
                "target_generation": next_state.get("generation"),
                "release_after_seconds": release.get("release_after_seconds"),
            },
        )
        final_lock["checkpoint"] = "completed"
        final_lock["locked"] = False
        final_lock["completed_at"] = now()
        final_lock["expires_at"] = now()
    else:
        final_lock = append_lock_event(
            active_lock,
            "pending_recovery",
            {
                "target_generation": next_state.get("generation"),
                "release_released": release.get("released"),
                "finalize_ok": finalize_response.get("ok"),
                "retry_after_seconds": retry_ttl,
            },
        )
        final_lock["checkpoint"] = "pending_recovery"
        final_lock["locked"] = True
        final_lock["expires_at"] = future(retry_ttl)
    lock_final_response = put_lock(final_lock, active_lock_sha, f"N7 lock {final_lock['checkpoint']} {next_state['generation']}")

    report = {
        "ok": bool(
            write_response.get("ok")
            and commit_verify.get("ok")
            and release.get("released")
            and finalize_response.get("ok")
            and lock_final_response.get("ok")
        ),
        "stage": "N7-external-breakpoint-recovery-and-anti-reentry",
        "started_at": started_at,
        "finished_at": now(),
        "previous_generation": previous.get("generation"),
        "next_generation": next_state.get("generation"),
        "decision": decision,
        "stale_lock_clear": stale_lock_clear,
        "lock": {
            "acquire": {
                "ok": lock_response.get("ok"),
                "status": lock_response.get("status"),
                "content_sha": active_lock_sha,
            },
            "state_written_checkpoint": {
                "ok": lock_written_response.get("ok"),
                "status": lock_written_response.get("status"),
                "error": lock_written_response.get("error"),
            },
            "final": {
                "checkpoint": final_lock.get("checkpoint"),
                "locked": final_lock.get("locked"),
                "ok": lock_final_response.get("ok"),
                "status": lock_final_response.get("status"),
                "error": lock_final_response.get("error"),
            },
        },
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
        "truth_boundary": "N7 proves external checkpointing and anti-reentry on GitHub Actions. It still uses GitHub cloud CPU and does not prove hardware-free network computation.",
    }
    return safe_exit(report, 0 if report["ok"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())
