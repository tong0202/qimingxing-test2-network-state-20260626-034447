from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from nsl_l6_scheduled_receiver_loop import (
    CAPSULE_PATH,
    canonical_hash,
    commit_hash_from_put,
    content_sha_from_put,
    decode_content,
    fetch_json_url,
    get_content,
    put_content,
    raw_url,
    run_owner,
    stable_hash,
    validate_capsule,
    verify_stored_hash,
)


LOCK_PATH = "states/nsl-l7-soak-lock.json"
LOOP_STATE_PATH = "states/nsl-l7-soak-state.json"
LAST_RUN_PATH = "states/nsl-l7-last-run.json"
CYCLE_PREFIX = "states/nsl-l7-soak-cycles"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def future(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=float(seconds))).isoformat()


def lock_active(lock: dict[str, Any] | None) -> bool:
    if not lock or lock.get("locked") is not True:
        return False
    expires_at = parse_time(lock.get("expires_at"))
    return bool(expires_at and datetime.now(timezone.utc) < expires_at)


def make_lock(run_id: str, ttl_seconds: int, previous_lock: dict[str, Any] | None) -> dict[str, Any]:
    events = list((previous_lock or {}).get("events") or [])[-20:]
    events.append({"at": now(), "event": "lock_acquired", "run_id": run_id, "owner": run_owner()})
    return {
        "stage": "L7-natural-cron-soak-lock",
        "locked": True,
        "checkpoint": "running",
        "run_id": run_id,
        "owner": run_owner(),
        "created_at": now(),
        "updated_at": now(),
        "expires_at": future(ttl_seconds),
        "ttl_seconds": ttl_seconds,
        "events": events,
        "truth_boundary": "This lock prevents overlapping GitHub Actions cron executions. It is not CPU-free network computation.",
    }


def release_lock(lock: dict[str, Any], checkpoint: str, details: dict[str, Any]) -> dict[str, Any]:
    released = dict(lock)
    events = list(released.get("events") or [])[-20:]
    events.append({"at": now(), "event": "lock_released", "checkpoint": checkpoint, "details": details})
    released.update(
        {
            "locked": False,
            "checkpoint": checkpoint,
            "updated_at": now(),
            "released_at": now(),
            "events": events,
        }
    )
    return released


def write_last_run(report: dict[str, Any]) -> dict[str, Any]:
    _, sha = decode_content(get_content(LAST_RUN_PATH))
    return put_content(LAST_RUN_PATH, report, f"L7 natural cron soak report {report['run_id']}", sha)


