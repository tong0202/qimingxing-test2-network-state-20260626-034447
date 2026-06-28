from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_f0_capsule_quorum_rebuild import core_hash
from nsl_f1_capsule_lifecycle import put_json, seal, wait_for_hash
from nsl_f2_lifecycle_self_scheduler import (
    DEFAULT_OWNER,
    DEFAULT_REPO,
    F1_STATE_PATH,
    LEDGER_PATH as F2_LEDGER_PATH,
    STATE_PATH as F2_STATE_PATH,
    append_decision,
    append_ledger as append_f2_ledger,
    build_scheduler_capsule,
    build_state as build_f2_state,
    execute_action,
    normalize_previous_state,
    read_json_content,
)
from nsl_l12_hourly_self_maintenance import (
    content_get,
    fetch_json_url,
    gh_token,
    now,
    raw_url,
    run_owner,
    stable_hash,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

F3_CAPSULE_PATH = "states/f3-loop-capsule.json"
F3_STATE_PATH = "states/f3-loop-state.json"
F3_LEDGER_PATH = "states/f3-loop-ledger.json"
F3_LAST_RUN_PATH = "states/f3-last-run.json"
F3_LAST_REPORT_PATH = "states/f3-last-report.json"

ALLOWED_F3_ACTIONS = {"split", "decay", "retire", "peer_check", "observe"}


def run_id_for(mode: str) -> str:
    event = os.environ.get("GITHUB_EVENT_NAME") or mode
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        return f"nsl-f3-{event}-{run_number}-attempt-{attempt}"
    return "nsl-f3-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def build_loop_capsule(run_id: str, source_f1_state_hash: str) -> dict[str, Any]:
    core = {
        "role": "low_frequency_lifecycle_loop",
        "kind": "mainline_scheduler_loop",
        "capsule_id": "f3cap-lowfreq-self-scheduler-loop",
        "path": F3_CAPSULE_PATH,
        "source_f1_state_hash": source_f1_state_hash,
        "mainline": "F-series capsule lifecycle and self-scheduling",
        "auxiliary_layers": {
            "L": "network state language, controlled interpreter, low-frequency maintenance base",
            "E": "external wake, post-wake check, ledger and status evidence",
        },
        "rule": "Each low-frequency wake window executes one low-risk lifecycle scheduler step, then persists state for the next wake.",
        "allowed_actions": sorted(ALLOWED_F3_ACTIONS),
        "direct_body_execution": False,
        "arbitrary_code_execution": False,
    }
    capsule = {
        "stage": "F3-lowfreq-self-scheduler-loop",
        "schema_version": "QMX-F3-LOOP-CAPSULE-0.1",
        "created_by_run_id": run_id,
        "created_at": now(),
        "updated_at": now(),
        "role": "low_frequency_lifecycle_loop",
        "path": F3_CAPSULE_PATH,
        "core": core,
        "core_hash": core_hash(core),
        "safety": {
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
            "allowed_write_prefixes": ["states/f2-", "states/f3-"],
            "allowed_actions": sorted(ALLOWED_F3_ACTIONS),
        },
        "truth_boundary": "F3 coordinates low-risk scheduler windows over remote anchors; it is not endpoint-free or CPU-free execution.",
        "capsule_hash": "",
    }
    return seal(capsule, "capsule_hash")


def active_child(scheduler_state: dict[str, Any]) -> dict[str, Any]:
    child = scheduler_state.get("child") if isinstance(scheduler_state.get("child"), dict) else {}
    return {
        "exists": bool(child.get("exists")),
        "state": str(child.get("state") or "missing"),
        "retired": bool(child.get("retired", True)),
        "vitality": int(child.get("vitality") or 0),
        "capsule_hash": str(child.get("capsule_hash") or ""),
    }


def scheduler_state_from_sources(
    previous_f3_state: dict[str, Any] | None,
    previous_f2_state: dict[str, Any] | None,
    run_id: str,
    f1_state: dict[str, Any],
) -> tuple[dict[str, Any], int, int, str]:
    if isinstance(previous_f3_state, dict) and isinstance(previous_f3_state.get("scheduler_state"), dict):
        state = json.loads(json.dumps(previous_f3_state["scheduler_state"], ensure_ascii=False))
        state["scheduler_generation"] = int(state.get("scheduler_generation") or 1) + 1
        state["source_f1_state_hash"] = f1_state.get("state_hash")
        state["source_f1_event_order"] = f1_state.get("event_order") or []
        return (
            state,
            int(previous_f3_state.get("window_count") or 0),
            int(previous_f3_state.get("lifecycle_cycle_count") or 0),
            str(previous_f3_state.get("state_hash") or ""),
        )

    if isinstance(previous_f2_state, dict):
        state = normalize_previous_state(previous_f2_state, run_id, f1_state)
        state["last_peer_check_hash"] = ""
        return state, 0, 0, str(previous_f2_state.get("state_hash") or "")

    state = normalize_previous_state(None, run_id, f1_state)
    return state, 0, 0, ""


def score_f3_candidates(
    scheduler_state: dict[str, Any],
    f1_state: dict[str, Any],
    lifecycle_cycle_count: int,
) -> list[dict[str, Any]]:
    child = active_child(scheduler_state)
    f1_hash = str(f1_state.get("state_hash") or "")
    last_peer_hash = str(scheduler_state.get("last_peer_check_hash") or "")
    candidates: list[dict[str, Any]] = []

    def add(action: str, score: int, reason: str) -> None:
        candidates.append({"action": action, "score": score, "reason": reason, "allowed": action in ALLOWED_F3_ACTIONS})

    child_active = child["exists"] and not child["retired"]
    if child_active and child["vitality"] > 35:
        add("decay", 90, "active scheduler child vitality is above decay threshold")
    if child_active and child["vitality"] <= 35:
        add("retire", 92, "active scheduler child vitality reached retirement threshold")
    if (not child_active) and lifecycle_cycle_count > 0 and last_peer_hash != f1_hash:
        add("peer_check", 96, "a lifecycle cycle ended and source F1 state has not been checked in F3")
    if (not child_active) and not (lifecycle_cycle_count > 0 and last_peer_hash != f1_hash):
        add("split", 95, "no active scheduler child exists; begin next low-risk lifecycle cycle")
    if last_peer_hash != f1_hash:
        add("peer_check", 80, "source F1 state hash has not been peer-checked by F3")
    add("observe", 10, "fallback observation if no stronger lifecycle event applies")
    return sorted(candidates, key=lambda item: (-int(item["score"]), str(item["action"])))


def append_f3_ledger(
    owner: str,
    repo: str,
    token: str,
    run_id: str,
    mode: str,
    entry: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, _, _ = content_get(owner, repo, F3_LEDGER_PATH, token)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    sealed_entry = seal(entry, "entry_hash")
    entries = [item for item in entries if isinstance(item, dict) and item.get("run_id") != run_id]
    entries.append(sealed_entry)
    entries = entries[-200:]
    ledger = {
        "stage": "F3-lowfreq-self-scheduler-loop-ledger",
        "schema_version": "QMX-F3-LEDGER-0.1",
        "updated_at": now(),
        "owner": run_owner(mode),
        "entry_count": len(entries),
        "latest_run_id": run_id,
        "entries": entries,
        "truth_boundary": "F3 ledger is mutable remote state, not tamper-proof storage.",
        "ledger_hash": "",
    }
    ledger = seal(ledger, "ledger_hash")
    write = put_json(owner, repo, token, F3_LEDGER_PATH, ledger, f"F3 loop ledger {run_id}")
    return ledger, write


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "stage": "F3-last-run",
        "schema_version": "QMX-F3-LAST-RUN-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "selected_actions": result["selected_actions"],
        "window_count": result["window_count"],
        "lifecycle_cycle_count": result["lifecycle_cycle_count"],
        "f3_state_hash": result["f3_state"]["state_hash"],
        "f3_ledger_hash": result["f3_ledger"]["ledger_hash"],
        "f2_state_hash": result["f2_state"]["state_hash"],
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(payload, "last_run_hash")


def build_last_report(result: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "stage": "F3-last-report",
        "schema_version": "QMX-F3-REPORT-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "selected_actions": result["selected_actions"],
        "window_count": result["window_count"],
        "lifecycle_cycle_count": result["lifecycle_cycle_count"],
        "f3_state_hash": result["f3_state"]["state_hash"],
        "f3_ledger_hash": result["f3_ledger"]["ledger_hash"],
        "f2_state_hash": result["f2_state"]["state_hash"],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(payload, "report_hash")


def write_local(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "nsl_f3_lowfreq_self_scheduler_loop_result.json"
    report_path = run_dir / "nsl_f3_lowfreq_self_scheduler_loop_report.md"
    latest_path = RUNS / "latest_nsl_f3_lowfreq_self_scheduler_loop_result.json"
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    result_path.write_text(text, encoding="utf-8")
    latest_path.write_text(text, encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# F3 low-frequency self-scheduler loop report",
                "",
                f"run_id: `{result.get('run_id')}`",
                f"ok: `{result.get('ok')}`",
                f"selected_actions: `{','.join(result.get('selected_actions') or [])}`",
                f"window_count: `{result.get('window_count')}`",
                f"f3_state_hash: `{result.get('f3_state', {}).get('state_hash')}`",
                "",
                "Truth boundary:",
                "",
                "```text",
                str(result.get("truth_boundary") or ""),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="F3 low-frequency multi-run lifecycle self-scheduler loop")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--windows", type=int, default=1)
    parser.add_argument("--raw-check", action="store_true")
    args = parser.parse_args()

    token = gh_token()
    run_id = run_id_for(args.mode)
    run_dir = RUNS / run_id

    f1_state, f1_response = read_json_content(args.owner, args.repo, token, F1_STATE_PATH)
    if not isinstance(f1_state, dict):
        result = {
            "run_id": run_id,
            "created_at": now(),
            "stage": "F3-lowfreq-self-scheduler-loop",
            "ok": False,
            "error": "missing_f1_lifecycle_state",
            "f1_state_status": f1_response.get("status"),
            "truth_boundary": "F3 cannot schedule without F1 lifecycle state.",
        }
        write_local(run_dir, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 1

    previous_f3_state, _, _ = content_get(args.owner, args.repo, F3_STATE_PATH, token)
    previous_f2_state, _, _ = content_get(args.owner, args.repo, F2_STATE_PATH, token)
    scheduler_state, previous_window_count, lifecycle_cycle_count, previous_state_hash = scheduler_state_from_sources(
        previous_f3_state if isinstance(previous_f3_state, dict) else None,
        previous_f2_state if isinstance(previous_f2_state, dict) else None,
        run_id,
        f1_state,
    )

    f1_state_hash_ok = bool(f1_state.get("state_hash") and f1_state.get("state_hash") == stable_hash(f1_state, "state_hash"))
    f2_scheduler_capsule = build_scheduler_capsule(run_id, str(f1_state.get("state_hash") or ""))
    f2_capsule_write = put_json(args.owner, args.repo, token, "states/f2-scheduler-capsule.json", f2_scheduler_capsule, f"F3 refresh F2 scheduler capsule {run_id}")
    f2_capsule_check = wait_for_hash(args.owner, args.repo, token, "states/f2-scheduler-capsule.json", "capsule_hash", f2_scheduler_capsule["capsule_hash"])

    f3_capsule = build_loop_capsule(run_id, str(f1_state.get("state_hash") or ""))
    f3_capsule_write = put_json(args.owner, args.repo, token, F3_CAPSULE_PATH, f3_capsule, f"F3 loop capsule {run_id}")
    f3_capsule_check = wait_for_hash(args.owner, args.repo, token, F3_CAPSULE_PATH, "capsule_hash", f3_capsule["capsule_hash"])

    decisions: list[dict[str, Any]] = []
    for window_index in range(1, max(1, args.windows) + 1):
        candidates = score_f3_candidates(scheduler_state, f1_state, lifecycle_cycle_count)
        selected = next(item for item in candidates if item.get("allowed"))
        execution = execute_action(args.owner, args.repo, token, run_id, str(selected["action"]), scheduler_state, f1_state)
        decision = append_decision(decisions, window_index, candidates, selected, execution)
        if execution.get("ok") and selected["action"] == "retire":
            lifecycle_cycle_count += 1
        scheduler_state["total_scheduler_ticks"] = int(scheduler_state.get("total_scheduler_ticks") or 0) + 1
        scheduler_state["last_selected_action"] = str(selected["action"])
        decision["window_after"] = {
            "window_count": previous_window_count + window_index,
            "lifecycle_cycle_count": lifecycle_cycle_count,
            "scheduler_child": active_child(scheduler_state),
            "last_peer_check_hash": scheduler_state.get("last_peer_check_hash"),
        }

    selected_actions = [item["selected_action"] for item in decisions]
    all_decisions_ok = all(item.get("execution_ok") for item in decisions)
    f2_state = build_f2_state(run_id, args.mode, f1_state, f2_scheduler_capsule["capsule_hash"], scheduler_state, decisions)
    f2_state_write = put_json(args.owner, args.repo, token, F2_STATE_PATH, f2_state, f"F3 update F2 scheduler state {run_id}")
    f2_state_check = wait_for_hash(args.owner, args.repo, token, F2_STATE_PATH, "state_hash", f2_state["state_hash"])
    f2_entry = {
        "stage": "F3-window-entry-over-f2-scheduler",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "source_f1_state_hash": f1_state.get("state_hash"),
        "selected_actions": selected_actions,
        "decision_hashes": [item["decision_hash"] for item in decisions],
        "decision_count": len(decisions),
        "all_decisions_ok": all_decisions_ok,
        "state_hash": f2_state["state_hash"],
        "entry_hash": "",
    }
    f2_ledger, f2_ledger_write = append_f2_ledger(args.owner, args.repo, token, run_id, args.mode, f2_entry)
    f2_ledger_check = wait_for_hash(args.owner, args.repo, token, F2_LEDGER_PATH, "ledger_hash", f2_ledger["ledger_hash"])

    final_window_count = previous_window_count + len(decisions)
    f3_state = {
        "stage": "F3-lowfreq-self-scheduler-loop-state",
        "schema_version": "QMX-F3-STATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "mainline_contract": {
            "mainline": "F-series capsule lifecycle, self-scheduling, self-repair, and controlled self-regeneration",
            "auxiliary_layers": {
                "L": "base network-state language and controlled interpreter infrastructure",
                "E": "external wake, post-wake health check, ledger, and status infrastructure",
            },
            "rule": "F stages define the current product direction; L and E are supporting infrastructure unless a later F stage explicitly depends on them.",
        },
        "previous_state_hash": previous_state_hash,
        "source_f1_state_hash": f1_state.get("state_hash"),
        "f2_state_hash": f2_state["state_hash"],
        "f2_ledger_hash": f2_ledger["ledger_hash"],
        "f3_capsule_hash": f3_capsule["capsule_hash"],
        "window_count": final_window_count,
        "windows_executed_this_run": len(decisions),
        "lifecycle_cycle_count": lifecycle_cycle_count,
        "selected_actions": selected_actions,
        "decision_count": len(decisions),
        "all_decisions_ok": all_decisions_ok,
        "scheduler_state": scheduler_state,
        "decisions": decisions,
        "truth_boundary": "F3 proves state continuity across scheduler wake windows over mutable remote anchors; it is not endpoint-free or CPU-free execution.",
        "state_hash": "",
    }
    f3_state = seal(f3_state, "state_hash")
    f3_state_write = put_json(args.owner, args.repo, token, F3_STATE_PATH, f3_state, f"F3 loop state {run_id}")
    f3_state_check = wait_for_hash(args.owner, args.repo, token, F3_STATE_PATH, "state_hash", f3_state["state_hash"])

    f3_entry = {
        "stage": "F3-loop-ledger-entry",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "previous_state_hash": previous_state_hash,
        "selected_actions": selected_actions,
        "decision_hashes": [item["decision_hash"] for item in decisions],
        "window_count": final_window_count,
        "lifecycle_cycle_count": lifecycle_cycle_count,
        "f2_state_hash": f2_state["state_hash"],
        "f3_state_hash": f3_state["state_hash"],
        "entry_hash": "",
    }
    f3_ledger, f3_ledger_write = append_f3_ledger(args.owner, args.repo, token, run_id, args.mode, f3_entry)
    f3_ledger_check = wait_for_hash(args.owner, args.repo, token, F3_LEDGER_PATH, "ledger_hash", f3_ledger["ledger_hash"])

    raw_state_check: dict[str, Any] = {}
    if args.raw_check and f3_state_write.get("commit_hash"):
        sample = fetch_json_url(raw_url(args.owner, args.repo, str(f3_state_write["commit_hash"]), F3_STATE_PATH), "f3-state-commit-raw")
        payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
        raw_state_check = {
            "ok": bool(sample.get("ok") and payload.get("state_hash") == f3_state["state_hash"]),
            "status": sample.get("status"),
            "observed_state_hash": payload.get("state_hash"),
            "expected_state_hash": f3_state["state_hash"],
            "error": sample.get("error"),
        }

    core_ok = bool(
        f1_state_hash_ok
        and f2_capsule_write.get("ok")
        and f2_capsule_check.get("ok")
        and f3_capsule_write.get("ok")
        and f3_capsule_check.get("ok")
        and all_decisions_ok
        and f2_state_write.get("ok")
        and f2_state_check.get("ok")
        and f2_ledger_write.get("ok")
        and f2_ledger_check.get("ok")
        and f3_state_write.get("ok")
        and f3_state_check.get("ok")
        and f3_ledger_write.get("ok")
        and f3_ledger_check.get("ok")
    )
    if args.raw_check:
        core_ok = bool(core_ok and raw_state_check.get("ok"))

    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "F3-lowfreq-self-scheduler-loop",
        "ok": core_ok,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "source_f1_state_hash": f1_state.get("state_hash"),
        "source_f1_state_hash_ok": f1_state_hash_ok,
        "selected_actions": selected_actions,
        "decision_count": len(decisions),
        "all_decisions_ok": all_decisions_ok,
        "window_count": final_window_count,
        "windows_executed_this_run": len(decisions),
        "lifecycle_cycle_count": lifecycle_cycle_count,
        "f2_state": {"state_hash": f2_state["state_hash"], "write": f2_state_write, "verify": f2_state_check},
        "f2_ledger": {"ledger_hash": f2_ledger["ledger_hash"], "entry_count": f2_ledger["entry_count"], "write": f2_ledger_write, "verify": f2_ledger_check},
        "f3_capsule": {"capsule_hash": f3_capsule["capsule_hash"], "write": f3_capsule_write, "verify": f3_capsule_check},
        "f3_state": {"state_hash": f3_state["state_hash"], "write": f3_state_write, "verify": f3_state_check},
        "f3_ledger": {"ledger_hash": f3_ledger["ledger_hash"], "entry_count": f3_ledger["entry_count"], "write": f3_ledger_write, "verify": f3_ledger_check},
        "raw_state_check": raw_state_check,
        "decisions": decisions,
        "evidence_level": "F3-lowfreq-multi-run-self-scheduler-loop-v0" if core_ok else "F3-lowfreq-self-scheduler-loop-partial",
        "conclusion": "F3 proves that the F2 scheduler can continue across wake windows, using persisted remote state to select the next low-risk lifecycle action.",
        "truth_boundary": "F3 is a low-frequency external-runner loop over mutable remote anchors. It does not prove endpoint-free existence, CPU-free network computation, or autonomous digital life.",
    }

    last_run = build_last_run(result)
    last_report = build_last_report(result)
    last_run_write = put_json(args.owner, args.repo, token, F3_LAST_RUN_PATH, last_run, f"F3 last run {run_id}")
    last_report_write = put_json(args.owner, args.repo, token, F3_LAST_REPORT_PATH, last_report, f"F3 last report {run_id}")
    result["last_run"] = last_run
    result["last_report"] = last_report
    result["writes"] = {"last_run": last_run_write, "last_report": last_report_write}
    result["ok"] = bool(result["ok"] and last_run_write.get("ok") and last_report_write.get("ok"))
    result["evidence_level"] = "F3-lowfreq-multi-run-self-scheduler-loop-v0" if result["ok"] else "F3-lowfreq-self-scheduler-loop-partial"

    write_local(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "evidence_level": result["evidence_level"],
                "selected_actions": selected_actions,
                "window_count": final_window_count,
                "lifecycle_cycle_count": lifecycle_cycle_count,
                "f3_state_hash": f3_state["state_hash"],
                "f3_ledger_hash": f3_ledger["ledger_hash"],
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
