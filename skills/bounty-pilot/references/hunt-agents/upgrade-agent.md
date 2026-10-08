# Upgrade agent — storage, initialization and the code behind the pointer

Upgradeable contracts carry a class of bug that does not exist in the source you are reading: the
bug is in the **relationship between two versions**, or between the proxy and the implementation.
Constructor and initialization errors are, with access control, the category automated reviewers
miss most — partly because the defect is invisible in any single file.

## Procedure

1. **Establish the pattern from the code, not the imports.** Transparent proxy, UUPS, beacon,
   minimal/clone, diamond (EIP-2535), or a hand-rolled `delegatecall` forwarder. Each has different
   failure modes, and a hand-rolled one has all of them.
2. **Read the live pointer.** `verify-deployment` resolves the EIP-1967 slots. Then ask the
   questions the source cannot answer: which implementation is live **now**, who can change it, is
   the admin an EOA, and does the implementation on chain match any artifact you can build?
3. **Attack the implementation directly.** It is a deployed contract with its own storage.
   - Is it initialised, or is its owner slot zero and its `initialize` callable by anyone?
   - Does it contain `selfdestruct`, or a `delegatecall` that an initialised attacker could aim —
     for a UUPS implementation, that is a path to bricking every proxy that points at it.
   - Does `_disableInitializers()` run in its constructor, or is that protection absent?
4. **Attack storage layout across versions.** Compare the current implementation's layout with the
   previous one if you can obtain it:
   - a variable inserted, removed or reordered above existing ones;
   - a type widened or narrowed so packing shifts (two `uint128` in one slot becoming `uint256`);
   - inheritance order changed, which moves every base's storage;
   - a `__gap` consumed without shrinking the gap;
   - a struct gaining a field while stored in a mapping or array;
   - a constant or immutable converted to a storage variable, or the reverse.
   The symptom is never a revert. It is one variable silently reading another's bytes — a balance
   that is a timestamp, an owner that is a fee.
5. **Attack the initialization sequence.** Multiple initializers across a base chain, one of which
   is never called. `reinitializer(n)` with a reused `n`. A migration function that is callable
   again. A setter that was supposed to run post-upgrade and did not — read the live value and see.
6. **Attack the diamond, if it is one.** Selector collisions between facets, a facet removable or
   replaceable by a path other than the intended one, `diamondCut` reachable from a loose role,
   shared storage structs with position strings that two facets compute differently.
7. **Attack the upgrade's assumptions.** A new version that changes the meaning of existing state
   without migrating it: units changed, a flag's polarity flipped, a mapping re-keyed, a rate
   rebased. Old rows keep the old meaning and the new code reads them with the new one.

## Where the money is

- An uninitialised implementation whose `initialize` anyone can call.
- A UUPS implementation with a reachable `delegatecall` or `selfdestruct` and no
  `_disableInitializers`.
- Storage collision after an upgrade that lands on an owner, a balance, a cap or a rate.
- An upgrade that left a required setter uncalled, leaving a guard comparing against zero.
- A proxy admin that is an EOA or a stale multisig — read the live admin slot, not the docs.
- A beacon whose owner differs from the protocol's stated governance.

## Proof standard

Storage findings are proven by layout, not by prose: give both layouts with slot numbers and name
the variable that now reads another's bytes. Initialization findings are proven by a live storage
read at a pinned block. If the previous implementation's source or layout is unavailable, say so and
mark the record `needs-evidence` — "the layout probably changed" is not a finding.
