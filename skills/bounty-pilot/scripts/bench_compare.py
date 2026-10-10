#!/usr/bin/env python3
"""Paired blind-benchmark comparison from bounty.py backtest_score 'scored' records.

No ground truth is fetched; inputs MUST already come from separately sealed hunts.
Unknown cases/versions or mismatched truth are errors, not silently dropped misses.
"""
import argparse
import json
from pathlib import Path

SEV = {"critical", "high"}

def normalize(case):
    if case.get("state") != "scored":
        raise ValueError("each case must be fully scored by the existing blind backtest")
    pin = case.get("pinned_commit")
    ident = case.get("case")
    if not isinstance(pin, str) or not pin or not isinstance(ident, str) or not ident:
        raise ValueError("scored backtest requires name and pinned commit")
    truth = {}
    found = set()
    for x in case.get("rediscovered", []):
        key = x["id"]
        if key in truth:
            raise ValueError("duplicated ground-truth ID")
        truth[key] = x["severity"]
        found.add(key)
    for x in case.get("missed", []):
        key = x["id"]
        if key in truth:
            raise ValueError("duplicated ground-truth ID")
        truth[key] = x["severity"]
    if case.get("published_findings") != len(truth):
        raise ValueError("published finding count differs from scored truth")
    if not case.get("sealed_at"):
        raise ValueError("unsealed report")
    return (ident, pin), truth, found

def compare(baseline, candidate):
    if not isinstance(baseline, list) or not isinstance(candidate, list):
        raise ValueError("baseline/candidate must be JSON arrays of fully scored cases")
    def index(rows):
        result = {}
        for row in rows:
            key, truth, found = normalize(row)
            if key in result:
                raise ValueError("duplicate case and commit")
            result[key] = (truth, found)
        return result
    before, after = index(baseline), index(candidate)
    if set(before) != set(after) or not before:
        raise ValueError("baseline and candidate must contain same nonempty pinned cases")
    per_case, wins, losses, ties = [], 0, 0, 0
    total, n_before, n_after = 0, 0, 0
    for key in sorted(before):
        bt, bf = before[key]
        ct, cf = after[key]
        if bt != ct:
            raise ValueError("ground truth/severities differ between paired cases: " + key[0])
        severe = {ident for ident, severity in bt.items() if severity in SEV}
        found_before = bf & severe
        found_after = cf & severe
        total += len(severe)
        n_before += len(found_before)
        n_after += len(found_after)
        delta = len(found_after) - len(found_before)
        wins += delta > 0
        losses += delta < 0
        ties += delta == 0
        per_case.append({"case": key[0], "commit": key[1],
                         "high_critical_total": len(severe),
                         "baseline_found": len(found_before),
                         "candidate_found": len(found_after),
                         "gained_ids": sorted(found_after - found_before),
                         "lost_ids": sorted(found_before - found_after)})
    return {"schema": 1, "method": "paired-blind-scored-counts",
            "cases": len(per_case), "high_critical_truth": total,
            "baseline_rediscovered": n_before, "candidate_rediscovered": n_after,
            "delta": n_after - n_before, "case_wins": wins, "case_losses": losses,
            "case_ties": ties, "details": per_case,
            "precision_measured": False, "payout_prediction": False,
            "notice": "A positive result is not yet robust evidence of improvement: blinded/held-out selection, contamination, tool budget, model, runtime and manual decision quality must be controlled. No true-negative data or private duplicate visibility."}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", required=True, help="JSON array of prior scored backtest results")
    p.add_argument("--candidate", required=True, help="JSON array of 0.9 scored backtest results")
    p.add_argument("--out")
    a = p.parse_args(argv)
    try:
        b = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
        c = json.loads(Path(a.candidate).read_text(encoding="utf-8"))
        report = compare(b, c)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    body = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_text(body, encoding="utf-8")
        print(json.dumps({"out": a.out, "delta": report["delta"]}))
    else:
        print(body, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
