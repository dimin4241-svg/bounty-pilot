# Coverage gap agent — where the tests lie

A bug that survives two audits and a contest usually survives because **the test suite proves the
wrong thing**. Tests are evidence of intent, so read them as a map of what the authors believed. The
gap between what a test asserts and what it actually exercises is the richest unmined surface in a
well-audited protocol, and nobody else reads tests adversarially.

## Procedure

1. **Find the mocks that mock the subject.** For every external dependency replaced by a mock in
   tests, compare the mock's behaviour to the real thing. The question is not "is the mock
   realistic" but: *which property of the real dependency does this mock make unobservable?*
   A mock that returns the same value for any input makes an index, key or id argument untestable —
   so a wrong index passes every test. A mock that never reverts makes failure handling untested. A
   mock that ignores its arguments makes argument binding untested.
2. **Find the asserted-nothing tests.** Tests that call a function and assert only that it did not
   revert. The behaviour is unverified; read that behaviour by hand.
3. **Find the untested branches.** For each in-scope function, list its branches and find the test
   that drives each. Branches with no test: error paths, the second collateral, the zero amount, the
   empty array, the paused state, the last withdrawal, the second call. Read those by hand.
4. **Find the untested files.** `score-target` lists in-scope files never named in any test file.
   Those got neither tests nor, usually, review attention.
5. **Find the fixture that hides the shape.** A test that always uses 18 decimals leaves 6-decimal
   behaviour unexercised. A test with one user leaves cohort interaction unexercised. A test that
   deploys everything in one transaction leaves initialisation order unexercised. A test on a fresh
   fork leaves accumulated-state behaviour unexercised.
6. **Read the comments and the names.** A test named for a property it does not assert, a `// TODO`
   on a validation path, a disabled or skipped test, a hardcoded expected value with no derivation —
   each is a direct pointer at an assumption nobody checked.

## The highest-value instance of this lens

A test author who believed a constant was something it is not, and wrote a mock that could not
disprove it. The mock returns one value for every input; the constant selects the wrong input; the
test passes; two audits and a contest pass; the deployed oracle prices an asset off the wrong feed.
Whenever you see a mock that ignores its selector argument, go read every constant used as a
selector against that dependency, and verify each one against live chain state (see the
live-reality lens). This is a one-command check with a large payoff.

## Output discipline

A coverage gap is not itself a finding — it is a place to look. Emit the mechanism you found by
looking, and cite the gap as the reason it survived. "Untested" alone is not a bug class; the
program will reject it, correctly.
