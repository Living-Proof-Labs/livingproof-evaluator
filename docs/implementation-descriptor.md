# Implementation descriptor

An evaluator implementation ships an implementation descriptor so a loader can install and run it with no code that knows that implementation by name. The format is `livingproof-evaluator-implementation/1`. The schema is [`schema/implementation.schema.json`](../schema/implementation.schema.json). The worked example is the Run Integrity descriptor in [`examples/implementation/run-integrity.json`](../examples/implementation/run-integrity.json), the document [livingproof-evaluator-run#67](https://github.com/Living-Proof-Labs/livingproof-evaluator-run/issues/67) ships.

## How this differs from the result descriptor

The [result descriptor](evaluator-descriptor.md) is optional display copy on a `livingproof-evaluator-result/1.1.0` result. A report renders its title, mark, tier, and findings. On that object, `kind` is a display label. The payload selector stays `evaluator.kind` on the result.

The implementation descriptor is a file in the implementation repository. It tells a loader the distribution name, the Python module, the arguments, and the exit codes. A report does not render it, and it is not a field of the result. `kind` here is a closed enum. A consumer MUST refuse a kind it does not know.

## Format

The format stays /1. Later kinds arrive as minor versions: a later minor version of this contract widens the `kind` enum additively, and the format identifier stays `/1`. A consumer MUST refuse a kind it does not know.

## Fields

Every field below is required. An object rejects a key the schema does not name.

| Field | Meaning |
| --- | --- |
| `format` | The constant `livingproof-evaluator-implementation/1`. The format stays /1. |
| `id` | The `evaluator.id` this implementation writes on its results. A slug, such as `livingproof-run-integrity`. |
| `kind` | `integrity` only in this version. Later kinds widen this enum. |
| `grading` | `none` only in this version. This implementation does not grade. |
| `package` | The distribution `name` only. See Install. |
| `runtime` | `python`, fixed at 3.12 for now. See Runtime. |
| `entrypoint` | `module`, the Python module a loader runs with `python -m`. |
| `arguments` | Ordered arguments. See Placeholders. |
| `exit_codes` | Each listed code means `result` or `refused`. See Exit codes. |
| `result` | The result format this implementation writes, `livingproof-evaluator-result/1.1.0`. |

## Install

`package.name` is the distribution name. It installs from the descriptor's own repository at the same commit as the descriptor. The descriptor never names another source: there is no path, URL, `git+` locator, or commit beside that name, and `package` has no key besides `name`.

The name matches a PEP 508 distribution name, so a path, a URL, `git+`, `@`, and `/` are rejected. A 40-character hexadecimal commit is rejected as well. A commit is a source pin, and the install commit is the descriptor's own commit, not a package name.

## Runtime

`runtime.python` is the interpreter a loader uses. Fixed at 3.12 for now and will widen later. The object has no key besides `python`.

## Placeholders

Each argument is a string, or an object with `if` and `then` that a loader includes only when that input is present. `if` is `evidence_manifest`, `media_dir`, or `result`, written without braces. `then` is a non-empty array of argument strings. Both keys are required. A conditional has no other keys and does not nest, so `then` cannot contain another `if`.

A string may contain only these placeholders, each written with braces:

| Placeholder | Role |
| --- | --- |
| `{evidence_manifest}` | Path of the evidence manifest. It appears in a top-level argument string. |
| `{media_dir}` | Path of the media directory when the loader has one. |
| `{result}` | Path where the implementation writes its result. It appears in a top-level argument string. |

Any other `{...}` token, such as `{trial_dir}`, is rejected. A placeholder that appears only inside `then` does not meet the top-level rule. `{evidence_manifest}` and `{result}` must each appear in a top-level string, because the run needs a manifest and a path for the result file.

## Exit codes

`exit_codes` maps a process exit code to `result` or `refused`. The key is the code in decimal, from 0 through 999, with no leading zero, written as a string. `"0"` is required and is `result`: the process wrote a result. `refused` means the implementation refused the inputs and did not write a result.

Any exit code not listed in exit_codes is a failure with no result. A loader does not read a result file for an unlisted code.

The Run Integrity example maps `2` to `refused`. That mapping belongs to that implementation. The schema requires the `"0"` entry and leaves every other code to the descriptor that needs it.
