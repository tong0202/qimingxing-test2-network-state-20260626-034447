#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

import nc_19_policy_versioned_worker as nc19

ACTIVE_PATH = nc19.ACTIVE_PATH
BANK_PATH = nc19.BANK_PATH
LAST_RUN_PATH = "states/nc-20-guarded-policy/last-run.json"
LEDGER_PATH = "states/nc-20-guarded-policy/ledger.json"
TARGET_INTENT = nc19.TARGET_INTENT
POLICY_MODES = nc19.POLICY_MODES
GUARD_VERSION = "QMX-NC-20-GUARD-0.1"


def guarded_state(bank: dict[str, Any]) -> dict[str, Any]:
    slots = bank.get("slots") if isinstance(bank.get("slots"), dict) else {}
    policy = slots.get("policy") if isinstance(slots.get("policy"), dict) else {}
    state = policy.get("guarded_self_selection") if isinstance(policy.get("guarded_self_selection"), dict) else {}
    history = state.get("history") if isinstance(state.get("history"), list) else []
    return {
        "type": "guarded_policy_self_selection_state",
        "guard_version": GUARD_VERSION,
        "selection_count": int(state.get("selection_count") or 0),
        "history": history[-16:],
        "last_selector_event": state.get("last_selector_event") if isinstance(state.get("last_selector_event"), dict) else {},
    }


def last_guard_mode(bank: dict[str, Any]) -> str:
    state = guarded_state(bank)
    history = state.get("history") if isinstance(state.get("history"), list) else []
    if history and isinstance(history[-1], dict):
        return str(history[-1].get("selected_policy_mode") or "")
    return ""


def select_guarded_policy_mode(bank: dict[str, Any], *, run_id: str) -> dict[str, Any]:
    summary = nc19.summarize_bank(bank)
    active_policy = str(summary.get("active_policy_version") or "policy_v1")
    rollback_stack = list(summary.get("rollback_stack") or [])
    control_tick = int(summary.get("control_tick") or 0)
    memory_count = int(summary.get("memory_entry_count") or 0)
    safety_low = summary.get("safety_risk_level") == "low"
    intent_ready = summary.get("intent_focus") == TARGET_INTENT
    previous_guard_mode = last_guard_mode(bank)

    selected = "use_active"
    reason = "default guarded reuse"
    if not safety_low:
        selected = "use_active"
        reason = "safety is not low; keep active policy and let behavior attest safety"
    elif active_policy == "policy_v2" and rollback_stack and control_tick >= memory_count + 1:
        selected = "rollback_policy"
        reason = "policy_v2 control pressure is ahead of memory by >= 1; rollback guard fires"
    elif active_policy == "policy_v1" and previous_guard_mode == "rollback_policy":
        selected = "use_active"
        reason = "post-rollback cooldown; do not immediately advance again"
    elif active_policy == "policy_v1" and safety_low and intent_ready and control_tick >= memory_count:
        selected = "advance_policy"
        reason = "policy_v1 is stable and control is caught up with memory; advance guard fires"
    else:
        selected = "use_active"
        reason = "no guarded transition condition matched"

    return nc19.seal(
        {
            "run_id": run_id,
            "guard_version": GUARD_VERSION,
            "decision_source": "remote_register_bank_guarded_policy_selector",
            "local_requested_policy_mode": None,
            "selected_policy_mode": selected,
            "reason": reason,
            "selector_inputs": {
                "bank_seq": summary.get("bank_seq"),
                "bank_hash": summary.get("bank_hash"),
                "active_policy_version": active_policy,
                "rollback_stack": rollback_stack,
                "memory_entry_count": memory_count,
                "control_tick": control_tick,
                "safety_risk_level": summary.get("safety_risk_level"),
                "intent_focus": summary.get("intent_focus"),
                "previous_guard_mode": previous_guard_mode,
            },
            "created_at": nc19.now_iso(),
            "selector_hash": "",
        },
        "selector_hash",
    )


