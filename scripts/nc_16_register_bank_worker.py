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
LAST_RUN_PATH = "states/nc-16-register-bank/last-run.json"
LEDGER_PATH = "states/nc-16-register-bank/ledger.json"

ALLOWED_OPS = (
    "bank_init",
    "memory_append",
    "control_tick",
    "intent_focus",
    "safety_attest",
)


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
            "User-Agent": "qimingxing-nc16-register-bank-worker",
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


def initial_bank(run_id: str, active_state: dict[str, Any] | None) -> dict[str, Any]:
    bank = {
        "stage": "NC-16-typed-register-bank",
        "schema_version": "QMX-NC-16-BANK-0.1",
        "run_id": run_id,
        "bank_seq": 0,
        "prev_bank_hash": "",
        "active_reference": active_reference(active_state),
        "slots": {
            "memory": {
                "type": "append_log",
                "entries": [],
                "entry_count": 0,
            },
            "control": {
                "type": "control_state",
                "tick": 0,
                "mode": "observe",
                "last_op": "bank_init",
            },
            "intent": {
                "type": "intent_state",
                "focus": "preserve_register_continuity",
                "priority": 1,
            },
            "safety": {
                "type": "policy_state",
                "risk_level": "low",
                "allowlisted_ops": list(ALLOWED_OPS),
                "blocked": [
                    "direct_body_write",
                    "unreviewed_code_patch",
                    "unbounded_network_action",
                ],
            },
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "truth_boundary": "NC-16 typed register bank is remote repository state maintained by GitHub Actions, not CPU-free or endpoint-free computation.",
        "bank_hash": "",
    }
    return seal(bank, "bank_hash")


def parse_ops(value: str, steps: int) -> list[str]:
    raw_ops = [item.strip() for item in value.split(",") if item.strip()]
    if not raw_ops:
        raw_ops = ["memory_append", "control_tick", "intent_focus", "safety_attest"]
    for op in raw_ops:
        if op not in ALLOWED_OPS:
            raise RuntimeError(f"operation is not allowlisted: {op}")
    if steps < 1:
        raise RuntimeError("steps must be >= 1")
    expanded: list[str] = []
    while len(expanded) < steps:
        expanded.extend(raw_ops)
    return expanded[:steps]


def apply_op(bank: dict[str, Any], *, op: str, run_id: str, active_state: dict[str, Any] | None, step_index: int) -> dict[str, Any]:
    if op not in ALLOWED_OPS:
        raise RuntimeError(f"operation is not allowlisted: {op}")
    previous_hash = str(bank.get("bank_hash") or "")
    slots = bank.get("slots") if isinstance(bank.get("slots"), dict) else {}
    next_bank = json.loads(json.dumps(bank, ensure_ascii=False))
    next_slots = next_bank["slots"]
    next_seq = int(next_bank.get("bank_seq") or 0) + 1
    event = {
        "run_id": run_id,
        "bank_seq": next_seq,
        "op": op,
        "step_index": step_index,
        "active_state_hash": (active_state or {}).get("state_hash"),
        "created_at": now_iso(),
    }

    if op == "bank_init":
        next_slots["control"]["mode"] = "observe"
        next_slots["control"]["last_op"] = op
    elif op == "memory_append":
        entry = seal({**event, "entry_hash": ""}, "entry_hash")
        entries = list(slots.get("memory", {}).get("entries") or [])
        entries.append(entry)
        next_slots["memory"]["entries"] = entries[-32:]
        next_slots["memory"]["entry_count"] = len(next_slots["memory"]["entries"])
    elif op == "control_tick":
        next_slots["control"]["tick"] = int(next_slots["control"].get("tick") or 0) + 1
        next_slots["control"]["mode"] = "remote_tick"
        next_slots["control"]["last_op"] = op
    elif op == "intent_focus":
        next_slots["intent"]["focus"] = "expand_typed_register_bank"
        next_slots["intent"]["priority"] = int(next_slots["intent"].get("priority") or 1) + 1
    elif op == "safety_attest":
        next_slots["safety"]["last_attested_at"] = now_iso()
        next_slots["safety"]["last_attested_by"] = "nc16_remote_worker"
        next_slots["safety"]["risk_level"] = "low"

    next_bank["run_id"] = run_id
    next_bank["bank_seq"] = next_seq
    next_bank["prev_bank_hash"] = previous_hash
    next_bank["active_reference"] = active_reference(active_state)
    next_bank["updated_at"] = now_iso()
    next_bank["last_op"] = op
    next_bank["remote_executor"] = {
        "platform": "github_actions",
        "workflow": "nc16-register-bank.yml",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        "step_index": step_index,
    }
    return seal(next_bank, "bank_hash")


def validate_bank(bank: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    slots = bank.get("slots") if isinstance(bank.get("slots"), dict) else {}
    expected = {
        "memory": "append_log",
        "control": "control_state",
        "intent": "intent_state",
        "safety": "policy_state",
    }
    for name, slot_type in expected.items():
        slot = slots.get(name) if isinstance(slots.get(name), dict) else {}
        if slot.get("type") != slot_type:
            errors.append(f"{name}_slot_type_mismatch")
    safety = slots.get("safety") if isinstance(slots.get("safety"), dict) else {}
    allowlisted = safety.get("allowlisted_ops") if isinstance(safety.get("allowlisted_ops"), list) else []
    for op in ALLOWED_OPS:
        if op not in allowlisted:
            errors.append(f"missing_allowlisted_op_{op}")
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
            "stage": "NC-16-register-bank-ledger",
            "schema_version": "QMX-NC-16-LEDGER-0.1",
            "updated_at": now_iso(),
            "latest_run_id": run_id,
            "entry_count": len(merged),
            "entries": merged,
            "truth_boundary": "NC-16 ledger records controlled remote register-bank slot transitions.",
            "ledger_hash": "",
        },
        "ledger_hash",
    )
    write = put_json(owner, repo, LEDGER_PATH, token_value, ledger, f"NC-16 ledger {run_id}")
    return ledger, write


