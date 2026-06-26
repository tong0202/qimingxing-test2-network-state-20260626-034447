from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from nsl_l3_receiver_probe import (
    api_request,
    canonical_hash,
    decode_content,
    gh_token,
    now,
    put_content,
    raw_url,
    read_json,
    sha16,
    write_json,
)


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
DEFAULT_L2_INPUT = RUNS / "latest_nsl_l2_decoder_result.json"
DEFAULT_L3_INPUT = RUNS / "latest_nsl_l3_receiver_result.json"
CAPSULE_PATH = "states/nsl-l4-receiver-capsule.json"
PULSE_PATH = "states/nsl-l4-last-pulse.json"
REPORT_PATH = "states/nsl-l4-last-capsule-report.json"
USER_AGENT = "qimingxing-test2-nsl-l4-receiver-capsule/0.1"

ALLOWED_ACTIONS = {"emit_program_pulse"}
FORBIDDEN_PROGRAM_KEYS = {"code", "shell", "command", "cmd", "powershell", "python", "javascript", "eval", "exec"}


def capsule_id(run_id: str, sentence: str, receiver_name: str) -> str:
    seed = f"{run_id}|{sentence}|{receiver_name}".encode("utf-8")
    return "l4cap-" + sha16(seed)


def content_get(owner: str, repo: str, path: str, token: str) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    response = api_request(owner, repo, "GET", f"/contents/{path}?ref=main", token)
    payload, sha = decode_content(response)
    return payload, sha, response


def commit_hash_from_put(response: dict[str, Any]) -> str:
    payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
    commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
    return str(commit.get("sha") or "")


def content_sha_from_put(response: dict[str, Any]) -> str:
    payload = response.get("payload") if isinstance(response.get("payload"), dict) else {}
    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
    return str(content.get("sha") or "")


