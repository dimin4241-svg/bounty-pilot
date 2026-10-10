#!/usr/bin/env python3
"""Rank *heuristic* coverage gaps from a state_graph inventory and reviewer records."""
import argparse
import json
from pathlib import Path

def gaps(graph, reviewed):
    symbols = graph.get("symbols", [])
    edges = graph.get("edges", [])
    if graph.get("method") != "regex-lexical-heuristic":
        raise ValueError("expected state_graph heuristic inventory")
    weight = {}
    for edge in edges:
        weight[edge["from"]] = weight.get(edge["from"], 0) + 1
        weight[edge["to"]] = weight.get(edge["to"], 0) + 1
    rows = []
    for item in symbols:
        if item["id"] in reviewed or item["path"] in reviewed:
            continue
        signals = item.get("signals", [])
        rows.append({"id": item["id"], "path": item["path"],
                     "symbol": item["symbol"], "line": item["line"],
                     "language": item["language"], "priority_heuristic":
                         min(100, 10 + 7 * len(signals) + 3 * min(weight.get(item["id"], 0), 12)),
                     "signals": signals, "edges": weight.get(item["id"], 0)})
    rows.sort(key=lambda row: (-row["priority_heuristic"], row["path"], row["line"]))
    return {
        "schema": 1, "method": "heuristic-coverage-ranking",
        "reviewed_entries": len(reviewed), "unreviewed_symbols": len(rows),
        "unreviewed": rows,
        "warning": "A reviewed label is self-reported, not evidence of actual path coverage. Priority is not vulnerability likelihood."
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True)
    parser.add_argument("--reviewed", help="JSON list of examined symbol IDs or repository-relative paths")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    graph = json.loads(Path(args.graph).read_text(encoding="utf-8"))
    reviewed = json.loads(Path(args.reviewed).read_text(encoding="utf-8")) if args.reviewed else []
    if not isinstance(reviewed, list) or not all(isinstance(x, str) for x in reviewed):
        parser.error("--reviewed must be a JSON string array")
    result = gaps(graph, set(reviewed))
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(json.dumps({"file": args.out, "unreviewed_symbols": result["unreviewed_symbols"]}))
    else:
        print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
