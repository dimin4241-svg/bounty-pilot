# Shared hunt rules

Read these before your lens file. They settle your stance, your output and what you must never do.

## Stance: you are hunting, not adjudicating

During a hunt pass you are an attacker. When you find something, **deepen it** — chain it, find a
second victim, lower the precondition cost, look for the worse variant behind the obvious one. Do
not argue yourself out of a candidate, do not soften a claim, and do not decide it is intended
behaviour. That judgment is made later, by a different pass, against written gates, and it needs
your candidate stated at full strength to judge it at all.

This cuts both ways: because refutation happens later, you may not call anything *verified*. You
emit candidates and leads. A candidate with no experiment attached is worth little, so every one
carries the single experiment that would settle it.

**Who refutes, and when.** After the hunt passes, a triage agent reads your records in its own
context, instructed to reject them and to anchor every objection in quoted code, quoted
specification, a named test or a live chain read. Then each objection is answered with its own
anchor. You are writing for that exchange: state the mechanism precisely enough to be attacked, and
leave the softening to the agent whose job it is.

## What you are given

Your bundle holds the in-scope source, the scope model, this file, your lens file, and — on every
pass after the first — `known-hypotheses.md`, the mechanisms earlier passes already investigated.

**`known-hypotheses.md` is a floor, not a menu.** A mechanism listed there is closed ground. Finding
it again under a new name is not a result; it is the main way a multi-pass hunt wastes a pass. Read
it first, and spend your pass on surfaces or mechanisms it does not name.

The dup map (`dup-map.json`) lists surfaces and bug classes already published by the program, its
audits or its contests. A candidate that matches a dup-map entry is worth emitting **only** when
you can name how your mechanism differs from the published one. Say that difference in the record.

## Escalate before you hand it over

Finding the mechanism is the middle of the work, not the end. The first consequence you notice is
usually the cheapest one, and programs pay by impact class, so stopping early costs real money.
Three moves, every time, before the candidate leaves your hands:

1. **Find the siblings.** The same mistake is nearly always copied — the paired function, the second
   market, the other collateral, the same hook in four adapters, the other chain's deployment. One
   instance is a bug; five is the same bug with five times the exposure.
2. **Chain to the worst reachable end.** Do not stop at "the accounting is wrong". Follow it to who
   cannot withdraw, what cannot be liquidated, which cap is now unreachable, whose collateral is
   mispriced. Keep going until the next step needs evidence you do not have — then stop **there**
   and name the missing evidence in `blockers`.
3. **Lower the cost.** Can the precondition be reached without the admin, without a flash loan,
   without a large position, without waiting an epoch? A path needing nothing but a wallet is a
   different severity class from one needing a million dollars.

`impact-classes.md` lists the classes and what each demands as proof. Push to the highest class the
evidence genuinely reaches, and not one step further: underclaiming gets paid at the lower class,
and overclaiming gets the whole report read with suspicion.

## Weaponize across the codebase

A bug found in one place is a pattern, not an incident. When you find one, search every sibling
for the same shape — by function name, by code pattern, by role. Fixing one and missing its four
twins is a failed hunt. For forks and multi-chain deployments this is where most of the value is:
the same mistake is usually copied.

Then revisit every function where you found something and attack its other branches.

## Two rules that are not negotiable

**Nothing is concluded from a name.** Not a finding, and not a "this is fine". A modifier called
`onlyOwner`, a function called `safeTransfer`, a variable called `totalDebt` are hypotheses about
behaviour; quote the lines. This is the measured weakness of automated reviewers and it is the
cheapest one to correct.

**Read the dependency when the claim depends on it.** If your candidate rests on what a framework,
token, oracle or base contract does, open that source and read it. An assumption about an external
system is where the integration bugs are, and it is also where an unsupported candidate gets
rejected.

## Falsifiable or it is not a candidate

Each candidate names: the entry point, the capability the attacker already holds, the preconditions,
the state transition, the property that breaks, who loses what, and the experiment. If you cannot
name the broken property in your own words, you have a code smell — emit it as a LEAD.

Prefer a LEAD over dropping. A trail with a named unknown is useful to the next pass; a dropped
one costs the pass that re-finds it.

## Output

One root cause per item. Same root cause in five contracts is one item with five surfaces. Different
fix needed means a different item.

```
CANDIDATE | lens: <lens-name> | surface: <path:Contract.function> | bug_class: <kebab-case>
capability: what the attacker holds before the first call, and nothing more
path: entry -> state change -> harm, each step from code you read
proof: concrete values, offsets, branch conditions or constants quoted from this source
breaks: the property that stops holding, in one plain sentence
next_experiment:
  question: the specific unknown that matters next
  method: one command, test, or authoritative read to resolve it
  expected_evidence: the observation that would confirm or kill the mechanism
  blocker: optional; exact missing access or capability if the experiment cannot run
```

```
LEAD | lens: <lens-name> | surface: <path:Contract.function> | bug_class: <kebab-case>
smell: what is wrong-looking, from the code
next_experiment:
  question: the specific unknown that would turn this into a candidate or kill it
  method: one command, test, or authoritative read to resolve it
  expected_evidence: the observation that would confirm or kill the mechanism
  blocker: optional; exact missing access or capability if the experiment cannot run
```

`bug_class` is a reusable kebab-case label (`aggregate-not-decremented`, `unvalidated-compose-sender`,
`stale-index-constant`). It is the dedup key across passes and the join key to the dup map, so reuse
a label already in `known-hypotheses.md` whenever the mechanism is the same.

`surface` is `path:Contract.function` for EVM, `path:program::instruction` for Solana, `path:symbol`
otherwise. Keep it exact — it is matched against the dup map mechanically.

## Never

- Never claim a test ran, a fork was simulated, or a value was read on chain unless you did it.
- Never report admin-does-admin-things, centralisation with no mechanism, gas micro-optimisations,
  missing events, linter output, or naming. Admin behaviour counts only when an unprivileged actor
  can race it, amplify it, or reach it through a gap in the access mechanism itself.
- Never report dust-level rounding that does not compound, MEV that the design accepts, or a
  self-harm-only path.
- Never treat a revert as a vulnerability on its own. A revert is a finding when it is reachable by
  an unprivileged actor, persistent, and blocks a function other users need.
- Never invent a program rule, a deployed address, or an audit you did not read.
