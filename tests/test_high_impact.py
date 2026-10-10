"""Tests for compiler AST paths, bounded state exploration, cost and blind A/B."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/bounty-pilot/scripts"

def module(name):
    spec = importlib.util.spec_from_file_location("test_bp_09_" + name,
                                                  SCRIPTS / (name + ".py"))
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    return imported

semantic = module("semantic_graph")
impact = module("impact_paths")
fuzz = module("scenario_fuzz")
cost = module("impact_feasibility")
bench = module("bench_compare")
bounty = module("bounty")

def solc_fixture():
    return {"output": {"sources": {"src/Vault.sol": {"ast": {
        "nodeType": "SourceUnit", "nodes": [{
            "nodeType": "ContractDefinition", "name": "Vault", "id": 1,
            "nodes": [
                {"nodeType": "VariableDeclaration", "id": 10,
                 "name": "assets", "stateVariable": True},
                {"nodeType": "FunctionDefinition", "id": 100,
                 "name": "deposit", "visibility": "external",
                 "body": {"nodeType": "Block", "statements": [
                     {"nodeType": "Assignment", "operator": "=",
                      "leftHandSide": {"nodeType": "Identifier", "referencedDeclaration": 10},
                      "rightHandSide": {"nodeType": "Literal", "value": "10"}}]}},
                {"nodeType": "FunctionDefinition", "id": 101,
                 "name": "withdraw", "visibility": "external",
                 "body": {"nodeType": "Block", "statements": [
                     {"nodeType": "Identifier", "referencedDeclaration": 10},
                     {"nodeType": "FunctionCall",
                      "expression": {"nodeType": "MemberAccess", "memberName": "transfer"},
                      "arguments": []}]}},
                {"nodeType": "FunctionDefinition", "id": 102,
                 "name": "internalTransfer", "visibility": "internal",
                 "body": {"nodeType": "Block", "statements": [
                     {"nodeType": "FunctionCall",
                      "expression": {"nodeType": "Identifier",
                                     "referencedDeclaration": 101,
                                     "name": "withdraw"},
                      "arguments": []}]}}
            ]}]}}}}}

def model(broken=True):
    return {"actors": ["alice", "bob"],
            "state": {"assets": "8", "debt": "8", "credit": "0"},
            "invariants": [{"id": "solvency", "kind": "compare",
                            "left": {"path": "assets"}, "op": "ge",
                            "right": {"path": "debt"}}],
            "actions": [
                {"name": "deposit-{actor}", "actor": "*",
                 "effects": [{"op": "add", "path": "assets", "value": "2"},
                             {"op": "add", "path": "credit", "value": "1"}]},
                {"name": "redeem-{actor}", "actor": "*",
                 "guards": [{"path": "credit", "op": "ge", "value": "1"}],
                 "effects": [{"op": "sub", "path": "assets",
                              "value": "3" if broken else "2"},
                             {"op": "sub", "path": "credit", "value": "1"}]}
            ]}

class SemanticTests(unittest.TestCase):
    def test_solidity_compiler_resolved_state_and_calls(self):
        with tempfile.TemporaryDirectory() as t:
            file = Path(t) / "build-info.json"
            file.write_text(json.dumps(solc_fixture()))
            trees = semantic.load_solc(file)
            g = semantic.build(semantic.solidity_symbols(trees))
            self.assertEqual(len(g["symbols"]), 3)
            symbols = {x["id"]: x for x in g["symbols"]}
            self.assertTrue(symbols["solc:100"]["entry"])
            self.assertIn("src/Vault.sol:assets", symbols["solc:100"]["writes"])
            self.assertIn("src/Vault.sol:assets", symbols["solc:101"]["reads"])
            self.assertIn("asset-movement", symbols["solc:101"]["sinks"])
            self.assertTrue(any(e["kind"] == "writer-reader-overlap" and
                                e["from"] == "solc:100" and e["to"] == "solc:101"
                                for e in g["edges"]))
            self.assertTrue(any(e["kind"] == "static-call-reference" and
                                e["from"] == "solc:102" and e["to"] == "solc:101"
                                for e in g["edges"]))
            ranked = impact.rank(g)
            self.assertTrue(any(row["entry"] == "solc:100" for row in ranked["ranked"]))
            self.assertFalse(g["reachable_verified"])

    def test_reject_compiler_json_without_ast(self):
        with tempfile.TemporaryDirectory() as t:
            file = Path(t) / "not-ast.json"
            file.write_text(json.dumps({"sources": {"a.sol": {"id": 3}}}))
            with self.assertRaises(ValueError):
                semantic.load_solc(file)

    def test_python_parser_does_not_execute_untrusted_source(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            marker = root / "execution-marker"
            (root / "service.py").write_text(
                "from pathlib import Path\n"
                "Path(" + repr(str(marker)) + ").write_text('EXECUTED')\n"
                "class Vault:\n"
                "  def repay(self):\n"
                "    self.debt = 1\n"
                "  def borrow(self):\n"
                "    return self.debt\n")
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            g = semantic.build(semantic.py_symbols(root))
            self.assertFalse(marker.exists())
            self.assertTrue(any("debt" in x["writes"] for x in g["symbols"]))
            self.assertTrue(any("debt" in x["reads"] for x in g["symbols"]))

    def test_impact_path_has_no_assumed_entry_or_severity(self):
        graph = semantic.build([{"id": "one", "name": "withdraw", "sinks": ["asset-movement"],
                                "entry": False, "writes": [], "reads": [],
                                "calls": []}])
        ranked = impact.rank(graph)
        self.assertIsNone(ranked["ranked"][0]["entry"])
        self.assertEqual(ranked["ranked"][0]["confidence"], "unverified-no-public-entry")
        self.assertIn("never severity", ranked["notice"])

    def test_bundle_high_impact_and_compiler_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkout = root / "repo"
            checkout.mkdir()
            subprocess.run(["git", "init", "-q", str(checkout)], check=True)
            (checkout / "a.py").write_text("def borrow():\n    return 1\n")
            subprocess.run(["git", "-C", str(checkout), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(checkout), "-c", "user.name=Test",
                            "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "init"], check=True)
            result = bounty.bundle(checkout, root / "private", ["high-impact"])
            self.assertEqual([x["lens"] for x in result["bundles"]],
                             list(bounty.HIGH_IMPACT_LENSES))
            text = (root / "private/bundles/impact-first-bundle.md").read_text()
            self.assertIn("High-impact workflow", text)
            self.assertIn("Impact-first agent", text)
            compiled = bounty.impact_plan(repo=checkout, out=root / "private")
            self.assertGreaterEqual(compiled["symbols"], 1)
            self.assertTrue((root / "private/impact-paths.json").exists())

class StatefulTests(unittest.TestCase):
    def test_detects_shortest_two_step_model_failure(self):
        result = fuzz.explore(model(), depth=5, max_states=500)
        self.assertEqual(result["status"], "model-counterexample")
        self.assertEqual(result["counterexamples"][0]["depth"], 2)
        self.assertEqual(result["counterexamples"][0]["invariant_ids"], ["solvency"])
        self.assertEqual(result["native_target_test"], "not-run")

    def test_protected_model_remains_clean_within_bounds(self):
        result = fuzz.explore(model(False), depth=4)
        self.assertEqual(result["status"], "no-model-counterexample-within-bounds")

    def test_invalid_initial_property_rejected(self):
        case = model()
        case["state"]["assets"] = "0"
        with self.assertRaises(ValueError):
            fuzz.explore(case)

    def test_empty_effect_and_untrusted_expression_rejected(self):
        bad = model()
        bad["actions"][0]["effects"] = [{"op": "eval", "path": "assets",
                                       "value": "__import__('os')"}]
        with self.assertRaises(ValueError):
            fuzz.explore(bad)

    def test_state_budget_and_depth_are_bounded(self):
        with self.assertRaises(ValueError):
            fuzz.explore(model(), depth=100)
        out = fuzz.explore(model(False), depth=8, max_states=1)
        self.assertTrue(out["truncated"])

class FeasibilityTests(unittest.TestCase):
    def case(self):
        return {"id": "one", "currency": "USD", "gross_extraction": "20",
                "capital_required": "100", "manipulation_cost": "2",
                "transaction_fees": "1", "slippage_cost": "0.5", "gas_cost": "0.1",
                "accessible_liquidity": "30", "victim_at_risk": "40",
                "source_revision": "hash", "evidence": {"block": "1234"}}

    def test_exact_values_without_invented_severity(self):
        out = cost.assess(self.case())
        self.assertEqual(out["net_before_capital_repayment"], "16.4")
        self.assertEqual(out["severity"], "unassessed")
        self.assertFalse(out["impact_verified"])
        self.assertGreater(len(out["flags"]), 1)

    def test_overextraction_flag_and_no_float(self):
        sample = self.case()
        sample["gross_extraction"] = "100"
        self.assertTrue(any("liquidity" in f for f in cost.assess(sample)["flags"]))
        sample["gross_extraction"] = 1.2
        with self.assertRaises(ValueError):
            cost.assess(sample)

class BlindBenchmarkTests(unittest.TestCase):
    def scored(self, found):
        truth = {"id": "H-1", "severity": "high"}
        return {"state": "scored", "case": "pinned-vault", "pinned_commit": "c0ffee",
                "sealed_at": "2026-10-10T12:00:00Z", "published_findings": 1,
                "rediscovered": [truth] if found else [],
                "missed": [] if found else [truth]}

    def test_pair_counts_real_highs(self):
        out = bench.compare([self.scored(False)], [self.scored(True)])
        self.assertEqual(out["delta"], 1)
        self.assertEqual(out["high_critical_truth"], 1)
        self.assertFalse(out["payout_prediction"])

    def test_mismatched_truth_or_unscored_refused(self):
        bad = self.scored(True)
        bad["rediscovered"][0]["severity"] = "medium"
        with self.assertRaises(ValueError):
            bench.compare([self.scored(False)], [bad])
        with self.assertRaises(ValueError):
            bench.compare([self.scored(False)], [{"state": "awaiting-decisions"}])

if __name__ == "__main__":
    unittest.main()
