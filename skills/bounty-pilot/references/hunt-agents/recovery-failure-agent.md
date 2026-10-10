# Recovery / failure agent — durable misbehavior across retries

This lens applies especially to bridges, indexers, oracles, watchers, signers, payment processors, keepers and relayers, including off-chain Rust, Go, JS and Python.

## Procedure
1. Map input acceptance → validation → external read → decision → side effect → durable acknowledgement. Identify persistence *before and after* every side effect.
2. Enumerate all retries and restarts: process exception/panic/abort, RPC timeout, partial batch, database rollback, duplicated webhook/event, reorg, out-of-order delivery, poison item, saturated queue and manual replay.
3. Ask whether one attacker-supplied but valid record can repeatedly crash a shared worker before its cursor or dedup marker advances. Confirm bounds, retry policy, dead-letter handling and independent consumer recovery.
4. Trace numeric/serialization boundaries across systems: JS safe integers vs Solidity uint/int vs Rust checked/wrapping integers, BigNumber conversion, JSON number precision, floating-point and string normalization.
5. For each scenario, measure scope (one item vs entire worker/batch), attacker cost, restoration paths, persistence across 2+ restarts, and who else is affected. Record the assumptions of liveness.
6. Compare happy-path success and fault-injection negative control. Use hermetic test harnesses; never flood real infrastructure or use production signing keys.

Output one minimal state/input sequence plus the failing checkpoint, observed persistence and a concrete experiment. Off-chain process crash ≠ chain-wide halt; don't inflate impact.
