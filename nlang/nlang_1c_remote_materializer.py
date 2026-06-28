from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (Path(__file__).resolve().parent, ROOT, SCRIPTS):
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)

import nlang_1b_materialize_action_plan as materializer  # noqa: E402


def main() -> int:
    defaults = [
        "--mode",
        "external",
        "--stage-label",
        "NLANG-1C",
        "--run-prefix",
        "nlang_1c_remote",
        "--proof-ledger-path",
        "states/nlang-1c-proof-ledger.json",
        "--last-run-path",
        "states/nlang-1c-last-run.json",
        "--out",
        str(ROOT / "runs" / "latest_nlang_1c_remote_materialize_result.json"),
    ]
    sys.argv = [sys.argv[0], *defaults, *sys.argv[1:]]
    return materializer.main()


if __name__ == "__main__":
    raise SystemExit(main())
