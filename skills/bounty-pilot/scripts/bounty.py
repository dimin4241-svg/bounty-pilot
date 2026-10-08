#!/usr/bin/env python3
"""Private audit run scaffolding and structural evidence validation; stdlib only."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

SOURCE_SUFFIXES = {'.sol', '.rs', '.move', '.vy', '.go', '.ts', '.js', '.py', '.c', '.h', '.cpp'}
STATUSES = {'hypothesis', 'needs-evidence', 'verified', 'refuted'}
SEVERITIES = {'unassessed', 'informational', 'low', 'medium', 'high', 'critical'}
REQUIRED = ('id', 'title', 'status', 'severity', 'root_cause', 'affected_paths',
            'attacker_capabilities', 'preconditions', 'impact', 'scope_status',
            'deployment_status', 'novelty', 'evidence', 'rejection_reason')


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode('utf-8', 'replace')


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def template():
    return dict(id='BP-001', title='', status='hypothesis', severity='unassessed',
                root_cause='', affected_paths=[], attacker_capabilities='', preconditions='',
                impact='', scope_status='unknown', deployment_status='unknown',
                novelty={'status': 'not-checked', 'sources': []},
                evidence={}, rejection_reason='')


def initialize(repo, out):
    repo, out = Path(repo).resolve(), Path(out).resolve()
    root = Path(git(repo, 'rev-parse', '--show-toplevel').strip()).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    if out == root or root in out.parents or out == skill_root or skill_root in out.parents:
        raise ValueError('Run directory must be outside the target and skill package')
    if out.exists():
        raise ValueError('Use a new run directory; existing output is never overwritten')
    commit = git(root, 'rev-parse', 'HEAD').strip()
    tracked = git(root, 'ls-files', '-z').split('\0')
    source = sorted(p for p in tracked if p and Path(p).suffix in SOURCE_SUFFIXES)
    dirty = bool(git(root, 'status', '--porcelain'))
    out.mkdir(parents=True, mode=0o700)
    dump(out / 'run.json', {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                          'commit': commit, 'dirty': dirty, 'scope_status': 'unknown',
                          'deployment_status': 'unknown', 'max_passes': 3,
                          'inventory_kind': 'tracked-source-candidates-not-authorized-scope',
                          'source_candidates': source})
    dump(out / 'findings.json', [])
    dump(out / 'candidate-template.json', template())
    (out / '.gitignore').write_text('*\n', encoding='utf-8')
    (out / 'scope.md').write_text('# Scope\n\nProgram eligibility and deployment: unknown.\n', encoding='utf-8')
    (out / 'model.md').write_text('# Model\n\nRecord assets, roles, transitions and evidenced invariants.\n', encoding='utf-8')
    (out / 'coverage.md').write_text('# Coverage\n\n| Surface / invariant | Pass | Experiment | Result / gaps |\n| --- | --- | --- | --- |\n', encoding='utf-8')
    return {'run': str(out), 'commit': commit, 'dirty': dirty, 'source_candidates': len(source)}


def has_text(value):
    return isinstance(value, str) and bool(value.strip())


def validate(run):
    run = Path(run).resolve()
    records = json.loads((run / 'findings.json').read_text(encoding='utf-8'))
    if not isinstance(records, list):
        return ['findings.json must be an array']
    errors, seen = [], set()
    for i, row in enumerate(records):
        prefix = f'finding[{i}]'
        if not isinstance(row, dict):
            errors.append(prefix + ': must be an object')
            continue
        missing = [k for k in REQUIRED if k not in row]
        if missing:
            errors.append(prefix + ': missing ' + ', '.join(missing))
            continue
        ident = row['id']
        if not isinstance(ident, str) or not re.fullmatch(r'BP-[0-9]{3,}', ident):
            errors.append(prefix + ': invalid id')
        elif ident in seen:
            errors.append(prefix + ': duplicate id')
        else:
            seen.add(ident)
        for key in ('title', 'root_cause', 'attacker_capabilities', 'preconditions', 'impact'):
            if not has_text(row[key]):
                errors.append(prefix + ': empty or non-string ' + key)
        paths = row['affected_paths']
        if not isinstance(paths, list) or not paths or not all(has_text(p) for p in paths):
            errors.append(prefix + ': affected_paths must be a nonempty string array')
        choices = {'status': STATUSES, 'severity': SEVERITIES,
                   'scope_status': {'unknown', 'in-scope', 'out-of-scope'},
                   'deployment_status': {'unknown', 'exact', 'partial', 'mismatch', 'not-applicable'}}
        for key, allowed in choices.items():
            if not isinstance(row[key], str) or row[key] not in allowed:
                errors.append(prefix + ': invalid ' + key)
        novelty = row['novelty']
        if not isinstance(novelty, dict):
            errors.append(prefix + ': novelty must be an object')
        else:
            if novelty.get('status') not in ('not-checked', 'no-public-match-found', 'matched-public-issue'):
                errors.append(prefix + ': invalid novelty.status')
            sources = novelty.get('sources')
            if not isinstance(sources, list) or not all(has_text(s) for s in sources):
                errors.append(prefix + ': novelty.sources must be a string array')
            elif novelty.get('status') != 'not-checked' and not sources:
                errors.append(prefix + ': novelty check requires sources and comparison notes')
        evidence = row['evidence']
        if not isinstance(evidence, dict):
            errors.append(prefix + ': evidence must be an object')
            continue
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
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    init = sub.add_parser('init', help='Create private run metadata; does not audit or run target code')
    init.add_argument('--repo', required=True)
    init.add_argument('--out', required=True)
    check = sub.add_parser('check', help='Check record structure and artifact presence, not exploit validity')
    check.add_argument('--run', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'init':
            print(json.dumps(initialize(args.repo, args.out), indent=2))
            return 0
        errors = validate(args.run)
        print(json.dumps({'structural_check': 'failed' if errors else 'passed', 'errors': errors,
                          'notice': 'This does not verify exploit validity, severity, originality or eligibility.'}, indent=2))
        return 1 if errors else 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
