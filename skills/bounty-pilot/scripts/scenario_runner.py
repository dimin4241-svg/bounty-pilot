#!/usr/bin/env python3
"""Run an explicitly approved paired local test plan without a shell.

This runner does not generate an exploit, attest protocol safety or submit reports.
Default is dry-run. Execute only in disposable, network-isolated and secret-free workspaces.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT_BYTES = 40000
ENV_ALLOWLIST = {"PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "WINDIR"}
SENSITIVE = re.compile(r"(?i)(\b(?:authorization|api[_-]?key|private[_-]?key|secret|password|token)\b\s*[:=]\s*)([^\s,]+)")

def _working_directory(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("cwd must be repository-relative")
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("cwd escapes repository")
    if not resolved.is_dir():
        raise ValueError("cwd is not a directory: " + relative)
    return resolved

def _validate(plan, root):
    cases = plan.get("cases")
    if not isinstance(cases, list) or not cases or len(cases) > 40:
        raise ValueError("plan.cases must contain between 1 and 40 cases")
    pairs, names = {}, set()
    for case in cases:
        ident = case.get("id")
        pair = case.get("pair_id")
        role = case.get("role")
        argv = case.get("argv")
        if not isinstance(ident, str) or not ident or ident in names:
            raise ValueError("missing or duplicate case id")
        names.add(ident)
        if not isinstance(pair, str) or not pair:
            raise ValueError("missing pair_id")
        if role not in ("candidate", "negative-control"):
            raise ValueError("role must be candidate or negative-control")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            raise ValueError("argv must be an array of nonempty strings; shell syntax is not accepted")
        if any("\x00" in x for x in argv):
            raise ValueError("NUL byte in argv")
        timeout = case.get("timeout_sec", 30)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
            raise ValueError("timeout_sec must be 1..120")
        expected = case.get("expected_exit", 0)
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise ValueError("expected_exit must be an integer >= 0")
        _working_directory(root, case.get("cwd", "."))
        pairs.setdefault(pair, set()).add(role)
    if any(roles != {"candidate", "negative-control"} for roles in pairs.values()):
        raise ValueError("each pair_id needs candidate and negative-control experiments")

def _redact(value):
    return SENSITIVE.sub(lambda m: m.group(1) + "<REDACTED>", value)

def _output(blob):
    truncated = len(blob) > MAX_OUTPUT_BYTES
    return _redact(blob[:MAX_OUTPUT_BYTES].decode("utf-8", "replace")), truncated

def execute(plan, root, allow_exec=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("repository not found")
    _validate(plan, root)
    results = []
    for case in plan["cases"]:
        command = case["argv"]
        record = {"id": case["id"], "pair_id": case["pair_id"], "role": case["role"],
                  "argv": command, "executed": False, "expected_exit": case.get("expected_exit", 0)}
        if allow_exec:
            env = {key: value for key, value in os.environ.items() if key in ENV_ALLOWLIST}
            try:
                result = subprocess.run(command, shell=False, cwd=_working_directory(
                    root, case.get("cwd", ".")), env=env, capture_output=True,
                    timeout=case.get("timeout_sec", 30), check=False)
                stdout, stdout_truncated = _output(result.stdout)
                stderr, stderr_truncated = _output(result.stderr)
                record.update({"executed": True, "exit_code": result.returncode,
                               "matched_expected_exit": result.returncode == record["expected_exit"],
                               "stdout": stdout, "stderr": stderr,
                               "truncated": stdout_truncated or stderr_truncated,
                               "timed_out": False})
            except subprocess.TimeoutExpired as exc:
                stdout, _ = _output(exc.stdout or b"")
                stderr, _ = _output(exc.stderr or b"")
                record.update({"executed": True, "timed_out": True,
                               "matched_expected_exit": False, "stdout": stdout, "stderr": stderr})
            except OSError as exc:
                record.update({"executed": False, "error": str(exc),
                               "matched_expected_exit": False})
        results.append(record)
    ok = allow_exec and all(r.get("matched_expected_exit") and not r.get("timed_out")
                            for r in results)
    return {"schema": 1, "mode": "executed" if allow_exec else "dry-run",
            "result": "experiments-conformed" if ok else ("not-executed" if not allow_exec else "incomplete"),
            "cases": results, "pairs": len({x["pair_id"] for x in results}),
            "notice": "Even passing paired experiments only show the named commands met exit expectations. Inspect assertions, source integrity, realistic setup, impact and chain state before calling a finding verified."}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, help="local JSON plan")
    parser.add_argument("--repo", required=True, help="disposable target checkout")
    parser.add_argument("--allow-exec", action="store_true", help="opt in to executing argv; no shell used")
    parser.add_argument("--out", help="write private JSON execution record")
    args = parser.parse_args(argv)
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        report = execute(plan, args.repo, args.allow_exec)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(json.dumps({"file": args.out, "result": report["result"]}))
    else:
        print(payload, end="")
    return 1 if args.allow_exec and report["result"] != "experiments-conformed" else 0

if __name__ == "__main__":
    sys.exit(main())
