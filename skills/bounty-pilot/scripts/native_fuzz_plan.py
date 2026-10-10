#!/usr/bin/env python3
"""Generate paired native fuzz/property-test commands, never execute them.

Read the generated JSON before using scenario_runner.py --allow-exec.
Native project tests/invariants MUST already exist; this does not fabricate them.
"""
import argparse
import json
import re
from pathlib import Path

SUPPORTED = ("foundry", "cargo", "pytest", "go")
SELECTOR = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_:.-]{0,119}$")
PYTEST_NODE = re.compile(r"^[a-zA-Z0-9_./:-]{1,180}$")
PACKAGE = re.compile(r"^[./a-zA-Z0-9_-]{1,100}$")

def _valid(case, stack):
    if not isinstance(case, dict) or not isinstance(case.get("id"), str):
        raise ValueError("case.id required")
    if not SELECTOR.fullmatch(case["id"]):
        raise ValueError("case.id must be a safe identifier")
    candidate, control = case.get("candidate"), case.get("control")
    if not isinstance(candidate, str) or not isinstance(control, str):
        raise ValueError("candidate and control test selectors required")
    pattern = PYTEST_NODE if stack == "pytest" else SELECTOR
    if (not pattern.fullmatch(candidate) or not pattern.fullmatch(control)
            or ".." in candidate or ".." in control or candidate == control):
        raise ValueError("invalid or identical test selectors")
    if not isinstance(case.get("cwd", "."), str) or Path(case.get("cwd", ".")).is_absolute():
        raise ValueError("cwd must be a relative path")
    if ".." in Path(case.get("cwd", ".")).parts:
        raise ValueError("cwd escapes checkout")

def argv_for(stack, selector, package="."):
    if stack == "foundry":
        return ["forge", "test", "--match-test", selector, "-vv"]
    if stack == "cargo":
        return ["cargo", "test", selector, "--", "--exact"]
    if stack == "pytest":
        return ["python3", "-m", "pytest", "-q", selector]
    if stack == "go":
        if not PACKAGE.fullmatch(package) or ".." in package:
            raise ValueError("unsafe go package")
        return ["go", "test", package, "-run", "^" + re.escape(selector) + "$", "-count=1"]
    raise ValueError("supported stacks: " + ", ".join(SUPPORTED))

def plan(spec, stack):
    if stack not in SUPPORTED:
        raise ValueError("unsupported stack")
    if not isinstance(spec, dict) or not isinstance(spec.get("cases"), list) or not spec["cases"]:
        raise ValueError("spec.cases required")
    if len(spec["cases"]) > 20:
        raise ValueError("max 20 paired cases")
    out, ids = [], set()
    for case in spec["cases"]:
        _valid(case, stack)
        if case["id"] in ids:
            raise ValueError("duplicate case id")
        ids.add(case["id"])
        for role, selector in (("candidate", case["candidate"]),
                               ("negative-control", case["control"])):
            out.append({"id": case["id"] + "-" + role, "pair_id": case["id"],
                        "role": role, "cwd": case.get("cwd", "."),
                        "argv": argv_for(stack, selector, case.get("package", ".")),
                        "expected_exit": 0, "timeout_sec": case.get("timeout_sec", 120)})
    return {"cases": out,
            "generated_by": "native_fuzz_plan.py",
            "evidence_level": "commands-not-run",
            "notice": "Selectors must match existing property/invariant tests. Verify test count, assertions, unchanged source and failure behavior; process exit code alone cannot prove security."}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec", required=True)
    p.add_argument("--stack", choices=SUPPORTED, required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    try:
        data = json.loads(Path(a.spec).read_text(encoding="utf-8"))
        generated = plan(data, a.stack)
        target = Path(a.out)
        if target.exists():
            raise ValueError("output exists: refusing overwrite")
        target.write_text(json.dumps(generated, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    print(json.dumps({"out": a.out, "paired_cases": len(generated["cases"]) // 2,
                      "status": "not-executed"}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
