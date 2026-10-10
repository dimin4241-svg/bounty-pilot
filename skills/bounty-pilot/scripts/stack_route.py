#!/usr/bin/env python3
"""Evidence-labelled, conservative multi-stack routing. No code is executed."""
import argparse
import json
import subprocess
from pathlib import Path

ADAPTERS = {
    "solidity-evm": "lenses.md",
    "rust-native": "adapters/rust-native.md",
    "rust-solana": "adapters/rust-solana.md",
    "rust-cosmwasm": "adapters/rust-cosmwasm.md",
    "move": "adapters/move.md",
    "cairo-starknet": "adapters/cairo.md",
    "go": "adapters/go.md",
    "web-backend": "adapters/web-backend.md",
}
LENSES = {
    "solidity-evm": ["impact-first", "privileged-path", "accounting", "business-logic", "temporal-logic"],
    "rust-native": ["impact-first", "recovery-failure", "semantic-mismatch", "business-logic"],
    "rust-solana": ["impact-first", "anchor-account", "privileged-path", "business-logic", "temporal-logic"],
    "rust-cosmwasm": ["business-logic", "temporal-logic", "integration-auth"],
    "move": ["privileged-path", "business-logic", "temporal-logic"],
    "cairo-starknet": ["privileged-path", "business-logic", "temporal-logic"],
    "go": ["recovery-failure", "business-logic", "semantic-mismatch"],
    "web-backend": ["privileged-path", "recovery-failure", "semantic-mismatch"],
}

def route(repo):
    root = Path(repo).resolve()
    raw = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                         check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    files = sorted(x for x in raw.stdout.decode("utf-8", "replace").split("\0") if x)
    lower = {x.lower() for x in files}
    matches, warnings = {}, []
    def add(stack, evidence):
        matches.setdefault(stack, set()).add(evidence)
    if any(x.endswith((".sol", ".vy")) for x in lower) or any(
            Path(x).name in ("foundry.toml", "hardhat.config.ts", "hardhat.config.js") for x in lower):
        add("solidity-evm", "solidity/vyper source or EVM build manifest")
    if any(Path(x).name == "move.toml" for x in lower) or any(x.endswith(".move") for x in lower):
        add("move", "Move.toml or .move source (exact VM must be confirmed)")
    if any(Path(x).name == "scarb.toml" for x in lower) or any(x.endswith(".cairo") for x in lower):
        add("cairo-starknet", "Scarb.toml or Cairo source (deployment type unconfirmed)")
    if any(Path(x).name == "go.mod" for x in lower) or any(x.endswith(".go") for x in lower):
        add("go", "Go manifest or .go source")
    if any(x.endswith((".ts", ".tsx", ".js", ".jsx", ".py")) for x in lower):
        add("web-backend", "TS/JS/Python detected (may be frontend-only; confirm entrypoints)")
    cargo = [x for x in files if Path(x).name.lower() == "cargo.toml"]
    anchors = [x for x in lower if Path(x).name == "anchor.toml"]
    if anchors:
        for x in anchors:
            add("rust-solana", x)
    for manifest in cargo:
        path = root / manifest
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 200000:
            warnings.append("skipped unreadable/oversized Rust manifest: " + manifest)
            continue
        data = path.read_text(encoding="utf-8", errors="replace").lower()
        solana = any(s in data for s in ("anchor-lang", "solana-program", "solana-sdk", "anchor-spl"))
        cosmwasm = any(s in data for s in ("cosmwasm-std", "cw-storage-plus", "cw-multi-test"))
        if solana:
            add("rust-solana", manifest + " contains Solana/Anchor dependency")
        if cosmwasm:
            add("rust-cosmwasm", manifest + " contains CosmWasm dependency")
        if not solana and not cosmwasm:
            add("rust-native", manifest + " (no Solana/CosmWasm dependency in this manifest)")
    if any(x.endswith(".rs") for x in lower) and not cargo:
        warnings.append("Rust source without tracked Cargo.toml: runtime unknown")
    stacks = [{"stack": s, "evidence": sorted(ev), "adapter": ADAPTERS[s],
               "recommended_lenses": LENSES[s]} for s, ev in sorted(matches.items())]
    if len(stacks) > 1:
        warnings.append("Mixed-language/repo detection is not component ownership. Inspect real process and trust boundaries.")
    report = {"schema": 1, "method": "manifest-and-extension-heuristics",
            "stacks": stacks, "warnings": warnings, "native_execution_verified": False,
            "suggested_cross_stack_lenses": ["semantic-mismatch", "recovery-failure", "composition"]
            if len(stacks) > 1 else [],
            "notice": "Routing only. A file extension does not prove a runtime, deployment or coverage."}
    report["prioritization"] = prioritize(report)
    return report

def prioritize(route_report, budget=6):
    """Rank diverse lenses from *evidence of stack*, never predicted vulnerability odds."""
    if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= 19:
        raise ValueError("budget must be 1..19")
    base = {"impact-first": 8, "privileged-path": 6, "coverage-gap": 5, "business-logic": 5,
            "temporal-logic": 3, "composition": 3, "semantic-mismatch": 2,
            "recovery-failure": 2, "integration-auth": 2, "accounting": 2,
            "external-call": 2, "economics": 2, "liveness": 2,
            "anchor-account": 0, "upgrade": 1, "live-reality": 1,
            "delta": 1, "upstream-diff": 1, "seam": 1}
    reasons = {name: ["general baseline"] for name in base}
    for stack in route_report["stacks"]:
        for lens in stack["recommended_lenses"]:
            base[lens] += 5
            reasons[lens].append("manifest hint: " + stack["stack"])
    if len(route_report["stacks"]) > 1:
        for name in ("semantic-mismatch", "recovery-failure", "composition"):
            base[name] += 4
            reasons[name].append("multiple language/runtime candidates")
    # Anchor's account model must never be force-selected on ordinary Rust.
    if "rust-solana" not in {x["stack"] for x in route_report["stacks"]}:
        base.pop("anchor-account")
    ranked = sorted(base, key=lambda name: (-base[name], name))
    return {"budget": budget, "selected": ranked[:budget],
            "not_selected": ranked[budget:],
            "rationale": {x: reasons[x] for x in ranked[:budget]},
            "disclaimer": "Heuristic reading allocation, not measured bug yield or audited code coverage."}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--out")
    args = p.parse_args(argv)
    try:
        report = route(args.repo)
    except (OSError, subprocess.SubprocessError) as exc:
        p.error(str(exc))
    body = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
        print(json.dumps({"out": args.out, "stacks": [x["stack"] for x in report["stacks"]]}))
    else:
        print(body, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
