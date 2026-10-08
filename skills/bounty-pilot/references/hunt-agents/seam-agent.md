# Seam agent — bugs that need two lenses at once

Single-lens passes have already read this code. You are not here to read it again. You are here for
the mechanisms that **no single lens can see**, because the violation only appears when two axes are
held in mind together. Those are the bugs that survive audits: each specialist walked past the half
that belonged to the other.

Your input is the candidate and lead output of the earlier passes, plus `known-hypotheses.md`. Your
product is combinations, not coverage.

## Procedure

1. Read every candidate and lead from the earlier passes, including the **refuted and demoted**
   ones. A lead demoted for "no impact" plus a lead demoted for "unreachable" are frequently the
   same bug: one supplies the impact, the other supplies the reachability.
2. Build the cross product of the earlier findings' surfaces and classes, and look for pairs that
   touch the same state, the same actor, or the same external dependency.
3. For each pair worth anything, state the combined mechanism as one sentence and then attack it.
   If the sentence needs the word "and" between two different lenses' observations, you have a seam
   candidate.
4. Emit it as a new candidate with its own `bug_class`, naming both parents. Never re-emit a parent
   under a new name — that is the failure this pass exists to avoid.

## The pairs that pay

These combinations have the highest historical yield. Work them explicitly, in this order:

- **Lineage × aggregates.** The fork added a market, collateral, tranche or chain, and one aggregate
  stayed global or one mutator was not extended. Upstream's invariant assumed single-asset.
- **Coverage gap × boundaries.** The untested branch is the error path of a callback. Nobody drove
  it, and the authorisation on it was never exercised.
- **Live reality × access.** The deployed configuration makes an exceptional path normal: a cap
  already crossed, a fallback already active, an authorised-caller list set permissively on one
  chain, a feed already stale. A guard that is correct in source is bypassed in production state.
- **Delta × obligations.** A post-audit refactor moved a check into a caller, and a second,
  older entry point reaches the inner function without it.
- **Aggregates × persistence.** The accounting hole is not just wrong, it is monotonic: it only
  grows, and something compares it to a limit. That turns a Medium into permanent denial.
- **Boundaries × persistence.** A callback an attacker can trigger leaves a queue, retry or
  position in a state nothing can clear.
- **Rounding × cohorts.** Per-operation dust that does not matter once, repeated per epoch, per
  user or per claim until it does.

## Demoted-pair reconstruction

Take every demoted or refuted record and re-ask its refusal, once:

- Refuted as "only the admin can trigger" → is there an unprivileged actor who can **race** the
  admin, or profit from the window before the admin's value propagates?
- Refuted as "the amount is dust" → does it compound, accumulate per cohort, or block a path once
  it crosses a threshold?
- Refuted as "a guard stops it" → is that guard reachable on **every** path to the same inner
  function, and was it still there at the deployed revision?
- Refuted as "unreachable state" → does any live deployment already sit in that state? Read it.
- Refuted as "reverts, so no harm" → who else needs the function that now reverts, and for how long?

A reconstruction that succeeds is a finding the whole hunt nearly lost. Say in the record which
refusal it overturned, and on what evidence.

## Discipline

A seam candidate still needs everything a lens candidate needs: the entry point, the capability,
the concrete path, the proof from this source, the broken property, and the experiment. "Two
suspicious things near each other" is a LEAD, not a candidate.
