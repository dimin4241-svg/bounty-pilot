# Target selection

The largest factor in whether a hunt finds a payable bug is chosen before any code is read. A
well-run sweep of a thoroughly audited vanilla fork returns nothing; a careless look at fresh glue
code returns something. Spend an hour here.

## What makes a target worth a week

- **Unreviewed code exists.** Code committed after the last audit, or never audited at all. This is
  measurable: `bounty.py score-target` reports the share of in-scope lines churned since the audited
  revision. A protocol whose scope is identical to its audited revision is a poor target no matter
  how large the bounty.
- **The custom part is the scope.** A fork's own deviation, the chain-specific adapters, the glue
  between two systems. Vanilla upstream code is audited, public and in every known-issues list.
- **Few eyes per dollar.** A new chain, an unfashionable language, an off-hours program, a protocol
  whose contest ended before half its code was written.
- **First-to-report.** Platforms that split or reject duplicates make your work contingent on
  strangers' timing; first-to-report programs do not.
- **No deposit, and a published rubric.** A program that states severities and payouts in writing is
  a program you can argue with.
- **A published known-issues list.** Counter-intuitive, but a long list is good news: it is a free
  dup map, and it tells you exactly where the team has already looked.
- **Live state you can read.** A deployed protocol lets you check constants, configuration and
  aggregates against the chain — evidence nobody reviewing source alone can produce.

## What makes a target a waste

- Scope is a faithful fork of a heavily audited upstream, unchanged. Diff it, confirm identity,
  record that, and leave.
- Formally verified core with the verification published, and the scope is that core.
- A contest that just closed on the same revision: hundreds of hunters have read it this month.
- Known-issues list that pre-empts the entire custom surface.
- Rules that exclude the only impact class the code can plausibly suffer.
- Unverifiable payment history, or a program with no public rules at all — hunt it only knowingly.

## The facts file

Write `program.json` in the run directory from the program's own pages, and record where each fact
came from. Never infer a fact to make the score better.

```json
{
  "program": "Example",
  "url": "https://example.com/bug-bounty",
  "rules_read_at": "2026-10-08",
  "platform": "self-hosted",
  "deposit_required": false,
  "duplicate_policy": "first-to-report",
  "payout_max_usd": 100000,
  "severity_rubric_url": "https://example.com/bug-bounty#severity",
  "in_scope_paths": ["src/"],
  "excluded_impacts": ["DDoS on UI/API/RPC", "economic attacks requiring a large price move"],
  "audited_revision": "<exact commit the last audit covered>",
  "audit_reports": ["https://..."],
  "known_issues_count": 12,
  "upstream_fork": "aave-v3",
  "deployment_addresses_url": "https://docs.example.com/contract-addresses"
}
```

Then:

```sh
python3 <skill-dir>/scripts/bounty.py score-target --repo <checkout> --program <run>/program.json
```

The score is a reading order over targets, not a prediction. It reports its own unknowns, and an
unknown is a question to answer, not a reason to round up. `band: deprioritise` on a program you
have a specific reason to hunt is fine — write the reason down, so the next scan can check whether
it held.

## Keep the outcome

For each submitted report, record its disposition in the private history after submission and again
when the program decides it:

```sh
python3 <skill-dir>/scripts/bounty.py history record --run <run> --finding BP-001 \
    --outcome submitted --program "Cantina / Example" --hours 4
python3 <skill-dir>/scripts/bounty.py history record --run <run> --finding BP-001 \
    --outcome paid --case-id <id-printed-by-first-command>
python3 <skill-dir>/scripts/bounty.py history summary
```

Use `history import` to seed previous reports from concise, verified metadata. Keep target-level
effort for hunts with no submissions in a separate private note. Compare counts by target shape,
bug class, lens and disposition; they describe your recorded sample and do not forecast future
acceptance or payment.
