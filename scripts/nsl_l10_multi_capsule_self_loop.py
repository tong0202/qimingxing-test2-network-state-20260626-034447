from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from nsl_l3_receiver_probe import gh_token, now, put_content, raw_url, write_json
from nsl_l4_receiver_capsule import commit_hash_from_put, content_get, content_sha_from_put, fetch_json_url
from nsl_l8_multi_capsule_language import put_json_file, stable_hash, validate_index, wait_for_branch_release
from nsl_l9_multi_capsule_loop_interpreter import load_remote_capsules, load_remote_index, interpret_graph, index_hash_ok


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

SIGNAL_PREFIX = "states/nsl-l10-signals"
CYCLE_PREFIX = "states/nsl-l10-cycles"
LOOP_STATE_PATH = "states/nsl-l10-loop-state.json"
LAST_REPORT_PATH = "states/nsl-l10-last-self-loop-report.json"
LOCK_PATH = "states/nsl-l10-self-loop-lock.json"


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
    previous, sha, _ = content_get(owner, repo, LOCK_PATH, token)
    if lock_active(previous):
        return {"ok": False, "skipped": True, "active_lock": previous, "write": {}}
    lock = {
        "stage": "L10-multi-capsule-self-loop-lock",
        "locked": True,
        "checkpoint": "running",
        "run_id": run_id,
        "owner": run_owner(mode),
        "created_at": now(),
        "updated_at": now(),
        "expires_at": future(ttl_seconds),
        "ttl_seconds": ttl_seconds,
        "previous_lock_recovered": bool(previous and previous.get("locked") is True),
        "truth_boundary": "This lock prevents overlapping L10 controlled interpreter loops. It is not autonomous network self-execution.",
    }
    write = put_content(owner, repo, LOCK_PATH, lock, f"L10 self-loop lock acquire {run_id}", token, sha)
    return {"ok": bool(write.get("ok")), "skipped": False, "lock": lock, "write": write}


def release_lock(owner: str, repo: str, token: str, run_id: str, ok: bool) -> dict[str, Any]:
    lock, sha, _ = content_get(owner, repo, LOCK_PATH, token)
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
        }
    )
    write = put_content(owner, repo, LOCK_PATH, released, f"L10 self-loop lock release {run_id}", token, sha)
    return {"ok": bool(write.get("ok")), "status": write.get("status"), "error": write.get("error")}


def signal_path(run_id: str, cycle_index: int, step_index: int, role: str) -> str:
    return f"{SIGNAL_PREFIX}/{run_id}-cycle-{cycle_index:03d}-step-{step_index:03d}-{role}.json"


def cycle_state_path(run_id: str, cycle_index: int) -> str:
    return f"{CYCLE_PREFIX}/{run_id}-cycle-{cycle_index:03d}.json"


