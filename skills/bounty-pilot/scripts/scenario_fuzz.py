#!/usr/bin/env python3
"""Bounded state-model explorer: shortest counterexamples to authored invariants.

A violation in a hand-built model is NOT a vulnerability in deployed code.
The model must be checked against original source and native execution.
No arbitrary expressions/eval/network or target process execution.
"""
import argparse
import copy
import importlib.util
import json
from collections import deque
from decimal import Decimal, InvalidOperation
from pathlib import Path

OPS = {"eq", "ne", "le", "lt", "ge", "gt"}
EFFECTS = {"set", "add", "sub", "append", "remove"}
MAX_ACTIONS = 60
MAX_ACTORS = 20

def _load_invariants():
    p = Path(__file__).resolve().parent / "invariant_check.py"
    spec = importlib.util.spec_from_file_location("bp_invariant_check", p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _substitute(value, actor):
    if isinstance(value, str):
        return value.replace("{actor}", actor)
    if isinstance(value, dict):
        return {k: _substitute(v, actor) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, actor) for v in value]
    return value

def _path(parent, name):
    if not isinstance(name, str) or not name or any(not piece for piece in name.split(".")):
        raise ValueError("invalid state path")
    parts = name.split(".")
    cur = parent
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            raise ValueError("missing state path: " + name)
        cur = cur[part]
    if not isinstance(cur, dict) or parts[-1] not in cur:
        raise ValueError("missing state field: " + name)
    return cur, parts[-1]

def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("numeric state/effect requires an exact decimal")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("invalid decimal")
    if not result.is_finite():
        raise ValueError("non-finite decimal")
    return result

def _test(lhs, op, rhs):
    if op not in OPS:
        raise ValueError("unknown comparison")
    a, b = _decimal(lhs), _decimal(rhs)
    return {"eq": a == b, "ne": a != b, "le": a <= b,
            "lt": a < b, "ge": a >= b, "gt": a > b}[op]

def enabled(state, rule):
    for check in rule.get("guards", []):
        if not isinstance(check, dict):
            raise ValueError("guard must be object")
        obj, field = _path(state, check["path"])
        rhs = check.get("value")
        if isinstance(rhs, dict) and set(rhs) == {"path"}:
            rhs_obj, rhs_key = _path(state, rhs["path"])
            rhs = rhs_obj[rhs_key]
        if not _test(obj[field], check["op"], rhs):
            return False
    return True

def transition(state, rule):
    if not enabled(state, rule):
        return None
    new = copy.deepcopy(state)
    for change in rule.get("effects", []):
        if not isinstance(change, dict) or change.get("op") not in EFFECTS:
            raise ValueError("unsupported effect")
        obj, field = _path(new, change["path"])
        kind = change["op"]
        value = change.get("value")
        if isinstance(value, dict) and set(value) == {"path"}:
            source, key = _path(new, value["path"])
            value = source[key]
        if kind == "set":
            obj[field] = copy.deepcopy(value)
        elif kind in ("add", "sub"):
            amount = _decimal(value)
            old = _decimal(obj[field])
            obj[field] = str(old + amount if kind == "add" else old - amount)
        elif kind in ("append", "remove"):
            if not isinstance(obj[field], list):
                raise ValueError("list effect requires a list field")
            if kind == "append":
                if len(obj[field]) >= 100:
                    return None  # bound unbounded list growth
                obj[field].append(value)
            elif value in obj[field]:
                obj[field].remove(value)
            else:
                return None
    return new

def actions_for(model):
    actors = model.get("actors", [])
    rules = model.get("actions", [])
    if not isinstance(actors, list) or not 1 <= len(actors) <= MAX_ACTORS:
        raise ValueError("actors must be a bounded string array")
    if not all(isinstance(x, str) and x and "{" not in x for x in actors):
        raise ValueError("invalid actor name")
    if not isinstance(rules, list) or not 1 <= len(rules) <= MAX_ACTIONS:
        raise ValueError("actions must contain 1..60 entries")
    expanded = []
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("name"), str):
            raise ValueError("invalid action definition")
        if not isinstance(rule.get("effects"), list) or not rule["effects"]:
            raise ValueError("each action needs at least one effect")
        for actor in actors if rule.get("actor") == "*" else [rule.get("actor")]:
            if actor not in actors:
                raise ValueError("action actor is not an allowed actor")
            expanded.append((_substitute(rule["name"], actor), actor,
                             _substitute(rule, actor)))
    return sorted(expanded, key=lambda v: (v[0], v[1]))

