from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sample_target(name: str, url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    status = 0
    body = b""
    headers: dict[str, str] = {}
    error = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "qimingxing-field-1b/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or 0)
            headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
            body = response.read(4096)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    body_hash = hashlib.sha256(body).hexdigest()[:16]
    header_material = "|".join(
        [
            str(status),
            str(len(body)),
            headers.get("etag", ""),
            headers.get("last-modified", ""),
            headers.get("date", ""),
            headers.get("server", ""),
            headers.get("cache-control", ""),
            headers.get("cf-cache-status", ""),
            headers.get("age", ""),
            body_hash,
        ]
    )
    return {
        "name": name,
        "url": url,
        "status": status,
        "size": len(body),
        "elapsed_ms": elapsed_ms,
        "etag_present": bool(headers.get("etag")),
        "last_modified_present": bool(headers.get("last-modified")),
        "date_present": bool(headers.get("date")),
        "server_present": bool(headers.get("server")),
        "cache_control_present": bool(headers.get("cache-control")),
        "cf_cache_status": headers.get("cf-cache-status", ""),
        "age": headers.get("age", ""),
        "body_hash": body_hash,
        "header_hash": hashlib.sha256(header_material.encode("utf-8")).hexdigest()[:16],
        "error": error,
    }


def hash_bit(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[-1], 16) & 1


def bits_from_sample(sample: dict[str, Any]) -> dict[str, int]:
    latency_bucket = int(float(sample.get("elapsed_ms") or 0.0) * 1000)
    latency_bit = (latency_bucket ^ int(sample.get("status") or 0) ^ int(sample.get("size") or 0)) & 1
    non_latency_material = "|".join(
        [
            str(sample.get("name") or ""),
            str(sample.get("status") or 0),
            str(sample.get("size") or 0),
            str(sample.get("etag_present")),
            str(sample.get("last_modified_present")),
            str(sample.get("date_present")),
            str(sample.get("server_present")),
            str(sample.get("cache_control_present")),
            str(sample.get("cf_cache_status") or ""),
            str(sample.get("age") or ""),
            str(sample.get("body_hash") or ""),
            str(sample.get("header_hash") or ""),
        ]
    )
    non_latency_bit = hash_bit(non_latency_material)
    return {
        "latency": latency_bit,
        "non_latency": non_latency_bit,
        "mixed": latency_bit ^ non_latency_bit,
    }


def state_machine(bits: list[int]) -> dict[str, Any]:
    state = 0
    trace = []
    for index, bit in enumerate(bits):
        state = ((state * 5 + 3) if bit else (state * 2 + 7)) % 31
        trace.append({"index": index, "bit": bit, "state": state})
    return {"final_state": state, "trace": trace}


def metrics(bits: list[int]) -> dict[str, Any]:
    if not bits:
        return {"count": 0, "ones": 0, "zeros": 0, "one_rate": 0.0, "transition_rate": 0.0, "entropy": 0.0, "coverage": 0}
    ones = sum(1 for bit in bits if bit)
    transitions = sum(1 for left, right in zip(bits, bits[1:]) if left != right)
    p = ones / len(bits)
    entropy = 0.0 if p in {0.0, 1.0} else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    machine = state_machine(bits)
    coverage = len({item["state"] for item in machine["trace"]})
    return {
        "count": len(bits),
        "ones": ones,
        "zeros": len(bits) - ones,
        "one_rate": round(p, 4),
        "transition_rate": round(transitions / max(1, len(bits) - 1), 4),
        "entropy": round(entropy, 4),
        "coverage": coverage,
        "final_state": machine["final_state"],
    }


def fixed_bits(length: int) -> list[int]:
    return [0] * length


def prng_bits(length: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.randint(0, 1) for _ in range(length)]


def wins_against(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return float(a["entropy"]) >= float(b["entropy"]) and int(a["coverage"]) > int(b["coverage"])


def main() -> int:
    parser = argparse.ArgumentParser(description="FIELD-1B stronger independent field metrics")
    parser.add_argument("--targets", default=str(Path(__file__).with_name("targets_1b.json")))
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--batches", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest_field_1b_stronger_metrics_result.json"))
    args = parser.parse_args()

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8")).get("targets", [])
    all_samples: list[dict[str, Any]] = []
    batch_results: list[dict[str, Any]] = []
    for batch_index in range(1, max(1, args.batches) + 1):
        streams = {"latency": [], "non_latency": [], "mixed": []}
        batch_samples: list[dict[str, Any]] = []
        for round_index in range(1, max(1, args.rounds) + 1):
            for target in targets:
                sample = sample_target(str(target["name"]), str(target["url"]), args.timeout) | {
                    "batch": batch_index,
                    "round": round_index,
                }
                sample_bits = bits_from_sample(sample)
                sample["bits"] = sample_bits
                for key, bit in sample_bits.items():
                    streams[key].append(bit)
                batch_samples.append(sample)
                all_samples.append(sample)

        length = len(streams["mixed"])
        fixed = metrics(fixed_bits(length))
        prng = metrics(prng_bits(length, 20260629 + batch_index))
        stream_metrics = {name: metrics(bits) for name, bits in streams.items()}
        batch_result = {
            "batch": batch_index,
            "sample_count": len(batch_samples),
            "sample_ok_rate": round(sum(1 for sample in batch_samples if sample.get("status") == 200 and not sample.get("error")) / max(1, len(batch_samples)), 4),
            "streams": stream_metrics,
            "controls": {"fixed": fixed, "prng": prng},
            "wins": {
                name: {
                    "beats_fixed": wins_against(metric, fixed),
                    "beats_prng": wins_against(metric, prng),
                }
                for name, metric in stream_metrics.items()
            },
        }
        batch_results.append(batch_result)

    stream_names = ["latency", "non_latency", "mixed"]
    beat_fixed_counts = {name: sum(1 for batch in batch_results if batch["wins"][name]["beats_fixed"]) for name in stream_names}
    beat_prng_counts = {name: sum(1 for batch in batch_results if batch["wins"][name]["beats_prng"]) for name in stream_names}
    batch_count = len(batch_results)
    if any(beat_prng_counts[name] / max(1, batch_count) >= 0.67 for name in ["non_latency", "mixed"]):
        verdict = "strong_field_advantage"
    elif any(beat_fixed_counts[name] / max(1, batch_count) >= 0.67 for name in ["non_latency", "mixed"]):
        verdict = "field_signal_present_no_prng_advantage"
    elif beat_fixed_counts["latency"] / max(1, batch_count) >= 0.67:
        verdict = "latency_only_signal"
    else:
        verdict = "inconclusive"

    aggregate_streams = {"latency": [], "non_latency": [], "mixed": []}
    for sample in all_samples:
        for key in aggregate_streams:
            aggregate_streams[key].append(int(sample["bits"][key]))
    aggregate_metrics = {name: metrics(bits) for name, bits in aggregate_streams.items()}
    result = {
        "stage": "FIELD-1B-stronger-independent-field-metrics",
        "ok": bool(all_samples),
        "rounds": max(1, args.rounds),
        "batches": max(1, args.batches),
        "target_count": len(targets),
        "sample_count": len(all_samples),
        "aggregate_streams": aggregate_metrics,
        "batch_results": batch_results,
        "beat_fixed_counts": beat_fixed_counts,
        "beat_prng_counts": beat_prng_counts,
        "verdict": {
            "verdict": verdict,
            "batch_count": batch_count,
            "beat_fixed_counts": beat_fixed_counts,
            "beat_prng_counts": beat_prng_counts,
            "truth_boundary": "FIELD-1B verdict is metric-bound and does not prove CPU-free computation.",
        },
        "samples": all_samples,
        "truth_boundary": "FIELD-1B tests stronger field-signal metrics. It does not prove network supercompute, CPU-free execution, or stable spontaneous compute.",
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

