# Impact classes — what the payout is actually for

Programs do not pay for cleverness, for lines of analysis, or for the rarity of the bug. They pay
for the **impact class** the report establishes. The same root cause, written at two different
classes, is two different payouts — and only one of them is what the code actually does.

**The program's own rubric governs, always.** Read it, cite the clause in `severity_rationale`, and
use the table below only to decide which class to aim the evidence at. The classes below follow the
taxonomy most platforms converged on; a self-hosted program may name them differently or weight
them differently, and some exclude a class entirely.

## The ladder, highest first

| Class | What it means | What the evidence must show |
| --- | --- | --- |
| **Direct theft of funds** | Attacker ends with assets that were users' or the protocol's | The attacker's balance up and an identifiable victim's down, in one demonstrated sequence, net of fees and capital |
| **Permanent freezing of funds** | Assets cannot be withdrawn, ever, without an upgrade | Reachability, persistence, and that you read the recovery paths and they do not repair it |
| **Protocol insolvency** | Liabilities recorded exceed assets held | The accounting identity broken with numbers, and that the shortfall is realisable by someone |
| **Governance manipulation** | Voting, parameter or upgrade control reachable by the wrong actor | The unprivileged path to a decision the protocol treats as privileged |
| **Theft of unclaimed yield** | Rewards, fees or interest redirected before they are claimed | Whose yield, how much per period, who receives it instead |
| **Temporary freezing** | Funds locked for a bounded, material period | The duration, what unlocks it, and who is affected while it lasts |
| **Griefing** | Damage with no profit for the attacker | The one-time cost to the attacker, the blast radius, and that it is not self-harm |
| **Gas / resource exhaustion** | A path made unusably expensive or unbounded | Growth per element, who pays, and the point where it stops working |
| **Informational** | A real defect with no reachable harm today | Why it is latent, and the configuration change that would make it live |

## How to place a candidate

Work **upward**, and stop where the evidence stops.

1. Start at the harm you demonstrated, not the harm you can imagine.
2. Ask the escalation question: *what decision is made from the thing I broke?* A wrong aggregate
   is informational until you find the cap, the solvency check, the share conversion or the
   liquidation threshold that reads it — then it is a freeze or an insolvency.
3. Ask the persistence question: does it clear by itself, on the next block, with a keeper call,
   with an admin call you have read, or never? Temporary and permanent are often two classes apart,
   and "the team can upgrade" is not a recovery path on most rubrics.
4. Ask the victim question: is the loss the attacker's own (not a finding), a few users', or
   everyone's? Blast radius moves the class on many rubrics and the payout on nearly all.
5. Stop at the highest class you can defend **with the evidence in the record**, and write the next
   class up as the limitation: "this would be insolvency if X, which I did not establish."

Overclaiming and underclaiming are the same mistake made in opposite directions. Overclaiming gets
the whole report read with suspicion. Underclaiming gets it paid at the lower class, and nobody
will argue you upward.

## Where hunters routinely leave money

- **Filing a freeze as a revert.** "Function X reverts" is not a class. "Nobody can withdraw
  collateral from market Y until an upgrade" is.
- **Filing insolvency as an accounting bug.** Follow the broken identity to the actor who can
  realise the shortfall, and name them.
- **Filing theft as griefing** because the profit was not computed. Compute it: fees, capital,
  slippage, liquidity available.
- **Not counting the instances.** One callback missing authorization is one finding; the same
  pattern in five adapters is the same finding with five times the exposure, and severity is often
  argued on exposure.
- **Not checking whether it is already live.** A condition already visible on chain today is
  stronger than the same condition in theory, and it moves the conversation from "could" to "does".
- **Stopping at the first victim.** Check whether the loss is bounded to one position or scales
  with TVL.

## Classes most programs exclude

Do not spend a pass on these unless the rules say otherwise: MEV and sandwiching that the design
accepts, price-movement economics that need a large market move, centralisation and admin-key risk
with no mechanism, best-practice and gas-optimisation notes, missing events, compiler and linter
output, DDoS on UI/API/RPC infrastructure, and anything reachable only by a trusted role acting
against its own documented intent. Each of these is a real-sounding report that is rejected by rule,
not by judgment.
