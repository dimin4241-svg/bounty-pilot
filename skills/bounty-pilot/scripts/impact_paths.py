#!/usr/bin/env python3
"""Impact-first review queue: reverse from economic/security sinks to upstream entries.

Traversing a state dependency is a *candidate* transition, not executable control flow.
Runtime reachability, actual access controls and measurable impact still need proof.
"""
import argparse
import json
from collections import defaultdict, deque
from pathlib import Path

CLASS_WEIGHTS = {
    "asset-movement": 6, "debt-solvency": 6, "privileged-power": 6,
    "settlement": 5, "price-oracle": 4
}

def rank(graph, max_depth=5, limit=120):
    if max_depth < 1 or max_depth > 12 or limit < 1 or limit > 500:
        raise ValueError("invalid depth/limit")
    symbols = {s["id"]: s for s in graph["symbols"]}
    incoming = defaultdict(list)
    for edge in graph["edges"]:
        if edge["to"] in symbols and edge["from"] in symbols:
            incoming[edge["to"]].append(edge)
    findings = []
    for sink in sorted(symbols.values(), key=lambda s: s["id"]):
        if not sink.get("sinks"):
            continue
        priority = max(CLASS_WEIGHTS.get(x, 0) for x in sink["sinks"])
        queue = deque([(sink["id"], [sink["id"]], [], False)])
        seen = {sink["id"]}
        candidate = []
        while queue:
            cur, path, evidence, uncertain = queue.popleft()
            if symbols[cur].get("entry"):
                candidate.append({"entry": cur, "path": list(reversed(path)),
                                  "edges": list(reversed(evidence)),
                                  "includes_state_candidate_edge": uncertain})
            if len(path) > max_depth:
                continue
            for edge in sorted(incoming[cur], key=lambda e: (e["from"], e["kind"])):
                previous = edge["from"]
                if previous in path:
                    continue
                uncertain_next = uncertain or edge["kind"] == "writer-reader-overlap"
                queue.append((previous, path + [previous], evidence + [edge],
                              uncertain_next))
                # Bound exploration per sink, not just returned top N.
                if len(queue) > 1000:
                    break
            if len(candidate) >= 20:
                break
        # A high-impact sink without a proven public entry is still a review lead.
        if not candidate:
            candidate = [{"entry": None, "path": [sink["id"]], "edges": [],
                          "includes_state_candidate_edge": False}]
        for row in candidate[:20]:
            findings.append({"sink": sink["id"], "impact_families": sink["sinks"],
                             "priority_heuristic": priority,
                             "entry": row["entry"], "path": row["path"],
                             "edges": row["edges"],
                             "confidence": "unverified-possible-sequence"
                             if row["includes_state_candidate_edge"]
                             else "unverified-static-path",
                             "todo": ["confirm source revision/deployment",
                                      "confirm public reachability and authority",
                                      "prove violated invariant and third-party loss",
                                      "execute native PoC and negative control"]})
    findings.sort(key=lambda r: (-r["priority_heuristic"],
                                  r["confidence"] != "unverified-static-path",
                                  r["sink"], r["path"]))
    return {"schema": 1, "method": "backwards-impact-review",
            "ranked": findings[:limit], "total_paths": len(findings),
            "notice": "No entry or sink is asserted exploitable. Static code links and lexical impact labels are triage hints, never severity classifications."}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph", required=True)
    p.add_argument("--max-depth", type=int, default=5)
    p.add_argument("--limit", type=int, default=120)
    p.add_argument("--out")
    a = p.parse_args(argv)
    try:
        report = rank(json.loads(Path(a.graph).read_text(encoding="utf-8")),
                      a.max_depth, a.limit)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if a.out:
        Path(a.out).write_text(payload, encoding="utf-8")
        print(json.dumps({"out": a.out, "paths": len(report["ranked"])}))
    else:
        print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
