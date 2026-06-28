from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import urllib.request
from pathlib import Path
from typing import Any


def sample_url(name: str, url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    status = 0
    size = 0
    etag = ""
    last_modified = ""
    error = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "qimingxing-field-probe/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read(4096)
            status = int(getattr(response, "status", 0) or 0)
            size = len(body)
            etag = response.headers.get("ETag", "")
            last_modified = response.headers.get("Last-Modified", "")
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    material = f"{name}|{url}|{status}|{size}|{etag}|{last_modified}|{elapsed_ms}|{error}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return {
        "name": name,
        "url": url,
        "status": status,
        "size": size,
        "etag_present": bool(etag),
        "last_modified_present": bool(last_modified),
        "elapsed_ms": elapsed_ms,
        "error": error,
        "signal_hash": digest[:16],
    }


def bit_from_sample(sample: dict[str, Any]) -> int:
    latency_bucket = int(float(sample.get("elapsed_ms") or 0.0) * 1000)
    status = int(sample.get("status") or 0)
    size = int(sample.get("size") or 0)
    etag_bit = 1 if sample.get("etag_present") else 0
    mixed = latency_bucket ^ status ^ size ^ etag_bit
    return mixed & 1


def state_machine(bits: list[int]) -> dict[str, Any]:
    state = 0
    trace = []
    for index, bit in enumerate(bits):
        if bit:
            state = (state * 3 + 1) % 17
        else:
            state = (state * 2 + 5) % 17
        trace.append({"index": index, "bit": bit, "state": state})
    return {"final_state": state, "trace": trace}


def fixed_control(length: int) -> list[int]:
    return [0 for _ in range(length)]


def prng_control(length: int) -> list[int]:
    rng = random.Random(20260629)
    return [rng.randint(0, 1) for _ in range(length)]


def main() -> int:
    parser = argparse.ArgumentParser(description="FIELD-1 network tide signal probe V0")
    parser.add_argument("--targets", default=str(Path(__file__).with_name("targets.json")))
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8")).get("targets", [])
    samples: list[dict[str, Any]] = []
    for round_index in range(max(1, args.rounds)):
        for target in targets:
            samples.append(sample_url(str(target["name"]), str(target["url"]), args.timeout) | {"round": round_index + 1})

    network_bits = [bit_from_sample(sample) for sample in samples]
    fixed_bits = fixed_control(len(network_bits))
    prng_bits = prng_control(len(network_bits))
    result = {
        "stage": "FIELD-1-signal-probe-v0",
        "ok": bool(samples),
        "sample_count": len(samples),
        "network_bits": network_bits,
        "controls": {
            "fixed_bits": fixed_bits,
            "prng_bits": prng_bits,
        },
        "state_machine": {
            "network": state_machine(network_bits),
            "fixed": state_machine(fixed_bits),
            "prng": state_machine(prng_bits),
        },
        "samples": samples,
        "truth_boundary": "FIELD-1 samples network tide as a drive signal. It does not prove CPU-free computation or useful spontaneous compute.",
    }
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

