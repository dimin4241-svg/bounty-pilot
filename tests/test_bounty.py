import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'skills/bounty-pilot/scripts/bounty.py'
spec = importlib.util.spec_from_file_location('bounty', MODULE)
bounty = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bounty)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        def git(*args):
            subprocess.run(['git', '-C', str(self.repo), *args], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git('init', '-q')
        (self.repo / 'Vault.sol').write_text('contract Vault {}\n')
        git('add', 'Vault.sol')
        git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')
        self.run = self.base / 'run'
        bounty.initialize(self.repo, self.run)

    def candidate(self):
        row = bounty.template()
        row.update(title='Example', root_cause='Example mechanism', affected_paths=['Vault.sol'],
                   attacker_capabilities='Unprivileged caller', preconditions='Example state',
                   impact='Demonstrated property change')
        return row

    def check(self, row):
        bounty.dump(self.run / 'findings.json', [row])
        return bounty.validate(self.run)

    def verified(self):
        row = self.candidate()
        row['status'] = 'verified'
        (self.run / 'poc.py').write_text('assert True\n')
        (self.run / 'log.txt').write_text('example test output\n')
        row['evidence'] = dict(command='python3 poc.py', exit_code=0, poc_path='poc.py',
                               log_path='log.txt', assertion='Example assertion',
                               negative_control='Observed control', source_integrity='Original source')
        return row

    def test_inventory_and_empty_run(self):
        data = json.loads((self.run / 'run.json').read_text())
        self.assertEqual(data['source_candidates'], ['Vault.sol'])
        self.assertFalse(data['dirty'])
        self.assertEqual(bounty.validate(self.run), [])

    def test_never_overwrite(self):
        with self.assertRaises(ValueError):
            bounty.initialize(self.repo, self.run)

    def test_no_output_in_target(self):
        with self.assertRaises(ValueError):
            bounty.initialize(self.repo, self.repo / 'findings')

    def test_verified_needs_artifacts(self):
        row = self.candidate()
        row['status'] = 'verified'
        self.assertTrue(self.check(row))

    def test_complete_record_is_structurally_valid_even_with_unknown_scope(self):
        self.assertEqual(self.check(self.verified()), [])

    def test_traversal_rejected(self):
        row = self.verified()
        (self.base / 'outside').write_text('not allowed')
        row['evidence']['log_path'] = '../outside'
        self.assertTrue(self.check(row))

    def test_symlink_escape_rejected(self):
        row = self.verified()
        outside = self.base / 'outside'
        outside.write_text('not allowed')
        (self.run / 'link').symlink_to(outside)
        row['evidence']['poc_path'] = 'link'
        self.assertTrue(self.check(row))

    def test_boolean_exit_code_rejected(self):
        row = self.verified()
        row['evidence']['exit_code'] = True
        self.assertTrue(self.check(row))

    def test_refutation_needs_reason(self):
        row = self.candidate()
        row['status'] = 'refuted'
        self.assertTrue(self.check(row))

    def test_duplicate_id_rejected(self):
        row = self.candidate()
        bounty.dump(self.run / 'findings.json', [row, row])
        self.assertTrue(bounty.validate(self.run))

    def test_wrong_types_reported(self):
        row = self.candidate()
        row.update(status=[], novelty=[]) 
        self.assertTrue(self.check(row))

    def test_public_novelty_claim_requires_sources(self):
        row = self.candidate()
        row['novelty']['status'] = 'no-public-match-found'
        self.assertTrue(self.check(row))


if __name__ == '__main__':
    unittest.main()
