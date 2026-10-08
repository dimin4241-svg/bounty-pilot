# Candidate records and evidence

`findings.json` is an array of records, one per root cause. Start from `candidate-template.json`
that `init` wrote, and assign stable ids (`BP-001`, …). Deduplicate by root cause and affected path,
never by title similarity; split independent root causes, and keep multiple impacts of one root
cause together.

## Required fields

- `id`, `title`, `status`, `severity`, `bug_class`, `revision`, `root_cause`, `affected_paths`,
  `attacker_capabilities`, `preconditions`, `impact`, `scope_status`, `deployment_status`,
  `novelty`, `evidence`, `rejection_reason`.
- `status`: `hypothesis` | `needs-evidence` | `verified` | `refuted`.
- `severity`: `unassessed` | `informational` | `low` | `medium` | `high` | `critical`. Cite the
  program's rubric in `severity_rationale` before assigning a final label.
- `bug_class`: kebab-case, reused across passes and shared with the dup map, so the same mechanism
  keeps the same label (`aggregate-not-decremented`, `unvalidated-compose-sender`).
- `revision`: the exact commit the record was established against. Without it a `verified` record
  cannot be rechecked after the target moves, and findings outlive the revision that produced them.
- `scope_status`: `unknown` | `in-scope` | `out-of-scope`.
- `deployment_status`: `unknown` | `exact` | `partial` | `mismatch` | `not-applicable`, as
  `verify-deployment` reported it. Never set `exact` by hand.
- `novelty.status`: `not-checked` | `no-public-match-found` | `matched-public-issue`, with
  `novelty.sources` listing URLs and the comparison you made at each.

## Evidence fields, required for `verified`

- `command`: the exact reproduction command, with no credentials in it.
- `exit_code`: the observed integer. For a test that asserts the bad outcome this is normally 0.
- `log_path`, `poc_path`: existing files inside the private run directory, never symlinks out of it.
- `assertion`: the property that broke, and what the observed result establishes.
- `negative_control`: the contrasting case you actually ran and its result — not a proposed test.
- `source_integrity`: how unmodified production code and realistic dependency behaviour were kept.
- `impact_quantification`: what moved, how much, and at what attacker cost. Required to submit.

For `refuted`, `rejection_reason` cites a concrete protection, specification or test result. For
`needs-evidence`, name the missing experiment. Lack of a toolchain is not a refutation.

## The gates

Technical validity, severity, program eligibility and public-known-issue status are four separate
judgments and are never merged. The decision procedure is `adjudicate.md`; the four technical gates
are reachability, causality, material impact and eligibility, and a record can clear the first three
while the fourth is unknown. That is a normal, reportable state: a source-review finding.

Claims about profit include fees, capital, slippage and the liquidity that must exist. Claims about
denial include persistence, blast radius, one-time cost and the recovery path. Fork simulations are
point-in-time evidence about one block, not proof about every deployment state.

## What a passing checker does and does not mean

```sh
python3 <skill-dir>/scripts/bounty.py check --run <run>               # structure and artifacts
python3 <skill-dir>/scripts/bounty.py dup-check --run <run>           # burned surfaces
python3 <skill-dir>/scripts/bounty.py check --run <run> --submission  # readiness gates
```

The structural check verifies record completeness and that the artifacts exist. The submission gate
additionally refuses what programs actually reject: a status other than `verified`, scope that is
not established, a `deployment_status` other than `exact` or `not-applicable`, an unassessed
severity, a severity with no rubric citation, fewer than two checked novelty sources, missing impact
quantification, and a run with no dup map built.

**Neither checker establishes that a finding is real.** They cannot run your PoC, judge your
severity, see a private duplicate, or read the program's mind. An empty findings file passes the
structural check. Treat a green gate as "nothing is obviously missing", never as "this is valid".
