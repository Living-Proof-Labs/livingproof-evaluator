# Contribute

Read [AGENTS.md](../AGENTS.md) and the explicitly adopted
[collaboration-guidelines v7.8.2](https://github.com/Living-Proof-Labs/collaboration-guidelines/tree/v7.8.2).
Use a draft pull request and obtain independent review before merge.

In a prepared environment with Python 3.12, uv, and Task 3.54.0:

```sh
task setup
task verify
uv run --locked --no-sync python tools/validate_contract.py examples/scenario/graded/result.json
```

The last command prints `valid` and exits zero for this fixture. The validator is
a repository utility, not an installed evaluator command. It accepts one JSON path;
wrong argument count prints usage and exits 2, contract errors exit 1. Malformed
JSON and unreadable files currently raise Python errors. Its source remains canonical.
There is no public package API or evaluator installation/quickstart in this repository.

Use [issues](https://github.com/Living-Proof-Labs/livingproof-evaluator/issues) for
ordinary help and bug reports. A private security reporting destination has not
been established by this adoption; do not put sensitive reports in public issues.

Repository prose, schemas, examples and tooling are [Apache-2.0](../LICENSE).
The manual tooling is adapted from collaboration-guidelines v7.8.2 under Apache-2.0.
The downloaded shared brand retains its upstream license notice.
