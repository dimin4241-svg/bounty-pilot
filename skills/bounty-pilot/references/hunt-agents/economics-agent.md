# Economics agent — is the attack actually profitable, and at what size

A finding that says "the attacker can manipulate the price" and stops there is the most common
half-finished report in bug bounty. Triage will ask three questions you must answer first: **how
much capital, how much does the manipulation cost, and how much comes out?** Answer them with live
numbers and a mediocre mechanism becomes a Critical; leave them and a real mechanism gets closed as
theoretical.

This lens also runs in reverse: it rescues findings wrongly dismissed as unprofitable because nobody
checked the actual pool depth or the actual position cap.

## Procedure

1. **Find every number that comes from outside.** Each price, rate, ratio, supply, index, TWAP and
   "amount out" read from another contract. For each, identify the exact source — which pool, which
   feed, which registry — and whether an attacker can move it within one transaction or one block.
2. **Measure the source, live.** For a pool-derived value, read the reserves or liquidity at a
   pinned block:
   ```sh
   python3 <skill-dir>/scripts/bounty.py eth-call --rpc <url> --to <pool> --sig 'getReserves()'
   python3 <skill-dir>/scripts/bounty.py value --rpc <url> --address <pool> --token <token>
   ```
   Thin liquidity next to a large borrowing cap is the whole finding. A protocol that prices a
   $50M market off a pool with $200k of depth is exploitable regardless of how clean the code is,
   and several 2026 incidents were exactly this (a lending pool priced from a pool the attacker
   seeded, and a vault priced from manipulable Curve pool data).
3. **Compute the cost of moving it.** Swap fees both ways, price impact, the capital required, and
   whether that capital is available as a flash loan — check whether the asset actually has a
   flash-loan source with enough depth, and include that fee. If no flash loan exists, the capital
   requirement is real and changes the severity.
4. **Compute the extraction.** What the mispricing lets the attacker take: over-borrow, under-pay a
   liquidation, mint too many shares, redeem too many assets. Bound it by what the protocol holds
   (`value`) and by caps, debt ceilings and per-transaction limits that are **live**, not the
   defaults in source.
5. **Net it out.** Extraction minus manipulation cost minus fees minus slippage minus gas. State the
   number. If it is negative at today's liquidity but positive at a plausible size, say that, with
   both numbers — that is still a finding, and an honest one.
6. **Then look for the asymmetries that need no manipulation at all:**
   - Rounding that favours the caller on **both** legs of a round trip, repeated in a batch.
     A loop of favourable rounding is how a precision bug becomes a nine-figure loss.
   - A fee or spread applied on one side and not the other.
   - Self-liquidation, self-borrowing or self-referral that is profitable.
   - Donation/inflation: a first depositor or direct transfer that moves the share price so later
     small deposits round to zero, or an attacker's share price is inflated before redeeming.
   - Liquidation that is not profitable to perform, leaving bad debt nobody clears.
   - Reward accrual that can be claimed twice, or claimed for a period not held.
   - Funding, interest or emission rates computed from a value the beneficiary influences.
7. **Check incentive reachability.** Who else must act for the attack to work — a liquidator, a
   keeper, an arbitrageur — and do they have a reason to? An attack that needs a rational third
   party to behave irrationally is weaker; an attack that *pays* a third party to help is stronger.

## Proof standard

Numbers, with their source and block. "The attacker profits" is not a claim, it is a placeholder.
Give: capital required and where it comes from, cost of manipulation, gross extraction, net profit,
and the live values you read to compute each. A fork test at a pinned block that prints the
attacker's balance before and after is the strongest form of this evidence, and it is also the
cheapest to review.

State the limits honestly: liquidity changes, so a profit computed today is point-in-time evidence.
Say which input would have to change to make the attack unprofitable.
