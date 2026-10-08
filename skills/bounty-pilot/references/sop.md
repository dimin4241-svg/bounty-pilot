# How to read code like someone who gets paid for finding bugs

This is not a checklist and it is not output. It is five habits, reached for when their trigger
fires. Your reply holds only CANDIDATE and LEAD blocks — none of the work below appears in it.

Pattern knowledge finds the bugs everyone finds. These habits find the ones that survived two
audits, and those are the ones still worth money.

---

## 1. Restate it in plain words — first, always

Before reasoning about any function, say what it does in words a non-programmer would follow. No
type names, no Solidity vocabulary, no restating the identifier.

`_settle(acc, amt)` is not "it settles the account". It is "it takes the money the protocol owes
this person and moves it to them, and writes down that it no longer owes it." Now keep going: are
those two things done in the same step? What is true in between? Who is the person — the caller,
or an address the caller chose?

**The place where your plain sentence gets vague is the bug.** When you reach for jargon, it is
because you do not actually know what happens there, and you were about to accept it anyway.

## 2. Trace the obligation, not the line

Every line that looks safe is safe *because of something that happens somewhere else*. That
something is an obligation, and an obligation has a holder.

For each check, cast, division, external call and state write, ask: what must be true for this to
be correct, and **who guarantees it?** A caller? A modifier? An earlier function? A deploy script?
A keeper? A human convention in a comment?

Then check that the holder exists and always holds. Three failures, all common and all profitable:

- **Nobody holds it.** Both sides assume the other validated. The classic shape: the caller
  trusts the callee to bound the index; the callee trusts the caller.
- **The holder is reachable only on one path.** The validation lives in the wrapper, and a second
  entry point reaches the inner function directly.
- **The holder changed.** A refactor moved the check, a fork removed it, an upgrade loosened it.
  The code it protected still assumes it.

A comment claiming an invariant is not a holder. It is a confession that the author knew the
obligation existed and did not enforce it.

## 3. Read it backwards

Forward reading answers "does this work". It is the author's question and you will get the author's
answer. Read every line a second time, inverted:

- For each guard: what value slips **past** it? Zero, one, the maximum, the self-reference, the
  duplicate, the empty array, the same block, the second call?
- For each state write: what state is possible **immediately before** this? Who could have put the
  contract there, and did they need permission?
- For each successful path: what makes it fail **halfway**, and what is left behind?
- For each loop or batch: what single element makes it never finish?

## 4. Ask who would notice

This one is specific to live protocols, and it is where the surviving bugs are.

For every value the code writes, ask: **if this were wrong, who would find out, and how long
would it take?** A user's own balance is reconciled constantly — bugs there get caught in testing.
An aggregate that only a cap check reads, a counter only a keeper consumes, a field only an
off-chain indexer displays: nobody reconciles those, so an error there lives in production until
it breaks something far away.

Then ask the follow-up that turns this into money: **what reads that value to make a decision?**
A mint cap, a solvency check, a price, a share conversion, a liquidation threshold. The harm is
never the wrong number; it is the decision made from it.

## 5. Escalate before you write it down

The moment you have something, you are not finished — you are at the *first* consequence, and the
first consequence is usually the cheapest one. Do three things before the finding leaves your
hands:

- **Find the siblings.** The same mistake is nearly always copied: the paired function, the other
  market, the second collateral, the other chain's deployment, the same hook in four adapters.
  One instance is a bug; five instances is the same bug with five times the blast radius.
- **Chain to the worst reachable end.** A wrong aggregate is not "incorrect accounting" — follow it
  to who cannot withdraw, what cannot be liquidated, which cap is now unreachable, whose collateral
  is mispriced. Keep going until the next step needs evidence you do not have, then stop **there**
  and say what the missing evidence is.
- **Lower the cost.** Can the precondition be reached without the admin, without the flash loan,
  without the large position, without waiting an epoch? A finding that needs nothing but a wallet
  is a different severity class from one that needs a million dollars.

Never do the opposite. During a hunt you do not soften a claim, decide it is intended, or assume a
guard exists that you have not read. Refutation is a separate pass with written gates; it needs
your claim at full strength to judge it at all.

---

## Why escalation is the part that pays

Programs pay by **impact class**, not by cleverness. The same root cause written as "accounting
inconsistency" and as "the market permanently stops accepting deposits, and no admin function
repairs it" are the same code and two different payouts — and only one of them is what the code
actually does. Underclaiming is as inaccurate as overclaiming.

So push every candidate to the highest class the evidence genuinely reaches, and not one step
further. `references/impact-classes.md` lists the classes and what each one demands as proof.

## Trust the discomfort

When a function reads fine but you cannot say why it is fine, that is the signal. It is not
fatigue and it is not your inexperience — it is habit 1 and 2 firing without a name yet. Stop,
restate it in plain words, and find the obligation holder. Do not move on until the discomfort has
a name, and if you cannot name it, emit a LEAD and say exactly what is unresolved. The next pass
can finish what you started; it cannot finish what you silently dropped.