def build_pulse(
    run_id: str,
    cycle_index: int,
    generation: int,
    pulse_path: str,
    capsule: dict[str, Any],
    capsule_read: dict[str, Any],
    validation: dict[str, Any],
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    pulse = {
        "stage": "L7-natural-cron-soak-pulse",
        "created_at": now(),
        "run_id": run_id,
        "cycle_index": cycle_index,
        "generation": generation,
        "state_signature": f"{run_id}-cycle-{cycle_index:03d}",
        "executor": "github_actions_schedule",
        "owner": run_owner(),
        "capsule_id": capsule.get("capsule_id"),
        "capsule_generation": capsule.get("generation"),
        "capsule_path": CAPSULE_PATH,
        "pulse_path": pulse_path,
        "previous_loop_state_hash": (previous_state or {}).get("state_hash"),
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
        "action": {"type": "emit_program_pulse", "meaning": "L7 自然 cron soak 中的一次受控胶囊脉冲。"},
        "pulse_hash": "",
        "truth_boundary": "This pulse is emitted by GitHub Actions schedule after reading the network-resident capsule.",
    }
    pulse["pulse_hash"] = stable_hash(pulse, "pulse_hash")
    return pulse


def build_state(
    run_id: str,
    cycle_index: int,
    generation: int,
    capsule: dict[str, Any],
    previous_state: dict[str, Any] | None,
    pulse: dict[str, Any],
    pulse_path: str,
    recovery_events: list[dict[str, Any]],
) -> dict[str, Any]:
    history = list((previous_state or {}).get("history") or [])[-40:]
    history.append(
        {
            "cycle_index": cycle_index,
            "generation": generation,
            "pulse_path": pulse_path,
            "pulse_hash": pulse.get("pulse_hash"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "executor_run_id": os.environ.get("GITHUB_RUN_ID"),
            "created_at": pulse.get("created_at"),
        }
    )
    state = {
        "stage": "L7-natural-cron-soak-and-recovery",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "state_signature": f"{run_id}-soak-state-{generation:03d}",
        "executor": "github_actions_schedule",
        "owner": run_owner(),
        "capsule": {
            "path": CAPSULE_PATH,
            "id": capsule.get("capsule_id"),
            "generation": capsule.get("generation"),
            "hash": capsule.get("capsule_hash"),
            "receiver": capsule.get("receiver"),
        },
        "previous": {
            "generation": (previous_state or {}).get("generation"),
            "state_hash": (previous_state or {}).get("state_hash"),
        },
        "latest_pulse": {"path": pulse_path, "hash": pulse.get("pulse_hash"), "cycle_index": cycle_index},
        "history": history,
        "recovery_events": recovery_events[-20:],
        "loop_rule": "NATURAL CRON -> ACQUIRE LOCK -> READ CAPSULE RAW -> VALIDATE -> EMIT PULSE -> UPDATE SOAK STATE -> RELEASE LOCK",
        "state_hash": "",
        "truth_boundary": "L7 proves natural cron soak/recovery around the receiver-capsule loop. GitHub Actions CPU still performs interpretation and writes.",
    }
    state["state_hash"] = stable_hash(state, "state_hash")
    return state


def run_cycle(run_id: str, cycle_index: int) -> dict[str, Any]:
    capsule_read = fetch_json_url(raw_url(CAPSULE_PATH), f"l7-cycle-{cycle_index}-capsule-raw")
    capsule = capsule_read.get("payload") if isinstance(capsule_read.get("payload"), dict) else {}
    validation = validate_capsule(capsule)

    previous_state_response = get_content(LOOP_STATE_PATH)
    previous_state, state_sha = decode_content(previous_state_response)
    previous_state_hash_ok = verify_stored_hash(previous_state, "state_hash")
    recovery_events: list[dict[str, Any]] = []
    if previous_state and not previous_state_hash_ok:
        recovery_events.append(
            {
                "at": now(),
                "event": "invalid_previous_state_hash",
                "previous_generation": previous_state.get("generation"),
                "previous_state_hash": previous_state.get("state_hash"),
            }
        )
        previous_state = None
        state_sha = ""

    previous_generation = int((previous_state or {}).get("generation") or 0)
    generation = previous_generation + 1
    continuity_ok = previous_state_hash_ok and generation == previous_generation + 1
    run_key = str(os.environ.get("GITHUB_RUN_ID") or run_id)
    attempt = str(os.environ.get("GITHUB_RUN_ATTEMPT") or "1")
    pulse_path = f"{CYCLE_PREFIX}/{run_id}-cycle-{cycle_index:03d}-run-{run_key}-attempt-{attempt}.json"
    pulse = build_pulse(run_id, cycle_index, generation, pulse_path, capsule, capsule_read, validation, previous_state)
    _, pulse_sha = decode_content(get_content(pulse_path))
    pulse_write = put_content(pulse_path, pulse, f"L7 natural cron soak pulse {run_id} cycle {cycle_index}", pulse_sha)
    pulse_commit = commit_hash_from_put(pulse_write)
    pulse_commit_raw = fetch_json_url(raw_url(pulse_path, pulse_commit), f"l7-cycle-{cycle_index}-pulse-commit") if pulse_commit else {}
    pulse_commit_raw_ok = bool(
        pulse_commit_raw.get("ok")
        and pulse_commit_raw.get("generation") == generation
        and pulse_commit_raw.get("state_signature") == pulse.get("state_signature")
    )

    state = build_state(run_id, cycle_index, generation, capsule, previous_state, pulse, pulse_path, recovery_events)
    state_write = put_content(LOOP_STATE_PATH, state, f"L7 natural cron soak state {run_id} generation {generation}", state_sha)
    state_api, _ = decode_content(get_content(LOOP_STATE_PATH))
    state_api_verify_ok = bool(
        state_api
        and state_api.get("generation") == generation
        and state_api.get("state_hash") == state.get("state_hash")
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
        "recovery_events": recovery_events,
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
        "pulse_commit_raw_verify": {"ok": pulse_commit_raw_ok, "sample": pulse_commit_raw},
        "state_path": LOOP_STATE_PATH,
        "state_hash": state.get("state_hash"),
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
        "recovery_event_count": len(cycle.get("recovery_events") or []),
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
    run_id = f"nsl-l7-cron-{run_key}-attempt-{attempt}"
    lock_ttl = env_int("L7_LOCK_TTL_SECONDS", 900)
    cycles_requested = env_int("L7_CYCLES", 1)
    cycle_delay = env_float("L7_CYCLE_DELAY_SECONDS", 0.0)

    lock_response = get_content(LOCK_PATH)
    existing_lock, lock_sha = decode_content(lock_response)
    if lock_active(existing_lock):
        report = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "L7-natural-cron-soak-and-recovery",
            "ok": True,
            "skipped": True,
            "skip_reason": "active_lock",
            "executor": "github_actions_schedule",
            "owner": run_owner(),
            "active_lock": existing_lock,
            "evidence_level": "L7-natural-cron-lock-skip",
            "truth_boundary": "A scheduled run skipped because another lock was active. This is anti-reentry evidence, not CPU-free computation.",
        }
        write_last_run(report)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        return 0

    stale_lock_recovered = bool(existing_lock and existing_lock.get("locked") is True and not lock_active(existing_lock))
    lock = make_lock(run_id, lock_ttl, existing_lock)
    lock["stale_lock_recovered"] = stale_lock_recovered
    lock_write = put_content(LOCK_PATH, lock, f"L7 natural cron lock acquire {run_id}", lock_sha)

    cycles: list[dict[str, Any]] = []
    final_report: dict[str, Any]
    try:
        for cycle_index in range(1, cycles_requested + 1):
            cycles.append(run_cycle(run_id, cycle_index))
            if cycle_index < cycles_requested and cycle_delay:
                time.sleep(cycle_delay)
        summaries = [cycle_summary(cycle) for cycle in cycles]
        cycles_ok = sum(1 for item in summaries if item["ok"])
        ok = bool(lock_write.get("ok") and cycles and cycles_ok == len(cycles))
        final_report = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "L7-natural-cron-soak-and-recovery",
            "ok": ok,
            "skipped": False,
            "executor": "github_actions_schedule",
            "owner": run_owner(),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "lock_path": LOCK_PATH,
            "lock_acquire": {"ok": lock_write.get("ok"), "status": lock_write.get("status"), "error": lock_write.get("error")},
            "stale_lock_recovered": stale_lock_recovered,
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
                "recovery_event_count": sum(item["recovery_event_count"] for item in summaries),
            },
            "evidence_level": "L7-natural-cron-soak-and-recovery" if ok else "L7-natural-cron-soak-partial",
            "conclusion": (
                "L7 成立：自然 cron 触发的 GitHub Actions 已完成接收器胶囊闭环，并通过锁/恢复层记录执行连续性。"
                if ok
                else "L7 部分成立：自然 cron 触发了执行器，但至少一个闭环校验未通过。"
            ),
            "truth_boundary": "L7 proves natural GitHub Actions cron soak/recovery around the receiver-capsule loop. GitHub Actions CPU still performs interpretation and writes; this is not CPU-free network computation.",
        }
    except Exception as exc:
        final_report = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "L7-natural-cron-soak-and-recovery",
            "ok": False,
            "skipped": False,
            "executor": "github_actions_schedule",
            "owner": run_owner(),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "lock_path": LOCK_PATH,
            "lock_acquire": {"ok": lock_write.get("ok"), "status": lock_write.get("status"), "error": lock_write.get("error")},
            "error": f"{type(exc).__name__}: {exc}",
            "evidence_level": "L7-natural-cron-soak-error",
            "truth_boundary": "L7 error report. GitHub Actions CPU still performs interpretation and writes.",
        }
    finally:
        latest_lock, latest_lock_sha = decode_content(get_content(LOCK_PATH))
        if latest_lock and latest_lock.get("run_id") == run_id:
            released = release_lock(latest_lock, "completed" if final_report.get("ok") else "failed", {"ok": final_report.get("ok")})
            put_content(LOCK_PATH, released, f"L7 natural cron lock release {run_id}", latest_lock_sha)

    report_write = write_last_run(final_report)
    final_report["remote_report_write"] = {
        "ok": report_write.get("ok"),
        "status": report_write.get("status"),
        "error": report_write.get("error"),
        "content_sha": content_sha_from_put(report_write),
    }
    print(json.dumps(final_report, ensure_ascii=False, indent=2), flush=True)
    return 0 if final_report.get("ok") and report_write.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
