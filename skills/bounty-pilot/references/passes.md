# The hunt loop

Passes differ by **what they are aimed at**, not by how hard they try. Repeating one prompt
produces the same findings under new titles, and that is the main way a multi-pass hunt wastes
money. This file settles the aiming, the dispatch mechanics, and when to stop.

Two working hypotheses shape this loop. Independent readings may surface different mechanisms, and
aiming may save effort on a large or heavily audited codebase. Neither should be treated as a
universal law: model outputs can be correlated, and a ranking can hide an unranked path. Record
unique coverage per reading, keep unexamined paths visible, and use held-out cases to decide whether
extra passes earn their cost.

## Stage A — Aim (cheap, mechanical, not a hunt pass)

Three lenses whose job is a ranked surface list, not findings. They read diffs, manifests and test
files rather than hunting the whole codebase, so they are cheap and they run once.

```sh
S=<skill-dir>/scripts/bounty.py
python3 $S delta --repo <checkout> --since <audited-commit> --scope src/ > <run>/delta.json
python3 $S bundle --repo <checkout> --run <run> --lens aim --scope src/ --include <run>/delta.json
```

Dispatch `delta`, `upstream-diff` and `coverage-gap`, one agent each. Their combined product goes
into `coverage.md` as a ranked reading order, and every later pass is given it. If `--since` has no
evidenced baseline, say so and review in full — never call an arbitrary recent range the
post-audit delta.

## Choosing lenses — select by behavior and stack

There are thirteen lenses. Running every one on every target wastes most of the budget on surfaces
the protocol does not have. Pick by shape, and say in `coverage.md` which you chose and why.

| Target shape | Run first | Then |
| --- | --- | --- |
| Lending / CDP / money market | `economics`, `accounting`, `privileged-path` | `live-reality`, `liveness`, `delta` |
| DEX / AMM / concentrated liquidity | `economics`, `accounting`, `external-call` | `upstream-diff`, `coverage-gap` |
| Vault / ERC-4626 / yield aggregator | `accounting`, `economics`, `external-call` | `privileged-path`, `liveness` |
| Bridge / cross-chain messaging | `integration-auth`, `privileged-path`, `external-call` | `live-reality`, `upgrade` |
| Router / aggregator / zapper | `external-call`, `integration-auth` | `privileged-path`, `accounting` |
| Staking / LST / restaking | `accounting`, `privileged-path`, `economics` | `liveness`, `upgrade` |
| Perps / options / structured | `economics`, `accounting`, `live-reality` | `liveness`, `coverage-gap` |
| Governance / timelock / treasury | `privileged-path`, `upgrade` | `liveness`, `delta` |
| Any fork of a known upstream | `upstream-diff`, `delta` | the shape's own row |
| Any upgradeable deployment | `upgrade`, `privileged-path` | the shape's own row |
| Solana / Anchor program | `anchor-account`, `privileged-path`, `economics` | `business-logic`, `temporal-logic` |
| Native Rust worker / keeper / bridge | `recovery-failure`, `semantic-mismatch`, `business-logic` | `temporal-logic`, `composition` |
| Move / Cairo / CosmWasm | `business-logic`, `temporal-logic`, `privileged-path` | `composition`, stack-native adapter |
| Cross-language relayer + contracts | `semantic-mismatch`, `recovery-failure`, `integration-auth` | `composition`, `coverage-gap` |
| Go / Python / TypeScript backend | `privileged-path`, `recovery-failure`, `business-logic` | `semantic-mismatch`, `composition` |

Two lenses run on essentially every target, because their yield does not depend on the protocol's
shape: **`privileged-path`** (access control and initialization are the categories automated
reviewers measurably miss most, and the largest real losses came from them) and **`coverage-gap`**
(the tests tell you what the authors never checked).

## Stage B — Attack (the hunt passes)

```sh
python3 $S bundle --repo <checkout> --run <run> --lens attack --scope src/ --include <run>/delta.json
```

The `attack` group is the six highest-yield mechanism lenses — `privileged-path`, `accounting`,
`integration-auth`, `external-call`, `economics`, `liveness` — and the `config` group is
`live-reality` and `upgrade`, which check what is true of the deployment rather than the source. Add
`--lens anchor-account` for Solana or Rust. Each bundle carries the SOP, the shared rules, that
lens's procedure, the impact ladder, the precedent catalogue, the run context and all in-scope
source.

**A pass that did not run `bundle` did not bundle its source**, and a lens reading files
opportunistically covers less than a lens handed everything. The command is the mechanic, not a
suggestion.

Dispatch one agent per bundle, each in its own context, up to four concurrent by default. Tell each
agent only: read this bundle and follow it. Independent contexts are the point — agents sharing one
context converge on the first idea and stop being independent reviewers.

**Pass 1** runs the mechanism lenses on the ranked surfaces. **Pass 2** runs the same lenses again,
with `known-hypotheses.md` now in the bundle, so each is explicitly hunting past its own earlier
output, plus the `seam` lens over both passes' records.

> **Where budget allows, dispatch a selected mechanism lens twice in pass 1, in separate
> contexts.** Do this selectively: count distinct mechanisms and new covered paths, not just model
> agreement. Repeated contexts cost real budget and may be correlated. State the readings that ran
> and what unique coverage each added.

## Adaptive reading budget

