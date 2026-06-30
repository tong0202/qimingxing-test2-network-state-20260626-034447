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
HOLD_PATH = "states/nc-13-transition/hold.json"
NC14_LAST_RUN_PATH = "states/nc-14/last-run.json"
NC14_LEDGER_PATH = "states/nc-14/transition-ledger.json"
OPS = ("remote_seed", "remote_pulse", "remote_split", "remote_invert", "remote_merge", "remote_rest")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(obj: Any) -> str:
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def encode_json(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


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
            "User-Agent": "qimingxing-nc14-remote-transition-worker",
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


def make_body(run_id: str, seq: int, op: str, size: int) -> str:
    seed = f"{run_id}|nc14-remote|{seq}|{op}"
    fragments = [hashlib.sha256(f"{seed}|{i}".encode("utf-8")).hexdigest()[:12] for i in range(24)]
    core = f"{seq:04d}:{op}:" + "|".join(fragments) + "|"
    repeats = (size // max(1, len(core))) + 1
    return (core * repeats)[:size]


def build_active_payload(
    *,
    run_id: str,
    seq: int,
    op: str,
    prev_state: dict[str, Any],
    hold_state: dict[str, Any],
    body_size: int,
    step_index: int,
) -> dict[str, Any]:
    prev_hash = str(prev_state.get("state_hash") or "")
    payload = {
        "stage": "NC-14-remote-transition-active-register",
        "schema_version": "QMX-NC-14-ACTIVE-0.1",
        "run_id": run_id,
        "register": "active",
        "seq": seq,
        "op": op,
        "prev_state_hash": prev_hash,
        "hold_state_hash": str(hold_state.get("state_hash") or ""),
        "remote_executor": {
            "platform": "github_actions",
            "workflow": "nc14-remote-transition-executor.yml",
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
            "step_index": step_index,
        },
        "body": make_body(run_id, seq, op, body_size),
        "created_at": now_iso(),
        "truth_boundary": "NC-14 active transition was written by a remote GitHub Actions executor, not by endpoint-free or CPU-free network computation.",
        "state_hash": "",
    }
    return seal(payload, "state_hash")


def append_ledger(
    *,
    owner: str,
    repo: str,
    token_value: str,
    run_summary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, _ = read_json(owner, repo, NC14_LEDGER_PATH, token_value)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    entry = seal(
        {
            "run_id": run_summary["run_id"],
            "created_at": run_summary["created_at"],
            "ok": run_summary["ok"],
            "steps": run_summary["steps"],
            "start_seq": run_summary["start_seq"],
            "end_seq": run_summary["end_seq"],
            "active_state_hash": run_summary["active_state_hash"],
            "github_run_id": run_summary["github_run_id"],
            "entry_hash": "",
        },
        "entry_hash",
    )
    entries = [item for item in entries if isinstance(item, dict) and item.get("run_id") != run_summary["run_id"]]
    entries.append(entry)
    entries = entries[-100:]
    ledger = seal(
        {
            "stage": "NC-14-remote-transition-ledger",
            "schema_version": "QMX-NC-14-LEDGER-0.1",
            "updated_at": now_iso(),
            "entry_count": len(entries),
            "latest_run_id": run_summary["run_id"],
            "entries": entries,
            "truth_boundary": "NC-14 ledger records remote platform execution; it is mutable GitHub repository state.",
            "ledger_hash": "",
        },
        "ledger_hash",
    )
    write = put_json(owner, repo, NC14_LEDGER_PATH, token_value, ledger, f"NC-14 ledger {run_summary['run_id']}")
    return ledger, write


def run(args: argparse.Namespace) -> dict[str, Any]:
    token_value = token()
    owner, repo = owner_repo()
    run_id = args.run_id or f"nc14-remote-{os.environ.get('GITHUB_RUN_ID', 'local')}-attempt-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    active_state, _ = read_json(owner, repo, ACTIVE_PATH, token_value)
    hold_state, _ = read_json(owner, repo, HOLD_PATH, token_value)
    if not isinstance(active_state, dict):
        raise RuntimeError(f"missing active state at {ACTIVE_PATH}")
    if not isinstance(hold_state, dict):
        raise RuntimeError(f"missing hold state at {HOLD_PATH}")

    start_seq = int(active_state.get("seq") or 0) + 1
    writes: list[dict[str, Any]] = []
    current = active_state
    for step_index in range(args.steps):
        seq = start_seq + step_index
        op = OPS[seq % len(OPS)]
        payload = build_active_payload(
            run_id=run_id,
            seq=seq,
            op=op,
            prev_state=current,
            hold_state=hold_state,
            body_size=args.body_size,
            step_index=step_index,
        )
        write = put_json(owner, repo, ACTIVE_PATH, token_value, payload, f"NC-14 remote active seq {seq} {run_id}")
        writes.append(
            {
                "seq": seq,
                "op": op,
                "ok": bool(write.get("ok")),
                "write": write,
                "state_hash": payload["state_hash"],
                "payload_hash": sha16(encode_json(payload)),
                "prev_state_hash": payload["prev_state_hash"],
            }
        )
        if not write.get("ok"):
            break
        current = payload
        time.sleep(max(0.0, args.pause))

    ok = len(writes) == args.steps and all(item["ok"] for item in writes)
    run_summary = seal(
        {
            "stage": "NC-14-remote-transition-last-run",
            "schema_version": "QMX-NC-14-LAST-RUN-0.1",
            "created_at": now_iso(),
            "run_id": run_id,
            "ok": ok,
            "steps": args.steps,
            "completed_steps": sum(1 for item in writes if item["ok"]),
            "start_seq": start_seq,
            "end_seq": int(current.get("seq") or start_seq - 1),
            "active_state_hash": str(current.get("state_hash") or ""),
            "hold_state_hash": str(hold_state.get("state_hash") or ""),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
            "actor": os.environ.get("GITHUB_ACTOR", ""),
            "writes": writes,
            "truth_boundary": "NC-14 proves controlled remote platform transition writing, not CPU-free network-native computation.",
            "last_run_hash": "",
        },
        "last_run_hash",
    )
    last_run_write = put_json(owner, repo, NC14_LAST_RUN_PATH, token_value, run_summary, f"NC-14 last run {run_id}")
    ledger, ledger_write = append_ledger(owner=owner, repo=repo, token_value=token_value, run_summary=run_summary)
    result = {
        "ok": ok,
        "run_summary": run_summary,
        "last_run_write": last_run_write,
        "ledger_hash": ledger.get("ledger_hash"),
        "ledger_write": ledger_write,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ok or not last_run_write.get("ok") or not ledger_write.get("ok"):
        raise SystemExit(2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="NC-14 remote transition worker")
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--body-size", type=int, default=2048)
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.steps < 1:
        raise SystemExit("--steps must be >= 1")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
