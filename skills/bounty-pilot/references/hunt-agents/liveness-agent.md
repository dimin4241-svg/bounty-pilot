# Liveness agent — damage that does not undo itself

Theft is the headline, but most programs pay for **permanent** loss of function, and that class is
systematically under-hunted because it needs no profit motive and no price assumption. Your question
is: what can an unprivileged actor do, once, cheaply, that the protocol cannot recover from without
an upgrade?

## Procedure

1. Enumerate the states the protocol cannot leave: values that only ever grow, counters with no
   reset, arrays with no removal, mappings with no delete, queues processed in order, flags set
   with no unsetter, and anything an upgrade would be needed to fix.
2. For each, find the cheapest unprivileged write. Dust deposits, one-wei donations, a zero-amount
   call, a self-referential registration, a first entry into an empty structure, a dust position
   that cannot be liquidated profitably.
3. Ask what reads that state: a cap, a loop bound, a required ordering, a solvency check, a
   division. The harm is the reader refusing to work, not the state itself.
4. Check the recovery path honestly, and read it rather than assuming it: is there an admin
   function that fixes this, is it reachable, does it have the right arguments, and does the fix
   leave the accounting consistent? "The team can upgrade" is not a recovery path, and most programs
   score it accordingly.
5. Measure cost and blast radius: what the attacker pays once, how many users are affected, whether
   the condition worsens over time on its own, and whether anyone else can repair it.
6. Check the growth paths: loops over user-controlled arrays, per-iteration external calls,
   unbounded queue processing, batch functions whose single poisoned element reverts the batch
   forever, and retries that persist a bad element rather than skipping it.

## Where the money is

- An aggregate that only grows, compared against a mint or borrow cap: the market stops accepting
  new positions, permanently, worsening with each use. Pair this lens with the accounting lens.
- A sorted list or queue an attacker can seed with an element that makes insertion revert.
- A liquidation path that cannot be profitably executed for a position an attacker created
  deliberately, leaving unclearable bad debt in the accounting.
- Initialisation that can be front-run or performed once by anyone, locking a parameter forever.
- A share price an attacker can inflate once so that all later small deposits round to zero.
- A dependency the protocol cannot change: a hardcoded router, oracle or token whose failure has no
  configured fallback.

## Discipline

A revert is not a finding. State, for every candidate: the unprivileged trigger, the persistence
(does it clear by itself, by a keeper, by an admin, or never), the set of users affected, and the
one-time cost. A reachable, permanent, cheap, wide condition is a strong finding; any one of those
four missing usually demotes it, and the program's own rubric decides by how much.
