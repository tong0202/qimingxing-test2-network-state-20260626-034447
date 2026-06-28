from __future__ import annotations

import argparse
import hashlib
import json
import math
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

from field_1b_stronger_metrics import bits_from_sample, sample_target  # noqa: E402


DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
REMOTE_LAST_RUN_PATH = "states/nsc-0-last-run.json"

STATE_KEYS = ["coherence", "continuity", "closure", "memory", "recovery"]
INITIAL_STATE = {
    "coherence": 0.31,
    "continuity": 0.42,
    "closure": 0.28,
    "memory": 0.37,
    "recovery": 0.33,
}
GOAL_STATE = {
    "coherence": 0.72,
    "continuity": 0.68,
    "closure": 0.74,
    "memory": 0.71,
    "recovery": 0.64,
}


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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def distance(left: dict[str, float], right: dict[str, float]) -> float:
    return math.sqrt(sum((float(left[key]) - float(right[key])) ** 2 for key in STATE_KEYS))


def vector_delta(left: dict[str, float], right: dict[str, float]) -> float:
    return math.sqrt(sum((float(left[key]) - float(right[key])) ** 2 for key in STATE_KEYS))


def hex_distance(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    if size == 0:
        return 0.0
    return sum(1 for index in range(size) if left[index] != right[index]) / size


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return 0.0
    return num / (den_x * den_y)


def median(values: list[float], fallback: float = 0.0) -> float:
    return float(statistics.median(values)) if values else fallback


def sample_round(targets: list[dict[str, Any]], round_index: int, timeout: float) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for target in targets:
        sample = sample_target(str(target["name"]), str(target["url"]), timeout)
        sample["round"] = round_index
        sample["bits"] = bits_from_sample(sample)
        samples.append(sample)
    return samples


def observation_from_samples(samples: list[dict[str, Any]], previous: dict[str, Any] | None) -> dict[str, Any]:
    latencies = [float(sample.get("elapsed_ms") or 9999.0) for sample in samples]
    ok_count = sum(1 for sample in samples if int(sample.get("status") or 0) == 200 and not sample.get("error"))
    status_ok_rate = ok_count / max(1, len(samples))
    sorted_latencies = sorted(latencies)
    p10 = sorted_latencies[max(0, int(len(sorted_latencies) * 0.1) - 1)] if sorted_latencies else 0.0
    p90 = sorted_latencies[min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.9))] if sorted_latencies else 0.0
    med = median(latencies, 9999.0)
    spread = clamp((p90 - p10) / max(1.0, med), 0.0, 3.0) / 3.0
    header_diversity = len({str(sample.get("header_hash") or "") for sample in samples}) / max(1, len(samples))
    body_diversity = len({str(sample.get("body_hash") or "") for sample in samples}) / max(1, len(samples))
    bit_rates = {
        key: sum(int(sample["bits"][key]) for sample in samples) / max(1, len(samples))
        for key in ["latency", "non_latency", "mixed"]
    }
    cache_age_values = []
    for sample in samples:
        try:
            cache_age_values.append(float(sample.get("age") or 0.0))
        except ValueError:
            cache_age_values.append(0.0)
    age_signal = clamp(math.log1p(sum(cache_age_values) / max(1, len(cache_age_values))) / 10.0)
    material = [
        {
            "name": sample.get("name"),
            "status": sample.get("status"),
            "size": sample.get("size"),
            "elapsed_bucket": int(float(sample.get("elapsed_ms") or 0.0) // 20),
            "header_hash": sample.get("header_hash"),
            "body_hash": sample.get("body_hash"),
            "bits": sample.get("bits"),
            "error": bool(sample.get("error")),
        }
        for sample in samples
    ]
    network_hash = canonical_hash(material)
    observation = {
        "round": int(samples[0].get("round") or 0) if samples else 0,
        "status_ok_rate": round(status_ok_rate, 6),
        "median_latency_ms": round(med, 3),
        "latency_spread": round(spread, 6),
        "header_diversity": round(header_diversity, 6),
        "body_diversity": round(body_diversity, 6),
        "age_signal": round(age_signal, 6),
        "bit_rates": {key: round(value, 6) for key, value in bit_rates.items()},
        "network_hash": network_hash,
        "samples": samples,
    }
    observation["input_delta"] = observation_delta(previous, observation) if previous else 0.0
    return observation


def observation_delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> float:
    if not previous:
        return 0.0
    items = [
        abs(float(current["status_ok_rate"]) - float(previous["status_ok_rate"])),
        abs(float(current["latency_spread"]) - float(previous["latency_spread"])),
        abs(float(current["header_diversity"]) - float(previous["header_diversity"])),
        abs(float(current["body_diversity"]) - float(previous["body_diversity"])),
        abs(float(current["age_signal"]) - float(previous["age_signal"])),
        abs(float(current["bit_rates"]["latency"]) - float(previous["bit_rates"]["latency"])),
        abs(float(current["bit_rates"]["non_latency"]) - float(previous["bit_rates"]["non_latency"])),
        abs(float(current["bit_rates"]["mixed"]) - float(previous["bit_rates"]["mixed"])),
        hex_distance(str(previous.get("network_hash") or ""), str(current.get("network_hash") or "")),
    ]
    prev_latency = float(previous.get("median_latency_ms") or 1.0)
    cur_latency = float(current.get("median_latency_ms") or 1.0)
    items.append(clamp(abs(cur_latency - prev_latency) / max(1.0, prev_latency), 0.0, 2.0) / 2.0)
    return round(sum(items) / len(items), 6)


def synthetic_observation(rng: random.Random, index: int, baseline: dict[str, Any]) -> dict[str, Any]:
    bit_rates = {key: clamp(rng.random()) for key in ["latency", "non_latency", "mixed"]}
    payload = {
        "kind": "synthetic-prng",
        "index": index,
        "seed": rng.random(),
        "baseline": baseline.get("network_hash", ""),
    }
    obs = {
        "round": index,
        "status_ok_rate": round(clamp(rng.gauss(float(baseline.get("status_ok_rate") or 0.8), 0.2)), 6),
        "median_latency_ms": round(max(10.0, rng.gauss(float(baseline.get("median_latency_ms") or 300.0), 140.0)), 3),
        "latency_spread": round(clamp(rng.random()), 6),
        "header_diversity": round(clamp(rng.random()), 6),
        "body_diversity": round(clamp(rng.random()), 6),
        "age_signal": round(clamp(rng.random()), 6),
        "bit_rates": {key: round(value, 6) for key, value in bit_rates.items()},
        "network_hash": canonical_hash(payload),
        "samples": [],
    }
    return obs


def build_streams(real_observations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    streams: dict[str, list[dict[str, Any]]] = {"real": real_observations}
    fixed_raw = [json.loads(json.dumps(real_observations[0], ensure_ascii=False)) for _ in real_observations]
    fixed: list[dict[str, Any]] = []
    prev: dict[str, Any] | None = None
    for index, obs in enumerate(fixed_raw, start=1):
        obs["round"] = index
        obs["input_delta"] = observation_delta(prev, obs) if prev else 0.0
        fixed.append(obs)
        prev = obs
    streams["fixed"] = fixed

    rng = random.Random(20260629)
    prng_raw = [synthetic_observation(rng, index, real_observations[0]) for index in range(1, len(real_observations) + 1)]
    prng: list[dict[str, Any]] = []
    prev = None
    for obs in prng_raw:
        obs["input_delta"] = observation_delta(prev, obs) if prev else 0.0
        prng.append(obs)
        prev = obs
    streams["prng"] = prng

    shuffled_raw = json.loads(json.dumps(real_observations, ensure_ascii=False))
    random.Random(20260629).shuffle(shuffled_raw)
    shuffled: list[dict[str, Any]] = []
    prev = None
    for index, obs in enumerate(shuffled_raw, start=1):
        obs["round"] = index
        obs["input_delta"] = observation_delta(prev, obs) if prev else 0.0
        shuffled.append(obs)
        prev = obs
    streams["shuffled_real"] = shuffled
    return streams


def transduce(state: dict[str, float], observation: dict[str, Any], round_index: int) -> dict[str, float]:
    status = float(observation["status_ok_rate"])
    spread = float(observation["latency_spread"])
    diversity = (float(observation["header_diversity"]) + float(observation["body_diversity"])) / 2.0
    age = float(observation["age_signal"])
    bit_latency = float(observation["bit_rates"]["latency"])
    bit_non_latency = float(observation["bit_rates"]["non_latency"])
    bit_mixed = float(observation["bit_rates"]["mixed"])
    balance = 1.0 - abs(bit_mixed - 0.5) * 2.0
    turbulence = float(observation.get("input_delta") or 0.0)
    digest = hashlib.sha256(f"{observation['network_hash']}|{round_index}".encode("utf-8")).digest()
    signs = [(1 if byte % 2 else -1) for byte in digest[: len(STATE_KEYS)]]

    drivers = {
        "coherence": 0.55 * status + 0.25 * balance + 0.20 * (1.0 - spread),
        "continuity": 0.60 * (1.0 - turbulence) + 0.25 * status + 0.15 * (1.0 - spread),
        "closure": 0.40 * diversity + 0.30 * status + 0.30 * bit_non_latency,
        "memory": 0.35 * (1.0 - turbulence) + 0.30 * diversity + 0.20 * age + 0.15 * bit_latency,
        "recovery": 0.45 * status + 0.25 * balance + 0.20 * (1.0 - turbulence) + 0.10 * bit_mixed,
    }
    new_state: dict[str, float] = {}
    for index, key in enumerate(STATE_KEYS):
        attraction = 0.115 * drivers[key] * (GOAL_STATE[key] - state[key])
        field_pressure = 0.028 * (drivers[key] - 0.5)
        trace_jitter = signs[index] * 0.006 * turbulence
        new_state[key] = round(clamp(state[key] + attraction + field_pressure + trace_jitter), 6)
    return new_state


def perturb(state: dict[str, float]) -> dict[str, float]:
    disturbed = dict(state)
    disturbed["coherence"] = clamp(disturbed["coherence"] - 0.18)
    disturbed["continuity"] = clamp(disturbed["continuity"] - 0.12)
    disturbed["closure"] = clamp(disturbed["closure"] + 0.08)
    disturbed["memory"] = clamp(disturbed["memory"] - 0.16)
    disturbed["recovery"] = clamp(disturbed["recovery"] - 0.20)
    return {key: round(value, 6) for key, value in disturbed.items()}


def run_stream(name: str, observations: list[dict[str, Any]], perturb_at: int) -> dict[str, Any]:
    state = dict(INITIAL_STATE)
    path = [{"round": 0, "state": state, "distance_to_goal": round(distance(state, GOAL_STATE), 6), "event": "initial"}]
    input_deltas: list[float] = []
    state_deltas: list[float] = []
    before_perturb_distance = 0.0
    after_perturb_distance = 0.0
    for index, observation in enumerate(observations, start=1):
        before = dict(state)
        state = transduce(state, observation, index)
        event = "transduce"
        if index == perturb_at:
            before_perturb_distance = distance(state, GOAL_STATE)
            state = perturb(state)
            after_perturb_distance = distance(state, GOAL_STATE)
            event = "transduce_and_perturb"
        input_deltas.append(float(observation.get("input_delta") or 0.0))
        state_deltas.append(vector_delta(before, state))
        path.append({"round": index, "state": state, "distance_to_goal": round(distance(state, GOAL_STATE), 6), "event": event})

    start_distance = float(path[0]["distance_to_goal"])
    final_distance = float(path[-1]["distance_to_goal"])
    distances = [float(item["distance_to_goal"]) for item in path]
    improvements = sum(1 for left, right in zip(distances, distances[1:]) if right < left)
    convergence_gain = clamp((start_distance - final_distance) / max(0.000001, start_distance), -1.0, 1.0)
    mean_state_delta = statistics.fmean(state_deltas) if state_deltas else 0.0
    continuity = 1.0 / (1.0 + mean_state_delta * 4.0)
    recovery = 0.0
    if after_perturb_distance > 0.0:
        recovery = clamp((after_perturb_distance - final_distance) / after_perturb_distance, -1.0, 1.0)
    coupling = abs(pearson(input_deltas, state_deltas))
    monotonicity = improvements / max(1, len(distances) - 1)
    effective_state_work = (
        0.34 * convergence_gain
        + 0.20 * recovery
        + 0.18 * monotonicity
        + 0.16 * continuity
        + 0.12 * coupling
    )
    return {
        "name": name,
        "rounds": len(observations),
        "start_distance": round(start_distance, 6),
        "final_distance": round(final_distance, 6),
        "convergence_gain": round(convergence_gain, 6),
        "monotonicity": round(monotonicity, 6),
        "continuity": round(continuity, 6),
        "recovery": round(recovery, 6),
        "input_state_coupling": round(coupling, 6),
        "effective_state_work": round(effective_state_work, 6),
        "before_perturb_distance": round(before_perturb_distance, 6),
        "after_perturb_distance": round(after_perturb_distance, 6),
        "final_state": path[-1]["state"],
        "path_hash": canonical_hash(path),
        "path": path,
        "observation_hashes": [observation["network_hash"] for observation in observations],
        "input_deltas": input_deltas,
        "state_deltas": [round(value, 6) for value in state_deltas],
    }


def verdict(stream_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    real = stream_results["real"]
    fixed = stream_results["fixed"]
    prng = stream_results["prng"]
    shuffled = stream_results["shuffled_real"]
    real_score = float(real["effective_state_work"])
    best_control_score = max(
        float(fixed["effective_state_work"]),
        float(prng["effective_state_work"]),
        float(shuffled["effective_state_work"]),
    )
    margin = real_score - best_control_score
    margin_rate = margin / max(0.000001, abs(best_control_score))
    beats = {
        "beats_fixed": real_score > float(fixed["effective_state_work"]),
        "beats_prng": real_score > float(prng["effective_state_work"]),
        "beats_shuffled_real": real_score > float(shuffled["effective_state_work"]),
    }
    if all(beats.values()) and margin_rate >= 0.05:
        name = "nsc_0_real_network_advantage"
    elif all(beats.values()) and margin > 0:
        name = "nsc_0_weak_real_network_edge"
    elif float(real["convergence_gain"]) > 0.0 and float(real["recovery"]) > 0.0:
        name = "nsc_0_transduction_observed_no_advantage"
    else:
        name = "nsc_0_no_transduction_advantage"
    return {
        "verdict": name,
        "real_effective_state_work": real_score,
        "best_control_effective_state_work": round(best_control_score, 6),
        "real_vs_best_control_margin": round(margin, 6),
        "real_vs_best_control_margin_rate": round(margin_rate, 6),
        "strong_advantage_threshold_margin_rate": 0.05,
        "control_effective_state_work": {
            "fixed": fixed["effective_state_work"],
            "prng": prng["effective_state_work"],
            "shuffled_real": shuffled["effective_state_work"],
        },
        "beats": beats,
        "truth_boundary": "NSC-0 is a state-transduction experiment. It does not prove CPU-free or faster-than-CPU computation.",
    }


def write_remote(owner: str, repo: str, result: dict[str, Any]) -> dict[str, Any]:
    try:
        from nsl_f1_capsule_lifecycle import put_json, wait_for_hash  # noqa: WPS433
        from nsl_l12_hourly_self_maintenance import gh_token  # noqa: WPS433

        payload = seal(
            {
                "stage": "NSC-0-last-run",
                "schema_version": "QMX-NSC-0-LAST-RUN-0.1",
                "created_at": now(),
                "ok": result["ok"],
                "run_id": result["run_id"],
                "result_hash": result["result_hash"],
                "verdict": result["verdict"],
                "stream_summary": {
                    name: {
                        "effective_state_work": stream["effective_state_work"],
                        "convergence_gain": stream["convergence_gain"],
                        "recovery": stream["recovery"],
                        "input_state_coupling": stream["input_state_coupling"],
                        "path_hash": stream["path_hash"],
                    }
                    for name, stream in result["streams"].items()
                },
                "truth_boundary": result["truth_boundary"],
                "state_hash": "",
            },
            "state_hash",
        )
        token = gh_token()
        write = put_json(owner, repo, token, REMOTE_LAST_RUN_PATH, payload, f"NSC-0 last run {result['run_id']}")
        check = wait_for_hash(owner, repo, token, REMOTE_LAST_RUN_PATH, "state_hash", payload["state_hash"])
        return {"ok": bool(write.get("ok") and check.get("ok")), "path": REMOTE_LAST_RUN_PATH, "state_hash": payload["state_hash"], "write": write, "check": check}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "path": REMOTE_LAST_RUN_PATH, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="NSC-0 network state compute experiment")
    parser.add_argument("--targets", default=str(Path(__file__).with_name("targets_nsc_0.json")))
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--write-remote", action="store_true")
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest_nsc_0_network_state_compute_result.json"))
    args = parser.parse_args()

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8")).get("targets", [])
    run_id = "nsc_0_network_state_compute-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    real_observations: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for round_index in range(1, max(3, args.rounds) + 1):
        samples = sample_round(targets, round_index, args.timeout)
        observation = observation_from_samples(samples, previous)
        real_observations.append(observation)
        previous = observation

    streams = build_streams(real_observations)
    perturb_at = max(2, len(real_observations) // 2)
    stream_results = {name: run_stream(name, observations, perturb_at) for name, observations in streams.items()}
    result = {
        "stage": "NSC-0-network-state-compute",
        "ok": bool(targets and real_observations),
        "run_id": run_id,
        "rounds": max(3, args.rounds),
        "target_count": len(targets),
        "initial_state": INITIAL_STATE,
        "goal_state": GOAL_STATE,
        "perturb_at_round": perturb_at,
        "hypothesis": "Real network-state input may drive measurable state transduction without judging it as CPU-style FLOPS.",
        "streams": stream_results,
        "verdict": verdict(stream_results),
        "real_observation_summary": [
            {
                "round": observation["round"],
                "status_ok_rate": observation["status_ok_rate"],
                "median_latency_ms": observation["median_latency_ms"],
                "latency_spread": observation["latency_spread"],
                "header_diversity": observation["header_diversity"],
                "body_diversity": observation["body_diversity"],
                "bit_rates": observation["bit_rates"],
                "input_delta": observation["input_delta"],
                "network_hash": observation["network_hash"],
            }
            for observation in real_observations
        ],
        "truth_boundary": "NSC-0 still uses a material CPU for observation, state update, and scoring. It does not prove endpoint-free execution, CPU-free computation, faster-than-CPU compute, or a finished ghost computer.",
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
