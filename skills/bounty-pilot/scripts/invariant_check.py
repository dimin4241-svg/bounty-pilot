#!/usr/bin/env python3
"""Evaluate explicit, data-only numeric/identity invariants on JSON snapshots.

This checks supplied snapshots, NOT whether the snapshots are reachable or genuine.
No Python eval, external code, arbitrary expressions, or silent float conversion.
"""
import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)

def resolve(snapshot, expression):
    """Resolve {"path":"a.b.0"} or {"const":"3"}; no expression evaluation."""
    if isinstance(expression, dict):
        if set(expression) == {"const"}:
            return expression["const"]
        if set(expression) != {"path"}:
            raise ValueError("expression must have exactly 'path' or 'const'")
        path = expression["path"]
        if not isinstance(path, str) or not path:
            raise ValueError("empty/invalid path")
        value = snapshot
        for key in path.split("."):
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif isinstance(value, list) and key.isdigit() and int(key) < len(value):
                value = value[int(key)]
            else:
                raise ValueError("missing snapshot path: " + path)
        return value
    if isinstance(expression, (str, int, Decimal)) and not isinstance(expression, bool):
        return expression
    raise ValueError("value requires path, const, numeric string or integer")

def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("expected exact decimal number, not bool/array/float")
    try:
        x = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("invalid decimal number")
    if not x.is_finite():
        raise ValueError("non-finite number not supported")
    return x

def check(rule, snapshot):
    kind = rule["kind"]
    if kind == "compare":
        lhs = number(resolve(snapshot, rule["left"]))
        rhs = number(resolve(snapshot, rule["right"]))
        op = rule["op"]
        actions = {"eq": lhs == rhs, "ne": lhs != rhs, "le": lhs <= rhs,
                   "ge": lhs >= rhs, "lt": lhs < rhs, "gt": lhs > rhs}
        if op not in actions:
            raise ValueError("unsupported comparison: " + str(op))
        return actions[op], {"left": str(lhs), "op": op, "right": str(rhs)}
    if kind == "conservation":
        terms = rule["terms"]
        if not isinstance(terms, list) or not terms:
            raise ValueError("conservation requires nonempty terms")
        actual = Decimal(0)
        for t in terms:
            actual += number(resolve(snapshot, t["value"])) * number(t.get("weight", 1))
        expected = number(resolve(snapshot, rule["expected"]))
        return actual == expected, {"actual": str(actual), "expected": str(expected)}
    if kind == "unique":
        values = resolve(snapshot, rule["values"])
        if not isinstance(values, list):
            raise ValueError("unique requires an array")
        as_text = [json.dumps(v, sort_keys=True, default=str) for v in values]
        return len(set(as_text)) == len(as_text), {"count": len(values),
                                                  "distinct": len(set(as_text))}
    raise ValueError("unknown invariant kind: " + str(kind))

def evaluate(spec, snapshot):
    rules = spec.get("invariants")
    if not isinstance(rules, list) or not rules:
        raise ValueError("spec.invariants must be a nonempty list")
    ids, output = set(), []
    for rule in rules:
        ident = rule.get("id")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("invariant IDs must be nonempty and unique")
        ids.add(ident)
        try:
            passed, observed = check(rule, snapshot)
            status = "pass" if passed else "fail"
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            status, observed = "unknown", {"error": str(exc)}
        output.append({"id": ident, "kind": rule.get("kind"),
                       "status": status, "observed": observed,
                       "basis": rule.get("basis", "unspecified")})
    return {"schema": 1, "results": output,
            "summary": {s: sum(x["status"] == s for x in output)
                        for s in ("pass", "fail", "unknown")},
            "evidence_level": "snapshot-consistency-only",
            "notice": "A failed property is a hypothesis until snapshot provenance, specification, reachability and victim impact are established."}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        report = evaluate(read_json(args.spec), read_json(args.snapshot))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(json.dumps({"file": args.out, "summary": report["summary"]}))
    else:
        print(payload, end="")
    return 1 if report["summary"]["fail"] or report["summary"]["unknown"] else 0

if __name__ == "__main__":
    sys.exit(main())
