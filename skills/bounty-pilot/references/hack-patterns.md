# What has actually been exploited

A reading list of root causes that took real money, each with the shape to grep for. Use it to aim
lenses and to argue severity: a mechanism with a named precedent is much harder for triage to call
theoretical.

**Read the caveats.** Loss figures differ between trackers, and attributions get revised when
post-mortems land — treat every number here as approximate and cite the protocol's own post-mortem
in a report, never this file. This is a pattern library, not a source of record.

## The distribution matters more than any single entry

Across 2025–2026, **the largest losses were not broken Solidity.** Vendor tallies put the majority
of 2026 losses on stolen keys, compromised infrastructure and social engineering — the Bybit theft
(~$1.4B, the largest ever) came from a supply-chain compromise of a third-party multisig front end,
and several nine-figure 2026 incidents started with a socially engineered developer.

Two consequences for a hunter:

1. **Most contract-level money is in mid-size protocols**, not in the headline numbers. Do not
   calibrate your expectations on the biggest incidents; they are not bugs you can find by reading
   code.
2. **Many programs include web, API and infrastructure scope** with real payouts and far fewer
   competent competitors than the contract scope. Read the program's full scope before assuming it
   is a Solidity-only hunt.

## Access control and initialization

Measurably the hardest category for automated reviewers, and consistently the most expensive.

- **Config value that makes a guard vacuous.** Nomad bridge (~$190M, 2022): an upgrade left the
  trusted root at zero, so any forged proof verified. Grep: a guard comparing against a settable
  address/root/hash, and read it live — zero or default accepted is the finding.
- **Uninitialised implementation.** Parity multisig (2017, ~500k ETH frozen): a library left
  uninitialised, then destroyed. Still shipping today as UUPS implementations with no
  `_disableInitializers`.
- **Masquerading as another account.** Balancer v2 (~$120M, Nov 2025): an access-control flaw let
  the attacker act as the owner of any account inside a pool, combined with a rounding error that
  moved the invariant. Two ordinary-looking defects, composed.
- **Role reachable through a message.** Poly Network (~$611M, 2021): a crafted cross-chain message
  changed the keeper role.
- **Governance by spot balance.** Beanstalk (~$182M, 2022): flash-loaned voting power executed a
  malicious proposal in one transaction.
- **Supply-cap and limit bypass.** Venus (~$3.7M, 2026): a supply cap that could be stepped around.
  Caps are guards; attack them like guards.

→ Lens: `privileged-path`, `upgrade`.

## Arbitrary external call plus standing approvals

The most *repeated* production bug of the last few years, because every aggregator reinvents it.

- Routers and bridge adapters that take a target and calldata from the caller: LI.FI (2022 and
  again 2024), Socket (~$3.3M, 2024), and a long tail of zappers and swap helpers. Users' standing
  approvals are what turns a plumbing bug into a drain.
- Unconstrained `delegatecall`, including to a settable library or a registry-loaded module.
- Munchables (~$62M, 2024) is the insider variant: an upgradeable contract whose storage was
  pre-set so the "upgrade" handed over control.

→ Lens: `external-call`, `privileged-path`.

## Cross-chain and message verification

- **Verifying the envelope, not the contents.** Verus–Ethereum bridge (~$11.6M, 2026): the notarised
  state root and proofs verified correctly, but nothing checked that the stated transfer amount
  matched the payout. Same family: Wormhole (~$326M, 2022), where signature verification was
  bypassed by passing an unvalidated account.
- **Authenticating the messenger instead of the message.** A handler checks `msg.sender == endpoint`
  and then trusts a sender field that travelled inside the attacker's payload. The permissionless
  compose/queue mechanisms of modern messaging layers make the `msg.sender` check worthless for
  identity — read the framework's own source to learn who may make it call you.
- **Bridge infrastructure rather than bridge contracts.** KelpDAO (~$292M, 2026) involved a
  compromised messaging RPC. Out of contract scope, in scope on some programs.

→ Lens: `integration-auth`.

## Oracles and economic feasibility

- **Pricing off a pool the attacker can move.** Mango Markets (~$115M, 2022), Rhea Finance (~$7.6M,
  2026, oracle manipulated with seeded liquidity), Makina (~$4.1M, 2026, flash-loaned manipulation
  of Curve pool data). The code often looks fine; the finding is the *ratio* between pool depth and
  position cap, which only live data shows.
- **Read-only reentrancy into a price.** Sentiment (2023): a view function read mid-operation by a
  third protocol returned a broken value.
- **A constant that selects the wrong feed.** A hardcoded asset index or feed id that names one
  asset and selects another. Invisible in source review; one live read settles it.
- **Stale or fallback behaviour** is usually in the program's known-issues list — check before
  spending a pass on it.

→ Lens: `economics`, `live-reality`.

## Arithmetic, precision and compiler

- **Math-library overflow.** Cetus on Sui (~$223M, 2025): an overflow in the concentrated-liquidity
  math library. KyberSwap (~$48M, 2023): an intricate tick/precision edge in concentrated liquidity.
  Tick math, bit shifts, fixed-point helpers and curve invariants are where the big numbers live.
- **Rounding that favours the caller on both legs, amplified by batching.** The Balancer v2 (2025)
  invariant manipulation; also the whole family of share-price and exchange-rate round trips.
- **Donation / inflation attacks.** Direct transfers that move a share price so later deposits round
  to zero, or an attacker's shares inflate before redemption. ERC-4626 vaults, cToken-style markets,
  empty-market first depositors.
- **Compiler bugs are a real finding class.** Curve (~$70M, 2023): a malfunctioning reentrancy guard
  in specific Vyper versions. Truebit (~$26M, 2026): an **old contract compiled with an old Solidity
  version lacking overflow checks**, letting a price be pushed to near zero. Both are found by
  checking the compiler version, not by reading the contract:
  ```sh
  python3 <skill-dir>/scripts/bounty.py solc-bugs --repo <checkout>
  ```

→ Lens: `economics`, `accounting`, plus the `solc-bugs` check in stage 1.

## Logic added later that breaks logic written earlier

- Euler (~$197M, 2023): a donate function, added later, broke an invariant the liquidation path
  depended on. Neither function is wrong alone.
- Penpie (~$27M, 2024): an attacker-registered market reached a reward path that trusted registry
  entries.
- Hundred Finance and the empty-market family: a market in a state the original design never had.

→ Lens: `delta`, `seam`, `accounting`.

## Solana and non-EVM account models

- Wormhole (2022) and Cashio (~$52M, 2022): a passed account whose owner, mint or type was never
  validated, so forged state was accepted — the "infinite mint" shape.
- Crema Finance (2022): a fake tick account supplied to a real instruction.
- Cetus (2025) is the Move/Sui reminder that non-EVM runtimes have their own arithmetic surface.

→ Lens: `anchor-account`, `economics`.

## How to use this file

Pick the two or three classes that match the target's shape, run the corresponding lenses first, and
when you find something, check this file for the precedent — then write the precedent into the
report's impact section. "This is the Nomad class of defect" tells a triage engineer in six words
why the severity you claimed is the right one.

Do not cite a precedent you have not checked, and never imply a protocol was hacked when it was not.
