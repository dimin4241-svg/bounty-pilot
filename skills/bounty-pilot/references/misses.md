# Where hunts stop short

Run this against **your own output** before you report anything, including before reporting that you
found nothing. Each item is a failure that has a cheap fix, and most of them are the difference
between a finding and a near-miss rather than between effort and no effort.

Answer every question in writing. "Probably fine" is not an answer to any of them.

## 1. Did you conclude anything from a name?

This is the single most measured weakness of automated reviewers: **they reason from identifiers
instead of from behaviour.** It cuts both ways — a false finding because a variable is called
`totalDebt`, and a missed finding because a modifier is called `onlyOwner` and was never read.

For every conclusion you reached, in a finding *or* in a "this is safe", name the lines you actually
read. Specifically re-check: anything called `safe*` that may not check a return value; `onlyX` that
may compare the wrong variable; `total*` that may not be the total; `is*`/`has*` flags that some
public function writes; `_internal` functions reachable externally; a `validate*` that returns a
bool nobody checks.

## 2. Did you stop at the first consequence?

For each finding, write the chain: broken thing → the value it corrupts → the decision made from
that value → who loses what. If your impact sentence ends at the broken thing, you are filing at a
lower class than the code earns. Then check `impact-classes.md` and place it deliberately.

## 3. Did you put numbers on it?

If the mechanism involves price, liquidity, rounding, caps or profit, the report needs: capital
required, cost of the manipulation, gross extraction, net result, and the live values behind each.
Read them — `eth-call` and `value` take seconds. "The attacker profits" is a placeholder, and triage
reads it as one.

## 4. Did you skip the privileged path because a checklist told you to?

"Do not report admin can rug" means *the admin behaving badly*. It does not mean skipping how an
**unprivileged** actor reaches privileged power. Access control and initialization are the two
categories automated reviewers miss most, and the most expensive incidents live there. Did you check
initializers, the implementation behind the proxy, role-granting paths, and what every guard
actually compares against — live?

## 5. Did you read the dependency, or trust it?

The bug is often in the integration's assumption about a framework, and provable only from the
framework's own source. Did you open the messaging layer, the token, the router, the oracle, the
base contract — or did you stop at the interface? `lib/` being out of scope makes it unreportable,
not safe.

## 6. Did you check what is actually live?

Constants against real feeds. Hardcoded addresses against what is deployed there. Caps and fees
against current values. Owner and implementation slots against the docs. Whitelists against whether
they are populated. Pause flags. A guard that is correct in source and disabled in production is a
finding; a guard you assumed is disabled and is not is a wasted report.

## 7. Did you check the compiler?

`solc-bugs --repo <checkout>`. Two nine-figure-adjacent incidents came from compiler versions, not
contracts: a malfunctioning reentrancy guard in specific Vyper versions, and an old contract
compiled without overflow checks. Takes one command.

## 8. Is the revision you reviewed the revision that is deployed?

Not HEAD — the revision at the **in-scope addresses**. Programs pin scope to deployed contracts, and
a repository's main branch is frequently ahead of or behind them. Run `verify-deployment`, and for a
proxy compare the implementation. Reporting against code that is not deployed is the most common
single reason a technically correct report is rejected.

## 9. Did you look for the siblings?

The same mistake is nearly always copied: the paired function, the second market, the other
collateral, four adapters with one hook, and **the same contract on another chain with one value
configured differently**. One instance is a bug; five is the same bug with five times the exposure,
and exposure is how severity gets argued.

## 10. For anything that reverts or blocks — did you establish persistence?

Trigger, who is affected, one-time cost, and whether it clears by itself, by a keeper, by an admin
function you **read**, or never. A revert with no persistence analysis is not a finding and will be
closed as one.

## 11. Did you check it is not already known?

Program known-issues list, past audits, contest findings, closed issues and PRs. `dup-check` does
the mechanical part. If the surface collides, is your *mechanism* different, and did you write the
difference down?

## 12. Did you write prose where one command would have settled it?

For every `needs-evidence` record, name the cheapest decisive experiment and ask why you did not run
it. Order of preference: a live read, then a fork test at a pinned block, then a local deployment,
then analysis. Agents routinely reason for pages about a question that one `eth-call` answers.

## 13. Did a toolchain failure become a narrative?

If the build or test runner failed, say so plainly and switch to a cheaper decisive experiment. Do
not describe what a test would have shown. Do not claim an exit code you did not observe.

## 14. Did you drop anything silently?

Every lead you opened should end as a candidate, a refuted record with an anchor, or an
`open-needs-experiment` entry in `known-hypotheses.md` with the next step. A trail that exists only
in your reasoning is lost work, and the next pass will pay to rediscover it.

## 15. Is your claimed coverage real?

List what you did **not** read: files, branches, dependencies, configurations. An audit that reports
honest partial coverage is more useful than one that implies completeness; and the unread list is
where the next pass aims. Which lenses did you actually dispatch, and how many readings each?

## 16. Did you let an unanchored objection kill a finding?

Re-read every record you refuted. Does `rejection_reason` quote code, a specification, a test or a
live read? If it says "probably intended", "the deployer would set it correctly" or "no attacker
would bother", the refutation is invalid — reopen it. A wrongly refuted finding is invisible, which
is exactly why it needs a deliberate second look.

## 17. Did you read the tests?

Not for coverage percentages — for intent. A mock that cannot distinguish two inputs, a test that
asserts only "did not revert", a hardcoded expected value with no derivation, a skipped test, a TODO
on a validation path. These are the authors telling you what they did not check.

## 18. Did you read the program's whole scope?

Many programs include websites, APIs, infrastructure and off-chain components, often at real
severity and with far fewer competent competitors than the contract scope. Did you check, or did you
assume it was a Solidity-only hunt?

## 19. If you found nothing — is that a result or a gap?

A zero-finding run is legitimate and useful **if** it says which surfaces were closed and on what
evidence. "I reviewed it and it looks fine" is not that. Which lenses ran, which surfaces are closed
with reasons, which leads are open with next steps, and what you could not reach.

## 20. Would you pay for this report?

Read it as the triage engineer: first three sentences, then the reproduction. Does it say who can do
what, to whom, for how much, and how to see it happen? If the first thing it does is explain the
code, rewrite it.
