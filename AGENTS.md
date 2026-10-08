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
- **Helper scripts are standard-library only** unless a concrete need justifies a dependency. The
  bundled keccak exists so on-chain identity checks need no install; Ethereum uses original Keccak
  padding, so `hashlib.sha3_256` is not a substitute.
- **Derived constants stay derived.** Proxy storage slots are computed from their labels, not pasted,
  and the tests assert they equal the published values.
- **No benchmark claims** without a reproducible measurement in the repository.

Skill entry point: `skills/bounty-pilot/SKILL.md`.
Run tests: `python3 -m unittest discover -s tests -v`.
Bump `VERSION` and `skills/bounty-pilot/VERSION` together; `.claude-plugin/plugin.json` carries the
same number.
