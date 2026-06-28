from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (Path(__file__).resolve().parent, ROOT, SCRIPTS):
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)

from nlang_1a_remote_f3_compile import DEFAULT_OWNER, DEFAULT_REPO, F3_STATE_PATH, map_remote_f3_state  # noqa: E402
from nlang_compiler_v0 import compile_rules, load_rules  # noqa: E402
from nsl_f1_capsule_lifecycle import put_json, seal, wait_for_hash  # noqa: E402
from nsl_f2_lifecycle_self_scheduler import (  # noqa: E402
    F1_STATE_PATH,
    LEDGER_PATH as F2_LEDGER_PATH,
    STATE_PATH as F2_STATE_PATH,
    append_decision,
    append_ledger as append_f2_ledger,
    build_scheduler_capsule,
    build_state as build_f2_state,
    execute_action,
    read_json_content,
)
from nsl_f3_lowfreq_self_scheduler_loop import (  # noqa: E402
    F3_LEDGER_PATH,
    F3_LAST_REPORT_PATH,
    F3_LAST_RUN_PATH,
    append_f3_ledger,
    build_last_report as build_f3_last_report,
    build_last_run as build_f3_last_run,
    build_loop_capsule,
)
from nsl_l12_hourly_self_maintenance import content_get, gh_token, now, run_owner, stable_hash  # noqa: E402


PROOF_LEDGER_PATH = "states/nlang-1b-proof-ledger.json"
LAST_RUN_PATH = "states/nlang-1b-last-run.json"
ALLOWED_ACTIONS = {"split", "decay", "retire", "peer_check", "observe"}


def run_id_for(prefix: str, mode: str) -> str:
    event = f"{prefix}_{mode}"
    return event + "-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def scheduler_state_from_remote_f3(remote_f3: dict[str, Any]) -> dict[str, Any]:
    scheduler_state = remote_f3.get("scheduler_state") if isinstance(remote_f3.get("scheduler_state"), dict) else {}
    return json.loads(json.dumps(scheduler_state, ensure_ascii=False))


def build_f3_state(
    run_id: str,
    mode: str,
    previous_f3_state: dict[str, Any],
    f1_state: dict[str, Any],
    f2_state_hash: str,
    f2_ledger_hash: str,
    f3_capsule_hash: str,
    scheduler_state: dict[str, Any],
    decision: dict[str, Any],
    action: str,
    stage_label: str,
) -> dict[str, Any]:
    window_count = int(previous_f3_state.get("window_count") or 0) + 1
    lifecycle_cycle_count = int(previous_f3_state.get("lifecycle_cycle_count") or 0)
    last_peer_check_cycle_count = int(previous_f3_state.get("last_peer_check_cycle_count") or 0)
    state = {
        "stage": "F3-lowfreq-self-scheduler-loop-state",
        "schema_version": "QMX-F3-STATE-0.1",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(mode),
        "mainline_contract": {
            "mainline": "F-series with NLANG/FIELD foundation prerequisites",
            "auxiliary_layers": {
                "L": "network language and controlled interpreter infrastructure",
                "E": "external wake, post-wake health check, ledger, and status infrastructure",
            },
            "rule": f"This F3 state was advanced by an {stage_label} compiled action_plan materializer.",
        },
        "previous_state_hash": previous_f3_state.get("state_hash"),
        "source_f1_state_hash": f1_state.get("state_hash"),
        "f2_state_hash": f2_state_hash,
        "f2_ledger_hash": f2_ledger_hash,
        "f3_capsule_hash": f3_capsule_hash,
        "window_count": window_count,
        "windows_executed_this_run": 1,
        "lifecycle_cycle_count": lifecycle_cycle_count,
        "last_peer_check_cycle_count": last_peer_check_cycle_count,
        "selected_actions": [action],
        "decision_count": 1,
        "all_decisions_ok": bool(decision.get("execution_ok")),
        "scheduler_state": scheduler_state,
        "decisions": [decision],
        "nlang_materialized": True,
        "truth_boundary": f"F3 state was advanced by {stage_label} materialization; this is still external-runner execution over mutable remote anchors.",
        "state_hash": "",
    }
    return seal(state, "state_hash")


