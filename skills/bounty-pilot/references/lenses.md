# Audit lenses

For every lens produce a falsifiable hypothesis: entry point, attacker capability, preconditions, state transition, broken property, consequence, and experiment. Derive properties from actual protocol intent; do not paste a generic checklist as a finding.

## Solidity / EVM

- Access lifecycle: creation, initialization, ownership/role transfer, revocation, delegated permissions, callback authority, upgrade authority.
- Signed intent: signer, account, chain, nonce, deadline, action and parameter binding; compare quoted intent with actual execution order and recipient.
- Asset accounting: list each asset, actual balance, accounted balance, shares, debt, pending claims and every writer. Reconcile all branches. Separate user loss from protocol debt and harmless dust.
- Arithmetic: units, decimals, casts, rounding beneficiary, repeated operations, minimum nonzero values, first/last user and exhausted reserves.
- Time and cohorts: accrual before/after entry or exit, checkpoints, epoch rollover, expiry, cancellation and claim uniqueness.
- Solvency/liquidations: economic assumptions, price freshness, collateral/debt valuation, bad debt and liquidation reachability; establish feasible capital and liquidity.
- Integration: external call boundaries, hooks, read-only and cross-contract reentrancy, token behavior actually supported by the project, oracle trust, returndata and gas limits.
- Liveness: adversarially poisoned queues/batches, retry persistence, restart/recovery behavior, gas growth and griefing cost; measure victim impact and recovery paths.
- Cross-chain: message identity, domain/source binding, replay state, finality, retries, refund and compensation paths.

## Rust / Solana

Use Cargo/Anchor metadata to establish the program boundary and runtime. Inspect signer/writable/owner checks, PDA seeds and bump assumptions, account substitution, cross-program invocation authority, account lifecycle/close/reinitialization, arithmetic and token-program selection. Include Token-2022 extensions only when reachable under supported configuration. Demonstrate account constraints and actual runtime behavior in the appropriate local validator or test harness. Do not label an ordinary Rust panic a chain-wide halt.

For off-chain Rust inspect untrusted parsing, panic/abort boundaries, persistence/retry state, resource growth, synchronization and unsafe code. Keep chain/runtime semantics explicit.

## Other languages

Build a language-specific model from primary documentation and available tools. State that the package has no specialized built-in checklist for that stack. Do not reuse EVM assumptions for Move, CosmWasm, TON or native bridges. Use language-specific upstream skills only after inspecting compatibility.
