<p align="center">
  <img src="docs/assets/banner.svg" alt="Bounty Pilot — Web3 security, backed by evidence" width="100%">
</p>

<h1 align="center">Bounty Pilot</h1>
<p align="center"><strong>An AI agent skill for smart contract security audits and Web3 bug bounty research.</strong><br>Start with a repository. Investigate hypotheses. Build local evidence. Draft a private report.</p>

<p align="center">
  <a href=".github/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/dimin4241-svg/bounty-pilot/tests.yml?branch=main&style=flat-square&label=tests" alt="Test status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-6ee7b7?style=flat-square" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/focus-Solidity%20%2F%20EVM-67e8f9?style=flat-square" alt="Focus: Solidity / EVM">
  <img src="https://img.shields.io/badge/helpers-Python%203.9%2B-a5b4fc?style=flat-square" alt="Helpers: Python 3.9 or later">
  <a href="README.ru.md"><img src="https://img.shields.io/badge/docs-English%20%2F%20Русский-cbd5e1?style=flat-square" alt="Documentation in English and Russian"></a>
</p>

<p align="center"><strong>English</strong> · <a href="README.ru.md">Русский</a></p>
<p align="center"><a href="#quick-start">Quick start</a> · <a href="#what-you-get">Features</a> · <a href="#how-it-works">Workflow</a> · <a href="#compared-with-solidity-auditor">Comparison</a> · <a href="#integrations">Integrations</a> · <a href="#faq">FAQ</a></p>

---

## What is Bounty Pilot?

Bounty Pilot gives a coding agent a repeatable workflow for **Solidity/EVM audits, Rust/Solana review, local proof-of-concept validation, and bug bounty report preparation**. It keeps technical validity, severity, program eligibility, and known-issue checks separate.

It has two halves, and both decide whether a hunt finds anything:

- A **funnel** that settles where to look and what counts as evidence — which target is worth the week, which code the last audit never saw, which surfaces are already burned by published known issues, and whether the bytecode on chain is the code you are reading.
- A **hunt** of nine aimed lenses, dispatched from assembled bundles over differentiated passes, where generation and refutation are deliberately separate steps: an agent that refutes itself while hunting finds less, and an agent that never refutes itself files reports that triage kills.
- A **two-round objection exchange** after the hunt, in which a triage agent is told to reject each finding and must anchor every objection in quoted code, quoted specification, a named test or a live chain read — and the answers must be anchored too. Both sides carry the same burden, because a one-round review rejects almost everything and you never learn which rejection was wrong.

**It is an agent skill, not a hosted scanner.** Your agent reads the instructions, inspects the target, runs available tools, and records evidence. The included Python helpers organize results, read live chain state and check structure; they do not discover or prove vulnerabilities by themselves.

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
| **Target triage** | Scores a program from churn since the audited revision, files never named in tests and published program economics — and lists its own unknowns instead of rounding up |
| **Post-audit delta** | Ranks non-test source changed since an exact audited commit, weighted by external calls, value movement, aggregate writes and callback entry points |
| **Duplicate map first** | Burns surfaces published in known-issue lists, past audits and contest findings *before* the first pass, then matches candidates against them mechanically |
| **Deployed-code verification** | Compares on-chain runtime bytecode with a local build, resolves EIP-1967/1822 proxy slots, pins one block per run, and separates `exact` from `partial` honestly |
| **Live-constant checks** | Reads a hardcoded index, address, decimal or feed id against live chain state, because a constant is a claim about the outside world |
| **Eight aimed lenses** | Hunts time, lineage, observability, aggregates, parameter authorization, persistence, live truth and the Solana account model |
| **Separated generation and refutation** | Hunt passes state claims at full strength; a later pass attacks each one against five written gates |
| **Evidence requirements** | A verified finding needs a local PoC, exit code, log, assertion, negative control and a source-integrity explanation |
| **Submission gate** | Refuses what programs actually reject: undeployed revision, unestablished scope, unassessed severity, no rubric citation, thin novelty check, unquantified impact |
| **Resumable findings** | Preserves hypotheses and rejection reasons; reopens a candidate when the protection that refuted it is edited |
| **Private report drafts** | Produces English submission drafts without automatically sending or publishing them |

## How it works

