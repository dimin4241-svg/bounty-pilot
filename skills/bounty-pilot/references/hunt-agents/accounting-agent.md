# Accounting agent — every writer of every aggregate

Protocols keep summary state: `totalDebt`, `totalCollateral`, `totalSupply`, `totalAssets`,
`totalShares`, utilisation, caps, accrued fees, points. Other code makes solvency, cap and pricing
decisions from those numbers. **A mutator that moves value but forgets the aggregate breaks every
reader of it**, and this class survives audits because each function looks correct alone.

## Procedure — writer enumeration

1. List every aggregate: any storage variable whose value summarises other state, plus every cap or
   limit compared against one.
2. For each aggregate, list **every writer**, exhaustively, with grep rather than by reading the
   happy path: `+=`, `-=`, `=`, `delete`, struct assignment, and any library or inherited function
   that writes it.
3. Build the table: one row per state-changing entry point, one column per aggregate. Fill each cell
   with "increments", "decrements", "sets", or "does not touch".
4. **Hunt the holes.** Every entry point that moves the underlying asset or debt must appear in the
   column for the aggregate that summarises it. A blank cell where value moved is the bug. Check
   especially: redemption, liquidation, partial close, forced close, migration, emergency withdraw,
   rescue/sweep, and anything added after the audit.
5. For each hole, establish the consequence by finding the readers: which function compares the
   aggregate to a cap, divides by it, prices with it, or gates on it. The impact is the reader's
   behaviour, not the wrong number.
6. Check symmetry pairwise: deposit/withdraw, borrow/repay, open/close, stake/unstake, mint/burn,
   lock/unlock. One side rounding or updating differently from the other is a candidate.

## Where the money is

- An aggregate that only ever grows: the protocol slowly bricks the cap it is compared against, or
  slowly misprices everything derived from it. Permanent, worsening, unrecoverable without an
  upgrade — that profile is a real DoS finding even with no direct theft.
- Shares and assets converted in both directions, with rounding that favours the caller on both legs.
- Fees accrued into a variable that a second path also spends, so the same balance is promised twice.
- Loss or slash waterfalls: check that each tier actually reduces supply or principal rather than
  only reducing a derived price, or the same loss is absorbed twice.
- First and last actor: the first deposit into an empty pool and the withdrawal that empties it.
- Per-market generalisation where one aggregate stayed global.

## Proof standard

Name the aggregate, the mutator that skips it, the reader that consumes it, and a concrete sequence
with numbers that leaves the aggregate wrong. Then read the aggregate live on chain if the protocol
is deployed — an aggregate already visibly wrong on mainnet is the strongest evidence this lens
produces, and it costs one `eth-call`.
