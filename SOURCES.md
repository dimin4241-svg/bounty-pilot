# Sources and optional integrations

Bounty Pilot's workflow text, lens agents and Python helpers are original to this repository. It
does not redistribute, vendor or merge any upstream skill files.

The multi-pass structure — independent parallel lens agents, a pass fed with what earlier passes
already found, and dedup on a surface-plus-bug-class key — was informed by studying
`pashov/skills`' `solidity-auditor`. `skills/bounty-pilot/references/compare.md` states what that
package does better, what it is not built to do, and how to run the two together. The lens set here
is deliberately aimed at different axes (time, lineage, observability, aggregates, parameter
authorization, persistence, live chain truth, the Solana account model) so the two are additive
rather than redundant.

- Pashov skills — https://github.com/pashov/skills — `solidity-auditor` (Solidity bug-class sweep),
  `x-ray` (readiness and threat modelling), `fizz` (Echidna/Medusa invariant suites).
- Trail of Bits skills — https://github.com/trailofbits/skills — differential and variant analysis,
  verification, property tests.
- 0xSimao AI — https://github.com/0xsimao/0xsimao-ai — accounting-focused review.
- QuillShield — https://github.com/quillai-network/quillshield_skills — semantic guards, invariants.
- Sanbir — https://github.com/sanbir/solidity-auditor-skills — complementary EVM checks; overlaps
  with Pashov.

No upstream version is bundled, and none is claimed to have executed. A runtime integration must
record the reviewed commit in `integrations.json` in the private run and retain upstream licensing.
Bounty Pilot's MIT licence applies only to original content here. Linked projects are not affiliated
with this one and do not endorse it.
