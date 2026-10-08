# Optional upstream integrations

Bounty Pilot is original orchestration with built-in lenses. It does not vendor or automatically install the projects below. Their presence is optional; no performance improvement has been established by a comparative benchmark.

| Upstream | Selected contribution | Repository |
| --- | --- | --- |
| Pashov | x-ray preparation, solidity-auditor discovery, fizz fuzz harness design | https://github.com/pashov/skills |
| Trail of Bits | differential-review, variant-analysis, fp-check, property-based-testing, spec-to-code-compliance | https://github.com/trailofbits/skills |
| 0xSimao | Independent accounting-focused review | https://github.com/0xsimao/0xsimao-ai |
| QuillShield | Targeted semantic guards, invariants and integration checks | https://github.com/quillai-network/quillshield_skills |
| Sanbir | Optional additional EVM vectors, overlapping with Pashov | https://github.com/sanbir/solidity-auditor-skills |

When requested or already installed:
1. Inspect upstream SKILL.md, scripts, license and runtime requirements. Record exact commit and selected module in integrations.json in the private run. Do not execute fetched install scripts blindly.
2. Install into the runtime's documented skill/plugin location, with distinct names to prevent same-name collisions. Do not copy a fork's solidity-auditor over another installation. Pin a reviewed commit for reproducible runs; updates require a new review and recorded revision.
3. Delegate a bounded task, not the entire orchestration. Do not nest full multi-pass orchestrators: this multiplies work and confounds coverage. Pass upstream modules the same target revision and scope.
4. Normalize their candidates into findings.json. Treat scores, severity and textual PoCs as hypotheses until local evidence meets this workflow's gates.
5. Record module availability, actual invocation and failures. Fall back to the corresponding built-in lens if unavailable and disclose the fallback.

Respect each upstream's license for redistribution. The MIT license of this original package does not relicense upstream content. No upstream source or skills are bundled; linked projects are not endorsers.
