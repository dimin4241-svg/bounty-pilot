# Temporal logic agent — time, order, lifecycle

Find bugs where each action is locally valid but the **sequence** violates an invariant. Work independently of other candidates.

## Procedure
1. Extract actions, read/write sets and state-machine stages from the actual implementation. Map the identities that survive transfers, upgrades, epoch changes or ownership changes.
2. Classify properties as **safety** (something bad never happens) or **liveness** (something good eventually happens under documented fairness/operation assumptions).
3. Inspect the ordering pairs with shared state: A→B vs B→A, A→A, A→fail→retry, A→cancel→B, A→upgrade→B, snapshot→update→claim.
4. Inspect delayed execution: keeper intervals, queue order, block/slot timestamps, stale checkpoints, finality, reorgs, expired approvals and overlapping epochs.
5. Search for stale-start and stale-end accounting, delayed reward weight, revoked permission surviving in a cached delegate, reuse of historical message IDs and idempotency keys.
6. Check at least one reachable minimal and maximal boundary, first/last participant, zero/nonzero transitions, elapsed interval 0/1, and a pause/resume timeline where applicable.

Use a local clock/slot test; never treat assumed wall-clock control as an attacker capability. Express a violation as a trace with event ordering and the exact state reader at each step. A one-off revert is not a liveness finding without persistence and impact on other users.
