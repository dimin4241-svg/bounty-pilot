# The hunt loop

Passes differ by **what they are aimed at**, not by how hard they try. Repeating one prompt
produces the same findings under new titles, and that is the main way a multi-pass hunt wastes
money. This file settles the aiming, the dispatch mechanics, and when to stop.

Two facts shape everything below. First, **the number of independent adversarial readings dominates
recall** — more than prompt wording, more than model choice. Second, **aiming beats sweeping on a
large or heavily audited codebase**, because an unaimed sweep spends the same effort on vanilla
upstream code that three auditors already read. So: aim cheaply, then attack with as many
independent readings as the budget allows.

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

## Stage B — Attack (the hunt passes)

```sh
python3 $S bundle --repo <checkout> --run <run> --lens attack --scope src/ --include <run>/delta.json
```

That writes one bundle per mechanism lens — `accounting`, `integration-auth`, `liveness`,
`live-reality` — each containing the SOP, the shared rules, that lens's procedure, the run context
and all in-scope source. Add `--lens anchor-account` for a Solana or Rust target.

**A pass that did not run `bundle` did not bundle its source**, and a lens reading files
opportunistically covers less than a lens handed everything. The command is the mechanic, not a
suggestion.

Dispatch one agent per bundle, each in its own context, up to four concurrent by default. Tell each
agent only: read this bundle and follow it. Independent contexts are the point — agents sharing one
context converge on the first idea and stop being independent reviewers.

**Pass 1** runs the mechanism lenses on the ranked surfaces. **Pass 2** runs the same lenses again,
with `known-hypotheses.md` now in the bundle, so each is explicitly hunting past its own earlier
output, plus the `seam` lens over both passes' records.

> **Where budget allows, dispatch each mechanism lens twice in pass 1, in two independent
> contexts.** Two independent readings of the same lens find different things; this is the cheapest
> recall increase available, and it costs only tokens. Doubling four lenses turns a 3-pass hunt from
> roughly 14 readings into roughly 18. State in the summary how many readings actually ran.

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
closed. A lens you could not dispatch is reported, never silently skipped.

## Stop rules

Stop when any one is true:

- The planned pass count is spent.
- Two consecutive passes produce neither a new mechanism nor new coverage. More reading will not
  help; the open leads need experiments.
- Every remaining lead is blocked on the same missing capability — a toolchain, an RPC, program
  rules. Report the blocker rather than narrating around it.

There is no finding quota. Zero verified findings after an honest run is a legitimate result, and
more useful than three inflated ones: say which surfaces you closed and on what evidence.

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
