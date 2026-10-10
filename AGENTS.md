# Repository maintenance

This repository contains a reusable bounty-hunting workflow, not audit results.

Keep target-specific data private: no private source, reports, wallet addresses, RPC keys, run
directories, logs or credentials. The toolkit being public does not make any finding public.

Preserve these invariants when editing:

- **Structural validation and exploit verification stay separate.** `check` reports structure;
  `check --submission` reports readiness; neither establishes that a finding is real, and no commit
  may blur that distinction in code or in prose.
- **Generation and adjudication stay separate passes.** Hunt agents must not be told to refute
  themselves (`references/hunt-agents/_shared.md`), and `references/adjudicate.md` must stay a
  distinct pass with written gates. Merging them silently lowers both recall and precision.
- **Objections carry the same evidence burden as findings.** `references/triage.md` may reject only
  on a quoted anchor; an unanchored objection is withdrawn and recorded as withdrawn, never
  weighed. Relaxing this makes the triage agent reject nearly everything, and a wrongly refuted
  finding leaves no trace — which is why the validator enforces it rather than the prose alone.
- **`bundle` stays the dispatch mechanic.** Lens instructions assume the bundle contains the source;
  a change that makes lenses fetch their own files reduces coverage silently.
- **Only `verify-deployment` sets `deployment_status`, and a proxy is compared at its
  implementation.** A matching proxy runtime must never read as `exact`, and a bytecode tail is
  stripped only when it really is solc CBOR metadata — both have produced false confidence before
  and both are covered by tests.
- **Helper scripts are standard-library only** unless a concrete need justifies a dependency. The
  bundled keccak exists so on-chain identity checks need no install; Ethereum uses original Keccak
  padding, so `hashlib.sha3_256` is not a substitute.
- **Derived constants stay derived.** Proxy storage slots are computed from their labels, not pasted,
  and the tests assert they equal the published values.
- **Every registered lens has an instruction file**, and `ATTACK_LENSES` leads with
  `privileged-path`: access control and initialization are the categories automated reviewers
  measurably miss most. A test asserts both.
- **`references/hack-patterns.md` is a pattern library, not a source of record.** Loss figures and
  attributions are approximate and get revised; a report cites the protocol's own post-mortem.
  Never add a claim that a protocol was exploited without a source.
- **`solc-bugs` reads the official list at runtime** rather than bundling a snapshot that would go
  stale, and reports a fetch failure instead of returning an empty, reassuring result.
- **The backtest's blind protocol is enforced, not advised.** Sealing is refused when `truth.json`
  already has entries, a case seals once, and a sealed file that changed voids the case. Any change
  that turns one of these into a warning destroys the only measurement this package can make.
  An unmatched hunt finding is never counted as a false positive.
- **No benchmark claims** without a reproducible measurement in the repository.

Skill entry point: `skills/bounty-pilot/SKILL.md`.
Run tests: `python3 -m unittest discover -s tests -v`.
Bump `VERSION` and `skills/bounty-pilot/VERSION` together; `.claude-plugin/plugin.json` carries the
same number.

- **Stateful helper evidence levels stay explicit.** `state_graph.py` is only a lexical heuristic; `invariant_check.py` tests supplied JSON snapshots; `scenario_runner.py` is dry-run unless execution is explicitly allowed. Never call any of those outcomes verified exploits. Both candidate and negative-control cases are mandatory for execution plans.
- **Cross-stack runtime semantics must be native.** Rust workers are not Solana programs; Sui is not Aptos; on-chain atomic failure is not off-chain crash persistence. Each added lens must have an instruction file and tests must cover it.

- **Impact-first results do not assert severity.** Solidity/Python AST references, source state overlaps, bounded model counterexamples and economics computed on user-supplied inputs are leads only. Confirm actual deployed revision, low-privileged reachability, real third-party loss and unchanged native source before High/Critical.
- **Paired blind benchmarks** must use the same pinned revisions, exact finding truths, examiner decisions, tool/model budgets and held-out cases. Report raw rediscovered counts only; no unmeasured uplift or guaranteed payout.