def attach_guarded_state(bank: dict[str, Any], selector_event: dict[str, Any]) -> dict[str, Any]:
    next_bank = json.loads(json.dumps(bank, ensure_ascii=False))
    slots = next_bank.setdefault("slots", {})
    policy = slots.setdefault("policy", {})
    state = guarded_state(next_bank)
    history = list(state.get("history") or [])
    history.append(selector_event)
    state["history"] = history[-16:]
    state["selection_count"] = int(state.get("selection_count") or 0) + 1
    state["last_selector_event"] = selector_event
    policy["guarded_self_selection"] = state
    slots["policy"] = policy
    next_bank["slots"] = slots
    return next_bank


def ensure_bank_preserving_guard(bank: dict[str, Any] | None, run_id: str, active_state: dict[str, Any] | None) -> dict[str, Any]:
    preserved_guard: dict[str, Any] = {}
    if isinstance(bank, dict):
        slots = bank.get("slots") if isinstance(bank.get("slots"), dict) else {}
        policy = slots.get("policy") if isinstance(slots.get("policy"), dict) else {}
        guard = policy.get("guarded_self_selection")
        if isinstance(guard, dict):
            preserved_guard = guard
    current = nc19.ensure_bank(bank, run_id, active_state)
    if preserved_guard:
        current.setdefault("slots", {}).setdefault("policy", {})["guarded_self_selection"] = preserved_guard
    return current


def apply_guarded_behavior_op(
    bank: dict[str, Any],
    *,
    op: str,
    reason: str,
    run_id: str,
    active_state: dict[str, Any] | None,
    cycle_index: int,
    policy_event: dict[str, Any],
    selector_event: dict[str, Any],
    pre_summary: dict[str, Any],
) -> dict[str, Any]:
    previous_hash = str(bank.get("bank_hash") or "")
    next_bank = json.loads(json.dumps(bank, ensure_ascii=False))
    slots = next_bank["slots"]
    next_seq = int(next_bank.get("bank_seq") or 0) + 1
    event = {
        "run_id": run_id,
        "bank_seq": next_seq,
        "op": op,
        "cycle_index": cycle_index,
        "decision_reason": reason,
        "decision_source": "remote_register_bank_guarded_policy_version",
        "selector_hash": selector_event.get("selector_hash"),
        "selected_policy_mode": selector_event.get("selected_policy_mode"),
        "policy_version": pre_summary.get("active_policy_version"),
        "policy_hash": pre_summary.get("active_policy_hash"),
        "policy_event_hash": policy_event.get("event_hash"),
        "active_state_hash": (active_state or {}).get("state_hash"),
        "created_at": nc19.now_iso(),
    }
    if op == "memory_append":
        entry = nc19.seal({**event, "entry_hash": ""}, "entry_hash")
        entries = list(slots["memory"].get("entries") or [])
        entries.append(entry)
        slots["memory"]["entries"] = entries[-32:]
        slots["memory"]["entry_count"] = len(slots["memory"]["entries"])
    elif op == "control_tick":
        slots["control"]["tick"] = int(slots["control"].get("tick") or 0) + 1
        slots["control"]["mode"] = "guarded_policy_self_selection"
        slots["control"]["last_op"] = op
    elif op == "intent_focus":
        slots["intent"]["focus"] = TARGET_INTENT
        slots["intent"]["priority"] = int(slots["intent"].get("priority") or 1) + 1
        slots["intent"]["last_decision_reason"] = reason
    elif op == "safety_attest":
        slots["safety"]["risk_level"] = "low"
        slots["safety"]["last_attested_at"] = nc19.now_iso()
        slots["safety"]["last_attested_by"] = "nc20_guarded_policy_self_selection_worker"
    else:
        raise RuntimeError(f"unsupported behavior op: {op}")

    behavior = next_bank.get("guarded_policy_behavior") if isinstance(next_bank.get("guarded_policy_behavior"), dict) else {}
    behavior["last_decision"] = event
    behavior["last_selector_event"] = selector_event
    behavior["decision_count"] = int(behavior.get("decision_count") or 0) + 1
    behavior["target_intent"] = TARGET_INTENT
    next_bank["guarded_policy_behavior"] = behavior
    next_bank["stage"] = "NC-20-guarded-policy-register-bank"
    next_bank["run_id"] = run_id
    next_bank["bank_seq"] = next_seq
    next_bank["prev_bank_hash"] = previous_hash
    next_bank["active_reference"] = nc19.active_reference(active_state)
    next_bank["updated_at"] = nc19.now_iso()
    next_bank["last_op"] = op
    next_bank["remote_executor"] = {
        "platform": "github_actions",
        "workflow": "nc20-guarded-policy-self-selection.yml",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        "cycle_index": cycle_index,
    }
    next_bank["truth_boundary"] = "NC-20 guarded policy self-selection is remote repository state transition, not CPU-free or endpoint-free computation."
    return nc19.seal(next_bank, "bank_hash")