def fetch_json_url(url: str, label: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=25) as response:
            body = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
            payload = json.loads(body.decode("utf-8"))
            return {
                "ok": True,
                "label": label,
                "url": url,
                "status": getattr(response, "status", None),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "generation": payload.get("generation"),
                "state_signature": payload.get("state_signature"),
                "stage": payload.get("stage"),
                "body_sha16": sha16(body),
                "canonical_sha16": canonical_hash(payload),
                "headers": {
                    key: headers.get(key, "")
                    for key in ["cache-control", "etag", "x-cache", "x-served-by", "via", "expires", "age"]
                    if headers.get(key, "")
                },
                "payload": payload,
                "error": "",
            }
    except Exception as exc:
        return {
            "ok": False,
            "label": label,
            "url": url,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "generation": None,
            "state_signature": "",
            "stage": "",
            "body_sha16": "",
            "canonical_sha16": "",
            "headers": {},
            "payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def top_receiver(l3: dict[str, Any]) -> dict[str, Any]:
    candidates = list(l3.get("candidates") or [])
    for item in candidates:
        if item.get("name") == "github_branch_raw_main" and item.get("is_receiver_candidate"):
            return item
    return {}


def latest_l2_program(l2: dict[str, Any]) -> dict[str, Any]:
    aggregate = l2.get("aggregate") or {}
    sentences = list(aggregate.get("decoded_sentences") or [])
    decoded_sentence = sentences[0] if sentences else ""
    intent = ""
    nsl_rule = ""
    next_action = ""
    cycles = list(l2.get("decoded_cycles") or [])
    if cycles:
        program_intent = cycles[-1].get("program_intent") or {}
        intent = str(program_intent.get("intent") or "")
        nsl_rule = str(program_intent.get("nsl_rule") or "")
        next_action = str(program_intent.get("next_action") or "")
    return {
        "decoded_sentence": decoded_sentence,
        "sentence_stability": bool((aggregate.get("sentence_stability") or {}).get("stable")),
        "intent": intent,
        "nsl_rule": nsl_rule,
        "next_action": next_action,
        "release_mean_seconds": aggregate.get("release_mean_seconds"),
        "symbols": aggregate.get("symbols") or {},
    }


def build_capsule(
    run_id: str,
    generation: int,
    previous: dict[str, Any] | None,
    l2: dict[str, Any],
    l3: dict[str, Any],
    receiver: dict[str, Any],
    owner: str,
    repo: str,
) -> dict[str, Any]:
    program = latest_l2_program(l2)
    cap_id = capsule_id(run_id, program["decoded_sentence"], str(receiver.get("name") or "unknown"))
    return {
        "stage": "L4-network-receiver-program-capsule-v0",
        "schema_version": "NSL-L4-CAPSULE-0.1",
        "created_at": now(),
        "generation": generation,
        "capsule_id": cap_id,
        "previous": previous,
        "receiver": {
            "name": receiver.get("name"),
            "kind": receiver.get("kind"),
            "fixed_point_score": receiver.get("fixed_point_score"),
            "receiver_score": receiver.get("receiver_score"),
            "raw_branch_url": raw_url(owner, repo, "main", CAPSULE_PATH),
        },
        "source": {
            "l2_run_id": l2.get("run_id"),
            "l2_evidence_level": l2.get("evidence_level"),
            "l3_run_id": l3.get("run_id"),
            "l3_evidence_level": l3.get("evidence_level"),
        },
        "program": {
            "language": "NSL",
            "decoded_sentence": program["decoded_sentence"],
            "sentence_stability": program["sentence_stability"],
            "intent": program["intent"],
            "nsl_rule": program["nsl_rule"],
            "next_action": program["next_action"],
            "allowed_action": {
                "type": "emit_program_pulse",
                "pulse_path": PULSE_PATH,
                "body": {
                    "pulse": "ADVANCE_AFTER_RELEASE",
                    "meaning": "网络态句子稳定且接收器候选成立后，发出一次可审计程序脉冲。",
                },
            },
            "blocked": {
                "arbitrary_code_execution": True,
                "direct_body_execution": True,
                "shell_execution": True,
            },
        },
        "safety": {
            "allowlist": sorted(ALLOWED_ACTIONS),
            "forbidden_program_keys": sorted(FORBIDDEN_PROGRAM_KEYS),
            "executor_contract": "Executor may interpret this declarative capsule only. It must not run arbitrary code from the capsule body.",
        },
        "capsule_hash": "",
        "truth_boundary": (
            "This capsule resides on a network receiver candidate and can be read back as a declarative program. "
            "The trigger is still interpreted by local or external CPU; this is not CPU-free network computation."
        ),
    }


def seal_capsule(capsule: dict[str, Any]) -> dict[str, Any]:
    sealed = json.loads(json.dumps(capsule, ensure_ascii=False))
    sealed["capsule_hash"] = ""
    sealed["capsule_hash"] = canonical_hash(sealed)
    return sealed


def contains_forbidden_keys(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_PROGRAM_KEYS:
                found.append(str(key))
            found.extend(contains_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(contains_forbidden_keys(child))
    return sorted(set(found))


def validate_capsule(capsule: dict[str, Any]) -> dict[str, Any]:
    program = capsule.get("program") or {}
    action = (program.get("allowed_action") or {}).get("type")
    forbidden = contains_forbidden_keys(program)
    expected_hash = capsule.get("capsule_hash")
    sealed = json.loads(json.dumps(capsule, ensure_ascii=False))
    sealed["capsule_hash"] = ""
    observed_hash = canonical_hash(sealed)
    checks = {
        "schema_ok": capsule.get("schema_version") == "NSL-L4-CAPSULE-0.1",
        "intent_ok": program.get("intent") == "ADVANCE_AFTER_RELEASE",
        "sentence_stable": bool(program.get("sentence_stability")),
        "action_allowlisted": action in ALLOWED_ACTIONS,
        "no_forbidden_keys": not forbidden,
        "hash_ok": expected_hash == observed_hash,
        "receiver_candidate": capsule.get("receiver", {}).get("name") == "github_branch_raw_main",
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "forbidden_keys": forbidden,
        "expected_hash": expected_hash,
        "observed_hash": observed_hash,
    }


def wait_for_branch_capsule(
    owner: str,
    repo: str,
    capsule: dict[str, Any],
    duration: int,
    interval: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    samples = []
    target_generation = capsule.get("generation")
    target_capsule_id = capsule.get("capsule_id")
    while True:
        sample = fetch_json_url(raw_url(owner, repo, "main", CAPSULE_PATH), "l4-capsule-branch-raw")
        full_ok = bool(
            sample.get("ok")
            and sample.get("generation") == target_generation
            and sample.get("state_signature") == target_capsule_id
        )
        sample["elapsed_since_write"] = round(time.perf_counter() - started, 2)
        sample["is_target_capsule"] = full_ok
        samples.append(sample)
        if full_ok:
            return {
                "released": True,
                "release_after_seconds": sample["elapsed_since_write"],
                "samples": samples,
            }
        if time.perf_counter() - started >= duration:
            return {
                "released": False,
                "release_after_seconds": None,
                "samples": samples,
            }
        time.sleep(interval)


def execute_capsule(capsule: dict[str, Any], read_sample: dict[str, Any]) -> dict[str, Any]:
    validation = validate_capsule(capsule)
    action = ((capsule.get("program") or {}).get("allowed_action") or {}).get("type")
    if not validation["ok"] or action not in ALLOWED_ACTIONS:
        return {
            "executed": False,
            "action": action,
            "validation": validation,
            "pulse": None,
            "reason": "capsule validation failed or action not allowlisted",
        }
    pulse = {
        "stage": "L4-network-receiver-program-pulse",
        "created_at": now(),
        "capsule_id": capsule.get("capsule_id"),
        "capsule_generation": capsule.get("generation"),
        "source_capsule_path": CAPSULE_PATH,
        "trigger_source": "branch_raw_capsule_read",
        "trigger_read": {
            "ok": read_sample.get("ok"),
            "status": read_sample.get("status"),
            "elapsed_ms": read_sample.get("elapsed_ms"),
            "headers": read_sample.get("headers") or {},
            "generation": read_sample.get("generation"),
            "state_signature": read_sample.get("state_signature"),
        },
        "decoded_sentence": (capsule.get("program") or {}).get("decoded_sentence"),
        "nsl_rule": (capsule.get("program") or {}).get("nsl_rule"),
        "action": (capsule.get("program") or {}).get("allowed_action"),
        "pulse_hash": "",
        "truth_boundary": "This pulse is emitted by an allowlisted interpreter after reading a network-resident capsule. CPU still performs the interpretation and write.",
    }
    pulse["pulse_hash"] = canonical_hash({**pulse, "pulse_hash": ""})
    return {
        "executed": True,
        "action": action,
        "validation": validation,
        "pulse": pulse,
        "reason": "allowlisted capsule emitted one auditable pulse",
    }


def write_report(run_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# L4：网络接收器程序胶囊 V0",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- created_at: `{result['created_at']}`",
        f"- stage: `{result['stage']}`",
        f"- ok: `{result['ok']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        "",
        "## 本轮做了什么",
        "",
        "把 L2 解码出的网络态句子封装成一个声明式程序胶囊，写入 L3 排名第一的接收器候选路径，然后从 branch Raw/CDN 读回，并由受控解释器触发一次程序脉冲。",
        "",
        "## 胶囊",
        "",
        f"- capsule_path: `{result['capsule_path']}`",
        f"- capsule_id: `{result['capsule'].get('capsule_id')}`",
        f"- generation: `{result['capsule'].get('generation')}`",
        f"- receiver: `{result['capsule'].get('receiver', {}).get('name')}`",
        f"- decoded_sentence: `{result['capsule'].get('program', {}).get('decoded_sentence')}`",
        f"- intent: `{result['capsule'].get('program', {}).get('intent')}`",
        "",
        "## 验证",
        "",
        f"- api_write_ok: `{result['remote_writes']['capsule'].get('ok')}`",
        f"- commit_raw_verify_ok: `{result['commit_raw_verify'].get('ok')}`",
        f"- branch_raw_released: `{result['branch_raw_observation'].get('released')}`",
        f"- branch_raw_release_after_seconds: `{result['branch_raw_observation'].get('release_after_seconds')}`",
        f"- capsule_validation_ok: `{result['execution'].get('validation', {}).get('ok')}`",
        f"- pulse_executed: `{result['execution'].get('executed')}`",
        f"- pulse_write_ok: `{result['remote_writes']['pulse'].get('ok')}`",
        "",
        "## 结论",
        "",
        result["conclusion"],
        "",
        "## 真实边界",
        "",
        result["truth_boundary"],
        "",
    ]
    (run_dir / "nsl_l4_receiver_capsule_report.md").write_text("\n".join(lines), encoding="utf-8")


def publish_remote_report(owner: str, repo: str, token: str, result: dict[str, Any]) -> dict[str, Any]:
    existing, sha, _ = content_get(owner, repo, REPORT_PATH, token)
    remote = {
        "run_id": result["run_id"],
        "created_at": result["created_at"],
        "stage": result["stage"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "capsule_path": result["capsule_path"],
        "pulse_path": result["pulse_path"],
        "capsule_id": result["capsule"].get("capsule_id"),
        "receiver": result["capsule"].get("receiver"),
        "execution": {
            "executed": result["execution"].get("executed"),
            "action": result["execution"].get("action"),
            "validation_ok": result["execution"].get("validation", {}).get("ok"),
        },
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
    }
    return put_content(owner, repo, REPORT_PATH, remote, f"L4 receiver capsule report {result['run_id']}", token, sha)


def main() -> int:
    parser = argparse.ArgumentParser(description="L4 network receiver program capsule V0")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--l2-input", default=str(DEFAULT_L2_INPUT))
    parser.add_argument("--l3-input", default=str(DEFAULT_L3_INPUT))
    parser.add_argument("--wait-duration", type=int, default=360)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()

    run_id = "nsl-l4-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    l2 = read_json(Path(args.l2_input))
    l3 = read_json(Path(args.l3_input))
    receiver = top_receiver(l3)
    if not receiver:
        raise RuntimeError("L3 has no valid github_branch_raw_main receiver candidate")

    token = gh_token()
    if not token:
        raise RuntimeError("gh auth token unavailable")

    existing_capsule, capsule_sha, existing_response = content_get(args.owner, args.repo, CAPSULE_PATH, token)
    previous = None
    generation = 1
    if existing_capsule:
        previous = {
            "generation": existing_capsule.get("generation"),
            "capsule_id": existing_capsule.get("capsule_id"),
            "capsule_hash": existing_capsule.get("capsule_hash"),
        }
        generation = int(existing_capsule.get("generation") or 0) + 1

    capsule = seal_capsule(build_capsule(run_id, generation, previous, l2, l3, receiver, args.owner, args.repo))
    capsule["state_signature"] = capsule["capsule_id"]
    capsule = seal_capsule(capsule)
    capsule_body = json.dumps(capsule, ensure_ascii=False, indent=2).encode("utf-8")

    capsule_write = put_content(
        args.owner,
        args.repo,
        CAPSULE_PATH,
        capsule,
        f"L4 receiver capsule {run_id}",
        token,
        capsule_sha,
    )
    commit_hash = commit_hash_from_put(capsule_write)
    commit_sample = fetch_json_url(raw_url(args.owner, args.repo, commit_hash, CAPSULE_PATH), "l4-capsule-commit-raw") if commit_hash else {}
    commit_ok = bool(
        commit_sample.get("ok")
        and commit_sample.get("generation") == capsule.get("generation")
        and commit_sample.get("state_signature") == capsule.get("capsule_id")
    )

    branch_observation = wait_for_branch_capsule(
        args.owner,
        args.repo,
        capsule,
        max(1, args.wait_duration),
        max(1, args.interval),
    )
    read_sample = branch_observation["samples"][-1] if branch_observation.get("samples") else {}
    raw_capsule = read_sample.get("payload") if isinstance(read_sample.get("payload"), dict) else {}
    execution = execute_capsule(raw_capsule, read_sample)

    pulse_write: dict[str, Any] = {"ok": False, "status": None, "error": "pulse not executed"}
    pulse_sha = ""
    if execution.get("executed") and execution.get("pulse"):
        _, pulse_sha, _ = content_get(args.owner, args.repo, PULSE_PATH, token)
        pulse_write = put_content(
            args.owner,
            args.repo,
            PULSE_PATH,
            execution["pulse"],
            f"L4 receiver capsule pulse {run_id}",
            token,
            pulse_sha,
        )

    ok = bool(
        capsule_write.get("ok")
        and commit_ok
        and branch_observation.get("released")
        and execution.get("executed")
        and pulse_write.get("ok")
    )
    evidence_level = "L4-network-receiver-program-capsule-v0" if ok else "L4-network-receiver-program-capsule-partial"
    conclusion = (
        "L4 成立：网络态程序胶囊已写入 L3 接收器候选路径，并从 branch Raw/CDN 读回后由受控解释器触发一次可审计程序脉冲。"
        if ok
        else "L4 部分成立：胶囊或脉冲链路有环节未完全通过，需要查看报告中的失败项。"
    )
    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "L4-network-receiver-program-capsule-v0",
        "ok": ok,
        "owner": args.owner,
        "repo": args.repo,
        "capsule_path": CAPSULE_PATH,
        "pulse_path": PULSE_PATH,
        "report_path": REPORT_PATH,
        "source_l2_run_id": l2.get("run_id"),
        "source_l3_run_id": l3.get("run_id"),
        "capsule": capsule,
        "capsule_body_sha16": sha16(capsule_body),
        "remote_writes": {
            "capsule": {
                "ok": capsule_write.get("ok"),
                "status": capsule_write.get("status"),
                "error": capsule_write.get("error"),
                "commit_hash": commit_hash,
                "content_sha": content_sha_from_put(capsule_write),
                "existing_lookup_status": existing_response.get("status"),
            },
            "pulse": {
                "ok": pulse_write.get("ok"),
                "status": pulse_write.get("status"),
                "error": pulse_write.get("error"),
                "content_sha": content_sha_from_put(pulse_write),
            },
        },
        "commit_raw_verify": {
            "ok": commit_ok,
            "sample": commit_sample,
        },
        "branch_raw_observation": branch_observation,
        "execution": execution,
        "evidence_level": evidence_level,
        "conclusion": conclusion,
        "truth_boundary": (
            "L4 proves a minimal network-resident declarative capsule can be stored on the receiver candidate, read back, validated, "
            "and used to trigger an allowlisted pulse. The interpretation and writes still use local/GitHub CPU; this is not CPU-free network computation."
        ),
    }

    write_json(run_dir / "nsl_l4_receiver_capsule_result.json", result)
    write_json(RUNS / "latest_nsl_l4_receiver_capsule_result.json", result)
    write_report(run_dir, result)
    report_write = publish_remote_report(args.owner, args.repo, token, result)
    result["remote_writes"]["report"] = {
        "ok": report_write.get("ok"),
        "status": report_write.get("status"),
        "error": report_write.get("error"),
        "content_sha": content_sha_from_put(report_write),
    }
    write_json(run_dir / "nsl_l4_receiver_capsule_result.json", result)
    write_json(RUNS / "latest_nsl_l4_receiver_capsule_result.json", result)

    print(
        json.dumps(
            {
                "ok": result["ok"],
                "run_id": result["run_id"],
                "result": str(run_dir / "nsl_l4_receiver_capsule_result.json"),
                "report": str(run_dir / "nsl_l4_receiver_capsule_report.md"),
                "capsule_path": CAPSULE_PATH,
                "pulse_path": PULSE_PATH,
                "evidence_level": evidence_level,
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
