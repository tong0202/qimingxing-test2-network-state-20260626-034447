from __future__ import annotations

import argparse
import json
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
    stable_hash,
    wait_for_branch_release,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

BUS_STATE_PATH = "states/e6-lowfreq-vitals-bus-state.json"
LAST_RUN_PATH = "states/e6-last-run.json"
LAST_REPORT_PATH = "states/e6-last-report.json"
SNAPSHOT_PREFIX = "states/e6-vitals-bus-snapshots"

SOURCE_SPECS: list[dict[str, Any]] = [
    {
        "id": "e4_loop_state",
        "path": "states/e4-triggered-interpreter-loop-state.json",
        "hash_field": "state_hash",
        "required": True,
    },
    {
        "id": "e5_loop_state",
        "path": "states/e5-external-triggered-interpreter-loop-state.json",
        "hash_field": "state_hash",
        "required": True,
    },
    {
        "id": "e5_last_run",
        "path": "states/e5-last-run.json",
        "hash_field": "last_run_hash",
        "required": True,
    },
    {
        "id": "e5_last_report",
        "path": "states/e5-last-report.json",
        "hash_field": "report_hash",
        "required": True,
    },
    {
        "id": "l12_last_run",
        "path": "states/nsl-l12-last-run.json",
        "hash_field": "last_run_hash",
        "required": True,
    },
    {
        "id": "l12_state",
        "path": "states/nsl-l12-hourly-self-maintenance-state.json",
        "hash_field": "state_hash",
        "required": False,
    },
    {
        "id": "global_runtime_lock",
        "path": "states/qmx-global-runtime-lock.json",
        "hash_field": "lock_hash",
        "required": True,
    },
    {
        "id": "l11_5_logic_spec",
        "path": "states/nsl-l11-5-minimal-logic-spec.json",
        "hash_field": "logic_hash",
        "required": True,
    },
]


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def path_snapshot(run_id: str) -> str:
    return f"{SNAPSHOT_PREFIX}/{run_id}.json"


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
    if source_id == "e4_loop_state":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "cycles_completed": payload.get("cycles_completed"),
            "cycles_ok": payload.get("cycles_ok"),
            "all_network_language_pulses": payload.get("all_network_language_pulses"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id == "e5_loop_state":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "event_name": ((payload.get("owner") or {}).get("event_name")),
            "cycles_completed": payload.get("cycles_completed"),
            "cycles_ok": payload.get("cycles_ok"),
            "all_network_language_pulses": payload.get("all_network_language_pulses"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id in {"e5_last_run", "e5_last_report"}:
        return {
            "run_id": payload.get("run_id"),
            "ok": payload.get("ok"),
            "event_name": ((payload.get("owner") or {}).get("event_name")),
            "cycles_completed": payload.get("cycles_completed"),
            "cycles_ok": payload.get("cycles_ok"),
            "evidence_level": payload.get("evidence_level"),
        }
    if source_id == "l12_last_run":
        return {
            "run_id": payload.get("run_id"),
            "event_name": payload.get("event_name") or ((payload.get("owner") or {}).get("event_name")),
            "window_ok": payload.get("window_ok"),
            "slot_id": payload.get("slot_id"),
            "last_run_hash": payload.get("last_run_hash"),
        }
    if source_id == "l12_state":
        return {
            "run_id": payload.get("run_id"),
            "generation": payload.get("generation"),
            "window_ok": payload.get("window_ok"),
            "state_hash": payload.get("state_hash"),
        }
    if source_id == "global_runtime_lock":
        return {
            "locked": payload.get("locked"),
            "checkpoint": payload.get("checkpoint"),
            "runtime_owner": payload.get("runtime_owner"),
            "run_id": payload.get("run_id"),
            "release_ok": payload.get("release_ok"),
            "lock_hash": payload.get("lock_hash"),
        }
    if source_id == "l11_5_logic_spec":
        return {
            "logic_hash": payload.get("logic_hash"),
            "minimum_logic_ready": payload.get("minimum_logic_ready"),
            "minimum_logic_sentence": payload.get("minimum_logic_sentence"),
        }
    return {"keys": sorted(payload.keys())[:16]}


def sample_source(owner: str, repo: str, spec: dict[str, Any]) -> dict[str, Any]:
    sample = fetch_json_url(raw_url(owner, repo, "main", spec["path"]), f"e6-{spec['id']}")
    payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else None
    return {
        "id": spec["id"],
        "path": spec["path"],
        "required": bool(spec.get("required")),
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


def derive_vitals(samples: list[dict[str, Any]]) -> dict[str, Any]:
    required = [item for item in samples if item.get("required")]
    required_reads_ok = all(item.get("read_ok") for item in required)
    required_hashes_ok = all((item.get("hash_verify") or {}).get("ok") for item in required)

    e4 = source_by_id(samples, "e4_loop_state").get("payload") or {}
    e5_loop = source_by_id(samples, "e5_loop_state").get("payload") or {}
    e5_last = source_by_id(samples, "e5_last_run").get("payload") or {}
    e5_owner = e5_last.get("owner") or {}
    l12_last = source_by_id(samples, "l12_last_run").get("payload") or {}
    lock = source_by_id(samples, "global_runtime_lock").get("payload") or {}
    logic = source_by_id(samples, "l11_5_logic_spec").get("payload") or {}

    e4_loop_ok = bool(e4.get("cycles_ok") and e4.get("all_network_language_pulses"))
    e5_loop_ok = bool(e5_loop.get("cycles_ok") and e5_loop.get("all_network_language_pulses"))
    e5_last_ok = bool(e5_last.get("ok") and e5_last.get("cycles_ok") and int(e5_last.get("cycles_completed") or 0) >= 3)
    e5_schedule_observed = bool(e5_owner.get("event_name") == "schedule")
    l12_window_ok = bool(l12_last.get("window_ok") or l12_last.get("ok"))
    global_lock_released = bool(lock and lock.get("locked") is False and lock.get("release_ok") is True)
    logic_ready = bool(logic and (logic.get("minimum_logic_ready") is not False))

    bus_ok = bool(
        required_reads_ok
        and required_hashes_ok
        and e4_loop_ok
        and e5_loop_ok
        and e5_last_ok
        and l12_window_ok
        and global_lock_released
        and logic_ready
    )
    return {
        "required_reads_ok": required_reads_ok,
        "required_hashes_ok": required_hashes_ok,
        "e4_loop_ok": e4_loop_ok,
        "e5_loop_ok": e5_loop_ok,
        "e5_last_run_ok": e5_last_ok,
        "e5_schedule_observed": e5_schedule_observed,
        "l12_window_ok": l12_window_ok,
        "global_lock_released": global_lock_released,
        "logic_ready": logic_ready,
        "bus_ok": bus_ok,
        "signals": {
            "LOWFREQ_VITALS_BUS_READY": bus_ok,
            "E4_INTERPRETER_LOOP_HEALTHY": e4_loop_ok,
            "E5_EXTERNAL_TAKEOVER_HEALTHY": bool(e5_loop_ok and e5_last_ok),
            "E5_NATURAL_SCHEDULE_OBSERVED": e5_schedule_observed,
            "L12_SELF_MAINTENANCE_HEALTHY": l12_window_ok,
            "GLOBAL_RUNTIME_LOCK_RELEASED": global_lock_released,
        },
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
            sample = fetch_json_url(raw_url(owner, repo, commit_hash, path), f"e6-commit-{path}-{attempt}")
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


def build_bus_state(
    run_id: str,
    mode: str,
    generation: int,
    samples: list[dict[str, Any]],
    vitals: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    state = {
        "stage": "E6-lowfreq-vitals-bus-state",
        "schema_version": "QMX-E6-VITALS-BUS-0.1",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "owner": run_owner(mode),
        "source_count": len(samples),
        "sources": [
            {
                "id": item["id"],
                "path": item["path"],
                "required": item["required"],
                "read_ok": item["read_ok"],
                "status": item["status"],
                "elapsed_ms": item["elapsed_ms"],
                "hash_verify": item["hash_verify"],
                "truth_boundary_present": item["truth_boundary_present"],
                "summary": item["summary"],
                "error": item["error"],
            }
            for item in samples
        ],
        "vitals": vitals,
        "previous": {
            "generation": (previous or {}).get("generation"),
            "state_hash": (previous or {}).get("state_hash"),
            "run_id": (previous or {}).get("run_id"),
        },
        "conclusion": (
            "E6 provides a low-frequency external vitals bus: it aggregates E4/E5/L12/global-lock/logic evidence into one auditable remote state."
        ),
        "truth_boundary": (
            "E6 is a monitoring and coordination bus executed by local or GitHub Actions CPU. "
            "It does not prove CPU-free network execution, autonomous digital life, or a self-executing network computer."
        ),
        "state_hash": "",
    }
    return seal(state, "state_hash")


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "E6-last-run",
        "schema_version": "QMX-E6-LAST-RUN-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "owner": result["owner"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "generation": result["generation"],
        "vitals": result["vitals"],
        "state_hash": result["bus_state"]["state_hash"],
        "last_run_hash": "",
        "truth_boundary": result["truth_boundary"],
    }
    return seal(last_run, "last_run_hash")


def build_last_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "E6-last-report",
        "schema_version": "QMX-E6-REPORT-0.1",
        "created_at": result["created_at"],
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "generation": result["generation"],
        "source_count": len(result["samples"]),
        "vitals": result["vitals"],
        "remote_paths": result["paths"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def write_local_outputs(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "nsl_e6_lowfreq_vitals_bus_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUNS / "latest_nsl_e6_lowfreq_vitals_bus_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# E6 Low-Frequency Vitals Bus",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- state_hash: `{result['bus_state']['state_hash']}`",
        "",
        "## Vitals",
        "",
    ]
    for key, value in result["vitals"].items():
        if key != "signals":
            lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Truth Boundary", "", result["truth_boundary"], ""])
    (run_dir / "nsl_e6_lowfreq_vitals_bus_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E6 low-frequency external vitals bus")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--global-lock-ttl-seconds", type=int, default=900)
    parser.add_argument("--raw-timeout", type=int, default=180)
    parser.add_argument("--raw-interval", type=float, default=6.0)
    args = parser.parse_args()

    event = __import__("os").environ.get("GITHUB_EVENT_NAME") or "local"
    run_number = __import__("os").environ.get("GITHUB_RUN_ID")
    attempt = __import__("os").environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        run_id = f"nsl-e6-{event}-{run_number}-attempt-{attempt}"
    else:
        run_id = "nsl-e6-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    token = gh_token()

    global_release: dict[str, Any] = {}
    try:
        previous_state, _, _ = content_get(args.owner, args.repo, BUS_STATE_PATH, token)
        generation = int((previous_state or {}).get("generation") or 0) + 1
        samples = [sample_source(args.owner, args.repo, spec) for spec in SOURCE_SPECS]
        vitals = derive_vitals(samples)
        global_lock = acquire_global_lock(args.owner, args.repo, token, run_id, args.mode, args.global_lock_ttl_seconds)
        if global_lock.get("skipped"):
            result = {
                "run_id": run_id,
                "created_at": now(),
                "stage": "E6-lowfreq-vitals-bus",
                "ok": True,
                "skipped": True,
                "reason": "active_global_lock",
                "owner": run_owner(args.mode),
                "evidence_level": "E6-lowfreq-vitals-bus-skipped",
                "truth_boundary": "E6 skipped because another controlled runtime window is active.",
            }
            write_local_outputs(run_dir, {**result, "vitals": vitals, "bus_state": {"state_hash": ""}})
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0
        bus_state = build_bus_state(run_id, args.mode, generation, samples, vitals, previous_state)
        snapshot_path = path_snapshot(run_id)

        state_write = put_and_verify(args.owner, args.repo, token, BUS_STATE_PATH, bus_state, "state_hash", f"E6 bus state {run_id}")
        snapshot_write = put_and_verify(args.owner, args.repo, token, snapshot_path, bus_state, "state_hash", f"E6 bus snapshot {run_id}")
        expected_release = [
            {"path": BUS_STATE_PATH, "hash_field": "state_hash", "hash_value": bus_state["state_hash"]},
            {"path": snapshot_path, "hash_field": "state_hash", "hash_value": bus_state["state_hash"]},
        ]
        branch_release = wait_for_branch_release(args.owner, args.repo, expected_release, args.raw_timeout, args.raw_interval)
        core_ok = bool(vitals["bus_ok"] and state_write.get("ok") and state_write.get("commit_raw_ok") and snapshot_write.get("ok") and snapshot_write.get("commit_raw_ok") and branch_release.get("ok"))
        result: dict[str, Any] = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "E6-lowfreq-vitals-bus",
            "ok": core_ok,
            "owner": run_owner(args.mode),
            "repo": args.repo,
            "generation": generation,
            "samples": samples,
            "vitals": vitals,
            "bus_state": bus_state,
            "paths": {
                "workflow": ".github/workflows/nsl-e6-lowfreq-vitals-bus.yml",
                "runner": "scripts/nsl_e6_lowfreq_vitals_bus.py",
                "bus_state": BUS_STATE_PATH,
                "snapshot": snapshot_path,
                "last_run": LAST_RUN_PATH,
                "last_report": LAST_REPORT_PATH,
            },
            "writes": {
                "global_lock_acquire": global_lock.get("write"),
                "bus_state": state_write,
                "snapshot": snapshot_write,
            },
            "verification": {
                "branch_raw_release": branch_release,
                "state_write_ok": state_write.get("ok"),
                "state_commit_raw_ok": state_write.get("commit_raw_ok"),
                "snapshot_write_ok": snapshot_write.get("ok"),
                "snapshot_commit_raw_ok": snapshot_write.get("commit_raw_ok"),
            },
            "evidence_level": "E6-lowfreq-vitals-bus-v0" if core_ok else "E6-lowfreq-vitals-bus-partial",
            "conclusion": (
                "E6 proved a low-frequency external vitals bus can aggregate E4/E5/L12/global-lock/logic evidence and write one auditable state back to the remote receiver."
                if core_ok
                else "E6 ran, but one or more source reads, hash checks, vitals checks, writebacks, or Raw release checks did not pass."
            ),
            "truth_boundary": (
                "E6 is a monitoring and coordination bus executed by local or GitHub Actions CPU. "
                "It does not prove CPU-free network execution, autonomous digital life, or a self-executing network computer."
            ),
        }
        last_run = build_last_run(result)
        last_run_write = put_and_verify(args.owner, args.repo, token, LAST_RUN_PATH, last_run, "last_run_hash", f"E6 last run {run_id}")
        last_report = build_last_report(result)
        last_report_write = put_and_verify(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, "report_hash", f"E6 last report {run_id}")
        global_release = release_global_lock(args.owner, args.repo, token, run_id, result["ok"])
        result["writes"]["last_run"] = last_run_write
        result["writes"]["last_report"] = last_report_write
        result["writes"]["global_lock_release"] = global_release
        result["ok"] = bool(core_ok and last_run_write.get("ok") and last_run_write.get("commit_raw_ok") and last_report_write.get("ok") and last_report_write.get("commit_raw_ok") and global_release.get("ok"))
        result["evidence_level"] = "E6-lowfreq-vitals-bus-v0" if result["ok"] else "E6-lowfreq-vitals-bus-partial"
        write_local_outputs(run_dir, result)
        print(
            json.dumps(
                {
                    "run_id": result["run_id"],
                    "ok": result["ok"],
                    "event_name": result["owner"].get("event_name"),
                    "evidence_level": result["evidence_level"],
                    "generation": result["generation"],
                    "vitals": result["vitals"],
                    "state_hash": result["bus_state"]["state_hash"],
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
