# Adjudication — two rounds, and the objection must be proven too

Hunt passes are forbidden from refuting themselves, so refutation is its own stage. It runs as an
**adversarial exchange in two rounds**, because a one-round review has an asymmetry that quietly
destroys good findings: the finding is held to an evidence standard and the objection is not. An
agent that may reject on "probably intended" will reject nearly everything, and you will never
learn which of those was real.

So both sides carry the same burden. A claim needs an anchor in code, specification, test or a live
read. **An objection needs exactly the same thing**, and an objection that cannot produce one is
withdrawn rather than weighed.

## Round 1 — triage attacks

Dispatch a triage agent in its own context with `triage.md`, the candidate records and the source.
It is instructed to behave like the program's triage engineer: rewarded for correct rejections,
damaged by wrong ones. It produces `OBJECTION` blocks, each with a gate, an anchor type and the
quoted evidence, and `CONCEDED` blocks where it tried and failed.

Give it the records, not the hunter's reasoning. Give it the dup map. Do not give it the hunter's
confidence.

```sh
python3 <skill-dir>/scripts/bounty.py bundle --repo <checkout> --run <run> --lens triage
```

## Round 2 — the hunter answers, with evidence

Every objection gets an answer, and the answer carries its own anchor. Three outcomes, and they
are decided by the evidence, not by who argued longer:

| Outcome | When | Effect |
| --- | --- | --- |
| `answered` | the answer is anchored and defeats the objection | record both; the exchange becomes report text |
| `sustained` | the objection is anchored and the answer is not | the gate fails: finding dies or is demoted |
| `withdrawn` | the objection has no anchor | no effect on the finding; record it anyway |

Answers that are **not** anchors, and therefore do not defeat anything: "the guard can be
bypassed somehow", "an attacker would find a way", "it is still bad practice", "the fix is cheap
anyway". If the only answer is of that kind, the objection is sustained and you have learned
something true.

Answers that **are** anchors: a second entry point that reaches the inner function without the
quoted guard; the deployed configuration read on chain showing the guard disabled; the test the
objection cited asserting something narrower than claimed; the specification text contradicting
the objection's reading; a PoC run that passes with the guard in place.

Record the exchange on the finding:

```json
"objections": [
  {
    "gate": "interruption",
    "claim": "the nonReentrant modifier on redeem() stops the second entry",
    "anchor": "code: src/Vault.sol:142 modifier nonReentrant on redeem()",
    "answer": "the path uses redeemFor(), which reaches _redeem() directly and carries no guard",
    "answer_anchor": "code: src/Vault.sol:188-204 redeemFor -> _redeem, no modifier",
    "outcome": "answered"
  }
]
```

`gate` is one of `interruption`, `reachability`, `trigger`, `harm`, `eligibility`, `evidence`.
`outcome` is `answered`, `sustained` or `withdrawn`.

An `answered` or `sustained` objection must carry an `anchor`. A `withdrawn` one must not be
required to: it was withdrawn precisely because no anchor could be produced, so record the `claim`
and say in `withdrawn_because` what triage searched for and did not find. Keep withdrawn objections
in the record — an unrecorded bad objection gets raised again by the next reviewer, and by the
program's own triage engineer.

The checker validates the shape, and the submission gate refuses a finding with a `sustained`
objection or with no objections at all — a finding nobody attacked is a finding nobody has
reviewed.

**The surviving exchange is not overhead; it is the report.** The answered objections, written out,
are exactly the "Existing protections and known issues" section — the part that decides whether a
triage engineer believes you, and the part hunters usually leave out. You get it drafted for free
by doing the round properly.

## The five gates, as the objection taxonomy

Triage works these in order. Each one names what kills a claim and what does not.

### Gate 1 — Interruption

Walk the claimed path from the attacker's first call and read every guard on it.

- A specific guard stops the claimed step before harm, quoted, and present on **every** path to the
  inner function → **dead**.
- The interruption is speculative ("a keeper would notice", "the deployer sets this correctly") →
  **withdrawn**.

### Gate 2 — Reachability

- An enforced invariant makes the state impossible → **dead**.
- It needs a privileged action outside documented operation → **demote**, unless an unprivileged
  actor can race, front-run or amplify it; then name that actor and continue.
- It is reachable through ordinary use, or through token behaviours the protocol accepts
  (fee-on-transfer, rebasing, blacklists, non-18 decimals, revert-on-zero) → **clears**.

### Gate 3 — Trigger

- Only a trusted role can fire it → **demote**. Admin acting against documented intent is not a
  finding; the access mechanism itself being broken is.
- An unprivileged actor can → **clears**.

### Gate 4 — Material harm

- Self-harm only → **dead**.
- Dust that neither compounds nor persists → **demote**.
- A quantified loss, broken liability, corrupted record or persistent denial affecting someone
  other than the attacker → **clears**, and now place it on the ladder in
  `impact-classes.md`.

### Gate 5 — Eligibility

Separate from everything above, and never merged with it.

- In scope as the rules define it?
- Is the affected revision what is **deployed**? Run `verify-deployment`. For a proxy, the
  implementation is what must match — a matching proxy runtime establishes nothing.
- Is the impact class excluded by the program?
- Did `dup-check` collide, and is the mechanism difference written down?

A finding can clear gates 1–4 and fail gate 5. That is a real result: technically valid, not
submittable. Label it a source-review finding and record both judgments.

### Gate 6 — The evidence itself

Triage also attacks the PoC, which is where agent-written reports fail most often: attacker
privileges granted that the world does not grant, the component under test replaced by a
permissive mock, storage written directly into an unreachable state, an assertion that proves only
that something reverted, a missing or vacuous negative control, a severity matching the
theoretical maximum rather than the demonstrated one.

## Outcomes

| Verdict | Record |
| --- | --- |
| survived every gate, experiment run | `verified` with full evidence and the objection exchange |
| survived, experiment not yet run | `needs-evidence`, with the experiment named |
| demoted | `needs-evidence` or `hypothesis`, with the missing capability named |
| dead | `refuted`, `rejection_reason` quoting the sustained objection's anchor |

Nothing is deleted. A refuted record citing a specific protection is the cheapest asset a later
scan has: if that protection is ever edited, the finding is alive again, and `passes.md` says to
recheck exactly that on resume.

## Severity

Assign severity only against the program's published rubric, cite the clause in
`severity_rationale`, and place the impact using `impact-classes.md`. Do not import a severity from
another program's table. Push to the highest class the evidence defends and write the next class up
as a limitation. A program that catches one inflated claim reads the whole report differently.

## Promotions worth making before closing

- A root cause confirmed in one contract promotes every sibling instance of the identical pattern.
- Two independent lenses landing on the same surface from different directions is signal; re-read
  it before leaving it demoted.
- A candidate whose only weakness was an incomplete trace, where the path is reachable and
  unguarded, deserves the trace finished rather than the demotion kept.
- A demoted record whose refusal the `seam` lens can overturn with a second axis — that is the
  finding the hunt nearly lost.
