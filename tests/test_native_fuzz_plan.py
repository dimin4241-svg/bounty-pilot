"""Minimal native test command generator validation."""
import importlib.util
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "skills/bounty-pilot/scripts/native_fuzz_plan.py"
spec = importlib.util.spec_from_file_location("test_bp_native_plan", p)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class NativePlanTests(unittest.TestCase):
    def data(self):
        return {"cases": [{"id": "claim", "candidate": "test_claim_attack",
                           "control": "test_claim_control"}]}

    def test_foundry_and_cargo_pair(self):
        for framework in ("foundry", "cargo"):
            report = module.plan(self.data(), framework)
            self.assertEqual([x["role"] for x in report["cases"]],
                             ["candidate", "negative-control"])
            self.assertEqual(report["cases"][0]["expected_exit"], 0)
            self.assertNotEqual(report["cases"][0]["argv"],
                                report["cases"][1]["argv"])
            self.assertEqual(report["evidence_level"], "commands-not-run")

    def test_pytest_and_go_pair(self):
        report = module.plan(self.data(), "pytest")
        self.assertIn("pytest", report["cases"][0]["argv"])
        report = module.plan(self.data(), "go")
        self.assertIn("-run", report["cases"][0]["argv"])

    def test_reject_unsafe_or_identical_selectors(self):
        d = self.data()
        d["cases"][0]["candidate"] = "../outside"
        with self.assertRaises(ValueError):
            module.plan(d, "pytest")
        d["cases"][0]["candidate"] = "test_claim_control"
        with self.assertRaises(ValueError):
            module.plan(d, "foundry")
        d["cases"][0]["candidate"] = "test_claim_attack"
        d["cases"][0]["cwd"] = "../.."
        with self.assertRaises(ValueError):
            module.plan(d, "cargo")

if __name__ == "__main__":
    unittest.main()
