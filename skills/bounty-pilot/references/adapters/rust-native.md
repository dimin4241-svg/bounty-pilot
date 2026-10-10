# Native Rust adapter (off-chain, non-Solana)

Establish crate graph and runtime from Cargo.lock, Cargo.toml, feature flags, target triple, panic profile, services and deployment manifests. Do not use Solana-specific account rules.

- Trace untrusted ingress (RPC/HTTP, websocket, bridge event, DB, file, peer message) through parsing, validation, queueing, state mutation, signing and durable acknowledgement.
- Investigate `unwrap`/`expect`/`panic!` on attacker-influenced values, but prove **blast radius** (task-local vs process-wide), restart behavior, and other-user impact before calling it DoS.
- Check `tokio::spawn`, `select!`, cancellation, channel bounds, timers, retries, semaphore permits, locks across await, ordering, stale caches and DB transaction boundaries.
- Check numeric casts, serde defaults/aliases, enum unknown variants, `checked_*`, `wrapping_*`, BigInt conversions and cross-language precision.
- `unsafe`, FFI and `Send`/`Sync` require actual soundness analysis; do not flag keyword presence as exploit.
- Native experiments: cargo test; cargo fuzz for explicit properties, Loom for concurrent interleavings, Miri for supported UB checks, Kani for bounded proofs when project/toolchain supports them.
- Compare 1) normal input 2) attacker-controlled boundary input 3) retry/restart negative control. Avoid production credentials and network load. Record blocked toolchain capabilities.
