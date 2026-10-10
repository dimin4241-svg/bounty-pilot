# Project and stack adapters

The core hunt is stack-neutral only at the level of questions: who can act, what state changes,
which invariant breaks, and what evidence proves impact. Execution details are stack-specific.
Select an adapter from manifests, build files, deployment artifacts and source; do not infer it
from one file extension. If a project mixes stacks, route each component separately and add a seam
pass across their trust boundary.

## Native adapter procedures

Read the matching files in `adapters/`: `rust-native.md`, `rust-solana.md`,
`rust-cosmwasm.md`, `move.md`, `cairo.md`, `go.md`, or `web-backend.md`.
Do this **in addition to** the basic workflow, not instead of scope, evidence and triage.
A Cargo.toml alone does not mean Solana: distinguish the exact VM/framework and mixed
native worker crates. When a repository has multiple runtimes, run targeted checks
for each and add `semantic-mismatch` and `recovery-failure` across the boundary.

## Built-in routing

| Component | Read | Emphasize | Evidence path |
| --- | --- | --- | --- |
| Solidity / EVM | `lenses.md`, EVM agent lenses, compiler and deployment artifacts | storage/accounting, callbacks, token semantics, proxy/facet/clone implementation, chain configuration | Foundry/Hardhat tests, Slither triage, explicit stateful invariants with Echidna/Medusa, local fork and pinned read-only RPC; see `integrations.md` |
| Rust / Solana / Anchor | `lenses.md`, `anchor-account-agent.md` | signer and owner constraints, PDA seeds/bump, account substitution, CPI privileges, writable aliases, token program IDs, rent/close authority | Anchor tests or local validator with adversarial account substitutions; Trident fuzzing when a compatible project harness and properties exist |
| Move | `lenses.md` and this core workflow | abilities, resource ownership, friend/module visibility, object/shared-object authority, transaction ordering | Aptos/Sui Move tests; Aptos Move Prover only for supported specifications and runtime; name the exact VM/runtime |
| Cairo / Starknet | `lenses.md` and this core workflow | caller/storage context, L1↔L2 message authentication, replay/consumption, upgrade and class-hash transitions | Cairo tests and local devnet; verify the deployed class hash |
| CosmWasm | this core workflow plus Rust/wasm procedures | message authorization, reply/submessage behavior, funds attached to execute, migration, chain-specific bank/staking messages | `cw-multi-test` plus chain-specific integration tests |
| Off-chain service or keeper | this core workflow plus the language's available analyzers | authentication, job retries/idempotency, queue ordering, reorgs, stale reads, signing boundary, reconciliation and failure recovery | integration tests with adversarial RPC/service responses; never use production credentials |

This table is routing guidance, not a claim that every feature has a complete specialist lens. If a
stack lacks a built-in lens, say so in `coverage.md`, identify the closest available tools from the
repository's own manifests/documentation, and keep the result at `needs-evidence` until a native
test or equivalent runtime experiment supports it. Do not silently translate EVM assumptions to
another VM.

Never install or run a fuzzer just to claim tool coverage. Check the target's pinned toolchain and
existing test harness first. A fuzzer without a meaningful invariant may produce lots of execution
without testing a security property; write the property and the expected counterexample down before
starting a campaign. Record the actual command, duration/budget, result and uncovered constraints.

## Build a component and boundary map

Before hunting, enumerate components from the repository tree and manifests. Include source,
contracts/programs, generated interfaces, deployment scripts, IDLs/ABIs, migrations, CI workflows,
configuration, and off-chain services that submit, sign, relay, index, settle or recover protocol
operations. Record how each component calls or trusts the next one. Treat generated files as a clue
to runtime shape; trace them back to their source and actual deployed version.

For each component, make a small boundary table:

| Caller / input | Trust check | State or value changed | External dependency | Failure / retry behavior |
| --- | --- | --- | --- | --- |

Then trace at least one complete path from an untrusted input to a protected state/value change and
one path from an external failure to retry or recovery. Mark missing links explicitly. A contract
finding may depend on an off-chain signer; an API flaw may be gated by an on-chain verifier. Hunt
the composed mechanism, not just one repository folder.

## Cross-stack invariants

Use these questions in every ecosystem, then translate them into the native runtime semantics:

- **Authority:** who can invoke, sign, upgrade, initialize, relay or recover, and what concrete
  state proves that authority?
- **Identity and replay:** which chain, domain, account, nonce, message and version are bound to a
  signature or message, and where is consumption made durable?
- **Accounting:** which assets and liabilities change, in what units, with what rounding, and which
  later reader relies on the resulting state?
- **Ordering:** can retries, callbacks, competing users, delayed messages, reorgs or partial
  failures produce a different state than the happy path?
- **Availability:** can an untrusted party make a shared operation permanently or materially
  unavailable, and who pays the resource cost?
- **Upgrade and migration:** what state or authority changes across versions, and is old state still
  interpreted the same way?
- **Observability and reconciliation:** which component notices a missing, duplicate or malformed
  operation, and how long can it remain undetected?

Do not treat an untested path, unsupported stack, unavailable network or unread dependency as
refuted. Record the concrete next experiment or the exact blocker on every open lead. A useful lead
states: `question`, `method`, `expected_evidence`, and, when blocked, `blocker`.

## Configuration context in bundles

`bounty.py bundle` includes a bounded allowlist of common build manifests and deployment/config
files, while excluding test fixtures, environment files, keystores and credential-like paths. It
reports files omitted by the size budget. This is a starting context, not a complete inventory:
when scope depends on another file, pass it explicitly with `--include` and record why it matters.
Never assume a tracked deployment config equals production; establish that from an authoritative
source or mark it unknown.
