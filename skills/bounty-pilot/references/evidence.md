# Candidate records and evidence

Use findings.json as an array. Start with candidate-template.json but assign stable IDs (BP-001, etc.). Deduplicate by root cause and relevant affected paths, not title similarity. Split independent root causes; preserve multiple impacts under one root cause when appropriate.

Required fields for every record:
- id, title, status, severity, root_cause, affected_paths, attacker_capabilities, preconditions, impact, scope_status, deployment_status, novelty, evidence, rejection_reason.
- status: hypothesis | needs-evidence | verified | refuted.
- severity: unassessed | informational | low | medium | high | critical. Cite the program rubric before assigning a final label.
- scope_status: unknown | in-scope | out-of-scope.
- deployment_status: unknown | exact | partial | mismatch | not-applicable.
- novelty.status: not-checked | no-public-match-found | matched-public-issue; novelty.sources: array of source URLs and comparison notes.

Evidence fields for verified:
- command: exact reproduction command, without credentials.
- exit_code: observed integer; normally zero for a test that asserts the bad outcome.
- log_path and poc_path: existing relative files inside the private run directory, never symlinks outside it.
- assertion: concrete violated property and what the observed result establishes.
- negative_control: observed contrasting case and result, not merely a proposed test.
- source_integrity: how unmodified production code and realistic dependency behavior were preserved.

For refuted, rejection_reason must cite a concrete protection, specification or test result. For needs-evidence, list the missing experiment in impact or evidence notes. A lack of tools is not refutation. Keep severity provisional where preconditions remain uncertain.

Verify four distinct gates:
1. Reachability: attacker capabilities and supported configuration permit the path.
2. Causality: the original source produces the claimed violation; a control isolates the mechanism.
3. Material impact: balances, liabilities, integrity or liveness actually change as claimed.
4. Eligibility: authoritative program rules and relevant deployment version support submission.

Technical verification may succeed while gate 4 is unknown or fails. Never merge these judgments. Claims about profitability include fees, capital and feasible market assumptions; claims about DoS include persistence, blast radius and recovery. Treat fork simulations as point-in-time evidence, not proof of all deployment states.
