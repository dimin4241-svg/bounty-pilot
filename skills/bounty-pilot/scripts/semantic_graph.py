#!/usr/bin/env python3
"""Compiler-aware source graph for Solidity AST and Python AST (stdlib only).

Solidity: explicitly supplied solc standard-json output / Foundry build-info JSON.
Python: ast.parse of git-tracked .py source. This does not execute target code.
Edges are syntactic call references and possible state dependencies, NOT verified
runtime exploit paths. Rust and other stacks remain on the heuristic adapter path.
"""
import argparse
import ast
import json
import subprocess
from collections import defaultdict
from pathlib import Path

SINK_TERMS = {
    "asset-movement": ("transfer", "transferfrom", "safetransfer", "withdraw",
                       "redeem", "release", "burn", "mint", "sweep"),
    "debt-solvency": ("borrow", "liquidat", "repay", "baddebt", "collateral"),
    "privileged-power": ("upgrade", "grantrole", "setowner", "ownership",
                         "authoriz", "admin", "delegate"),
    "settlement": ("claim", "settle", "finaliz", "acknowledge", "processmessage"),
    "price-oracle": ("price", "oracle", "twap", "exchange_rate"),
}
MAX_AST_BYTES = 25_000_000
MAX_NODES = 150_000

def walk_json(node):
    todo = [node]
    count = 0
    while todo:
        x = todo.pop()
        count += 1
        if count > MAX_NODES:
            raise ValueError("compiler AST too large")
        if isinstance(x, dict):
            yield x
            todo.extend(reversed([v for v in x.values() if isinstance(v, (dict, list))]))
        elif isinstance(x, list):
            todo.extend(reversed(x))

def load_solc(path):
    p = Path(path)
    if p.stat().st_size > MAX_AST_BYTES:
        raise ValueError("compiler JSON exceeds size cap")
    data = json.loads(p.read_text(encoding="utf-8"))
    if "output" in data and isinstance(data["output"], dict):
        data = data["output"]
    sources = data.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("Solidity compiler JSON missing sources")
    trees = []
    for filename, desc in sorted(sources.items()):
        if not isinstance(desc, dict):
            continue
        tree = desc.get("ast")
        if isinstance(tree, dict) and tree.get("nodeType") == "SourceUnit":
            trees.append((filename, tree))
    if not trees:
        raise ValueError("no Solidity SourceUnit AST; compile with outputSelection for sources.*.ast")
    return trees

def solidity_symbols(trees):
    decls, parent = {}, {}
    for path, tree in trees:
        for node in walk_json(tree):
            nt = node.get("nodeType")
            if nt == "VariableDeclaration" and node.get("stateVariable"):
                ident = node.get("id")
                if isinstance(ident, int):
                    decls[ident] = str(path) + ":" + str(node.get("name", ident))
            if nt == "ContractDefinition":
                cname = node.get("name", "")
                for child in node.get("nodes", []):
                    if isinstance(child, dict):
                        parent[child.get("id")] = cname
    funcs = {}
    for path, tree in trees:
        for node in walk_json(tree):
            if node.get("nodeType") != "FunctionDefinition":
                continue
            num = node.get("id")
            if not isinstance(num, int):
                continue
            name = node.get("name") or node.get("kind") or "unnamed"
            funcs[num] = {"id": "solc:" + str(num), "path": str(path),
                          "name": str(parent.get(num, "")) + "." + str(name),
                          "declaration": num, "language": "solidity",
                          "entry": node.get("visibility") in ("external", "public"),
                          "visibility": node.get("visibility", "unknown"),
                          "line": None, "source_span": node.get("src"),
                          "modifiers_unverified": [str((m.get("modifierName") or {}).get("name", "unknown"))
                              for m in node.get("modifiers", []) if isinstance(m, dict)],
                          "writes": [], "reads": [],
                          "calls": [], "sinks": [], "source": "compiler-ast"}
    for path, tree in trees:
        for node in walk_json(tree):
            if node.get("nodeType") != "FunctionDefinition" or node.get("id") not in funcs:
                continue
            current = funcs[node["id"]]
            writes, reads, calls, names = set(), set(), set(), {current["name"]}
            # Iterate the function BODY, not signature, modifiers or nested definitions.
            body = node.get("body") or {}
            for x in walk_json(body):
                nt = x.get("nodeType")
                if nt in ("Identifier", "MemberAccess"):
                    rid = x.get("referencedDeclaration")
                    if rid in decls:
                        reads.add(decls[rid])
                if nt == "Assignment":
                    left = x.get("leftHandSide")
                    for lhs in walk_json(left):
                        if lhs.get("referencedDeclaration") in decls:
                            writes.add(decls[lhs["referencedDeclaration"]])
                    if x.get("operator") == "=":
                        # Keep conservative reads: lhs may index a mapping dynamically.
                        pass
                if nt == "UnaryOperation" and x.get("operator") in ("++", "--", "delete"):
                    for lhs in walk_json(x.get("subExpression")):
                        if lhs.get("referencedDeclaration") in decls:
                            writes.add(decls[lhs["referencedDeclaration"]])
                if nt == "FunctionCall":
                    expression = x.get("expression") or {}
                    if expression.get("nodeType") == "MemberAccess" and expression.get("memberName") in ("push", "pop"):
                        for ref in walk_json(expression.get("expression")):
                            if ref.get("referencedDeclaration") in decls:
                                writes.add(decls[ref["referencedDeclaration"]])
                    target = expression.get("referencedDeclaration")
                    if target in funcs:
                        calls.add(funcs[target]["id"])
                    for y in walk_json(expression):
                        name = y.get("memberName") or y.get("name")
                        if isinstance(name, str):
                            names.add(name)
            current["writes"] = sorted(writes)
            current["reads"] = sorted(reads)
            current["calls"] = sorted(calls)
            current["sinks"] = classify(names)
    return list(funcs.values())