def append_ledger(owner: str, repo: str, token_value: str, entries_to_add: list[dict[str, Any]], run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, _ = nc19.read_json(owner, repo, LEDGER_PATH, token_value)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    existing = {item.get("entry_hash"): item for item in entries if isinstance(item, dict)}
    for entry in entries_to_add:
        existing[entry["entry_hash"]] = entry
    merged = list(existing.values())[-200:]
    ledger = nc19.seal(
        {
            "stage": "NC-20-guarded-policy-ledger",
            "schema_version": "QMX-NC-20-LEDGER-0.1",
            "updated_at": nc19.now_iso(),
            "latest_run_id": run_id,
            "entry_count": len(merged),
            "entries": merged,
            "truth_boundary": "NC-20 ledger records guarded policy self-selection, policy transitions, and writes.",
            "ledger_hash": "",
        },
        "ledger_hash",
    )
    write = nc19.put_json(owner, repo, LEDGER_PATH, token_value, ledger, f"NC-20 guarded policy ledger {run_id}")
    return ledger, write


def run(args: argparse.Namespace) -> dict[str, Any]:
    token_value = nc19.token()
    owner, repo = nc19.owner_repo()
    run_id = args.run_id or f"nc20-guarded-policy-{os.environ.get('GITHUB_RUN_ID', 'local')}-attempt-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    active_state, _ = nc19.read_json(owner, repo, ACTIVE_PATH, token_value)
    bank_obj, _ = nc19.read_json(owner, repo, BANK_PATH, token_value)
    current = ensure_bank_preserving_guard(bank_obj, run_id, active_state)
    selector_event = select_guarded_policy_mode(current, run_id=run_id)
    policy_bank, policy_event = nc19.apply_policy_mode(current, mode=selector_event["selected_policy_mode"], run_id=run_id)
    current = attach_guarded_state(policy_bank, selector_event)

    decisions: list[dict[str, Any]] = []
    writes: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    for cycle_index in range(args.cycles):
        pre_summary = nc19.summarize_bank(current)
        chosen_op, reason = nc19.choose_behavior_op(pre_summary)
        next_bank = apply_guarded_behavior_op(
            current,
            op=chosen_op,
            reason=reason,
            run_id=run_id,
            active_state=active_state,
            cycle_index=cycle_index,
            policy_event=policy_event,
            selector_event=selector_event,
            pre_summary=pre_summary,
        )
        validation_errors = nc19.validate_bank(next_bank)
        write = nc19.put_json(owner, repo, BANK_PATH, token_value, next_bank, f"NC-20 guarded policy seq {next_bank['bank_seq']} {run_id}")
        decision = {
            "cycle_index": cycle_index,
            "decision_source": "remote_register_bank_guarded_policy_version",
            "local_requested_op": None,
            "local_requested_policy_mode": None,
            "pre_state_summary": pre_summary,
            "selector_event": selector_event,
            "selected_policy_mode": selector_event["selected_policy_mode"],
            "policy_event": policy_event,
            "chosen_op": chosen_op,
            "decision_reason": reason,
            "post_bank_seq": next_bank["bank_seq"],
            "post_bank_hash": next_bank["bank_hash"],
            "prev_bank_hash": next_bank["prev_bank_hash"],
        }
        entry = nc19.seal(
            {
                **decision,
                "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
                "write_ok": bool(write.get("ok")),
                "validation_errors": validation_errors,
                "created_at": nc19.now_iso(),
                "entry_hash": "",
            },
            "entry_hash",
        )
        ledger_entries.append(entry)
        decisions.append(decision)
        writes.append(
            {
                "ok": bool(write.get("ok")) and not validation_errors,
                "cycle_index": cycle_index,
                "op": chosen_op,
                "bank_seq": next_bank["bank_seq"],
                "bank_hash": next_bank["bank_hash"],
                "prev_bank_hash": next_bank["prev_bank_hash"],
                "policy_version": pre_summary.get("active_policy_version"),
                "policy_hash": pre_summary.get("active_policy_hash"),
                "selected_policy_mode": selector_event["selected_policy_mode"],
                "selector_hash": selector_event.get("selector_hash"),
                "policy_event_hash": policy_event.get("event_hash"),
                "payload_hash": nc19.sha16(nc19.encode_json(next_bank)),
                "validation_errors": validation_errors,
                "write": write,
            }
        )
        current = next_bank
        if not write.get("ok") or validation_errors:
            break
        time.sleep(max(0.0, args.pause))

    ok = len(writes) == args.cycles and all(item["ok"] for item in writes)
    ledger, ledger_write = append_ledger(owner, repo, token_value, ledger_entries, run_id)
    last_run = nc19.seal(
        {
            "stage": "NC-20-guarded-policy-last-run",
            "schema_version": "QMX-NC-20-LAST-RUN-0.1",
            "created_at": nc19.now_iso(),
            "run_id": run_id,
            "ok": ok,
            "requested_cycles": args.cycles,
            "completed_cycles": sum(1 for item in writes if item["ok"]),
            "start_bank_seq": decisions[0]["pre_state_summary"].get("bank_seq") + 1 if decisions else None,
            "end_bank_seq": int(current.get("bank_seq") or 0),
            "bank_hash": str(current.get("bank_hash") or ""),
            "active_reference": nc19.active_reference(active_state),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
            "actor": os.environ.get("GITHUB_ACTOR", ""),
            "client_payload_contract": {
                "local_supplied_behavior_ops": False,
                "local_supplied_policy_mode": False,
                "local_supplied_cycles_only_for_behavior": True,
            },
            "selected_policy_mode": selector_event["selected_policy_mode"],
            "selector_event": selector_event,
            "policy_event": policy_event,
            "decisions": decisions,
            "writes": writes,
            "ledger_hash": ledger.get("ledger_hash"),
            "ledger_write_ok": bool(ledger_write.get("ok")),
            "truth_boundary": "NC-20 proves guarded policy self-selection over remote repository state, not CPU-free or endpoint-free network-native computation.",
            "last_run_hash": "",
        },
        "last_run_hash",
    )
    last_run_write = nc19.put_json(owner, repo, LAST_RUN_PATH, token_value, last_run, f"NC-20 guarded policy last run {run_id}")
    result = {
        "ok": ok and bool(ledger_write.get("ok")) and bool(last_run_write.get("ok")),
        "last_run": last_run,
        "last_run_write": last_run_write,
        "ledger_write": ledger_write,
        "bank": current,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="NC-20 guarded policy self-selection worker")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.cycles < 1:
        raise SystemExit("--cycles must be >= 1")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