| Stage | Main question | Output |
| --- | --- | --- |
| 0. Triage | Is this target worth the week? | Priority score, reasons and unknowns |
| 1. Resolve | Which code, which program, and what is actually deployed? | Scope, revision, duplicate map, bytecode comparison |
| 2. Model | What must remain true, and what did the audit never see? | Invariants, trust boundaries, ranked delta |
| 3. Hunt | Where could those properties break? | Candidates, leads and recorded coverage |
| 4. Adjudicate | Can each claim survive an attack on it? | Five gates: interruption, reachability, trigger, harm, eligibility |
| 5. Verify | Does the original source demonstrate the effect? | Local PoC, logs, negative control |
| 6. Novelty | Has someone already published this? | Cited sources, duplicate collisions |
| 7. Deliver | What can we substantiate? | Private draft, limitations, next experiment |

### The hunt lenses

| Lens | Axis it attacks |
| --- | --- |
| `delta` | **Time** — code the last audit never saw |
| `upstream-diff` | **Lineage** — a fork's own deviation from the canonical upstream |
| `coverage-gap` | **Observability** — where tests lie, including mocks that mock the subject |
| `accounting` | **Aggregates** — enumerating every writer of every `total*` |
| `live-reality` | **Truth** — constants and deployed config against the live chain |
| `integration-auth` | **Boundaries** — which callback parameters the attacker controls |
| `liveness` | **Persistence** — cheap, unprivileged, irreversible denial |
| `anchor-account` | **Solana** — account substitution, PDA seeds, CPI authority |
| `seam` | **Combinations** — mechanisms no single lens can see, and refusals worth overturning |

Passes differ by **what they aim at**, not by effort. Aiming is cheap and mechanical — diffs, manifests and test files — and produces a ranked reading order, not findings. The attack passes then run the mechanism lenses against that ranking, each from an assembled bundle holding the reading SOP, the shared rules, that lens's procedure, the run context and all in-scope source:

```sh
python3 skills/bounty-pilot/scripts/bounty.py bundle \
  --repo /path/to/target --run run --lens attack --scope src/ --include run/delta.json
```

One bundle per lens, one agent per bundle, each in its own context. Recall is driven by the number of **independent** adversarial readings, so where budget allows each mechanism lens is dispatched twice in separate contexts — the cheapest recall increase available. Between passes, investigated mechanisms — including the ones looked for and *not* found — are written to `known-hypotheses.md`, and later passes must hunt past it.

The default budget is **up to three stages**, roughly 18 readings plus triage. It stops at the budget, or after two consecutive passes yield neither a new mechanism nor new coverage. There is no infinite loop and no finding quota — zero verified findings after an honest run is a legitimate result.

### Severity is the payout

Programs pay for the **impact class** a report establishes, so every candidate is pushed to the highest class its evidence genuinely reaches and no further: the same root cause filed as "accounting inconsistency" and as "the market permanently stops accepting deposits, with no admin function that repairs it" is the same code and two different payouts. [`impact-classes.md`](skills/bounty-pilot/references/impact-classes.md) holds the ladder and what each class demands as proof.

### Finding states

| State | Meaning |
| --- | --- |
| `hypothesis` | A mechanism worth investigating |
| `needs-evidence` | A concrete experiment or missing fact is still needed |
| `verified` | The workflow's technical evidence requirements are met; eligibility is assessed separately |
| `refuted` | A concrete protection, specification or test contradicts the claim |

## Requirements and coverage

- **Coding agent:** file access, repository access and a shell/test runner. Browsing helps verify program rules and public known issues.
- **Helper scripts:** Python 3.9+ and Git; no third-party Python dependencies, including for Keccak-256 and JSON-RPC.
- **Optional, for live checks:** any read-only JSON-RPC endpoint. No keys are loaded and no transaction is ever signed or broadcast.
- **Target tests:** the target's own toolchain, such as Foundry, Cargo or a local Solana harness.
- **Built-in focus:** Solidity/EVM, with a narrower Rust/Solana route. Other ecosystems require additional domain-specific guidance.
- **Language defaults:** Russian progress summaries, English report drafts. Request a different explanation language if preferred.

Designed as portable Markdown instructions; compatibility depends on the agent's available tools. A regular chat without execution tools cannot complete the same validation steps. Model/API usage is billed by your provider.

## Compared with solidity-auditor

