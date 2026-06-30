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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(obj: Any) -> str:
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def encode_json(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def parse_vector(value: str) -> list[int]:
    cleaned = value.strip().replace(",", "").replace(" ", "")
    if not cleaned:
        raise ValueError("empty vector")
    bits = [int(char) for char in cleaned]
    if any(bit not in (0, 1) for bit in bits):
        raise ValueError(f"vector must contain only 0/1: {value}")
    return bits


def vector_to_str(bits: list[int]) -> str:
    return "".join(str(bit) for bit in bits)


def github_request(method: str, path: str, token_value: str, payload: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
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
            "User-Agent": "qimingxing-root12-audited-vector-writer",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8")) if raw else {}


def put_json(owner: str, repo: str, path: str, token_value: str, obj: dict[str, Any], message: str, branch: str) -> dict[str, Any]:
    quoted = urllib.parse.quote(path, safe="/")
    previous_sha = ""
    try:
        current = github_request("GET", f"repos/{owner}/{repo}/contents/{quoted}?ref={branch}", token_value)
        previous_sha = str(current.get("sha") or "")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(encode_json(obj)).decode("ascii"),
        "branch": branch,
    }
    if previous_sha:
        payload["sha"] = previous_sha
    written = github_request("PUT", f"repos/{owner}/{repo}/contents/{quoted}", token_value, payload)
    body_bytes = encode_json(obj)
    return {
        "ok": True,
        "path": path,
        "previous_sha": previous_sha,
        "sha": written.get("content", {}).get("sha"),
        "body_hash": sha16(body_bytes),
        "anchor_hash": obj.get("anchor_hash"),
    }


def make_target_anchor(
    *,
    run_id: str,
    lane: str,
    gate_id: str,
    index: int,
    bit: int,
    initial_vector: str,
    target_vector: str,
) -> dict[str, Any]:
    anchor = {
        "stage": "ROOT-12-audited-writer-vector-anchor",
        "schema_version": "QMX-ROOT-12-ANCHOR-0.1",
        "run_id": run_id,
        "lane": lane,
        "gate_id": gate_id,
        "anchor_id": gate_id,
        "vector_index": index,
        "bit": bit,
        "phase": "target_remote_writer",
        "state_seq": 1,
        "state": f"root12_remote_writer_bit_{bit}",
        "initial_vector": initial_vector,
        "target_vector": target_vector,
        "created_at": now_iso(),
        "payload": f"root12:{run_id}:{lane}:{gate_id}:{index}:target:{bit}:" + ("w" * 256),
        "transition_source": "explicit_audited_github_actions_remote_writer",
        "writer_kind": "endpoint_execution",
        "writer_identity": {
            "platform": "github_actions",
            "github_repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "github_workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "github_actor": os.environ.get("GITHUB_ACTOR", ""),
            "github_event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        },
        "truth_boundary": (
            "This anchor was written by an explicit GitHub Actions endpoint writer. "
            "It is not evidence of endpoint-free or network-native execution."
        ),
        "anchor_hash": "",
    }
    anchor["anchor_hash"] = canonical_hash({k: v for k, v in anchor.items() if k != "anchor_hash"})
    return anchor


def run(args: argparse.Namespace) -> dict[str, Any]:
    token_value = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token_value:
        raise RuntimeError("GITHUB_TOKEN is required")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    owner, repo = repository.split("/", 1) if "/" in repository else (args.owner, args.repo)
    initial = parse_vector(args.initial_vector)
    target = parse_vector(args.target_vector)
    if len(initial) != len(target):
        raise ValueError("initial and target vectors must have same length")
    gate_paths = json.loads(args.gate_paths_json)
    if not isinstance(gate_paths, dict):
        raise ValueError("gate_paths_json must be an object")

    writes: list[dict[str, Any]] = []
    skipped_unchanged: list[dict[str, Any]] = []
    changed_gate_ids: list[str] = []
    for index, bit in enumerate(target):
        gate_id = f"gate-{index:02d}"
        path = str(gate_paths[gate_id])
        if initial[index] == target[index]:
            skipped_unchanged.append({"gate_id": gate_id, "path": path, "bit": bit, "reason": "bit_unchanged_no_remote_write"})
            continue
        changed_gate_ids.append(gate_id)
        anchor = make_target_anchor(
            run_id=args.run_id,
            lane=args.lane,
            gate_id=gate_id,
            index=index,
            bit=bit,
            initial_vector=vector_to_str(initial),
            target_vector=vector_to_str(target),
        )
        write = put_json(
            owner,
            repo,
            path,
            token_value,
            anchor,
            f"ROOT-12 audited writer {args.run_id} {gate_id}",
            args.branch,
        )
        write["gate_id"] = gate_id
        write["bit"] = bit
        writes.append(write)
        time.sleep(0.2)

    audit = {
        "stage": "ROOT-12-audited-vector-writer",
        "schema_version": "QMX-ROOT-12-WRITER-AUDIT-0.1",
        "created_at": now_iso(),
        "run_id": args.run_id,
        "lane": args.lane,
        "initial_vector": vector_to_str(initial),
        "target_vector": vector_to_str(target),
        "changed_gate_ids": changed_gate_ids,
        "writer_kind": "endpoint_execution",
        "transition_source": "explicit_audited_github_actions_remote_writer",
        "github_identity": {
            "github_repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "github_workflow": os.environ.get("GITHUB_WORKFLOW", ""),
            "github_actor": os.environ.get("GITHUB_ACTOR", ""),
            "github_event_name": os.environ.get("GITHUB_EVENT_NAME", ""),
        },
        "local_manual_write_after_dispatch": False,
        "no_network_native_claim": True,
        "truth_boundary": (
            "A successful ROOT-12 writer lane proves audited endpoint execution can mutate "
            "the vector. It must not be interpreted as network-native or CPU-free execution."
        ),
        "writes": writes,
        "skipped_unchanged_gates": skipped_unchanged,
        "audit_hash": "",
    }
    audit["audit_hash"] = canonical_hash({k: v for k, v in audit.items() if k != "audit_hash"})
    audit_write = put_json(owner, repo, args.audit_path, token_value, audit, f"ROOT-12 writer audit {args.run_id}", args.branch)
    return {"ok": True, "audit": audit, "audit_write": audit_write}


def main() -> int:
    parser = argparse.ArgumentParser(description="ROOT-12 audited vector writer")
    parser.add_argument("--owner", default="")
    parser.add_argument("--repo", default="")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--run-id", default=os.environ.get("EVENT_RUN_ID", ""))
    parser.add_argument("--lane", default=os.environ.get("EVENT_LANE", "writer"))
    parser.add_argument("--initial-vector", default=os.environ.get("EVENT_INITIAL_VECTOR", "01010"))
    parser.add_argument("--target-vector", default=os.environ.get("EVENT_TARGET_VECTOR", "11001"))
    parser.add_argument("--gate-paths-json", default=os.environ.get("EVENT_GATE_PATHS_JSON", "{}"))
    parser.add_argument("--audit-path", default=os.environ.get("EVENT_AUDIT_PATH", "states/root-12/writer-audit.json"))
    args = parser.parse_args()
    if not args.run_id:
        raise RuntimeError("run_id is required")
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
