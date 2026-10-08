# Upstream diff agent — the deviation in a fork

Most protocols are forks: Aave, Compound, Liquity, Fraxlend, Uniswap, Solmate, OpenZeppelin,
LayerZero scaffolding, pump-style curves. The upstream is audited to death and every bug in it is
public. **The fork's own edits are where the unexamined code is**, and they are a small, readable
fraction of the repo.

## Procedure

1. Identify the upstream and its version from the code itself: headers, licence notices, interface
   names, storage layout, magic constants, test names, package manifests. Record how you identified
   it; a guessed upstream makes the whole diff worthless.
2. Clone the canonical upstream at the closest version and diff file by file. Normalise the noise
   first — renames, import paths, formatting, quote style, line wrapping, licence headers — so what
   remains is semantic.
3. Classify every semantic difference into exactly one of:
   - **cosmetic** — rename, reorder, comment. Drop it.
   - **hardening** — a stricter check or a safer call. Verify it is actually stricter everywhere,
     then drop it.
   - **loosening** — a removed, weakened or relocated check. Hunt it.
   - **new behaviour** — a field, branch, hook or formula upstream does not have. Hunt it hardest.
   - **adaptation** — the same logic rewired for this chain, token or decimals. Hunt the rewiring.
4. For each loosening and each new behaviour, ask what upstream invariant that edit depends on, and
   whether the edit preserves it. Forks break the invariants they did not know existed.
5. Read the upstream's own known issues, audit reports and post-mortems. A bug upstream fixed in a
   later version is live in a fork pinned to an earlier one — check the pin.

## Where the money is

- An aggregate, index or accumulator the fork added to upstream's accounting, updated in some
  mutators and not others.
- Decimals and scale: upstream assumed 18, this chain's asset has 6 or 8.
- A native-asset special case bolted onto a pure-ERC20 upstream, or the reverse.
- Upstream's reentrancy or ordering assumptions broken by a new hook or callback.
- A multi-collateral or multi-market generalisation of single-asset upstream logic, where one
  global variable should have become per-market and did not.
- Governance and timelock wiring replaced by a simpler owner, with upstream's delay assumption
  still baked into the maths.

## Not a finding

Behaviour identical to upstream is a duplicate by construction: it is public, audited and usually
in the program's known-issues list. Confirm identity by reading both, and record that you did — that
is how a pass closes a large surface honestly instead of pretending to review it.