def classify(names):
    joined = " ".join(str(n).lower() for n in names)
    return sorted(key for key, words in SINK_TERMS.items()
                  if any(w in joined for w in words))

def attr_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = attr_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""

def py_symbols(root):
    root = Path(root).resolve()
    raw = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                         check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    tracked = raw.stdout.decode("utf-8", "replace").split("\0")
    defs = []
    files = [x for x in tracked if x.endswith(".py") and
             not set(Path(x).parts).intersection(
                 {"test", "tests", "vendor", "node_modules", "build", "dist", ".git", "secrets", "credentials", ".env"})]
    if len(files) > 2000:
        raise ValueError("too many Python files; narrow repository")
    for path in sorted(files):
        p = root / path
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 250_000:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=path)
        except (SyntaxError, UnicodeDecodeError):
            continue
        funcs = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(("", node))
            elif isinstance(node, ast.ClassDef):
                funcs.extend((node.name, child) for child in node.body
                             if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)))
        by_name = {name + "." + n.name if name else n.name for name, n in funcs}
        for owner, n in funcs:
            fullname = owner + "." + n.name if owner else n.name
            writes, reads, calls, names = set(), set(), set(), {fullname}
            for v in ast.walk(n):
                if isinstance(v, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    lhs = v.targets if isinstance(v, ast.Assign) else [v.target]
                    for target in lhs:
                        for item in ast.walk(target):
                            if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and item.value.id in ("self", "cls"):
                                writes.add(item.attr)
                if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id in ("self", "cls"):
                    reads.add(v.attr)
                if isinstance(v, ast.Call):
                    symbol = attr_name(v.func)
                    names.add(symbol)
                    if symbol in by_name:
                        calls.add(path + ":" + symbol)
                    elif owner and symbol in ("self." + x.name for _, x in funcs):
                        calls.add(path + ":" + owner + "." + symbol.split(".", 1)[1])
            defs.append({"id": path + ":" + fullname, "path": path,
                         "name": fullname, "declaration": None,
                         "language": "python", "entry": False,
                         "visibility": "unknown", "line": n.lineno,
                         "writes": sorted(writes), "reads": sorted(reads),
                         "calls": sorted(calls), "sinks": classify(names),
                         "source": "python-ast"})
    return defs

def build(symbols):
    symbols = sorted(symbols, key=lambda x: x["id"])
    known = {x["id"] for x in symbols}
    edges = []
    for s in symbols:
        for callee in s["calls"]:
            if callee in known:
                edges.append({"from": s["id"], "to": callee,
                              "kind": "static-call-reference", "confidence": "ast-reference"})
    readers = defaultdict(list)
    for s in symbols:
        for name in s["reads"]:
            readers[name].append(s["id"])
    for s in symbols:
        for name in s["writes"]:
            for other in readers[name][:150]:
                if other != s["id"]:
                    edges.append({"from": s["id"], "to": other,
                                  "kind": "writer-reader-overlap", "state": name,
                                  "confidence": "candidate-only"})
                if len(edges) >= 7500:
                    break
            if len(edges) >= 7500:
                break
        if len(edges) >= 7500:
            break
    return {"schema": 1, "method": "compiler-ast-plus-python-ast",
            "symbols": symbols, "edges": edges[:7500],
            "semantic_scope": "Solidity compiler-resolved declarations and calls; Python syntax only",
            "reachable_verified": False,
            "warning": "Solidity calls are static references, not full dynamic dispatch. Writer-reader overlap is NOT an executable path. Python entrypoints/calls can be unresolved. No Rust/Move/Cairo semantics are claimed."}

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", help="git checkout for Python AST; optional when --solc provided")
    ap.add_argument("--solc", help="solc output/build-info JSON with sources AST")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if not args.repo and not args.solc:
        ap.error("pass --repo or --solc")
    try:
        symbols = []
        if args.solc:
            symbols += solidity_symbols(load_solc(args.solc))
        if args.repo:
            symbols += py_symbols(args.repo)
        report = build(symbols)
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        ap.error(str(exc))
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(json.dumps({"out": args.out, "symbols": len(report["symbols"]),
                          "edges": len(report["edges"])}))
    else:
        print(payload, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
