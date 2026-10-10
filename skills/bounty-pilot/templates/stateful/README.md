# Stateful audit helper fixtures

These are **examples**, not exploit assertions or runnable target tests.

1. Use `stack_route.py --repo <target>` to identify candidate native adapters. Confirm actual runtime and trust boundaries yourself.
2. Use `state_graph.py` to suggest read/write overlap and 2–3 step scenarios, then validate every edge on original source.
3. Replace the example `finding.example.json` with a realistic, source-anchored hypothesis. Use `poc_scaffold.py --stack rust --finding <finding.json> --out-dir <private-dir>` (Solidity, Rust, Python, Go skeletons only). The generated candidate **and** negative control deliberately fail until implemented.
4. Replace the example `invariants.example.json` and `snapshot.example.json` with the protocol's actual property and a captured, provenance-documented state. Run `invariant_check.py`; note that the test does not prove snapshot reachability.
5. Update the example test plan to point to native test commands in an isolated target checkout. Run `scenario_runner.py --plan <plan.json> --repo <checkout>` first, inspect argv, and only then use `--allow-exec` in a secret-free sandbox.

A successfully executed test plan demonstrates **command exit expectations**, not valid impact, novelty, scope or payout. Never put undisclosed findings or credentials in the public skill repository.
