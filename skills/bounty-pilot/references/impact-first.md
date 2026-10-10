# High-impact workflow 0.9.0

## Threat-first discovery

1. Read the program's actual scope, severity policy, audited/deployed revision,
   known issues and duplicate history. Select targets with unreviewed high-value
   integration and state changes; do not mistake "recent" for "unreviewed".
2. From a real compiler output or supported native parser, map critical state
   writers/readers, calls, externally reachable operations and the decisions
   where a wrong value would cause asset loss, insolvency, control takeover,
   message replay or unwithdrawable funds.
3. Run `semantic_graph.py` then `impact_paths.py` on an explicit
   compiler JSON (Solidity) or tracked Python checkout. A program's compiler
   JSON, trusted for structural data **only**, should be from the exact
   pinned revision. Rust remains on the existing heuristic graph plus
   rust-analyzer/native test guidance. This release does **not** claim native
   Rust compiler IR support or a generic sound call graph.
4. Run the `impact-first` lens independently. Work backwards from each
   proposed sink until a *source-confirmed* entry with an unprivileged
   capability reaches it. Distinguish a static call path from a sequence of
   stateful transactions: a state-dependency edge only proposes a test.
5. Author an explicit state-machine model for a strong lead, including real
   actors, guards, actions, failure/retry and invariants. Run
   `scenario_fuzz.py` within a finite state/depth budget and a separate
   protected control model. BFS produces shortest **model** counterexamples,
   not exploit proof. Inspect whether a state and transition are realizable
   in the native code; synthetic models are good for falsifying ideas, not
   certifying a bug.
6. Move every candidate to a native target test on unchanged source and a
   paired negative control. Verify pinned chain state and program eligibility.
   Calculate cost and victim loss with the actual currency/units and verified
   capital/liquidity. If anything is missing, leave a LEAD.

## A/B evaluation and anti-overfitting

Use existing `bounty.py backtest` to run separately sealed, blind hunts on
identical pinned revisions, scope, ground truth and model/tool budget. The
comparison helper `bench_compare.py` consumes **fully scored** baseline
and candidate result arrays only and refuses mismatched cases, revisions
or severities. Never compare two differently curated subsets. Evaluate High
and Critical separately from Medium/Low, record misses and unique verified
paths, and hand-audit unmatched reports: they are not automatically false
positives. Track cost/hours externally because scored reports do not contain
validated cost estimates.

Keep a strictly held-out set whose published findings were **not**
read during prompt tuning. Report paired counts and cases, not magical
percentages, guaranteed payouts, or manufactured benchmarks.

## Caveats

No tool in 0.9.0 autonomously writes and executes trustworthy exploit code on
all supported languages. Compiler AST parsing covers Solidity, while Python
uses stdlib AST; Rust, Move, Cairo and CosmWasm retain native-specific agent
procedures, native testing suggestions and the earlier low-confidence
inventory. A graph, model violation or numeric profit estimate cannot
establish program severity or a payable finding.
