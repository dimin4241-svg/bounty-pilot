#!/usr/bin/env python3
"""Bounty Pilot helper: run scaffolding, delta ranking, on-chain identity checks
and structural/submission gates. Standard library only.

Nothing here audits code or proves a finding. Every subcommand reports what it
observed and labels what it could not establish.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
SKILL_ROOT = Path(__file__).resolve().parents[1]

SOURCE_SUFFIXES = {'.sol', '.vy', '.yul', '.huff', '.rs', '.move', '.cairo', '.fe',
                   '.fc', '.func', '.tolk', '.go', '.ts', '.tsx', '.js', '.py', '.c', '.h',
                   '.cpp', '.java', '.kt', '.kts', '.php', '.rb', '.swift', '.cs', '.scala',
                   '.ex', '.exs', '.dart', '.tf', '.hcl', '.sql', '.sh', '.bash', '.lua',
                   '.graphql', '.graphqls', '.gql', '.proto'}
CONFIG_SUFFIXES = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.xml',
                   '.graphql', '.graphqls', '.gql', '.proto', '.idl'}
CONFIG_ROOT_FILES = {
    'foundry.toml', 'hardhat.config.js', 'hardhat.config.ts', 'hardhat.config.cjs',
    'truffle-config.js', 'anchor.toml', 'move.toml', 'scarb.toml', 'cargo.toml',
    'package.json', 'go.mod', 'pyproject.toml', 'setup.cfg', 'remappings.txt',
    'rust-toolchain', 'rust-toolchain.toml', 'docker-compose.yml', 'compose.yml',
    'dockerfile', 'makefile', 'justfile',
}
CONFIG_DIRS = {'config', 'configs', 'deployment', 'deployments', 'idl', 'abi',
               'migrations', 'workflows'}
CONFIG_BUNDLE_MAX_FILE_BYTES = 200_000
CONFIG_BUNDLE_MAX_TOTAL_BYTES = 800_000
SENSITIVE_PATH_PARTS = {'.env', 'secrets', 'credentials', 'keystore', 'wallet', 'mnemonic'}
SECRET_KEY_VALUE = re.compile(
    r'(?i)(\b(?:private[_-]?key|api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|'
    r'bearer[_-]?token|password|mnemonic)\b\s*[:=]\s*)(["\'])(.*?)(\2)')
UNQUOTED_SECRET_KEY_VALUE = re.compile(
    r'(?i)(\b(?:private[_-]?key|api[_-]?key|secret(?:[_-]?key)?|access[_-]?token|'
    r'bearer[_-]?token|password|mnemonic)\b\s*[:=]\s*)(?!["\'])([^,\s}\]]+)')
STATUSES = {'hypothesis', 'needs-evidence', 'verified', 'refuted'}
SEVERITIES = {'unassessed', 'informational', 'low', 'medium', 'high', 'critical'}
SCOPE_STATUSES = {'unknown', 'in-scope', 'out-of-scope'}
DEPLOY_STATUSES = {'unknown', 'exact', 'partial', 'mismatch', 'not-applicable'}
NOVELTY_STATUSES = {'not-checked', 'no-public-match-found', 'matched-public-issue'}
GATES = {'interruption', 'reachability', 'trigger', 'harm', 'eligibility', 'evidence'}
OBJECTION_OUTCOMES = {'answered', 'sustained', 'withdrawn'}
HISTORY_SCHEMA = 1
HISTORY_DISPOSITIONS = {'submitted', 'pending', 'accepted', 'paid', 'duplicate',
                        'invalid', 'out-of-scope', 'rejected', 'withdrawn'}
HISTORY_REASONS = {'private-duplicate', 'public-known-issue', 'out-of-scope',
                   'impact-not-met', 'not-reproducible', 'severity-dispute', 'other',
                   'unspecified'}
HISTORY_REVIEW_STATUSES = {'unchecked', 'no-match', 'different-root-cause', 'regression',
                           'same-mechanism', 'unavailable'}
REQUIRED = ('id', 'title', 'status', 'severity', 'bug_class', 'revision', 'root_cause',
            'affected_paths', 'attacker_capabilities', 'preconditions', 'impact',
            'scope_status', 'deployment_status', 'novelty', 'evidence', 'objections',
            'rejection_reason')


def load_stack_route():
    """Load bundled manifest router; its output is always heuristic."""
    path = Path(__file__).resolve().parent / 'stack_route.py'
    spec = importlib.util.spec_from_file_location('bp_stack_route', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_keccak():
    path = Path(__file__).resolve().parent / 'keccak.py'
    spec = importlib.util.spec_from_file_location('bp_keccak', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #

def git(repo, *args, check=True):
    done = subprocess.run(['git', '-C', str(repo), *args], check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return done.stdout.decode('utf-8', 'replace')


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def has_text(value):
    return isinstance(value, str) and bool(value.strip())


def skill_version():
    version_file = SKILL_ROOT / 'VERSION'
    try:
        return version_file.read_text(encoding='utf-8').strip()
    except OSError:
        return 'unknown'


def canonical_project(value):
    """Return a credential-free host/repository key from an HTTPS, SSH or owner/repo URL."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    scp = re.match(r'^(?:[^@/:]+@)?([^/:]+):(.+)$', raw)
    if scp and '://' not in raw:
        host, path = scp.group(1), scp.group(2)
    elif '://' in raw:
        parsed = urllib.parse.urlsplit(raw)
        host, path = parsed.hostname or '', parsed.path
    elif '/' in raw:
        host, path = raw.split('/', 1)
    else:
        return None
    host = host.lower().strip()
    path = path.strip('/').removesuffix('.git').lower()
    if not host or not path or any(c.isspace() for c in host + path):
        return None
    return host + '/' + path


def project_for_repo(repo):
    remote = git(repo, 'remote', 'get-url', 'origin', check=False).strip()
    return canonical_project(remote)


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #

def template():
    return dict(id='BP-001', title='', status='hypothesis', severity='unassessed',
                bug_class='', revision='', lens='', root_cause='', affected_paths=[],
                attacker_capabilities='', preconditions='', impact='',
                scope_status='unknown', deployment_status='unknown',
                novelty={'status': 'not-checked', 'sources': []},
                evidence={}, next_experiment={'question': '', 'method': '', 'expected_evidence': '',
                                              'blocker': ''},
                history_review={'status': 'unchecked', 'case_ids': [], 'rationale': '',
                                'evidence': ''},
                objections=[], rejection_reason='')


def initialize(repo, out):
    repo, out = Path(repo).resolve(), Path(out).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    if out == root or root in out.parents or out == SKILL_ROOT or SKILL_ROOT in out.parents:
        raise ValueError('Run directory must be outside the target and skill package')
    if out.exists():
        raise ValueError('Use a new run directory; existing output is never overwritten')
    commit = git(root, 'rev-parse', 'HEAD').strip()
    tracked = git(root, 'ls-files', '-z').split('\0')
    source = sorted(p for p in tracked if p and Path(p).suffix in SOURCE_SUFFIXES)
    dirty = bool(git(root, 'status', '--porcelain'))
    out.mkdir(parents=True)
    out.chmod(0o700)
    dump(out / 'run.json', {
        'schema_version': SCHEMA_VERSION, 'skill_version': skill_version(),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'run_id': uuid.uuid4().hex,
        'target_root': str(root), 'project_key': project_for_repo(root),
        'commit': commit, 'dirty': dirty,
        'scope_status': 'unknown', 'deployment_status': 'unknown', 'max_passes': 3,
        'audited_revision': None,
        'inventory_kind': 'tracked-source-candidates-not-authorized-scope',
        'source_candidates': source})
    dump(out / 'findings.json', [])
    dump(out / 'candidate-template.json', template())
    dump(out / 'dup-map.json', [])
    (out / '.gitignore').write_text('*\n', encoding='utf-8')
    (out / 'scope.md').write_text(
        '# Scope\n\nProgram eligibility and deployment: unknown.\n', encoding='utf-8')
    (out / 'model.md').write_text(
        '# Model\n\nRecord assets, roles, transitions and evidenced invariants.\n', encoding='utf-8')
    (out / 'coverage.md').write_text(
        '# Coverage\n\n| Surface / invariant | Lens | Pass | Experiment | Result / gaps |\n'
        '| --- | --- | --- | --- | --- |\n', encoding='utf-8')
    (out / 'known-hypotheses.md').write_text(
        '# Known hypotheses\n\nAppend one line per investigated mechanism after every pass:\n'
        '`surface | bug-class | status | why it is closed or still open`.\n'
        'Later passes read this file and must hunt mechanisms absent from it.\n', encoding='utf-8')
    return {'run': str(out), 'run_id': read_json(out / 'run.json')['run_id'],
            'project_key': project_for_repo(root), 'commit': commit, 'dirty': dirty,
            'source_candidates': len(source), 'schema_version': SCHEMA_VERSION}


# --------------------------------------------------------------------------- #
# private report history
# --------------------------------------------------------------------------- #

def default_history_path():
    return Path.home() / '.bounty-pilot' / 'history.jsonl'


def _history_path(value=None, target_root=None, run_dir=None):
    path = Path(value).expanduser() if value else default_history_path()
    if path.is_symlink() or (path.parent.exists() and path.parent.is_symlink()):
        raise ValueError('History file must not be a symlink')
    resolved = path.resolve()
    protected = [SKILL_ROOT]
    if target_root:
        protected.append(Path(target_root).resolve())
    if run_dir:
        protected.append(Path(run_dir).resolve())
    cwd_repo = git(Path.cwd(), 'rev-parse', '--show-toplevel', check=False).strip()
    if cwd_repo:
        protected.append(Path(cwd_repo).resolve())
    for root in protected:
        if resolved == root or root in resolved.parents:
            raise ValueError('Keep the private history file outside the target, run and skill')
    return resolved


def _history_rows(path):
    if not path.exists():
        return []
    rows = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'history line {number} is not valid JSON') from exc
        required = ('case_id', 'recorded_at', 'project_key', 'finding_id', 'bug_class',
                    'affected_paths', 'root_cause_summary', 'disposition')
        if not isinstance(row, dict) or row.get('schema_version') != HISTORY_SCHEMA:
            raise ValueError(f'history line {number} has an unsupported record schema')
        missing = [key for key in required if key not in row]
        if missing:
            raise ValueError(f'history line {number} is missing: ' + ', '.join(missing))
        if (not isinstance(row['disposition'], str) or
                row['disposition'] not in HISTORY_DISPOSITIONS):
            raise ValueError(f'history line {number} has an invalid disposition')
        if (not isinstance(row['case_id'], str) or not row['case_id'] or
                not isinstance(row['finding_id'], str) or not row['finding_id'] or
                not isinstance(row['project_key'], str) or
                canonical_project(row['project_key']) != row['project_key'] or
                not isinstance(row['bug_class'], str) or
                not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', row['bug_class']) or
                not isinstance(row['root_cause_summary'], str) or
                len(row['root_cause_summary']) > 500 or
                not isinstance(row['recorded_at'], str)):
            raise ValueError(f'history line {number} has invalid field types or values')
        reason = row.get('reason', 'unspecified')
        if (not isinstance(reason, str) or reason not in HISTORY_REASONS or
                not isinstance(row.get('program', ''), str) or
                not isinstance(row.get('lens', 'unattributed'), str) or
                not isinstance(row.get('revision', ''), str)):
            raise ValueError(f'history line {number} has invalid optional fields')
        if (not isinstance(row['affected_paths'], list) or not row['affected_paths'] or
                not all(isinstance(item, str) and item.strip() for item in row['affected_paths'])):
            raise ValueError(f'history line {number} has invalid affected_paths')
        rows.append(row)
    return rows


def _private_history_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path == default_history_path():
        path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        fchmod = getattr(os, 'fchmod', None)
        if callable(fchmod):
            fchmod(fd, 0o600)
        else:  # os.fchmod is not available on every supported platform.
            os.chmod(str(path), 0o600)
    finally:
        os.close(fd)


def _append_history(path, event):
    _private_history_file(path)
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(str(path), flags)
    with os.fdopen(fd, 'a', encoding='utf-8') as out:
        out.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')


def history_record(run, finding_id, disposition, ledger=None, project=None, program='',
                   case_id=None, reason='unspecified', hours=None):
    if disposition not in HISTORY_DISPOSITIONS:
        raise ValueError('Invalid disposition: ' + str(disposition))
    if reason not in HISTORY_REASONS:
        raise ValueError('Invalid reason category: ' + str(reason))
    run = Path(run).resolve()
    meta = read_json(run / 'run.json')
    records = read_json(run / 'findings.json')
    matches = [row for row in records if isinstance(row, dict) and row.get('id') == finding_id]
    if len(matches) != 1:
        raise ValueError('Finding id must identify exactly one record in findings.json')
    finding = matches[0]
    if finding.get('status') != 'verified':
        raise ValueError('Only a verified finding can be recorded as a submitted report')
    record_errors = []
    _check_record(finding, 'finding', run, set(), record_errors)
    if record_errors:
        raise ValueError('Fix the finding record before adding it to history: '
                         + '; '.join(record_errors))
    target_root = meta.get('target_root')
    project_key = (canonical_project(project) if project else
                   meta.get('history_project_key') or meta.get('project_key'))
    if not project_key and target_root and Path(target_root).is_dir():
        project_key = project_for_repo(target_root)
    if not project_key:
        raise ValueError('No canonical repository remote in run.json; pass --project owner/repo')
    if program and (len(program) > 120 or any(ord(c) < 32 for c in program)):
        raise ValueError('Program label must be plain text of at most 120 characters')
    if hours is not None:
        try:
            hours = float(hours)
        except (TypeError, ValueError) as exc:
            raise ValueError('--hours must be a non-negative number') from exc
        if hours < 0 or hours == float('inf') or hours != hours:
            raise ValueError('--hours must be a finite non-negative number')
    path = _history_path(ledger, target_root=target_root, run_dir=run)
    rows = _history_rows(path)
    if meta.get('history_project_key') != project_key:
        meta['history_project_key'] = project_key
        dump(run / 'run.json', meta)
    latest = {row['case_id']: row for row in rows}
    if case_id:
        prior = latest.get(case_id)
        if not prior:
            raise ValueError('Unknown --case-id; omit it to start a new report record')
        if (prior['project_key'] != project_key or
                prior['bug_class'] != finding.get('bug_class') or
                prior['finding_id'] != finding_id):
            raise ValueError('--case-id belongs to a different report, project or bug class')
    else:
        case_id = 'H-' + uuid.uuid4().hex[:12]
    event = {
        'schema_version': HISTORY_SCHEMA, 'case_id': case_id,
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'run_id': meta.get('run_id'), 'project_key': project_key,
        'program': program.strip(), 'finding_id': finding_id,
        'revision': finding.get('revision', ''), 'bug_class': finding.get('bug_class', ''),
        'lens': finding.get('lens') or 'unattributed',
        'affected_paths': finding.get('affected_paths', []),
        'root_cause_summary': finding.get('root_cause', '')[:500],
        'severity': finding.get('severity', 'unassessed'),
        'disposition': disposition, 'reason': reason, 'effort_hours': hours,
    }
    _append_history(path, event)
    return {'case_id': case_id, 'disposition': disposition, 'history': str(path),
            'stored_fields': sorted(event),
            'notice': 'Private local metadata only; no report text, source, PoC, wallet or credentials.'}