def build_l10_signal(
    run_id: str,
    mode: str,
    cycle_index: int,
    l9_signal: dict[str, Any],
    step: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    signal = {
        "stage": "L10-multi-capsule-low-frequency-self-loop-signal",
        "schema_version": "NSL-L10-SIGNAL-0.1",
        "created_at": now(),
        "run_id": run_id,
        "cycle_index": cycle_index,
        "step_index": step.get("step_index"),
        "role": step.get("role"),
        "path": path,
        "owner": run_owner(mode),
        "capsule_id": step.get("capsule_id"),
        "capsule_hash": l9_signal.get("capsule_hash"),
        "network_id": l9_signal.get("network_id"),
        "network_hash": l9_signal.get("network_hash"),
        "inputs_required": l9_signal.get("inputs_required") or [],
        "signals_before": l9_signal.get("signals_before") or [],
        "signals_out": step.get("signals_out") or [],
        "signals_after": l9_signal.get("signals_after") or [],
        "decision": l9_signal.get("decision") or {},
        "interpreted_action": {
            "type": step.get("action"),
            "executed": bool(step.get("ok")),
            "effect": "emit declarative signal only; no arbitrary capsule body execution",
        },
        "signal_hash": "",
        "truth_boundary": "L10 signal is emitted by a controlled low-frequency interpreter loop, not by autonomous network self-execution.",
    }
    return seal(signal, "signal_hash")


def build_cycle_state(
    run_id: str,
    mode: str,
    cycle_index: int,
    index: dict[str, Any],
    interpretation: dict[str, Any],
    signal_paths: list[str],
    signal_hashes: list[str],
) -> dict[str, Any]:
    state = {
        "stage": "L10-multi-capsule-low-frequency-cycle",
        "schema_version": "NSL-L10-CYCLE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "cycle_index": cycle_index,
        "owner": run_owner(mode),
        "network_id": index.get("network_id"),
        "network_hash": index.get("network_hash"),
        "route": interpretation.get("route"),
        "step_count": len(interpretation.get("steps") or []),
        "network_language_pulse": interpretation.get("network_language_pulse"),
        "signal_paths": signal_paths,
        "signal_hashes": signal_hashes,
        "cycle_hash": "",
        "truth_boundary": "This cycle records one controlled interpretation pass over the L8/L9 multi-capsule language graph.",
    }
    return seal(state, "cycle_hash")


def build_loop_state(
    run_id: str,
    mode: str,
    generation: int,
    cycle_results: list[dict[str, Any]],
    previous_state: dict[str, Any] | None,
    cycle_delay_seconds: float,
) -> dict[str, Any]:
    history = list((previous_state or {}).get("history") or [])[-30:]
    history.append(
        {
            "run_id": run_id,
            "generation": generation,
            "cycle_count": len(cycle_results),
            "cycles_ok": sum(1 for item in cycle_results if item.get("ok")),
            "mode": mode,
            "created_at": now(),
        }
    )
    final_cycle = cycle_results[-1] if cycle_results else {}
    state = {
        "stage": "L10-multi-capsule-low-frequency-self-loop",
        "schema_version": "NSL-L10-LOOP-STATE-0.1",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "owner": run_owner(mode),
        "mode": mode,
        "cycle_delay_seconds": cycle_delay_seconds,
        "cycle_count": len(cycle_results),
        "cycles_ok": sum(1 for item in cycle_results if item.get("ok")),
        "network_id": final_cycle.get("network_id"),
        "network_hash": final_cycle.get("network_hash"),
        "state_signature": f"l10-{run_id}-generation-{generation:03d}",
        "previous": {
            "generation": (previous_state or {}).get("generation"),
            "state_hash": (previous_state or {}).get("state_hash"),
        },
        "cycles": [
            {
                "cycle_index": item.get("cycle_index"),
                "ok": item.get("ok"),
                "cycle_state_path": item.get("cycle_state_path"),
                "cycle_hash": item.get("cycle_hash"),
                "network_language_pulse": item.get("network_language_pulse"),
                "signal_count": len(item.get("signal_paths") or []),
            }
            for item in cycle_results
        ],
        "history": history,
        "state_hash": "",
        "truth_boundary": "L10 proves controlled low-frequency looping and external takeover readiness. It does not prove CPU-free or autonomous network life.",
    }
    return seal(state, "state_hash")


def run_cycle(owner: str, repo: str, token: str, run_id: str, mode: str, cycle_index: int, raw_timeout: int, raw_interval: float) -> dict[str, Any]:
    index_load = load_remote_index(owner, repo)
    index = index_load["index"]
    if not index_hash_ok(index):
        raise RuntimeError("L8 index hash validation failed")
    capsule_load = load_remote_capsules(owner, repo, index)
    graph_validation = validate_index(index, capsule_load["capsules"])
    interpretation = interpret_graph(f"{run_id}-cycle-{cycle_index:03d}", index, capsule_load["capsules"], graph_validation)

    signal_writes: list[dict[str, Any]] = []
    commit_raw_checks: list[dict[str, Any]] = []
    signal_paths: list[str] = []
    signal_hashes: list[str] = []
    expected_release: list[dict[str, str]] = []

    for l9_signal, step in zip(interpretation.get("signal_records") or [], interpretation.get("steps") or []):
        path = signal_path(run_id, cycle_index, int(step["step_index"]), str(step["role"]))
        signal = build_l10_signal(run_id, mode, cycle_index, l9_signal, step, path)
        write = put_json_file(owner, repo, token, path, signal, f"L10 signal {run_id} cycle {cycle_index} {step['role']}")
        signal_writes.append(write)
        signal_paths.append(path)
        signal_hashes.append(signal["signal_hash"])
        step["signal_path"] = path
        step["signal_hash"] = signal["signal_hash"]
        commit_hash = write.get("commit_hash")
        sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"l10-signal-commit-{cycle_index}-{step['role']}") if commit_hash else {}
        payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
        commit_raw_checks.append(
            {
                "path": path,
                "ok": bool(sample.get("ok") and payload.get("signal_hash") == signal["signal_hash"]),
                "status": sample.get("status"),
                "elapsed_ms": sample.get("elapsed_ms"),
                "observed_hash": payload.get("signal_hash"),
                "expected_hash": signal["signal_hash"],
            }
        )
        expected_release.append({"path": path, "hash_field": "signal_hash", "hash_value": signal["signal_hash"]})

    cycle_state = build_cycle_state(run_id, mode, cycle_index, index, interpretation, signal_paths, signal_hashes)
    c_path = cycle_state_path(run_id, cycle_index)
    cycle_write = put_json_file(owner, repo, token, c_path, cycle_state, f"L10 cycle state {run_id} cycle {cycle_index}")
    expected_release.append({"path": c_path, "hash_field": "cycle_hash", "hash_value": cycle_state["cycle_hash"]})
    branch_release = wait_for_branch_release(owner, repo, expected_release, raw_timeout, raw_interval)

    ok = bool(
        graph_validation.get("ok")
        and interpretation.get("ok")
        and all(item.get("ok") for item in signal_writes)
        and all(item.get("ok") for item in commit_raw_checks)
        and cycle_write.get("ok")
        and branch_release.get("ok")
    )
    return {
        "cycle_index": cycle_index,
        "ok": ok,
        "network_id": index.get("network_id"),
        "network_hash": index.get("network_hash"),
        "index_read": {"ok": index_load["sample"].get("ok"), "elapsed_ms": index_load["sample"].get("elapsed_ms")},
        "capsule_reads": capsule_load["samples"],
        "graph_validation_ok": graph_validation.get("ok"),
        "interpretation_ok": interpretation.get("ok"),
        "route": interpretation.get("route"),
        "steps": interpretation.get("steps"),
        "network_language_pulse": interpretation.get("network_language_pulse"),
        "signal_paths": signal_paths,
        "signal_hashes": signal_hashes,
        "signal_writes_ok": all(item.get("ok") for item in signal_writes),
        "signal_commit_raw_ok": all(item.get("ok") for item in commit_raw_checks),
        "cycle_state_path": c_path,
        "cycle_hash": cycle_state["cycle_hash"],
        "cycle_write_ok": cycle_write.get("ok"),
        "branch_raw_release_ok": branch_release.get("ok"),
        "branch_raw_release": branch_release,
    }


