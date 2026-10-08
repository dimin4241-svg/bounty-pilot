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
