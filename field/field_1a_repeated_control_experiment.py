from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from field_signal_probe_v0 import bit_from_sample, fixed_control, sample_url, state_machine  # noqa: E402


def bit_metrics(bits: list[int]) -> dict[str, Any]:
    if not bits:
        return {"count": 0, "ones": 0, "zeros": 0, "one_rate": 0.0, "transition_count": 0, "transition_rate": 0.0, "entropy": 0.0}
    ones = sum(1 for bit in bits if bit)
    zeros = len(bits) - ones
    transitions = sum(1 for left, right in zip(bits, bits[1:]) if left != right)
    p = ones / len(bits)
    entropy = 0.0
    if p not in {0.0, 1.0}:
        entropy = -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))
    return {
        "count": len(bits),
        "ones": ones,
        "zeros": zeros,
        "one_rate": round(p, 4),
        "transition_count": transitions,
        "transition_rate": round(transitions / max(1, len(bits) - 1), 4),
        "entropy": round(entropy, 4),
    }


def coverage(machine: dict[str, Any]) -> int:
    trace = machine.get("trace") if isinstance(machine.get("trace"), list) else []
    return len({item.get("state") for item in trace if isinstance(item, dict)})


def score(bits: list[int]) -> dict[str, Any]:
    metrics = bit_metrics(bits)
    machine = state_machine(bits)
    return {
        "bits": bits,
        "metrics": metrics,
        "state_machine": machine,
        "coverage": coverage(machine),
        "final_state": machine.get("final_state"),
    }


def prng_control_for_batch(length: int, batch_index: int) -> list[int]:
    import random

    rng = random.Random(20260629 + batch_index)
    return [rng.randint(0, 1) for _ in range(length)]


def classify_single(network: dict[str, Any], fixed: dict[str, Any], prng: dict[str, Any], sample_ok_rate: float) -> dict[str, Any]:
    network_entropy = float(network["metrics"]["entropy"])
    fixed_entropy = float(fixed["metrics"]["entropy"])
    prng_entropy = float(prng["metrics"]["entropy"])
    network_coverage = int(network["coverage"])
    fixed_coverage = int(fixed["coverage"])
    prng_coverage = int(prng["coverage"])
    beats_fixed = bool(network_entropy > fixed_entropy and network_coverage > fixed_coverage)
    beats_prng = bool(network_entropy >= prng_entropy and network_coverage > prng_coverage)
    if sample_ok_rate <= 0:
        verdict = "signal_absent"
    elif beats_prng:
        verdict = "batch_beats_prng_metric"
    elif beats_fixed:
        verdict = "batch_beats_fixed_only"
    elif network_entropy > 0:
        verdict = "batch_drive_signal_present"
    else:
        verdict = "batch_inconclusive"
    return {
        "verdict": verdict,
        "sample_ok_rate": round(sample_ok_rate, 4),
        "beats_fixed_control": beats_fixed,
        "beats_prng_control": beats_prng,
        "truth_boundary": "This verdict is metric-bound and does not prove CPU-free computation.",
    }


def classify_batches(batch_results: list[dict[str, Any]]) -> dict[str, Any]:
    batch_count = len(batch_results)
    fixed_wins = sum(1 for item in batch_results if item["verdict"]["beats_fixed_control"])
    prng_wins = sum(1 for item in batch_results if item["verdict"]["beats_prng_control"])
    signal_batches = sum(1 for item in batch_results if float(item["network"]["metrics"]["entropy"]) > 0)
    fixed_rate = fixed_wins / max(1, batch_count)
    prng_rate = prng_wins / max(1, batch_count)
    signal_rate = signal_batches / max(1, batch_count)
    if batch_count == 0:
        verdict = "signal_absent"
    elif prng_rate >= 0.67:
        verdict = "repeated_metric_beats_prng_control"
    elif fixed_rate >= 0.67:
        verdict = "repeated_metric_beats_fixed_only"
    elif signal_rate >= 0.67:
        verdict = "repeated_drive_signal_present_no_control_advantage"
    else:
        verdict = "inconclusive"
    return {
        "verdict": verdict,
        "batch_count": batch_count,
        "beats_fixed_batches": fixed_wins,
        "beats_prng_batches": prng_wins,
        "signal_batches": signal_batches,
        "beats_fixed_rate": round(fixed_rate, 4),
        "beats_prng_rate": round(prng_rate, 4),
        "signal_rate": round(signal_rate, 4),
        "truth_boundary": "Repeated FIELD-1A verdict is still metric-bound and does not prove CPU-free computation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="FIELD-1A repeated network tide control experiment")
    parser.add_argument("--targets", default=str(Path(__file__).with_name("targets.json")))
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--batches", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest_field_1a_repeated_control_result.json"))
    args = parser.parse_args()

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8")).get("targets", [])
    samples: list[dict[str, Any]] = []
    batch_results: list[dict[str, Any]] = []
    for batch_index in range(max(1, args.batches)):
        batch_samples: list[dict[str, Any]] = []
        for round_index in range(max(1, args.rounds)):
            for target in targets:
                sample = sample_url(str(target["name"]), str(target["url"]), args.timeout) | {
                    "batch": batch_index + 1,
                    "round": round_index + 1,
                }
                batch_samples.append(sample)
                samples.append(sample)
        network_bits = [bit_from_sample(sample) for sample in batch_samples]
        fixed_bits = fixed_control(len(network_bits))
        prng_bits = prng_control_for_batch(len(network_bits), batch_index + 1)
        sample_ok_rate = sum(1 for sample in batch_samples if int(sample.get("status") or 0) == 200 and not sample.get("error")) / max(1, len(batch_samples))
        network_score = score(network_bits)
        fixed_score = score(fixed_bits)
        prng_score = score(prng_bits)
        batch_verdict = classify_single(network_score, fixed_score, prng_score, sample_ok_rate)
        batch_results.append(
            {
                "batch": batch_index + 1,
                "network": network_score,
                "fixed": fixed_score,
                "prng": prng_score,
                "verdict": batch_verdict,
            }
        )

    all_network_bits = [bit_from_sample(sample) for sample in samples]
    all_fixed_bits = fixed_control(len(all_network_bits))
    all_prng_bits = prng_control_for_batch(len(all_network_bits), 999)
    network_score = score(all_network_bits)
    fixed_score = score(all_fixed_bits)
    prng_score = score(all_prng_bits)
    verdict = classify_batches(batch_results)
    result = {
        "stage": "FIELD-1A-repeated-control-experiment",
        "ok": bool(samples),
        "rounds": max(1, args.rounds),
        "batches": max(1, args.batches),
        "target_count": len(targets),
        "sample_count": len(samples),
        "network": network_score,
        "controls": {
            "fixed": fixed_score,
            "prng": prng_score,
        },
        "batch_results": batch_results,
        "verdict": verdict,
        "samples": samples,
        "conclusion": (
            "FIELD-1A found repeated metric-bound evidence for a usable network drive signal."
            if verdict["verdict"] in {"repeated_metric_beats_fixed_only", "repeated_metric_beats_prng_control", "repeated_drive_signal_present_no_control_advantage"}
            else "FIELD-1A did not establish repeated metric-bound evidence for a usable network drive signal."
        ),
        "truth_boundary": "FIELD-1A compares network tide against controls. It does not prove CPU-free computation, a network supercomputer, or stable spontaneous compute.",
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
