# 0.9 impact-first fixtures

These JSON files are **toy fixtures, not actual vulnerabilities, benchmark
scores or native proof-of-concepts**.

- Use the broken and protected model pair with
  `scenario_fuzz.py --model model.example.json --control control.example.json`.
  The model demonstrates a bounded two-step invariant counterexample only.
- Replace inputs with verified real-world context before using
  `impact_feasibility.py`. Economic output remains severity=`unassessed`.
- Use `native_fuzz_plan.py --stack foundry --spec native-tests.example.json
  --out <private>/plan.json` only with existing Foundry test names. Review
  commands in dry-run mode before opting into execution via scenario_runner.
- Use `bounty.py impact-plan --solc <build-info.json> --out <private>`
  with a pinned source AST (`sources.*.ast`) to obtain static review clues.
- Compare versions using separately blind-sealed and fully scored
  backtest output arrays. Keep all private target evidence outside this repo.

No model violation or numeric calculation can establish a real High/Critical.