def explore(model, depth=4, max_states=3000):
    if not isinstance(depth, int) or not 1 <= depth <= 8:
        raise ValueError("depth must be 1..8")
    if not isinstance(max_states, int) or not 1 <= max_states <= 20000:
        raise ValueError("max_states must be 1..20000")
    initial = model.get("state")
    if not isinstance(initial, dict):
        raise ValueError("state must be an object")
    invariants = {"invariants": model.get("invariants")}
    checker = _load_invariants()
    verdict = checker.evaluate(invariants, initial)
    if verdict["summary"]["fail"] or verdict["summary"]["unknown"]:
        raise ValueError("starting state must satisfy every declared invariant")
    possible = actions_for(model)
    queue = deque([(copy.deepcopy(initial), [])])
    seen = {json.dumps(initial, sort_keys=True, default=str)}
    attempts = 0
    counterexamples = []
    truncated = False
    while queue:
        state, trace = queue.popleft()
        if len(trace) >= depth:
            continue
        for label, actor, action in possible:
            attempts += 1
            next_state = transition(state, action)
            if next_state is None:
                continue
            step = {"action": label, "actor": actor}
            new_trace = trace + [step]
            report = checker.evaluate(invariants, next_state)
            failing = [x for x in report["results"] if x["status"] == "fail"]
            unknown = [x for x in report["results"] if x["status"] == "unknown"]
            if unknown:
                raise ValueError("unknown invariant in generated state: " +
                                 ", ".join(x["id"] for x in unknown))
            if failing:
                counterexamples.append({"trace": new_trace, "depth": len(new_trace),
                                        "invariant_ids": [x["id"] for x in failing],
                                        "state": next_state, "evidence_level": "model-only"})
                # BFS: first counterexample is minimal depth.
                return {"schema": 1, "status": "model-counterexample",
                        "counterexamples": counterexamples,
                        "visited_states": len(seen), "transitions_checked": attempts,
                        "truncated": False, "native_target_test": "not-run",
                        "notice": "A model failure is not evidence of a deployed exploit."}
            key = json.dumps(next_state, sort_keys=True, default=str)
            if key not in seen:
                if len(seen) >= max_states:
                    truncated = True
                    break
                seen.add(key)
                queue.append((next_state, new_trace))
        if truncated:
            break
    return {"schema": 1, "status": "bounded-search-incomplete" if truncated else "no-model-counterexample-within-bounds",
            "counterexamples": [], "visited_states": len(seen),
            "transitions_checked": attempts, "truncated": truncated,
            "native_target_test": "not-run",
            "notice": "No model counterexample within bounds does not prove real target safety."}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", required=True)
    p.add_argument("--control", help="patched/non-exploitable model for comparative negative control")
    p.add_argument("--depth", type=int, default=4)
    p.add_argument("--max-states", type=int, default=3000)
    p.add_argument("--out")
    a = p.parse_args(argv)
    try:
        model = json.loads(Path(a.model).read_text(encoding="utf-8"))
        candidate = explore(model, a.depth, a.max_states)
        result = {"candidate": candidate, "controlled": False}
        if a.control:
            control = json.loads(Path(a.control).read_text(encoding="utf-8"))
            result["negative_control"] = explore(control, a.depth, a.max_states)
            result["controlled"] = True
            result["contrast"] = ("candidate-only-model-counterexample"
                if candidate["status"] == "model-counterexample"
                and result["negative_control"]["status"] == "no-model-counterexample-within-bounds"
                else "inconclusive")
        payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if a.out:
            Path(a.out).write_text(payload, encoding="utf-8")
            print(json.dumps({"out": a.out, "candidate_status": candidate["status"]}))
        else:
            print(payload, end="")
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