def history_import(project, finding_id, bug_class, surfaces, root_cause, disposition,
                   ledger=None, program='', case_id=None, reason='unspecified', hours=None,
                   lens='unattributed'):
    project_key = canonical_project(project)
    if not project_key:
        raise ValueError('--project must be a repository URL or host/owner/repo key')
    if disposition not in HISTORY_DISPOSITIONS or reason not in HISTORY_REASONS:
        raise ValueError('Invalid disposition or reason category')
    if not isinstance(finding_id, str) or not finding_id.strip() or len(finding_id) > 120:
        raise ValueError('--finding-id must be nonempty and at most 120 characters')
    if not isinstance(bug_class, str) or not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*', bug_class):
        raise ValueError('--bug-class must be a kebab-case label')
    if not isinstance(surfaces, list) or not surfaces or not all(has_text(x) for x in surfaces):
        raise ValueError('At least one --surface is required')
    if any(len(x) > 240 or any(ord(c) < 32 for c in x) for x in surfaces):
        raise ValueError('Each --surface must be plain text of at most 240 characters')
    if not has_text(root_cause) or len(root_cause) > 500:
        raise ValueError('--root-cause must be a short mechanism summary (1-500 characters)')
    if program and (len(program) > 120 or any(ord(c) < 32 for c in program)):
        raise ValueError('--program must be plain text of at most 120 characters')
    if lens and lens not in LENSES and lens not in ('manual', 'unattributed'):
        raise ValueError('--lens must name a registered lens or manual')
    if hours is not None:
        try:
            hours = float(hours)
        except (TypeError, ValueError) as exc:
            raise ValueError('--hours must be a finite non-negative number') from exc
        if hours < 0 or hours == float('inf') or hours != hours:
            raise ValueError('--hours must be a finite non-negative number')
    path = _history_path(ledger)
    old = _latest_history(_history_rows(path))
    if case_id:
        prior = next((row for row in old if row['case_id'] == case_id), None)
        if not prior:
            raise ValueError('Unknown --case-id; omit it to start a new report record')
        if (prior['project_key'] != project_key or prior['bug_class'] != bug_class or
                prior['finding_id'] != finding_id.strip()):
            raise ValueError('--case-id belongs to a different report, project or bug class')
    else:
        case_id = 'H-' + uuid.uuid4().hex[:12]
    event = {
        'schema_version': HISTORY_SCHEMA, 'case_id': case_id,
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'run_id': None,
        'project_key': project_key, 'program': program.strip(), 'finding_id': finding_id.strip(),
        'revision': '', 'bug_class': bug_class, 'lens': lens or 'unattributed',
        'affected_paths': surfaces, 'root_cause_summary': root_cause.strip(),
        'severity': 'unassessed', 'disposition': disposition, 'reason': reason,
        'effort_hours': hours,
    }
    _append_history(path, event)
    return {'case_id': case_id, 'disposition': disposition, 'history': str(path),
            'notice': 'Imported as private metadata; verify every field against the original record.'}


def _latest_history(rows):
    latest = {}
    for row in rows:
        latest[row['case_id']] = row
    return list(latest.values())


def _history_input_digest(records):
    """Fingerprint only the candidate fields used by the personal-history comparison."""
    inputs = []
    for row in records:
        if not isinstance(row, dict) or row.get('status') == 'refuted':
            continue
        inputs.append({key: row.get(key) for key in
                       ('id', 'status', 'bug_class', 'affected_paths', 'root_cause')})
    inputs.sort(key=lambda row: str(row.get('id', '')))
    payload = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _mechanism_overlap(left, right):
    tokens = lambda value: {w for w in re.findall(r'[a-z0-9]+', str(value).lower()) if len(w) > 2}
    a, b = tokens(left), tokens(right)
    shared = a & b
    return len(shared) / min(len(a), len(b)) if shared and a and b else 0.0


def history_check(run, ledger=None, project=None):
    run = Path(run).resolve()
    meta = read_json(run / 'run.json')
    target_root = meta.get('target_root')
    path = _history_path(ledger, target_root=target_root, run_dir=run)
    project_key = (canonical_project(project) if project else
                   meta.get('history_project_key') or meta.get('project_key'))
    if not project_key and target_root and Path(target_root).is_dir():
        project_key = project_for_repo(target_root)
    if not project_key:
        raise ValueError('No canonical repository remote in run.json; pass --project owner/repo')
    records = read_json(run / 'findings.json')
    if not isinstance(records, list):
        raise ValueError('findings.json must be an array')
    history = _history_rows(path)
    _private_history_file(path)
    old = _latest_history(history)
    prior_cases = [row for row in old if row.get('project_key') == project_key]
    prior_cases.sort(key=lambda row: str(row.get('recorded_at', '')), reverse=True)
    prior_case_fields = ('case_id', 'finding_id', 'recorded_at', 'revision', 'program', 'bug_class',
                         'lens', 'affected_paths', 'root_cause_summary', 'severity',
                         'disposition', 'reason')
    prior_case_summaries = [
        {key: row.get(key) for key in prior_case_fields}
        for row in prior_cases
    ]
    matches = []
    for finding in records:
        if not isinstance(finding, dict) or finding.get('status') == 'refuted':
            continue
        current_paths = _path_keys(finding.get('affected_paths'))
        current_class = str(finding.get('bug_class', '')).lower()
        current_cause = finding.get('root_cause', '')
        for prior in old:
            if (prior.get('run_id') == meta.get('run_id') and
                    prior.get('finding_id') == finding.get('id')):
                continue
            same_project = prior.get('project_key') == project_key
            prior_paths = _path_keys(prior.get('affected_paths'))
            shared_paths = sorted(current_paths & prior_paths)
            same_class = bool(current_class and current_class == prior.get('bug_class', '').lower())
            cause_overlap = _mechanism_overlap(current_cause,
                                               prior.get('root_cause_summary', ''))
            basis = []
            if same_project:
                if same_class:
                    basis.append('same bug class')
                if shared_paths:
                    basis.append('same path/symbol: ' + ', '.join(shared_paths[:4]))
                if cause_overlap >= 0.55:
                    basis.append('overlapping mechanism terms')
                if not basis:
                    continue
                relationship = 'same-project: review manually; not an automatic duplicate'
                priority = 2 if same_class and shared_paths else 1
            elif same_class and shared_paths:
                basis = ['same bug class', 'same path/symbol: ' + ', '.join(shared_paths[:4])]
                relationship = 'other project: related pattern, not a duplicate'
                priority = 0
            else:
                continue
            matches.append({
                'finding_id': finding.get('id'), 'case_id': prior['case_id'],
                'prior_finding_id': prior.get('finding_id'), 'project_key': prior['project_key'],
                'program': prior.get('program', ''), 'disposition': prior['disposition'],
                'bug_class': prior['bug_class'], 'affected_paths': prior['affected_paths'],
                'root_cause_summary': prior['root_cause_summary'], 'basis': basis,
                'relationship': relationship, 'review_priority': priority,
            })
    matches.sort(key=lambda row: (-row['review_priority'], row['finding_id'], row['case_id']))
    result = {
        'project_key': project_key, 'history_path': str(path), 'history_records': len(old),
        'prior_cases_total': len(prior_cases), 'prior_cases_returned': len(prior_case_summaries),
        'prior_cases': prior_case_summaries,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'run_id': meta.get('run_id'), 'findings_sha256': _history_input_digest(records),
        'matches': matches, 'candidate_matches': len({row['finding_id'] for row in matches}),
        'state': 'review-required' if matches else 'no-history-match-found',
        'notice': 'prior_cases are your own compact same-project history and can seed the hunt. '
        'Candidate matches are recall-oriented leads, not duplicate verdicts; compare '
                  'root cause, path, revision and program outcome. No match cannot reveal another '
                  'researcher\'s private submissions.',
    }
    if meta.get('history_project_key') != project_key:
        meta['history_project_key'] = project_key
        dump(run / 'run.json', meta)
    dump(run / 'history-matches.json', result)
    return result


def history_summary(ledger=None):
    path = _history_path(ledger)
    rows = _latest_history(_history_rows(path))
    counts = {status: sum(row['disposition'] == status for row in rows)
              for status in sorted(HISTORY_DISPOSITIONS)}
    closed = {'accepted', 'paid', 'duplicate', 'invalid', 'out-of-scope', 'rejected', 'withdrawn'}
    decided = sum(row['disposition'] in closed for row in rows)
    by_class, by_lens, duplicate_reasons = {}, {}, {}
    for row in rows:
        bug_class = row.get('bug_class', 'unknown')
        lens = row.get('lens', 'unattributed')
        by_class.setdefault(bug_class, {})[row['disposition']] = (
            by_class.setdefault(bug_class, {}).get(row['disposition'], 0) + 1)
        by_lens.setdefault(lens, {})[row['disposition']] = (
            by_lens.setdefault(lens, {}).get(row['disposition'], 0) + 1)
        if row['disposition'] == 'duplicate':
            reason = row.get('reason', 'unspecified')
            duplicate_reasons[reason] = duplicate_reasons.get(reason, 0) + 1
    return {
        'history': str(path), 'reports': len(rows), 'dispositions': counts,
        'duplicate_of_decided': f"{counts['duplicate']} of {decided}" if decided else '0 of 0',
        'duplicate_reasons': duplicate_reasons, 'by_bug_class': by_class, 'by_lens': by_lens,
        'notice': 'Descriptive counts from your own recorded reports; not a forecast of future '
                  'acceptance, duplicates or payout.',
    }


def lead_queue(run):
    run = Path(run).resolve()
    errors = validate(run)
    records = read_json(run / 'findings.json')
    if errors:
        return {'state': 'invalid', 'errors': errors, 'leads': []}
    leads = []
    for row in records:
        if row['status'] not in ('hypothesis', 'needs-evidence'):
            continue
        leads.append({
            'id': row['id'], 'status': row['status'], 'severity': row['severity'],
            'bug_class': row['bug_class'], 'root_cause': row['root_cause'],
            'next_experiment': row['next_experiment'],
        })
    leads.sort(key=lambda row: (0 if row['status'] == 'needs-evidence' else 1,
                                row['id']))
    return {'state': 'open-leads' if leads else 'all-leads-closed',
            'open_count': len(leads), 'leads': leads,
            'notice': 'Every open lead needs a decisive next experiment. A listed experiment is '
                      'not evidence that it was run.'}


# --------------------------------------------------------------------------- #
# structural and submission gates
# --------------------------------------------------------------------------- #

