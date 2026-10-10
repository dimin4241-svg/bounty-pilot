#!/usr/bin/env python3
"""Compute exact-decimal attack feasibility assumptions; never infer profitability.

Input is investigator-supplied scenario, not live chain data. No market simulation.
"""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

def decimal(v):
    if isinstance(v, bool) or isinstance(v, (float, list, dict)) or v is None:
        raise ValueError("amount must be a decimal string or integer")
    try:
        x = Decimal(str(v))
    except InvalidOperation:
        raise ValueError("invalid amount")
    if not x.is_finite() or x < 0:
        raise ValueError("amounts must be finite and nonnegative")
    return x

def assess(case):
    required = {"id", "currency", "gross_extraction", "capital_required",
                "manipulation_cost", "transaction_fees", "slippage_cost",
                "gas_cost", "accessible_liquidity", "victim_at_risk",
                "source_revision", "evidence"}
    if not isinstance(case, dict) or not required.issubset(case):
        raise ValueError("scenario missing required amounts, provenance or identity")
    if not isinstance(case["evidence"], dict) or not case["evidence"]:
        raise ValueError("scenario requires cited assumption provenance")
    keys = ("gross_extraction", "capital_required", "manipulation_cost",
            "transaction_fees", "slippage_cost", "gas_cost",
            "accessible_liquidity", "victim_at_risk")
    amounts = {k: decimal(case[k]) for k in keys}
    gross = amounts["gross_extraction"]
    costs = sum((amounts[k] for k in ("manipulation_cost", "transaction_fees",
                                     "slippage_cost", "gas_cost")), Decimal(0))
    profit = gross - costs
    flags = []
    if gross > amounts["accessible_liquidity"]:
        flags.append("extraction exceeds provided accessible liquidity")
    if gross > amounts["victim_at_risk"]:
        flags.append("extraction exceeds provided victim value at risk")
    if not case.get("capital_available_verified"):
        flags.append("availability of upfront capital is unverified")
    if case.get("real_chain_state_verified") is not True:
        flags.append("on-chain reserves/caps/configuration are unverified")
    if not case.get("unprivileged_reachability_verified"):
        flags.append("unprivileged reachability is unverified")
    if profit <= 0:
        flags.append("net profit is not positive at supplied inputs")
    return {"id": str(case["id"]), "currency": str(case["currency"]),
            "gross_extraction": str(gross), "costs": str(costs),
            "net_before_capital_repayment": str(profit),
            "capital_required": str(amounts["capital_required"]),
            "assumptions": {k: str(v) for k, v in amounts.items()},
            "flags": flags, "source_revision": str(case["source_revision"]),
            "evidence": case["evidence"], "impact_verified": False,
            "severity": "unassessed",
            "notice": "Arithmetic scenario only. No verified exploit, victim loss, protocol solvency, scope, live price, or bounty severity is established."}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--case", required=True)
    p.add_argument("--out")
    a = p.parse_args(argv)
    try:
        result = assess(json.loads(Path(a.case).read_text(encoding="utf-8")))
    except (KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if a.out:
        Path(a.out).write_text(payload, encoding="utf-8")
        print(json.dumps({"out": a.out, "flags": len(result["flags"])}))
    else:
        print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
