from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (Path(__file__).resolve().parent, ROOT, SCRIPTS):
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)

from nlang_compiler_v0 import compile_rules, load_rules  # noqa: E402
from nsl_l12_hourly_self_maintenance import content_get, gh_token, stable_hash  # noqa: E402


DEFAULT_OWNER = "tong0202"
DEFAULT_REPO = "qimingxing-test2-network-state-20260626-034447"
F3_STATE_PATH = "states/f3-loop-state.json"


def map_remote_f3_state(remote_state: dict[str, Any]) -> dict[str, Any]:
    scheduler_state = remote_state.get("scheduler_state") if isinstance(remote_state.get("scheduler_state"), dict) else {}
    child = scheduler_state.get("child") if isinstance(scheduler_state.get("child"), dict) else {}
    return {
        "f3": {
            "remote": {
                "run_id": remote_state.get("run_id"),
                "state_hash": remote_state.get("state_hash"),
                "window_count": int(remote_state.get("window_count") or 0),
                "selected_actions": remote_state.get("selected_actions") or [],
            },
            "child": {
                "exists": bool(child.get("exists")),
                "state": str(child.get("state") or "missing"),
                "retired": bool(child.get("retired", True)),
                "vitality": int(child.get("vitality") or 0),
                "capsule_hash": str(child.get("capsule_hash") or ""),
            },
            "lifecycle_cycle_count": int(remote_state.get("lifecycle_cycle_count") or 0),
            "last_peer_check_cycle_count": int(remote_state.get("last_peer_check_cycle_count") or 0),
            "last_peer_check_hash": str(scheduler_state.get("last_peer_check_hash") or ""),
            "total_scheduler_ticks": int(scheduler_state.get("total_scheduler_ticks") or 0),
            "last_selected_action": str(scheduler_state.get("last_selected_action") or ""),
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="NLANG-1A compile real remote F3 state")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--rules", default=str(Path(__file__).with_name("remote_f3_rules.nlang")))
    parser.add_argument("--out", default=str(ROOT / "runs" / "latest_nlang_1a_remote_f3_compile_result.json"))
    args = parser.parse_args()

    token = gh_token()
    remote_state, sha, response = content_get(args.owner, args.repo, F3_STATE_PATH, token)
    if not isinstance(remote_state, dict):
        result = {
            "stage": "NLANG-1A-remote-f3-compile",
            "ok": False,
            "error": "missing_remote_f3_state",
            "status": response.get("status"),
            "truth_boundary": "NLANG-1A cannot compile without remote F3 state.",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    remote_state_hash_ok = bool(remote_state.get("state_hash") and remote_state.get("state_hash") == stable_hash(remote_state, "state_hash"))
    nlang_state = map_remote_f3_state(remote_state)
    rules = load_rules(Path(args.rules))
    compiled = compile_rules(rules, nlang_state)
    selected_action = compiled.get("action_plan", {}).get("action")
    result = {
        "stage": "NLANG-1A-remote-f3-compile",
        "ok": bool(remote_state_hash_ok and compiled.get("ok")),
        "remote": {
            "repo": f"{args.owner}/{args.repo}",
            "path": F3_STATE_PATH,
            "content_sha": sha,
            "status": response.get("status"),
            "state_hash": remote_state.get("state_hash"),
            "state_hash_ok": remote_state_hash_ok,
            "run_id": remote_state.get("run_id"),
        },
        "nlang_state": nlang_state,
        "compiled": compiled,
        "selected_action": selected_action,
        "action_plan": compiled.get("action_plan"),
        "meaning": "NLANG selected the next action from real remote F3 state.",
        "truth_boundary": "NLANG-1A proves remote-state compilation only. It does not execute the action or prove spontaneous network compute.",
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
