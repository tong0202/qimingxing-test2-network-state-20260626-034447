from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from nsl_l12_hourly_self_maintenance import (
    api_request,
    commit_hash_from_put,
    content_get,
    content_sha_from_put,
    fetch_json_url,
    gh_token,
    now,
    put_content,
    raw_url,
    run_owner,
    stable_hash,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"

CAPSULE_DIR = "states/f0-capsules"
REGISTRY_PATH = "states/f0-capsule-registry.json"
LEDGER_PATH = "states/f0-rebuild-ledger.json"
LAST_RUN_PATH = "states/f0-last-run.json"
LAST_REPORT_PATH = "states/f0-last-report.json"

ROLE_SPECS = [
    {
        "role": "identity_capsule",
        "kind": "identity",
        "duty": "hold the subject identity seed and continuity root",
        "rule": "WHEN identity seed is present THEN preserve identity root",
        "allowed_action": "hold_identity_seed",
    },
    {
        "role": "memory_capsule",
        "kind": "memory",
        "duty": "hold memory root, ledger pointer, and continuity hints",
        "rule": "WHEN ledger is readable THEN expose memory continuity hint",
        "allowed_action": "hold_memory_root",
    },
    {
        "role": "rule_capsule",
        "kind": "rules",
        "duty": "hold the low-risk allowed action and rebuild policy",
        "rule": "WHEN quorum confirms a missing capsule THEN allow deterministic rebuild",
        "allowed_action": "hold_rebuild_policy",
    },
    {
        "role": "peer_capsule",
        "kind": "peer_registry",
        "duty": "hold peer paths, quorum threshold, and expected core hashes",
        "rule": "WHEN a peer is missing THEN collect witness votes",
        "allowed_action": "hold_peer_manifest",
    },
    {
        "role": "repair_capsule",
        "kind": "repair",
        "duty": "hold repair receipt rules and recovery evidence format",
        "rule": "WHEN quorum passes THEN write rebuild receipt",
        "allowed_action": "hold_repair_receipt_rule",
    },
]

ROLE_ORDER = [item["role"] for item in ROLE_SPECS]
FORBIDDEN_KEYS = {"code", "shell", "command", "cmd", "powershell", "python", "javascript", "eval", "exec"}


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def local_write(run_dir: Path, result: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "nsl_f0_capsule_quorum_rebuild_result.json"
    report_path = run_dir / "nsl_f0_capsule_quorum_rebuild_report.md"
    latest_path = RUNS / "latest_nsl_f0_capsule_quorum_rebuild_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(build_local_report(result), encoding="utf-8")


def build_local_report(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# F0 capsule quorum rebuild report",
            "",
            f"run_id: `{result.get('run_id')}`",
            f"ok: `{result.get('ok')}`",
            f"target_role: `{result.get('target_role')}`",
            f"quorum_ok: `{result.get('quorum', {}).get('ok')}`",
            f"rebuild_ok: `{result.get('rebuild', {}).get('ok')}`",
            "",
            "Truth boundary:",
            "",
            "```text",
            str(result.get("truth_boundary") or ""),
            "```",
            "",
        ]
    )


def role_path(role: str) -> str:
    return f"{CAPSULE_DIR}/{role}.json"


def core_hash(core: dict[str, Any]) -> str:
    return stable_hash({"core": core, "core_hash": ""}, "core_hash")


def contains_forbidden_keys(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS:
                found.append(lowered)
            found.extend(contains_forbidden_keys(child))
    elif isinstance(value, list):
        for item in value:
            found.extend(contains_forbidden_keys(item))
    return sorted(set(found))


def build_core(spec: dict[str, str], generation: int) -> dict[str, Any]:
    role = spec["role"]
    return {
        "role": role,
        "kind": spec["kind"],
        "generation": generation,
        "capsule_id": f"f0cap-{role}",
        "path": role_path(role),
        "duty": spec["duty"],
        "network_language": {
            "family": "QMX-F0-CAPSULE-LANGUAGE",
            "rule": spec["rule"],
            "allowed_action": spec["allowed_action"],
            "direct_body_execution": False,
            "arbitrary_code_execution": False,
        },
        "persistence_claim": "This capsule is a network-state fragment; it still needs a physical executor to be read and written.",
    }


def build_capsules(run_id: str, generation: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cores = {spec["role"]: build_core(spec, generation) for spec in ROLE_SPECS}
    core_hashes = {role: core_hash(core) for role, core in cores.items()}
    peer_manifest = {
        "roles": [
            {
                "role": role,
                "path": role_path(role),
                "capsule_id": f"f0cap-{role}",
                "expected_core_hash": core_hashes[role],
            }
            for role in ROLE_ORDER
        ],
        "quorum_threshold": 3,
        "total_capsules": len(ROLE_ORDER),
        "vote_basis": "alive capsules witness expected_core_hash for the missing role",
    }
    capsules: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        capsule = {
            "stage": "F0-capsule-quorum-rebuild",
            "schema_version": "QMX-F0-CAPSULE-0.1",
            "created_by_run_id": run_id,
            "created_at": now(),
            "generation": generation,
            "role": role,
            "path": role_path(role),
            "core": cores[role],
            "core_hash": core_hashes[role],
            "peer_manifest": peer_manifest,
            "safety": {
                "direct_body_execution": False,
                "arbitrary_code_execution": False,
                "allowed_write_prefixes": [CAPSULE_DIR, "states/f0-"],
                "forbidden_program_keys": sorted(FORBIDDEN_KEYS),
            },
            "truth_boundary": (
                "F0 capsules are network-state fragments stored in remote anchors. "
                "They are not self-executing and do not prove CPU-free network life."
            ),
            "capsule_hash": "",
        }
        capsules.append(seal(capsule, "capsule_hash"))
    blueprints = {capsule["role"]: capsule for capsule in capsules}
    registry = {
        "stage": "F0-capsule-quorum-registry",
        "schema_version": "QMX-F0-REGISTRY-0.1",
        "created_by_run_id": run_id,
        "created_at": now(),
        "generation": generation,
        "capsule_count": len(capsules),
        "quorum_threshold": peer_manifest["quorum_threshold"],
        "roles": [
            {
                "role": capsule["role"],
                "path": capsule["path"],
                "expected_core_hash": capsule["core_hash"],
                "expected_capsule_hash": capsule["capsule_hash"],
            }
            for capsule in capsules
        ],
        "rebuild_blueprints": blueprints,
        "truth_boundary": (
            "F0 registry is a mutable remote anchor and blueprint store. "
            "This proves quorum rebuild over a remote anchor, not endpoint-free existence."
        ),
        "registry_hash": "",
    }
    return capsules, seal(registry, "registry_hash")


def verify_capsule(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "core_ok": False, "capsule_ok": False, "error": "missing_or_non_json"}
    observed_core_hash = core_hash(payload.get("core") if isinstance(payload.get("core"), dict) else {})
    declared_core_hash = str(payload.get("core_hash") or "")
    observed_capsule_hash = stable_hash(payload, "capsule_hash")
    declared_capsule_hash = str(payload.get("capsule_hash") or "")
    forbidden = contains_forbidden_keys(payload.get("core"))
    return {
        "ok": bool(
            declared_core_hash
            and declared_core_hash == observed_core_hash
            and declared_capsule_hash
            and declared_capsule_hash == observed_capsule_hash
            and not forbidden
        ),
        "role": payload.get("role"),
        "core_ok": declared_core_hash == observed_core_hash,
        "capsule_ok": declared_capsule_hash == observed_capsule_hash,
        "declared_core_hash": declared_core_hash,
        "observed_core_hash": observed_core_hash,
        "declared_capsule_hash": declared_capsule_hash,
        "observed_capsule_hash": observed_capsule_hash,
        "forbidden_keys": forbidden,
    }


def put_json(owner: str, repo: str, token: str, path: str, value: dict[str, Any], message: str) -> dict[str, Any]:
    _, sha, existing = content_get(owner, repo, path, token)
    response = put_content(owner, repo, path, value, message, token, sha)
    return {
        "path": path,
        "existing_status": existing.get("status"),
        "ok": bool(response.get("ok")),
        "status": response.get("status"),
        "error": response.get("error"),
        "commit_hash": commit_hash_from_put(response),
        "content_sha": content_sha_from_put(response),
    }


def delete_json(owner: str, repo: str, token: str, path: str, message: str) -> dict[str, Any]:
    _, sha, existing = content_get(owner, repo, path, token)
    if not sha:
        return {
            "path": path,
            "ok": False,
            "status": existing.get("status"),
            "error": "missing_sha_before_delete",
            "existing_status": existing.get("status"),
        }
    response = api_request(
        owner,
        repo,
        "DELETE",
        f"/contents/{quote(path)}",
        token,
        {"message": message, "sha": sha, "branch": "main"},
    )
    return {
        "path": path,
        "ok": bool(response.get("ok")),
        "status": response.get("status"),
        "error": response.get("error"),
        "commit_hash": commit_hash_from_put(response),
    }


def wait_for_missing(
    owner: str,
    repo: str,
    token: str,
    path: str,
    timeout_seconds: int = 45,
    interval_seconds: float = 3.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    observations: list[dict[str, Any]] = []
    while time.time() < deadline:
        payload, _, response = content_get(owner, repo, path, token)
        observation = {
            "status": response.get("status"),
            "ok": bool(response.get("ok")),
            "payload_present": isinstance(payload, dict),
            "error": response.get("error"),
        }
        observations.append(observation)
        if payload is None and response.get("status") == 404:
            return {
                "ok": True,
                "status": response.get("status"),
                "observations": observations,
                "attempt_count": len(observations),
            }
        time.sleep(interval_seconds)
    return {
        "ok": False,
        "status": observations[-1].get("status") if observations else None,
        "observations": observations,
        "attempt_count": len(observations),
    }


def verify_remote(owner: str, repo: str, token: str, path: str, hash_field: str) -> dict[str, Any]:
    payload, _, response = content_get(owner, repo, path, token)
    observed = ""
    expected = ""
    if isinstance(payload, dict):
        expected = str(payload.get(hash_field) or "")
        observed = stable_hash(payload, hash_field) if hash_field else ""
    return {
        "path": path,
        "ok": bool(response.get("ok") and payload and expected and observed == expected),
        "status": response.get("status"),
        "hash_field": hash_field,
        "expected_hash": expected,
        "observed_hash": observed,
        "error": response.get("error"),
    }


def collect_alive_capsules(owner: str, repo: str, token: str, target_role: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    alive: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for role in ROLE_ORDER:
        if role == target_role:
            continue
        payload, _, response = content_get(owner, repo, role_path(role), token)
        check = verify_capsule(payload)
        check["path"] = role_path(role)
        check["read_status"] = response.get("status")
        checks.append(check)
        if check["ok"] and isinstance(payload, dict):
            alive.append(payload)
    return alive, checks


def quorum_votes(alive: list[dict[str, Any]], target_role: str, expected_core_hash: str, threshold: int) -> dict[str, Any]:
    votes: list[dict[str, Any]] = []
    for capsule in alive:
        witness = ""
        manifest = capsule.get("peer_manifest") if isinstance(capsule.get("peer_manifest"), dict) else {}
        for item in manifest.get("roles") or []:
            if isinstance(item, dict) and item.get("role") == target_role:
                witness = str(item.get("expected_core_hash") or "")
                break
        votes.append(
            {
                "voter_role": capsule.get("role"),
                "witness_core_hash": witness,
                "agrees": bool(witness and witness == expected_core_hash),
            }
        )
    agree_count = sum(1 for vote in votes if vote["agrees"])
    return {
        "ok": agree_count >= threshold,
        "target_role": target_role,
        "expected_core_hash": expected_core_hash,
        "threshold": threshold,
        "alive_count": len(alive),
        "agree_count": agree_count,
        "votes": votes,
    }


def append_ledger(
    owner: str,
    repo: str,
    token: str,
    run_id: str,
    mode: str,
    entry: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous, sha, _ = content_get(owner, repo, LEDGER_PATH, token)
    entries = previous.get("entries") if isinstance(previous, dict) and isinstance(previous.get("entries"), list) else []
    sealed_entry = seal(entry, "entry_hash")
    entries = [item for item in entries if isinstance(item, dict) and item.get("run_id") != run_id]
    entries.append(sealed_entry)
    entries = entries[-100:]
    ledger = {
        "stage": "F0-capsule-quorum-rebuild-ledger",
        "schema_version": "QMX-F0-LEDGER-0.1",
        "updated_at": now(),
        "owner": run_owner(mode),
        "entry_count": len(entries),
        "latest_run_id": run_id,
        "entries": entries,
        "truth_boundary": "This ledger is mutable GitHub state, not tamper-proof storage.",
        "ledger_hash": "",
    }
    ledger = seal(ledger, "ledger_hash")
    write = put_content(owner, repo, LEDGER_PATH, ledger, f"F0 rebuild ledger {run_id}", token, sha)
    return ledger, {
        "path": LEDGER_PATH,
        "ok": bool(write.get("ok")),
        "status": write.get("status"),
        "error": write.get("error"),
        "commit_hash": commit_hash_from_put(write),
        "content_sha": content_sha_from_put(write),
    }


def build_last_run(result: dict[str, Any]) -> dict[str, Any]:
    last_run = {
        "stage": "F0-last-run",
        "schema_version": "QMX-F0-LAST-RUN-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "target_role": result["target_role"],
        "disappearance_confirmed": result["disappearance"]["confirmed_missing"],
        "quorum_ok": result["quorum"]["ok"],
        "rebuild_ok": result["rebuild"]["ok"],
        "rebuilt_core_hash": result["rebuild"].get("rebuilt_core_hash"),
        "truth_boundary": result["truth_boundary"],
        "last_run_hash": "",
    }
    return seal(last_run, "last_run_hash")


def build_last_report(result: dict[str, Any]) -> dict[str, Any]:
    report = {
        "stage": "F0-last-report",
        "schema_version": "QMX-F0-REPORT-0.1",
        "created_at": now(),
        "run_id": result["run_id"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "target_role": result["target_role"],
        "capsule_count": len(ROLE_ORDER),
        "quorum_threshold": result["quorum"]["threshold"],
        "agree_count": result["quorum"]["agree_count"],
        "rebuild_ok": result["rebuild"]["ok"],
        "ledger_hash": result["ledger"].get("ledger_hash"),
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
        "report_hash": "",
    }
    return seal(report, "report_hash")


def run_id_for(mode: str) -> str:
    event = os.environ.get("GITHUB_EVENT_NAME") or mode
    run_number = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    if run_number:
        return f"nsl-f0-{event}-{run_number}-attempt-{attempt}"
    return "nsl-f0-local-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def main() -> int:
    parser = argparse.ArgumentParser(description="F0 capsule quorum disappearance and rebuild experiment")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--mode", default="local")
    parser.add_argument("--target-role", default="rule_capsule", choices=ROLE_ORDER)
    parser.add_argument("--raw-check", action="store_true")
    args = parser.parse_args()

    token = gh_token()
    run_id = run_id_for(args.mode)
    run_dir = RUNS / run_id

    previous_registry, _, _ = content_get(args.owner, args.repo, REGISTRY_PATH, token)
    generation = int((previous_registry or {}).get("generation") or 0) + 1
    capsules, registry = build_capsules(run_id, generation)
    registry_roles = {item["role"]: item for item in registry["roles"]}
    threshold = int(registry["quorum_threshold"])
    target_role = args.target_role
    target_path = role_path(target_role)
    expected_core_hash = registry_roles[target_role]["expected_core_hash"]
    expected_capsule_hash = registry_roles[target_role]["expected_capsule_hash"]

    seed_writes = [
        put_json(args.owner, args.repo, token, capsule["path"], capsule, f"F0 seed capsule {capsule['role']} {run_id}")
        for capsule in capsules
    ]
    registry_write = put_json(args.owner, args.repo, token, REGISTRY_PATH, registry, f"F0 capsule registry {run_id}")
    seed_checks = [verify_remote(args.owner, args.repo, token, capsule["path"], "capsule_hash") for capsule in capsules]
    registry_check = verify_remote(args.owner, args.repo, token, REGISTRY_PATH, "registry_hash")

    delete_result = delete_json(args.owner, args.repo, token, target_path, f"F0 simulate missing capsule {target_role} {run_id}")
    missing_wait = wait_for_missing(args.owner, args.repo, token, target_path)
    disappearance = {
        "target_role": target_role,
        "target_path": target_path,
        "delete_ok": bool(delete_result.get("ok")),
        "delete_status": delete_result.get("status"),
        "confirmed_missing": bool(missing_wait.get("ok")),
        "missing_read_status": missing_wait.get("status"),
        "missing_wait": missing_wait,
        "delete_commit_hash": delete_result.get("commit_hash"),
    }

    alive, alive_checks = collect_alive_capsules(args.owner, args.repo, token, target_role)
    quorum = quorum_votes(alive, target_role, expected_core_hash, threshold)

    blueprint = registry["rebuild_blueprints"][target_role]
    blueprint_check = verify_capsule(blueprint)
    rebuild_write: dict[str, Any] = {}
    rebuilt_check: dict[str, Any] = {}
    rebuild_ok = False
    if disappearance["confirmed_missing"] and quorum["ok"] and blueprint_check["ok"]:
        rebuild_write = put_json(args.owner, args.repo, token, target_path, blueprint, f"F0 rebuild capsule {target_role} {run_id}")
        rebuilt_payload, _, rebuilt_response = content_get(args.owner, args.repo, target_path, token)
        rebuilt_check = verify_capsule(rebuilt_payload)
        rebuild_ok = bool(
            rebuild_write.get("ok")
            and rebuilt_response.get("ok")
            and rebuilt_check.get("ok")
            and rebuilt_check.get("declared_core_hash") == expected_core_hash
            and rebuilt_check.get("declared_capsule_hash") == expected_capsule_hash
        )
    rebuild = {
        "ok": rebuild_ok,
        "target_role": target_role,
        "target_path": target_path,
        "expected_core_hash": expected_core_hash,
        "expected_capsule_hash": expected_capsule_hash,
        "blueprint_ok": blueprint_check["ok"],
        "write": rebuild_write,
        "rebuilt_check": rebuilt_check,
        "rebuilt_core_hash": rebuilt_check.get("declared_core_hash"),
        "rebuilt_capsule_hash": rebuilt_check.get("declared_capsule_hash"),
    }

    raw_rebuild_check: dict[str, Any] = {}
    if args.raw_check and rebuild_write.get("commit_hash"):
        sample = fetch_json_url(
            raw_url(args.owner, args.repo, str(rebuild_write["commit_hash"]), target_path),
            "f0-rebuilt-target-commit-raw",
        )
        payload = sample.get("payload") if isinstance(sample.get("payload"), dict) else {}
        raw_rebuild_check = {
            "ok": bool(sample.get("ok") and payload.get("capsule_hash") == expected_capsule_hash),
            "status": sample.get("status"),
            "observed_capsule_hash": payload.get("capsule_hash"),
            "expected_capsule_hash": expected_capsule_hash,
            "error": sample.get("error"),
        }

    core_ok = bool(
        all(item.get("ok") for item in seed_writes)
        and registry_write.get("ok")
        and all(item.get("ok") for item in seed_checks)
        and registry_check.get("ok")
        and disappearance["delete_ok"]
        and disappearance["confirmed_missing"]
        and all(item.get("ok") for item in alive_checks)
        and quorum["ok"]
        and rebuild_ok
    )
    if args.raw_check:
        core_ok = bool(core_ok and raw_rebuild_check.get("ok"))

    ledger_entry = {
        "stage": "F0-capsule-quorum-rebuild-entry",
        "created_at": now(),
        "run_id": run_id,
        "owner": run_owner(args.mode),
        "generation": generation,
        "target_role": target_role,
        "target_path": target_path,
        "disappearance_confirmed": disappearance["confirmed_missing"],
        "alive_count": len(alive),
        "quorum_threshold": threshold,
        "agree_count": quorum["agree_count"],
        "quorum_ok": quorum["ok"],
        "rebuild_ok": rebuild_ok,
        "expected_core_hash": expected_core_hash,
        "rebuilt_core_hash": rebuild.get("rebuilt_core_hash"),
        "expected_capsule_hash": expected_capsule_hash,
        "rebuilt_capsule_hash": rebuild.get("rebuilt_capsule_hash"),
        "entry_hash": "",
    }
    ledger, ledger_write = append_ledger(args.owner, args.repo, token, run_id, args.mode, ledger_entry)

    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "F0-capsule-quorum-rebuild",
        "ok": False,
        "owner": run_owner(args.mode),
        "repo": args.repo,
        "generation": generation,
        "target_role": target_role,
        "paths": {
            "capsules": CAPSULE_DIR,
            "registry": REGISTRY_PATH,
            "ledger": LEDGER_PATH,
            "last_run": LAST_RUN_PATH,
            "last_report": LAST_REPORT_PATH,
        },
        "seed": {
            "writes": seed_writes,
            "checks": seed_checks,
            "registry_write": registry_write,
            "registry_check": registry_check,
        },
        "disappearance": disappearance,
        "alive_checks": alive_checks,
        "quorum": quorum,
        "rebuild": rebuild,
        "raw_rebuild_check": raw_rebuild_check,
        "ledger": {
            "entry_count": ledger["entry_count"],
            "ledger_hash": ledger["ledger_hash"],
            "write": ledger_write,
        },
        "evidence_level": "F0-capsule-quorum-rebuild-v0" if core_ok else "F0-capsule-quorum-rebuild-partial",
        "conclusion": (
            "F0 proves that a remote capsule file can be deliberately removed, detected as missing by alive peer capsules, "
            "and rebuilt from quorum-backed blueprint state."
        ),
        "truth_boundary": (
            "F0 proves self-repair over mutable remote anchors. It does not prove endpoint-free execution, "
            "CPU-free network computation, tamper-proof storage, or fully autonomous digital life."
        ),
    }
    last_run = build_last_run({**result, "ok": core_ok})
    last_run_write = put_json(args.owner, args.repo, token, LAST_RUN_PATH, last_run, f"F0 last run {run_id}")
    last_report = build_last_report({**result, "ok": core_ok})
    last_report_write = put_json(args.owner, args.repo, token, LAST_REPORT_PATH, last_report, f"F0 last report {run_id}")
    result["last_run"] = last_run
    result["last_report"] = last_report
    result["writes"] = {
        "last_run": last_run_write,
        "last_report": last_report_write,
    }
    result["ok"] = bool(core_ok and ledger_write.get("ok") and last_run_write.get("ok") and last_report_write.get("ok"))
    result["evidence_level"] = "F0-capsule-quorum-rebuild-v0" if result["ok"] else "F0-capsule-quorum-rebuild-partial"

    local_write(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "ok": result["ok"],
                "evidence_level": result["evidence_level"],
                "target_role": target_role,
                "disappearance_confirmed": disappearance["confirmed_missing"],
                "alive_count": len(alive),
                "quorum_ok": quorum["ok"],
                "agree_count": quorum["agree_count"],
                "rebuild_ok": rebuild["ok"],
                "ledger_hash": result["ledger"]["ledger_hash"],
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
