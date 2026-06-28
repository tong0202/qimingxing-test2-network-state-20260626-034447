from __future__ import annotations

import argparse
import json
import operator
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RULE_RE = re.compile(r"^WHEN\s+(.+?)\s+THEN\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")
PRED_RE = re.compile(r"^([A-Za-z0-9_.]+)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")

OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}

LOW_RISK_ACTIONS = {"peer_check", "split", "decay", "retire", "observe"}


@dataclass
class Predicate:
    left: str
    op: str
    right: Any


@dataclass
class Rule:
    source: str
    predicates: list[Predicate]
    action: str


def parse_value(text: str) -> Any:
    lowered = text.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        if "." in lowered:
            return float(lowered)
        return int(lowered)
    except ValueError:
        return text.strip().strip('"').strip("'")


def get_path(state: dict[str, Any], path: str) -> Any:
    current: Any = state
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def parse_rule(line: str) -> Rule:
    match = RULE_RE.match(line.strip())
    if not match:
        raise ValueError(f"invalid rule syntax: {line}")
    predicate_text, action = match.groups()
    predicates: list[Predicate] = []
    for chunk in re.split(r"\s+AND\s+", predicate_text):
        pred_match = PRED_RE.match(chunk.strip())
        if not pred_match:
            raise ValueError(f"invalid predicate syntax: {chunk}")
        left, op, right = pred_match.groups()
        predicates.append(Predicate(left=left, op=op, right=parse_value(right)))
    return Rule(source=line.strip(), predicates=predicates, action=action)


def load_rules(path: Path) -> list[Rule]:
    rules: list[Rule] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rules.append(parse_rule(stripped))
    return rules


def evaluate_predicate(predicate: Predicate, state: dict[str, Any]) -> dict[str, Any]:
    try:
        left_value = get_path(state, predicate.left)
        right_value = predicate.right
        right_resolved_from_path = False
        if isinstance(predicate.right, str) and re.match(r"^[A-Za-z0-9_.]+$", predicate.right):
            try:
                right_value = get_path(state, predicate.right)
                right_resolved_from_path = True
            except KeyError:
                right_value = predicate.right
        ok = bool(OPS[predicate.op](left_value, right_value))
        return {
            "ok": ok,
            "left": predicate.left,
            "op": predicate.op,
            "right": right_value,
            "right_source": predicate.right if right_resolved_from_path else "literal",
            "observed": left_value,
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "left": predicate.left,
            "op": predicate.op,
            "right": predicate.right,
            "right_source": "literal",
            "observed": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def compile_rules(rules: list[Rule], state: dict[str, Any]) -> dict[str, Any]:
    evaluated_rules: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    for index, rule in enumerate(rules):
        predicate_results = [evaluate_predicate(predicate, state) for predicate in rule.predicates]
        matched = all(item["ok"] for item in predicate_results)
        risk_level = "low" if rule.action in LOW_RISK_ACTIONS else "high"
        rule_result = {
            "index": index,
            "source": rule.source,
            "action": rule.action,
            "matched": matched,
            "risk_level": risk_level,
            "predicates": predicate_results,
        }
        evaluated_rules.append(rule_result)
        if selected is None and matched and risk_level == "low":
            selected = rule_result

    action_plan = {
        "selected": bool(selected),
        "action": selected["action"] if selected else "observe",
        "risk_level": selected["risk_level"] if selected else "low",
        "required_reads": ["network_state"],
        "required_writes": ["scoped_state", "ledger"],
        "proof_required": True,
    }
    return {
        "stage": "NLANG-1-compiler-v0",
        "ok": bool(selected),
        "selected_rule": selected,
        "rules": evaluated_rules,
        "action_plan": action_plan,
        "truth_boundary": "NLANG-1 compiles formal rules into an action plan. It does not prove spontaneous network compute.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="NLANG-1 compiler V0")
    parser.add_argument("--rules", default=str(Path(__file__).with_name("sample_rules.nlang")))
    parser.add_argument("--state", default=str(Path(__file__).with_name("sample_state.json")))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    rules = load_rules(Path(args.rules))
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    result = compile_rules(rules, state)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
