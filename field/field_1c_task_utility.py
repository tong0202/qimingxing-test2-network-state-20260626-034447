from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (Path(__file__).resolve().parent, ROOT, SCRIPTS):
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)

from field_1b_stronger_metrics import bits_from_sample, sample_target  # noqa: E402


DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
REMOTE_LAST_RUN_PATH = "states/field-1c-last-run.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def seal(value: dict[str, Any], field: str) -> dict[str, Any]:
    sealed = json.loads(json.dumps(value, ensure_ascii=False))
    sealed[field] = ""
    sealed[field] = canonical_hash(sealed)
    return sealed


def target_reward(sample: dict[str, Any], median_latency_ms: float) -> float:
    status = int(sample.get("status") or 0)
    elapsed = float(sample.get("elapsed_ms") or 9999.0)
    error = str(sample.get("error") or "")
    body_hash = str(sample.get("body_hash") or "")
    ok = status == 200 and not error
    status_score = 2.0 if ok else -2.0
    latency_score = max(-1.0, min(1.0, (median_latency_ms - elapsed) / max(1.0, median_latency_ms)))
    metadata_score = 0.0
    for key in ["etag_present", "last_modified_present", "date_present", "server_present", "cache_control_present"]:
        if sample.get(key):
            metadata_score += 0.08
    hash_score = (int(hashlib.sha256(body_hash.encode("utf-8")).hexdigest()[:2], 16) % 7) / 100.0 if body_hash else 0.0
    return round(status_score + latency_score + metadata_score + hash_score, 6)


def signal_choice(samples: list[dict[str, Any]], stream_name: str, target_count: int) -> dict[str, Any]:
    bits = [int(sample["bits"][stream_name]) for sample in samples]
    if not bits:
        return {"index": 0, "bits": [], "score": 0, "reason": "empty signal"}
    bit_text = "".join(str(bit) for bit in bits)
    latency_rank = sorted(range(len(samples)), key=lambda idx: float(samples[idx].get("elapsed_ms") or 9999.0))
    base = int(hashlib.sha256(bit_text.encode("utf-8")).hexdigest()[:8], 16)
    if stream_name == "latency":
        index = latency_rank[base % len(latency_rank)] % target_count
    else:
        index = base % target_count
    return {"index": index, "bits": bits, "score": base, "reason": f"{stream_name} field bits mapped to next target"}


def prng_choices(decision_count: int, target_count: int, trials: int, seed: int) -> list[list[int]]:
    return [[random.Random(seed + trial * 9973).randrange(target_count) for _ in range(decision_count)] for trial in range(trials)]


def score_choices(choices: list[int], future_rewards: list[list[float]]) -> float:
    total = 0.0
    for index, choice in enumerate(choices):
        rewards = future_rewards[index]
        total += rewards[choice % len(rewards)]
    return round(total, 6)


