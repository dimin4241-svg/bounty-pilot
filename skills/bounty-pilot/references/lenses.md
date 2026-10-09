# Audit lenses

Two kinds of lens, and they are used differently.

**Aimed lenses** live in `hunt-agents/` and are dispatched per pass by `passes.md`. Each is a
procedure over one axis — time, lineage, observability, aggregates, boundary authorization,
persistence, live truth, the Solana account model — and each produces falsifiable candidates.

**Classic bug-class lenses** are the list below: the standard sweep for well-known vulnerability
shapes. Select only the relevant ones; a generic checklist pasted into a report is not a finding.
On Solidity targets this sweep is exactly what `solidity-auditor` does in parallel and in depth, so
prefer delegating it when installed (see `compare.md`) and spend your own passes on the aimed
lenses it has no equivalent for.

For every lens, produce: entry point, attacker capability, preconditions, state transition, broken
property, consequence, experiment. Derive the property from the protocol's actual intent, read from
its docs, specs and tests — not from a template.

## Solidity / EVM

- **Access lifecycle:** creation, initialization, ownership and role transfer, revocation, delegated
  permissions, callback authority, upgrade authority.
- **Signed intent:** signer, account, chain, nonce, deadline, action and parameter binding; compare
  the quoted intent against the executed order and recipient.
- **Asset accounting:** per asset, the real balance, the accounted balance, shares, debt, pending
  claims and every writer; reconcile all branches; separate user loss from protocol debt from dust.
- **Arithmetic:** units, decimals, casts, rounding beneficiary, repeated operations, minimum nonzero
  values, the first and last user, exhausted reserves.
- **Time and cohorts:** accrual relative to entry and exit, checkpoints, epoch rollover, expiry,
  cancellation, claim uniqueness.
- **Solvency and liquidation:** economic assumptions, price freshness, collateral and debt
  valuation, bad debt, liquidation reachability, and the capital and liquidity actually required.
- **Integration:** external call boundaries, hooks, read-only and cross-contract reentrancy, the
  token behaviours the project really supports, oracle trust, returndata and gas limits.
- **Liveness:** poisoned queues and batches, retry persistence, restart and recovery, gas growth,
  griefing cost, victim impact and repair paths.
- **Cross-chain:** message identity, domain and source binding, replay state, finality, retries,
  refunds and compensation.

## Rust / Solana

Establish the program boundary and runtime from Cargo and Anchor metadata. Then work the account
model — signer, writable and owner checks, PDA seeds and bumps, account substitution, CPI authority,
account lifecycle, close and reinitialisation, arithmetic, token-program selection — with the
procedure in `hunt-agents/anchor-account-agent.md`. Include Token-2022 extensions only where they are
reachable in a supported configuration. Demonstrate account constraints and runtime behaviour in a
local validator or test harness. An ordinary Rust panic is a failed transaction, not a chain halt.

For off-chain Rust: untrusted parsing, panic and abort boundaries, persistence and retry state,
resource growth, synchronisation, and `unsafe`. Keep chain and runtime semantics explicit.

## Other languages

Route from `adapters.md`. Build the model from primary documentation and the project's own tooling,
and state plainly when this package has no specialised checklist for that stack. Do not carry EVM
assumptions into Move, CosmWasm, TON, Cairo or a native bridge. Use an ecosystem-specific upstream
skill only after checking its compatibility, and record which one ran. For a mixed repository, run
component-specific analysis and a separate cross-boundary pass.
