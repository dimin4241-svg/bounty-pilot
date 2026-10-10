# Rust Solana / Anchor adapter

Native semantics are transaction atomicity and account-parameter trust; an instruction panic alone rolls back its own transaction and does not halt the chain.

Enumerate every instruction's signer/writable/owner/executable constraints, PDA seeds and bump, account address/authority binding, reinit/close/realloc, CPI signer seeds, program IDs, Token-2022 extensions and delegate lifecycles. Check remaining_accounts and raw AccountInfo independently of typed wrappers. Construct swapped-but-valid accounts in a local validator, LiteSVM or Mollusk, then test a correct-account negative control. For each multi-instruction scenario trace the exact account state and rights after each successful transaction. Include transaction ordering, slot/epoch behavior and off-chain bots as a separate native-Rust boundary. Use Trident/property fuzzing when a compatible harness exists; do not translate Solidity reentrancy or EVM storage assumptions.
