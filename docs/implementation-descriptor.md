# Implementation descriptor

An evaluator implementation ships an implementation descriptor so a loader can install and run it with no code that knows that implementation by name. The format is `livingproof-evaluator-implementation/1`. The schema is [`schema/implementation.schema.json`](../schema/implementation.schema.json). The worked examples are the Run Integrity descriptor in [`examples/implementation/run-integrity.json`](../examples/implementation/run-integrity.json), the document [livingproof-evaluator-run#67](https://github.com/Living-Proof-Labs/livingproof-evaluator-run/issues/67) ships, and the Scenario descriptor in [`examples/implementation/scenario.json`](../examples/implementation/scenario.json).

## How this differs from the result descriptor

The [result descriptor](evaluator-descriptor.md) is optional display copy on a `livingproof-evaluator-result/1.1.0` result. A report renders its title, mark, tier, and findings. On that object, `kind` is a display label. The payload selector stays `evaluator.kind` on the result.

The implementation descriptor is a file in the implementation repository. It tells a loader the distribution name, the Python module, the arguments, and the exit codes. A report does not render it, and it is not a field of the result. `kind` here is a closed enum. A consumer MUST refuse a kind it does not know.

## Format

The format stays /1. Later kinds arrive as minor versions: a later minor version of this contract widens the `kind` enum additively, and the format identifier stays `/1`. This version's kinds are `integrity`, `advisory`, and `scenario`. A consumer MUST refuse a kind it does not know.

## Fields

Every field below is required. An object rejects a key the schema does not name. A consumer MUST refuse a document with duplicate JSON object keys.

| Field | Meaning |
| --- | --- |
| `format` | The constant `livingproof-evaluator-implementation/1`. The format stays /1. |
| `id` | The `evaluator.id` this implementation writes on its results. A slug, such as `livingproof-run-integrity`. |
| `kind` | `integrity`, `advisory`, or `scenario`. A consumer MUST refuse a kind it does not know. |
| `grading` | `integrity` and `advisory` require `none`. `scenario` requires `robot`. Every other combination is rejected. See One grading evaluator. |
| `package` | The distribution `name` only. See Install. |
| `runtime` | `python`, fixed at 3.12 for now. See Runtime. |
| `entrypoint` | `module`, the Python module a loader runs with `python -m`. |
| `arguments` | Ordered arguments. See Placeholders. |
| `exit_codes` | Each listed code means `result` or `refused`. See Exit codes. |
| `result` | `result` is `livingproof-evaluator-result/1.<minor>.<patch>`. Another major is refused. `advisory` names minor 1.3 or any later 1.x minor. |

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
| `{evidence_manifest}` | Path of the evidence manifest. It appears in a top-level argument string, and in `media.arguments` when that object is present. |
| `{media_dir}` | Path of the media directory when the loader has one. On the trial run it is optional. |
| `{result}` | Path where the implementation writes its result. It appears in a top-level argument string. The consumer substitutes it separately for the media run. |
| `{thresholds}` | Path of the thresholds file the trial run reads. It may appear in a trial argument string. |
| `{world}` | Path of the world file the media run reads. It may appear only in `media.arguments`. |
| `{identity}` | The evaluator identity the media run records, a commit or an image digest. It may appear only in `media.arguments`. The consumer already resolved that identity when it fetched the descriptor. |

Any other `{...}` token, such as `{trial_dir}`, is rejected. A placeholder that appears only inside `then` does not meet the top-level rule for `{evidence_manifest}` or `{result}`. Those two must each appear in a top-level string, because the run needs a manifest and a path for the result file.

A placeholder for an optional input may appear only inside a conditional whose `if` names that input. A top-level argument string may not contain `{media_dir}`, `{world}`, or `{identity}`. `{media_dir}` may appear in `then` only when `if` is `media_dir`, and it may appear in `media.arguments`. `{thresholds}` may appear in a trial argument string, including inside `then`. It may not appear in `media.arguments`.

## Exit codes

`exit_codes` maps a process exit code to `result` or `refused`. The key is the code in decimal, from 0 through 255, with no leading zero, written as a string. `"0"` is required and is `result`: the process wrote a result. `refused` means the implementation refused the inputs and did not write a result.

Any exit code not listed in exit_codes is a failure with no result. A loader does not read a result file for an unlisted code.

The Run Integrity example maps `2` to `refused`. That mapping belongs to that implementation. The schema requires the `"0"` entry and leaves every other code to the descriptor that needs it.

## Result

`result` is `livingproof-evaluator-result/1.<minor>.<patch>`. Another major is refused. Minor and patch are ASCII digits with no leading zero. The Run Integrity example declares `livingproof-evaluator-result/1.2.0`. An `advisory` implementation names minor 1.3 or any later 1.x minor, for example `livingproof-evaluator-result/1.3.0` or `livingproof-evaluator-result/1.4.0`. The descriptor names the one version it writes. Consumers must check that the produced result's format equals the declared value and that its major is one they support.

## Advisory

`kind` may be `advisory`. `grading` is `none`: an advisory implementation does not grade. `result` names `livingproof-evaluator-result/1.<minor>.<patch>` with minor 1.3 or any later 1.x minor. The descriptor names the one version it writes. The format identifier stays `/1`. `{media_dir}` may appear only in a conditional whose `if` is `media_dir`. An advisory descriptor has no `media` run.

The result contract for this kind is in [advisory](advisory.md). A consumer MUST refuse a kind it does not know.

## Scenario

`kind` may be `scenario`. `grading` is `robot`: this is the implementation that grades the robot. `result` uses the same `livingproof-evaluator-result/1.<minor>.<patch>` rule as any other descriptor. The first-party scenario evaluator writes `livingproof-evaluator-result/1.1.0`. The format identifier stays `/1`.

The trial run is `entrypoint` and `arguments`, as for every kind. The media run is the optional `media` object: `module` and a flat `arguments` list. `integrity` and `advisory` reject that key. A consumer runs the media process only when it has a media directory, and it substitutes `{result}` separately so the two runs write different paths.

The worked example is [`examples/implementation/scenario.json`](../examples/implementation/scenario.json). It declares the two commands the scenario package accepts today:

```text
python -m livingproof_evaluator_scenario {evidence_manifest} --thresholds {thresholds} --out {result}
python -m livingproof_evaluator_scenario.media {evidence_manifest} {media_dir} {result} --world {world} --identity {identity}
```

Those are `python -m livingproof_evaluator_scenario` and `python -m livingproof_evaluator_scenario.media`. The package defaults `--started-at` and `--completed-at` to the current minute, so the descriptor omits them. The media module is not the trial module: the recordings run is `livingproof_evaluator_scenario.media`.

Exit `0` writes a result. The scenario package exits `1` when it refuses the evidence and `2` when the arguments are wrong. The example maps both to `refused`. Any exit code not listed in exit_codes is a failure with no result.

## One grading evaluator

At most one evaluator in a run may grade the robot. A descriptor is one evaluator, so the descriptor cannot state that rule. A consumer that loads a list of descriptors MUST refuse a list with two `grading` values of `robot`.

`tools/validate_contract.py` checks one document and does not see the run's list, so the rule is left to consumers. [`examples/implementation/consumer/two-robot-graders.json`](../examples/implementation/consumer/two-robot-graders.json) is two scenario descriptors that each validate. A consumer test refuses that list before it installs either one.
