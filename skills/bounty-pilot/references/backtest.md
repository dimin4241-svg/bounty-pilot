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

Backtests compare rediscovery and misses, but cannot estimate private duplicates, program
eligibility, acceptance or payment. Keep a private, target-specific ledger with one row per report:
effort, whether the PoC reproduced from a clean checkout, public match, scope decision, triage
status, accepted severity and reward status/date. Attribute discoveries to a lens only when the run
record supports it. Do not turn a small personal sample into a payout probability, and never put
target identities, report text, wallet addresses or private outcomes in the public toolkit.

Use the ledger to ask which target shapes produce fewer duplicates, which lenses produce candidates
that survive reproduction, and where reports are rejected. Change one workflow factor at a time and
keep the old baseline; otherwise an apparent improvement cannot be attributed to the change.

## Measure the live funnel separately

Backtests can compare rediscovery and misses, but they cannot estimate private duplicates, program
eligibility, acceptance or payment. Keep a private, target-specific ledger with one row per submitted
report: time/cost to investigate, whether the PoC reproduced from a clean checkout, public match,
scope decision, triage status, severity accepted, and reward status/date. Attribute discoveries to a
lens only when the run record supports it. Do not turn a small personal sample into a payout
probability, and never put target identities, report text, wallet addresses or private outcomes in
the public skill repository.

Use the ledger to answer practical tuning questions: which target shapes produce fewer duplicates,
which lens produces candidates that survive reproduction, and where reports are most often rejected.
Change one workflow factor at a time and keep the old baseline; otherwise an apparent improvement
cannot be attributed to the change.

## Keeping yourself honest

Record every case you ran, including the ones that went badly or whose protocol you broke. A
backtest set you prune is a backtest set that only ever improves. The cheapest way to lie to
yourself here is to quietly drop the case that went worst.
