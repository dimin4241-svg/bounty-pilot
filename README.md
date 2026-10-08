<p align="center">
  <img src="docs/assets/banner.svg" alt="Bounty Pilot — Web3 security, backed by evidence" width="100%">
</p>

<h1 align="center">Bounty Pilot</h1>
<p align="center"><strong>An AI agent skill for smart contract security audits and Web3 bug bounty research.</strong><br>Start with a repository. Investigate hypotheses. Build local evidence. Draft a private report.</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-6ee7b7?style=flat-square" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/focus-Solidity%20%2F%20EVM-67e8f9?style=flat-square" alt="Focus: Solidity / EVM">
  <img src="https://img.shields.io/badge/helpers-Python%203.9%2B-a5b4fc?style=flat-square" alt="Helpers: Python 3.9 or later">
  <a href="README.ru.md"><img src="https://img.shields.io/badge/docs-English%20%2F%20Русский-cbd5e1?style=flat-square" alt="Documentation in English and Russian"></a>
</p>

<p align="center"><strong>English</strong> · <a href="README.ru.md">Русский</a></p>
<p align="center"><a href="#quick-start">Quick start</a> · <a href="#what-you-get">Features</a> · <a href="#how-it-works">Workflow</a> · <a href="#integrations">Integrations</a> · <a href="#faq">FAQ</a></p>

---

## What is Bounty Pilot?

Bounty Pilot gives a coding agent a repeatable workflow for **Solidity/EVM audits, Rust/Solana review, local proof-of-concept validation, and bug bounty report preparation**. It keeps technical validity, severity, program eligibility, and known-issue checks separate.

**It is an agent skill, not a hosted scanner.** Your agent reads the instructions, inspects the target, runs available tools, and records evidence. The included Python helper organizes results and checks their structure; it does not discover or prove vulnerabilities by itself.

## Quick start

### 1. Give this to your coding agent

Replace `OWNER/TARGET` with the repository you want to review:

```text
Install https://github.com/dimin4241-svg/bounty-pilot
and run Bounty Pilot on https://github.com/OWNER/TARGET.
Read skills/bounty-pilot/SKILL.md and follow it.
Keep findings private. Explain results in English.
```

### 2. Reuse it for the next project

```text
Bounty Pilot: https://github.com/OWNER/TARGET
```

A bounty program URL is useful, but optional for starting source review. Without verified program rules or deployment information, submission eligibility remains **unknown**.

<details>
<summary><strong>Manual setup or an agent without skill auto-discovery</strong></summary>

Clone this repository and ask the agent to read the skill directly:

```sh
git clone https://github.com/dimin4241-svg/bounty-pilot.git
```

```text
Read /absolute/path/to/bounty-pilot/skills/bounty-pilot/SKILL.md
and use it to review my target repository.
```

Alternatively, copy `skills/bounty-pilot` into your agent's supported skills directory. Review changes before replacing an existing installation. Installation locations depend on the client and version.

</details>

## What you get

| Capability | Practical result |
| --- | --- |
| **Scope and revision tracking** | Records the code version, program boundaries and deployment uncertainty |
| **Three distinct review passes** | Investigates exposure, asset accounting and integration gaps |
| **Evidence requirements** | Requires a local PoC, observed result, negative control and source-integrity explanation for verified findings |
| **Reasoned verification** | Keeps unresolved candidates instead of dismissing them with unsupported objections |
| **Known-issue comparisons** | Compares root causes with public audits, issues and fixes |
| **Resumable findings** | Preserves hypotheses and rejection reasons; rechecks changed assumptions |
| **Private report drafts** | Produces English submission drafts without automatically sending or publishing them |

## How it works

| Stage | Main question | Output |
| --- | --- | --- |
| 1. Resolve | Which code and program are we reviewing? | Scope, revision and deployment status |
| 2. Model | What must remain true? | Asset flows, trust boundaries and invariants |
| 3. Investigate | Where could those properties break? | Distinct hypotheses and coverage notes |
| 4. Reproduce | Can the original source demonstrate the effect? | Local PoC, logs and negative control |
| 5. Verify | Is it reachable, material and eligible? | Separate technical and program judgments |
| 6. Report | What can we substantiate? | Private draft and explicit limitations |

The default budget is **up to three passes**. Independent bounded tasks may use up to four workers when supported; otherwise the workflow runs sequentially. There is no infinite loop or finding quota.

