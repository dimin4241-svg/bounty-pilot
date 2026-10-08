# The duplicate map — built before the first pass

A bounty pays for a bug nobody has reported. Most of what a competent sweep finds on a mature
protocol is already public: in the program's own known-issues list, in its audit reports, in a
contest's published findings, in a closed GitHub issue, in the docs as acknowledged behaviour.
Discovering those again costs a pass and, filed, costs reputation with the program.

So the map is built **first**, and it burns surfaces before anyone reads code for bugs.

## Sources, in order of authority

1. **The program's own known-issues or out-of-scope list.** Highest authority: the team is telling
   you what it will reject. Read every line and record it, including the ones that sound like real
   bugs — especially those, because they are the tempting ones.
2. **Published audit reports** for this protocol, with their exact reviewed revision. A finding
   fixed at a later revision is still a dup signal for the mechanism; check whether the fix landed.
3. **Public contest results** (Sherlock, Code4rena, Cantina and similar), which publish every valid
   finding and often the invalid ones.
4. **The upstream's public issues** when the target is a fork: upstream's known bugs are not novel
   here either.
5. **Closed issues, PRs and release notes** in the target repository: a PR titled "fix rounding in
   redeem" names a class the team already handled.
6. **Post-mortems** of protocols running the same fork.

Record retrieval dates. A known-issues list is edited, and the version you read is the one you were
judged against.

## Format — `dup-map.json` in the run directory

```json
[
  {
    "id": "KI-001",
    "kind": "program-known-issue",
    "source": "https://github.com/<org>/bug-bounty#known-issues (read 2026-10-08)",
    "surfaces": ["src/oracle/PriceOracle.sol:latestAnswer", "src/oracle/DualFallbackOracle.sol"],
    "bug_classes": ["oracle-staleness"],
    "note": "team states staleness is accepted for this feed; deprecated market"
  }
]
```

`kind` is one of `program-known-issue`, `past-audit`, `contest-finding`, `docs-acknowledged`,
`public-disclosure`. `surfaces` uses the same `path:Contract.function` spelling the hunt agents
emit, because the join is mechanical:

```sh
python3 <skill-dir>/scripts/bounty.py dup-check --run <run-directory>
```

That reports every finding whose surface and bug class were already burned, as `class-match`
(same surface and same class) or `surface-only` (same surface, different or unlabelled class).

## What a collision means

A collision is **not** an automatic drop. It means: before this goes anywhere, state in the record
how your mechanism differs from the published one. Three outcomes, and all three are legitimate:

- **Same mechanism** → mark the finding `refuted` for submission purposes with the dup source as
  `rejection_reason`, and keep it in the file. It is coverage, not waste.
- **Same surface, different mechanism** → keep it, and write the difference into the report. This is
  common and valuable: teams burn a surface with one sentence and leave a second bug sitting there.
- **Same mechanism, different consequence** → keep it only when the new consequence changes severity
  materially, and lead the report with the consequence rather than the mechanism.

## The limit of this map

No public search proves there is no private duplicate. Another hunter may have filed yours an hour
ago, and self-hosted programs rarely publish their queue. `no-public-match-found` is the strongest
claim the evidence supports; never upgrade it to "original" in a report.
