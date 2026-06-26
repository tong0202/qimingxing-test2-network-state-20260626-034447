from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RUNS.mkdir(parents=True, exist_ok=True)

DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
DEFAULT_STATE_PATH = "states/nsl-l1-symbol-state.json"
DEFAULT_L1_INPUT = RUNS / "latest_nsl_l1_symbol_result.json"
DEFAULT_L2_INPUT = RUNS / "latest_nsl_l2_decoder_result.json"
REMOTE_REPORT_PATH = "states/nsl-l3-last-receiver-report.json"
USER_AGENT = "qimingxing-test2-nsl-l3-receiver-probe/0.1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha16(payload)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_ordered(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value in (None, ""):
            continue
        if value not in result:
            result.append(value)
    return result


def stable_values(values: list[Any]) -> dict[str, Any]:
    cleaned = [value for value in values if value not in (None, "")]
    unique = unique_ordered(cleaned)
    return {"count": len(cleaned), "unique": unique, "stable": bool(cleaned) and len(unique) == 1}


def score_features(features: dict[str, bool]) -> dict[str, Any]:
    passed = [name for name, ok in features.items() if ok]
    failed = [name for name, ok in features.items() if not ok]
    total = len(features)
    return {
        "score": round(len(passed) / total, 3) if total else 0.0,
        "passed": passed,
        "failed": failed,
        "feature_count": total,
    }