def _check_record(row, prefix, run, seen, errors):
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        errors.append(prefix + ': missing ' + ', '.join(missing))
        return False
    ident = row['id']
    if not isinstance(ident, str) or not re.fullmatch(r'BP-[0-9]{3,}', ident):
        errors.append(prefix + ': invalid id')
    elif ident in seen:
        errors.append(prefix + ': duplicate id')
    else:
        seen.add(ident)
    for key in ('title', 'root_cause', 'attacker_capabilities', 'preconditions', 'impact',
                'revision'):
        if not has_text(row[key]):
            errors.append(prefix + ': empty or non-string ' + key)
    if not isinstance(row['bug_class'], str) or not re.fullmatch(r'[a-z0-9]+(-[a-z0-9]+)*',
                                                                 row['bug_class'] or ''):
        errors.append(prefix + ': bug_class must be a kebab-case label')
    lens = row.get('lens')
    if lens is not None and not isinstance(lens, str):
        errors.append(prefix + ': lens must be a string naming the lens that produced this')
    elif isinstance(lens, str) and lens and lens not in LENSES and lens != 'manual':
        errors.append(prefix + ': lens must be one of ' + ', '.join(LENSES) + ', or manual')
    paths = row['affected_paths']
    if not isinstance(paths, list) or not paths or not all(has_text(p) for p in paths):
        errors.append(prefix + ': affected_paths must be a nonempty string array')
    if row['status'] in ('hypothesis', 'needs-evidence'):
        next_step = row.get('next_experiment')
        if not isinstance(next_step, dict):
            errors.append(prefix + ': open candidate requires next_experiment object')
        else:
            for key in ('question', 'method', 'expected_evidence'):
                if not has_text(next_step.get(key)):
                    errors.append(prefix + ': open candidate requires next_experiment.' + key)
            if 'blocker' in next_step and not isinstance(next_step['blocker'], str):
                errors.append(prefix + ': next_experiment.blocker must be a string')
    history_review = row.get('history_review')
    if history_review is not None:
        if not isinstance(history_review, dict):
            errors.append(prefix + ': history_review must be an object')
        else:
            if history_review.get('status') not in HISTORY_REVIEW_STATUSES:
                errors.append(prefix + ': invalid history_review.status')
            case_ids = history_review.get('case_ids', [])
            if not isinstance(case_ids, list) or not all(has_text(x) for x in case_ids):
                errors.append(prefix + ': history_review.case_ids must be a string array')
            if not isinstance(history_review.get('rationale', ''), str):
                errors.append(prefix + ': history_review.rationale must be a string')
            if not isinstance(history_review.get('evidence', ''), str):
                errors.append(prefix + ': history_review.evidence must be a string')
    for key, allowed in (('status', STATUSES), ('severity', SEVERITIES),
                         ('scope_status', SCOPE_STATUSES),
                         ('deployment_status', DEPLOY_STATUSES)):
        if not isinstance(row[key], str) or row[key] not in allowed:
            errors.append(prefix + ': invalid ' + key)
    novelty = row['novelty']
    if not isinstance(novelty, dict):
        errors.append(prefix + ': novelty must be an object')
    else:
        if novelty.get('status') not in NOVELTY_STATUSES:
            errors.append(prefix + ': invalid novelty.status')
        sources = novelty.get('sources')
        if not isinstance(sources, list) or not all(has_text(s) for s in sources):
            errors.append(prefix + ': novelty.sources must be a string array')
        elif novelty.get('status') != 'not-checked' and not sources:
            errors.append(prefix + ': novelty check requires sources and comparison notes')
    objections = row['objections']
    if not isinstance(objections, list):
        errors.append(prefix + ': objections must be an array')
    else:
        for j, item in enumerate(objections):
            label = f'{prefix}.objections[{j}]'
            if not isinstance(item, dict):
                errors.append(label + ': must be an object')
                continue
            if item.get('gate') not in GATES:
                errors.append(label + ': gate must be one of ' + ', '.join(sorted(GATES)))
            if not has_text(item.get('claim')):
                errors.append(label + ': claim is required')
            outcome = item.get('outcome')
            if outcome not in OBJECTION_OUTCOMES:
                errors.append(label + ': outcome must be one of '
                              + ', '.join(sorted(OBJECTION_OUTCOMES)))
            # A withdrawn objection is one that could produce no anchor - that is why it was
            # withdrawn - so requiring one here would make the outcome unrecordable.
            elif outcome != 'withdrawn' and not has_text(item.get('anchor')):
                errors.append(label + ': anchor is required unless the objection was withdrawn')
            if outcome == 'answered':
                # Symmetry: an answer defeats an objection only with its own anchor.
                for key in ('answer', 'answer_anchor'):
                    if not has_text(item.get(key)):
                        errors.append(label + ': an answered objection requires ' + key)
    evidence = row['evidence']
    if not isinstance(evidence, dict):
        errors.append(prefix + ': evidence must be an object')
        return False
    if row['status'] == 'refuted' and not has_text(row['rejection_reason']):
        errors.append(prefix + ': refutation requires an evidence-backed reason')
    if row['status'] == 'verified':
        for key in ('command', 'assertion', 'negative_control', 'source_integrity'):
            if not has_text(evidence.get(key)):
                errors.append(prefix + ': verified requires evidence.' + key)
        if type(evidence.get('exit_code')) is not int:
            errors.append(prefix + ': verified requires observed integer exit_code')
        for key in ('log_path', 'poc_path'):
            value = evidence.get(key)
            if not has_text(value):
                errors.append(prefix + ': verified requires evidence.' + key)
                continue
            rel = Path(value)
            target = (run / rel).resolve()
            if rel.is_absolute() or run not in target.parents or not target.is_file():
                errors.append(prefix + ': evidence.' + key + ' must resolve to a file inside the run')
            elif target.stat().st_size == 0:
                errors.append(prefix + ': evidence.' + key + ' must not be empty')
    return True


def _check_submission(row, prefix, run, errors, history_match_ids=None):
    """Gates that encode why bounty reports actually get rejected."""
    if row['status'] != 'verified':
        errors.append(prefix + ': submission requires status verified, not ' + row['status'])
    if row['scope_status'] != 'in-scope':
        errors.append(prefix + ': submission requires scope_status in-scope (program rules read)')
    if row['deployment_status'] not in ('exact', 'not-applicable'):
        errors.append(prefix + ': submission requires deployment_status exact or not-applicable; '
                      'reporting against a revision that is not deployed is the most common rejection')
    if row['severity'] == 'unassessed':
        errors.append(prefix + ': submission requires an assessed severity')
    if not has_text(row.get('severity_rationale')):
        errors.append(prefix + ': submission requires severity_rationale citing the program rubric')
    if row['novelty']['status'] != 'no-public-match-found':
        errors.append(prefix + ': submission requires novelty no-public-match-found, got '
                      + str(row['novelty']['status']))
    elif len(row['novelty']['sources']) < 2:
        errors.append(prefix + ': submission requires at least two checked novelty sources '
                      '(program known-issues list and one public audit/contest search)')
    if not has_text(row['evidence'].get('impact_quantification')):
        errors.append(prefix + ': submission requires evidence.impact_quantification '
                      '(what moves, how much, at what attacker cost)')
    history = row.get('history_review')
    if not isinstance(history, dict):
        errors.append(prefix + ': submission requires a personal history review')
    else:
        status = history.get('status')
        case_ids = history.get('case_ids', [])
        rationale = history.get('rationale', '')
        if status == 'unchecked':
            errors.append(prefix + ': personal history was not checked; run history check')
        elif status == 'same-mechanism':
            errors.append(prefix + ': personal history marks the same mechanism; do not submit')
        elif status == 'unavailable':
            errors.append(prefix + ': personal history is unavailable; resolve the history check')
        elif status == 'no-match':
            if case_ids:
                errors.append(prefix + ': no-match cannot list prior case_ids')
            if not has_text(rationale):
                errors.append(prefix + ': no-match requires the history check result/date')
            if history_match_ids and history_match_ids.get(row['id']):
                errors.append(prefix + ': personal history has matching cases; review them before submission')
        elif status in ('different-root-cause', 'regression'):
            if not case_ids:
                errors.append(prefix + ': reviewed history match requires case_ids')
            if not has_text(rationale):
                errors.append(prefix + ': reviewed history match requires a mechanism comparison')
            if (history_match_ids is not None and isinstance(case_ids, list) and
                    all(isinstance(case_id, str) for case_id in case_ids)):
                detected = set(history_match_ids.get(row['id'], set()))
                reviewed = set(case_ids)
                if detected != reviewed:
                    errors.append(prefix + ': history case_ids must cover every match from history check')
            if status == 'regression' and not has_text(history.get('evidence')):
                errors.append(prefix + ': regression requires evidence that the issue was reintroduced in the current deployment')
    if not (run / 'dup-map.json').is_file():
        errors.append(prefix + ': submission requires a built dup-map.json in the run')
    objections = row['objections'] if isinstance(row['objections'], list) else []
    if not objections:
        errors.append(prefix + ': submission requires a recorded triage exchange; a finding no '
                      'agent attacked is a finding nobody has reviewed')
    sustained = [o for o in objections if isinstance(o, dict) and o.get('outcome') == 'sustained']
    if sustained:
        gates = ', '.join(sorted({str(o.get('gate')) for o in sustained}))
        errors.append(prefix + ': submission blocked by sustained objection(s) on ' + gates
                      + '; answer them with an anchor or mark the finding refuted')


def _submission_history_matches(run, meta, records, errors):
    """Require a fresh history comparison and return its detected case ids by finding."""
    path = run / 'history-matches.json'
    if not path.is_file():
        errors.append('history-matches.json: run history check before submission')
        return None
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError):
        errors.append('history-matches.json: must be valid JSON from history check')
        return None
    if not isinstance(data, dict) or not isinstance(data.get('matches'), list):
        errors.append('history-matches.json: invalid history check result')
        return None
    if data.get('run_id') != meta.get('run_id'):
        errors.append('history-matches.json: belongs to a different run; rerun history check')
    expected_project = meta.get('history_project_key') or meta.get('project_key')
    if data.get('project_key') != expected_project:
        errors.append('history-matches.json: project key changed; rerun history check')
    if data.get('findings_sha256') != _history_input_digest(records):
        errors.append('history-matches.json: candidate mechanisms changed; rerun history check')
    by_finding = {}
    for i, match in enumerate(data['matches']):
        if (not isinstance(match, dict) or not has_text(match.get('finding_id')) or
                not has_text(match.get('case_id'))):
            errors.append(f'history-matches.json: matches[{i}] is missing finding_id or case_id')
            continue
        by_finding.setdefault(match['finding_id'], set()).add(match['case_id'])
    return by_finding


def validate(run, submission=False):
    run = Path(run).resolve()
    errors = []
    meta_path = run / 'run.json'
    if meta_path.is_file():
        meta = read_json(meta_path)
        found = meta.get('schema_version')
        if found != SCHEMA_VERSION:
            errors.append(f'run.json: schema_version {found!r} is not {SCHEMA_VERSION}; '
                          'start a new run directory with this version of the helper')
    else:
        meta = {}
        errors.append('run.json: missing; this directory was not created by init')
    records = read_json(run / 'findings.json')
    if not isinstance(records, list):
        return errors + ['findings.json must be an array']
    history_matches = (_submission_history_matches(run, meta, records, errors)
                       if submission else None)
    seen = set()
    for i, row in enumerate(records):
        prefix = f'finding[{i}]'
        if not isinstance(row, dict):
            errors.append(prefix + ': must be an object')
            continue
        complete = _check_record(row, prefix, run, seen, errors)
        if complete and submission:
            _check_submission(row, prefix, run, errors, history_matches)
    if submission and not records:
        errors.append('findings.json: no records to submit')
    return errors


# --------------------------------------------------------------------------- #
# duplicate map
# --------------------------------------------------------------------------- #

DUP_KINDS = {'program-known-issue', 'past-audit', 'contest-finding', 'docs-acknowledged',
             'public-disclosure'}


def check_dup_map(run):
    """Flag findings whose surface and bug class were already publicly burned."""
    run = Path(run).resolve()
    entries = read_json(run / 'dup-map.json')
    records = read_json(run / 'findings.json')
    errors, collisions = [], []
    if not isinstance(entries, list):
        return ['dup-map.json must be an array'], []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f'dup-map[{i}]: must be an object')
            continue
        if not has_text(entry.get('source')):
            errors.append(f'dup-map[{i}]: source is required (URL or document reference)')
        if entry.get('kind') not in DUP_KINDS:
            errors.append(f'dup-map[{i}]: kind must be one of ' + ', '.join(sorted(DUP_KINDS)))
        surfaces = entry.get('surfaces')
        if not isinstance(surfaces, list) or not surfaces or not all(has_text(s) for s in surfaces):
            errors.append(f'dup-map[{i}]: surfaces must be a nonempty string array')
    if errors:
        return errors, []
    for row in records if isinstance(records, list) else []:
        if not isinstance(row, dict) or row.get('status') == 'refuted':
            continue
        paths = [p.lower() for p in row.get('affected_paths', []) if isinstance(p, str)]
        bug_class = (row.get('bug_class') or '').lower()
        for entry in entries:
            classes = [c.lower() for c in entry.get('bug_classes', []) if isinstance(c, str)]
            for surface in entry['surfaces']:
                key = surface.lower()
                if not any(key in p or p in key for p in paths):
                    continue
                if classes and bug_class and bug_class not in classes:
                    continue
                collisions.append({
                    'finding': row.get('id'), 'bug_class': row.get('bug_class'),
                    'surface': surface, 'dup_kind': entry.get('kind'),
                    'source': entry.get('source'),
                    'confidence': 'class-match' if classes and bug_class in classes
                                  else 'surface-only',
                    'note': entry.get('note', '')})
                break
    return errors, collisions


# --------------------------------------------------------------------------- #
# post-audit delta
# --------------------------------------------------------------------------- #

SOLIDITY_SIGNALS = (
    ('external-call', 3, re.compile(r'\.(call|delegatecall|staticcall)\s*[({]|functionCall')),
    ('token-move', 3, re.compile(r'safeTransfer|safeTransferFrom|\.transfer\s*\(|\.transferFrom\s*\(')),
    ('value-flow', 3, re.compile(r'msg\.value|address\(this\)\.balance|payable\s*\(')),
    ('mint-burn', 2, re.compile(r'\b_?(mint|burn)\s*\(')),
    ('aggregate-write', 2, re.compile(r'\b(total|cumulative|accrued|pending)[A-Za-z]*\s*(\+=|-=|=)')),
    ('auth-edge', 2, re.compile(r'onlyOwner|onlyRole|_checkRole|require\s*\(\s*msg\.sender')),
    ('callback-entry', 3, re.compile(r'function\s+(on[A-Z]\w*|\w*[Cc]allback|lzCompose|lzReceive|'
                                     r'executeOperation|uniswapV\dSwapCallback|receiveFlashLoan)')),
    ('oracle-read', 3, re.compile(r'latestAnswer|latestRoundData|getPrice|consult|staticcall.*price',
                                  re.IGNORECASE)),
    ('unchecked-math', 1, re.compile(r'unchecked\s*{')),
    ('narrow-cast', 1, re.compile(r'\buint(8|16|32|64|96|112|128)\s*\(')),
    ('delegate-upgrade', 3, re.compile(r'upgradeTo|_authorizeUpgrade|initializer|reinitializer')),
    ('hardcoded-constant', 2, re.compile(r'(constant|immutable)\s+\w+\s*=\s*(0x[0-9a-fA-F]{6,}|\d+)')),
)
RUST_SIGNALS = (
    ('cpi-invoke', 3, re.compile(r'invoke_signed|invoke\s*\(|CpiContext')),
    ('account-constraint', 2, re.compile(r'#\[account\(')),
    ('unchecked-account', 3, re.compile(r'UncheckedAccount|AccountInfo<')),
    ('pda-seed', 2, re.compile(r'seeds\s*=|find_program_address|create_program_address')),
    ('signer-check', 2, re.compile(r'is_signer|Signer<')),
    ('owner-check', 3, re.compile(r'\.owner\s*==|owner\s*=\s*')),
    ('arith', 2, re.compile(r'checked_(add|sub|mul|div)|saturating_|as\s+u(8|16|32|64)')),
    ('close-realloc', 3, re.compile(r'close\s*=|realloc|try_borrow_mut_lamports')),
    ('token-program', 2, re.compile(r'token_interface|spl_token|Token2022|TokenAccount')),
)
TEST_HINTS = ('test', 'tests', 'spec', 'mock', 'mocks', 'fixture', 'fixtures')


def _is_test_path(path):
    lowered = path.lower()
    name = Path(lowered).name
    if name.endswith(('.t.sol', '_test.go', '_test.py', '.test.ts', '.spec.ts')):
        return True
    return any(part in TEST_HINTS for part in Path(lowered).parts) or 'mock' in name


def _signals_for(path):
    suffix = Path(path).suffix
    if suffix == '.rs':
        return RUST_SIGNALS
    if suffix in ('.sol', '.vy', '.yul', '.huff'):
        return SOLIDITY_SIGNALS
    return SOLIDITY_SIGNALS + RUST_SIGNALS


