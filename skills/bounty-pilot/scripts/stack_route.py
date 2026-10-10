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
    "solidity-evm": ["privileged-path", "accounting", "business-logic", "temporal-logic"],
    "rust-native": ["recovery-failure", "semantic-mismatch", "business-logic"],
    "rust-solana": ["anchor-account", "privileged-path", "business-logic", "temporal-logic"],
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
    return {"schema": 1, "method": "manifest-and-extension-heuristics",
            "stacks": stacks, "warnings": warnings, "native_execution_verified": False,
            "suggested_cross_stack_lenses": ["semantic-mismatch", "recovery-failure", "composition"]
            if len(stacks) > 1 else [],
            "notice": "Routing only. A file extension does not prove a runtime, deployment or coverage."}

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
