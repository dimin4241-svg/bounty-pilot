#!/usr/bin/env python3
"""Conservative heuristic source inventory for stateful security review.

This is NOT a parser, sound call graph, taint analysis, or proof of reachability.
Read the original code before trusting any proposed edge or scenario.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

LANGUAGES = {
    ".sol": "solidity", ".vy": "vyper", ".rs": "rust", ".move": "move",
    ".cairo": "cairo", ".go": "go", ".py": "python", ".ts": "typescript",
    ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
    ".java": "java", ".kt": "kotlin", ".cs": "csharp", ".fc": "func",
    ".func": "func", ".tolk": "tolk",
}
EXCLUDE = {"test", "tests", "mock", "mocks", "fixtures", "target", "node_modules",
           "vendor", "dist", "build", "out", ".git", "generated", "__pycache__"}
SENSITIVE = {".env", "secrets", "secret", "credential", "credentials", "wallet",
             "keystore", "mnemonic"}
PATTERNS = {
    "solidity": r"\b(?:function|modifier)\s+([A-Za-z_]\w*)\s*\(",
    "vyper": r"^\s*def\s+([A-Za-z_]\w*)\s*\(",
    "rust": r"\b(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*\(",
    "move": r"\b(?:entry\s+)?fun\s+([A-Za-z_]\w*)\s*\(",
    "cairo": r"\bfn\s+([A-Za-z_]\w*)\s*\(",
    "go": r"\bfunc\s+(?:\([^\n]*?\)\s*)?([A-Za-z_]\w*)\s*\(",
    "python": r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(",
    "typescript": r"\b(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(",
    "javascript": r"\b(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(",
    "java": r"\b(?:public|private|protected)\s+(?:static\s+)?(?:[\w<>\[\]]+\s+)([A-Za-z_]\w*)\s*\(",
    "kotlin": r"\bfun\s+([A-Za-z_]\w*)\s*\(",
    "csharp": r"\b(?:public|private|internal)\s+(?:static\s+)?(?:[\w<>\[\]]+\s+)([A-Za-z_]\w*)\s*\(",
}
GENERAL_PATTERN = r"\b(?:fn|function|def|fun)\s+([A-Za-z_]\w*)\s*\("
IDENT = re.compile(r"\b[A-Za-z_]\w*\b")
QUALIFIED_WRITE = re.compile(
    r"\b(?:self|this|storage|state|ctx|account|accounts)\.([A-Za-z_]\w*)\s*(?:\+=|-=|=(?!=)|\.set\b|\.write\b)")
ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\+=|-=|=(?!=))")
IGNORE = {"self", "this", "return", "require", "assert", "let", "mut", "var",
          "const", "true", "false", "None", "Some", "Ok", "Err", "result",
          "value", "data", "args", "ctx", "account", "accounts", "i", "j", "x",
          "y", "n", "u256", "uint256", "address", "string", "bool", "msg"}
RISK_TERMS = {
    "asset": ("balance", "transfer", "withdraw", "deposit", "mint", "burn", "claim"),
    "authority": ("owner", "auth", "sign", "delegate", "admin", "upgrade", "revoke"),
    "asynchronous": ("retry", "queue", "watch", "ack", "final", "callback", "reply"),
    "temporal": ("epoch", "time", "slot", "checkpoint", "expire", "deadline"),
    "accounting": ("reward", "debt", "share", "reserve", "fee", "rate", "total"),
}

def _tracked(root):
    proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return sorted(p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p)

def _safe_path(root, relative):
    path = root / relative
    parts = set(Path(relative).parts)
    if parts & EXCLUDE or parts & SENSITIVE or path.is_symlink():
        return False
    if path.suffix.lower() not in LANGUAGES or path.name.lower().startswith(".env"):
        return False
    return path.is_file() and path.stat().st_size <= 250_000

def scan(root, limit=600):
    if not isinstance(limit, int) or not 1 <= limit <= 5000:
        raise ValueError('symbol limit must be between 1 and 5000')
    root = Path(root).resolve()
    files = [p for p in _tracked(root) if _safe_path(root, p)]
    symbols, omitted = [], []
    for relative in files:
        if len(symbols) >= limit:
            omitted.append(relative)
            continue
        path = root / relative
        lang = LANGUAGES[path.suffix.lower()]
        content = path.read_text(encoding="utf-8", errors="replace")
        pattern = re.compile(PATTERNS.get(lang, GENERAL_PATTERN), re.MULTILINE)
        found = list(pattern.finditer(content))
        for index, match in enumerate(found):
            if len(symbols) >= limit:
                omitted.append(relative)
                break
            stop = found[index + 1].start() if index + 1 < len(found) else len(content)
            body = content[match.start():min(stop, match.start() + 12000)]
            words = set(IDENT.findall(body))
            writes = set(QUALIFIED_WRITE.findall(body))
            # Raw assignment is intentionally excluded from graph edges: a local variable
            # named 'balance' must not be mistaken for a write to protocol state.
            local_writes = set(ASSIGN.findall(body))
            reads = {w for w in words if w not in IGNORE and len(w) > 3}
            markers = [key for key, terms in RISK_TERMS.items()
                       if any(t in body.lower() for t in terms)]
            symbols.append({
                "id": relative + ":" + match.group(1) + ":" + str(content.count("\n", 0, match.start()) + 1),
                "path": relative, "language": lang, "symbol": match.group(1),
                "line": content.count("\n", 0, match.start()) + 1,
                "reads_approx": sorted(reads)[:90],
                "qualified_writes_approx": sorted(writes),
                "local_assignments_not_state": sorted(local_writes)[:50],
                "signals": markers,
            })
    # Only propose edges supported by an explicit qualified write on one side.
    # Other protocols need AST- and runtime-specific analysis to establish the edge.
    reverse = {}
    for symbol in symbols:
        for token in symbol["reads_approx"]:
            reverse.setdefault(token, []).append(symbol)
    edges = []
    for src in symbols:
        for token in src["qualified_writes_approx"]:
            for dst in reverse.get(token, []):
                if src["id"] == dst["id"]:
                    continue
                edges.append({"from": src["id"], "to": dst["id"],
                              "reason": "qualified-write / lexical-read overlap",
                              "token": token, "confidence": "low"})
                if len(edges) >= 3000:
                    break
            if len(edges) >= 3000:
                break
        if len(edges) >= 3000:
            break
    sequences = [{"actions": [e["from"], e["to"]], "shared_token": e["token"],
                  "status": "unverified-seed"} for e in edges[:150]]
    return {
        "schema": 1, "source": str(root), "method": "regex-lexical-heuristic",
        "sound": False, "reachability_verified": False, "in_scope_files": len(files),
        "truncated_files": sorted(set(omitted)), "symbols": symbols, "edges": edges,
        "scenario_seeds": sequences,
        "notice": "Lexical inventory only. Validate state ownership, calls, permissions, reachability and effects against actual source and native tests.",
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", help="JSON destination; keep private run artifacts outside the audited repo")
    parser.add_argument("--limit", type=int, default=600)
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > 5000:
        parser.error("--limit must be between 1 and 5000")
    report = scan(args.repo, args.limit)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(json.dumps({"file": args.out, "symbols": len(report["symbols"]),
                          "edges": len(report["edges"]), "heuristic_only": True}))
    else:
        print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