def write_report(run_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# L10：多胶囊低频自循环与外层接管",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- mode: `{result['mode']}`",
        f"- generation: `{result['generation']}`",
        f"- cycles_ok: `{result['aggregate']['cycles_ok']}/{result['aggregate']['cycle_count']}`",
        f"- external_takeover: `{result['external_takeover']}`",
        f"- final_state_hash: `{result['loop_state']['state_hash']}`",
        "",
        "## 周期",
        "",
        "| cycle | ok | pulse | signals |",
        "| ---: | --- | --- | ---: |",
    ]
    for cycle in result["cycles"]:
        lines.append(
            f"| {cycle['cycle_index']} | `{cycle['ok']}` | `{cycle['network_language_pulse']}` | {len(cycle.get('signal_paths') or [])} |"
        )
    lines.extend(
        [
            "",
            "## 真实含义",
            "",
            result["conclusion"],
            "",
            "## 边界",
            "",
            result["truth_boundary"],
            "",
        ]
    )
    (run_dir / "nsl_l10_multi_capsule_self_loop_report.md").write_text("\n".join(lines), encoding="utf-8")


def publish_remote_report(owner: str, repo: str, token: str, result: dict[str, Any]) -> dict[str, Any]:
    remote = {
        "run_id": result["run_id"],
        "stage": result["stage"],
        "created_at": result["created_at"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "mode": result["mode"],
        "owner": result["owner"],
        "external_takeover": result["external_takeover"],
        "loop_state_path": LOOP_STATE_PATH,
        "cycles": [
            {
                "cycle_index": item["cycle_index"],
                "ok": item["ok"],
                "network_language_pulse": item["network_language_pulse"],
                "cycle_state_path": item["cycle_state_path"],
                "signal_paths": item["signal_paths"],
            }
            for item in result["cycles"]
        ],
        "aggregate": result["aggregate"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
    }
    _, sha, _ = content_get(owner, repo, LAST_REPORT_PATH, token)
    return put_content(owner, repo, LAST_REPORT_PATH, remote, f"L10 self-loop report {result['run_id']}", token, sha)


def main() -> int:
    parser = argparse.ArgumentParser(description="L10 multi-capsule low-frequency self-loop and external takeover")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--cycle-delay", type=float, default=5.0)
    parser.add_argument("--raw-timeout", type=int, default=180)
    parser.add_argument("--raw-interval", type=float, default=6.0)
    parser.add_argument("--mode", choices=["local", "external"], default="local")
    parser.add_argument("--lock-ttl", type=int, default=1200)
    args = parser.parse_args()

    run_id_prefix = "nsl-l10-external" if args.mode == "external" else "nsl-l10-local"
    gh_run = os.environ.get("GITHUB_RUN_ID")
    run_id = f"{run_id_prefix}-{gh_run or datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    token = gh_token()
    if not token:
        raise RuntimeError("gh auth token is required to run L10")

    lock = acquire_lock(args.owner, args.repo, token, run_id, args.mode, args.lock_ttl)
    if lock.get("skipped"):
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "L10-multi-capsule-low-frequency-self-loop",
            "ok": True,
            "skipped": True,
            "skip_reason": "active_lock",
            "mode": args.mode,
            "owner": run_owner(args.mode),
            "active_lock": lock.get("active_lock"),
            "evidence_level": "L10-self-loop-lock-skip",
            "truth_boundary": "Lock skip proves anti-reentry only, not autonomous network execution.",
        }
        write_json(run_dir / "nsl_l10_multi_capsule_self_loop_result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0

    cycles: list[dict[str, Any]] = []
    ok = False
    try:
        for cycle_index in range(1, max(1, args.cycles) + 1):
            cycles.append(
                run_cycle(args.owner, args.repo, token, run_id, args.mode, cycle_index, args.raw_timeout, args.raw_interval)
            )
            if cycle_index < max(1, args.cycles) and args.cycle_delay:
                time.sleep(args.cycle_delay)

        previous_state, state_sha, _ = content_get(args.owner, args.repo, LOOP_STATE_PATH, token)
        generation = int((previous_state or {}).get("generation") or 0) + 1
        loop_state = build_loop_state(run_id, args.mode, generation, cycles, previous_state, args.cycle_delay)
        loop_state_write = put_content(args.owner, args.repo, LOOP_STATE_PATH, loop_state, f"L10 loop state {run_id}", token, state_sha)
        loop_state_api, _, loop_state_api_response = content_get(args.owner, args.repo, LOOP_STATE_PATH, token)
        loop_state_api_ok = bool(
            loop_state_api_response.get("ok")
            and loop_state_api
            and loop_state_api.get("state_hash") == loop_state["state_hash"]
            and stable_hash(loop_state_api, "state_hash") == loop_state["state_hash"]
        )
        final_release = wait_for_branch_release(
            args.owner,
            args.repo,
            [{"path": LOOP_STATE_PATH, "hash_field": "state_hash", "hash_value": loop_state["state_hash"]}],
            args.raw_timeout,
            args.raw_interval,
        )
        cycles_ok = sum(1 for item in cycles if item.get("ok"))
        ok = bool(cycles and cycles_ok == len(cycles) and loop_state_write.get("ok") and loop_state_api_ok and final_release.get("ok"))
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "L10-multi-capsule-low-frequency-self-loop",
            "ok": ok,
            "mode": args.mode,
            "owner": run_owner(args.mode),
            "external_takeover": bool(args.mode == "external" and os.environ.get("GITHUB_ACTIONS")),
            "generation": generation,
            "loop_state_path": LOOP_STATE_PATH,
            "last_report_path": LAST_REPORT_PATH,
            "cycles": cycles,
            "loop_state": loop_state,
            "verification": {
                "lock_acquire_ok": lock.get("ok"),
                "cycles_ok": cycles_ok,
                "loop_state_write_ok": loop_state_write.get("ok"),
                "loop_state_api_ok": loop_state_api_ok,
                "loop_state_branch_raw_release_ok": final_release.get("ok"),
            },
            "aggregate": {
                "cycle_count": len(cycles),
                "cycles_ok": cycles_ok,
                "all_cycles_ok": cycles_ok == len(cycles),
                "all_pulses": all(item.get("network_language_pulse") for item in cycles),
                "all_branch_raw_release_ok": all(item.get("branch_raw_release_ok") for item in cycles) and final_release.get("ok"),
            },
            "evidence_level": "L10-multi-capsule-low-frequency-self-loop" if ok else "L10-multi-capsule-self-loop-partial",
            "conclusion": (
                "L10 成立：L9 多胶囊解释器已经被推进为多轮低频自循环，并写回可恢复 loop state。"
                if args.mode == "local"
                else "L10 外层接管成立：GitHub Actions 已在本机之外运行多胶囊低频自循环，并写回可恢复 loop state。"
            )
            if ok
            else "L10 部分成立：多胶囊低频循环已尝试运行，但至少一个 cycle、状态写回或 Raw 释放校验未通过。",
            "truth_boundary": (
                "L10 proves controlled low-frequency looping and, in external mode, external runner takeover of the multi-capsule interpreter. "
                "It does not prove CPU-free network computation, autonomous digital life, or digital supercomputing."
            ),
        }
        remote_report_write = publish_remote_report(args.owner, args.repo, token, result)
        result["writes"] = {
            "loop_state": {
                "ok": loop_state_write.get("ok"),
                "status": loop_state_write.get("status"),
                "error": loop_state_write.get("error"),
                "commit_hash": commit_hash_from_put(loop_state_write),
                "content_sha": content_sha_from_put(loop_state_write),
            },
            "remote_report": {
                "ok": remote_report_write.get("ok"),
                "status": remote_report_write.get("status"),
                "error": remote_report_write.get("error"),
                "commit_hash": commit_hash_from_put(remote_report_write),
                "content_sha": content_sha_from_put(remote_report_write),
            },
        }
        write_json(run_dir / "nsl_l10_multi_capsule_self_loop_result.json", result)
        write_json(RUNS / "latest_nsl_l10_multi_capsule_self_loop_result.json", result)
        write_report(run_dir, result)
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "ok": ok,
                    "mode": args.mode,
                    "external_takeover": result["external_takeover"],
                    "evidence_level": result["evidence_level"],
                    "result": str(run_dir / "nsl_l10_multi_capsule_self_loop_result.json"),
                    "report": str(run_dir / "nsl_l10_multi_capsule_self_loop_report.md"),
                    "cycles_ok": f"{cycles_ok}/{len(cycles)}",
                    "loop_state_path": LOOP_STATE_PATH,
                    "truth_boundary": result["truth_boundary"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
    finally:
        release_lock(args.owner, args.repo, token, run_id, ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
