# The hunt loop

A pass is one round of lens agents over the target. Passes differ by **what they are aimed at**, not
by how hard they try. Repeating one prompt produces the same findings with new titles; that is the
failure this file exists to prevent.

## Shape of the loop

Default is three passes. Each pass dispatches its lenses, collects candidates and leads, then
appends to `known-hypotheses.md` before the next pass starts.

**Pass 1 — where to look.** Lenses: `delta`, `upstream-diff`, `coverage-gap`.
This pass produces almost no findings and that is correct: its product is a *ranked surface list* —
which code is new since the audit, which is the fork's own deviation, and which is untested or
untestable. Write that ranking into `coverage.md`. Everything later is aimed by it.
Run `bounty.py delta` and `bounty.py score-target` here, before reading source in bulk.

**Pass 2 — mechanism.** Lenses: `accounting`, `integration-auth`, `liveness`.
These are the heavy bug-class lenses, and they run **against the surfaces pass 1 ranked first**, not
against the whole repo. Give each agent the ranking and the scope model, and let it read the rest of
the source as needed.

**Pass 3 — reality and seams.** Lenses: `live-reality`, plus one *seam* agent.
`live-reality` verifies every externally-meaningful constant and the deployed configuration against
the chain. The seam agent receives pass 1 and pass 2 output and hunts only mechanisms that need two
lenses at once — an accounting hole reachable through a callback, a stale constant that only matters
in the untested branch, a fork deviation that breaks an upstream invariant one layer away. Seam
mechanisms are what single-lens passes structurally cannot see.

**Solana or Rust target:** `anchor-account` joins pass 2, and `live-reality` reads the on-chain IDL
and account state in pass 3.

**Pass 4 and beyond** exist only when leads remain that name a concrete experiment. Then the pass is
that experiment, not another sweep.

## Dispatch

Run the lenses of one pass in parallel when the runtime supports independent agents — each in its own
context, each with the scope model, `_shared.md`, its own lens file, and `known-hypotheses.md`.
Default to at most four concurrent workers. Independent contexts matter: agents sharing one context
converge on the first idea and stop being independent reviewers.

Where parallel agents are unavailable, run the same lenses sequentially and say so in the summary —
sequential passes lose independence, because each lens has already read the previous lens's
conclusions.

Never dispatch a lens whose file you have not read, and never report a lens as run when it was not.

## Between passes — write the floor

After every pass, append one line per investigated mechanism to `known-hypotheses.md`:

```
surface | bug-class | status | one line: why it is closed, or what is still open
```

Status is `closed-refuted`, `closed-verified`, `open-needs-experiment`, or `open-blocked`. Include
the mechanisms you looked for and did **not** find — an absence recorded is coverage; an absence
forgotten is a pass spent re-deriving it.

Also record what you did not reach: files not read, branches not traced, dependencies not opened.
That list is the honest answer to "what did this audit cover", and it is where pass 3 aims.

## Stop rules

Stop when any one of these is true:

- The planned pass count is spent.
- Two consecutive passes produce neither a new mechanism nor new coverage. More passes will not
  help; the leads need experiments, not more reading.
- Every remaining lead is blocked on the same missing capability (a toolchain, an RPC, program
  rules). Report the blocker instead of working around it with narrative.

There is no finding quota. Zero verified findings after three honest passes is a legitimate result,
and far more useful than three inflated ones — say which surfaces you closed and why.

## Carrying work across scans

`known-hypotheses.md` and `findings.json` from a previous run on the same target are inputs to the
next one. On resume, compare the recorded commit with the current one: mechanisms on unchanged code
stay closed, mechanisms on changed code reopen. A refuted hypothesis whose refuting protection was
edited is no longer refuted — that is one of the most productive things a second scan can find.