def evaluate_batch(batch_index: int, targets: list[dict[str, Any]], rounds: int, timeout: float, prng_trials: int) -> dict[str, Any]:
    round_samples: list[list[dict[str, Any]]] = []
    target_count = len(targets)
    for round_index in range(1, rounds + 1):
        samples: list[dict[str, Any]] = []
        for target in targets:
            sample = sample_target(str(target["name"]), str(target["url"]), timeout)
            sample["batch"] = batch_index
            sample["round"] = round_index
            sample["bits"] = bits_from_sample(sample)
            samples.append(sample)
        round_samples.append(samples)

    all_latencies = [float(sample.get("elapsed_ms") or 9999.0) for samples in round_samples for sample in samples]
    sorted_latencies = sorted(all_latencies)
    median_latency = sorted_latencies[len(sorted_latencies) // 2] if sorted_latencies else 1000.0
    rewards_by_round = [[target_reward(sample, median_latency) for sample in samples] for samples in round_samples]

    decisions: list[dict[str, Any]] = []
    policy_choices = {"latency": [], "non_latency": [], "mixed": [], "fixed_first": [], "fixed_cycle": []}
    future_rewards: list[list[float]] = []
    for index in range(0, max(0, len(round_samples) - 1)):
        current_samples = round_samples[index]
        future = rewards_by_round[index + 1]
        future_rewards.append(future)
        choices = {
            "latency": signal_choice(current_samples, "latency", target_count),
            "non_latency": signal_choice(current_samples, "non_latency", target_count),
            "mixed": signal_choice(current_samples, "mixed", target_count),
            "fixed_first": {"index": 0, "reason": "fixed first target"},
            "fixed_cycle": {"index": index % target_count, "reason": "fixed cycle target"},
        }
        for name in policy_choices:
            policy_choices[name].append(int(choices[name]["index"]))
        decisions.append(
            {
                "decision_index": index + 1,
                "source_round": index + 1,
                "scored_round": index + 2,
                "choices": choices,
                "future_rewards": future,
            }
        )

    policy_scores = {name: score_choices(choices, future_rewards) for name, choices in policy_choices.items()}
    prng = prng_choices(len(future_rewards), target_count, prng_trials, 20260629 + batch_index)
    prng_scores = [score_choices(choices, future_rewards) for choices in prng]
    prng_mean = round(sum(prng_scores) / max(1, len(prng_scores)), 6)
    prng_sorted = sorted(prng_scores)
    prng_median = prng_sorted[len(prng_sorted) // 2] if prng_sorted else 0.0
    oracle_next_best = round(sum(max(rewards) for rewards in future_rewards), 6)
    fixed_best = max(policy_scores.get("fixed_first", 0.0), policy_scores.get("fixed_cycle", 0.0))
    wins = {
        name: {
            "beats_fixed_best": score > fixed_best,
            "beats_prng_mean": score > prng_mean,
            "beats_prng_median": score > prng_median,
        }
        for name, score in policy_scores.items()
        if name in {"latency", "non_latency", "mixed"}
    }
    return {
        "batch": batch_index,
        "rounds": rounds,
        "target_count": target_count,
        "decision_count": len(future_rewards),
        "median_latency_ms": round(median_latency, 3),
        "policy_scores": policy_scores,
        "controls": {
            "fixed_best": fixed_best,
            "prng_trials": prng_trials,
            "prng_mean": prng_mean,
            "prng_median": prng_median,
            "prng_max": max(prng_scores) if prng_scores else 0.0,
            "oracle_next_best": oracle_next_best,
        },
        "wins": wins,
        "samples": [sample for samples in round_samples for sample in samples],
        "decisions": decisions,
    }


def write_remote(owner: str, repo: str, result: dict[str, Any]) -> dict[str, Any]:
    from nsl_f1_capsule_lifecycle import put_json, wait_for_hash  # noqa: WPS433
    from nsl_l12_hourly_self_maintenance import gh_token  # noqa: WPS433

    payload = seal(
        {
            "stage": "FIELD-1C-task-utility-last-run",
            "schema_version": "QMX-FIELD-1C-LAST-RUN-0.1",
            "created_at": now(),
            "ok": result["ok"],
            "run_id": result["run_id"],
            "result_hash": result["result_hash"],
            "verdict": result["verdict"],
            "aggregate": result["aggregate"],
            "truth_boundary": result["truth_boundary"],
            "state_hash": "",
        },
        "state_hash",
    )
    token = gh_token()
    write = put_json(owner, repo, token, REMOTE_LAST_RUN_PATH, payload, f"FIELD-1C task utility last run {result['run_id']}")
    check = wait_for_hash(owner, repo, token, REMOTE_LAST_RUN_PATH, "state_hash", payload["state_hash"])
    return {"path": REMOTE_LAST_RUN_PATH, "state_hash": payload["state_hash"], "write": write, "check": check}


def main() -> int:
    parser = argparse.ArgumentParser(description="FIELD-1C task-level utility experiment")
    parser.add_argument("--targets", default=str(Path(__file__).with_name("targets_1b.json")))
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--batches", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--prng-trials", type=int, default=24)
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--write-remote", action="store_true")
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest_field_1c_task_utility_result.json"))
    args = parser.parse_args()

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8")).get("targets", [])
    run_id = "field_1c_task_utility-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    batch_results = [
        evaluate_batch(index, targets, max(2, args.rounds), args.timeout, max(1, args.prng_trials))
        for index in range(1, max(1, args.batches) + 1)
    ]
    signal_names = ["latency", "non_latency", "mixed"]
    aggregate_scores = {
        name: round(sum(float(batch["policy_scores"][name]) for batch in batch_results), 6)
        for name in [*signal_names, "fixed_first", "fixed_cycle"]
    }
    aggregate_prng_mean = round(sum(float(batch["controls"]["prng_mean"]) for batch in batch_results), 6)
    aggregate_fixed_best = round(sum(float(batch["controls"]["fixed_best"]) for batch in batch_results), 6)
    aggregate_wins = {
        name: {
            "beats_fixed_best_batches": sum(1 for batch in batch_results if batch["wins"][name]["beats_fixed_best"]),
            "beats_prng_mean_batches": sum(1 for batch in batch_results if batch["wins"][name]["beats_prng_mean"]),
            "beats_prng_median_batches": sum(1 for batch in batch_results if batch["wins"][name]["beats_prng_median"]),
        }
        for name in signal_names
    }
    batch_count = len(batch_results)
    mixed_wins = aggregate_wins["mixed"]
    if batch_count == 0:
        verdict_name = "inconclusive"
    elif mixed_wins["beats_fixed_best_batches"] / batch_count >= 0.67 and mixed_wins["beats_prng_mean_batches"] / batch_count >= 0.67:
        verdict_name = "task_utility_strong"
    elif mixed_wins["beats_fixed_best_batches"] / batch_count >= 0.67:
        verdict_name = "task_utility_beats_fixed_only"
    else:
        verdict_name = "no_task_utility"

    result = {
        "stage": "FIELD-1C-task-level-utility",
        "ok": bool(batch_results and targets),
        "run_id": run_id,
        "rounds": max(2, args.rounds),
        "batches": max(1, args.batches),
        "target_count": len(targets),
        "task": "Use current network field signal to choose the next network read target; score against next-round real target quality.",
        "aggregate": {
            "policy_scores": aggregate_scores,
            "fixed_best": aggregate_fixed_best,
            "prng_mean_total": aggregate_prng_mean,
            "wins": aggregate_wins,
        },
        "verdict": {
            "verdict": verdict_name,
            "batch_count": batch_count,
            "mixed_score": aggregate_scores.get("mixed", 0.0),
            "fixed_best": aggregate_fixed_best,
            "prng_mean_total": aggregate_prng_mean,
            "truth_boundary": "FIELD-1C is a task-level routing benchmark, not proof of CPU-free computation.",
        },
        "batch_results": batch_results,
        "truth_boundary": "FIELD-1C can show whether field signal helps this specific real network-target choice task. It does not prove spontaneous compute, CPU-free execution, or network supercompute.",
    }
    result = seal(result, "result_hash")
    if args.write_remote:
        result["remote_write"] = write_remote(args.owner, args.repo, result)
        result = seal(result, "result_hash")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
