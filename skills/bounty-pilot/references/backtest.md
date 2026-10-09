# Backtesting — the only honest answer to "does this find bugs"

Everything else in this package is an argument. A backtest is a measurement: run the hunt on a
revision whose real findings are already published, **without looking at them**, then count what
it rediscovered.

It will not tell you whether you will get paid. It will tell you which lenses earn their passes,
which bug classes the hunt walks past, and whether a change made things better or only longer.

## The blind protocol, and why each rule is enforced in code

A rediscovery number means nothing if the hunt could see the answers — and the leak is rarely
deliberate, it is reading "just the titles" to set up the case. So the harness refuses rather than
warns:

- `truth.json` must be **empty when you seal**. If it has entries, the case is refused outright:
  that hunt was not blind and cannot produce a measurement.
- A case can be **sealed once**. A second seal would let a hunt be revised after the answers
  appeared.
- The sealed findings are **hashed**. Editing them afterwards voids the case.
- Scoring before sealing is refused.

If you break the protocol, start a new case on a different contest. A spoiled case is cheap; a
number you cannot trust is expensive, because you will act on it.

## Choosing cases

- **Published findings with a pinned commit.** Audit contests (Code4rena, Sherlock, Cantina) are
  ideal: every valid finding is published with its severity, and the reviewed commit is recorded.
  Public audit reports work too when they name the exact revision.
- **Check out that commit.** `backtest init --commit` warns when your checkout is somewhere else;
  measuring a different revision measures nothing.
- **Diverse shapes.** A lending protocol, an AMM, a bridge, a vault and a Solana program tell you
  far more than five lending protocols.
- **Keep a held-out set.** Use two or three cases to tune, and keep the rest closed until you want
  a number you can state. The moment you change a lens because you saw a miss, that case has
  become a training case — write that down in the case README.
- **Age matters.** A contest that closed last month may be in the model's training data. An older
  one measures the workflow; a very recent one measures less contaminated ground. Note which.

## Procedure

```sh
S=<skill-dir>/scripts/bounty.py

# 1. Open the case at the reviewed commit. Do not open the findings page.
python3 $S backtest init --name c4-example --repo <checkout> --commit <reviewed-commit> \
    --out <private>/backtests/c4-example --scope src/

# 2. Hunt that commit with the normal workflow, into its own run directory.
python3 $S init --repo <checkout> --out <private>/runs/c4-example
#    ... stages 0-5 as usual. Set `lens` on each finding - that is what gives per-lens credit.

# 3. Seal, before the answers exist anywhere on disk.
python3 $S backtest seal --case <private>/backtests/c4-example --run <private>/runs/c4-example

# 4. Only now read the published findings and transcribe them into truth.json.
# 5. Propose pairs, decide them, score.
python3 $S backtest score --case <private>/backtests/c4-example
```

Step 5 runs twice by design: the first call writes `matches.json` with the pairs the heuristic
proposes, the second scores once you have decided them.

## Deciding a pair

The heuristic proposes on file/symbol overlap and shared terms. **It does not judge**, and it is
deliberately loose — it would rather propose a pair you reject than hide one.

Decide on **root cause and affected path**, never on title similarity:

| Decision | When |
| --- | --- |
| `same-mechanism` | the same defect, reachable the same way, whatever the wording |
| `related-not-same` | the same function or surface, a different root cause |
| `different` | the overlap is coincidental |

Write one line in `decision_reason` for each. Then read the **missed** list by hand: a truth entry
the heuristic never proposed may still have been found under a very different description. Nothing
in the harness can catch that for you.

## Reading the result

What the output gives you, and what each number is worth:

- **`serious_rediscovered`** — of the published Critical/High/Medium, how many the hunt found. This
  is the headline, and it is a **count**, not a rate: with three cases you have an anecdote with
  error bars wider than any difference you are trying to measure. Report `7 of 19 across 4 cases`,
  never `37%`.
- **`missed`** — the most valuable output in the file. For each miss, answer one question: *which
  lens should have caught this, and why did it not?* That answer is the only reliable tuning signal
  this package has. A miss no lens covers is a missing lens.
- **`credited_lenses`** — which lenses actually produced the rediscoveries. A lens that never gets
  credit across several cases is costing a reading per pass and returning nothing.
- **`unmatched_hunt_findings`** — findings with no published counterpart. **These are not false
  positives**, and the harness refuses to call them that. Contests miss things, judges deduplicate
  aggressively, scope differs, and some of your findings may be genuinely novel. Judge each one
  separately and label it: likely wrong, out of the contest's scope, or possibly novel. If one is
  possibly novel on a live protocol, stop backtesting and go check whether it is still there.

## What a backtest cannot tell you

- **It does not predict a payout.** A contest has no private duplicates, a fixed scope, no
  deployment question and a judge who wants to pay valid findings. A live bounty has all four
  working against you. Rediscovery measures the hunt; it does not measure the funnel.
- **It does not measure precision.** You would need ground truth about what is *not* a bug, and
  nobody has that.
- **It can be contaminated.** A widely-discussed contest may be in the model's training data, which
  inflates rediscovery. Prefer a spread of ages and say which cases are recent.
- **It measures this workflow, on this model, on that day.** Re-measure after a model change before
  reusing an old number.

## Measure the live funnel separately

Backtests measure rediscovery on published cases. They cannot reveal your platform's private queue or
predict acceptance. Keep report outcomes locally so the next run can spot repeated mechanisms and
you can see which kinds of reports get rejected.

```sh
S=<skill-dir>/scripts/bounty.py
python3 $S history check --run <run>
python3 $S history record --run <run> --finding BP-001 --outcome submitted \
    --program "Cantina / Example" --hours 4
# Later, reuse the printed case id when a decision arrives.
python3 $S history record --run <run> --finding BP-001 --outcome duplicate \
    --case-id <full-id-printed-by-first-command> --reason private-duplicate
python3 $S history summary
python3 $S history import --project https://github.com/org/repo \
    --finding-id C4-123 --bug-class accounting-dust --surface src/Vault.sol:withdraw \
    --root-cause "withdraw does not decrement accrued fees" --outcome duplicate
```

The default JSONL file is `~/.bounty-pilot/history.jsonl`; set `--ledger` to choose another private
path. The helper creates it with owner-only permissions and refuses to place it inside the target,
run or skill. It stores the project key, bug class, paths, a short mechanism summary, lens, program,
outcome, reason category and effort. It never stores report text, source files, PoCs, wallet addresses
or credentials. Seed older reports with `history import` only when their mechanism metadata can be
verified against the original; do not reconstruct missing details from memory as if they were facts.

On an empty new run, `history check` returns every compact prior case for that repository in
`prior_cases`; review them before the first pass and add the mechanisms as hunt leads, never as
surfaces to skip. After candidates exist, it reports exact project/class/path overlaps first and
related cross-project patterns second. These are recall-oriented suggestions; inspect root cause and
revision yourself. Never let the helper declare a duplicate or suppress a candidate.
`history summary` reports counts from your own recorded reports, not payout odds. Use those counts
to change one workflow factor at a time and keep the old baseline.

## Keeping yourself honest

Record every case you ran, including the ones that went badly or whose protocol you broke. A
backtest set you prune is a backtest set that only ever improves. The cheapest way to lie to
yourself here is to quietly drop the case that went worst.
