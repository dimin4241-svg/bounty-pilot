# Adjudication — the pass that tries to kill the candidate

The hunt pass is forbidden from refuting itself, so refutation is a separate pass with its own
instructions, and ideally its own context. Its job is to break each candidate, in order, against
written gates. A candidate that survives all five gates is worth an experiment; one that dies at a
gate is recorded as dead, with the reason, and kept.

Run this with the source open. An objection you cannot anchor in code, a specification, a test or a
live read is **not a refutation** — it is a feeling, and it does not close a candidate.

## Gate 1 — Interruption

Trace the claimed path from the attacker's first call to the harm. Read every modifier, require,
guard, bound, pause flag and ordering constraint actually on that path, and quote them.

- A specific guard on the path stops the step before harm → **dead**. Quote the line.
- The interruption is speculative ("the keeper would notice", "nobody would do that", "the deployer
  presumably sets this") → the gate **clears**.

## Gate 2 — Reachability

Show the vulnerable state is reachable in the configuration that is actually deployed.

- An enforced invariant makes the state impossible → **dead**.
- It needs a privileged action outside documented operation → **demote** to lead, unless an
  unprivileged actor can race, front-run or amplify that action; then name that actor and continue.
- It is reachable through ordinary use, or through token behaviours the protocol accepts
  (fee-on-transfer, rebasing, blacklists, 6 decimals, reverting on zero) → **clears**.

## Gate 3 — Trigger

Show who fires it.

- Only a trusted role can → **demote**. Admin acting against documented intent is not a finding on
  its own; the access mechanism itself being broken is.
- An unprivileged actor can → **clears**.

## Gate 4 — Material harm

Name the victim and what they lose.

- Self-harm only → **dead**.
- Dust that does not compound and does not persist → **demote**.
- A quantified loss, a broken liability, a corrupted record, or a persistent denial that affects
  users other than the attacker → **clears**.

For a profit claim, include fees, capital, slippage and the liquidity that must exist. For a denial
claim, include persistence, blast radius, one-time cost and the recovery path you read.

## Gate 5 — Eligibility

Separate from everything above, and never merged into it:

- Is the affected code **in the program's scope** as the rules define it?
- Is the affected revision **what is deployed**? Run `bounty.py verify-deployment`. A finding against
  code that is not deployed is a source-review finding and must be labelled one.
- Is the impact class excluded by the program?
- Did `dup-check` collide, and if so, is the mechanism difference written down?

A candidate can pass gates 1–4 and fail gate 5. That is a real result: technically valid, not
submittable. Record both judgments; never let one overwrite the other.

## Outcomes

| Outcome | Record |
| --- | --- |
| cleared all five, experiment run | `verified` with full evidence |
| cleared all five, experiment not yet run | `needs-evidence`, with the experiment named |
| demoted | `needs-evidence` or `hypothesis`, with the missing capability named |
| dead | `refuted`, with `rejection_reason` quoting the protection, spec or test |

Nothing is deleted. A refuted record with a cited reason is the cheapest asset a later scan has: if
the protection it cites is ever edited, the candidate is alive again.

## Severity

Assign severity only against the program's published rubric, and cite the clause in
`severity_rationale`. Where the rubric is unavailable, leave severity provisional and say so. Do not
import a severity from another program's table, and do not inflate a denial into a loss or a latent
bug into a live one — a program that catches one inflated claim reads the rest of the report
differently.

## Promotions worth making

Before closing the pass, look across the demoted set:

- The same root cause confirmed in one contract promotes every sibling instance of the identical
  pattern.
- Two independent lenses landing on the same surface from different directions is signal; re-read
  that surface before leaving it demoted.
- A candidate whose only weakness was an incomplete trace, where the path is reachable and
  unguarded, deserves the trace completed rather than the demotion kept.
