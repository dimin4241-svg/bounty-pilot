import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bounty = load('bounty', 'skills/bounty-pilot/scripts/bounty.py')
keccak = load('bp_keccak', 'skills/bounty-pilot/scripts/keccak.py')


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeNode:
    """Answers JSON-RPC from a dict, and records what was asked."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, request, timeout=None):
        body = json.loads(request.data.decode('utf-8'))
        self.calls.append((body['method'], body['params']))
        key = body['method']
        value = self.answers[key]
        if callable(value):
            value = value(body['params'])
        return FakeResponse({'jsonrpc': '2.0', 'id': body['id'], 'result': value})


def git(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def commit(repo, message):
    git(repo, 'add', '-A')
    git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
        'commit', '-qm', message)


class KeccakTests(unittest.TestCase):
    def test_known_digests(self):
        self.assertEqual(keccak.keccak256('').hex(),
                         'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470')
        self.assertEqual(keccak.keccak256('abc').hex(),
                         '4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45')

    def test_digest_crosses_the_rate_boundary(self):
        # 200 bytes needs two absorb blocks at a 136-byte rate
        self.assertEqual(len(keccak.keccak256(b'a' * 200)), 32)
        self.assertNotEqual(keccak.keccak256(b'a' * 200), keccak.keccak256(b'a' * 136))

    def test_selectors(self):
        self.assertEqual(keccak.selector('transfer(address,uint256)'), '0xa9059cbb')
        self.assertEqual(keccak.selector('balanceOf(address)'), '0x70a08231')
        self.assertEqual(keccak.selector('totalSupply()'), '0x18160ddd')

    def test_selector_rejects_non_signature(self):
        with self.assertRaises(ValueError):
            keccak.selector('not a signature')

    def test_proxy_slots_match_the_published_constants(self):
        slots = bounty.proxy_slots()
        self.assertEqual(slots['eip1967-implementation'],
                         '0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc')
        self.assertEqual(slots['eip1967-beacon'],
                         '0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50')
        self.assertEqual(slots['eip1967-admin'],
                         '0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103')


class BytecodeTests(unittest.TestCase):
    def setUp(self):
        self.code = bytes.fromhex('6080604052') + b'\xab' * 20
        blob = b'\xa2dipfsX"\x12 ' + b'\x11' * 32 + b'dsolcC\x00\x08\x14'
        self.trailer = blob + len(blob).to_bytes(2, 'big')
        self.live = '0x' + (self.code + self.trailer).hex()

    def test_a_trailing_length_alone_is_not_stripped(self):
        # Reported case: two unrelated runtimes both ending in 0x0002 compared as exact,
        # because the tail length was trusted without checking the tail is solc metadata.
        left, right = '0x6001aabb0002', '0x6001ccdd0002'
        self.assertEqual(bounty.strip_metadata(left)[1], 0)
        result = bounty.compare_bytecode(left, right)
        self.assertNotEqual(result['status'], 'exact')
        self.assertEqual(result['differing_bytes'], 2)

    def test_a_cbor_sized_tail_without_a_solc_marker_is_not_stripped(self):
        blob = b'\xa2' + b'\x41' * 40          # CBOR map header, no solc/ipfs/bzzr marker
        raw = b'\x60\x01' + blob + len(blob).to_bytes(2, 'big')
        self.assertEqual(bounty.strip_metadata('0x' + raw.hex())[1], 0)

    def test_a_tail_that_is_not_a_cbor_map_is_not_stripped(self):
        blob = b'\x01solc' + b'\x00' * 40       # right size and marker, wrong header byte
        raw = b'\x60\x01' + blob + len(blob).to_bytes(2, 'big')
        self.assertEqual(bounty.strip_metadata('0x' + raw.hex())[1], 0)

    def test_metadata_is_stripped(self):
        body, stripped = bounty.strip_metadata(self.live)
        self.assertEqual(body, self.code)
        self.assertEqual(stripped, len(self.trailer))

    def test_identical_builds_are_exact(self):
        self.assertEqual(bounty.compare_bytecode(self.live, self.live)['status'], 'exact')

    def test_differing_metadata_only_is_still_exact(self):
        other_blob = b'\xa2dipfsX"\x12 ' + b'\x22' * 32 + b'dsolcC\x00\x08\x14'
        other = '0x' + (self.code + other_blob + len(other_blob).to_bytes(2, 'big')).hex()
        self.assertEqual(bounty.compare_bytecode(self.live, other)['status'], 'exact')

    def test_same_length_different_body_is_partial_not_exact(self):
        mutated = bytearray(self.code)
        mutated[3] ^= 0xFF
        other = '0x' + (bytes(mutated) + self.trailer).hex()
        result = bounty.compare_bytecode(self.live, other)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['differing_bytes'], 1)

    def test_different_length_is_mismatch(self):
        other = '0x' + (self.code[:-4] + self.trailer).hex()
        self.assertEqual(bounty.compare_bytecode(self.live, other)['status'], 'mismatch')

    def test_no_code_is_mismatch(self):
        self.assertEqual(bounty.compare_bytecode('0x', self.live)['status'], 'mismatch')

    def test_artifact_reading_supports_foundry_and_hardhat(self):
        with tempfile.TemporaryDirectory() as temp:
            foundry = Path(temp) / 'f.json'
            foundry.write_text(json.dumps({'deployedBytecode': {'object': '0xdead'}}))
            self.assertEqual(bounty.read_artifact(foundry), ('0xdead', 'deployedBytecode'))
            hardhat = Path(temp) / 'h.json'
            hardhat.write_text(json.dumps({'deployedBytecode': '0xbeef'}))
            self.assertEqual(bounty.read_artifact(hardhat), ('0xbeef', 'deployedBytecode'))
            empty = Path(temp) / 'e.json'
            empty.write_text(json.dumps({'abi': []}))
            with self.assertRaises(ValueError):
                bounty.read_artifact(empty)


class EncodingTests(unittest.TestCase):
    def test_static_types(self):
        self.assertEqual(bounty.encode_static(['uint32'], ['4']).hex(), '00' * 31 + '04')
        self.assertEqual(
            bounty.encode_static(['address'], ['0x' + '55' * 20]).hex(),
            '00' * 12 + '55' * 20)
        self.assertEqual(bounty.encode_static(['bool'], ['true']).hex(), '00' * 31 + '01')
        self.assertEqual(bounty.encode_static(['int256'], ['-1']).hex(), 'ff' * 32)

    def test_out_of_range_integers_are_refused(self):
        for type_name, value in (('uint8', '256'), ('uint8', '-1'), ('int8', '128'),
                                 ('int8', '-129'), ('uint256', str(1 << 256))):
            with self.assertRaises(ValueError, msg=f'{type_name} {value}'):
                bounty.encode_static([type_name], [value])
        self.assertTrue(bounty.encode_static(['uint8'], ['255']).endswith(b'\xff'))
        bounty.encode_static(['int8'], ['-128'])

    def test_non_boolean_words_are_refused_not_read_as_false(self):
        with self.assertRaises(ValueError):
            bounty.encode_static(['bool'], ['banana'])
        self.assertEqual(bounty.encode_static(['bool'], ['no']), b'\x00' * 32)
        self.assertEqual(bounty.encode_static(['bool'], ['TRUE']), b'\x00' * 31 + b'\x01')

    def test_malformed_address_and_bytes_are_refused(self):
        for type_name, value in (('address', '0x1234'), ('address', 'not-hex'),
                                 ('bytes32', '0xaa'), ('bytes32', '0xzz'), ('bytes33', '0x00')):
            with self.assertRaises(ValueError, msg=f'{type_name} {value}'):
                bounty.encode_static([type_name], [value])

    def test_invalid_integer_widths_are_refused(self):
        for type_name in ('uint7', 'uint512', 'int0'):
            with self.assertRaises(ValueError, msg=type_name):
                bounty.encode_static([type_name], ['1'])

    def test_dynamic_types_are_refused_rather_than_mis_encoded(self):
        with self.assertRaises(ValueError):
            bounty.encode_static(['string'], ['hello'])
        with self.assertRaises(ValueError):
            bounty.encode_static(['uint256[]'], ['1'])

    def test_argument_count_is_checked(self):
        with self.assertRaises(ValueError):
            bounty.encode_static(['uint256', 'uint256'], ['1'])


class RpcTests(unittest.TestCase):
    def test_verify_deployment_reports_exact_and_pins_one_block(self):
        code = '0x' + ('60' * 40)
        node = FakeNode({'eth_chainId': '0x3e7', 'eth_blockNumber': '0x1e240',
                         'eth_getCode': code, 'eth_getStorageAt': '0x' + '00' * 32})
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / 'a.json'
            artifact.write_text(json.dumps({'deployedBytecode': {'object': code}}))
            result = bounty.verify_deployment('http://node.invalid', '0x' + '11' * 20,
                                              str(artifact), 'latest', opener=node)
        self.assertEqual(result['deployment_status'], 'exact')
        self.assertEqual(result['chain_id'], 999)
        self.assertEqual(result['block'], 123456)
        blocks = {params[-1] for method, params in node.calls
                  if method in ('eth_getCode', 'eth_getStorageAt')}
        self.assertEqual(blocks, {'0x1e240'}, 'every read must use the one pinned block')

    def test_verify_deployment_flags_an_address_with_no_code(self):
        node = FakeNode({'eth_chainId': '0x1', 'eth_blockNumber': '0x10', 'eth_getCode': '0x'})
        result = bounty.verify_deployment('http://node.invalid', '0x' + '22' * 20, None,
                                          'latest', opener=node)
        self.assertEqual(result['deployment_status'], 'mismatch')
        self.assertIn('no code', result['reason'])

    def test_verify_deployment_detects_a_proxy_and_stays_unknown_without_an_artifact(self):
        impl = '0x' + '00' * 12 + '33' * 20
        node = FakeNode({
            'eth_chainId': '0x1', 'eth_blockNumber': '0x10', 'eth_getCode': '0xdeadbeef',
            'eth_getStorageAt': lambda params: impl if params[1] == bounty.proxy_slots()[
                'eip1967-implementation'] else '0x' + '00' * 32})
        result = bounty.verify_deployment('http://node.invalid', '0x' + '22' * 20, None,
                                          'latest', opener=node)
        self.assertEqual(result['proxy']['eip1967-implementation'], '0x' + '33' * 20)
        self.assertEqual(result['deployment_status'], 'unknown')

    def _proxy_node(self, proxy_code, impl_code, impl_address):
        slot = bounty.proxy_slots()['eip1967-implementation']
        padded = '0x' + '00' * 12 + impl_address[2:]
        return FakeNode({
            'eth_chainId': '0x1', 'eth_blockNumber': '0x100',
            'eth_getCode': lambda params: impl_code if params[0] == impl_address else proxy_code,
            'eth_getStorageAt': lambda params: padded if params[1] == slot else '0x' + '00' * 32})

    def test_a_proxy_is_compared_against_its_implementation(self):
        impl_address = '0x' + '33' * 20
        impl_code = '0x' + '61' * 60
        node = self._proxy_node('0x' + '60' * 30, impl_code, impl_address)
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / 'impl.json'
            artifact.write_text(json.dumps({'deployedBytecode': {'object': impl_code}}))
            result = bounty.verify_deployment('http://node.invalid', '0x' + '22' * 20,
                                              str(artifact), 'latest', opener=node)
        self.assertEqual(result['deployment_status'], 'exact')
        self.assertEqual(result['compared'], 'implementation')
        self.assertEqual(result['proxy_implementation']['address'], impl_address)

    def test_a_matching_proxy_runtime_never_reads_as_exact(self):
        # The logic lives behind the proxy; matching the proxy's own runtime proves nothing,
        # and the submission gate accepts exact, so this must not be exact.
        impl_address = '0x' + '33' * 20
        proxy_code = '0x' + '60' * 30
        node = self._proxy_node(proxy_code, '0x' + '61' * 60, impl_address)
        with tempfile.TemporaryDirectory() as temp:
            artifact = Path(temp) / 'proxy.json'
            artifact.write_text(json.dumps({'deployedBytecode': {'object': proxy_code}}))
            result = bounty.verify_deployment('http://node.invalid', '0x' + '22' * 20,
                                              str(artifact), 'latest', opener=node)
        self.assertEqual(result['deployment_status'], 'partial')
        self.assertIn('not the implementation', result['comparison']['reason'])

    def test_implementation_code_is_read_at_the_same_pinned_block(self):
        impl_address = '0x' + '33' * 20
        node = self._proxy_node('0x' + '60' * 30, '0x' + '61' * 60, impl_address)
        bounty.verify_deployment('http://node.invalid', '0x' + '22' * 20, None, 'latest',
                                 opener=node)
        blocks = {params[-1] for method, params in node.calls if method == 'eth_getCode'}
        self.assertEqual(blocks, {'0x100'})

    def test_decimal_block_is_converted_before_it_reaches_the_node(self):
        node = FakeNode({'eth_chainId': '0x1', 'eth_blockNumber': '0x10',
                         'eth_getCode': '0xdead', 'eth_getStorageAt': '0x' + '00' * 32})
        bounty.verify_deployment('http://node.invalid', '0x' + '22' * 20, None, '4096',
                                 opener=node)
        codes = [params[-1] for method, params in node.calls if method == 'eth_getCode']
        self.assertEqual(codes, ['0x1000'])

    def test_bad_address_is_refused_before_any_network_call(self):
        node = FakeNode({})
        with self.assertRaises(ValueError):
            bounty.verify_deployment('http://node.invalid', 'not-an-address', None,
                                     'latest', opener=node)
        self.assertEqual(node.calls, [])

    def test_eth_call_builds_the_selector_and_decodes_words(self):
        node = FakeNode({'eth_call': '0x' + '00' * 31 + '2a'})
        result = bounty.eth_call('http://node.invalid', '0x' + '44' * 20, 'markPx(uint32)',
                                 ['4'], 'latest', opener=node)
        self.assertEqual(result['selector'], keccak.selector('markPx(uint32)'))
        self.assertEqual(result['words'][0]['uint'], '42')
        self.assertEqual(node.calls[0][1][0]['data'][10:], '00' * 31 + '04')

    def test_eth_call_does_not_read_a_small_number_as_an_address(self):
        node = FakeNode({'eth_call': '0x' + '00' * 31 + '06'})
        result = bounty.eth_call('http://node.invalid', '0x' + '44' * 20, 'decimals()', [],
                                 'latest', opener=node)
        self.assertEqual(result['words'][0]['uint'], '6')
        self.assertIsNone(result['words'][0]['address'])

    def test_eth_call_offers_an_address_reading_for_a_padded_address(self):
        node = FakeNode({'eth_call': '0x' + '00' * 12 + '33' * 20})
        result = bounty.eth_call('http://node.invalid', '0x' + '44' * 20, 'owner()', [],
                                 'latest', opener=node)
        self.assertEqual(result['words'][0]['address'], '0x' + '33' * 20)

    def test_rpc_error_is_raised_not_swallowed(self):
        class Failing(FakeNode):
            def __call__(self, request, timeout=None):
                return FakeResponse({'jsonrpc': '2.0', 'id': 1,
                                     'error': {'code': -32000, 'message': 'nope'}})
        with self.assertRaises(ValueError):
            bounty.rpc_call('http://node.invalid', 'eth_chainId', [], Failing({}))


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        (self.repo / 'src').mkdir(parents=True)
        git(self.repo, 'init', '-q')
        (self.repo / 'src/Vault.sol').write_text('contract Vault {}\n')
        commit(self.repo, 'fixture')
        self.run = self.base / 'run'
        bounty.initialize(self.repo, self.run)

    def candidate(self):
        row = bounty.template()
        row.update(title='Example', root_cause='Example mechanism',
                   affected_paths=['src/Vault.sol'], bug_class='aggregate-not-decremented',
                   revision='abc1234', attacker_capabilities='Unprivileged caller',
                   preconditions='Example state', impact='Demonstrated property change')
        return row

    def check(self, row, submission=False):
        bounty.dump(self.run / 'findings.json', [row])
        return bounty.validate(self.run, submission=submission)

    def verified(self):
        row = self.candidate()
        row['status'] = 'verified'
        (self.run / 'poc.py').write_text('assert True\n')
        (self.run / 'log.txt').write_text('example test output\n')
        row['evidence'] = dict(command='python3 poc.py', exit_code=0, poc_path='poc.py',
                               log_path='log.txt', assertion='Example assertion',
                               negative_control='Observed control',
                               source_integrity='Original source')
        return row

    def objection(self, outcome='answered'):
        item = {'gate': 'interruption',
                'claim': 'the nonReentrant modifier on redeem() stops the second entry',
                'anchor': 'code: src/Vault.sol:142 modifier nonReentrant on redeem()',
                'outcome': outcome}
        if outcome == 'answered':
            item['answer'] = 'redeemFor() reaches _redeem() directly and carries no guard'
            item['answer_anchor'] = 'code: src/Vault.sol:188-204 redeemFor -> _redeem'
        return item

    def submittable(self):
        row = self.verified()
        row['objections'] = [self.objection()]
        row.update(severity='high', scope_status='in-scope', deployment_status='exact',
                   severity_rationale='Program rubric: permanent loss of core function')
        row['novelty'] = {'status': 'no-public-match-found',
                          'sources': ['https://example.invalid/known-issues (read 2026-10-08)',
                                      'https://example.invalid/audit.pdf (no match on mechanism)']}
        row['evidence']['impact_quantification'] = '12,400 USDC of debt accounting, cost 0.002 ETH'
        return row

    # ---- init ----
    def test_inventory_and_empty_run(self):
        data = json.loads((self.run / 'run.json').read_text())
        self.assertEqual(data['source_candidates'], ['src/Vault.sol'])
        self.assertFalse(data['dirty'])
        self.assertEqual(data['schema_version'], bounty.SCHEMA_VERSION)
        self.assertEqual(bounty.validate(self.run), [])

    def test_init_writes_the_funnel_scaffolding(self):
        for name in ('dup-map.json', 'known-hypotheses.md', 'coverage.md', 'scope.md', 'model.md'):
            self.assertTrue((self.run / name).exists(), name)
        self.assertEqual(json.loads((self.run / 'dup-map.json').read_text()), [])

    def test_never_overwrite(self):
        with self.assertRaises(ValueError):
            bounty.initialize(self.repo, self.run)

    def test_no_output_in_target(self):
        with self.assertRaises(ValueError):
            bounty.initialize(self.repo, self.repo / 'inside')

    def test_stale_schema_is_reported(self):
        meta = json.loads((self.run / 'run.json').read_text())
        meta['schema_version'] = 1
        bounty.dump(self.run / 'run.json', meta)
        errors = bounty.validate(self.run)
        self.assertTrue(any('schema_version' in e for e in errors))

    # ---- structural gate ----
    def test_complete_record_is_structurally_valid_even_with_unknown_scope(self):
        self.assertEqual(self.check(self.candidate()), [])

    def test_duplicate_id_rejected(self):
        row = self.candidate()
        bounty.dump(self.run / 'findings.json', [row, dict(row)])
        self.assertTrue(any('duplicate id' in e for e in bounty.validate(self.run)))

    def test_bug_class_must_be_kebab_case(self):
        row = self.candidate()
        row['bug_class'] = 'Not Kebab Case'
        self.assertTrue(any('bug_class' in e for e in self.check(row)))

    def test_revision_is_required(self):
        row = self.candidate()
        row['revision'] = ''
        self.assertTrue(any('revision' in e for e in self.check(row)))

    def test_wrong_types_reported(self):
        row = self.candidate()
        row['affected_paths'] = 'src/Vault.sol'
        row['severity'] = 'catastrophic'
        errors = self.check(row)
        self.assertTrue(any('affected_paths' in e for e in errors))
        self.assertTrue(any('severity' in e for e in errors))

    def test_refutation_needs_reason(self):
        row = self.candidate()
        row['status'] = 'refuted'
        self.assertTrue(any('refutation' in e for e in self.check(row)))

    def test_public_novelty_claim_requires_sources(self):
        row = self.candidate()
        row['novelty'] = {'status': 'no-public-match-found', 'sources': []}
        self.assertTrue(any('novelty' in e for e in self.check(row)))

    def test_verified_needs_artifacts(self):
        row = self.candidate()
        row['status'] = 'verified'
        errors = self.check(row)
        for field in ('command', 'assertion', 'negative_control', 'source_integrity',
                      'exit_code', 'log_path', 'poc_path'):
            self.assertTrue(any(field in e for e in errors), field)
        self.assertEqual(self.check(self.verified()), [])

    def test_boolean_exit_code_rejected(self):
        row = self.verified()
        row['evidence']['exit_code'] = True
        self.assertTrue(any('exit_code' in e for e in self.check(row)))

    def test_traversal_rejected(self):
        row = self.verified()
        row['evidence']['log_path'] = '../outside.txt'
        (self.base / 'outside.txt').write_text('x')
        self.assertTrue(any('inside the run' in e for e in self.check(row)))

    def test_symlink_escape_rejected(self):
        row = self.verified()
        (self.base / 'outside.txt').write_text('x')
        (self.run / 'link.txt').symlink_to(self.base / 'outside.txt')
        row['evidence']['log_path'] = 'link.txt'
        self.assertTrue(any('inside the run' in e for e in self.check(row)))

    def test_empty_evidence_file_rejected(self):
        row = self.verified()
        (self.run / 'log.txt').write_text('')
        self.assertTrue(any('must not be empty' in e for e in self.check(row)))

    # ---- submission gate ----
    def test_submission_gate_passes_a_complete_record(self):
        self.assertEqual(self.check(self.submittable(), submission=True), [])

    def test_submission_gate_blocks_undeployed_revision(self):
        row = self.submittable()
        row['deployment_status'] = 'unknown'
        errors = self.check(row, submission=True)
        self.assertTrue(any('deployment_status' in e for e in errors))

    def test_submission_gate_blocks_partial_bytecode_match(self):
        row = self.submittable()
        row['deployment_status'] = 'partial'
        self.assertTrue(any('deployment_status' in e for e in self.check(row, submission=True)))

    def test_submission_gate_blocks_unverified_and_out_of_scope(self):
        row = self.submittable()
        row['status'] = 'needs-evidence'
        row['scope_status'] = 'unknown'
        errors = self.check(row, submission=True)
        self.assertTrue(any('status verified' in e for e in errors))
        self.assertTrue(any('scope_status' in e for e in errors))

    def test_submission_gate_requires_rubric_and_two_novelty_sources(self):
        row = self.submittable()
        del row['severity_rationale']
        row['novelty']['sources'] = ['https://example.invalid/only-one']
        errors = self.check(row, submission=True)
        self.assertTrue(any('severity_rationale' in e for e in errors))
        self.assertTrue(any('two checked novelty sources' in e for e in errors))

    def test_submission_gate_requires_quantified_impact(self):
        row = self.submittable()
        del row['evidence']['impact_quantification']
        self.assertTrue(any('impact_quantification' in e
                            for e in self.check(row, submission=True)))

    def test_submission_gate_refuses_an_empty_file(self):
        self.assertTrue(any('no records' in e for e in bounty.validate(self.run, submission=True)))

    # ---- objection exchange ----
    def test_objections_must_be_an_array_of_anchored_objects(self):
        row = self.candidate()
        row['objections'] = 'none'
        self.assertTrue(any('objections must be an array' in e for e in self.check(row)))
        row['objections'] = [{'gate': 'nonsense', 'claim': '', 'outcome': 'answered'}]
        errors = self.check(row)
        self.assertTrue(any('gate must be one of' in e for e in errors))
        self.assertTrue(any('claim is required' in e for e in errors))
        self.assertTrue(any('anchor is required' in e for e in errors))

    def test_a_withdrawn_objection_needs_no_anchor(self):
        # Withdrawn means triage could not anchor it. Demanding an anchor would make the
        # outcome unrecordable, and unrecorded withdrawals are how bad objections get reused.
        row = self.candidate()
        row['objections'] = [{'gate': 'eligibility', 'outcome': 'withdrawn',
                              'claim': 'probably intended behaviour',
                              'withdrawn_because': 'no spec or code supports it'}]
        self.assertEqual(self.check(row), [])

    def test_a_sustained_objection_still_needs_an_anchor(self):
        row = self.candidate()
        row['objections'] = [{'gate': 'harm', 'claim': 'dust only', 'outcome': 'sustained'}]
        self.assertTrue(any('anchor is required' in e for e in self.check(row)))

    def test_an_answered_objection_needs_its_own_anchor(self):
        # The symmetry is the point: an unanchored answer must not defeat an anchored objection.
        row = self.candidate()
        item = self.objection()
        del item['answer_anchor']
        row['objections'] = [item]
        self.assertTrue(any('answered objection requires answer_anchor' in e
                            for e in self.check(row)))

    def test_withdrawn_and_sustained_objections_need_no_answer(self):
        for outcome in ('withdrawn', 'sustained'):
            row = self.candidate()
            row['objections'] = [self.objection(outcome)]
            self.assertEqual(self.check(row), [], outcome)

    def test_submission_requires_a_triage_exchange(self):
        row = self.submittable()
        row['objections'] = []
        self.assertTrue(any('triage exchange' in e for e in self.check(row, submission=True)))

    def test_submission_is_blocked_by_a_sustained_objection(self):
        row = self.submittable()
        row['objections'] = [self.objection(), self.objection('sustained')]
        errors = self.check(row, submission=True)
        self.assertTrue(any('sustained objection' in e for e in errors))
        self.assertTrue(any('interruption' in e for e in errors))

    def test_withdrawn_objections_do_not_block_submission(self):
        row = self.submittable()
        row['objections'] = [self.objection('withdrawn')]
        self.assertEqual(self.check(row, submission=True), [])

    # ---- duplicate map ----
    def test_dup_check_is_clean_on_an_empty_map(self):
        bounty.dump(self.run / 'findings.json', [self.candidate()])
        self.assertEqual(bounty.check_dup_map(self.run), ([], []))

    def test_dup_check_matches_surface_and_class(self):
        bounty.dump(self.run / 'findings.json', [self.candidate()])
        bounty.dump(self.run / 'dup-map.json', [{
            'id': 'KI-001', 'kind': 'program-known-issue',
            'source': 'https://example.invalid/known-issues',
            'surfaces': ['src/Vault.sol'],
            'bug_classes': ['aggregate-not-decremented'], 'note': 'acknowledged'}])
        errors, collisions = bounty.check_dup_map(self.run)
        self.assertEqual(errors, [])
        self.assertEqual(collisions[0]['confidence'], 'class-match')

    def test_dup_check_reports_surface_only_when_the_class_differs(self):
        bounty.dump(self.run / 'findings.json', [self.candidate()])
        bounty.dump(self.run / 'dup-map.json', [{
            'id': 'KI-002', 'kind': 'past-audit', 'source': 'https://example.invalid/audit',
            'surfaces': ['src/Vault.sol'], 'bug_classes': ['oracle-staleness']}])
        errors, collisions = bounty.check_dup_map(self.run)
        self.assertEqual((errors, collisions), ([], []))
        bounty.dump(self.run / 'dup-map.json', [{
            'id': 'KI-003', 'kind': 'past-audit', 'source': 'https://example.invalid/audit',
            'surfaces': ['src/Vault.sol']}])
        _, collisions = bounty.check_dup_map(self.run)
        self.assertEqual(collisions[0]['confidence'], 'surface-only')

    def test_dup_check_ignores_refuted_findings_and_validates_the_map(self):
        row = self.candidate()
        row['status'] = 'refuted'
        row['rejection_reason'] = 'guarded'
        bounty.dump(self.run / 'findings.json', [row])
        bounty.dump(self.run / 'dup-map.json', [{
            'id': 'KI-004', 'kind': 'program-known-issue', 'source': 'https://x.invalid',
            'surfaces': ['src/Vault.sol']}])
        self.assertEqual(bounty.check_dup_map(self.run), ([], []))
        bounty.dump(self.run / 'dup-map.json', [{'id': 'KI-005', 'kind': 'invented'}])
        errors, _ = bounty.check_dup_map(self.run)
        self.assertTrue(any('kind' in e for e in errors))
        self.assertTrue(any('source' in e for e in errors))


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.repo = base / 'repo'
        (self.repo / 'src').mkdir(parents=True)
        (self.repo / 'test').mkdir(parents=True)
        git(self.repo, 'init', '-q')
        (self.repo / 'src/Vault.sol').write_text('contract Vault { uint256 totalDebt; }\n')
        (self.repo / 'test/Vault.t.sol').write_text('contract VaultTest { Vault v; }\n')
        commit(self.repo, 'fixture')
        self.run = base / 'run'
        bounty.initialize(self.repo, self.run)

    def test_one_bundle_per_lens_with_source_and_lens_text(self):
        result = bounty.bundle(self.repo, self.run, ['accounting', 'liveness'])
        self.assertEqual([b['lens'] for b in result['bundles']], ['accounting', 'liveness'])
        text = (self.run / 'bundles/accounting-bundle.md').read_text()
        self.assertIn('contract Vault', text)                      # source bundled
        self.assertIn('every writer of every aggregate', text)     # the lens procedure
        self.assertIn('Shared hunt rules', text)                   # the shared stance
        self.assertIn('plain words', text)                         # the SOP
        self.assertIn('Lens: **accounting**', text)                # restated task footer

    def test_groups_expand_and_duplicates_collapse(self):
        result = bounty.bundle(self.repo, self.run, ['attack', 'accounting'])
        lenses = [b['lens'] for b in result['bundles']]
        self.assertEqual(lenses, list(bounty.ATTACK_LENSES))

    def test_unknown_lens_is_refused(self):
        with self.assertRaises(ValueError):
            bounty.bundle(self.repo, self.run, ['reentrancy'])

    def test_only_the_coverage_gap_lens_receives_the_tests(self):
        bounty.bundle(self.repo, self.run, ['coverage-gap', 'accounting'])
        gap = (self.run / 'bundles/coverage-gap-bundle.md').read_text()
        acc = (self.run / 'bundles/accounting-bundle.md').read_text()
        self.assertIn('contract VaultTest', gap)
        self.assertNotIn('contract VaultTest', acc)

    def test_test_files_are_never_in_the_in_scope_source(self):
        bounty.bundle(self.repo, self.run, ['accounting'])
        source = (self.run / 'bundles/source.md').read_text()
        self.assertIn('src/Vault.sol', source)
        self.assertNotIn('test/Vault.t.sol', source)

    def test_triage_bundle_carries_records_and_not_the_hunt_stance(self):
        row = bounty.template()
        row.update(title='t', root_cause='r', affected_paths=['src/Vault.sol'],
                   bug_class='aggregate-not-decremented', revision='abc1234',
                   attacker_capabilities='a', preconditions='p', impact='i')
        bounty.dump(self.run / 'findings.json', [row])
        bounty.bundle(self.repo, self.run, ['triage'])
        text = (self.run / 'bundles/triage-bundle.md').read_text()
        self.assertIn('records under review', text)
        self.assertIn('aggregate-not-decremented', text)
        self.assertIn('OBJECTION', text)
        self.assertIn('Direct theft of funds', text)      # the impact ladder
        self.assertNotIn('Shared hunt rules', text)       # never the no-self-refutation stance

    def test_seam_bundle_carries_the_earlier_records_to_cross(self):
        bounty.dump(self.run / 'findings.json', [])
        bounty.bundle(self.repo, self.run, ['seam'])
        text = (self.run / 'bundles/seam-bundle.md').read_text()
        self.assertIn('Cross them', text)

    def test_context_files_are_included_when_present(self):
        (self.run / 'known-hypotheses.md').write_text('surface | bug-class | closed-refuted | x\n')
        extra = Path(self.temp.name) / 'delta.json'
        extra.write_text('{"ranked": []}')
        result = bounty.bundle(self.repo, self.run, ['accounting'], includes=[str(extra)])
        text = (self.run / 'bundles/accounting-bundle.md').read_text()
        self.assertIn('known-hypotheses.md', text)
        self.assertIn('delta.json', text)
        self.assertGreaterEqual(result['context_sections'], 2)

    def test_missing_include_is_refused(self):
        with self.assertRaises(ValueError):
            bounty.bundle(self.repo, self.run, ['accounting'], includes=['/nonexistent.json'])

    def test_scope_prefix_emptiness_is_reported(self):
        result = bounty.bundle(self.repo, self.run, ['accounting'], scope_prefixes=['nope/'])
        self.assertEqual(result['in_scope_files'], 0)
        self.assertTrue(any('no in-scope source' in n for n in result['notes']))


class DeltaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        (self.repo / 'src').mkdir(parents=True)
        (self.repo / 'test').mkdir(parents=True)
        git(self.repo, 'init', '-q')
        (self.repo / 'src/Audited.sol').write_text('contract Audited { uint256 x; }\n')
        (self.repo / 'README.md').write_text('docs\n')
        commit(self.repo, 'audited state')
        self.audited = subprocess.run(['git', '-C', str(self.repo), 'rev-parse', 'HEAD'],
                                      check=True, stdout=subprocess.PIPE
                                      ).stdout.decode().strip()
        (self.repo / 'src/Risky.sol').write_text(
            'contract Risky {\n'
            '  uint256 public totalDebt;\n'
            '  function redeem(uint256 a) external {\n'
            '    (bool ok,) = msg.sender.call("");\n'
            '    require(ok);\n'
            '    token.safeTransfer(msg.sender, a);\n'
            '  }\n'
            '}\n')
        (self.repo / 'src/Quiet.sol').write_text('contract Quiet { uint256 y; }\n')
        (self.repo / 'test/Quiet.t.sol').write_text('contract QuietTest { Quiet q; }\n')
        (self.repo / 'README.md').write_text('docs changed\n')
        commit(self.repo, 'post-audit work')

    def test_ranking_prefers_value_bearing_untested_code(self):
        report = bounty.delta(self.repo, self.audited)
        paths = [row['path'] for row in report['ranked']]
        self.assertEqual(paths[0], 'src/Risky.sol')
        self.assertIn('src/Quiet.sol', paths)
        self.assertNotIn('README.md', paths)
        self.assertNotIn('test/Quiet.t.sol', paths)
        self.assertEqual(report['test_files_excluded'], 1)
        risky = report['ranked'][0]
        self.assertIn('external-call', risky['signals'])
        self.assertIn('token-move', risky['signals'])
        self.assertTrue(risky['untested_by_name'])

    def test_tested_file_is_marked_as_named_in_tests(self):
        report = bounty.delta(self.repo, self.audited)
        quiet = next(r for r in report['ranked'] if r['path'] == 'src/Quiet.sol')
        self.assertFalse(quiet['untested_by_name'])

    def test_scope_prefix_filters(self):
        report = bounty.delta(self.repo, self.audited, ['src/nonexistent/'])
        self.assertEqual(report['ranked'], [])

    def test_unknown_baseline_is_an_error_not_a_guess(self):
        with self.assertRaises(ValueError):
            bounty.delta(self.repo, 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef')

    def test_score_target_uses_code_and_program_facts(self):
        program = Path(self.temp.name) / 'program.json'
        program.write_text(json.dumps({
            'program': 'Example', 'audited_revision': self.audited,
            'in_scope_paths': ['src/'], 'duplicate_policy': 'first-to-report',
            'deposit_required': False, 'known_issues_count': 7,
            'upstream_fork': 'aave-v3', 'payout_max_usd': 100000}))
        result = bounty.score_target(self.repo, program)
        self.assertEqual(result['band'], 'hunt')
        self.assertGreaterEqual(result['priority_score'], 60)
        self.assertEqual(result['in_scope_files'], 3)
        self.assertIn('src/Risky.sol', result['untested_sample'])
        self.assertTrue(any('first-to-report' in r for r in result['reasons']))

    def test_score_target_records_unknowns_instead_of_assuming(self):
        program = Path(self.temp.name) / 'bare.json'
        program.write_text(json.dumps({'program': 'Bare', 'in_scope_paths': ['src/']}))
        result = bounty.score_target(self.repo, program)
        self.assertIsNone(result['churn_share_since_audit'])
        self.assertTrue(any('audited_revision' in u for u in result['unknowns']))
        self.assertTrue(any('duplicate_policy' in u for u in result['unknowns']))


class TemplateTests(unittest.TestCase):
    def test_the_solana_control_test_cannot_pass_while_empty(self):
        # A passing empty negative control looks like evidence and establishes nothing.
        text = (ROOT / 'skills/bounty-pilot/templates/anchor_poc.rs').read_text()
        control = text.split('fn control_correct_account_path')[1]
        self.assertIn('unimplemented!', control)

    def test_every_template_demands_a_negative_control(self):
        for name in ('ForkPoC.t.sol', 'LocalPoC.t.sol', 'anchor_poc.rs'):
            text = (ROOT / 'skills/bounty-pilot/templates' / name).read_text()
            self.assertIn('control', text.lower(), name)


class CliTests(unittest.TestCase):
    def test_subcommands_are_wired(self):
        parser = bounty.build_parser()
        for argv in (['init', '--repo', '.', '--out', 'x'], ['check', '--run', 'x'],
                     ['check', '--run', 'x', '--submission'], ['dup-check', '--run', 'x'],
                     ['delta', '--repo', '.', '--since', 'HEAD'],
                     ['bundle', '--repo', '.', '--run', 'x', '--lens', 'attack'],
                     ['bundle', '--repo', '.', '--run', 'x', '--lens', 'triage'],
                     ['score-target', '--repo', '.', '--program', 'p.json'],
                     ['verify-deployment', '--rpc', 'u', '--address', 'a'],
                     ['sig', 'transfer(address,uint256)'],
                     ['eth-call', '--rpc', 'u', '--to', 't', '--sig', 's']):
            parser.parse_args(argv)

    def test_sig_subcommand_prints_a_selector(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = bounty.main(['sig', 'transfer(address,uint256)'])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), '0xa9059cbb')

    def test_bad_input_exits_two_without_a_traceback(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = bounty.main(['delta', '--repo', '/nonexistent', '--since', 'HEAD'])
        self.assertEqual(code, 2)
        self.assertTrue(err.getvalue().startswith('Error:'))


if __name__ == '__main__':
    unittest.main()
