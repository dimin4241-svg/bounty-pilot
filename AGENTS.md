# Repository maintenance

This repository contains a reusable audit workflow, not audit results.
Keep target-specific data private. Do not add private source, reports, wallet addresses, logs or credentials. Preserve the distinction between structural validation and exploit verification. Do not claim benchmark improvements without reproducible measurements.

Skill entry point: skills/bounty-pilot/SKILL.md.
Run tests with: python3 -m unittest discover -s tests -v.
Keep helper scripts standard-library-only unless a concrete need justifies a dependency.
