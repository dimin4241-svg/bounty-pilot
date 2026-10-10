# Adversarial composition agent — search the source graph, not only past leads

Unlike `seam`, which combines prior candidates, this lens independently discovers multi-step mechanisms even when no previous agent emitted a lead.

## Build a dependency graph
From **source**, for every critical operation collect state read/write sets, identity/authority, external calls and economic effects. Connect two operations when they touch one state, asset, message, right or callback. Follow connections across modules and languages; distinguish observed edges from inferred ones.

## Search
1. Start at payout, privilege change, liquidation, shared queue and irreversible state changes; work backwards to attacker-controlled entrypoints.
2. Generate bounded sequences of 2–5 actions (including two different actors), ranked by shared writes, low-frequency paths, missing tests and boundary crossings.
3. Test reorderings, repeated operations, stale snapshots, cancellation followed by execution, partial success followed by retry, and transfer/upgrade in the middle.
4. Challenge independent local correctness: A can preserve invariant X and B can preserve invariant X but A→B may not.
5. Do not assume every two linked functions can run consecutively: document per-step guards, capability, timestamps and reachable setup.
6. Cross-check any prior LEAD/refuted record *after* independent graph exploration; do not merely restate it.

Emit concise ordered traces with explicit source anchors and one native-runtime experiment. Treat combinatorial search as bounded prioritization, not a completeness proof.
