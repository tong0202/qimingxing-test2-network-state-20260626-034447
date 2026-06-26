from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nsl_l3_receiver_probe import canonical_hash, gh_token, now, put_content, raw_url, sha16, write_json
from nsl_l4_receiver_capsule import commit_hash_from_put, content_get, content_sha_from_put, fetch_json_url
from nsl_l8_multi_capsule_language import (
    ALLOWED_ACTIONS,
    INDEX_PATH,
    ROLE_ORDER,
    contains_forbidden_keys,
    put_json_file,
    stable_hash,
    validate_index,
    wait_for_branch_release,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
DEFAULT_L8_INPUT = RUNS / "latest_nsl_l8_multi_capsule_language_result.json"

SIGNAL_PREFIX = "states/nsl-l9-signals"
LOOP_STATE_PATH = "states/nsl-l9-loop-state.json"
LAST_REPORT_PATH = "states/nsl-l9-last-loop-report.json"

INITIAL_SYMBOLS = {
    "STATE_ID",
    "SHADOW",
    "RESIDUAL",
    "RELEASE",
    "RHYTHM",
    "ADVANCE_AFTER_RELEASE",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = stable_hash(sealed, field)
    return sealed


def index_hash_ok(index: dict[str, Any]) -> bool:
    return bool(index.get("network_hash") and stable_hash(index, "network_hash") == index.get("network_hash"))


def signal_path(run_id: str, step_index: int, role: str) -> str:
    return f"{SIGNAL_PREFIX}/{run_id}-step-{step_index:03d}-{role}.json"


def load_remote_index(owner: str, repo: str) -> dict[str, Any]:
    sample = fetch_json_url(raw_url(owner, repo, "main", INDEX_PATH), "l9-index-branch-raw")
    if not sample.get("ok") or not isinstance(sample.get("payload"), dict):
        raise RuntimeError(f"Unable to read L8 index from branch Raw: {sample.get('error')}")
    return {"sample": sample, "index": sample["payload"]}


def load_remote_capsules(owner: str, repo: str, index: dict[str, Any]) -> dict[str, Any]:
    capsules: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    for item in index.get("capsules") or []:
        path = str(item.get("path") or "")
        sample = fetch_json_url(raw_url(owner, repo, "main", path), f"l9-capsule-{item.get('role')}")
        samples.append(
            {
                "role": item.get("role"),
                "path": path,
                "ok": sample.get("ok"),
                "status": sample.get("status"),
                "elapsed_ms": sample.get("elapsed_ms"),
                "error": sample.get("error"),
                "headers": sample.get("headers") or {},
            }
        )
        if not sample.get("ok") or not isinstance(sample.get("payload"), dict):
            raise RuntimeError(f"Unable to read capsule {path} from branch Raw: {sample.get('error')}")
        capsules.append(sample["payload"])
    capsules.sort(key=lambda item: ROLE_ORDER.index(str(item.get("role"))) if item.get("role") in ROLE_ORDER else 999)
    return {"capsules": capsules, "samples": samples}


def route_from_edges(index: dict[str, Any]) -> list[str]:
    if not index.get("edges"):
        return []
    start = str((index.get("edges") or [{}])[0].get("from_role") or "")
    route = [start] if start else []
    for edge in index.get("edges") or []:
        target = str(edge.get("to_role") or "")
        if target:
            route.append(target)
    return route


def can_run_capsule(capsule: dict[str, Any], available: set[str], graph_validated: bool) -> dict[str, Any]:
    language = capsule.get("language") or {}
    role = str(capsule.get("role") or "")
    inputs = [str(item) for item in language.get("symbols_in") or []]
    action = str((capsule.get("allowed_action") or {}).get("type") or "")
    missing = [item for item in inputs if item not in available]
    checks = {
        "role_known": role in ROLE_ORDER,
        "capsule_hash_ok": bool(capsule.get("capsule_hash")) and stable_hash(capsule, "capsule_hash") == capsule.get("capsule_hash"),
        "action_allowlisted": action in ALLOWED_ACTIONS,
        "no_forbidden_keys": not contains_forbidden_keys(capsule),
        "inputs_available": not missing,
        "graph_validation_available": role != "behavior_pulse" or graph_validated,
    }
    return {"ok": all(checks.values()), "checks": checks, "missing_inputs": missing, "action": action}


def build_signal_record(
    run_id: str,
    step_index: int,
    capsule: dict[str, Any],
    available_before: set[str],
    available_after: set[str],
    decision: dict[str, Any],
    graph_validation: dict[str, Any],
    index: dict[str, Any],
) -> dict[str, Any]:
    language = capsule.get("language") or {}
    role = str(capsule.get("role") or "")
    outputs = [str(item) for item in language.get("signals_out") or []] if decision.get("ok") else []
    record = {
        "stage": "L9-multi-capsule-loop-signal",
        "schema_version": "NSL-L9-SIGNAL-0.1",
        "created_at": now(),
        "run_id": run_id,
        "step_index": step_index,
        "role": role,
        "capsule_id": capsule.get("capsule_id"),
        "capsule_hash": capsule.get("capsule_hash"),
        "network_id": index.get("network_id"),
        "network_hash": index.get("network_hash"),
        "inputs_required": language.get("symbols_in") or [],
        "signals_before": sorted(available_before),
        "signals_out": outputs,
        "signals_after": sorted(available_after),
        "decision": decision,
        "graph_validation_ok": bool(graph_validation.get("ok")),
        "interpreted_action": {
            "type": decision.get("action"),
            "executed": bool(decision.get("ok")),
            "effect": "emit declarative signal only; no arbitrary body execution",
        },
        "signal_hash": "",
        "truth_boundary": (
            "This signal is emitted by a controlled L9 interpreter after validating a network-resident capsule. "
            "It is not autonomous network self-execution."
        ),
    }
    return seal(record, "signal_hash")


def interpret_graph(run_id: str, index: dict[str, Any], capsules: list[dict[str, Any]], graph_validation: dict[str, Any]) -> dict[str, Any]:
    by_role = {str(capsule.get("role")): capsule for capsule in capsules}
    available = set(INITIAL_SYMBOLS)
    steps: list[dict[str, Any]] = []
    signal_records: list[dict[str, Any]] = []
    graph_ok_seen = False
    route = route_from_edges(index)

    for step_index, role in enumerate(route, start=1):
        capsule = by_role.get(role)
        if not capsule:
            steps.append({"step_index": step_index, "role": role, "ok": False, "error": "missing_capsule"})
            continue
        before = set(available)
        decision = can_run_capsule(capsule, available, graph_ok_seen)
        outputs = [str(item) for item in ((capsule.get("language") or {}).get("signals_out") or [])] if decision.get("ok") else []
        if decision.get("ok"):
            available.update(outputs)
        if role == "graph_verifier" and decision.get("ok") and graph_validation.get("ok"):
            graph_ok_seen = True
            available.add("GRAPH_VALIDATED")
        after = set(available)
        signal = build_signal_record(run_id, step_index, capsule, before, after, decision, graph_validation, index)
        signal_records.append(signal)
        steps.append(
            {
                "step_index": step_index,
                "role": role,
                "ok": bool(decision.get("ok")),
                "capsule_id": capsule.get("capsule_id"),
                "action": decision.get("action"),
                "missing_inputs": decision.get("missing_inputs"),
                "signals_out": outputs,
                "signal_hash": signal.get("signal_hash"),
            }
        )
    return {
        "ok": bool(route and all(item.get("ok") for item in steps) and "NETWORK_LANGUAGE_PULSE" in available),
        "route": route,
        "steps": steps,
        "signal_records": signal_records,
        "final_signals": sorted(available),
        "network_language_pulse": "NETWORK_LANGUAGE_PULSE" in available,
    }


def build_loop_state(
    run_id: str,
    generation: int,
    index: dict[str, Any],
    graph_validation: dict[str, Any],
    interpretation: dict[str, Any],
    previous_state: dict[str, Any] | None,
) -> dict[str, Any]:
    history = list((previous_state or {}).get("history") or [])[-30:]
    history.append(
        {
            "run_id": run_id,
            "generation": generation,
            "network_id": index.get("network_id"),
            "step_count": len(interpretation.get("steps") or []),
            "network_language_pulse": interpretation.get("network_language_pulse"),
            "created_at": now(),
        }
    )
    state = {
        "stage": "L9-multi-capsule-loop-interpreter",
        "schema_version": "NSL-L9-LOOP-STATE-0.1",
        "updated_at": now(),
        "run_id": run_id,
        "generation": generation,
        "network_id": index.get("network_id"),
        "network_hash": index.get("network_hash"),
        "state_signature": f"{index.get('network_id')}-l9-loop-{generation:03d}",
        "previous": {
            "generation": (previous_state or {}).get("generation"),
            "state_hash": (previous_state or {}).get("state_hash"),
        },
        "graph_validation": {
            "ok": graph_validation.get("ok"),
            "checks": graph_validation.get("checks"),
            "route": graph_validation.get("route"),
        },
        "interpretation": {
            "ok": interpretation.get("ok"),
            "route": interpretation.get("route"),
            "steps": interpretation.get("steps"),
            "final_signals": interpretation.get("final_signals"),
            "network_language_pulse": interpretation.get("network_language_pulse"),
        },
        "history": history,
        "state_hash": "",
        "truth_boundary": (
            "L9 records a controlled interpreter loop over the L8 multi-capsule network language graph. "
            "It does not prove self-executing network life or network-only computation."
        ),
    }
    return seal(state, "state_hash")


def write_report(run_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# L9：多胶囊闭环解释器 V0",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- generation: `{result['generation']}`",
        f"- route: `{' -> '.join(result['interpretation']['route'])}`",
        f"- step_count: `{len(result['interpretation']['steps'])}`",
        f"- network_language_pulse: `{result['interpretation']['network_language_pulse']}`",
        f"- branch_raw_release_ok: `{result['verification']['branch_raw_release'].get('ok')}`",
        "",
        "## 步骤",
        "",
        "| step | role | ok | action | signal |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for step in result["interpretation"]["steps"]:
        signals = ",".join(step.get("signals_out") or [])
        lines.append(f"| {step['step_index']} | `{step['role']}` | `{step['ok']}` | `{step['action']}` | `{signals}` |")
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
    (run_dir / "nsl_l9_multi_capsule_loop_interpreter_report.md").write_text("\n".join(lines), encoding="utf-8")


def publish_remote_report(owner: str, repo: str, token: str, result: dict[str, Any]) -> dict[str, Any]:
    remote = {
        "run_id": result["run_id"],
        "stage": result["stage"],
        "created_at": result["created_at"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "network_id": result["network_id"],
        "loop_state_path": result["loop_state_path"],
        "signal_paths": result["signal_paths"],
        "route": result["interpretation"]["route"],
        "steps": result["interpretation"]["steps"],
        "network_language_pulse": result["interpretation"]["network_language_pulse"],
        "verification": {
            "graph_validation_ok": result["verification"]["graph_validation"].get("ok"),
            "signals_write_ok": result["verification"]["signals_write_ok"],
            "loop_state_write_ok": result["verification"]["loop_state_write"].get("ok"),
            "branch_raw_release_ok": result["verification"]["branch_raw_release"].get("ok"),
        },
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
    }
    _, sha, _ = content_get(owner, repo, LAST_REPORT_PATH, token)
    return put_content(owner, repo, LAST_REPORT_PATH, remote, f"L9 multi-capsule loop interpreter report {result['run_id']}", token, sha)


def main() -> int:
    parser = argparse.ArgumentParser(description="L9 multi-capsule loop interpreter V0")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--l8", type=Path, default=DEFAULT_L8_INPUT)
    parser.add_argument("--raw-timeout", type=int, default=180)
    parser.add_argument("--raw-interval", type=float, default=6.0)
    args = parser.parse_args()

    l8_local = read_json(args.l8)
    if not l8_local.get("ok"):
        raise RuntimeError("L9 requires successful L8 result")

    run_id = "nsl-l9-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    token = gh_token()
    if not token:
        raise RuntimeError("gh auth token is required to publish L9")

    index_load = load_remote_index(args.owner, args.repo)
    index = index_load["index"]
    if not index_hash_ok(index):
        raise RuntimeError("L8 index hash validation failed")
    capsule_load = load_remote_capsules(args.owner, args.repo, index)
    capsules = capsule_load["capsules"]
    graph_validation = validate_index(index, capsules)
    interpretation = interpret_graph(run_id, index, capsules, graph_validation)

    signal_writes: list[dict[str, Any]] = []
    commit_raw_checks: list[dict[str, Any]] = []
    expected_release: list[dict[str, str]] = []
    signal_paths: list[str] = []
    for signal_index, signal in enumerate(interpretation["signal_records"]):
        path = signal_path(run_id, int(signal["step_index"]), str(signal["role"]))
        signal["path"] = path
        signal = seal(signal, "signal_hash")
        interpretation["signal_records"][signal_index] = signal
        for step in interpretation["steps"]:
            if step.get("step_index") == signal.get("step_index") and step.get("role") == signal.get("role"):
                step["signal_hash"] = signal.get("signal_hash")
                step["signal_path"] = path
        write = put_json_file(args.owner, args.repo, token, path, signal, f"L9 signal {run_id} {signal['role']}")
        signal_writes.append(write)
        signal_paths.append(path)
        commit_hash = write.get("commit_hash")
        commit_sample = fetch_json_url(raw_url(args.owner, args.repo, commit_hash, path), f"l9-signal-commit-{signal['role']}") if commit_hash else {}
        payload = commit_sample.get("payload") if isinstance(commit_sample.get("payload"), dict) else {}
        commit_raw_checks.append(
            {
                "path": path,
                "ok": bool(commit_sample.get("ok") and payload.get("signal_hash") == signal["signal_hash"]),
                "status": commit_sample.get("status"),
                "elapsed_ms": commit_sample.get("elapsed_ms"),
                "observed_hash": payload.get("signal_hash"),
                "expected_hash": signal["signal_hash"],
            }
        )
        expected_release.append({"path": path, "hash_field": "signal_hash", "hash_value": signal["signal_hash"]})

    previous_state, state_sha, _ = content_get(args.owner, args.repo, LOOP_STATE_PATH, token)
    generation = int((previous_state or {}).get("generation") or 0) + 1
    loop_state = build_loop_state(run_id, generation, index, graph_validation, interpretation, previous_state)
    loop_state_write = put_content(args.owner, args.repo, LOOP_STATE_PATH, loop_state, f"L9 loop state {run_id}", token, state_sha)
    loop_state_api, _, loop_state_api_response = content_get(args.owner, args.repo, LOOP_STATE_PATH, token)
    loop_state_api_ok = bool(
        loop_state_api_response.get("ok")
        and loop_state_api
        and loop_state_api.get("state_hash") == loop_state["state_hash"]
        and stable_hash(loop_state_api, "state_hash") == loop_state["state_hash"]
    )
    expected_release.append({"path": LOOP_STATE_PATH, "hash_field": "state_hash", "hash_value": loop_state["state_hash"]})

    branch_release = wait_for_branch_release(args.owner, args.repo, expected_release, args.raw_timeout, args.raw_interval)
    signals_write_ok = all(item.get("ok") for item in signal_writes)
    signal_commit_raw_ok = all(item.get("ok") for item in commit_raw_checks)
    ok = bool(
        graph_validation.get("ok")
        and interpretation.get("ok")
        and signals_write_ok
        and signal_commit_raw_ok
        and loop_state_write.get("ok")
        and loop_state_api_ok
        and branch_release.get("ok")
    )
    evidence_level = "L9-multi-capsule-loop-interpreter-v0" if ok else "L9-multi-capsule-loop-interpreter-partial"
    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "L9-multi-capsule-loop-interpreter-v0",
        "ok": ok,
        "owner": args.owner,
        "repo": args.repo,
        "generation": generation,
        "network_id": index.get("network_id"),
        "network_hash": index.get("network_hash"),
        "source_l8_run_id": l8_local.get("run_id"),
        "loop_state_path": LOOP_STATE_PATH,
        "last_report_path": LAST_REPORT_PATH,
        "signal_prefix": SIGNAL_PREFIX,
        "signal_paths": signal_paths,
        "index_read": {
            "ok": index_load["sample"].get("ok"),
            "status": index_load["sample"].get("status"),
            "elapsed_ms": index_load["sample"].get("elapsed_ms"),
            "network_hash_ok": index_hash_ok(index),
        },
        "capsule_reads": capsule_load["samples"],
        "graph_validation": graph_validation,
        "interpretation": interpretation,
        "loop_state": loop_state,
        "writes": {
            "signals": signal_writes,
            "loop_state": {
                "ok": loop_state_write.get("ok"),
                "status": loop_state_write.get("status"),
                "error": loop_state_write.get("error"),
                "commit_hash": commit_hash_from_put(loop_state_write),
                "content_sha": content_sha_from_put(loop_state_write),
            },
        },
        "verification": {
            "graph_validation": graph_validation,
            "signals_write_ok": signals_write_ok,
            "signal_commit_raw_checks": commit_raw_checks,
            "signal_commit_raw_ok": signal_commit_raw_ok,
            "loop_state_write": {
                "ok": loop_state_write.get("ok"),
                "api_verify_ok": loop_state_api_ok,
                "status": loop_state_write.get("status"),
                "error": loop_state_write.get("error"),
            },
            "branch_raw_release": branch_release,
        },
        "evidence_level": evidence_level,
        "conclusion": (
            "L9 成立：L8 的 6 胶囊网络语言图已被受控解释器按信号顺序推进一轮，"
            "每个胶囊产生可审计 signal，并写回 L9 loop state。"
            if ok
            else "L9 部分成立：解释器已尝试推进多胶囊图，但至少一个图校验、signal 写回、Raw 读回或 loop state 校验未通过。"
        ),
        "truth_boundary": (
            "L9 proves controlled interpretation of a network-resident multi-capsule language graph. "
            "It does not prove autonomous self-execution, CPU-free network computation, digital life, or digital supercomputing."
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

    write_json(run_dir / "nsl_l9_multi_capsule_loop_interpreter_result.json", result)
    write_json(RUNS / "latest_nsl_l9_multi_capsule_loop_interpreter_result.json", result)
    write_report(run_dir, result)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "ok": ok,
                "evidence_level": evidence_level,
                "result": str(run_dir / "nsl_l9_multi_capsule_loop_interpreter_result.json"),
                "report": str(run_dir / "nsl_l9_multi_capsule_loop_interpreter_report.md"),
                "loop_state_path": LOOP_STATE_PATH,
                "signal_count": len(signal_paths),
                "network_language_pulse": interpretation.get("network_language_pulse"),
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
