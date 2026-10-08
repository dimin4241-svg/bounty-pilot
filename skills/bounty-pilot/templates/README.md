# PoC templates

Copy a template into the **private run directory**, never into the target repository, and fill it in.
Every template is built around the four things `evidence.md` requires and a reviewer looks for:

1. **Unmodified production source.** Import or fork the real contracts. If you must change anything
   to make the exploit work, the exploit does not exist yet — record the change as a limitation.
2. **An assertion on the violated property**, not on a revert. `vm.expectRevert` proves a revert
   happened; it does not prove a vulnerability. State the property in the assertion message.
3. **A negative control** in the same file: the same sequence with the one attacker capability
   removed, or against the fixed code, showing the property holds. Without it, a reviewer cannot
   tell your harness from your finding.
4. **A pinned environment.** A fork test without a pinned block is not reproducible; it will behave
   differently next week and a triage engineer will not be able to reproduce it at all.

No private keys, no mainnet transactions, no broadcast. Use `vm.prank`, impersonation and local
forks. Read the program's rules before any network interaction.

| Template | Use for |
| --- | --- |
| `ForkPoC.t.sol` | a deployed EVM protocol, exploited against live state at a pinned block |
| `LocalPoC.t.sol` | a source-level finding on code that is not deployed, or needs a built-up state |
| `Invariant.t.sol` | a property that breaks under some sequence you cannot name by hand |
| `anchor_poc.rs` | a Solana program, account substitution and PDA findings |
