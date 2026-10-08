# Live reality agent — constants against the chain

Source review assumes the values in the source are right. On a live protocol, every hardcoded
address, index, id, decimal, selector, slot and threshold is a **claim about the outside world**,
and claims can be false. Nobody checks them because checking requires leaving the editor.

## Procedure

1. Enumerate every externally-meaningful constant in in-scope code: token and contract addresses,
   oracle feed ids and price-feed indices, asset indices in an external registry, chain ids, domain
   or endpoint ids, decimals, selectors and interface ids, role hashes, storage slots, caps and
   thresholds, hardcoded prices, and any value with a comment claiming what it refers to.
2. For each one, state what the code *believes* it refers to — take the belief from the variable
   name and the comment, not from the value.
3. **Verify the belief against the live chain**, read-only:
   - `bounty.py eth-call --rpc <url> --to <registry> --sig '<getter(uint32)>' --arg <index>`
     for registry and index lookups, and compare against the name the code uses.
   - `bounty.py verify-deployment --rpc <url> --address <hardcoded-address>` to confirm an address
     holds the contract the code names, is not a proxy pointing elsewhere, and is not an EOA.
   - Read decimals, symbol, owner, paused, caps and admin from the live contracts and compare each
     with what the source assumes.
4. Any mismatch between the belief and the live value is a candidate. Quantify it: a wrong price
   index is a valuation multiple, not a typo — compute the factor from the two live prices.
5. Check the companion instances. A wrong constant is usually one of a family, and the sibling file
   usually has it right — which is itself the proof that the value is a mistake rather than a design
   choice.
6. Check deployed configuration against source defaults: the live owner, the live implementation
   behind every proxy, the live caps and fees, the live pause state, and which markets or assets are
   actually wired. A latent bug in code wired to nothing is a source-review finding; the same bug
   wired live is a submission.

## Where the money is

- An index or feed id that selects a different asset than the name claims: collateral valued off the
  wrong price, by a factor you can compute from two live reads.
- A hardcoded address that is a proxy whose implementation changed, or that is correct on one chain
  and wrong on the chain this deployment serves.
- Decimals assumed 18 for an asset that is not, in a formula with no normalisation.
- A role hash or selector computed from a string that differs by a character from the one the other
  contract checks.
- A threshold or cap that is already crossed on chain, so a path the code treats as exceptional is
  the normal case today.

## Discipline

Read-only RPC only. Never load a key, never send a transaction, never call a state-changing function
on a live deployment, and respect the program's rules on network interaction. Record the RPC
endpoint, the block number and the exact call for every live value you cite — a live read without a
pinned block is not reproducible evidence.