def run(args: argparse.Namespace) -> dict[str, Any]:
    token_value = token()
    owner, repo = owner_repo()
    run_id = args.run_id or f"nc16-register-bank-{os.environ.get('GITHUB_RUN_ID', 'local')}-attempt-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    active_state, _ = read_json(owner, repo, ACTIVE_PATH, token_value)
    bank, _ = read_json(owner, repo, BANK_PATH, token_value)
    if not isinstance(bank, dict):
        bank = initial_bank(run_id, active_state)

    ops = parse_ops(args.ops, args.steps)
    writes: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    current = bank
    for step_index, op in enumerate(ops):
        next_bank = apply_op(current, op=op, run_id=run_id, active_state=active_state, step_index=step_index)
        validation_errors = validate_bank(next_bank)
        write = put_json(owner, repo, BANK_PATH, token_value, next_bank, f"NC-16 bank seq {next_bank['bank_seq']} {run_id}")
        entry = seal(
            {
                "run_id": run_id,
                "bank_seq": next_bank["bank_seq"],
                "op": op,
                "prev_bank_hash": next_bank["prev_bank_hash"],
                "bank_hash": next_bank["bank_hash"],
                "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
                "validation_errors": validation_errors,
                "write_ok": bool(write.get("ok")),
                "created_at": now_iso(),
                "entry_hash": "",
            },
            "entry_hash",
        )
        ledger_entries.append(entry)
        writes.append(
            {
                "ok": bool(write.get("ok")) and not validation_errors,
                "op": op,
                "bank_seq": next_bank["bank_seq"],
                "bank_hash": next_bank["bank_hash"],
                "prev_bank_hash": next_bank["prev_bank_hash"],
                "payload_hash": sha16(encode_json(next_bank)),
                "validation_errors": validation_errors,
                "write": write,
            }
        )
        if not write.get("ok") or validation_errors:
            current = next_bank
            break
        current = next_bank
        time.sleep(max(0.0, args.pause))

    ok = len(writes) == len(ops) and all(item["ok"] for item in writes)
    ledger, ledger_write = append_ledger(owner, repo, token_value, ledger_entries, run_id)
    last_run = seal(
        {
            "stage": "NC-16-register-bank-last-run",
            "schema_version": "QMX-NC-16-LAST-RUN-0.1",
            "created_at": now_iso(),
            "run_id": run_id,
            "ok": ok,
            "requested_steps": args.steps,
            "completed_steps": sum(1 for item in writes if item["ok"]),
            "start_bank_seq": int(bank.get("bank_seq") or 0) + 1,
            "end_bank_seq": int(current.get("bank_seq") or 0),
            "bank_hash": str(current.get("bank_hash") or ""),
            "active_reference": active_reference(active_state),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
            "actor": os.environ.get("GITHUB_ACTOR", ""),
            "ops": ops,
            "writes": writes,
            "ledger_hash": ledger.get("ledger_hash"),
            "ledger_write_ok": bool(ledger_write.get("ok")),
            "truth_boundary": "NC-16 proves controlled remote typed register-bank maintenance, not CPU-free or endpoint-free network-native computation.",
            "last_run_hash": "",
        },
        "last_run_hash",
    )
    last_run_write = put_json(owner, repo, LAST_RUN_PATH, token_value, last_run, f"NC-16 last run {run_id}")
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
    parser = argparse.ArgumentParser(description="NC-16 typed register bank remote worker")
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--ops", default="")
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