def delta(repo, since, scope_prefixes=None, limit=40):
    repo = Path(repo).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    try:
        base = git(root, 'rev-parse', '--verify', '--quiet', since + '^{commit}').strip()
    except subprocess.CalledProcessError:
        raise ValueError(f'revision {since!r} is not in this repository; pass the exact '
                         'commit the last audit covered, and never guess a recent range')
    head = git(root, 'rev-parse', 'HEAD').strip()
    raw = git(root, 'diff', '--numstat', '-M', f'{base}..{head}')
    tracked = [p for p in git(root, 'ls-files', '-z').split('\0') if p]
    test_corpus = []
    for path in tracked:
        if _is_test_path(path) and Path(path).suffix in SOURCE_SUFFIXES:
            try:
                test_corpus.append((root / path).read_text(encoding='utf-8', errors='replace'))
            except OSError:
                continue
    test_blob = '\n'.join(test_corpus)
    rows, skipped_tests = [], 0
    for line in raw.splitlines():
        parts = line.split('\t')
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if '=>' in path:  # rename: git prints "old => new"
            path = path.split('=>')[-1].strip(' {}')
        if Path(path).suffix not in SOURCE_SUFFIXES:
            continue
        if scope_prefixes and not any(path.startswith(p) for p in scope_prefixes):
            continue
        if _is_test_path(path):
            skipped_tests += 1
            continue
        churn = sum(int(v) for v in (added, removed) if v.isdigit())
        full = root / path
        text = ''
        if full.is_file():
            try:
                text = full.read_text(encoding='utf-8', errors='replace')
            except OSError:
                text = ''
        hits = {}
        weight = 0
        for name, value, pattern in _signals_for(path):
            found = len(pattern.findall(text))
            if found:
                hits[name] = found
                weight += value
        stem = Path(path).stem
        untested = bool(stem) and stem not in test_blob
        score = churn ** 0.5 * (1 + weight) * (1.5 if untested else 1.0)
        rows.append({'path': path, 'churn': churn, 'signal_weight': weight,
                     'signals': hits, 'untested_by_name': untested,
                     'exists_at_head': full.is_file(), 'score': round(score, 2)})
    rows.sort(key=lambda r: (-r['score'], r['path']))
    return {'base': base, 'head': head, 'scope_prefixes': scope_prefixes or [],
            'changed_source_files': len(rows), 'test_files_excluded': skipped_tests,
            'ranked': rows[:limit],
            'notice': 'Ranking is a reading order over changed non-test source, not a '
                      'vulnerability claim. untested_by_name is a filename heuristic, not coverage.'}


# --------------------------------------------------------------------------- #
# lens bundles
# --------------------------------------------------------------------------- #

LENSES = ('delta', 'upstream-diff', 'coverage-gap', 'privileged-path', 'accounting',
          'integration-auth', 'external-call', 'economics', 'liveness', 'upgrade',
          'live-reality', 'anchor-account', 'seam', 'business-logic',
          'temporal-logic', 'recovery-failure', 'semantic-mismatch', 'composition')
TRIAGE = 'triage'
AIM_LENSES = ('delta', 'upstream-diff', 'coverage-gap')
# The six highest-yield mechanism lenses. privileged-path leads because access control and
# initialization are the categories automated reviewers measurably miss most, and the ones
# the largest real losses came from.
ATTACK_LENSES = ('privileged-path', 'accounting', 'integration-auth', 'external-call',
                 'economics', 'liveness')
CONFIG_LENSES = ('live-reality', 'upgrade')
LOGIC_LENSES = ('business-logic', 'temporal-logic', 'composition')
CROSS_STACK_LENSES = ('semantic-mismatch', 'recovery-failure')
BUNDLE_WARN_BYTES = 400_000

BUNDLE_HEADER = """# Hunt bundle: {lens}

You are one lens of a bounty hunt on `{target}` at commit `{commit}`.

Read this bundle once, top to bottom, then hunt. It holds, in order: how to think (SOP), the
rules every lens obeys, YOUR lens procedure, the run context, and the in-scope source.

Return only CANDIDATE and LEAD blocks in the format the shared rules define. Do not refute your
own candidates - a later pass does that against written gates, and it needs your claim at full
strength. Do not claim any command ran, test passed or chain value was read unless you did it.
"""

BUNDLE_FOOTER = """
---

# Your task, restated

Lens: **{lens}**. Target: `{target}` @ `{commit}`.

Hunt your lens over the source above, aimed at the ranked surfaces when a ranking is included.
Weaponize anything you find across every sibling. Escalate each finding to the worst variant the
evidence actually reaches. Emit CANDIDATE and LEAD blocks only, each with a `surface`, a
kebab-case `bug_class`, a concrete `proof` from this source, and the one `experiment` that would
settle it. Prefer a LEAD over dropping a trail.
"""


TRIAGE_HEADER = """# Triage bundle

You are the bounty program's triage engineer, reviewing reports against `{target}` at commit
`{commit}`.

This bundle holds, in order: how to read code, your triage instructions, the impact ladder, the
records under review, the run context, and the in-scope source.

Your job is to reject what should be rejected, and to say exactly what stops each claim. Every
objection carries an anchor - quoted code, quoted specification, a named test, or a live chain
read. An objection you cannot anchor is withdrawn, not weighed. Concede explicitly when you
attacked a gate and could not break it.
"""

TRIAGE_FOOTER = """
---

# Your task, restated

Target: `{target}` @ `{commit}`. For every record above, work the five gates plus the evidence
itself, and emit OBJECTION blocks with `gate`, `anchor` type and the quoted evidence, plus
CONCEDED blocks where you tried and failed. End with a one-line verdict per record: dead, demote,
severity-down, eligibility-blocked, or survives.

Reject on anchors, never on impressions. Never reject because the code is well audited, widely
forked or formally verified - those make a surviving bug more valuable, not less likely.
"""


def _fenced(path, text):
    fence = '```'
    while fence in text:
        fence += '`'
    language = {'.sol': 'solidity', '.rs': 'rust', '.vy': 'python', '.move': 'move',
                '.cairo': 'cairo', '.py': 'python', '.ts': 'typescript', '.js': 'javascript',
                '.go': 'go'}.get(Path(path).suffix, '')
    return f'### {path}\n\n{fence}{language}\n{text.rstrip()}\n{fence}\n'


TESTS_BUDGET_BYTES = 600_000


def _relevant_tests(root, all_tests, in_scope, scope_prefixes):
    """Keep only the tests that plausibly cover the scoped source.

    Bundling every test file in the repository defeats the point of --scope: on a repo with a
    hundred test files the coverage-gap bundle becomes too large to read, which is the one thing
    a lens must not be handed.
    """
    if not scope_prefixes:
        return all_tests, []
    stems = {Path(p).stem.lower() for p in in_scope if Path(p).stem}
    kept, omitted, used = [], [], 0
    for path in all_tests:
        reason = None
        if any(path.startswith(prefix) for prefix in scope_prefixes):
            reason = 'under a scope prefix'
        else:
            name = Path(path).stem.lower()
            if any(stem in name or name.replace('.t', '') in stems for stem in stems):
                reason = 'filename matches an in-scope source file'
            else:
                try:
                    text = (root / path).read_text(encoding='utf-8', errors='replace')
                except OSError:
                    text = ''
                if any(stem in text.lower() for stem in stems):
                    reason = 'mentions an in-scope source file'
        if reason is None:
            omitted.append(path)
            continue
        try:
            size = (root / path).stat().st_size
        except OSError:
            size = 0
        if used + size > TESTS_BUDGET_BYTES:
            omitted.append(path)
            continue
        used += size
        kept.append(path)
    return kept, omitted


def _collect(root, paths):
    parts, skipped = [], []
    for path in paths:
        try:
            text = (root / path).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            skipped.append(path)
            continue
        parts.append(_fenced(path, text))
    return '\n'.join(parts), skipped


def _redact_context_secrets(text):
    text = SECRET_KEY_VALUE.sub(lambda m: m.group(1) + m.group(2) + '<redacted>' + m.group(4), text)
    return UNQUOTED_SECRET_KEY_VALUE.sub(r'\1<redacted>', text)


def _collect_project_context(root, paths):
    parts, skipped = [], []
    for path in paths:
        try:
            body = (root / path).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            skipped.append(path)
            continue
        parts.append(_fenced(path, _redact_context_secrets(body)))
    return '\n'.join(parts), skipped


