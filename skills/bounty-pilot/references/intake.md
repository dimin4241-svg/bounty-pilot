# Intake and scope

Resolve a bare GitHub repository URL without repeatedly asking for preferences. For tree/blob links preserve the requested revision and subpath; do not assume branch names contain no slash. If revision resolution is ambiguous, fetch refs or ask one precise question. Reject arbitrary command strings as repository URLs. Prefer authenticated repository tools for private code and do not expose credentials in logs or remotes.

Record in scope.md:
- Canonical repository, full commit, clean/dirty status and local changes relevant to the audit.
- Program URL and rule retrieval date, eligible repositories/contracts, explicitly excluded impacts and trust assumptions.
- Chain ID, contract address, proxy implementation and block number when grounded in authoritative sources. Otherwise unknown.
- Previous audit links and their exact revisions. If no baseline is known, do a full review; do not call an arbitrary recent range the post-audit delta.
- Commands required to compile/test; whether they were inspected and actually run.

A URL-only request authorizes useful local review. Continue without a bounty page by explicitly marking eligibility unknown. Read-only inspection is distinct from active testing; follow the program's limits for any network interaction.

Choose a private output directory separate from the target checkout and from the skill package. Do not commit run artifacts. Never publish credentials, private source or undisclosed vulnerabilities with the generic toolkit.

For large repositories, map all relevant components, prioritize reachable value-bearing paths and recent changes, and mark unreviewed modules. No universal hard LOC cutoff. Review the dependency boundary and off-chain workers when they influence on-chain safety; scope eligibility may differ from technical relevance.
