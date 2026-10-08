# Anchor / Solana account agent

On Solana the vulnerability is rarely in the arithmetic; it is in **which account the instruction
was handed**. The caller supplies every account, and anything the program does not constrain, it
trusts. Hunt the constraint set, not the function body.

## Procedure

1. Establish the boundary from the manifests: `Cargo.toml`, `Anchor.toml`, declared program ids, the
   IDL if one is published, and which instructions are reachable by an unprivileged signer. Pull the
   on-chain IDL when the program is deployed; a published IDL that differs from the repo is itself a
   finding candidate about which code is live.
2. For every instruction, tabulate each account: expected owner program, `signer` or not, `mut` or
   not, PDA seeds and bump, and whether the type is a checked account wrapper or a raw
   `AccountInfo`/`UncheckedAccount`. Note every account with no constraint at all.
3. **Hunt account substitution.** For each unconstrained or weakly constrained account, ask what
   passing a different-but-valid account of the same shape achieves: another user's position, another
   market's config, a vault belonging to a different mint, a stale copy, an account the attacker
   created and fully controls. Deserialising successfully is not a check.
4. **Hunt the PDA seeds.** Are the seeds sufficient to make the address unique per thing it
   represents? A missing seed component merges two logical accounts. A user-controlled seed string
   with no delimiter allows a collision between distinct seed tuples. Is the bump canonical and
   verified, or taken from the caller?
5. **Hunt authority.** For CPI: which signer seeds are passed, and does the program sign with an
   authority broader than the action requires? Is the token program id checked, or can a fake
   token program be supplied? Is the mint of a token account verified against the market's mint?
   Is `token_interface` used in a way that admits unintended Token-2022 extensions?
6. **Hunt lifecycle.** Close and reinitialise: does closing zero the discriminator and drain
   lamports, can a closed account be revived with stale data, can an account be initialised twice,
   can an attacker pre-create an account the program expects to create? Check `realloc` and manual
   lamport moves for rent exemption and for data left over from the previous size.
7. **Hunt the economics of the sysvar and the clock**: anything decided by slot, timestamp or
   recent blockhash that an attacker can position against.

## Where the money is

- A vault or fee account passed in, not derived, so profits route to an attacker-controlled address.
- A config or global account not pinned by seeds, letting one market's parameters govern another.
- A position account whose owner field is read for authorization but never compared to a signer.
- Shared state initialised per-user where a seed component is missing, so two users collide.
- A crank or permissionless instruction that moves funds and takes the destination as an argument.

## Proof standard

Demonstrate in a local harness — `solana-program-test`, `litesvm` or `anchor test` against a local
validator — not in prose. Construct the substituted account explicitly, show the instruction
succeeding, and show the resulting state. A Rust panic is a failed transaction, not a chain halt:
describe impact in terms of what the succeeding transaction took or broke.
