from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_l12_hourly_self_maintenance import (
    acquire_global_lock,
    commit_hash_from_put,
    content_get,
    content_sha_from_put,
    fetch_json_url,
    gh_token,
    now,
    put_content,
    raw_url,
    release_global_lock,
    run_owner,
    wait_for_branch_release,
)
from nsl_l8_multi_capsule_language import INDEX_PATH, stable_hash, validate_index
from nsl_l9_multi_capsule_loop_interpreter import (
    index_hash_ok,
    interpret_graph,
    load_remote_capsules,
    load_remote_index,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

E4_LOOP_STATE_PATH = "states/e4-triggered-interpreter-loop-state.json"
L12_LAST_RUN_PATH = "states/nsl-l12-last-run.json"

SOURCE_PREFIX = "states/e5-external-trigger-loop-sources"
GATE_PREFIX = "states/e5-external-trigger-loop-gates"
SIGNAL_PREFIX = "states/e5-external-trigger-loop-signals"
CYCLE_PREFIX = "states/e5-external-trigger-loop-cycles"
LOOP_STATE_PATH = "states/e5-external-triggered-interpreter-loop-state.json"
LAST_RUN_PATH = "states/e5-last-run.json"
LAST_REPORT_PATH = "states/e5-last-report.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def safe_header_subset(headers: dict[str, Any]) -> dict[str, str]:
    keep = [
        "cache-control",
        "etag",
        "age",
        "x-cache",
        "x-served-by",
        "via",
        "expires",
        "date",
        "last-modified",
    ]
    return {key: str(headers.get(key) or "") for key in keep if headers.get(key) is not None}


def source_path(run_id: str, cycle_index: int) -> str:
    return f"{SOURCE_PREFIX}/{run_id}-cycle-{cycle_index:03d}-source.json"


def gate_path(run_id: str, cycle_index: int) -> str:
    return f"{GATE_PREFIX}/{run_id}-cycle-{cycle_index:03d}-gate.json"


def signal_path(run_id: str, cycle_index: int) -> str:
    return f"{SIGNAL_PREFIX}/{run_id}-cycle-{cycle_index:03d}-signal.json"


def cycle_path(run_id: str, cycle_index: int) -> str:
    return f"{CYCLE_PREFIX}/{run_id}-cycle-{cycle_index:03d}.json"


def put_and_verify(owner: str, repo: str, token: str, path: str, value: dict[str, Any], hash_field: str, message: str) -> dict[str, Any]:
    write: dict[str, Any] = {}
    write_attempts: list[dict[str, Any]] = []
    for attempt in range(1, 4):
        _, sha, _ = content_get(owner, repo, path, token)
        write = put_content(owner, repo, path, value, f"{message} attempt {attempt}", token, sha)
        write_attempts.append(
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
            sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"e5-commit-{path}-attempt-{attempt}")
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
        "write_attempts": write_attempts,
        "commit_attempts": commit_attempts,
    }


def sample_branch_path(owner: str, repo: str, path: str, hash_field: str, label: str) -> dict[str, Any]:
    sample = fetch_json_url(raw_url(owner, repo, "main", path), label)
    payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
    return {
        "ok": bool(sample.get("ok") and payload),
        "status": sample.get("status"),
        "elapsed_ms": sample.get("elapsed_ms"),
        "hash_value": str(payload.get(hash_field) or ""),
        "generation": payload.get("generation"),
        "run_id": payload.get("run_id"),
        "headers": safe_header_subset(sample.get("headers") or {}),
        "error": sample.get("error"),
    }