### Finding states

| State | Meaning |
| --- | --- |
| `hypothesis` | A mechanism worth investigating |
| `needs-evidence` | A concrete experiment or missing fact is still needed |
| `verified` | The workflow's technical evidence requirements are met; eligibility is assessed separately |
| `refuted` | A concrete protection, specification or test contradicts the claim |

## Requirements and coverage

- **Coding agent:** file access, repository access and a shell/test runner. Browsing helps verify program rules and public known issues.
- **Helper scripts:** Python 3.9+ and Git; no third-party Python dependencies.
- **Target tests:** the target's own toolchain, such as Foundry, Cargo or a local Solana harness.
- **Built-in focus:** Solidity/EVM, with a narrower Rust/Solana route. Other ecosystems require additional domain-specific guidance.
- **Language defaults:** Russian progress summaries, English report drafts. Request a different explanation language if preferred.

Designed as portable Markdown instructions; compatibility depends on the agent's available tools. A regular chat without execution tools cannot complete the same validation steps. Model/API usage is billed by your provider.

## Integrations

Use complementary modules when available. **None is bundled or downloaded automatically.** The built-in workflow works on its own.

| Project | Optional role |
| --- | --- |
| [Pashov Skills](https://github.com/pashov/skills) | Preparation, Solidity discovery and fuzz-harness design |
| [Trail of Bits Skills](https://github.com/trailofbits/skills) | Change review, variant analysis, false-positive checks and property tests |
| [0xSimao AI](https://github.com/0xsimao/0xsimao-ai) | Independent accounting-focused review |
| [QuillShield](https://github.com/quillai-network/quillshield_skills) | Targeted semantic guards and invariant checks |
| [Sanbir](https://github.com/sanbir/solidity-auditor-skills) | Additional EVM checks with overlap to Pashov |

Inspect and pin upstream revisions before use. Delegate bounded tasks instead of nesting full audit loops. See [integration instructions](skills/bounty-pilot/references/integrations.md) and [attribution](SOURCES.md).

## Files and helper commands

| File | Purpose |
| --- | --- |
| [SKILL.md](skills/bounty-pilot/SKILL.md) | Agent entry point and orchestration |
| [Audit lenses](skills/bounty-pilot/references/lenses.md) | Stack-specific investigation prompts |
| [Evidence rules](skills/bounty-pilot/references/evidence.md) | Candidate records and verification gates |
| [Report template](skills/bounty-pilot/references/report.md) | English report structure |
| [bounty.py](skills/bounty-pilot/scripts/bounty.py) | Private run scaffolding and structural validation |
| [Tests](tests/test_bounty.py) | Helper regression checks |

```sh
# Use a new private directory outside both the target and the skill package.
python3 skills/bounty-pilot/scripts/bounty.py init \
  --repo /path/to/target --out /path/to/private/new-run

# Check record completeness and local artifact presence.
python3 skills/bounty-pilot/scripts/bounty.py check \
  --run /path/to/private/new-run

# Run helper tests.
python3 -m unittest discover -s tests -v
```

`init` does not clone, audit or execute the target. `check` does not verify exploit truth, severity, originality or payout eligibility. Even an empty finding list can pass its structural checks.

## FAQ

**Will it find more paid bugs?**  
That has not been established. There is no published comparative benchmark or payout guarantee. The aim is a more disciplined investigation and evidence process.

**Is this all the upstream skills merged together?**  
No. It is original orchestration and built-in guidance, with optional upstream integrations. Their source files and licenses are not repackaged as this project's own work.

**Can it rule out duplicates?**  
It can compare publicly disclosed issues. It cannot see private submissions or guarantee uniqueness.

**Does it submit or publish findings?**  
No. Results stay private unless the user explicitly authorizes a separate disclosure action.

## Contributing

Useful contributions include better ecosystem-specific lenses, clearer evidence requirements, reproducible helper fixes and synthetic test cases. Explain what changes and how you verified it. Do not include private source, credentials or undisclosed target vulnerabilities in issues or pull requests. Read [SECURITY.md](SECURITY.md).

## Responsible use and license

Review only authorized targets and follow program rules. Run PoCs locally in a secret-free environment; do not broadcast exploit transactions. No guarantee of coverage, validity, novelty or acceptance is made.

**[MIT licensed](LICENSE)** for original content. Upstream licenses remain separate. No affiliation with or endorsement by the linked projects is implied.
