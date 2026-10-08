# English report template

Title: [Impact] through [root cause] in [component]

Status: technical validity / scope / deployment / public-known-issue check.
Severity: provisional or final, with program rubric and rationale.
Target: repository, full commit, affected file/function; chain/address/block if verified.

## Summary
State who can do what, under which realistic conditions, and who is harmed.

## Root cause
Explain the violated property and the exact implementation behavior. Cite relevant source locations.

## Preconditions and attack path
List attacker capabilities, reachable setup, transactions or calls, and the resulting state.

## Impact
Quantify the demonstrated effect separately from theoretical maximums. Include limitations and recovery options.

## Reproduction
List environment/tool versions, installation/build prerequisites, exact command, PoC location, observed log and assertions. Explain the negative control and source integrity. Never include secrets or require a live attack.

## Existing protections and known issues
Explain why relevant guards do not prevent this mechanism. Link public comparisons and avoid claiming private-duplicate certainty.

## Suggested remediation
Describe a minimal mitigation and invariant/regression to preserve. Keep any patch separate from the original reproduction.

## Limitations
State unsupported assumptions, missing deployment evidence and checks not run.

Draft only. Do not submit automatically.