[`pashov/skills`](https://github.com/pashov/skills)' `solidity-auditor` is a strong **candidate generator** for Solidity bug classes: twelve parallel specialists, three of which hunt the seams between lenses, with a loop mode that remembers findings between scans. On that axis it is better than anything here, and Bounty Pilot does not try to replace it.

But it audits a **repository**, while a bounty submission is a claim about a **deployed** system inside a **program's rules** — a different object:

| Needed for a payable report | `solidity-auditor` | Bounty Pilot |
| --- | --- | --- |
| Program rules, scope and exclusions | not modelled | stage 1, gate 5 |
| The deployed code is the code you audited | not checked | `verify-deployment` |
| Known issues burned before the hunt | not checked | `dup-check` |
| Priority on code the last audit never saw | all code equally | `delta` |
| Constants checked against the chain | source only | `eth-call`, `live-reality` |
| A runnable PoC with a negative control | reasoning trace | evidence gates, `templates/` |
| Objections held to the same evidence standard as findings | self-scored confidence | anchored two-round exchange |
| Non-EVM targets | Solidity only | Rust/Solana route |

Its confidence score is self-assessed by the model that produced the finding, so a high number means the agent was convinced, not that anything executed. **The two are additive.** Recommended combination: run Bounty Pilot's funnel and `delta`, delegate the Solidity bug-class sweep to `solidity-auditor` in loop mode, run the aimed lenses it has no equivalent for, import its output as `hypothesis` records, then adjudicate, verify and gate everything together. Do not nest the two orchestrators. Full detail and import rules: [references/compare.md](skills/bounty-pilot/references/compare.md).

## Integrations

Use complementary modules when available. **None is bundled or downloaded automatically.** The built-in workflow works on its own.

| Project | Optional role |
| --- | --- |
| [Pashov Skills](https://github.com/pashov/skills) | `solidity-auditor` for the Solidity bug-class sweep, `x-ray` for readiness, `fizz` for invariant suites ([comparison](#compared-with-solidity-auditor)) |
| [Trail of Bits Skills](https://github.com/trailofbits/skills) | Change review, variant analysis, false-positive checks and property tests |
| [0xSimao AI](https://github.com/0xsimao/0xsimao-ai) | Independent accounting-focused review |
| [QuillShield](https://github.com/quillai-network/quillshield_skills) | Targeted semantic guards and invariant checks |
| [Sanbir](https://github.com/sanbir/solidity-auditor-skills) | Additional EVM checks with overlap to Pashov |

Inspect and pin upstream revisions before use. Delegate bounded tasks instead of nesting full audit loops. See [integration instructions](skills/bounty-pilot/references/integrations.md) and [attribution](SOURCES.md).

## Files and helper commands

| File | Purpose |
| --- | --- |
| [SKILL.md](skills/bounty-pilot/SKILL.md) | Agent entry point and orchestration |
| [Target selection](skills/bounty-pilot/references/targets.md) | What makes a target worth a week, and the program facts file |
| [Hunt agents](skills/bounty-pilot/references/hunt-agents) | The eight aimed lenses and their shared stance and output contract |
| [Pass protocol](skills/bounty-pilot/references/passes.md) | What each pass aims at, dispatch, the known-hypotheses floor, stop rules |
| [Reading SOP](skills/bounty-pilot/references/sop.md) | How to read code: plain restatement, obligation tracing, backward reads, escalation |
| [Adjudication](skills/bounty-pilot/references/adjudicate.md) | The two-round exchange, the five gates, outcomes and promotions |
| [Triage agent](skills/bounty-pilot/references/triage.md) | The agent paid to reject, and the anchors it must produce |
| [Impact classes](skills/bounty-pilot/references/impact-classes.md) | What the payout is for, and where hunters leave money |
| [Duplicate map](skills/bounty-pilot/references/dup-map.md) | Sources, format and what a collision means |
| [Audit lenses](skills/bounty-pilot/references/lenses.md) | Classic bug-class checklists per stack |
| [Evidence rules](skills/bounty-pilot/references/evidence.md) | Candidate records and verification gates |
| [Comparison](skills/bounty-pilot/references/compare.md) | Division of labour with `solidity-auditor` |
| [Report template](skills/bounty-pilot/references/report.md) | English report structure |
| [PoC templates](skills/bounty-pilot/templates) | Fork, local, invariant and Solana harnesses |
| [bounty.py](skills/bounty-pilot/scripts/bounty.py) | Run scaffolding, delta, triage, on-chain checks, gates |
| [keccak.py](skills/bounty-pilot/scripts/keccak.py) | Dependency-free Keccak-256, so proxy slots are derived, not pasted |
| [Tests](tests/test_bounty.py) | 61 helper regression checks |

```sh
S=skills/bounty-pilot/scripts/bounty.py

# Prioritise a target from its code and its published program facts.
python3 $S score-target --repo /path/to/target --program run/program.json

# Use a new private directory outside both the target and the skill package.
python3 $S init --repo /path/to/target --out /path/to/private/new-run

# Assemble one bundle per lens: SOP + rules + lens procedure + context + in-scope source.
python3 $S bundle --repo /path/to/target --run run --lens attack --scope src/
python3 $S bundle --repo /path/to/target --run run --lens seam
python3 $S bundle --repo /path/to/target --run run --lens triage

# Rank non-test source changed since the exact commit the last audit covered.
python3 $S delta --repo /path/to/target --since <audited-commit> --scope src/

# Is the code on chain the code you are reading?
python3 $S verify-deployment --rpc <read-only-rpc> --address 0x... \
  --artifact out/Target.sol/Target.json

# Does that hardcoded constant mean what the source claims?
python3 $S eth-call --rpc <read-only-rpc> --to 0x... --sig 'markPx(uint32)' --arg 4
python3 $S sig 'transfer(address,uint256)'

# Gates.
python3 $S dup-check --run /path/to/private/new-run
python3 $S check     --run /path/to/private/new-run [--submission]

# Run helper tests.
python3 -m unittest discover -s tests -v
```

`init` does not clone, audit or execute the target. `eth-call` encodes static types only — use `cast` for strings, bytes and arrays. `verify-deployment` never rounds `partial` up to `exact`: same-length bytecode that differs is consistent with immutables or a different compiler build, and is not proof the logic matches.

`bundle` is the dispatch mechanic, not a convenience: a pass that skipped it handed its lenses less than they needed. Only the `coverage-gap` lens receives the test and mock files, because reading tests adversarially is its job and nobody else's.

`check` does not verify exploit truth, severity, originality or payout eligibility, and an empty finding list passes its structural checks. `check --submission` adds the readiness gates — including a recorded triage exchange with no sustained objection — and a green gate still means "nothing obviously missing", never "this is valid".

## FAQ

**Will it find more paid bugs?**  
That has not been measured, and this repository contains no comparative benchmark. What changed is where effort goes: toward unreviewed code, unburned surfaces, what is actually deployed, and the impact class the evidence reaches — and away from re-deriving a program's published known issues. The reasoning is stated so you can disagree with it; it is not a payout guarantee.

**Why does the triage agent have to prove its objections?**  
Because otherwise the exchange is asymmetric: the finding needs evidence and the rejection needs none. An agent allowed to reject on "probably intended" rejects nearly everything, and a wrongly refuted finding is invisible — you never learn it was real. So an objection carries quoted code, quoted specification, a named test or a live read, or it is withdrawn and recorded as withdrawn.

**How is this different from `solidity-auditor`?**  
That skill generates Solidity bug-class candidates better than this one does. This one decides which target and which code deserve the passes, checks that the code is deployed, burns known issues first, and gates what may be submitted. See [the comparison](#compared-with-solidity-auditor) — running both is the intended setup.

**Is this all the upstream skills merged together?**  
No. It is original orchestration and built-in guidance, with optional upstream integrations. Their source files and licenses are not repackaged as this project's own work.

**Can it rule out duplicates?**  
It builds a map of publicly burned surfaces before the hunt and matches candidates against it mechanically. It cannot see private submissions or guarantee uniqueness — `no-public-match-found` is the strongest claim the evidence supports.

**Does it submit or publish findings?**  
No. Results stay private unless the user explicitly authorizes a separate disclosure action.

## Contributing

Useful contributions include better ecosystem-specific lenses, clearer evidence requirements, reproducible helper fixes and synthetic test cases. Explain what changes and how you verified it. Do not include private source, credentials or undisclosed target vulnerabilities in issues or pull requests. Read [SECURITY.md](SECURITY.md).

## Responsible use and license

Review only authorized targets and follow program rules. Run PoCs locally in a secret-free environment; do not broadcast exploit transactions. No guarantee of coverage, validity, novelty or acceptance is made.

**[MIT licensed](LICENSE)** for original content. Upstream licenses remain separate. No affiliation with or endorsement by the linked projects is implied.