def _is_sensitive_context_path(path):
    parts = [part.lower() for part in Path(path).parts]
    name = parts[-1] if parts else ''
    return (any(part in SENSITIVE_PATH_PARTS for part in parts)
            or any(marker in name for marker in ('secret', 'credential', 'keystore', 'mnemonic'))
            or name.startswith('.env')
            or Path(name).suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.keystore'})


def _is_project_context_path(path):
    """Select behavior-defining metadata without sweeping arbitrary data files."""
    p = Path(path)
    parts = [part.lower() for part in p.parts]
    name = p.name.lower()
    if _is_test_path(path) or _is_sensitive_context_path(path):
        return False
    if name in CONFIG_ROOT_FILES or name.startswith('rust-toolchain'):
        return True
    if p.suffix.lower() not in CONFIG_SUFFIXES:
        return False
    return any(part in CONFIG_DIRS for part in parts[:-1]) or name in {
        'package.json', 'cargo.toml', 'move.toml', 'scarb.toml', 'foundry.toml',
        'anchor.toml', 'go.mod', 'pyproject.toml'}


def _collect_context_files(root, tracked):
    selected, omitted, used = [], [], 0
    for path in tracked:
        if not _is_project_context_path(path):
            continue
        try:
            size = (root / path).stat().st_size
        except OSError:
            omitted.append(path)
            continue
        if size > CONFIG_BUNDLE_MAX_FILE_BYTES or used + size > CONFIG_BUNDLE_MAX_TOTAL_BYTES:
            omitted.append(path)
            continue
        selected.append(path)
        used += size
    return selected, omitted


def bundle(repo, run, lenses, scope_prefixes=None, includes=None):
    """Assemble one deterministic bundle per lens. This is the dispatch mechanic:
    a pass that did not run this command did not bundle its source."""
    repo, run = Path(repo).resolve(), Path(run).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    commit = git(root, 'rev-parse', 'HEAD').strip()
    references = SKILL_ROOT / 'references'
    routed = load_stack_route().route(root)
    chosen = []
    for lens in lenses:
        if lens == 'all':
            chosen.extend(LENSES)
        elif lens == 'aim':
            chosen.extend(AIM_LENSES)
        elif lens == 'attack':
            chosen.extend(ATTACK_LENSES)
        elif lens == 'config':
            chosen.extend(CONFIG_LENSES)
        elif lens == 'logic':
            chosen.extend(LOGIC_LENSES)
        elif lens == 'cross-stack':
            chosen.extend(CROSS_STACK_LENSES)
        elif lens == 'recommended':
            chosen.extend(routed['prioritization']['selected'])
        elif lens in LENSES or lens == TRIAGE:
            chosen.append(lens)
        else:
            raise ValueError(f'unknown lens {lens!r}; choose from ' + ', '.join(LENSES)
                             + f', {TRIAGE}, or the groups aim / attack / config / logic / cross-stack / recommended / all')
    chosen = list(dict.fromkeys(chosen))
    for lens in chosen:
        source_file = (references / f'{TRIAGE}.md' if lens == TRIAGE
                       else references / 'hunt-agents' / f'{lens}-agent.md')
        if not source_file.is_file():
            raise ValueError(f'instruction file missing for {lens!r}; the skill install '
                             'is incomplete')

    tracked = [p for p in git(root, 'ls-files', '-z').split('\0') if p]
    in_scope = [p for p in tracked if Path(p).suffix in SOURCE_SUFFIXES
                and not _is_test_path(p)
                and (not scope_prefixes or any(p.startswith(s) for s in scope_prefixes))]
    all_tests = [p for p in tracked if Path(p).suffix in SOURCE_SUFFIXES and _is_test_path(p)]
    test_paths, tests_omitted = _relevant_tests(root, all_tests, in_scope, scope_prefixes)
    config_paths, config_omitted = _collect_context_files(root, tracked)

    out = run / 'bundles'
    out.mkdir(parents=True, exist_ok=True)
    source, skipped = _collect(root, in_scope)
    source_doc = f'# In-scope source ({len(in_scope)} files)\n\n' + source
    (out / 'source.md').write_text(source_doc, encoding='utf-8')
    tests, _ = _collect(root, test_paths)
    tests_doc = (f'# Tests, mocks and fixtures ({len(test_paths)} files)\n\n'
                 'Read these as evidence of what the authors believed, not as code to audit.\n'
                 + (f'\n{len(tests_omitted)} further test file(s) were omitted as unrelated to the '
                    'scoped source or over the size budget; read them from the repository if a '
                    'trail leads there.\n' if tests_omitted else '')
                 + '\n' + tests)
    (out / 'tests.md').write_text(tests_doc, encoding='utf-8')
    configs, config_skipped = _collect_project_context(root, config_paths)
    config_doc = ('# Project configuration and deployment artifacts\n\n'
                  'These files can define compiler versions, deployment addresses, account '
                  'layouts, feature flags and runtime wiring. Treat them as context; confirm '
                  'which configuration is actually deployed.\n\n'
                  + (f'{len(config_omitted)} candidate file(s) omitted by path/size budget; '
                     'read them from the checkout if a trail leads there.\n\n'
                     if config_omitted else '') + configs)

    context = []
    for name in ('scope.md', 'model.md', 'coverage.md', 'dup-map.json', 'known-hypotheses.md'):
        path = run / name
        if path.is_file() and path.stat().st_size > 0:
            body = path.read_text(encoding='utf-8')
            context.append(f'## Run context: {name}\n\n```\n{body.rstrip()}\n```\n')
    for extra in includes or []:
        path = Path(extra)
        if not path.is_file():
            raise ValueError(f'--include {extra!r} is not a file')
        body = path.read_text(encoding='utf-8', errors='replace')
        context.append(f'## Included: {path.name}\n\n```\n{body.rstrip()}\n```\n')
    context_doc = '\n'.join(context)

    shared = (references / 'hunt-agents' / '_shared.md').read_text(encoding='utf-8')

    def optional(name):
        path = references / name
        return path.read_text(encoding='utf-8') if path.is_file() else ''

    sop = optional('sop.md')
    impact = optional('impact-classes.md')
    patterns = optional('hack-patterns.md')
    findings_doc = ''
    findings_path = run / 'findings.json'
    if findings_path.is_file():
        body = findings_path.read_text(encoding='utf-8')
        findings_doc = ('## The records under review\n\nAttack these. Nothing here is '
                        'established.\n\n```json\n' + body.rstrip() + '\n```\n')
    written = []
    for lens in chosen:
        if lens == TRIAGE:
            # Triage gets the records, the source and the impact ladder - but never the hunt
            # stance, which forbids self-refutation and is the opposite of this agent's job.
            pieces = [TRIAGE_HEADER.format(target=root.name, commit=commit)]
            if sop:
                pieces.append(sop)
            pieces.append((references / f'{TRIAGE}.md').read_text(encoding='utf-8'))
            for extra in (impact, patterns):
                if extra:
                    pieces.append(extra)
            if findings_doc:
                pieces.append(findings_doc)
            if context_doc:
                pieces.append(context_doc)
            if config_doc:
                pieces.append(config_doc)
            pieces.append(source_doc)
            pieces.append(TRIAGE_FOOTER.format(target=root.name, commit=commit))
            path = out / 'triage-bundle.md'
            path.write_text('\n---\n\n'.join(pieces), encoding='utf-8')
            written.append({'lens': lens, 'bundle': str(path.relative_to(run)),
                            'bytes': path.stat().st_size,
                            'records_under_review': bool(findings_doc)})
            continue
        lens_text = (references / 'hunt-agents' / f'{lens}-agent.md').read_text(encoding='utf-8')
        pieces = [BUNDLE_HEADER.format(lens=lens, target=root.name, commit=commit)]
        if sop:
            pieces.append(sop)
        pieces += [shared, lens_text]
        if lens in LOGIC_LENSES + CROSS_STACK_LENSES + ('anchor-account',):
            guide = references / 'stateful-search.md'
            if guide.is_file():
                pieces.append(guide.read_text(encoding='utf-8'))
            for selected_stack in routed['stacks']:
                adapter = references / selected_stack['adapter']
                if adapter.is_file():
                    pieces.append('# Adapter for ' + selected_stack['stack'] + '\n\n'
                                  + adapter.read_text(encoding='utf-8'))
        # The ladder tells the lens how far to escalate; the precedents make a candidate concrete
        # and much harder for triage to call theoretical.
        for extra in (impact, patterns):
            if extra:
                pieces.append(extra)
        if lens in ('seam', 'composition') and findings_doc:
            pieces.append(findings_doc.replace('Attack these. Nothing here is established.',
                                               'The earlier passes produced these. Cross them.'))
        if context_doc:
            pieces.append(context_doc)
        if config_doc:
            pieces.append(config_doc)
        pieces.append(source_doc)
        if lens in ('coverage-gap', 'business-logic', 'temporal-logic', 'composition'):
            pieces.append(tests_doc)
        pieces.append(BUNDLE_FOOTER.format(lens=lens, target=root.name, commit=commit))
        path = out / f'{lens}-bundle.md'
        path.write_text('\n---\n\n'.join(pieces), encoding='utf-8')
        written.append({'lens': lens, 'bundle': str(path.relative_to(run)),
                        'bytes': path.stat().st_size})

    notes = []
    biggest = max((w['bytes'] for w in written), default=0)
    if biggest > BUNDLE_WARN_BYTES:
        notes.append(f'largest bundle is {biggest} bytes; narrow with --scope and hunt the ranked '
                     'surfaces first, or the lens will skim instead of reading')
    if skipped:
        notes.append(f'{len(skipped)} file(s) unreadable and omitted: ' + ', '.join(skipped[:5]))
    if not in_scope:
        notes.append('no in-scope source matched; check --scope and the tracked file list')
    if config_skipped:
        notes.append(f'{len(config_skipped)} configuration file(s) unreadable and omitted: '
                     + ', '.join(config_skipped[:5]))
    return {'target': str(root), 'commit': commit, 'run': str(run),
            'detected_stacks_heuristic': [x['stack'] for x in routed['stacks']],
            'in_scope_files': len(in_scope), 'test_files_bundled_for_coverage_gap': len(test_paths),
            'test_files_omitted': len(tests_omitted),
            'config_files_bundled': len(config_paths) - len(config_skipped),
            'config_files_omitted': len(config_omitted),
            'context_sections': len(context), 'bundles': written, 'notes': notes,
            'dispatch': 'Give each bundle to its own agent, in its own context. Record in '
                        'coverage.md which lenses actually ran.'}

# --------------------------------------------------------------------------- #
# target scoring
# --------------------------------------------------------------------------- #

def score_target(repo, program_path):
    program = read_json(program_path)
    repo = Path(repo).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    scope_prefixes = program.get('in_scope_paths') or []
    tracked = [p for p in git(root, 'ls-files', '-z').split('\0') if p]
    in_scope = [p for p in tracked
                if Path(p).suffix in SOURCE_SUFFIXES and not _is_test_path(p)
                and (not scope_prefixes or any(p.startswith(s) for s in scope_prefixes))]
    total_lines = 0
    for path in in_scope:
        try:
            total_lines += len((root / path).read_text(encoding='utf-8', errors='replace').splitlines())
        except OSError:
            continue
    points, reasons, unknowns = 0, [], []

    audited = program.get('audited_revision')
    new_share = None
    if audited:
        try:
            report = delta(root, audited, scope_prefixes or None, limit=10000)
            churn = sum(r['churn'] for r in report['ranked'])
            new_share = (churn / total_lines) if total_lines else None
        except (ValueError, subprocess.CalledProcessError) as exc:
            unknowns.append(f'audited_revision not usable: {exc}')
    else:
        unknowns.append('audited_revision absent: post-audit delta unknown, treat as full review')
    if new_share is not None:
        if new_share >= 0.25:
            points += 30
            reasons.append(f'{new_share:.0%} of in-scope lines churned since the audited revision '
                           '- large unreviewed surface')
        elif new_share >= 0.08:
            points += 20
            reasons.append(f'{new_share:.0%} churn since the audited revision - meaningful new code')
        else:
            points += 5
            reasons.append(f'only {new_share:.0%} churn since the audited revision - '
                           'the audited report probably covers what you will read')

    untested = []
    test_blob = []
    for path in tracked:
        if _is_test_path(path):
            try:
                test_blob.append((root / path).read_text(encoding='utf-8', errors='replace'))
            except OSError:
                continue
    blob = '\n'.join(test_blob)
    for path in in_scope:
        stem = Path(path).stem
        if stem and stem not in blob:
            untested.append(path)
    if in_scope:
        gap = len(untested) / len(in_scope)
        if gap >= 0.3:
            points += 20
            reasons.append(f'{gap:.0%} of in-scope files are never named in any test file')
        elif gap >= 0.1:
            points += 12
            reasons.append(f'{gap:.0%} of in-scope files are never named in any test file')
        else:
            points += 4
            reasons.append('test files name almost every in-scope file')
    if not blob:
        unknowns.append('no test files found: either untested, or tests live outside this repo')

    mock_files = [p for p in tracked if 'mock' in Path(p).name.lower()]
    if mock_files:
        points += 8
        reasons.append(f'{len(mock_files)} mock file(s): check whether a mock replaces the exact '
                       'component under test - that is where surviving bugs hide')

    policy = (program.get('duplicate_policy') or '').lower()
    if policy in ('first-to-report', 'first-come'):
        points += 15
        reasons.append('first-to-report: your report is not split with parallel submissions')
    elif policy:
        reasons.append(f'duplicate_policy {policy!r}: assume parallel hunters on the same surface')
    else:
        unknowns.append('duplicate_policy unknown')

    if program.get('deposit_required') is False:
        points += 10
        reasons.append('no deposit required to submit')
    elif program.get('deposit_required') is True:
        reasons.append('deposit required: only submit evidence-complete reports')
    else:
        unknowns.append('deposit_required unknown')

    known = program.get('known_issues_count')
    if isinstance(known, int) and known > 0:
        points += 8
        reasons.append(f'{known} published known issues: a usable dup map exists before you start')
    else:
        unknowns.append('known_issues_count unknown: you cannot pre-burn surfaces')

    if program.get('upstream_fork'):
        points += 12
        reasons.append(f"declared fork of {program['upstream_fork']}: diff against the canonical "
                       'upstream and hunt only the deviation')

    payout = program.get('payout_max_usd')
    if isinstance(payout, (int, float)) and payout > 0:
        reasons.append(f'max payout {payout:,.0f} USD as published')
    else:
        unknowns.append('payout_max_usd unknown')

    if total_lines > 60000:
        reasons.append(f'{total_lines} in-scope lines: too large for one sweep, '
                       'prioritise by delta and value-bearing paths')
    score = max(0, min(100, points))
    band = ('hunt' if score >= 60 else 'maybe' if score >= 35 else 'deprioritise')
    return {'program': program.get('program'), 'url': program.get('url'),
            'in_scope_files': len(in_scope), 'in_scope_lines': total_lines,
            'files_never_named_in_tests': len(untested),
            'untested_sample': untested[:15],
            'churn_share_since_audit': None if new_share is None else round(new_share, 4),
            'priority_score': score, 'band': band, 'reasons': reasons, 'unknowns': unknowns,
            'notice': 'A prioritisation heuristic over code and published program facts. '
                      'It does not predict a payout, a finding, or originality.'}


# --------------------------------------------------------------------------- #
# on-chain identity
# --------------------------------------------------------------------------- #

def rpc_call(url, method, params, opener=None, timeout=30):
    payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method,
                          'params': params}).encode('utf-8')
    request = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        # Many public RPC providers reject urllib's default agent with a 403.
        'User-Agent': f'bounty-pilot/{skill_version()} (+https://github.com/dimin4241-svg/bounty-pilot)',
    })
    open_fn = opener or (lambda req, timeout: urllib.request.urlopen(req, timeout=timeout))
    with open_fn(request, timeout=timeout) as response:
        body = json.loads(response.read().decode('utf-8'))
    if 'error' in body:
        raise ValueError(f"rpc {method} failed: {body['error']}")
    return body.get('result')


def proxy_slots():
    """EIP-1967 / EIP-1822 storage slots, derived rather than pasted."""
    keccak = load_keccak()
    def minus_one(label):
        value = int.from_bytes(keccak.keccak256(label), 'big') - 1
        return '0x' + format(value, '064x')
    return {
        'eip1967-implementation': minus_one('eip1967.proxy.implementation'),
        'eip1967-beacon': minus_one('eip1967.proxy.beacon'),
        'eip1967-admin': minus_one('eip1967.proxy.admin'),
        'eip1822-proxiable': keccak.keccak_hex('PROXIABLE'),
    }


def minimal_clone_implementation(code_hex):
    """Return the implementation address for the canonical EIP-1167 runtime, if present."""
    raw = bytes.fromhex(code_hex[2:] if code_hex.startswith('0x') else code_hex)
    prefix = bytes.fromhex('363d3d373d3d3d363d73')
    suffix = bytes.fromhex('5af43d82803e903d91602b57fd5bf3')
    if (len(raw) != len(prefix) + 20 + len(suffix)
            or not raw.startswith(prefix) or not raw.endswith(suffix)):
        return None
    return '0x' + raw[len(prefix):-len(suffix)].hex()


def looks_like_minimal_clone(code_hex):
    raw = bytes.fromhex(code_hex[2:] if code_hex.startswith('0x') else code_hex)
    return raw.startswith(bytes.fromhex('363d3d373d3d3d363d73'))


# solc appends a CBOR map then its own 2-byte big-endian length. The map starts with a
# CBOR major-type-5 header (0xa1..0xaf for 1..15 pairs) and names its hash algorithm.
METADATA_MARKERS = (b'solc', b'ipfs', b'bzzr0', b'bzzr1')
METADATA_MIN_BYTES = 0x20


def strip_metadata(code_hex):
    """Remove the trailing solc CBOR metadata, and only if the tail really is that.

    Stripping on the trailing length alone makes unrelated bytecodes compare equal: any two
    runtimes ending in the same small number would have their differing bodies cut away. So the
    tail must look like solc metadata before a single byte is removed.
    """
    raw = bytes.fromhex(code_hex[2:] if code_hex.startswith('0x') else code_hex)
    if len(raw) < METADATA_MIN_BYTES + 2:
        return raw, 0
    length = int.from_bytes(raw[-2:], 'big')
    if not METADATA_MIN_BYTES <= length <= len(raw) - 2:
        return raw, 0
    blob = raw[-(length + 2):-2]
    if not blob or not 0xa1 <= blob[0] <= 0xaf:
        return raw, 0
    if not any(marker in blob for marker in METADATA_MARKERS):
        return raw, 0
    return raw[:-(length + 2)], length + 2


def compare_bytecode(onchain_hex, artifact_hex):
    """Decide exact / partial / mismatch without pretending immutables away."""
    live, live_meta = strip_metadata(onchain_hex)
    local, local_meta = strip_metadata(artifact_hex)
    if not live:
        return {'status': 'mismatch', 'reason': 'no runtime code at the address'}
    if live == local:
        return {'status': 'exact', 'reason': 'runtime bytecode matches after metadata strip',
                'bytes': len(live), 'metadata_stripped': [live_meta, local_meta]}
    if len(live) == len(local):
        differing = sum(1 for a, b in zip(live, local) if a != b)
        return {'status': 'partial', 'bytes': len(live), 'differing_bytes': differing,
                'reason': f'same length, {differing} byte(s) differ - consistent with immutable '
                          'variables, linked libraries or a different compiler build; '
                          'not proof of the same logic'}
    return {'status': 'mismatch', 'reason': f'length differs: {len(live)} on chain vs '
                                            f'{len(local)} locally',
            'bytes': len(live), 'local_bytes': len(local)}


def read_artifact(path):
    data = read_json(path)
    for key in ('deployedBytecode', 'bytecode'):
        value = data.get(key)
        if isinstance(value, dict) and has_text(value.get('object')):
            return value['object'], key
        if has_text(value):
            return value, key
    raise ValueError('no deployedBytecode/bytecode found in the artifact')