def append_proof_ledger(
    owner: str,
    repo: str,
    token: str,
    run_id: str,
    entry: dict[str, Any],
    proof_ledger_path: str,
    stage_label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, _, _ = content_get(owner, repo, proof_ledger_path, token)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    sealed_entry = seal(entry, "entry_hash")
    entries = [item for item in entries if isinstance(item, dict) and item.get("run_id") != run_id]
    entries.append(sealed_entry)
    ledger = {
        "stage": f"{stage_label}-proof-ledger",
        "schema_version": "QMX-NLANG-1B-LEDGER-0.1",
        "updated_at": now(),
        "entry_count": len(entries),
        "latest_run_id": run_id,
        "entries": entries[-100:],
        "truth_boundary": "This ledger proves materialization of compiled NLANG action plans. It is mutable remote state, not tamper-proof storage.",
        "ledger_hash": "",
    }
    ledger = seal(ledger, "ledger_hash")
    write = put_json(owner, repo, token, proof_ledger_path, ledger, f"{stage_label} proof ledger {run_id}")
    return ledger, write


def main() -> int:
    parser = argparse.ArgumentParser(description="NLANG-1B materialize compiled action plan")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--stage-label", default="NLANG-1B")
    parser.add_argument("--run-prefix", default="nlang_1b")
    parser.add_argument("--proof-ledger-path", default=PROOF_LEDGER_PATH)
    parser.add_argument("--last-run-path", default=LAST_RUN_PATH)
    parser.add_argument("--rules", default=str(Path(__file__).with_name("remote_f3_rules.nlang")))
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest_nlang_1b_materialize_result.json"))
    args = parser.parse_args()

    token = gh_token()
    stage_label = str(args.stage_label)
    run_id = run_id_for(str(args.run_prefix), args.mode)
    remote_f3, _, f3_response = content_get(args.owner, args.repo, F3_STATE_PATH, token)
    if not isinstance(remote_f3, dict):
        result = {"stage": f"{stage_label}-materialize", "ok": False, "error": "missing_remote_f3_state", "status": f3_response.get("status")}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    remote_hash_ok = bool(remote_f3.get("state_hash") and remote_f3.get("state_hash") == stable_hash(remote_f3, "state_hash"))
    nlang_state = map_remote_f3_state(remote_f3)
    compiled = compile_rules(load_rules(Path(args.rules)), nlang_state)
    action = str(compiled.get("action_plan", {}).get("action") or "")
    risk_level = str(compiled.get("action_plan", {}).get("risk_level") or "")
    compile_ok = bool(remote_hash_ok and compiled.get("ok") and risk_level == "low" and action in ALLOWED_ACTIONS)

    f1_state, _ = read_json_content(args.owner, args.repo, token, F1_STATE_PATH)
    if not isinstance(f1_state, dict):
        compile_ok = False

    scheduler_state = scheduler_state_from_remote_f3(remote_f3)
    before_scheduler_state = json.loads(json.dumps(scheduler_state, ensure_ascii=False))
    f2_capsule = build_scheduler_capsule(run_id, str(f1_state.get("state_hash") if isinstance(f1_state, dict) else ""))
    f2_capsule_write = put_json(args.owner, args.repo, token, "states/f2-scheduler-capsule.json", f2_capsule, f"{stage_label} refresh F2 scheduler capsule {run_id}")
    f2_capsule_check = wait_for_hash(args.owner, args.repo, token, "states/f2-scheduler-capsule.json", "capsule_hash", f2_capsule["capsule_hash"])
    f3_capsule = build_loop_capsule(run_id, str(f1_state.get("state_hash") if isinstance(f1_state, dict) else ""))
    f3_capsule_write = put_json(args.owner, args.repo, token, "states/f3-loop-capsule.json", f3_capsule, f"{stage_label} refresh F3 capsule {run_id}")
    f3_capsule_check = wait_for_hash(args.owner, args.repo, token, "states/f3-loop-capsule.json", "capsule_hash", f3_capsule["capsule_hash"])

    execution = {"ok": False, "action": action, "error": "compile_or_risk_check_failed"}
    if compile_ok and isinstance(f1_state, dict):
        execution = execute_action(args.owner, args.repo, token, run_id, action, scheduler_state, f1_state)

    selected = {"action": action, "score": 100, "reason": "selected by NLANG compiler action_plan", "allowed": action in ALLOWED_ACTIONS}
    candidates = [
        {
            "action": item.get("action"),
            "score": 100 if item.get("matched") else 0,
            "reason": item.get("source"),
            "allowed": item.get("risk_level") == "low",
            "matched": item.get("matched"),
        }
        for item in compiled.get("rules", [])
        if isinstance(item, dict)
    ]
    decision = append_decision([], 1, candidates, selected, execution)
    decision["nlang_selected_rule"] = compiled.get("selected_rule")
    decision["nlang_action_plan"] = compiled.get("action_plan")
    scheduler_state["total_scheduler_ticks"] = int(scheduler_state.get("total_scheduler_ticks") or 0) + 1
    scheduler_state["last_selected_action"] = action

    all_ok = bool(compile_ok and execution.get("ok"))
    f2_state = build_f2_state(run_id, args.mode, f1_state if isinstance(f1_state, dict) else {}, f2_capsule["capsule_hash"], scheduler_state, [decision])
    f2_state_write = put_json(args.owner, args.repo, token, F2_STATE_PATH, f2_state, f"{stage_label} update F2 state {run_id}")
    f2_state_check = wait_for_hash(args.owner, args.repo, token, F2_STATE_PATH, "state_hash", f2_state["state_hash"])
    f2_entry = {
        "stage": f"{stage_label}-entry-over-f2-scheduler",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "selected_actions": [action],
        "decision_hashes": [decision["decision_hash"]],
        "decision_count": 1,
        "all_decisions_ok": all_ok,
        "state_hash": f2_state["state_hash"],
        "entry_hash": "",
    }
    f2_ledger, f2_ledger_write = append_f2_ledger(args.owner, args.repo, token, run_id, args.mode, f2_entry)
    f2_ledger_check = wait_for_hash(args.owner, args.repo, token, F2_LEDGER_PATH, "ledger_hash", f2_ledger["ledger_hash"])

    f3_state = build_f3_state(
        run_id,
        args.mode,
        remote_f3,
        f1_state if isinstance(f1_state, dict) else {},
        f2_state["state_hash"],
        f2_ledger["ledger_hash"],
        f3_capsule["capsule_hash"],
        scheduler_state,
        decision,
        action,
        stage_label,
    )
    f3_state_write = put_json(args.owner, args.repo, token, F3_STATE_PATH, f3_state, f"{stage_label} materialized F3 state {run_id}")
    f3_state_check = wait_for_hash(args.owner, args.repo, token, F3_STATE_PATH, "state_hash", f3_state["state_hash"])
    f3_entry = {
        "stage": f"{stage_label}-entry-over-f3-loop",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "previous_state_hash": remote_f3.get("state_hash"),
        "selected_actions": [action],
        "decision_hashes": [decision["decision_hash"]],
        "window_count": f3_state["window_count"],
        "lifecycle_cycle_count": f3_state["lifecycle_cycle_count"],
        "f2_state_hash": f2_state["state_hash"],
        "f3_state_hash": f3_state["state_hash"],
        "entry_hash": "",
    }
    f3_ledger, f3_ledger_write = append_f3_ledger(args.owner, args.repo, token, run_id, args.mode, f3_entry)
    f3_ledger_check = wait_for_hash(args.owner, args.repo, token, F3_LEDGER_PATH, "ledger_hash", f3_ledger["ledger_hash"])

    f3_result = {
        "run_id": run_id,
        "ok": all_ok,
        "evidence_level": f"{stage_label}-materialized-action-plan-v0",
        "selected_actions": [action],
        "window_count": f3_state["window_count"],
        "lifecycle_cycle_count": f3_state["lifecycle_cycle_count"],
        "last_peer_check_cycle_count": f3_state["last_peer_check_cycle_count"],
        "f3_state": {"state_hash": f3_state["state_hash"]},
        "f3_ledger": {"ledger_hash": f3_ledger["ledger_hash"]},
        "f2_state": {"state_hash": f2_state["state_hash"]},
        "truth_boundary": f"{stage_label} materializes a compiled action_plan with an external runner; it is not CPU-free execution.",
        "conclusion": f"{stage_label} materialized one low-risk NLANG-selected action into F2/F3 remote state.",
    }
    f3_last_run = build_f3_last_run(f3_result)
    f3_last_report = build_f3_last_report(f3_result)
    f3_last_run_write = put_json(args.owner, args.repo, token, F3_LAST_RUN_PATH, f3_last_run, f"{stage_label} update F3 last run {run_id}")
    f3_last_report_write = put_json(args.owner, args.repo, token, F3_LAST_REPORT_PATH, f3_last_report, f"{stage_label} update F3 last report {run_id}")

    proof_entry = {
        "stage": f"{stage_label}-proof-entry",
        "created_at": now(),
        "run_id": run_id,
        "remote_f3_state_hash_before": remote_f3.get("state_hash"),
        "remote_f3_state_hash_ok": remote_hash_ok,
        "compiled_ok": compiled.get("ok"),
        "selected_rule": compiled.get("selected_rule"),
        "action_plan": compiled.get("action_plan"),
        "materialized_action": action,
        "execution": execution,
        "before_scheduler_state": before_scheduler_state,
        "after_scheduler_state": scheduler_state,
        "f2_state_hash": f2_state["state_hash"],
        "f3_state_hash": f3_state["state_hash"],
        "entry_hash": "",
    }
    proof_ledger, proof_ledger_write = append_proof_ledger(
        args.owner,
        args.repo,
        token,
        run_id,
        proof_entry,
        args.proof_ledger_path,
        stage_label,
    )
    proof_ledger_check = wait_for_hash(args.owner, args.repo, token, args.proof_ledger_path, "ledger_hash", proof_ledger["ledger_hash"])

    core_ok = bool(
        all_ok
        and f2_capsule_write.get("ok")
        and f2_capsule_check.get("ok")
        and f3_capsule_write.get("ok")
        and f3_capsule_check.get("ok")
        and f2_state_write.get("ok")
        and f2_state_check.get("ok")
        and f2_ledger_write.get("ok")
        and f2_ledger_check.get("ok")
        and f3_state_write.get("ok")
        and f3_state_check.get("ok")
        and f3_ledger_write.get("ok")
        and f3_ledger_check.get("ok")
        and f3_last_run_write.get("ok")
        and f3_last_report_write.get("ok")
        and proof_ledger_write.get("ok")
        and proof_ledger_check.get("ok")
    )
    result = {
        "stage": f"{stage_label}-materialize-action-plan",
        "ok": core_ok,
        "run_id": run_id,
        "remote_f3_state_hash_before": remote_f3.get("state_hash"),
        "remote_f3_state_hash_ok": remote_hash_ok,
        "compiled_selected_action": action,
        "compiled_selected_rule": compiled.get("selected_rule"),
        "action_plan": compiled.get("action_plan"),
        "execution": execution,
        "before_child": before_scheduler_state.get("child"),
        "after_child": scheduler_state.get("child"),
        "f2_state_hash": f2_state["state_hash"],
        "f2_ledger_hash": f2_ledger["ledger_hash"],
        "f3_state_hash": f3_state["state_hash"],
        "f3_ledger_hash": f3_ledger["ledger_hash"],
        "proof_ledger_hash": proof_ledger["ledger_hash"],
        "f3_last_run_hash": f3_last_run["last_run_hash"],
        "f3_report_hash": f3_last_report["report_hash"],
        "writes": {
            "f2_state": f2_state_write,
            "f3_state": f3_state_write,
            "proof_ledger": proof_ledger_write,
            "f3_last_run": f3_last_run_write,
            "f3_last_report": f3_last_report_write,
        },
        "truth_boundary": f"{stage_label} proves compiled-plan materialization over remote anchors. It does not prove endpoint-free or CPU-free execution.",
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    put_json(args.owner, args.repo, token, args.last_run_path, result, f"{stage_label} last run {run_id}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
