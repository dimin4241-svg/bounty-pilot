#!/usr/bin/env python3
"""Create deliberately failing native-test skeletons; never fabricate passing PoCs."""
import argparse
import json
import re
from pathlib import Path

KINDS = {"solidity": ".t.sol", "rust": ".rs", "python": ".py", "go": "_test.go"}
def safe_id(label):
    ident = re.sub(r"[^a-zA-Z0-9_]", "_", label.strip()).strip("_").lower()[:55]
    if not ident:
        raise ValueError("finding id must contain letters or digits")
    if ident[0].isdigit():
        ident = "case_" + ident
    return ident

def scaffold(finding, stack):
    if stack not in KINDS:
        raise ValueError("supported: solidity, rust, python, go")
    required = ("id", "invariant", "entry_point", "attacker_capabilities", "steps")
    if any(not finding.get(x) for x in required):
        raise ValueError("finding needs id, invariant, entry_point, attacker_capabilities and steps")
    if not isinstance(finding["steps"], list) or not all(isinstance(x, str) for x in finding["steps"]):
        raise ValueError("steps must be a nonempty array of strings")
    ident = safe_id(str(finding["id"]))
    if stack == "solidity":
        data = '''// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.20;
import {Test} from "forge-std/Test.sol";

// TODO: replace with the actual deployed/unmodified target and pinned dependencies.
contract BountyPilotScenario is Test {
    function test_candidate_''' + ident + '''() public {
        // TODO: implement reachable ordered actions and quantify impact.
        assertTrue(false, "TODO: no evidence; fill candidate assertions");
    }

    function test_negative_control_''' + ident + '''() public {
        // TODO: same path with a safe input; assert absence of the violation.
        assertTrue(false, "TODO: no evidence; fill negative-control assertions");
    }
}
'''
    elif stack == "rust":
        data = '''// TODO: import the original target crate and build realistic actors/state.
#[test]
fn candidate_''' + ident + '''() {
    // TODO: execute attack sequence with the native runtime.
    panic!("TODO: candidate invariant and impact assertions not implemented");
}

#[test]
fn negative_control_''' + ident + '''() {
    // TODO: execute the comparable protected scenario.
    panic!("TODO: negative-control assertions not implemented");
}
'''
    elif stack == "python":
        data = '''"""TODO: import the original service, fixtures and real dependencies."""
def test_candidate_''' + ident + '''():
    # TODO: reachable setup, ordered actions, measurable victim effect.
    raise AssertionError("TODO: candidate not implemented")

def test_negative_control_''' + ident + '''():
    # TODO: protected counterpart, with real checks.
    raise AssertionError("TODO: negative control not implemented")
'''
    else:
        camel = "".join(p[:1].upper() + p[1:] for p in ident.split("_"))
        data = '''package scenario_test

import "testing"

// TODO: use the target package's native test setup and actual process semantics.
func TestCandidate''' + camel + '''(t *testing.T) {
    t.Fatal("TODO: candidate evidence not implemented")
}

func TestNegativeControl''' + camel + '''(t *testing.T) {
    t.Fatal("TODO: negative-control evidence not implemented")
}
'''
    notes = {"finding_id": finding["id"], "stack": stack,
             "entry_point": finding["entry_point"], "invariant": finding["invariant"],
             "attacker_capabilities": finding["attacker_capabilities"],
             "steps": finding["steps"], "status": "incomplete-test-skeleton",
             "source_integrity": "target must remain unmodified",
             "verification": "not-run-not-proven"}
    return ident, data, notes

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--finding", required=True, help="JSON hypothesis with reachable steps")
    p.add_argument("--stack", required=True, choices=sorted(KINDS))
    p.add_argument("--out-dir", required=True, help="private output outside target checkout")
    args = p.parse_args(argv)
    try:
        finding = json.loads(Path(args.finding).read_text(encoding="utf-8"))
        ident, code, notes = scaffold(finding, args.stack)
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        basename = "bp_" + ident
        path = out / (basename + KINDS[args.stack])
        meta = out / (basename + ".json")
        # Exclusive creation means we never silently erase test work.
        if path.exists() or meta.exists():
            raise ValueError("output already exists; choose a new output directory")
        with path.open("x", encoding="utf-8") as w:
            w.write(code)
        with meta.open("x", encoding="utf-8") as w:
            json.dump(notes, w, indent=2, ensure_ascii=False)
            w.write("\n")
        print(json.dumps({"template": str(path), "metadata": str(meta),
                          "status": "incomplete-test-skeleton"}))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