def observe_network_trigger(
    owner: str,
    repo: str,
    path: str,
    expected_hash: str,
    previous_hash: str,
    cycle_index: int,
    timeout_seconds: int,
    interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    observations: list[dict[str, Any]] = []
    first_seen_at = ""
    started = time.perf_counter()
    while time.time() < deadline:
        sample = sample_branch_path(owner, repo, path, "source_hash", f"e5-cycle-{cycle_index}-source-{len(observations) + 1}")
        sample["matches_expected"] = sample["hash_value"] == expected_hash
        sample["changed_from_previous"] = bool(previous_hash and sample["hash_value"] and sample["hash_value"] != previous_hash)
        observations.append({"at": now(), **sample})
        if sample["matches_expected"]:
            first_seen_at = now()
            break
        time.sleep(interval_seconds)
    post_release_samples: list[dict[str, Any]] = []
    if first_seen_at:
        for index in range(3):
            time.sleep(1.0 if index else 0.0)
            sample = sample_branch_path(owner, repo, path, "source_hash", f"e5-cycle-{cycle_index}-post-{index + 1}")
            sample["matches_expected"] = sample["hash_value"] == expected_hash
            post_release_samples.append({"at": now(), **sample})
    stable_after_release = bool(post_release_samples) and all(item["matches_expected"] for item in post_release_samples)
    trigger_fired = bool(first_seen_at and stable_after_release)
    return {
        "ok": trigger_fired,
        "cycle_index": cycle_index,
        "path": path,
        "trigger_fired": trigger_fired,
        "expected_hash": expected_hash,
        "previous_hash": previous_hash,
        "first_seen_at": first_seen_at,
        "release_after_seconds": round(time.perf_counter() - started, 3) if first_seen_at else None,
        "stable_after_release": stable_after_release,
        "observations": observations[-20:],
        "post_release_samples": post_release_samples,
        "timed_out": not bool(first_seen_at),
        "truth_boundary": (
            "E5 observes branch Raw network-state release as a trigger condition. "
            "The external runner still uses GitHub Actions CPU."
        ),
    }


def load_interpreter_context(owner: str, repo: str, attempts: int = 3) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            index_load = load_remote_index(owner, repo)
            index = index_load["index"]
            if not index_hash_ok(index):
                raise RuntimeError("L8 index hash validation failed")
            capsule_load = load_remote_capsules(owner, repo, index)
            capsules = capsule_load["capsules"]
            graph_validation = validate_index(index, capsules)
            return {
                "ok": True,
                "attempt": attempt,
                "index_load": index_load,
                "index": index,
                "capsule_load": capsule_load,
                "capsules": capsules,
                "graph_validation": graph_validation,
            }
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(2.0 * attempt)
    return {"ok": False, "error": last_error}


def build_cycle_source(
    run_id: str,
    generation: int,
    cycle_index: int,
    path: str,
    previous_source_hash: str,
    previous_signal_hash: str,
    e4_loop_state: dict[str, Any] | None,
    l12_last_run: dict[str, Any] | None,
    mode: str,
) -> dict[str, Any]:
    source = {
        "stage": "E5-external-scheduled-triggered-interpreter-loop-source",
        "schema_version": "QMX-E5-SOURCE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "generation": generation,
        "cycle_index": cycle_index,
        "path": path,
        "owner": run_owner(mode),
        "trigger_kind": "external_runner_branch_raw_release_to_interpreter_loop",
        "trigger_sentence": (
            "WHEN E5_EXTERNAL_SOURCE_HASH APPEARS ON BRANCH_RAW THEN FIRE CYCLE_GATE; "
            "WHEN CYCLE_GATE IS OPEN THEN RUN ONE CONTROLLED NETWORK_LANGUAGE_INTERPRETER STEP"
        ),
        "previous_source_hash": previous_source_hash,
        "previous_signal_hash": previous_signal_hash,
        "source_e4": {
            "run_id": (e4_loop_state or {}).get("run_id"),
            "state_hash": (e4_loop_state or {}).get("state_hash"),
            "cycles_ok": (e4_loop_state or {}).get("cycles_ok"),
            "final_signal_hash": (e4_loop_state or {}).get("final_signal_hash"),
        },
        "source_l12_2": {
            "run_id": (l12_last_run or {}).get("run_id"),
            "slot_id": (l12_last_run or {}).get("slot_id"),
            "state_hash": (l12_last_run or {}).get("state_hash"),
            "window_ok": (l12_last_run or {}).get("window_ok"),
        },
        "interpreter_target": {
            "index_path": INDEX_PATH,
            "expected_network_hash": ((e4_loop_state or {}).get("network_hash")),
        },
        "network_role": "external scheduled trigger surface for the E4 interpreter loop",
        "executor_role": "GitHub Actions external runner observes, interprets, and writes back",
        "source_hash": "",
        "truth_boundary": (
            "E5 source is written by an external scheduled runner and then observed through branch Raw. "
            "It does not prove CPU-free network execution."
        ),
    }
    return seal(source, "source_hash")


def build_gate(run_id: str, cycle_index: int, path: str, source: dict[str, Any], trigger: dict[str, Any]) -> dict[str, Any]:
    gate = {
        "stage": "E5-external-scheduled-triggered-interpreter-loop-gate",
        "schema_version": "QMX-E5-GATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "cycle_index": cycle_index,
        "path": path,
        "source_path": source["path"],
        "source_hash": source["source_hash"],
        "trigger_fired": trigger.get("trigger_fired"),
        "release_after_seconds": trigger.get("release_after_seconds"),
        "stable_after_release": trigger.get("stable_after_release"),
        "effect": "allow this externally scheduled interpreter cycle after observed network-state release",
        "gate_hash": "",
        "truth_boundary": "The gate is opened by observed network-state release. Interpretation still uses GitHub Actions CPU.",
    }
    return seal(gate, "gate_hash")


def build_signal(
    run_id: str,
    cycle_index: int,
    path: str,
    source: dict[str, Any],
    gate: dict[str, Any],
    trigger: dict[str, Any],
    context: dict[str, Any],
    interpretation: dict[str, Any] | None,
) -> dict[str, Any]:
    index = context.get("index") if context.get("ok") else {}
    graph_validation = context.get("graph_validation") if context.get("ok") else {}
    steps = (interpretation or {}).get("steps") or []
    step_summaries = [
        {
            "step_index": step.get("step_index"),
            "role": step.get("role"),
            "ok": step.get("ok"),
            "action": step.get("action"),
            "signals_out": step.get("signals_out") or [],
            "signal_hash": step.get("signal_hash"),
        }
        for step in steps
    ]
    signal = {
        "stage": "E5-external-scheduled-triggered-interpreter-loop-signal",
        "schema_version": "QMX-E5-SIGNAL-0.1",
        "created_at": now(),
        "run_id": run_id,
        "cycle_index": cycle_index,
        "path": path,
        "source_path": source["path"],
        "source_hash": source["source_hash"],
        "gate_path": gate["path"],
        "gate_hash": gate["gate_hash"],
        "trigger_fired": bool(trigger.get("trigger_fired")),
        "release_after_seconds": trigger.get("release_after_seconds"),
        "interpreter_step_executed": bool(trigger.get("trigger_fired") and context.get("ok") and (interpretation or {}).get("ok")),
        "interpreter_action": "external_controlled_declarative_multi_capsule_interpretation",
        "network_id": index.get("network_id"),
        "network_hash": index.get("network_hash"),
        "index_path": INDEX_PATH,
        "graph_validation_ok": bool((graph_validation or {}).get("ok")),
        "route": (interpretation or {}).get("route") or [],
        "step_count": len(steps),
        "steps": step_summaries,
        "final_signals": (interpretation or {}).get("final_signals") or [],
        "network_language_pulse": bool((interpretation or {}).get("network_language_pulse")),
        "context_error": context.get("error"),
        "signal_hash": "",
        "truth_boundary": (
            "E5 signal proves the external runner ran one controlled interpreter step after a network-state trigger. "
            "It is not autonomous network self-execution."
        ),
    }
    return seal(signal, "signal_hash")


def build_cycle_record(
    run_id: str,
    cycle_index: int,
    path: str,
    source: dict[str, Any],
    gate: dict[str, Any],
    signal: dict[str, Any],
    trigger: dict[str, Any],
    writes: dict[str, Any],
) -> dict[str, Any]:
    record = {
        "stage": "E5-external-scheduled-triggered-interpreter-loop-cycle",
        "schema_version": "QMX-E5-CYCLE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "cycle_index": cycle_index,
        "path": path,
        "source_hash": source["source_hash"],
        "gate_hash": gate["gate_hash"],
        "signal_hash": signal["signal_hash"],
        "trigger_fired": trigger.get("trigger_fired"),
        "release_after_seconds": trigger.get("release_after_seconds"),
        "stable_after_release": trigger.get("stable_after_release"),
        "interpreter_step_executed": signal.get("interpreter_step_executed"),
        "network_language_pulse": signal.get("network_language_pulse"),
        "route": signal.get("route"),
        "step_count": signal.get("step_count"),
        "writes": writes,
        "cycle_hash": "",
        "truth_boundary": (
            "This cycle records one externally scheduled, network-state-triggered controlled interpreter loop step. "
            "It does not prove CPU-free execution."
        ),
    }
    return seal(record, "cycle_hash")


def build_loop_state(
    run_id: str,
    mode: str,
    generation: int,
    cycles_requested: int,
    cycle_records: list[dict[str, Any]],
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    release_times = [float(item["release_after_seconds"]) for item in cycle_records if item.get("release_after_seconds") is not None]
    history = list((previous_state or {}).get("history") or [])[-12:]
    if previous_state:
        history.append(
            {
                "run_id": previous_state.get("run_id"),
                "generation": previous_state.get("generation"),
                "state_hash": previous_state.get("state_hash"),
                "cycles_ok": previous_state.get("cycles_ok"),
            }
        )
    all_triggers_fired = bool(cycle_records) and all(item.get("trigger_fired") for item in cycle_records)
    all_interpreter_steps = bool(cycle_records) and all(item.get("interpreter_step_executed") for item in cycle_records)
    all_pulses = bool(cycle_records) and all(item.get("network_language_pulse") for item in cycle_records)
    all_stable = bool(cycle_records) and all(item.get("stable_after_release") for item in cycle_records)
    state = {
        "stage": "E5-external-scheduled-triggered-interpreter-loop-state",
        "schema_version": "QMX-E5-LOOP-STATE-0.1",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "owner": run_owner(mode),
        "path": LOOP_STATE_PATH,
        "cycles_requested": cycles_requested,
        "cycles_completed": len(cycle_records),
        "cycles_ok": len(cycle_records) == cycles_requested and all_triggers_fired and all_interpreter_steps and all_pulses and all_stable,
        "all_triggers_fired": all_triggers_fired,
        "all_interpreter_steps_executed": all_interpreter_steps,
        "all_network_language_pulses": all_pulses,
        "all_stable_after_release": all_stable,
        "release_times_seconds": release_times,
        "release_mean_seconds": round(statistics.mean(release_times), 3) if release_times else None,
        "release_min_seconds": round(min(release_times), 3) if release_times else None,
        "release_max_seconds": round(max(release_times), 3) if release_times else None,
        "source_hashes": [item["source_hash"] for item in cycle_records],
        "gate_hashes": [item["gate_hash"] for item in cycle_records],
        "signal_hashes": [item["signal_hash"] for item in cycle_records],
        "cycle_hashes": [item["cycle_hash"] for item in cycle_records],
        "final_signal_hash": cycle_records[-1]["signal_hash"] if cycle_records else "",
        "final_cycle_hash": cycle_records[-1]["cycle_hash"] if cycle_records else "",
        "previous": {
            "generation": (previous_state or {}).get("generation"),
            "state_hash": (previous_state or {}).get("state_hash"),
        },
        "history": history,
        "state_hash": "",
        "truth_boundary": (
            "E5 proves an external runner can take over the E4-style network-state-triggered interpreter loop. "
            "It still uses GitHub Actions CPU."
        ),
    }
    return seal(state, "state_hash")


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "E5-last-run",
        "schema_version": "QMX-E5-LAST-RUN-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "owner": result["owner"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "cycles_requested": result["cycles_requested"],
        "cycles_completed": result["loop_state"]["cycles_completed"],
        "cycles_ok": result["loop_state"]["cycles_ok"],
        "state_hash": result["loop_state"]["state_hash"],
        "branch_raw_release_ok": result["verification"]["branch_raw_release"].get("ok"),
        "last_run_hash": "",
        "truth_boundary": result["truth_boundary"],
    }
    return seal(last_run, "last_run_hash")


def build_last_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E5-last-report",
        "schema_version": "QMX-E5-REPORT-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "owner": result["owner"],
        "cycles_requested": result["cycles_requested"],
        "cycles_completed": result["loop_state"]["cycles_completed"],
        "cycles_ok": result["loop_state"]["cycles_ok"],
        "release_times_seconds": result["loop_state"]["release_times_seconds"],
        "release_mean_seconds": result["loop_state"]["release_mean_seconds"],
        "state_hash": result["loop_state"]["state_hash"],
        "branch_raw_release_ok": result["verification"]["branch_raw_release"].get("ok"),
        "remote_paths": result["paths"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_e5_external_scheduled_interpreter_loop_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_e5_external_scheduled_interpreter_loop_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E5: external scheduled E4 interpreter loop takeover",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- event_name: `{result['owner'].get('event_name')}`",
        f"- generation: `{result['generation']}`",
        f"- cycles_requested: `{result['cycles_requested']}`",
        f"- cycles_completed: `{result['loop_state']['cycles_completed']}`",
        f"- release_times_seconds: `{result['loop_state']['release_times_seconds']}`",
        f"- state_hash: `{result['loop_state']['state_hash']}`",
        "",
        "## Cycles",
        "",
        "| cycle | trigger | release_seconds | interpreter | pulse | signal_hash |",
        "| ---: | --- | ---: | --- | --- | --- |",
    ]
    for item in result["cycles"]:
        lines.append(
            f"| {item['cycle_index']} | `{item['trigger_fired']}` | `{item['release_after_seconds']}` | "
            f"`{item['interpreter_step_executed']}` | `{item['network_language_pulse']}` | `{item['signal_hash']}` |"
        )
    lines.extend(["", "## Truth Boundary", "", result["truth_boundary"], ""])
    (run_dir / "nsl_e5_external_scheduled_interpreter_loop_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E5 external scheduled takeover of the E4 interpreter loop")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--global-lock-ttl-seconds", type=int, default=2700)
    parser.add_argument("--trigger-timeout", type=int, default=150)
    parser.add_argument("--trigger-interval", type=float, default=4.0)
    parser.add_argument("--raw-timeout", type=int, default=240)
    parser.add_argument("--raw-interval", type=float, default=8.0)
    args = parser.parse_args()
    if args.cycles < 1:
        raise ValueError("E5 requires at least 1 cycle")

    event = __import__("os").environ.get("GITHUB_EVENT_NAME") or "local"
    run_number = __import__("os").environ.get("GITHUB_RUN_ID")
    attempt = __import__("os").environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        run_id = f"nsl-e5-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-e5-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()

    global_lock = acquire_global_lock(args.owner, args.repo, token, run_id, args.mode, args.global_lock_ttl_seconds)
    if global_lock.get("skipped"):
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "E5-external-scheduled-triggered-interpreter-loop",
            "ok": True,
            "skipped": True,
            "reason": "active_global_lock",
            "owner": run_owner(args.mode),
            "generation": 0,
            "cycles_requested": args.cycles,
            "cycles": [],
            "loop_state": {"cycles_completed": 0, "cycles_ok": False, "release_times_seconds": [], "state_hash": ""},
            "evidence_level": "E5-external-scheduled-interpreter-loop-skipped",
            "truth_boundary": "E5 skipped because another controlled runtime window is active.",
        }
        write_local_outputs(run_dir, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0

    global_release: dict[str, Any] = {}
    try:
        previous_state, _, _ = content_get(args.owner, args.repo, LOOP_STATE_PATH, token)
        e4_loop_state, _, _ = content_get(args.owner, args.repo, E4_LOOP_STATE_PATH, token)
        l12_last_run, _, _ = content_get(args.owner, args.repo, L12_LAST_RUN_PATH, token)
        generation = int((previous_state or {}).get("generation") or 0) + 1
        previous_source_hash = str(((previous_state or {}).get("source_hashes") or [""])[-1] or "")
        previous_signal_hash = str(((previous_state or {}).get("signal_hashes") or [""])[-1] or "")

        cycle_records: list[dict[str, Any]] = []
        expected_release: list[dict[str, str]] = []
        for cycle_index in range(1, args.cycles + 1):
            spath = source_path(run_id, cycle_index)
            gpath = gate_path(run_id, cycle_index)
            sigpath = signal_path(run_id, cycle_index)
            cpath = cycle_path(run_id, cycle_index)

            source = build_cycle_source(
                run_id,
                generation,
                cycle_index,
                spath,
                previous_source_hash,
                previous_signal_hash,
                e4_loop_state,
                l12_last_run,
                args.mode,
            )
            source_write = put_and_verify(args.owner, args.repo, token, spath, source, "source_hash", f"E5 cycle {cycle_index} source {run_id}")
            trigger = observe_network_trigger(
                args.owner,
                args.repo,
                spath,
                source["source_hash"],
                previous_source_hash,
                cycle_index,
                args.trigger_timeout,
                args.trigger_interval,
            )
            gate = build_gate(run_id, cycle_index, gpath, source, trigger)
            gate_write = put_and_verify(args.owner, args.repo, token, gpath, gate, "gate_hash", f"E5 cycle {cycle_index} gate {run_id}")

            context: dict[str, Any] = {"ok": False, "error": "trigger_not_fired"}
            interpretation: dict[str, Any] | None = None
            if trigger.get("trigger_fired"):
                context = load_interpreter_context(args.owner, args.repo)
                if context.get("ok"):
                    interpretation = interpret_graph(f"{run_id}-cycle-{cycle_index:03d}", context["index"], context["capsules"], context["graph_validation"])
            signal = build_signal(run_id, cycle_index, sigpath, source, gate, trigger, context, interpretation)
            signal_write = put_and_verify(args.owner, args.repo, token, sigpath, signal, "signal_hash", f"E5 cycle {cycle_index} signal {run_id}")
            writes = {"source": source_write, "gate": gate_write, "signal": signal_write}
            cycle_record = build_cycle_record(run_id, cycle_index, cpath, source, gate, signal, trigger, writes)
            cycle_write = put_and_verify(args.owner, args.repo, token, cpath, cycle_record, "cycle_hash", f"E5 cycle {cycle_index} record {run_id}")
            cycle_record["writes"]["cycle"] = cycle_write
            cycle_records.append(cycle_record)
            expected_release.extend(
                [
                    {"path": spath, "hash_field": "source_hash", "hash_value": source["source_hash"]},
                    {"path": gpath, "hash_field": "gate_hash", "hash_value": gate["gate_hash"]},
                    {"path": sigpath, "hash_field": "signal_hash", "hash_value": signal["signal_hash"]},
                    {"path": cpath, "hash_field": "cycle_hash", "hash_value": cycle_record["cycle_hash"]},
                ]
            )
            previous_source_hash = source["source_hash"]
            previous_signal_hash = signal["signal_hash"]
            if not trigger.get("trigger_fired") or not signal.get("interpreter_step_executed"):
                break

        loop_state = build_loop_state(run_id, args.mode, generation, args.cycles, cycle_records, previous_state)
        loop_write = put_and_verify(args.owner, args.repo, token, LOOP_STATE_PATH, loop_state, "state_hash", f"E5 loop state {run_id}")
        expected_release.append({"path": LOOP_STATE_PATH, "hash_field": "state_hash", "hash_value": loop_state["state_hash"]})
        branch_release = wait_for_branch_release(args.owner, args.repo, expected_release, args.raw_timeout, args.raw_interval)
        cycle_writes_ok = all(
            all((record.get("writes") or {}).get(kind, {}).get("ok") and (record.get("writes") or {}).get(kind, {}).get("commit_raw_ok") for kind in ["source", "gate", "signal", "cycle"])
            for record in cycle_records
        )
        core_ok = bool(loop_state["cycles_ok"] and cycle_writes_ok and loop_write.get("ok") and loop_write.get("commit_raw_ok") and branch_release.get("ok"))
        evidence_level = "E5-external-scheduled-network-state-triggered-interpreter-loop-v0" if core_ok else "E5-external-scheduled-network-state-triggered-interpreter-loop-partial"
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "E5-external-scheduled-triggered-interpreter-loop",
            "ok": core_ok,
            "owner": run_owner(args.mode),
            "repo": args.repo,
            "generation": generation,
            "cycles_requested": args.cycles,
            "paths": {
                "workflow": ".github/workflows/nsl-e5-external-scheduled-interpreter-loop.yml",
                "runner": "scripts/nsl_e5_external_scheduled_interpreter_loop.py",
                "source_prefix": SOURCE_PREFIX,
                "gate_prefix": GATE_PREFIX,
                "signal_prefix": SIGNAL_PREFIX,
                "cycle_prefix": CYCLE_PREFIX,
                "loop_state": LOOP_STATE_PATH,
                "last_run": LAST_RUN_PATH,
                "last_report": LAST_REPORT_PATH,
            },
            "source_e4": {"path": E4_LOOP_STATE_PATH, "state_hash": (e4_loop_state or {}).get("state_hash")},
            "source_l12_2": {"path": L12_LAST_RUN_PATH, "state_hash": (l12_last_run or {}).get("state_hash")},
            "cycles": cycle_records,
            "loop_state": loop_state,
            "writes": {"global_lock_acquire": global_lock.get("write"), "loop_state": loop_write},
            "verification": {
                "cycles_completed": len(cycle_records),
                "cycles_ok": loop_state["cycles_ok"],
                "cycle_writes_ok": cycle_writes_ok,
                "loop_state_write_ok": loop_write.get("ok"),
                "loop_state_commit_raw_ok": loop_write.get("commit_raw_ok"),
                "branch_raw_release": branch_release,
            },
            "evidence_level": evidence_level,
            "conclusion": (
                "E5 proved that an external GitHub Actions runner can take over the E4-style network-state-triggered interpreter loop, "
                "run the multi-capsule interpreter across controlled cycles, emit NETWORK_LANGUAGE_PULSE, and write state back to the network receiver."
                if core_ok
                else "E5 partially ran, but one or more trigger releases, interpreter cycles, writebacks, or Raw release checks did not fully pass."
            ),
            "truth_boundary": (
                "E5 proves external scheduled takeover under GitHub Actions CPU. "
                "It does not prove the network executes the interpreter loop by itself, CPU-free computation, autonomous cognition, digital life, or digital supercomputing."
            ),
        }
        last_run = build_last_run(result)
        last_run_write = put_and_verify(args.owner, args.repo, token, LAST_RUN_PATH, last_run, "last_run_hash", f"E5 last run {run_id}")
        last_report = build_last_report(result)
        last_report_write = put_and_verify(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, "report_hash", f"E5 last report {run_id}")
        global_release = release_global_lock(args.owner, args.repo, token, run_id, result["ok"])
        result["writes"]["last_run"] = last_run_write
        result["writes"]["last_report"] = last_report_write
        result["writes"]["global_lock_release"] = global_release
        result["ok"] = bool(core_ok and last_run_write.get("ok") and last_run_write.get("commit_raw_ok") and last_report_write.get("ok") and last_report_write.get("commit_raw_ok") and global_release.get("ok"))
        result["evidence_level"] = "E5-external-scheduled-network-state-triggered-interpreter-loop-v0" if result["ok"] else "E5-external-scheduled-network-state-triggered-interpreter-loop-partial"
        write_local_outputs(run_dir, result)
        print(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "ok": result["ok"],
                    "event_name": result["owner"].get("event_name"),
                    "evidence_level": result["evidence_level"],
                    "generation": result["generation"],
                    "cycles_requested": result["cycles_requested"],
                    "cycles_completed": result["loop_state"]["cycles_completed"],
                    "cycles_ok": result["loop_state"]["cycles_ok"],
                    "release_times_seconds": result["loop_state"]["release_times_seconds"],
                    "state_hash": result["loop_state"]["state_hash"],
                    "branch_raw_release_ok": result["verification"]["branch_raw_release"].get("ok"),
                    "truth_boundary": result["truth_boundary"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 0 if result["ok"] else 1
    except Exception:
        global_release = release_global_lock(args.owner, args.repo, token, run_id, False)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
