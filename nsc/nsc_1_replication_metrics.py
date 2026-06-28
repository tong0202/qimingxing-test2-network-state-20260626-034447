from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (Path(__file__).resolve().parent, ROOT, ROOT / "field", ROOT / "scripts"):
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)

from nsc_0_network_state_compute import (  # noqa: E402
    DEFAULT_OWNER,
    DEFAULT_REPO,
    INITIAL_STATE,
    REMOTE_LAST_RUN_PATH as NSC0_REMOTE_LAST_RUN_PATH,
    canonical_hash,
    observation_delta,
    observation_from_samples,
    run_stream,
    sample_round,
    seal,
    synthetic_observation,
)


REMOTE_LAST_RUN_PATH = "states/nsc-1-last-run.json"
STREAM_NAMES = ["real", "fixed", "prng", "shuffled_real", "reversed_real"]
CONTROL_NAMES = ["fixed", "prng", "shuffled_real", "reversed_real"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_streams_for_batch(real_observations: list[dict[str, Any]], batch_index: int) -> dict[str, list[dict[str, Any]]]:
    streams: dict[str, list[dict[str, Any]]] = {"real": real_observations}

    fixed_raw = [json.loads(json.dumps(real_observations[0], ensure_ascii=False)) for _ in real_observations]
    fixed: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for index, observation in enumerate(fixed_raw, start=1):
        observation["round"] = index
        observation["input_delta"] = observation_delta(previous, observation) if previous else 0.0
        fixed.append(observation)
        previous = observation
    streams["fixed"] = fixed

    rng = random.Random(20260629 + batch_index * 104729)
    prng_raw = [synthetic_observation(rng, index, real_observations[0]) for index in range(1, len(real_observations) + 1)]
    prng: list[dict[str, Any]] = []
    previous = None
    for observation in prng_raw:
        observation["input_delta"] = observation_delta(previous, observation) if previous else 0.0
        prng.append(observation)
        previous = observation
    streams["prng"] = prng

    shuffled_raw = json.loads(json.dumps(real_observations, ensure_ascii=False))
    random.Random(20260629 + batch_index * 8191).shuffle(shuffled_raw)
    shuffled: list[dict[str, Any]] = []
    previous = None
    for index, observation in enumerate(shuffled_raw, start=1):
        observation["round"] = index
        observation["input_delta"] = observation_delta(previous, observation) if previous else 0.0
        shuffled.append(observation)
        previous = observation
    streams["shuffled_real"] = shuffled

    reversed_raw = json.loads(json.dumps(list(reversed(real_observations)), ensure_ascii=False))
    reversed_stream: list[dict[str, Any]] = []
    previous = None
    for index, observation in enumerate(reversed_raw, start=1):
        observation["round"] = index
        observation["input_delta"] = observation_delta(previous, observation) if previous else 0.0
        reversed_stream.append(observation)
        previous = observation
    streams["reversed_real"] = reversed_stream
    return streams


def run_batch(batch_index: int, targets: list[dict[str, Any]], rounds: int, timeout: float) -> dict[str, Any]:
    real_observations: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for round_index in range(1, max(3, rounds) + 1):
        samples = sample_round(targets, round_index, timeout)
        observation = observation_from_samples(samples, previous)
        observation["batch"] = batch_index
        real_observations.append(observation)
        previous = observation

    streams = build_streams_for_batch(real_observations, batch_index)
    perturb_at = max(2, len(real_observations) // 2)
    stream_results = {name: run_stream(name, observations, perturb_at) for name, observations in streams.items()}
    real = stream_results["real"]
    best_control_work = max(float(stream_results[name]["effective_state_work"]) for name in CONTROL_NAMES)
    best_control_convergence = max(float(stream_results[name]["convergence_gain"]) for name in CONTROL_NAMES)
    best_control_recovery = max(float(stream_results[name]["recovery"]) for name in CONTROL_NAMES)
    best_control_coupling = max(float(stream_results[name]["input_state_coupling"]) for name in CONTROL_NAMES)
    best_order_control = max(
        float(stream_results["shuffled_real"]["effective_state_work"]),
        float(stream_results["reversed_real"]["effective_state_work"]),
    )
    margins = {
        "effective_state_work": round(float(real["effective_state_work"]) - best_control_work, 6),
        "convergence": round(float(real["convergence_gain"]) - best_control_convergence, 6),
        "recovery": round(float(real["recovery"]) - best_control_recovery, 6),
        "coupling": round(float(real["input_state_coupling"]) - best_control_coupling, 6),
        "temporal_order": round(float(real["effective_state_work"]) - best_order_control, 6),
    }
    margin_rates = {
        key: round(value / max(0.000001, abs(base)), 6)
        for key, value, base in [
            ("effective_state_work", margins["effective_state_work"], best_control_work),
            ("convergence", margins["convergence"], best_control_convergence),
            ("recovery", margins["recovery"], best_control_recovery),
            ("coupling", margins["coupling"], best_control_coupling),
            ("temporal_order", margins["temporal_order"], best_order_control),
        ]
    }
    wins = {key: value > 0.0 for key, value in margins.items()}
    return {
        "batch": batch_index,
        "rounds": rounds,
        "target_count": len(targets),
        "perturb_at_round": perturb_at,
        "streams": stream_results,
        "margins": margins,
        "margin_rates": margin_rates,
        "wins": wins,
        "real_observation_hashes": [observation["network_hash"] for observation in real_observations],
        "batch_hash": canonical_hash({"streams": stream_results, "margins": margins, "wins": wins}),
    }


def mean(values: list[float]) -> float:
    return round(float(statistics.fmean(values)), 6) if values else 0.0


def stdev(values: list[float]) -> float:
    return round(float(statistics.pstdev(values)), 6) if len(values) > 1 else 0.0


def classify_metric(win_rate: float, mean_margin_rate: float) -> str:
    if win_rate >= 0.70 and mean_margin_rate >= 0.05:
        return "strong_stable"
    if win_rate >= 0.60 and mean_margin_rate > 0.0:
        return "weak_stable"
    return "unstable_or_negative"


def aggregate_batches(batch_results: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = ["effective_state_work", "convergence", "recovery", "coupling", "temporal_order"]
    batch_count = len(batch_results)
    metrics: dict[str, Any] = {}
    for metric in metric_names:
        margins = [float(batch["margins"][metric]) for batch in batch_results]
        margin_rates = [float(batch["margin_rates"][metric]) for batch in batch_results]
        wins = [bool(batch["wins"][metric]) for batch in batch_results]
        win_count = sum(1 for item in wins if item)
        win_rate = win_count / max(1, batch_count)
        mean_margin_rate = mean(margin_rates)
        metrics[metric] = {
            "win_count": win_count,
            "batch_count": batch_count,
            "win_rate": round(win_rate, 6),
            "mean_margin": mean(margins),
            "mean_margin_rate": mean_margin_rate,
            "stdev_margin_rate": stdev(margin_rates),
            "classification": classify_metric(win_rate, mean_margin_rate),
            "margins": margins,
            "margin_rates": margin_rates,
        }

    strong = [name for name, item in metrics.items() if item["classification"] == "strong_stable"]
    weak = [name for name, item in metrics.items() if item["classification"] == "weak_stable"]
    unstable = [name for name, item in metrics.items() if item["classification"] == "unstable_or_negative"]
    if "effective_state_work" in strong and "temporal_order" in strong:
        verdict_name = "nsc_1_stable_real_network_state_edge"
    elif "effective_state_work" in weak or "temporal_order" in weak or "coupling" in weak:
        verdict_name = "nsc_1_weak_or_partial_edge"
    else:
        verdict_name = "nsc_1_no_stable_edge"
    return {
        "verdict": verdict_name,
        "batch_count": batch_count,
        "metrics": metrics,
        "strong_metrics": strong,
        "weak_metrics": weak,
        "unstable_metrics": unstable,
        "truth_boundary": "NSC-1 tests repeatability and split metrics. It does not prove CPU-free or faster-than-CPU computation.",
    }


def write_remote(owner: str, repo: str, result: dict[str, Any]) -> dict[str, Any]:
    try:
        from nsl_f1_capsule_lifecycle import put_json, wait_for_hash  # noqa: WPS433
        from nsl_l12_hourly_self_maintenance import gh_token  # noqa: WPS433

        payload = seal(
            {
                "stage": "NSC-1-last-run",
                "schema_version": "QMX-NSC-1-LAST-RUN-0.1",
                "created_at": now(),
                "ok": result["ok"],
                "run_id": result["run_id"],
                "result_hash": result["result_hash"],
                "source_nsc_0_remote_path": NSC0_REMOTE_LAST_RUN_PATH,
                "verdict": result["verdict"],
                "batch_summaries": [
                    {
                        "batch": batch["batch"],
                        "batch_hash": batch["batch_hash"],
                        "margins": batch["margins"],
                        "margin_rates": batch["margin_rates"],
                        "wins": batch["wins"],
                    }
                    for batch in result["batch_results"]
                ],
                "truth_boundary": result["truth_boundary"],
                "state_hash": "",
            },
            "state_hash",
        )
        token = gh_token()
        write = put_json(owner, repo, token, REMOTE_LAST_RUN_PATH, payload, f"NSC-1 last run {result['run_id']}")
        check = wait_for_hash(owner, repo, token, REMOTE_LAST_RUN_PATH, "state_hash", payload["state_hash"])
        return {"ok": bool(write.get("ok") and check.get("ok")), "path": REMOTE_LAST_RUN_PATH, "state_hash": payload["state_hash"], "write": write, "check": check}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "path": REMOTE_LAST_RUN_PATH, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="NSC-1 multi-batch replication with split metrics")
    parser.add_argument("--targets", default=str(Path(__file__).with_name("targets_nsc_0.json")))
    parser.add_argument("--batches", type=int, default=5)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--write-remote", action="store_true")
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest_nsc_1_replication_metrics_result.json"))
    args = parser.parse_args()

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8")).get("targets", [])
    run_id = "nsc_1_replication_metrics-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    batch_results = [
        run_batch(batch_index, targets, max(3, args.rounds), args.timeout)
        for batch_index in range(1, max(1, args.batches) + 1)
    ]
    aggregate = aggregate_batches(batch_results)
    result = {
        "stage": "NSC-1-replication-and-split-metrics",
        "ok": bool(targets and batch_results),
        "run_id": run_id,
        "batches": max(1, args.batches),
        "rounds_per_batch": max(3, args.rounds),
        "target_count": len(targets),
        "initial_state": INITIAL_STATE,
        "controls": CONTROL_NAMES,
        "split_questions": ["coupling", "recovery", "convergence", "temporal_order"],
        "batch_results": batch_results,
        "verdict": aggregate,
        "truth_boundary": "NSC-1 repeats NSC-0 and separates metrics. It still uses material observation, transduction, and scoring, so it does not prove endpoint-free, CPU-free, faster-than-CPU, or a stable network compute law by itself.",
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
