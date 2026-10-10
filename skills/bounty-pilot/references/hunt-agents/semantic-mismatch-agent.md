# Semantic mismatch agent — two components disagree about one fact

Find defects at **boundaries** where two implementations interpret the same value differently. Independently inspect source at both ends of the interface.

1. Build the end-to-end trust graph for frontend → API → signer → keeper/relayer → RPC → contract/program, as applicable. Identify which representation is authoritative.
2. Trace identity fields (actor, asset, recipient, chain, message, nonce, epoch, version) and validate **binding** at every boundary. A signature authorizing a quote need not authorize the executed command unless parameters are bound.
3. Compare wire encodings and number ranges: JSON/JS safe integers, bigint, ethers, Rust serde, decimals, token units, negative values, canonicalization, Unicode, bytes32 padding, hash domain separation, little/big endian.
4. Trace success and failure semantics: HTTP 200 vs operation completed, transaction submitted vs finalized, event observed vs state committed, at-least-once delivery vs exactly-once consumer, client timeout vs transaction success.
5. Probe mismatch scenarios with a cross-language round-trip test and negative control using the **actual libraries** and configurations. Avoid imaginary behavior inferred from function names.
6. Emit an end-to-end path, each side's exact interpretation, reachable attacker input, broken invariant, affected downstream decision, and smallest decisive integration test.

Never extrapolate an EVM rule to Move, Solana or off-chain workers. If one component is missing, preserve a LEAD with the missing source as blocker.