def raw_url(owner: str, repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def sample_json_url(url: str, label: str) -> dict[str, Any]:
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
                "payload_excerpt": {
                    "stage": payload.get("stage"),
                    "generation": payload.get("generation"),
                    "state_signature": payload.get("state_signature"),
                },
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
            "payload_excerpt": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


def sample_raw_many(owner: str, repo: str, ref: str, path: str, label: str, count: int, interval: float) -> list[dict[str, Any]]:
    samples = []
    url = raw_url(owner, repo, ref, path)
    for index in range(count):
        item = sample_json_url(url, f"{label}-{index + 1}")
        item["index"] = index + 1
        item["sampled_at"] = now()
        samples.append(item)
        if index < count - 1 and interval > 0:
            time.sleep(interval)
    return samples


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    ok_samples = [item for item in samples if item.get("ok")]
    generations = [item.get("generation") for item in ok_samples]
    signatures = [item.get("state_signature") for item in ok_samples]
    etags = [(item.get("headers") or {}).get("etag", "") for item in ok_samples]
    x_cache = [(item.get("headers") or {}).get("x-cache", "") for item in ok_samples]
    return {
        "ok_count": len(ok_samples),
        "sample_count": len(samples),
        "generation_stability": stable_values(generations),
        "signature_stability": stable_values(signatures),
        "etag_stability": stable_values(etags),
        "x_cache_values": unique_ordered(x_cache),
        "elapsed_ms": [item.get("elapsed_ms") for item in samples],
        "errors": [item.get("error") for item in samples if item.get("error")],
    }


def gh_token() -> str:
    completed = subprocess.run(["gh", "auth", "token"], text=True, capture_output=True, timeout=30)
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def api_request(
    owner: str,
    repo: str,
    method: str,
    route: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}{route}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return {
                "ok": True,
                "status": getattr(response, "status", None),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "payload": parsed,
                "error": "",
            }
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": exc.code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "payload": raw,
            "error": f"HTTPError: {exc.code}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "payload": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def decode_content(response: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not response.get("ok") or not isinstance(response.get("payload"), dict):
        return None, ""
    payload = response["payload"]
    content = str(payload.get("content") or "")
    if not content:
        return None, str(payload.get("sha") or "")
    data = base64.b64decode("".join(content.split())).decode("utf-8")
    return json.loads(data), str(payload.get("sha") or "")


def put_content(
    owner: str,
    repo: str,
    path: str,
    value: dict[str, Any],
    message: str,
    token: str,
    sha: str = "",
) -> dict[str, Any]:
    content = base64.b64encode((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")
    payload: dict[str, Any] = {"message": message, "content": content, "branch": "main"}
    if sha:
        payload["sha"] = sha
    return api_request(owner, repo, "PUT", f"/contents/{path}", token, payload)


def l2_symbol(l2: dict[str, Any], name: str) -> dict[str, Any]:
    return ((l2.get("aggregate") or {}).get("symbols") or {}).get(name) or {}


def l2_symbol_reproduced(l2: dict[str, Any], name: str) -> bool:
    return bool(l2_symbol(l2, name).get("reproduced"))


def cycle_commit_ok(cycle: dict[str, Any]) -> bool:
    target_generation = cycle.get("target_generation")
    target_signature = str(cycle.get("target_signature") or "")
    commit = cycle.get("commit_verify") or {}
    generations = list(commit.get("generations") or [])
    signatures = [str(item) for item in commit.get("signatures") or []]
    return bool(
        commit.get("ok")
        and generations
        and all(item == target_generation for item in generations)
        and signatures
        and all(item == target_signature for item in signatures)
    )


def cycle_api_ok(cycle: dict[str, Any]) -> bool:
    target_generation = cycle.get("target_generation")
    target_signature = str(cycle.get("target_signature") or "")
    api_state = ((cycle.get("api_after_write") or {}).get("state") or {})
    return api_state.get("generation") == target_generation and str(api_state.get("state_signature") or "") == target_signature


def branch_release_times(l1: dict[str, Any]) -> list[float]:
    values = []
    for cycle in l1.get("cycles", []):
        release_after = (cycle.get("release_observation") or {}).get("release_after_seconds")
        if release_after is not None:
            values.append(round(float(release_after), 2))
    return values


def build_candidates(l1: dict[str, Any], l2: dict[str, Any], local_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    cycles = list(l1.get("cycles") or [])
    cycle_count = len(cycles)
    commit_ok_all = bool(cycles) and all(cycle_commit_ok(cycle) for cycle in cycles)
    api_ok_all = bool(cycles) and all(cycle_api_ok(cycle) for cycle in cycles)
    multi_round = cycle_count >= 2
    decoder_ok = bool((l2.get("aggregate") or {}).get("decoder_ok"))
    sentence_stable = bool(((l2.get("aggregate") or {}).get("sentence_stability") or {}).get("stable"))
    release_times = branch_release_times(l1)
    release_stable = bool(release_times) and (max(release_times) - min(release_times) <= 30)
    branch_all_symbols = all(l2_symbol_reproduced(l2, name) for name in ["STATE_ID", "SHADOW", "RESIDUAL", "RELEASE", "RHYTHM"])

    candidates: list[dict[str, Any]] = []

    branch_fixed_features = {
        "network_addressable": True,
        "state_identity": l2_symbol_reproduced(l2, "STATE_ID"),
        "stable_readback": l2_symbol_reproduced(l2, "RESIDUAL"),
        "multi_round_reproducible": multi_round,
        "can_receive_new_branch_state": True,
        "has_release_or_transition": l2_symbol_reproduced(l2, "RELEASE"),
    }
    branch_receiver_features = {
        "network_addressable": True,
        "state_identity": l2_symbol_reproduced(l2, "STATE_ID"),
        "shadow": l2_symbol_reproduced(l2, "SHADOW"),
        "residual": l2_symbol_reproduced(l2, "RESIDUAL"),
        "release": l2_symbol_reproduced(l2, "RELEASE"),
        "rhythm": l2_symbol_reproduced(l2, "RHYTHM"),
        "decoded_by_l2": decoder_ok and sentence_stable,
        "multi_round_reproducible": multi_round and branch_all_symbols,
    }
    candidates.append(
        candidate_record(
            name="github_branch_raw_main",
            kind="mutable_branch_raw_cdn_path",
            fixed_features=branch_fixed_features,
            receiver_features=branch_receiver_features,
            interpretation="当前最强接收器候选：同一分支 Raw 路径能承载旧态残影、新态释放和低频节律。",
            evidence={
                "decoded_sentence": (l2.get("aggregate") or {}).get("decoded_sentences", []),
                "release_times": release_times,
                "release_stable_within_30s": release_stable,
                "source": "L1 release observations + L2 decoder",
            },
        )
    )

    commit_fixed_features = {
        "network_addressable": True,
        "state_identity": commit_ok_all,
        "stable_readback": commit_ok_all,
        "multi_round_reproducible": multi_round,
        "can_receive_new_branch_state": False,
        "has_release_or_transition": False,
    }
    commit_receiver_features = {
        "network_addressable": True,
        "state_identity": commit_ok_all,
        "shadow": False,
        "residual": False,
        "release": False,
        "rhythm": False,
        "decoded_by_l2": False,
        "multi_round_reproducible": multi_round and commit_ok_all,
    }
    candidates.append(
        candidate_record(
            name="github_commit_raw",
            kind="immutable_commit_raw_snapshot",
            fixed_features=commit_fixed_features,
            receiver_features=commit_receiver_features,
            interpretation="强固化标本，不是接收器：它能稳定保存一个已发生状态，但不能接收后续变化，也没有释放节律。",
            evidence={
                "commit_hashes": unique_ordered([((cycle.get("write") or {}).get("commit_hash")) for cycle in cycles]),
                "commit_ok_all_cycles": commit_ok_all,
                "source": "L1 commit Raw verification",
            },
        )
    )

    api_fixed_features = {
        "network_addressable": True,
        "state_identity": api_ok_all,
        "stable_readback": api_ok_all,
        "multi_round_reproducible": multi_round,
        "can_receive_new_branch_state": True,
        "has_release_or_transition": False,
    }
    api_receiver_features = {
        "network_addressable": True,
        "state_identity": api_ok_all,
        "shadow": False,
        "residual": False,
        "release": False,
        "rhythm": False,
        "decoded_by_l2": False,
        "multi_round_reproducible": multi_round and api_ok_all,
    }
    candidates.append(
        candidate_record(
            name="github_contents_api",
            kind="latest_state_control_plane",
            fixed_features=api_fixed_features,
            receiver_features=api_receiver_features,
            interpretation="最新态控制面，不是网络态接收器：它适合确认真实写入，但缺少残影和节律。",
            evidence={"api_ok_all_cycles": api_ok_all, "source": "L1 GitHub Contents API observations"},
        )
    )

    local_ok = isinstance(local_state, dict) and bool(local_state)
    local_matches_latest = False
    if local_ok and cycles:
        last = cycles[-1]
        local_matches_latest = (
            local_state.get("generation") == last.get("target_generation")
            and str(local_state.get("state_signature") or "") == str(last.get("target_signature") or "")
        )
    local_fixed_features = {
        "network_addressable": False,
        "state_identity": local_ok,
        "stable_readback": local_ok,
        "multi_round_reproducible": False,
        "can_receive_new_branch_state": True,
        "has_release_or_transition": False,
    }
    local_receiver_features = {
        "network_addressable": False,
        "state_identity": local_ok,
        "shadow": False,
        "residual": False,
        "release": False,
        "rhythm": False,
        "decoded_by_l2": False,
        "multi_round_reproducible": False,
    }
    candidates.append(
        candidate_record(
            name="local_file_baseline",
            kind="local_storage_control",
            fixed_features=local_fixed_features,
            receiver_features=local_receiver_features,
            interpretation="本地对照组：能存状态，但不是网络点，不能作为网络固化点证据。",
            evidence={
                "local_generation": local_state.get("generation") if local_ok else None,
                "local_matches_latest_l1_target": local_matches_latest,
                "source": "local clone file",
            },
        )
    )

    return sorted(candidates, key=lambda item: (item["receiver_score"], item["fixed_point_score"]), reverse=True)


def candidate_record(
    name: str,
    kind: str,
    fixed_features: dict[str, bool],
    receiver_features: dict[str, bool],
    interpretation: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    fixed_score = score_features(fixed_features)
    receiver_score = score_features(receiver_features)
    return {
        "name": name,
        "kind": kind,
        "fixed_point_score": fixed_score["score"],
        "receiver_score": receiver_score["score"],
        "is_fixed_point_candidate": fixed_score["score"] >= 0.65,
        "is_receiver_candidate": receiver_score["score"] >= 0.75,
        "fixed_features": fixed_features,
        "fixed_feature_summary": fixed_score,
        "receiver_features": receiver_features,
        "receiver_feature_summary": receiver_score,
        "interpretation": interpretation,
        "evidence": evidence,
    }


def live_probe(owner: str, repo: str, state_path: str, l1: dict[str, Any], token: str, samples: int, interval: float) -> dict[str, Any]:
    cycles = list(l1.get("cycles") or [])
    commit_hashes = unique_ordered([((cycle.get("write") or {}).get("commit_hash")) for cycle in cycles])
    latest_commit = commit_hashes[-1] if commit_hashes else ""
    branch_samples = sample_raw_many(owner, repo, "main", state_path, "branch_raw_main", samples, interval)
    commit_samples = sample_raw_many(owner, repo, latest_commit, state_path, "commit_raw_latest_l1", max(1, min(samples, 2)), interval) if latest_commit else []

    api_response = api_request(owner, repo, "GET", f"/contents/{state_path}?ref=main", token)
    api_state, api_sha = decode_content(api_response)
    api_sample = {
        "ok": bool(api_state),
        "status": api_response.get("status"),
        "elapsed_ms": api_response.get("elapsed_ms"),
        "sha": api_sha,
        "generation": api_state.get("generation") if api_state else None,
        "state_signature": api_state.get("state_signature") if api_state else "",
        "error": api_response.get("error", ""),
    }

    local_path = ROOT / "github-repos" / repo / state_path
    local_state = None
    local_error = ""
    try:
        local_state = read_json(local_path)
    except Exception as exc:
        local_error = f"{type(exc).__name__}: {exc}"
    local_sample = {
        "ok": isinstance(local_state, dict),
        "path": str(local_path),
        "generation": local_state.get("generation") if isinstance(local_state, dict) else None,
        "state_signature": local_state.get("state_signature") if isinstance(local_state, dict) else "",
        "error": local_error,
    }

    return {
        "branch_raw_main": {"samples": branch_samples, "summary": summarize_samples(branch_samples)},
        "commit_raw_latest_l1": {"samples": commit_samples, "summary": summarize_samples(commit_samples)},
        "github_contents_api": api_sample,
        "local_file_baseline": local_sample,
    }


def load_local_state(repo: str, state_path: str) -> dict[str, Any] | None:
    path = ROOT / "github-repos" / repo / state_path
    try:
        return read_json(path)
    except Exception:
        return None


def write_report(run_dir: Path, result: dict[str, Any]) -> None:
    lines = [
        "# L3：网络固化点 / 接收器候选实验",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- created_at: `{result['created_at']}`",
        f"- stage: `{result['stage']}`",
        f"- evidence_level: `{result['evidence_level']}`",
        f"- ok: `{result['ok']}`",
        "",
        "## 本轮问题",
        "",
        "L3 不问“网络是否已经能无 CPU 计算”。L3 只问：哪些网络点只是端点，哪些网络点已经接近“可承载状态、残影、释放、节律、可解码”的接收器候选。",
        "",
        "## 排名",
        "",
        "| 候选点 | 固化分 | 接收器分 | 结论 |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in result["candidates"]:
        conclusion = "接收器候选" if item["is_receiver_candidate"] else ("固化点候选" if item["is_fixed_point_candidate"] else "对照/非候选")
        lines.append(f"| `{item['name']}` | {item['fixed_point_score']} | {item['receiver_score']} | {conclusion} |")

    lines.extend(["", "## 逐项解释", ""])
    for item in result["candidates"]:
        lines.extend(
            [
                f"### {item['name']}",
                "",
                f"- kind: `{item['kind']}`",
                f"- fixed_point_score: `{item['fixed_point_score']}`",
                f"- receiver_score: `{item['receiver_score']}`",
                f"- is_receiver_candidate: `{item['is_receiver_candidate']}`",
                f"- 解释：{item['interpretation']}",
                f"- 固化缺失项：`{item['fixed_feature_summary']['failed']}`",
                f"- 接收器缺失项：`{item['receiver_feature_summary']['failed']}`",
                "",
            ]
        )

    branch = next((item for item in result["candidates"] if item["name"] == "github_branch_raw_main"), None)
    if branch:
        lines.extend(
            [
                "## L2 解码回接",
                "",
                f"- decoded_sentence: `{branch['evidence'].get('decoded_sentence')}`",
                f"- release_times: `{branch['evidence'].get('release_times')}`",
                f"- release_stable_within_30s: `{branch['evidence'].get('release_stable_within_30s')}`",
                "",
            ]
        )

    lines.extend(["## 只读现场探测", ""])
    for name, probe in result["live_probe"].items():
        if isinstance(probe, dict) and "summary" in probe:
            summary = probe["summary"]
            lines.extend(
                [
                    f"- `{name}`: ok `{summary['ok_count']}/{summary['sample_count']}`, "
                    f"generation_stable `{summary['generation_stability']['stable']}`, "
                    f"signature_stable `{summary['signature_stability']['stable']}`, "
                    f"x_cache `{summary['x_cache_values']}`",
                ]
            )
        else:
            lines.append(
                f"- `{name}`: ok `{probe.get('ok')}`, generation `{probe.get('generation')}`, "
                f"signature `{probe.get('state_signature')}`, error `{probe.get('error')}`"
            )

    lines.extend(
        [
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
    )
    (run_dir / "nsl_l3_receiver_report.md").write_text("\n".join(lines), encoding="utf-8")


def publish_remote_report(owner: str, repo: str, result: dict[str, Any], token: str) -> dict[str, Any]:
    existing = api_request(owner, repo, "GET", f"/contents/{REMOTE_REPORT_PATH}?ref=main", token)
    _, sha = decode_content(existing)
    remote = {
        "run_id": result["run_id"],
        "created_at": result["created_at"],
        "stage": result["stage"],
        "ok": result["ok"],
        "evidence_level": result["evidence_level"],
        "top_candidate": result["top_candidate"],
        "candidates": [
            {
                "name": item["name"],
                "kind": item["kind"],
                "fixed_point_score": item["fixed_point_score"],
                "receiver_score": item["receiver_score"],
                "is_receiver_candidate": item["is_receiver_candidate"],
                "interpretation": item["interpretation"],
            }
            for item in result["candidates"]
        ],
        "conclusion": result["conclusion"],
        "truth_boundary": result["truth_boundary"],
    }
    return put_content(owner, repo, REMOTE_REPORT_PATH, remote, f"L3 receiver candidate report {result['run_id']}", token, sha)


def main() -> int:
    parser = argparse.ArgumentParser(description="L3 network fixed-point / receiver candidate probe")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--state-path", default=DEFAULT_STATE_PATH)
    parser.add_argument("--l1-input", default=str(DEFAULT_L1_INPUT))
    parser.add_argument("--l2-input", default=str(DEFAULT_L2_INPUT))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--publish-remote", action="store_true")
    args = parser.parse_args()

    run_id = "nsl-l3-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    l1 = read_json(Path(args.l1_input))
    l2 = read_json(Path(args.l2_input))
    local_state = load_local_state(args.repo, args.state_path)
    token = gh_token()
    probes = live_probe(args.owner, args.repo, args.state_path, l1, token, max(1, args.samples), max(0.0, args.interval))
    candidates = build_candidates(l1, l2, local_state)
    top_candidate = candidates[0] if candidates else {}
    ok = bool(top_candidate.get("name") == "github_branch_raw_main" and top_candidate.get("is_receiver_candidate"))

    if ok:
        evidence_level = "L3-network-receiver-candidate-ranked"
        conclusion = (
            "L3 成立：在当前样本里，GitHub branch Raw/CDN 分支路径是最强的网络态接收器候选；"
            "commit Raw 更像不可变固化标本，Contents API 更像最新态控制面，本地文件只是对照组。"
        )
    else:
        evidence_level = "L3-network-receiver-candidate-partial"
        conclusion = "L3 部分成立：已经完成候选分型，但没有候选点达到接收器阈值，需要新增样本或候选点。"

    result = {
        "run_id": run_id,
        "created_at": now(),
        "stage": "L3-network-fixed-point-receiver-candidate-experiment",
        "ok": ok,
        "owner": args.owner,
        "repo": args.repo,
        "state_path": args.state_path,
        "source_l1_run_id": l1.get("run_id"),
        "source_l2_run_id": l2.get("run_id"),
        "candidate_rule": {
            "fixed_point_candidate": "fixed_point_score >= 0.65",
            "receiver_candidate": "receiver_score >= 0.75",
            "receiver_features": [
                "network_addressable",
                "state_identity",
                "shadow",
                "residual",
                "release",
                "rhythm",
                "decoded_by_l2",
                "multi_round_reproducible",
            ],
        },
        "top_candidate": {
            "name": top_candidate.get("name"),
            "receiver_score": top_candidate.get("receiver_score"),
            "fixed_point_score": top_candidate.get("fixed_point_score"),
            "is_receiver_candidate": top_candidate.get("is_receiver_candidate"),
        },
        "candidates": candidates,
        "live_probe": probes,
        "evidence_level": evidence_level,
        "conclusion": conclusion,
        "truth_boundary": (
            "L3 identifies network-state receiver candidates from observed state identity, shadow, residual, release, rhythm, "
            "and decoder stability. It does not prove CPU-free computation, network-only execution, or a real ghost computer."
        ),
    }

    write_json(run_dir / "nsl_l3_receiver_result.json", result)
    write_json(RUNS / "latest_nsl_l3_receiver_result.json", result)
    write_report(run_dir, result)

    if args.publish_remote:
        if token:
            remote_response = publish_remote_report(args.owner, args.repo, result, token)
            result["remote_report_write"] = {
                "ok": remote_response.get("ok"),
                "status": remote_response.get("status"),
                "error": remote_response.get("error"),
            }
        else:
            result["remote_report_write"] = {"ok": False, "status": None, "error": "gh auth token unavailable"}
        write_json(run_dir / "nsl_l3_receiver_result.json", result)
        write_json(RUNS / "latest_nsl_l3_receiver_result.json", result)

    print(
        json.dumps(
            {
                "ok": result["ok"],
                "run_id": result["run_id"],
                "result": str(run_dir / "nsl_l3_receiver_result.json"),
                "report": str(run_dir / "nsl_l3_receiver_report.md"),
                "top_candidate": result["top_candidate"],
                "evidence_level": result["evidence_level"],
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