def verify_deployment(rpc, address, artifact=None, block='latest', opener=None):
    keccak = load_keccak()
    if not re.fullmatch(r'0x[0-9a-fA-F]{40}', address):
        raise ValueError('address must be 0x followed by 40 hex characters')
    chain_id = rpc_call(rpc, 'eth_chainId', [], opener)
    tip = rpc_call(rpc, 'eth_blockNumber', [], opener)
    if block == 'latest':
        pinned = tip  # pin the tip once, so every read below sees one block
    elif isinstance(block, str) and block.isdigit():
        pinned = hex(int(block))
    else:
        pinned = block
    code = rpc_call(rpc, 'eth_getCode', [address, pinned], opener) or '0x'
    result = {'address': address, 'chain_id': int(chain_id, 16),
              'block': int(pinned, 16) if isinstance(pinned, str) and pinned.startswith('0x')
                       else pinned,
              'runtime_code_bytes': max(0, (len(code) - 2) // 2),
              'runtime_code_keccak256': keccak.keccak_hex(bytes.fromhex(code[2:]))
                                        if len(code) > 2 else None,
              'proxy': {}, 'deployment_status': 'unknown'}
    if result['runtime_code_bytes'] == 0:
        result['deployment_status'] = 'mismatch'
        result['reason'] = ('no code at this address on this chain at this block - '
                            'an EOA, a wrong chain, or not deployed yet')
        return result
    slots = proxy_slots()
    for label, slot in slots.items():
        word = rpc_call(rpc, 'eth_getStorageAt', [address, slot, pinned], opener) or '0x'
        packed = word[-40:] if len(word) >= 42 else ''
        if packed and int(packed, 16) != 0:
            result['proxy'][label] = '0x' + packed
    clone_implementation = minimal_clone_implementation(code)
    if clone_implementation:
        result['proxy']['eip1167-minimal-clone'] = clone_implementation
    elif looks_like_minimal_clone(code):
        result['proxy']['eip1167-pattern'] = 'detected-but-unresolved'
    if result['proxy']:
        result['note'] = ('this address is a proxy; verify the implementation address too, '
                          'and record which implementation was live at this block')
    implementation = (result['proxy'].get('eip1967-implementation')
                      or result['proxy'].get('eip1822-proxiable')
                      or clone_implementation)
    beacon = result['proxy'].get('eip1967-beacon')
    resolution_errors = []
    if beacon:
        try:
            raw_impl = rpc_call(rpc, 'eth_call',
                                [{'to': beacon, 'data': load_keccak().selector('implementation()')},
                                 pinned], opener)
            if not isinstance(raw_impl, str) or not re.fullmatch(r'0x[0-9a-fA-F]{64,}', raw_impl):
                raise ValueError('beacon implementation() returned malformed data')
            beacon_implementation = '0x' + raw_impl[-40:]
            if int(beacon_implementation, 16) == 0:
                raise ValueError('beacon implementation() returned the zero address')
            if implementation and implementation.lower() != beacon_implementation.lower():
                resolution_errors.append('EIP-1967 implementation and beacon resolve to different addresses')
            implementation = beacon_implementation
            result['proxy']['beacon-implementation'] = beacon_implementation
        except (OSError, ValueError, urllib.error.URLError) as exc:
            resolution_errors.append(f'could not resolve EIP-1967 beacon implementation: {exc}')
    result['proxy_resolution'] = ('resolved' if implementation and not resolution_errors
                                  else ('unresolved' if result['proxy'] else 'not-a-proxy'))
    if resolution_errors:
        result['proxy_resolution_errors'] = resolution_errors
    if implementation:
        impl_code = rpc_call(rpc, 'eth_getCode', [implementation, pinned], opener) or '0x'
        result['proxy_implementation'] = {
            'address': implementation,
            'runtime_code_bytes': max(0, (len(impl_code) - 2) // 2),
            'runtime_code_keccak256': keccak.keccak_hex(bytes.fromhex(impl_code[2:]))
                                      if len(impl_code) > 2 else None}
    if artifact:
        artifact_code, source_key = read_artifact(artifact)
        result['artifact'] = {'path': str(artifact), 'field': source_key}
        if implementation and not resolution_errors:
            # The logic lives in the implementation, so that is what an artifact must match.
            # A proxy whose own runtime matches proves nothing about the code that runs.
            impl_comparison = compare_bytecode(impl_code, artifact_code)
            result['compared'] = 'implementation'
            result['comparison'] = impl_comparison
            result['deployment_status'] = impl_comparison['status']
            result['comparison']['reason'] += (
                f' - compared against the implementation at {implementation}, not the proxy; '
                'the proxy may be pointed elsewhere by its admin at any later block')
            proxy_comparison = compare_bytecode(code, artifact_code)
            if proxy_comparison['status'] == 'exact':
                result['deployment_status'] = 'partial'
                result['comparison'] = {
                    'status': 'partial',
                    'reason': 'the artifact matches the PROXY runtime, not the implementation. '
                              'Build and pass the implementation artifact; a matching proxy '
                              'establishes nothing about the logic that executes.'}
        else:
            comparison = compare_bytecode(code, artifact_code)
            result['compared'] = 'address runtime'
            result['comparison'] = comparison
            result['deployment_status'] = comparison['status']
            if result['proxy']:
                result['deployment_status'] = 'partial'
                result['comparison'] = {
                    'status': 'partial',
                    'reason': ('proxy was detected but its executing implementation could not be '
                               'resolved and compared: ' + '; '.join(resolution_errors or
                               ['this proxy pattern is not supported yet']))}
        if result['proxy'] and result['deployment_status'] == 'exact':
            result['note'] = ('implementation bytecode matches at this block. A proxy can be '
                              'repointed, so record this block in the finding and recheck before '
                              'submitting.')
    else:
        result['reason'] = ('no local artifact given, so source-to-chain identity is unproven; '
                            'build the target and pass --artifact')
    return result


# --------------------------------------------------------------------------- #
# compiler known-bug check
# --------------------------------------------------------------------------- #

SOLC_BUGS_BY_VERSION = ('https://raw.githubusercontent.com/ethereum/solidity/develop/'
                        'docs/bugs_by_version.json')
SOLC_BUGS = 'https://raw.githubusercontent.com/ethereum/solidity/develop/docs/bugs.json'
SEVERITY_ORDER = {'very low': 0, 'low': 1, 'low/medium': 2, 'medium': 3,
                  'medium/high': 4, 'high': 5}
# Ecosystem advisories that are not in solc's own list. Keep this short and verifiable.
OTHER_TOOLCHAIN_ADVISORIES = (
    {'toolchain': 'vyper', 'versions': '0.2.15, 0.2.16, 0.3.0',
     'issue': 'the reentrancy guard did not work as intended',
     'precedent': 'exploited across several Curve pools in July 2023'},
)
PRAGMA = re.compile(r'pragma\s+solidity\s+([^;]+);')
EXACT_VERSION = re.compile(r'^\s*(\d+\.\d+\.\d+)\s*$')
VERSION_VALUE = re.compile(r'["\']?[~^>=<\s]*v?(\d+\.\d+\.\d+)')
# A key named `version` names a COMPILER version only inside a compiler block. Matching it
# anywhere pulls in an npm package's own version or a plugin's, and then solc-bugs reports
# bugs for a compiler nobody used.
TOML_SOLC_KEY = re.compile(r'^\s*(solc_version|solc)\s*=\s*(.+?)\s*(?:#.*)?$', re.M)
JS_COMPILER_BLOCK = re.compile(r'\b(solidity|solc)\b')
JS_VERSION_KEY = re.compile(r'\bversion\s*:\s*(["\'][^"\']+["\'])')
COMPILER_BLOCK_WINDOW = 800


def fetch_json(url, opener=None, timeout=30):
    request = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'User-Agent': f'bounty-pilot/{skill_version()}'})
    open_fn = opener or (lambda req, timeout: urllib.request.urlopen(req, timeout=timeout))
    with open_fn(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _js_compiler_regions(text):
    """Yield only the text of each `solidity`/`solc` block, matched by brace depth.

    A fixed-size window after the key swallows whatever object comes next, which is how an
    unrelated plugin's `version:` was being read as a compiler version.
    """
    for key in JS_COMPILER_BLOCK.finditer(text):
        rest = text[key.end():]
        head = re.match(r'\s*:\s*', rest)
        if not head:
            continue
        rest = rest[head.end():]
        inline = re.match(r'["\']([^"\']+)["\']', rest)
        if inline:                       # solidity: "0.8.19"
            yield inline.group(0)
            continue
        if not rest[:1] in ('{', '['):
            continue
        depth, end = 0, None
        for i, char in enumerate(rest[:20000]):
            if char in '{[':
                depth += 1
            elif char in '}]':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        yield rest[:end] if end else rest[:COMPILER_BLOCK_WINDOW]


def _versions_from_config(name, text):
    """Read a compiler version only from the key that actually names one, per file format."""
    found = []

    def value(raw):
        match = VERSION_VALUE.match(raw.strip())
        return match.group(1) if match else None

    if name.endswith('.toml'):
        for match in TOML_SOLC_KEY.finditer(text):
            version = value(match.group(2))
            if version:
                found.append(version)
    elif name == 'package.json':
        try:
            data = json.loads(text)
        except ValueError:
            return found
        for section in ('dependencies', 'devDependencies'):
            entry = (data.get(section) or {}).get('solc')
            if isinstance(entry, str):
                version = value(entry)
                if version:
                    found.append(version)
    else:  # hardhat / truffle: a `version:` key only inside a solidity or solc block
        for region in _js_compiler_regions(text):
            inline = value(region)
            if inline and region.lstrip()[:1] in ('"', "'"):
                found.append(inline)
                continue
            for match in JS_VERSION_KEY.finditer(region):
                version = value(match.group(1))
                if version:
                    found.append(version)
    return found


def collect_compiler_versions(root):
    """Find which compiler actually built this code, and what the source merely asks for."""
    exact, ranges, sources = {}, {}, {}
    tracked = [p for p in git(root, 'ls-files', '-z').split('\0') if p]

    def note(version, where):
        exact.setdefault(version, []).append(where)

    for name in ('foundry.toml', 'hardhat.config.js', 'hardhat.config.ts', 'hardhat.config.cjs',
                 'truffle-config.js', 'package.json'):
        path = root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for version in _versions_from_config(name, text):
            note(version, name)
    # Build artifacts carry the authoritative compiler version.
    artifacts = 0
    for candidate in sorted(root.glob('out/**/*.json'))[:400]:
        try:
            data = json.loads(candidate.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        version = (data.get('metadata') or {}).get('compiler', {}).get('version')
        if isinstance(version, str):
            artifacts += 1
            note(version.split('+')[0], 'build artifact')
    for path in tracked:
        if Path(path).suffix not in ('.sol', '.vy'):
            continue
        try:
            text = (root / path).read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        sources[path] = Path(path).suffix
        for match in PRAGMA.finditer(text):
            spec = match.group(1).strip()
            fixed = EXACT_VERSION.match(spec)
            if fixed:
                note(fixed.group(1), path)
            else:
                ranges.setdefault(spec, []).append(path)
    return {'exact': {v: sorted(set(w))[:6] for v, w in exact.items()},
            'ranges': {k: sorted(set(v))[:6] for k, v in ranges.items()},
            'artifacts_read': artifacts,
            'vyper_sources': sorted(p for p, suffix in sources.items() if suffix == '.vy')}


def solc_bugs(repo=None, versions=None, opener=None):
    """Check compiler versions against Solidity's own published bug list.

    A compiler bug is a real finding class, not trivia: a malfunctioning reentrancy guard in
    specific Vyper versions was exploited across Curve pools in 2023, and a contract compiled
    with a pre-0.8 Solidity lacking overflow checks was drained in 2026.
    """
    found = {'exact': {}, 'ranges': {}, 'artifacts_read': 0, 'vyper_sources': []}
    if repo:
        root = Path(git(Path(repo).resolve(), 'rev-parse', '--show-toplevel').strip()).resolve()
        found = collect_compiler_versions(root)
    for version in versions or []:
        found['exact'].setdefault(version, []).append('--version argument')
    if not found['exact'] and not found['ranges']:
        return {'checked': [], 'notes': ['no compiler version found; pass --version explicitly'],
                'source': SOLC_BUGS_BY_VERSION}
    notes = []
    try:
        by_version = fetch_json(SOLC_BUGS_BY_VERSION, opener)
        catalogue = {b['name']: b for b in fetch_json(SOLC_BUGS, opener) if 'name' in b}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {'checked': sorted(found['exact']), 'pragma_ranges': found['ranges'],
                'notes': [f'could not fetch the official bug list ({exc}); read it at '
                          f'{SOLC_BUGS_BY_VERSION} and compare by hand'],
                'other_toolchain_advisories': list(OTHER_TOOLCHAIN_ADVISORIES)}
    checked = []
    for version in sorted(found['exact']):
        entry = by_version.get(version)
        if entry is None:
            notes.append(f'{version} is not in the published list (unreleased, nightly, '
                         'or older than the list goes)')
            continue
        bugs = []
        for name in entry.get('bugs', []):
            meta = catalogue.get(name, {})
            bugs.append({'name': name, 'uid': meta.get('uid'),
                         'severity': meta.get('severity', 'unknown'),
                         'summary': (meta.get('summary') or '').strip()[:240],
                         'fixed_in': meta.get('fixed'), 'link': meta.get('link')})
        bugs.sort(key=lambda b: -SEVERITY_ORDER.get(b['severity'], 0))
        notable = [b for b in bugs if SEVERITY_ORDER.get(b['severity'], 0) >= 3]
        checked.append({'version': version, 'seen_in': found['exact'][version],
                        'released': entry.get('released'), 'bug_count': len(bugs),
                        'medium_or_higher': notable, 'all_bugs': [b['name'] for b in bugs]})
    if found['ranges']:
        notes.append('pragma ranges do not determine the compiled version; the build config or a '
                     'build artifact does. Resolve each range before relying on it.')
    if found['vyper_sources']:
        notes.append(f"{len(found['vyper_sources'])} Vyper source(s) present: solc's list does not "
                     'cover Vyper, see other_toolchain_advisories and Vyper\'s own releases')
    return {'checked': checked, 'pragma_ranges': found['ranges'],
            'artifacts_read': found['artifacts_read'],
            'other_toolchain_advisories': list(OTHER_TOOLCHAIN_ADVISORIES),
            'notes': notes, 'source': SOLC_BUGS_BY_VERSION,
            'notice': 'A listed bug is a lead, not a finding: establish that the affected feature '
                      'is used on a reachable path, and that this version built the DEPLOYED code.'}


# --------------------------------------------------------------------------- #
# value at risk
# --------------------------------------------------------------------------- #

def value_at_risk(rpc, addresses, tokens=None, block='latest', opener=None):
    """Read native and ERC-20 balances so severity can be aimed at the money."""
    keccak = load_keccak()
    for address in list(addresses) + list(tokens or []):
        if not re.fullmatch(r'0x[0-9a-fA-F]{40}', address):
            raise ValueError(f'{address!r} is not an address')
    tip = rpc_call(rpc, 'eth_blockNumber', [], opener)
    pinned = tip if block == 'latest' else (hex(int(block)) if str(block).isdigit() else block)
    chain_id = int(rpc_call(rpc, 'eth_chainId', [], opener), 16)
    balance_of = keccak.selector('balanceOf(address)')
    decimals_sig = keccak.selector('decimals()')
    token_meta = {}
    for token in tokens or []:
        raw = rpc_call(rpc, 'eth_call', [{'to': token, 'data': decimals_sig}, pinned], opener)
        try:
            token_meta[token] = int(raw, 16) if raw and raw != '0x' else None
        except ValueError:
            token_meta[token] = None
    rows = []
    for address in addresses:
        native = rpc_call(rpc, 'eth_getBalance', [address, pinned], opener) or '0x0'
        holdings = []
        for token in tokens or []:
            data = balance_of + encode_static(['address'], [address]).hex()
            raw = rpc_call(rpc, 'eth_call', [{'to': token, 'data': data}, pinned], opener)
            amount = int(raw, 16) if raw and raw != '0x' else 0
            decimals = token_meta.get(token)
            holdings.append({'token': token, 'raw': str(amount), 'decimals': decimals,
                             'scaled': (amount / (10 ** decimals)) if decimals else None})
        rows.append({'address': address, 'native_wei': str(int(native, 16)),
                     'native': int(native, 16) / 1e18, 'tokens': holdings})
    ranked = {}
    for token in tokens or []:
        ranked[token] = sorted(
            ({'address': r['address'],
              'raw': next(h['raw'] for h in r['tokens'] if h['token'] == token)}
             for r in rows), key=lambda x: -int(x['raw']))
    return {'chain_id': chain_id,
            'block': int(pinned, 16) if str(pinned).startswith('0x') else pinned,
            'holdings': rows, 'ranked_per_token': ranked,
            'notice': 'Balances only - no prices are fetched, so totals are not comparable across '
                      'tokens. Use this to find which contract is the honeypot, and to bound a '
                      'claimed extraction by what is actually there.'}

# --------------------------------------------------------------------------- #
# static-type eth_call probe
# --------------------------------------------------------------------------- #

TRUE_WORDS = ('1', 'true', 'yes')
FALSE_WORDS = ('0', 'false', 'no')


def _int_bits(type_name, prefix):
    digits = type_name[len(prefix):]
    bits = 256 if not digits else int(digits)
    if bits % 8 or not 8 <= bits <= 256:
        raise ValueError(f'{type_name} is not a valid ABI type; width must be 8..256 in steps of 8')
    return bits


def encode_static(types, args):
    """ABI-encode static arguments, refusing anything it cannot encode faithfully.

    Silent coercion is worse than an error here: a wrong argument produces a successful call
    against the wrong input, and the reader believes the live value they get back.
    """
    if len(types) != len(args):
        raise ValueError(f'signature takes {len(types)} argument(s), {len(args)} given')
    out = b''
    for type_name, raw in zip(types, args):
        text = str(raw).strip()
        if type_name == 'address':
            if not re.fullmatch(r'0x[0-9a-fA-F]{40}', text):
                raise ValueError(f'{raw!r} is not an address: expected 0x and 40 hex characters')
            out += int(text, 16).to_bytes(32, 'big')
        elif type_name == 'bool':
            lowered = text.lower()
            if lowered in TRUE_WORDS:
                out += (1).to_bytes(32, 'big')
            elif lowered in FALSE_WORDS:
                out += (0).to_bytes(32, 'big')
            else:
                raise ValueError(f'{raw!r} is not a bool: use true/false, 1/0 or yes/no')
        elif re.fullmatch(r'uint\d*', type_name):
            bits = _int_bits(type_name, 'uint')
            value = int(text, 0)
            if not 0 <= value < (1 << bits):
                raise ValueError(f'{raw!r} does not fit in {type_name}')
            out += value.to_bytes(32, 'big')
        elif re.fullmatch(r'int\d*', type_name):
            bits = _int_bits(type_name, 'int')
            value = int(text, 0)
            if not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
                raise ValueError(f'{raw!r} does not fit in {type_name}')
            out += (value & ((1 << 256) - 1)).to_bytes(32, 'big')
        elif re.fullmatch(r'bytes\d+', type_name):
            size = int(type_name[5:])
            if not 1 <= size <= 32:
                raise ValueError(f'{type_name} is not a valid ABI type')
            body = text[2:] if text.startswith('0x') else text
            try:
                data = bytes.fromhex(body)
            except ValueError:
                raise ValueError(f'{raw!r} is not hex for {type_name}')
            if len(data) != size:
                raise ValueError(f'{raw!r} is {len(data)} byte(s); {type_name} needs exactly {size}')
            out += data + b'\0' * (32 - len(data))
        else:
            raise ValueError(f'{type_name} is not a static type; use cast/foundry for '
                             'strings, bytes, tuples and arrays')
    return out


def eth_call(rpc, to, signature, args, block='latest', opener=None):
    keccak = load_keccak()
    canonical = ''.join(signature.split())
    match = re.fullmatch(r'([A-Za-z_]\w*)\((.*)\)', canonical)
    if not match:
        raise ValueError('signature must look like name(type,type)')
    types = [t for t in match.group(2).split(',') if t]
    data = keccak.selector(canonical) + encode_static(types, args).hex()
    result = rpc_call(rpc, 'eth_call', [{'to': to, 'data': data}, block], opener)
    raw = (result or '0x')[2:]
    words = [raw[i:i + 64] for i in range(0, len(raw), 64)]
    decoded = []
    for word in words:
        if len(word) < 64:
            continue
        value = int(word, 16)
        # Only offer an address reading when the word cannot plausibly be a plain number:
        # right-aligned in 20 bytes and too large for a uint64. Showing decimals()==6 as
        # 0x...06 would be worse than showing nothing.
        as_address = ('0x' + word[24:]) if (value >> 160 == 0 and value >> 64 != 0) else None
        decoded.append({'hex': '0x' + word, 'uint': str(value), 'address': as_address})
    return {'to': to, 'selector': data[:10], 'signature': canonical, 'block': block,
            'raw': result, 'words': decoded,
            'notice': 'Static-type decoding only. Compare this live value against the constant '
                      'in the source; a mismatch is a finding candidate, not yet a finding.'}


# --------------------------------------------------------------------------- #
# backtest: measure the hunt against already-published findings
# --------------------------------------------------------------------------- #
#
# The only thing that makes a rediscovery number mean anything is that the hunt could not see
# the answers. So the ground truth is loaded only AFTER the hunt's output is sealed, the seal
# is hashed, and nothing can be sealed twice. A case whose truth file already had content when
# the seal was taken is refused outright rather than scored with a caveat.

TRUTH_SEVERITIES = {'critical', 'high', 'medium', 'low', 'informational'}
MATCH_THRESHOLD = 2.0
STOPWORDS = {'the', 'a', 'an', 'of', 'in', 'to', 'is', 'and', 'or', 'for', 'on', 'can', 'be',
             'not', 'with', 'by', 'from', 'this', 'that', 'it', 'as', 'at', 'are', 'when',
             'if', 'due', 'has', 'have', 'will', 'may', 'contract', 'function', 'user', 'users',
             'attacker', 'protocol', 'token', 'tokens', 'value', 'amount'}


def _sha256_file(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tokens(*texts):
    words = set()
    for text in texts:
        for word in re.split(r'[^a-zA-Z0-9]+', (text or '').lower()):
            if len(word) > 3 and word not in STOPWORDS:
                words.add(word)
    return words


def _path_keys(paths):
    keys = set()
    for raw in paths or []:
        if not isinstance(raw, str):
            continue
        lowered = raw.lower().strip()
        head = lowered.split(':')[0]
        keys.add(Path(head).name)
        if ':' in lowered:
            symbol = lowered.split(':', 1)[1]
            keys.add(symbol)
            keys.add(symbol.split('.')[-1])
    return {k for k in keys if k}


def _match_score(finding, truth):
    """Propose, never decide. Mechanical overlap only - a human or an agent judges the pair."""
    fpaths, tpaths = _path_keys(finding.get('affected_paths')), _path_keys(truth.get('paths'))
    score, why = 0.0, []
    shared_paths = fpaths & tpaths
    if shared_paths:
        score += 2.0
        why.append('same file/symbol: ' + ', '.join(sorted(shared_paths)[:3]))
    ftok = _tokens(finding.get('title'), finding.get('root_cause'), finding.get('bug_class'))
    ttok = _tokens(truth.get('title'), truth.get('root_cause'))
    shared_words = ftok & ttok
    if shared_words:
        score += min(2.0, 0.5 * len(shared_words))
        why.append('shared terms: ' + ', '.join(sorted(shared_words)[:5]))
    return score, why


def backtest_init(name, repo, out, commit=None, scope=None):
    repo = Path(repo).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    head = git(root, 'rev-parse', 'HEAD').strip()
    pinned = head
    warnings = []
    if commit:
        pinned = git(root, 'rev-parse', '--verify', '--quiet', commit + '^{commit}').strip()
        if pinned != head:
            warnings.append(f'the checkout is at {head[:12]}, not the pinned {pinned[:12]}; '
                            'check out the pinned commit before hunting or the measurement is '
                            'against different code')
    case = Path(out).resolve()
    if case.exists():
        raise ValueError('use a new case directory; an existing one is never overwritten')
    case.mkdir(parents=True)
    case.chmod(0o700)
    dump(case / 'case.json', {
        'schema_version': SCHEMA_VERSION, 'skill_version': skill_version(), 'name': name,
        'created_at': datetime.now(timezone.utc).isoformat(), 'target_root': str(root),
        'pinned_commit': pinned, 'checkout_head': head, 'scope_prefixes': scope or [],
        'protocol': 'blind: hunt and seal first, load truth.json only afterwards'})
    dump(case / 'truth.json', [])
    dump(case / 'truth-template.json', [{
        'id': 'TRUTH-001', 'source': 'https://... the published report entry',
        'severity': 'high', 'title': '', 'root_cause': '',
        'paths': ['src/Vault.sol:Vault.redeem'], 'notes': 'judge comments, duplicates count, etc.'}])
    (case / '.gitignore').write_text('*\n', encoding='utf-8')
    (case / 'README.md').write_text(
        f'# Backtest case: {name}\n\n'
        f'Pinned commit: `{pinned}`\n\n'
        '1. Hunt this commit with the normal workflow. Do not open the published findings.\n'
        '2. `bounty.py backtest seal --case . --run <run-dir>`\n'
        '3. Only now transcribe the published findings into `truth.json`.\n'
        '4. `bounty.py backtest score --case .`, decide the proposed pairs, score again.\n',
        encoding='utf-8')
    return {'case': str(case), 'name': name, 'pinned_commit': pinned, 'warnings': warnings,
            'next': 'hunt the pinned commit without reading the published findings, then seal'}


def backtest_seal(case, run):
    case, run = Path(case).resolve(), Path(run).resolve()
    meta = read_json(case / 'case.json')
    if (case / 'seal.json').exists():
        raise ValueError('this case is already sealed; a second seal would let a hunt be revised '
                         'after seeing the answers. Start a new case instead.')
    truth = read_json(case / 'truth.json')
    if truth:
        raise ValueError('truth.json already has entries, so this hunt was not blind. '
                         'This case cannot produce a measurement; start a new one.')
    findings = read_json(run / 'findings.json')
    if not isinstance(findings, list):
        raise ValueError('findings.json must be an array')
    dump(case / 'sealed-findings.json', findings)
    for name in ('coverage.md', 'known-hypotheses.md', 'scope.md'):
        source = run / name
        if source.is_file():
            (case / f'sealed-{name}').write_text(source.read_text(encoding='utf-8'),
                                                 encoding='utf-8')
    run_meta = read_json(run / 'run.json') if (run / 'run.json').is_file() else {}
    seal = {'sealed_at': datetime.now(timezone.utc).isoformat(),
            'sealed_findings_sha256': _sha256_file(case / 'sealed-findings.json'),
            'finding_count': len(findings), 'run': str(run),
            'run_commit': run_meta.get('commit'), 'pinned_commit': meta.get('pinned_commit')}
    if run_meta.get('commit') and run_meta['commit'] != meta.get('pinned_commit'):
        seal['warning'] = (f"the run was initialised at {run_meta['commit'][:12]}, not the case's "
                           f"pinned {str(meta.get('pinned_commit'))[:12]}")
    dump(case / 'seal.json', seal)
    return {'sealed': str(case / 'sealed-findings.json'), **seal,
            'next': 'now transcribe the published findings into truth.json, then score'}


def backtest_score(case):
    case = Path(case).resolve()
    meta = read_json(case / 'case.json')
    seal_path = case / 'seal.json'
    if not seal_path.is_file():
        raise ValueError('nothing sealed: hunt and seal before loading the ground truth')
    seal = read_json(seal_path)
    actual = _sha256_file(case / 'sealed-findings.json')
    if actual != seal['sealed_findings_sha256']:
        raise ValueError('sealed-findings.json changed after it was sealed; this case is void')
    truth = read_json(case / 'truth.json')
    if not truth:
        return {'state': 'awaiting-truth', 'case': meta.get('name'),
                'sealed_findings': seal['finding_count'],
                'next': 'transcribe the published findings into truth.json using '
                        'truth-template.json, then score again'}
    findings = read_json(case / 'sealed-findings.json')
    for i, row in enumerate(truth):
        if not isinstance(row, dict) or not has_text(row.get('id')):
            raise ValueError(f'truth[{i}]: id is required')
        if row.get('severity') not in TRUTH_SEVERITIES:
            raise ValueError(f"truth[{i}]: severity must be one of "
                             + ', '.join(sorted(TRUTH_SEVERITIES)))

    decisions_path = case / 'matches.json'
    existing = {}
    if decisions_path.is_file():
        for row in read_json(decisions_path):
            existing[(row.get('truth_id'), row.get('finding_id'))] = row

    proposals, undecided = [], 0
    for item in truth:
        for finding in findings:
            score, why = _match_score(finding, item)
            if score < MATCH_THRESHOLD:
                continue
            key = (item['id'], finding.get('id'))
            row = existing.get(key, {})
            decision = row.get('decision', 'undecided')
            if decision == 'undecided':
                undecided += 1
            proposals.append({
                'truth_id': item['id'], 'truth_title': item.get('title', '')[:90],
                'truth_severity': item['severity'], 'finding_id': finding.get('id'),
                'finding_title': (finding.get('title') or '')[:90],
                'finding_lens': finding.get('lens'), 'finding_status': finding.get('status'),
                'overlap_score': round(score, 2), 'overlap_reasons': why,
                'decision': decision, 'decision_reason': row.get('decision_reason', '')})
    # keep any decided pair the heuristic no longer proposes, so a judgment is never lost
    seen = {(p['truth_id'], p['finding_id']) for p in proposals}
    for key, row in existing.items():
        if key not in seen and row.get('decision') not in (None, 'undecided'):
            proposals.append(row)
    proposals.sort(key=lambda r: (-r['overlap_score'], str(r['truth_id'])))
    dump(decisions_path, proposals)

    if undecided:
        return {'state': 'awaiting-decisions', 'case': meta.get('name'),
                'proposed_pairs': len(proposals), 'undecided': undecided,
                'matches_file': str(decisions_path),
                'how': "set each pair's decision to 'same-mechanism', 'related-not-same' or "
                       "'different', with a one-line decision_reason, then score again. Match on "
                       'root cause and affected path, never on title similarity.',
                'notice': 'The heuristic proposes pairs; it does not judge them. A truth entry '
                          'with no proposal may still have been found - check the misses by hand.'}

    matched = {}
    for row in proposals:
        if row.get('decision') == 'same-mechanism':
            matched.setdefault(row['truth_id'], []).append(row)
    rediscovered, missed = [], []
    for item in truth:
        hits = matched.get(item['id'], [])
        record = {'id': item['id'], 'severity': item['severity'],
                  'title': (item.get('title') or '')[:90]}
        if hits:
            record['found_by'] = [{'finding_id': h['finding_id'], 'lens': h.get('finding_lens'),
                                   'status': h.get('finding_status')} for h in hits]
            rediscovered.append(record)
        else:
            record['source'] = item.get('source')
            missed.append(record)

    matched_finding_ids = {h['finding_id'] for hits in matched.values() for h in hits}
    unmatched = [{'id': f.get('id'), 'title': (f.get('title') or '')[:90],
                  'lens': f.get('lens'), 'status': f.get('status'),
                  'severity': f.get('severity')}
                 for f in findings if f.get('id') not in matched_finding_ids]

    def tally(entries, key='severity'):
        out = {}
        for e in entries:
            out[e.get(key) or 'unspecified'] = out.get(e.get(key) or 'unspecified', 0) + 1
        return out

    per_lens = {}
    for record in rediscovered:
        for hit in record['found_by']:
            lens = hit.get('lens') or 'unattributed'
            per_lens[lens] = per_lens.get(lens, 0) + 1

    serious = [t for t in truth if t['severity'] in ('critical', 'high', 'medium')]
    serious_found = [r for r in rediscovered if r['severity'] in ('critical', 'high', 'medium')]
    return {
        'state': 'scored', 'case': meta.get('name'), 'pinned_commit': meta.get('pinned_commit'),
        'sealed_at': seal['sealed_at'],
        'published_findings': len(truth), 'hunt_findings': len(findings),
        'rediscovered': rediscovered, 'rediscovered_by_severity': tally(rediscovered),
        'missed': missed, 'missed_by_severity': tally(missed),
        'serious_rediscovered': f'{len(serious_found)} of {len(serious)}',
        'credited_lenses': per_lens,
        'unmatched_hunt_findings': unmatched,
        'notice': 'Counts, not rates: one case is an anecdote. An unmatched hunt finding is NOT '
                  'a false positive - contests miss things, judges deduplicate, and scope '
                  'differs. Judge each unmatched entry separately before calling it wrong. A '
                  'rediscovery count does not predict a live-bounty payout: contests have no '
                  'private duplicates, no deployment question and a fixed scope.'}

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='version', version=skill_version())
    sub = parser.add_subparsers(dest='action', required=True)

    init = sub.add_parser('init', help='create private run metadata; audits nothing')
    init.add_argument('--repo', required=True)
    init.add_argument('--out', required=True)

    check = sub.add_parser('check', help='record structure and artifact presence')
    check.add_argument('--run', required=True)
    check.add_argument('--submission', action='store_true',
                       help='also apply the submission-readiness gates')

    dup = sub.add_parser('dup-check', help='match findings against the built duplicate map')
    dup.add_argument('--run', required=True)

    queue = sub.add_parser('queue', help='show every open lead and its required next experiment')
    queue.add_argument('--run', required=True)

    hist = sub.add_parser('history', help='record and compare private bounty-report outcomes')
    hist_sub = hist.add_subparsers(dest='history_action', required=True)
    hist_check = hist_sub.add_parser('check', help='compare this run with your private report history')
    hist_check.add_argument('--run', required=True)
    hist_check.add_argument('--ledger', default=None, help='private JSONL path; default ~/.bounty-pilot/history.jsonl')
    hist_check.add_argument('--project', default=None, help='override project key when the repo has no origin remote')
    hist_record = hist_sub.add_parser('record', help='record a submitted report or a program decision')
    hist_record.add_argument('--run', required=True)
    hist_record.add_argument('--finding', required=True)
    hist_record.add_argument('--outcome', required=True, choices=sorted(HISTORY_DISPOSITIONS))
    hist_record.add_argument('--ledger', default=None)
    hist_record.add_argument('--project', default=None)
    hist_record.add_argument('--program', default='')
    hist_record.add_argument('--case-id', default=None, help='reuse the id printed by the first record')
    hist_record.add_argument('--reason', default='unspecified', choices=sorted(HISTORY_REASONS))
    hist_record.add_argument('--hours', type=float, default=None, help='total hours spent on this report')
    hist_import = hist_sub.add_parser('import', help='seed the private history from an older report')
    hist_import.add_argument('--project', required=True, help='repository URL or host/owner/repo key')
    hist_import.add_argument('--finding-id', required=True, help='your report identifier or local label')
    hist_import.add_argument('--bug-class', required=True)
    hist_import.add_argument('--surface', action='append', required=True,
                             help='affected path or path:function; repeatable')
    hist_import.add_argument('--root-cause', required=True, help='short mechanism summary, max 500 chars')
    hist_import.add_argument('--outcome', required=True, choices=sorted(HISTORY_DISPOSITIONS))
    hist_import.add_argument('--ledger', default=None)
    hist_import.add_argument('--program', default='')
    hist_import.add_argument('--case-id', default=None)
    hist_import.add_argument('--reason', default='unspecified', choices=sorted(HISTORY_REASONS))
    hist_import.add_argument('--hours', type=float, default=None)
    hist_import.add_argument('--lens', default='unattributed')
    hist_summary = hist_sub.add_parser('summary', help='summarise your own recorded report outcomes')
    hist_summary.add_argument('--ledger', default=None)

    dlt = sub.add_parser('delta', help='rank non-test source changed since an audited revision')
    dlt.add_argument('--repo', required=True)
    dlt.add_argument('--since', required=True, help='exact commit the last audit covered')
    dlt.add_argument('--scope', action='append', default=None,
                     help='path prefix to keep; repeatable')
    dlt.add_argument('--limit', type=int, default=40)

    bnd = sub.add_parser('bundle', help='assemble one deterministic source bundle per hunt lens')
    bnd.add_argument('--repo', required=True)
    bnd.add_argument('--run', required=True)
    bnd.add_argument('--lens', action='append', required=True,
                     help='lens name, or a group: aim, attack, config, logic, cross-stack, recommended, all. Repeatable.')
    bnd.add_argument('--scope', action='append', default=None, help='path prefix to keep')
    bnd.add_argument('--include', action='append', default=None,
                     help='extra context file to append, e.g. a delta ranking. Repeatable.')

    route_parser = sub.add_parser('route', help='recommend native adapters from tracked manifests (heuristic)')
    route_parser.add_argument('--repo', required=True)

    score = sub.add_parser('score-target', help='prioritise a target from code and program facts')
    score.add_argument('--repo', required=True)
    score.add_argument('--program', required=True, help='JSON of published program facts')

    dep = sub.add_parser('verify-deployment', help='compare on-chain runtime code with a build')
    dep.add_argument('--rpc', required=True, help='read-only JSON-RPC endpoint')
    dep.add_argument('--address', required=True)
    dep.add_argument('--artifact', default=None, help='Foundry/Hardhat artifact JSON')
    dep.add_argument('--block', default='latest')

    bugs = sub.add_parser('solc-bugs',
                          help="check compiler versions against Solidity's published bug list")
    bugs.add_argument('--repo', default=None)
    bugs.add_argument('--version', action='append', default=None,
                      help='exact compiler version to check; repeatable')

    val = sub.add_parser('value', help='read native and ERC-20 balances of in-scope contracts')
    val.add_argument('--rpc', required=True)
    val.add_argument('--address', action='append', required=True)
    val.add_argument('--token', action='append', default=None)
    val.add_argument('--block', default='latest')

    bt = sub.add_parser('backtest',
                        help='measure a hunt against already-published findings, blind')
    bt_sub = bt.add_subparsers(dest='backtest_action', required=True)
    bt_init = bt_sub.add_parser('init', help='open a case at a pinned commit')
    bt_init.add_argument('--name', required=True)
    bt_init.add_argument('--repo', required=True)
    bt_init.add_argument('--out', required=True)
    bt_init.add_argument('--commit', default=None, help='the revision the contest covered')
    bt_init.add_argument('--scope', action='append', default=None)
    bt_seal = bt_sub.add_parser('seal', help='freeze the hunt output before truth is loaded')
    bt_seal.add_argument('--case', required=True)
    bt_seal.add_argument('--run', required=True)
    bt_score = bt_sub.add_parser('score', help='propose pairs, then score decided ones')
    bt_score.add_argument('--case', required=True)

    sig = sub.add_parser('sig', help='keccak256 function selector of a canonical signature')
    sig.add_argument('signature')

    call = sub.add_parser('eth-call', help='read a live value through a static-type eth_call')
    call.add_argument('--rpc', required=True)
    call.add_argument('--to', required=True)
    call.add_argument('--sig', required=True)
    call.add_argument('--arg', action='append', default=[])
    call.add_argument('--block', default='latest')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.action == 'init':
            print(json.dumps(initialize(args.repo, args.out), indent=2))
            return 0
        if args.action == 'check':
            errors = validate(args.run, submission=args.submission)
            notice = ('Structural and submission gates only. They do not verify exploit '
                      'validity, severity, originality or eligibility.' if args.submission else
                      'This does not verify exploit validity, severity, originality or eligibility.')
            print(json.dumps({'gate': 'submission' if args.submission else 'structural',
                              'result': 'failed' if errors else 'passed',
                              'errors': errors, 'notice': notice}, indent=2))
            return 1 if errors else 0
        if args.action == 'dup-check':
            errors, collisions = check_dup_map(args.run)
            print(json.dumps({'map_errors': errors, 'collisions': collisions,
                              'result': 'failed' if errors else
                                        ('collisions' if collisions else 'clean'),
                              'notice': 'A collision means the surface and class were already '
                                        'public. Compare mechanisms before dropping or filing.'},
                             indent=2))
            return 1 if errors or collisions else 0
        if args.action == 'queue':
            result = lead_queue(args.run)
            print(json.dumps(result, indent=2))
            return 1 if result['state'] == 'invalid' else 0
        if args.action == 'history':
            if args.history_action == 'check':
                result = history_check(args.run, args.ledger, args.project)
            elif args.history_action == 'record':
                result = history_record(args.run, args.finding, args.outcome, args.ledger,
                                        args.project, args.program, args.case_id, args.reason,
                                        args.hours)
            elif args.history_action == 'import':
                result = history_import(args.project, args.finding_id, args.bug_class,
                                        args.surface, args.root_cause, args.outcome, args.ledger,
                                        args.program, args.case_id, args.reason, args.hours, args.lens)
            else:
                result = history_summary(args.ledger)
            print(json.dumps(result, indent=2))
            return 0
        if args.action == 'delta':
            print(json.dumps(delta(args.repo, args.since, args.scope, args.limit), indent=2))
            return 0
        if args.action == 'bundle':
            print(json.dumps(bundle(args.repo, args.run, args.lens, args.scope,
                                    args.include), indent=2))
            return 0
        if args.action == 'route':
            print(json.dumps(load_stack_route().route(args.repo), indent=2))
            return 0
        if args.action == 'score-target':
            print(json.dumps(score_target(args.repo, args.program), indent=2))
            return 0
        if args.action == 'verify-deployment':
            print(json.dumps(verify_deployment(args.rpc, args.address, args.artifact,
                                               args.block), indent=2))
            return 0
        if args.action == 'backtest':
            if args.backtest_action == 'init':
                print(json.dumps(backtest_init(args.name, args.repo, args.out, args.commit,
                                               args.scope), indent=2))
            elif args.backtest_action == 'seal':
                print(json.dumps(backtest_seal(args.case, args.run), indent=2))
            else:
                print(json.dumps(backtest_score(args.case), indent=2))
            return 0
        if args.action == 'solc-bugs':
            print(json.dumps(solc_bugs(args.repo, args.version), indent=2))
            return 0
        if args.action == 'value':
            print(json.dumps(value_at_risk(args.rpc, args.address, args.token,
                                           args.block), indent=2))
            return 0
        if args.action == 'sig':
            print(load_keccak().selector(args.signature))
            return 0
        if args.action == 'eth-call':
            print(json.dumps(eth_call(args.rpc, args.to, args.sig, args.arg, args.block), indent=2))
            return 0
        return 2
    except (OSError, ValueError, KeyError, subprocess.SubprocessError,
            urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
