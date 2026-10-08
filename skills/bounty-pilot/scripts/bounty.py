#!/usr/bin/env python3
"""Bounty Pilot helper: run scaffolding, delta ranking, on-chain identity checks
and structural/submission gates. Standard library only.

Nothing here audits code or proves a finding. Every subcommand reports what it
observed and labels what it could not establish.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 2
SKILL_ROOT = Path(__file__).resolve().parents[1]

SOURCE_SUFFIXES = {'.sol', '.vy', '.yul', '.huff', '.rs', '.move', '.cairo', '.fe',
                   '.go', '.ts', '.tsx', '.js', '.py', '.c', '.h', '.cpp'}
STATUSES = {'hypothesis', 'needs-evidence', 'verified', 'refuted'}
SEVERITIES = {'unassessed', 'informational', 'low', 'medium', 'high', 'critical'}
SCOPE_STATUSES = {'unknown', 'in-scope', 'out-of-scope'}
DEPLOY_STATUSES = {'unknown', 'exact', 'partial', 'mismatch', 'not-applicable'}
NOVELTY_STATUSES = {'not-checked', 'no-public-match-found', 'matched-public-issue'}
GATES = {'interruption', 'reachability', 'trigger', 'harm', 'eligibility', 'evidence'}
OBJECTION_OUTCOMES = {'answered', 'sustained', 'withdrawn'}
REQUIRED = ('id', 'title', 'status', 'severity', 'bug_class', 'revision', 'root_cause',
            'affected_paths', 'attacker_capabilities', 'preconditions', 'impact',
            'scope_status', 'deployment_status', 'novelty', 'evidence', 'objections',
            'rejection_reason')


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


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #

def template():
    return dict(id='BP-001', title='', status='hypothesis', severity='unassessed',
                bug_class='', revision='', root_cause='', affected_paths=[],
                attacker_capabilities='', preconditions='', impact='',
                scope_status='unknown', deployment_status='unknown',
                novelty={'status': 'not-checked', 'sources': []},
                evidence={}, objections=[], rejection_reason='')


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
        'target_root': str(root), 'commit': commit, 'dirty': dirty,
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
    return {'run': str(out), 'commit': commit, 'dirty': dirty,
            'source_candidates': len(source), 'schema_version': SCHEMA_VERSION}


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
    paths = row['affected_paths']
    if not isinstance(paths, list) or not paths or not all(has_text(p) for p in paths):
        errors.append(prefix + ': affected_paths must be a nonempty string array')
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


def _check_submission(row, prefix, run, errors):
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
        errors.append('run.json: missing; this directory was not created by init')
    records = read_json(run / 'findings.json')
    if not isinstance(records, list):
        return errors + ['findings.json must be an array']
    seen = set()
    for i, row in enumerate(records):
        prefix = f'finding[{i}]'
        if not isinstance(row, dict):
            errors.append(prefix + ': must be an object')
            continue
        complete = _check_record(row, prefix, run, seen, errors)
        if complete and submission:
            _check_submission(row, prefix, run, errors)
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

LENSES = ('delta', 'upstream-diff', 'coverage-gap', 'accounting', 'live-reality',
          'integration-auth', 'liveness', 'anchor-account', 'seam')
TRIAGE = 'triage'
AIM_LENSES = ('delta', 'upstream-diff', 'coverage-gap')
ATTACK_LENSES = ('accounting', 'integration-auth', 'liveness', 'live-reality')
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


def bundle(repo, run, lenses, scope_prefixes=None, includes=None):
    """Assemble one deterministic bundle per lens. This is the dispatch mechanic:
    a pass that did not run this command did not bundle its source."""
    repo, run = Path(repo).resolve(), Path(run).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    commit = git(root, 'rev-parse', 'HEAD').strip()
    references = SKILL_ROOT / 'references'
    chosen = []
    for lens in lenses:
        if lens == 'all':
            chosen.extend(LENSES)
        elif lens == 'aim':
            chosen.extend(AIM_LENSES)
        elif lens == 'attack':
            chosen.extend(ATTACK_LENSES)
        elif lens in LENSES or lens == TRIAGE:
            chosen.append(lens)
        else:
            raise ValueError(f'unknown lens {lens!r}; choose from ' + ', '.join(LENSES)
                             + f', {TRIAGE}, or the groups aim / attack / all')
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
    test_paths = [p for p in tracked if Path(p).suffix in SOURCE_SUFFIXES and _is_test_path(p)]

    out = run / 'bundles'
    out.mkdir(parents=True, exist_ok=True)
    source, skipped = _collect(root, in_scope)
    source_doc = f'# In-scope source ({len(in_scope)} files)\n\n' + source
    (out / 'source.md').write_text(source_doc, encoding='utf-8')
    tests, _ = _collect(root, test_paths)
    tests_doc = (f'# Tests, mocks and fixtures ({len(test_paths)} files)\n\n'
                 'Read these as evidence of what the authors believed, not as code to audit.\n\n'
                 + tests)
    (out / 'tests.md').write_text(tests_doc, encoding='utf-8')

    context = []
    for name in ('scope.md', 'dup-map.json', 'known-hypotheses.md'):
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
    sop_path = references / 'sop.md'
    sop = sop_path.read_text(encoding='utf-8') if sop_path.is_file() else ''
    findings_doc = ''
    findings_path = run / 'findings.json'
    if findings_path.is_file():
        body = findings_path.read_text(encoding='utf-8')
        findings_doc = ('## The records under review\n\nAttack these. Nothing here is '
                        'established.\n\n```json\n' + body.rstrip() + '\n```\n')
    impact_path = references / 'impact-classes.md'
    impact = impact_path.read_text(encoding='utf-8') if impact_path.is_file() else ''

    written = []
    for lens in chosen:
        if lens == TRIAGE:
            # Triage gets the records, the source and the impact ladder - but never the hunt
            # stance, which forbids self-refutation and is the opposite of this agent's job.
            pieces = [TRIAGE_HEADER.format(target=root.name, commit=commit)]
            if sop:
                pieces.append(sop)
            pieces.append((references / f'{TRIAGE}.md').read_text(encoding='utf-8'))
            if impact:
                pieces.append(impact)
            if findings_doc:
                pieces.append(findings_doc)
            if context_doc:
                pieces.append(context_doc)
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
        if lens == 'seam' and findings_doc:
            pieces.append(findings_doc.replace('Attack these. Nothing here is established.',
                                               'The earlier passes produced these. Cross them.'))
        if context_doc:
            pieces.append(context_doc)
        pieces.append(source_doc)
        if lens == 'coverage-gap':
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
    return {'target': str(root), 'commit': commit, 'run': str(run),
            'in_scope_files': len(in_scope), 'test_files_bundled_for_coverage_gap': len(test_paths),
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
    for label, slot in proxy_slots().items():
        word = rpc_call(rpc, 'eth_getStorageAt', [address, slot, pinned], opener) or '0x'
        packed = word[-40:] if len(word) >= 42 else ''
        if packed and int(packed, 16) != 0:
            result['proxy'][label] = '0x' + packed
    if result['proxy']:
        result['note'] = ('this address is a proxy; verify the implementation address too, '
                          'and record which implementation was live at this block')
    implementation = result['proxy'].get('eip1967-implementation')
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
        if implementation:
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
        if result['proxy'] and result['deployment_status'] == 'exact':
            result['note'] = ('implementation bytecode matches at this block. A proxy can be '
                              'repointed, so record this block in the finding and recheck before '
                              'submitting.')
    else:
        result['reason'] = ('no local artifact given, so source-to-chain identity is unproven; '
                            'build the target and pass --artifact')
    return result


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
                     help='lens name, or a group: aim, attack, all. Repeatable.')
    bnd.add_argument('--scope', action='append', default=None, help='path prefix to keep')
    bnd.add_argument('--include', action='append', default=None,
                     help='extra context file to append, e.g. a delta ranking. Repeatable.')

    score = sub.add_parser('score-target', help='prioritise a target from code and program facts')
    score.add_argument('--repo', required=True)
    score.add_argument('--program', required=True, help='JSON of published program facts')

    dep = sub.add_parser('verify-deployment', help='compare on-chain runtime code with a build')
    dep.add_argument('--rpc', required=True, help='read-only JSON-RPC endpoint')
    dep.add_argument('--address', required=True)
    dep.add_argument('--artifact', default=None, help='Foundry/Hardhat artifact JSON')
    dep.add_argument('--block', default='latest')

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
        if args.action == 'delta':
            print(json.dumps(delta(args.repo, args.since, args.scope, args.limit), indent=2))
            return 0
        if args.action == 'bundle':
            print(json.dumps(bundle(args.repo, args.run, args.lens, args.scope,
                                    args.include), indent=2))
            return 0
        if args.action == 'score-target':
            print(json.dumps(score_target(args.repo, args.program), indent=2))
            return 0
        if args.action == 'verify-deployment':
            print(json.dumps(verify_deployment(args.rpc, args.address, args.artifact,
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
