# Optional upstream integrations

Bounty Pilot is original orchestration with built-in lenses. It does not vendor or automatically
install anything below, and no comparative benchmark establishes a performance claim for any
combination. `compare.md` holds the detailed comparison with `solidity-auditor` and the recommended
division of labour — read it before delegating a stage.

| Upstream | Selected contribution | Repository |
| --- | --- | --- |
| Pashov | `solidity-auditor` for the classic Solidity bug-class sweep, `x-ray` for readiness and threat modelling, `fizz` for invariant suites | https://github.com/pashov/skills |
| Trail of Bits | differential review, variant analysis, false-positive checking, property-based testing, spec-to-code compliance | https://github.com/trailofbits/skills |
| 0xSimao | independent accounting-focused review | https://github.com/0xsimao/0xsimao-ai |
| QuillShield | targeted semantic guards, invariants and integration checks | https://github.com/quillai-network/quillshield_skills |
| Sanbir | additional EVM vectors, overlapping with Pashov | https://github.com/sanbir/solidity-auditor-skills |
| claudit / Solodit | search publicly disclosed audit findings by class, surface and protocol | https://github.com/marchev/claudit |

For `claudit`, a Solodit API key and a configured MCP server are required. Use it only as a public
known-finding search: it cannot see a program's private queue. Search with a generic mechanism and
project identifier; never send private report text, unpublished exploit steps or target credentials.
Copy relevant public results into `dup-map.json` with the source and a mechanism comparison. A
result proposes a collision; it does not decide one.

## Stack-specific references

| Upstream | Use when | Limit |
| --- | --- | --- |
| OpenZeppelin Skills | The target uses OpenZeppelin contracts or upgrade tooling; check APIs and version-specific upgrade assumptions | Development guidance, not an auditor; inspect its AGPL-3.0 licence before redistribution |

https://github.com/OpenZeppelin/openzeppelin-skills

## Optional analysis and test tools

Choose a tool only when it fits the repository's pinned stack. Run it against the existing build
and tests where possible; first write the security property it is meant to check. A clean scanner
result is not proof of safety, and a fuzzer run without a meaningful property is not useful
coverage.

| Tool | Useful for | Keep in mind |
| --- | --- | --- |
| [Slither](https://github.com/crytic/slither) | Static triage and code-structure queries for Solidity/Vyper | AGPL-3.0; review findings against the exact build, since detectors are leads, not proofs |
| [Echidna](https://github.com/crytic/echidna) | ABI-driven stateful property fuzzing and Solidity assertions | Define invariants and realistic actor/state setup before the campaign |
| [Medusa](https://github.com/crytic/medusa) | Parallel, coverage-guided stateful EVM fuzzing | Pin the installed version and record campaign budget, corpus and result; AGPL-3.0 |
| [Crytic properties](https://github.com/crytic/properties) | Example properties for ERC-20, ERC-721, ERC-4626 and fixed-point math | Treat them as adaptable examples; confirm they match the protocol's intended semantics |
| [Trident](https://github.com/Ackee-Blockchain/trident) | Fuzzing Anchor/Solana programs with adversarial transaction sequences | Requires a compatible Anchor harness and properties; it is not a general Rust fuzzer |
| [Aptos Move Prover](https://aptos.dev/build/smart-contracts/prover) | Formal checks of supported Aptos Move specifications | Applies only where the actual chain/runtime and specifications support it; do not assume Sui compatibility |

When requested or already installed:

1. Inspect the upstream `SKILL.md`, its scripts, its licence and its runtime requirements. Record the
   exact commit and the selected module in `integrations.json` in the private run. Do not execute a
   fetched install script blindly.
2. Install into the runtime's documented skill location with distinct names, so a fork does not
   overwrite another installation of the same name. Pin a reviewed commit; an update needs a new
   review and a new recorded revision.
3. Delegate a **bounded stage**, not the whole orchestration, and never nest two multi-pass
   orchestrators — that multiplies cost and makes coverage unreadable. Pass the same target revision,
   the same scope and, where the upstream accepts context, the ranked surfaces and the dup map.
4. Normalise what comes back into `findings.json` as `hypothesis` records. An upstream's confidence
   score, severity label or textual PoC is not evidence under `evidence.md` and does not transfer.
5. Record availability, actual invocation and failures. If a module was unavailable, fall back to the
   corresponding built-in lens and disclose the fallback in the summary.

Respect each upstream's licence for redistribution. The MIT licence of this package covers only the
original content in this repository. Linked projects are not affiliated and do not endorse this one.
