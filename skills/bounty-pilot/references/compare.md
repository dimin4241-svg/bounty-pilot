# Relationship to pashov/skills `solidity-auditor`

Read this before deciding whether to run Bounty Pilot's own hunt passes, `solidity-auditor`, or
both. The honest answer is usually both, in a particular order. Observations below are from
`solidity-auditor` v4.1; check the version you have installed before relying on them.

## What `solidity-auditor` does

One invocation dispatches twelve specialist agents in parallel, each given the whole in-scope
Solidity source plus a senior-auditor reasoning file, its own specialty file, shared output rules and
report-language rules. Nine agents are single-lens (math and precision, access control, economic
security, execution trace, invariants, periphery, first principles, asymmetry, boundaries) and three
hunt the seams between lenses (flow, numerical, trust). Loop mode runs N such passes — three by
default — and feeds each later pass the bug classes earlier passes already found, deduplicating on a
`Contract | function | bug_class` key and persisting across scans in a ledger. Findings are then
judged against four gates, scored for confidence against a 75 threshold, and assembled into one
report, with explicit lists of safe patterns and things not to report.

**It is very good at generating candidates.** The breadth of lenses, the parallel independent
contexts, the three seam agents, the "deepen the attack, never refute your own finding" stance and
the cross-contract weaponization rule are the right machinery for recall, and Bounty Pilot's own
lens set does not replace it on Solidity.

## What it is not built to do

It audits a repository. A bounty submission is a claim about a **deployed** system inside a
**program's rules**, and that is a different object:

| Needed for a payable report | `solidity-auditor` | Bounty Pilot |
| --- | --- | --- |
| Program rules, scope and exclusions | not modelled | `intake.md`, `targets.md`, gate 5 |
| Deployed code is the code you audited | not checked | `verify-deployment`, EIP-1967 resolution |
| Known issues and public findings burned first | not checked | `dup-map.md`, `dup-check` |
| Priority on code the last audit never saw | all code equally | `delta`, `delta-agent` |
| Constants and config checked against the chain | source only | `live-reality-agent`, `eth-call` |
| A runnable PoC with a negative control | reasoning trace | `evidence.md`, `templates/` |
| Novelty search with cited sources | not performed | stage 6 |
| Non-EVM targets | Solidity only | Rust/Solana route, `anchor-account-agent` |

Two more differences matter in practice. Its confidence number is self-assessed by the model that
produced the finding, so a 90 means the agent was convinced, not that anything executed — Bounty
Pilot's `verified` requires a command, an exit code, a log and a negative control. And its
generation stance deliberately suppresses self-refutation, which is right for recall and must be
paid for by a real adjudication pass afterwards, or the report arrives at the program full of
confident candidates that a triage engineer kills in one reading.

## Recommended combination

1. **Bounty Pilot stages 0–2.** Choose the target, read the program rules, build the dup map, verify
   what is deployed, and run `delta` to get the ranked surface list. Nothing is read for bugs yet.
2. **Delegate the Solidity generation pass to `solidity-auditor`, in loop mode**, pointed at the
   target. Give it the ranked surfaces and the dup map contents in the request so its passes do not
   spend themselves on burned ground. Keep its own report; it is a good artifact.
3. **Run Bounty Pilot's own lenses that it does not have** — `delta`, `upstream-diff`,
   `coverage-gap`, `live-reality`, `accounting` (as writer enumeration), `integration-auth`,
   `liveness`, and `anchor-account` for non-EVM. These are aimed at axes outside its lens set:
   time, lineage, observability, live truth, and the authorization of parameters rather than callers.
4. **Import its output as hypotheses, not findings.** Each `FINDING` / `LEAD` block becomes one
   `findings.json` record with `status: hypothesis`, its `group_key` split into `surface` and
   `bug_class`, and `evidence` empty. Its confidence score is not evidence and does not transfer.
5. **Adjudicate everything together** with `adjudicate.md`, then verify survivors with a real PoC,
   then `dup-check`, then `check --submission`.

Do not nest the two orchestrators — do not ask `solidity-auditor` to run Bounty Pilot's passes or
the reverse. Both are multi-pass loops; nesting multiplies cost and makes coverage unreadable.

## Note on its artifacts

`solidity-auditor` writes into the audited repository (`.solidity-auditor/`, including a findings
ledger). That path is already in this repository's `.gitignore`, but check the target's own
`.gitignore` before committing anything there, and never commit a findings ledger to a public
target repo.

## Also in the same family

`x-ray` (pre-audit readiness: threat model, invariants, git history) is a reasonable substitute for
parts of Bounty Pilot stage 2 on Solidity targets, and `fizz` (Echidna/Medusa invariant suites) is a
genuine verification tool — if a candidate is an invariant violation, a fuzz suite that breaks the
invariant is stronger evidence than a hand-written PoC. Prefer them over writing those stages from
scratch, record the exact commit you ran, and normalise whatever they produce through this
workflow's gates.
