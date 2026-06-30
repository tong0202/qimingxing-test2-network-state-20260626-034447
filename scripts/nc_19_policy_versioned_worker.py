#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

ACTIVE_PATH = "states/nc-13-transition/active.json"
BANK_PATH = "states/nc-16-register-bank/bank.json"
LAST_RUN_PATH = "states/nc-19-policy-versioned/last-run.json"
LEDGER_PATH = "states/nc-19-policy-versioned/ledger.json"
TARGET_INTENT = "execute_minimal_behavior_cycle"

BEHAVIOR_OPS = ("memory_append", "control_tick", "intent_focus", "safety_attest")
POLICY_MODES = ("use_active", "advance_policy", "rollback_policy")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(obj: Any) -> str:
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def encode_json(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def seal(obj: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = dict(obj)
    sealed[field] = ""
    sealed[field] = canonical_hash({k: v for k, v in sealed.items() if k != field})
    return sealed


def policy_catalog() -> dict[str, dict[str, Any]]:
    raw = {
        "policy_v1": {
            "version": "policy_v1",
            "name": "balanced_minimal_cycle",
            "target_intent": TARGET_INTENT,
            "rule": "if unsafe then safety_attest; if intent mismatch then intent_focus; if control_tick <= memory_entry_count then control_tick; else memory_append",
            "rollback_allowed": True,
        },
        "policy_v2": {
            "version": "policy_v2",
            "name": "control_first_minimal_cycle",
            "target_intent": TARGET_INTENT,
            "rule": "if unsafe then safety_attest; if intent mismatch then intent_focus; if control_tick < memory_entry_count + 2 then control_tick; else memory_append",
            "rollback_allowed": True,
        },
    }
    return {name: seal({**spec, "policy_hash": ""}, "policy_hash") for name, spec in raw.items()}


def token() -> str:
    value = os.environ.get("GITHUB_TOKEN", "").strip()
    if not value:
        raise RuntimeError("GITHUB_TOKEN is required")
    return value


def owner_repo() -> tuple[str, str]:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if "/" not in repo:
        return "tong0202", "qimingxing-test2-network-state-20260626-034447"
    owner, name = repo.split("/", 1)
    return owner, name


def github_request(method: str, path: str, token_value: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"https://api.github.com/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token_value}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "qimingxing-nc19-policy-versioned-worker",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def read_json(owner: str, repo: str, path: str, token_value: str) -> tuple[dict[str, Any] | None, str]:
    quoted = urllib.parse.quote(path, safe="/")
    try:
        data = github_request("GET", f"repos/{owner}/{repo}/contents/{quoted}?ref=main", token_value)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, ""
        raise
    content = str(data.get("content") or "").replace("\n", "")
    if not content:
        return None, str(data.get("sha") or "")
    raw = base64.b64decode(content.encode("utf-8"))
    return json.loads(raw.decode("utf-8")), str(data.get("sha") or "")


def put_json(owner: str, repo: str, path: str, token_value: str, obj: dict[str, Any], message: str) -> dict[str, Any]:
    _, sha = read_json(owner, repo, path, token_value)
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(encode_json(obj)).decode("ascii"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    quoted = urllib.parse.quote(path, safe="/")
    for attempt in range(1, 4):
        try:
            result = github_request("PUT", f"repos/{owner}/{repo}/contents/{quoted}", token_value, payload)
            return {
                "ok": True,
                "path": result.get("content", {}).get("path", path),
                "sha": result.get("content", {}).get("sha", ""),
                "attempt_count": attempt,
            }
        except urllib.error.HTTPError as exc:
            if exc.code == 409 and attempt < 3:
                _, fresh_sha = read_json(owner, repo, path, token_value)
                if fresh_sha:
                    payload["sha"] = fresh_sha
                time.sleep(2 * attempt)
                continue
            body = exc.read().decode("utf-8", "replace")[:300]
            return {"ok": False, "error": f"HTTPError {exc.code}: {body}", "attempt_count": attempt}
        except Exception as exc:  # noqa: BLE001
            if attempt < 3:
                time.sleep(2 * attempt)
                continue
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "attempt_count": attempt}
    return {"ok": False, "error": "unreachable_put_failure"}


def active_reference(active_state: dict[str, Any] | None) -> dict[str, Any]:
    active = active_state if isinstance(active_state, dict) else {}
    return {
        "path": ACTIVE_PATH,
        "seq": active.get("seq"),
        "state_hash": active.get("state_hash"),
        "run_id": active.get("run_id"),
        "op": active.get("op"),
    }


def ensure_policy_slot(bank: dict[str, Any]) -> dict[str, Any]:
    slots = bank.setdefault("slots", {})
    catalog = policy_catalog()
    existing = slots.get("policy") if isinstance(slots.get("policy"), dict) else {}
    active_version = existing.get("active_policy_version") or "policy_v1"
    if active_version not in catalog:
        active_version = "policy_v1"
    policy_slot = {
        "type": "policy_version_state",
        "active_policy_version": active_version,
        "previous_policy_version": existing.get("previous_policy_version") or "",
        "versions": catalog,
        "rollback_stack": list(existing.get("rollback_stack") or []),
        "transition_log": list(existing.get("transition_log") or [])[-32:],
        "last_policy_event": existing.get("last_policy_event") or {},
        "policy_guard": {
            "allowed_modes": list(POLICY_MODES),
            "behavior_ops": list(BEHAVIOR_OPS),
            "rollback_requires_stack": True,
        },
    }
    slots["policy"] = policy_slot
    return bank


def ensure_bank(bank: dict[str, Any] | None, run_id: str, active_state: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(bank, dict) and isinstance(bank.get("slots"), dict):
        return ensure_policy_slot(bank)
    bank_obj = {
        "stage": "NC-19-bootstrap-register-bank",
        "schema_version": "QMX-NC-19-BANK-BOOTSTRAP-0.1",
        "run_id": run_id,
        "bank_seq": 0,
        "prev_bank_hash": "",
        "active_reference": active_reference(active_state),
        "slots": {
            "memory": {"type": "append_log", "entries": [], "entry_count": 0},
            "control": {"type": "control_state", "tick": 0, "mode": "observe", "last_op": "bank_init"},
            "intent": {"type": "intent_state", "focus": "preserve_register_continuity", "priority": 1},
            "safety": {
                "type": "policy_state",
                "risk_level": "low",
                "allowlisted_ops": ["bank_init", *BEHAVIOR_OPS],
                "blocked": ["direct_body_write", "unreviewed_code_patch", "unbounded_network_action"],
            },
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "truth_boundary": "NC-19 bootstrap bank is remote repository state, not CPU-free computation.",
        "bank_hash": "",
    }
    return seal(ensure_policy_slot(bank_obj), "bank_hash")


def summarize_bank(bank: dict[str, Any]) -> dict[str, Any]:
    slots = bank.get("slots") if isinstance(bank.get("slots"), dict) else {}
    memory = slots.get("memory") if isinstance(slots.get("memory"), dict) else {}
    control = slots.get("control") if isinstance(slots.get("control"), dict) else {}
    intent = slots.get("intent") if isinstance(slots.get("intent"), dict) else {}
    safety = slots.get("safety") if isinstance(slots.get("safety"), dict) else {}
    policy = slots.get("policy") if isinstance(slots.get("policy"), dict) else {}
    active_policy = policy.get("active_policy_version") or "policy_v1"
    versions = policy.get("versions") if isinstance(policy.get("versions"), dict) else {}
    active_spec = versions.get(active_policy) if isinstance(versions.get(active_policy), dict) else {}
    return {
        "bank_seq": bank.get("bank_seq"),
        "bank_hash": bank.get("bank_hash"),
        "memory_entry_count": int(memory.get("entry_count") or 0),
        "control_tick": int(control.get("tick") or 0),
        "control_mode": control.get("mode"),
        "intent_focus": intent.get("focus"),
        "intent_priority": int(intent.get("priority") or 0),
        "safety_risk_level": safety.get("risk_level"),
        "safety_last_attested_at": safety.get("last_attested_at"),
        "allowlisted_ops": safety.get("allowlisted_ops") if isinstance(safety.get("allowlisted_ops"), list) else [],
        "active_policy_version": active_policy,
        "active_policy_hash": active_spec.get("policy_hash"),
        "rollback_stack": list(policy.get("rollback_stack") or []),
    }


def apply_policy_mode(bank: dict[str, Any], *, mode: str, run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if mode not in POLICY_MODES:
        raise RuntimeError(f"unsupported policy mode: {mode}")
    next_bank = ensure_policy_slot(json.loads(json.dumps(bank, ensure_ascii=False)))
    policy = next_bank["slots"]["policy"]
    before_version = policy.get("active_policy_version") or "policy_v1"
    after_version = before_version
    rollback_stack = list(policy.get("rollback_stack") or [])
    transition_reason = "active policy reused"
    transition_ok = True
    if mode == "advance_policy":
        after_version = "policy_v2" if before_version == "policy_v1" else before_version
        if after_version != before_version:
            rollback_stack.append(before_version)
            transition_reason = f"advanced {before_version} to {after_version}"
        else:
            transition_reason = f"already at {before_version}"
    elif mode == "rollback_policy":
        if rollback_stack:
            after_version = rollback_stack.pop()
            transition_reason = f"rolled back {before_version} to {after_version}"
        else:
            transition_ok = False
            transition_reason = "rollback stack empty; active policy retained"

    policy["previous_policy_version"] = before_version if after_version != before_version else policy.get("previous_policy_version", "")
    policy["active_policy_version"] = after_version
    policy["rollback_stack"] = rollback_stack[-8:]
    event = seal(
        {
            "run_id": run_id,
            "mode": mode,
            "before_policy_version": before_version,
            "after_policy_version": after_version,
            "ok": transition_ok,
            "reason": transition_reason,
            "created_at": now_iso(),
            "event_hash": "",
        },
        "event_hash",
    )
    log = list(policy.get("transition_log") or [])
    log.append(event)
    policy["transition_log"] = log[-32:]
    policy["last_policy_event"] = event
    next_bank["slots"]["policy"] = policy
    return next_bank, event


def choose_behavior_op(summary: dict[str, Any]) -> tuple[str, str]:
    active_policy = summary.get("active_policy_version") or "policy_v1"
    allowlisted = summary.get("allowlisted_ops") if isinstance(summary.get("allowlisted_ops"), list) else []
    if summary.get("safety_risk_level") != "low" or not summary.get("safety_last_attested_at"):
        op = "safety_attest"
        reason = f"{active_policy}: safety slot is not freshly attested as low risk"
    elif summary.get("intent_focus") != TARGET_INTENT:
        op = "intent_focus"
        reason = f"{active_policy}: intent slot is not focused on the minimal behavior cycle"
    elif active_policy == "policy_v2":
        if int(summary.get("control_tick") or 0) < int(summary.get("memory_entry_count") or 0) + 2:
            op = "control_tick"
            reason = "policy_v2: control_tick is less than memory_entry_count + 2"
        else:
            op = "memory_append"
            reason = "policy_v2: control is sufficiently ahead, append memory"
    else:
        if int(summary.get("control_tick") or 0) <= int(summary.get("memory_entry_count") or 0):
            op = "control_tick"
            reason = "policy_v1: control tick has not advanced beyond memory entry count"
        else:
            op = "memory_append"
            reason = "policy_v1: control is ahead, append memory"
    if op not in allowlisted:
        raise RuntimeError(f"chosen op is not allowlisted by safety slot: {op}")
    return op, reason


def apply_behavior_op(
    bank: dict[str, Any],
    *,
    op: str,
    reason: str,
    run_id: str,
    active_state: dict[str, Any] | None,
    cycle_index: int,
    policy_event: dict[str, Any],
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
        "decision_source": "remote_register_bank_policy_version",
        "policy_version": pre_summary.get("active_policy_version"),
        "policy_hash": pre_summary.get("active_policy_hash"),
        "policy_event_hash": policy_event.get("event_hash"),
        "active_state_hash": (active_state or {}).get("state_hash"),
        "created_at": now_iso(),
    }
    if op == "memory_append":
        entry = seal({**event, "entry_hash": ""}, "entry_hash")
        entries = list(slots["memory"].get("entries") or [])
        entries.append(entry)
        slots["memory"]["entries"] = entries[-32:]
        slots["memory"]["entry_count"] = len(slots["memory"]["entries"])
    elif op == "control_tick":
        slots["control"]["tick"] = int(slots["control"].get("tick") or 0) + 1
        slots["control"]["mode"] = "policy_versioned_behavior"
        slots["control"]["last_op"] = op
    elif op == "intent_focus":
        slots["intent"]["focus"] = TARGET_INTENT
        slots["intent"]["priority"] = int(slots["intent"].get("priority") or 1) + 1
        slots["intent"]["last_decision_reason"] = reason
    elif op == "safety_attest":
        slots["safety"]["risk_level"] = "low"
        slots["safety"]["last_attested_at"] = now_iso()
        slots["safety"]["last_attested_by"] = "nc19_policy_versioned_worker"
    else:
        raise RuntimeError(f"unsupported behavior op: {op}")

    behavior = next_bank.get("policy_versioned_behavior") if isinstance(next_bank.get("policy_versioned_behavior"), dict) else {}
    behavior["last_decision"] = event
    behavior["decision_count"] = int(behavior.get("decision_count") or 0) + 1
    behavior["target_intent"] = TARGET_INTENT
    next_bank["policy_versioned_behavior"] = behavior
    next_bank["stage"] = "NC-19-policy-versioned-register-bank"
    next_bank["run_id"] = run_id
    next_bank["bank_seq"] = next_seq
    next_bank["prev_bank_hash"] = previous_hash
    next_bank["active_reference"] = active_reference(active_state)
    next_bank["updated_at"] = now_iso()
    next_bank["last_op"] = op
    next_bank["remote_executor"] = {
        "platform": "github_actions",
        "workflow": "nc19-policy-versioned.yml",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        "cycle_index": cycle_index,
    }
    next_bank["truth_boundary"] = "NC-19 policy-versioned behavior is remote repository state transition, not CPU-free or endpoint-free computation."
    return seal(next_bank, "bank_hash")


def validate_bank(bank: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    slots = bank.get("slots") if isinstance(bank.get("slots"), dict) else {}
    expected = {
        "memory": "append_log",
        "control": "control_state",
        "intent": "intent_state",
        "safety": "policy_state",
        "policy": "policy_version_state",
    }
    for name, slot_type in expected.items():
        slot = slots.get(name) if isinstance(slots.get(name), dict) else {}
        if slot.get("type") != slot_type:
            errors.append(f"{name}_slot_type_mismatch")
    policy = slots.get("policy") if isinstance(slots.get("policy"), dict) else {}
    versions = policy.get("versions") if isinstance(policy.get("versions"), dict) else {}
    active = policy.get("active_policy_version")
    if active not in versions:
        errors.append("active_policy_missing_from_versions")
    for name in ("policy_v1", "policy_v2"):
        if name not in versions:
            errors.append(f"missing_{name}")
    return errors


def append_ledger(owner: str, repo: str, token_value: str, entries_to_add: list[dict[str, Any]], run_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, _ = read_json(owner, repo, LEDGER_PATH, token_value)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    existing = {item.get("entry_hash"): item for item in entries if isinstance(item, dict)}
    for entry in entries_to_add:
        existing[entry["entry_hash"]] = entry
    merged = list(existing.values())[-200:]
    ledger = seal(
        {
            "stage": "NC-19-policy-versioned-ledger",
            "schema_version": "QMX-NC-19-LEDGER-0.1",
            "updated_at": now_iso(),
            "latest_run_id": run_id,
            "entry_count": len(merged),
            "entries": merged,
            "truth_boundary": "NC-19 ledger records remote policy-versioned decisions, policy transitions, and writes.",
            "ledger_hash": "",
        },
        "ledger_hash",
    )
    write = put_json(owner, repo, LEDGER_PATH, token_value, ledger, f"NC-19 ledger {run_id}")
    return ledger, write


def run(args: argparse.Namespace) -> dict[str, Any]:
    token_value = token()
    owner, repo = owner_repo()
    run_id = args.run_id or f"nc19-policy-versioned-{os.environ.get('GITHUB_RUN_ID', 'local')}-attempt-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    active_state, _ = read_json(owner, repo, ACTIVE_PATH, token_value)
    bank_obj, _ = read_json(owner, repo, BANK_PATH, token_value)
    current = ensure_bank(bank_obj, run_id, active_state)
    policy_bank, policy_event = apply_policy_mode(current, mode=args.policy_mode, run_id=run_id)
    current = policy_bank

    decisions: list[dict[str, Any]] = []
    writes: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    for cycle_index in range(args.cycles):
        pre_summary = summarize_bank(current)
        chosen_op, reason = choose_behavior_op(pre_summary)
        next_bank = apply_behavior_op(
            current,
            op=chosen_op,
            reason=reason,
            run_id=run_id,
            active_state=active_state,
            cycle_index=cycle_index,
            policy_event=policy_event,
            pre_summary=pre_summary,
        )
        validation_errors = validate_bank(next_bank)
        write = put_json(owner, repo, BANK_PATH, token_value, next_bank, f"NC-19 policy behavior seq {next_bank['bank_seq']} {run_id}")
        decision = {
            "cycle_index": cycle_index,
            "decision_source": "remote_register_bank_policy_version",
            "local_requested_op": None,
            "pre_state_summary": pre_summary,
            "policy_mode": args.policy_mode,
            "policy_event": policy_event,
            "chosen_op": chosen_op,
            "decision_reason": reason,
            "post_bank_seq": next_bank["bank_seq"],
            "post_bank_hash": next_bank["bank_hash"],
            "prev_bank_hash": next_bank["prev_bank_hash"],
        }
        entry = seal(
            {
                **decision,
                "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
                "write_ok": bool(write.get("ok")),
                "validation_errors": validation_errors,
                "created_at": now_iso(),
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
                "policy_mode": args.policy_mode,
                "policy_event_hash": policy_event.get("event_hash"),
                "payload_hash": sha16(encode_json(next_bank)),
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
    last_run = seal(
        {
            "stage": "NC-19-policy-versioned-last-run",
            "schema_version": "QMX-NC-19-LAST-RUN-0.1",
            "created_at": now_iso(),
            "run_id": run_id,
            "ok": ok,
            "requested_cycles": args.cycles,
            "completed_cycles": sum(1 for item in writes if item["ok"]),
            "start_bank_seq": decisions[0]["pre_state_summary"].get("bank_seq") + 1 if decisions else None,
            "end_bank_seq": int(current.get("bank_seq") or 0),
            "bank_hash": str(current.get("bank_hash") or ""),
            "active_reference": active_reference(active_state),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
            "actor": os.environ.get("GITHUB_ACTOR", ""),
            "client_payload_contract": {
                "local_supplied_behavior_ops": False,
                "local_supplied_policy_mode": True,
                "local_supplied_cycles_only_for_behavior": True,
            },
            "policy_mode": args.policy_mode,
            "policy_event": policy_event,
            "decisions": decisions,
            "writes": writes,
            "ledger_hash": ledger.get("ledger_hash"),
            "ledger_write_ok": bool(ledger_write.get("ok")),
            "truth_boundary": "NC-19 proves controlled policy-versioned remote behavior, not CPU-free or endpoint-free network-native computation.",
            "last_run_hash": "",
        },
        "last_run_hash",
    )
    last_run_write = put_json(owner, repo, LAST_RUN_PATH, token_value, last_run, f"NC-19 last run {run_id}")
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
    parser = argparse.ArgumentParser(description="NC-19 policy-versioned behavior worker")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--policy-mode", choices=POLICY_MODES, default="use_active")
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.cycles < 1:
        raise SystemExit("--cycles must be >= 1")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