Use `python3 <skill-dir>/scripts/stack_route.py --repo <checkout>` to produce a conservative
runtime inventory and a six-lens shortlist, or `bounty.py bundle --lens recommended` for
bundled independent contexts. The priority is an unvalidated heuristic based on manifests,
not the probability of real vulnerabilities. Track unique surfaces and mechanisms after
passes; stop duplicating a lens if its new coverage is zero. Override automatically chosen
lenses when target facts warrant it, and document omitted necessary analyses.

## Independent stateful logic discovery

Use `--lens logic` for `business-logic`, `temporal-logic`, and `composition`.
These independently inspect source, even when earlier lenses produced **zero** candidates.
Use `--lens cross-stack` for `semantic-mismatch` and `recovery-failure` whenever
multiple runtimes or asynchronous components participate. Apply adapter guidance
(`adapters/`) for the **actual** runtime. `seam` remains a separate recombination
pass over earlier records; it does not replace independent composition search.

Avoid exploding the budget: after the initial ranked pass, choose the single most plausible
hypothesis and attempt its cheapest decisive native test before duplicating readings.
The lexical `state_graph.py` output can guide selection but is not a reachability graph.

## Stage C — Seams

```sh
python3 $S bundle --repo <checkout> --run <run> --lens seam --scope src/
```

The `seam` bundle carries the earlier passes' records, including the **demoted and refuted** ones,
and hunts only mechanisms that need two axes at once. This is also where refusals get reconstructed:
a lead demoted for "no impact" and one demoted for "unreachable" are often the same bug, each
supplying what the other lacked.

## Stage D — Triage, two rounds

Findings now meet an agent whose job is to reject them. The full protocol, including the rule that
**objections carry anchors too**, is in `adjudicate.md`.

```sh
python3 $S bundle --repo <checkout> --run <run> --lens triage
```

Round 1: the triage agent emits anchored `OBJECTION` blocks and explicit `CONCEDED` blocks. Round 2:
each objection is answered with its own anchor, and the exchange is recorded on the finding as
`objections[]`. The checker validates the shape; the submission gate refuses a finding with a
sustained objection, or with no triage exchange at all.

Run triage **after** the hunt passes, not between them. A hunter that knows triage is coming next
starts softening its own claims, which is exactly what the separation exists to prevent.

## Between passes — write the floor

After every pass, append one line per investigated mechanism to `known-hypotheses.md`:

```
surface | bug-class | status | one line: why it is closed, or what is still open
```

Status is `closed-refuted`, `closed-verified`, `open-needs-experiment` or `open-blocked`. Include
the mechanisms you looked for and did **not** find — an absence recorded is coverage; an absence
forgotten is a pass spent re-deriving it. Record what you did not reach too: files unread, branches
untraced, dependencies unopened. That list is the honest answer to "what did this cover", and it is
where the next pass aims.

Update `coverage.md` with which lenses actually ran, how many readings each got, and what each
closed. A lens you could not dispatch is reported, never silently skipped. Then run:

```sh
python3 $S queue --run <run>
python3 $S history check --run <run>
```

Run the cheapest decisive queued test before another broad pass. Review same-project history matches
for exact repeats; use them to steer later passes toward distinct root causes. A shared path is not a
reason to drop a lead, and a similar pattern in another repository is context, not a duplicate.

## Stop rules

Stop when any one is true:

- The planned pass count is spent.
- Two consecutive passes produce neither a new mechanism nor new coverage. More reading will not
  help; the open leads need experiments.
- Every lens the shape table calls for has run, and `misses.md` is answered.
- Every remaining lead is blocked on the same missing capability — a toolchain, an RPC, program
  rules. Report the blocker rather than narrating around it.

There is no finding quota. Zero verified findings after an honest run is a legitimate result, and
more useful than three inflated ones: say which surfaces you closed and on what evidence.

## Before you report — answer `misses.md`

The last step of the loop is not a pass; it is a check against your own output.
`references/misses.md` lists twenty ways a hunt stops short, each with a cheap fix: concluding from
a name, stopping at the first consequence, skipping the privileged path because a checklist said
"do not report admin can rug", never reading the dependency, never checking the compiler, auditing
HEAD when scope is pinned to deployed addresses, dropping leads silently, and letting an unanchored
objection kill a real finding.

Answer every item in writing, including on a run that found nothing. Most are one command or one
paragraph, and each of them is a near-miss that was already paid for.

## Budget, honestly

A 3-stage run with four mechanism lenses, doubled in pass 1, is roughly 18 agent readings plus
triage. Each mechanism bundle contains the full in-scope source, so cost scales with the codebase —
`bundle` reports each bundle's size and warns past 400 KB, where narrowing `--scope` and trusting
the ranking beats handing a lens more than it will read.

If the target is Solidity and `solidity-auditor` is installed, delegate the classic bug-class sweep
to it in loop mode instead of writing those lenses yourself, and spend this loop's passes on the
aimed lenses it has no equivalent for. `compare.md` has the division of labour and the import rules.
Do not nest the two orchestrators.

## Carrying work across scans

`known-hypotheses.md` and `findings.json` from a previous run on the same target are inputs to the
next one. On resume, compare the recorded commit with the current one: mechanisms on unchanged code
stay closed, mechanisms on changed code reopen. A refuted record whose cited protection has since
been edited is alive again — rechecking exactly those is one of the most productive things a second
scan does.
