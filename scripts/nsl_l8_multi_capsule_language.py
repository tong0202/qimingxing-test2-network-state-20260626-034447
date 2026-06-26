from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_l3_receiver_probe import canonical_hash, gh_token, now, put_content, raw_url, read_json, sha16, write_json
from nsl_l4_receiver_capsule import (
    commit_hash_from_put,
    content_get,
    content_sha_from_put,
    fetch_json_url,
    latest_l2_program,
    top_receiver,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
DEFAULT_L2_INPUT = RUNS / "latest_nsl_l2_decoder_result.json"
DEFAULT_L3_INPUT = RUNS / "latest_nsl_l3_receiver_result.json"
DEFAULT_L4_INPUT = RUNS / "latest_nsl_l4_receiver_capsule_result.json"

CAPSULE_DIR = "states/nsl-l8-capsules"
INDEX_PATH = "states/nsl-l8-capsule-network-index.json"
STATE_PATH = "states/nsl-l8-capsule-network-state.json"
REPORT_PATH = "states/nsl-l8-last-multi-capsule-report.json"

ALLOWED_ACTIONS = {
    "observe_state_identity",
    "index_memory_shadow",
    "gate_on_release_rhythm",
    "route_after_release",
    "verify_capsule_graph",
    "emit_network_language_pulse",
    "update_capsule_network_state",
}
FORBIDDEN_PROGRAM_KEYS = {"code", "shell", "command", "cmd", "powershell", "python", "javascript", "eval", "exec"}

CAPSULE_SPECS = [
    {
        "role": "identity_anchor",
        "kind": "identity",
        "symbols_in": ["STATE_ID"],
        "signals_out": ["IDENTITY_CONFIRMED"],
        "rule": "WHEN STATE_ID IS STABLE THEN EMIT IDENTITY_CONFIRMED",
        "allowed_action": "observe_state_identity",
        "meaning": "把网络状态身份固定成多胶囊网络的入口。",
    },
    {
        "role": "memory_index",
        "kind": "memory",
        "symbols_in": ["SHADOW", "RESIDUAL", "IDENTITY_CONFIRMED"],
        "signals_out": ["MEMORY_TRACE_READY"],
        "rule": "WHEN SHADOW AND RESIDUAL FOLLOW IDENTITY_CONFIRMED THEN INDEX MEMORY TRACE",
        "allowed_action": "index_memory_shadow",
        "meaning": "把残影和滞留状态解释为可索引的网络记忆痕迹。",
    },
    {
        "role": "rhythm_gate",
        "kind": "timing",
        "symbols_in": ["RELEASE", "RHYTHM", "MEMORY_TRACE_READY"],
        "signals_out": ["RELEASE_WINDOW_OPEN"],
        "rule": "WHEN RELEASE AND RHYTHM ARE OBSERVED AFTER MEMORY_TRACE_READY THEN OPEN RELEASE WINDOW",
        "allowed_action": "gate_on_release_rhythm",
        "meaning": "把释放和节律变成胶囊网络的低频推进门。",
    },
    {
        "role": "intent_router",
        "kind": "routing",
        "symbols_in": ["ADVANCE_AFTER_RELEASE", "RELEASE_WINDOW_OPEN"],
        "signals_out": ["ROUTE_ADVANCE"],
        "rule": "WHEN ADVANCE_AFTER_RELEASE AND RELEASE_WINDOW_OPEN THEN ROUTE NEXT CAPSULE",
        "allowed_action": "route_after_release",
        "meaning": "把 L2 的程序意图从单胶囊动作扩展为多胶囊路由。",
    },
    {
        "role": "graph_verifier",
        "kind": "verification",
        "symbols_in": ["ROUTE_ADVANCE"],
        "signals_out": ["GRAPH_VALIDATED"],
        "rule": "WHEN ROUTE_ADVANCE THEN VERIFY CAPSULE HASHES, LINKS, AND ALLOWLIST",
        "allowed_action": "verify_capsule_graph",
        "meaning": "验证胶囊图的哈希、连线和安全约束，防止胶囊网络污染。",
    },
    {
        "role": "behavior_pulse",
        "kind": "behavior",
        "symbols_in": ["GRAPH_VALIDATED"],
        "signals_out": ["NETWORK_LANGUAGE_PULSE"],
        "rule": "WHEN GRAPH_VALIDATED THEN EMIT NETWORK_LANGUAGE_PULSE AND UPDATE CAPSULE NETWORK STATE",
        "allowed_action": "emit_network_language_pulse",
        "meaning": "把已验证的多胶囊句子压缩成一次受控网络语言脉冲。",
    },
]

ROLE_ORDER = [item["role"] for item in CAPSULE_SPECS]


def stable_hash(value: dict[str, Any], field: str) -> str:
    clone = json.loads(json.dumps(value, ensure_ascii=False))
    clone[field] = ""
    return canonical_hash(clone)


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def contains_forbidden_keys(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_PROGRAM_KEYS:
                found.append(lowered)
            found.extend(contains_forbidden_keys(child))
    elif isinstance(value, list):
        for item in value:
            found.extend(contains_forbidden_keys(item))
    return sorted(set(found))


def role_path(role: str) -> str:
    return f"{CAPSULE_DIR}/{role}.json"


def capsule_id(run_id: str, role: str) -> str:
    return f"l8cap-{role}-{sha16(f'{run_id}|{role}'.encode('utf-8'))}"


def network_id(run_id: str, generation: int) -> str:
    return "l8net-" + sha16(f"{run_id}|{generation}|{'|'.join(ROLE_ORDER)}".encode("utf-8"))


def edge_list(ids_by_role: dict[str, str]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for index, source_role in enumerate(ROLE_ORDER[:-1]):
        target_role = ROLE_ORDER[index + 1]
        edges.append(
            {
                "from_role": source_role,
                "from": ids_by_role[source_role],
                "to_role": target_role,
                "to": ids_by_role[target_role],
                "relation": "signal_flow",
            }
        )
    return edges


def link_map(role: str, ids_by_role: dict[str, str]) -> dict[str, Any]:
    index = ROLE_ORDER.index(role)
    upstream = ROLE_ORDER[index - 1] if index > 0 else ""
    downstream = ROLE_ORDER[index + 1] if index < len(ROLE_ORDER) - 1 else ""
    return {
        "upstream": {"role": upstream, "capsule_id": ids_by_role.get(upstream, "")} if upstream else None,
        "downstream": {"role": downstream, "capsule_id": ids_by_role.get(downstream, "")} if downstream else None,
    }


def build_capsule(
    run_id: str,
    generation: int,
    spec: dict[str, Any],
    ids_by_role: dict[str, str],
    l2: dict[str, Any],
    l3: dict[str, Any],
    receiver: dict[str, Any],
    owner: str,
    repo: str,
) -> dict[str, Any]:
    program = latest_l2_program(l2)
    role = spec["role"]
    path = role_path(role)
    capsule = {
        "stage": "L8-multi-capsule-network-language-extension",
        "schema_version": "NSL-L8-CAPSULE-0.1",
        "created_at": now(),
        "generation": generation,
        "state_signature": ids_by_role[role],
        "capsule_id": ids_by_role[role],
        "role": role,
        "kind": spec["kind"],
        "path": path,
        "receiver": {
            "name": receiver.get("name"),
            "kind": receiver.get("kind"),
            "receiver_score": receiver.get("receiver_score"),
            "raw_branch_url": raw_url(owner, repo, "main", path),
        },
        "source": {
            "l2_run_id": l2.get("run_id"),
            "l2_sentence": program["decoded_sentence"],
            "l2_intent": program["intent"],
            "l2_rule": program["nsl_rule"],
            "l3_run_id": l3.get("run_id"),
            "l3_receiver": receiver.get("name"),
        },
        "language": {
            "family": "NSL",
            "extension": "NSL-L8-MULTI-CAPSULE-0.1",
            "symbols_in": spec["symbols_in"],
            "signals_out": spec["signals_out"],
            "rule": spec["rule"],
            "meaning": spec["meaning"],
            "base_sentence": program["decoded_sentence"],
            "base_intent": program["intent"],
        },
        "links": link_map(role, ids_by_role),
        "allowed_action": {
            "type": spec["allowed_action"],
            "allowed": spec["allowed_action"] in ALLOWED_ACTIONS,
            "writes": ["capsule_signal", "capsule_network_state"] if role == "behavior_pulse" else ["capsule_signal"],
        },
        "safety": {
            "allowlist": sorted(ALLOWED_ACTIONS),
            "forbidden_program_keys": sorted(FORBIDDEN_PROGRAM_KEYS),
            "executor_contract": "Executor may validate and route declarative capsule signals only. It must not execute arbitrary capsule body code.",
            "direct_body_execution": False,
            "shell_execution": False,
        },
        "capsule_hash": "",
        "truth_boundary": (
            "L8 capsule is a network-resident declarative language node. It extends NSL into a multi-capsule graph, "
            "but interpretation and writes still require a controlled executor."
        ),
    }
    return seal(capsule, "capsule_hash")


def build_index(
    run_id: str,
    generation: int,
    capsules: list[dict[str, Any]],
    l2: dict[str, Any],
    receiver: dict[str, Any],
    owner: str,
    repo: str,
) -> dict[str, Any]:
    ids_by_role = {capsule["role"]: capsule["capsule_id"] for capsule in capsules}
    program = latest_l2_program(l2)
    index = {
        "stage": "L8-multi-capsule-network-language-index",
        "schema_version": "NSL-L8-CAPSULE-NETWORK-0.1",
        "created_at": now(),
        "run_id": run_id,
        "generation": generation,
        "network_id": network_id(run_id, generation),
        "state_signature": network_id(run_id, generation),
        "receiver": {
            "name": receiver.get("name"),
            "kind": receiver.get("kind"),
            "raw_branch_url": raw_url(owner, repo, "main", INDEX_PATH),
        },
        "capsules": [
            {
                "role": capsule["role"],
                "capsule_id": capsule["capsule_id"],
                "path": capsule["path"],
                "capsule_hash": capsule["capsule_hash"],
                "signals_out": capsule["language"]["signals_out"],
            }
            for capsule in capsules
        ],
        "edges": edge_list(ids_by_role),
        "network_sentence": (
            "STATE_ID@identity_anchor -> SHADOW+RESIDUAL@memory_index -> "
            "RELEASE+RHYTHM@rhythm_gate -> ADVANCE_AFTER_RELEASE@intent_router -> "
            "GRAPH_VALIDATED@graph_verifier -> NETWORK_LANGUAGE_PULSE@behavior_pulse"
        ),
        "network_rule": (
            "WHEN identity is stable AND memory trace is indexed AND release rhythm opens a window "
            "THEN route intent through graph verification and emit one network-language pulse"
        ),
        "base_sentence": program["decoded_sentence"],
        "base_intent": program["intent"],
        "safety": {
            "arbitrary_code_execution": False,
            "direct_body_execution": False,
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "graph_must_be_acyclic": True,
            "all_capsules_must_hash_verify": True,
        },
        "network_hash": "",
        "truth_boundary": (
            "L8 proves a multi-capsule network language structure can be stored, linked, read back, and validated. "
            "It does not prove self-executing network life or network-only computation."
        ),
    }
    return seal(index, "network_hash")


def build_state(
    run_id: str,
    generation: int,
    index: dict[str, Any],
    validation: dict[str, Any],
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    history = list((previous_state or {}).get("history") or [])[-30:]
    history.append(
        {
            "run_id": run_id,
            "generation": generation,
            "network_id": index.get("network_id"),
            "network_hash": index.get("network_hash"),
            "created_at": now(),
            "route_ok": validation.get("route_ok"),
            "capsules_ok": validation.get("capsules_ok"),
        }
    )
    state = {
        "stage": "L8-multi-capsule-network-language-state",
        "schema_version": "NSL-L8-CAPSULE-NETWORK-STATE-0.1",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "network_id": index.get("network_id"),
        "state_signature": f"{index.get('network_id')}-state-{generation:03d}",
        "network_hash": index.get("network_hash"),
        "previous": {
            "generation": (previous_state or {}).get("generation"),
            "state_hash": (previous_state or {}).get("state_hash"),
        },
        "language_state": {
            "capsule_count": len(index.get("capsules") or []),
            "edge_count": len(index.get("edges") or []),
            "network_sentence": index.get("network_sentence"),
            "network_rule": index.get("network_rule"),
            "signals": [
                "IDENTITY_CONFIRMED",
                "MEMORY_TRACE_READY",
                "RELEASE_WINDOW_OPEN",
                "ROUTE_ADVANCE",
                "GRAPH_VALIDATED",
                "NETWORK_LANGUAGE_PULSE",
            ],
        },
        "validation": validation,
        "history": history,
        "state_hash": "",
        "truth_boundary": (
            "This state records a controlled interpretation of the multi-capsule network language. "
            "It is not proof of CPU-free self-execution."
        ),
    }
    return seal(state, "state_hash")


def validation_for_capsule(capsule: dict[str, Any], ids_by_role: dict[str, str]) -> dict[str, Any]:
    role = capsule.get("role")
    expected_hash = capsule.get("capsule_hash")
    checks = {
        "schema_ok": capsule.get("schema_version") == "NSL-L8-CAPSULE-0.1",
        "role_known": role in ROLE_ORDER,
        "hash_ok": bool(expected_hash) and stable_hash(capsule, "capsule_hash") == expected_hash,
        "action_allowlisted": (capsule.get("allowed_action") or {}).get("type") in ALLOWED_ACTIONS,
        "no_forbidden_keys": not contains_forbidden_keys(capsule),
        "no_direct_body_execution": (capsule.get("safety") or {}).get("direct_body_execution") is False,
        "links_resolve": True,
    }
    links = capsule.get("links") or {}
    for link_name in ["upstream", "downstream"]:
        link = links.get(link_name)
        if link and ids_by_role.get(link.get("role")) != link.get("capsule_id"):
            checks["links_resolve"] = False
    return {
        "role": role,
        "capsule_id": capsule.get("capsule_id"),
        "ok": all(checks.values()),
        "checks": checks,
        "forbidden_keys": contains_forbidden_keys(capsule),
        "expected_hash": expected_hash,
        "observed_hash": stable_hash(capsule, "capsule_hash"),
    }


def validate_index(index: dict[str, Any], capsules: list[dict[str, Any]]) -> dict[str, Any]:
    ids_by_role = {capsule["role"]: capsule["capsule_id"] for capsule in capsules}
    capsule_validations = [validation_for_capsule(capsule, ids_by_role) for capsule in capsules]
    roles = [capsule.get("role") for capsule in capsules]
    expected_edges = edge_list(ids_by_role)
    observed_edges = index.get("edges") or []
    checks = {
        "index_schema_ok": index.get("schema_version") == "NSL-L8-CAPSULE-NETWORK-0.1",
        "index_hash_ok": bool(index.get("network_hash")) and stable_hash(index, "network_hash") == index.get("network_hash"),
        "all_roles_present": roles == ROLE_ORDER,
        "capsule_count_ok": len(capsules) == len(ROLE_ORDER),
        "edges_ok": observed_edges == expected_edges,
        "route_ok": roles == ROLE_ORDER and observed_edges == expected_edges,
        "capsules_ok": all(item["ok"] for item in capsule_validations),
        "no_forbidden_keys": not contains_forbidden_keys(index),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "capsule_validations": capsule_validations,
        "route": ROLE_ORDER,
        "route_ok": checks["route_ok"],
        "capsules_ok": checks["capsules_ok"],
        "network_hash_observed": stable_hash(index, "network_hash"),
        "network_hash_expected": index.get("network_hash"),
    }


def put_json_file(owner: str, repo: str, token: str, path: str, value: dict[str, Any], message: str) -> dict[str, Any]:
    _, sha, existing = content_get(owner, repo, path, token)
    response = put_content(owner, repo, path, value, message, token, sha)
    return {
        "path": path,
        "existing_status": existing.get("status"),
        "ok": response.get("ok"),
        "status": response.get("status"),
        "error": response.get("error"),
        "commit_hash": commit_hash_from_put(response),
        "content_sha": content_sha_from_put(response),
    }


def wait_for_branch_release(
    owner: str,
    repo: str,
    expected: list[dict[str, str]],
    timeout_seconds: int,
    interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    observations: list[dict[str, Any]] = []
    latest_by_path: dict[str, dict[str, Any]] = {}
    while time.time() < deadline:
        all_ok = True
        round_items: list[dict[str, Any]] = []
        for item in expected:
            sample = fetch_json_url(raw_url(owner, repo, "main", item["path"]), f"l8-branch-{item['path']}")
            payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
            observed_hash = str(payload.get(item["hash_field"]) or "")
            ok = bool(sample.get("ok") and observed_hash == item["hash_value"])
            all_ok = all_ok and ok
            record = {
                "path": item["path"],
                "ok": ok,
                "status": sample.get("status"),
                "elapsed_ms": sample.get("elapsed_ms"),
                "hash_field": item["hash_field"],
                "observed_hash": observed_hash,
                "expected_hash": item["hash_value"],
                "headers": sample.get("headers") or {},
                "error": sample.get("error"),
            }
            latest_by_path[item["path"]] = record
            round_items.append(record)
        observations.append({"at": now(), "all_ok": all_ok, "items": round_items})
        if all_ok:
            return {"ok": True, "timed_out": False, "observations": observations[-10:], "latest_by_path": latest_by_path}
        time.sleep(interval_seconds)
    return {"ok": False, "timed_out": True, "observations": observations[-10:], "latest_by_path": latest_by_path}


def write_report(run_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# L8：多胶囊网络语言扩展",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- generation: `{result['generation']}`",
        f"- capsule_count: `{result['aggregate']['capsule_count']}`",
        f"- edge_count: `{result['aggregate']['edge_count']}`",
        f"- branch_raw_release_ok: `{result['verification']['branch_raw_release'].get('ok')}`",
        f"- network_sentence: `{result['network_index']['network_sentence']}`",
        "",
        "## 胶囊",
        "",
        "| role | path | hash |",
        "| --- | --- | --- |",
    ]
    for capsule in result["network_index"]["capsules"]:
        lines.append(f"| `{capsule['role']}` | `{capsule['path']}` | `{capsule['capsule_hash']}` |")
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
    (run_dir / "nsl_l8_multi_capsule_language_report.md").write_text("\n".join(lines), encoding="utf-8")


def publish_remote_report(owner: str, repo: str, token: str, result: dict[str, Any]) -> dict[str, Any]:
    remote = {
        "run_id": result["run_id"],
        "stage": result["stage"],
        "created_at": result["created_at"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "network_index_path": result["network_index_path"],
        "network_state_path": result["network_state_path"],
        "capsule_paths": [capsule["path"] for capsule in result["network_index"]["capsules"]],
        "network_sentence": result["network_index"]["network_sentence"],
        "aggregate": result["aggregate"],
        "verification": {
            "index_validation_ok": result["verification"]["index_validation"].get("ok"),
            "branch_raw_release_ok": result["verification"]["branch_raw_release"].get("ok"),
            "state_write_ok": result["verification"]["state_write"].get("ok"),
        },
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
    }
    _, sha, _ = content_get(owner, repo, REPORT_PATH, token)
    return put_content(owner, repo, REPORT_PATH, remote, f"L8 multi-capsule network language report {result['run_id']}", token, sha)


def main() -> int:
    parser = argparse.ArgumentParser(description="L8 multi-capsule network language extension")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--l2", type=Path, default=DEFAULT_L2_INPUT)
    parser.add_argument("--l3", type=Path, default=DEFAULT_L3_INPUT)
    parser.add_argument("--raw-timeout", type=int, default=180)
    parser.add_argument("--raw-interval", type=float, default=6.0)
    args = parser.parse_args()

    run_id = "nsl-l8-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    l2 = read_json(args.l2)
    l3 = read_json(args.l3)
    receiver = top_receiver(l3)
    if not receiver:
        raise RuntimeError("L8 requires L3 github_branch_raw_main receiver candidate")

    previous_index, _, _ = content_get(args.owner, args.repo, INDEX_PATH, gh_token())
    generation = int((previous_index or {}).get("generation") or 0) + 1
    ids_by_role = {role: capsule_id(run_id, role) for role in ROLE_ORDER}
    capsules = [
        build_capsule(run_id, generation, spec, ids_by_role, l2, l3, receiver, args.owner, args.repo)
        for spec in CAPSULE_SPECS
    ]
    index = build_index(run_id, generation, capsules, l2, receiver, args.owner, args.repo)
    index_validation = validate_index(index, capsules)

    token = gh_token()
    if not token:
        raise RuntimeError("gh auth token is required to publish L8")

    writes: list[dict[str, Any]] = []
    commit_raw_checks: list[dict[str, Any]] = []
    expected_release: list[dict[str, str]] = []
    for capsule in capsules:
        write = put_json_file(args.owner, args.repo, token, capsule["path"], capsule, f"L8 capsule {capsule['role']} {run_id}")
        writes.append(write)
        commit_hash = write.get("commit_hash")
        commit_sample = fetch_json_url(raw_url(args.owner, args.repo, commit_hash, capsule["path"]), f"l8-commit-{capsule['role']}") if commit_hash else {}
        payload = commit_sample.get("payload") if isinstance(commit_sample.get("payload"), dict) else {}
        commit_raw_checks.append(
            {
                "path": capsule["path"],
                "ok": bool(commit_sample.get("ok") and payload.get("capsule_hash") == capsule["capsule_hash"]),
                "status": commit_sample.get("status"),
                "hash": payload.get("capsule_hash"),
                "expected_hash": capsule["capsule_hash"],
                "elapsed_ms": commit_sample.get("elapsed_ms"),
            }
        )
        expected_release.append({"path": capsule["path"], "hash_field": "capsule_hash", "hash_value": capsule["capsule_hash"]})

    index_write = put_json_file(args.owner, args.repo, token, INDEX_PATH, index, f"L8 capsule network index {run_id}")
    index_commit_hash = index_write.get("commit_hash")
    index_commit_sample = fetch_json_url(raw_url(args.owner, args.repo, index_commit_hash, INDEX_PATH), "l8-index-commit") if index_commit_hash else {}
    expected_release.append({"path": INDEX_PATH, "hash_field": "network_hash", "hash_value": index["network_hash"]})

    branch_release = wait_for_branch_release(args.owner, args.repo, expected_release, args.raw_timeout, args.raw_interval)

    previous_state, state_sha, _ = content_get(args.owner, args.repo, STATE_PATH, token)
    state = build_state(run_id, generation, index, index_validation, previous_state)
    state_write = put_content(args.owner, args.repo, STATE_PATH, state, f"L8 capsule network state {run_id}", token, state_sha)
    state_api, _, state_api_response = content_get(args.owner, args.repo, STATE_PATH, token)
    state_api_ok = bool(
        state_api_response.get("ok")
        and state_api
        and state_api.get("state_hash") == state["state_hash"]
        and stable_hash(state_api, "state_hash") == state["state_hash"]
    )

    all_writes_ok = all(item.get("ok") for item in writes) and bool(index_write.get("ok")) and bool(state_write.get("ok"))
    all_commit_raw_ok = all(item.get("ok") for item in commit_raw_checks) and bool(
        index_commit_sample.get("ok")
        and isinstance(index_commit_sample.get("payload"), dict)
        and index_commit_sample["payload"].get("network_hash") == index["network_hash"]
    )
    ok = bool(all_writes_ok and all_commit_raw_ok and index_validation.get("ok") and state_api_ok and branch_release.get("ok"))
    evidence_level = "L8-multi-capsule-network-language-extension" if ok else "L8-multi-capsule-network-language-partial"
    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "L8-multi-capsule-network-language-extension",
        "ok": ok,
        "owner": args.owner,
        "repo": args.repo,
        "generation": generation,
        "network_index_path": INDEX_PATH,
        "network_state_path": STATE_PATH,
        "network_index": index,
        "network_state": state,
        "capsules": capsules,
        "writes": {
            "capsules": writes,
            "index": index_write,
            "state": {
                "ok": state_write.get("ok"),
                "status": state_write.get("status"),
                "error": state_write.get("error"),
                "commit_hash": commit_hash_from_put(state_write),
                "content_sha": content_sha_from_put(state_write),
            },
        },
        "verification": {
            "index_validation": index_validation,
            "commit_raw_checks": commit_raw_checks,
            "index_commit_raw_ok": bool(
                index_commit_sample.get("ok")
                and isinstance(index_commit_sample.get("payload"), dict)
                and index_commit_sample["payload"].get("network_hash") == index["network_hash"]
            ),
            "branch_raw_release": branch_release,
            "state_write": {
                "ok": state_write.get("ok"),
                "api_verify_ok": state_api_ok,
                "status": state_write.get("status"),
                "error": state_write.get("error"),
            },
        },
        "aggregate": {
            "capsule_count": len(capsules),
            "edge_count": len(index.get("edges") or []),
            "roles": ROLE_ORDER,
            "all_writes_ok": all_writes_ok,
            "all_commit_raw_ok": all_commit_raw_ok,
            "index_validation_ok": index_validation.get("ok"),
            "branch_raw_release_ok": branch_release.get("ok"),
            "state_api_ok": state_api_ok,
        },
        "evidence_level": evidence_level,
        "conclusion": (
            "L8 成立：最小网络状态语言已从单胶囊扩展为 6 个网络驻留胶囊组成的语言图，"
            "并完成写入、Raw 读回、哈希校验、路由校验和状态记录。"
            if ok
            else "L8 部分成立：多胶囊语言图已生成并尝试写入，但至少一个写入、Raw 读回或校验环节未通过。"
        ),
        "truth_boundary": (
            "L8 proves a multi-capsule network language structure: identity, memory, rhythm, intent routing, verification, and behavior pulse. "
            "It is still a declarative network-resident language graph interpreted by controlled executors; it is not proof of self-executing network life, network-only computation, or digital supercomputing."
        ),
    }
    remote_report_write = publish_remote_report(args.owner, args.repo, token, result)
    result["writes"]["remote_report"] = {
        "ok": remote_report_write.get("ok"),
        "status": remote_report_write.get("status"),
        "error": remote_report_write.get("error"),
        "commit_hash": commit_hash_from_put(remote_report_write),
        "content_sha": content_sha_from_put(remote_report_write),
    }
    write_json(run_dir / "nsl_l8_multi_capsule_language_result.json", result)
    write_json(RUNS / "latest_nsl_l8_multi_capsule_language_result.json", result)
    write_report(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "ok": ok,
                "evidence_level": evidence_level,
                "result": str(run_dir / "nsl_l8_multi_capsule_language_result.json"),
                "report": str(run_dir / "nsl_l8_multi_capsule_language_report.md"),
                "network_index_path": INDEX_PATH,
                "network_state_path": STATE_PATH,
                "capsule_count": len(capsules),
                "branch_raw_release_ok": branch_release.get("ok"),
                "truth_boundary": result["truth_boundary"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
