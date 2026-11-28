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
| `{result}` | Path of one result file. Only integrity and advisory may use it. integrity and advisory write that file. It is not a directory. It appears in a top-level argument string. scenario rejects it. |
| `{result_dir}` | A directory a scenario run writes into. Only `kind: scenario` may use it. The per-trial result files in that directory are the results, and each one carries the declared result format. `thresholds.json` and any other file in the directory are not results. |
| `{thresholds}` | Path of the thresholds file a scenario trial reads. Only `kind: scenario` may use it, in a top-level trial argument or inside `then`. `integrity` and `advisory` reject it. |
| `{world}` | Path of the world file the media run reads. It may appear only in `media.arguments`. |
| `{identity}` | The `--identity` string the media CLI records. The package stores that string as the evaluator input URI. Today's value is `git+https://github.com/<owner>/<repo>@<commit>`. The flag also accepts a commit or an image digest. It may appear only in `media.arguments`. |

Any other `{...}` token, such as `{trial_dir}`, is rejected. A placeholder that appears only inside `then` does not meet the top-level rule for `{evidence_manifest}` or `{result}`. `{evidence_manifest}` must appear in a top-level string. integrity and advisory must also include `{result}` there, because the run needs a manifest and a path for the result file. A scenario run names `{result_dir}` there instead, and rejects `{result}`.

A placeholder for an optional input may appear only inside a conditional whose `if` names that input. A top-level argument string may not contain `{media_dir}`, `{world}`, or `{identity}`. `{media_dir}` may appear in `then` only when `if` is `media_dir`, and it may appear in `media.arguments`. `{thresholds}` may appear in a scenario trial argument, including inside `then`. `integrity` and `advisory` reject it in either place. It may not appear in `media.arguments`.

## Exit codes

`exit_codes` maps a process exit code to `result` or `refused`. The key is the code in decimal, from 0 through 255, with no leading zero, written as a string. `"0"` is required and is `result`: the process wrote a result. `refused` means the implementation refused the inputs and did not write a result.

Any exit code not listed in exit_codes is a failure with no result. A loader does not read a result file for an unlisted code.

The Run Integrity example maps `2` to `refused`. That mapping belongs to that implementation. The schema requires the `"0"` entry and leaves every other code to the descriptor that needs it.

## Result

`result` is `livingproof-evaluator-result/1.<minor>.<patch>`. Another major is refused. Minor and patch are ASCII digits with no leading zero. The Run Integrity example declares `livingproof-evaluator-result/1.2.0`. An `advisory` implementation names minor 1.3 or any later 1.x minor, for example `livingproof-evaluator-result/1.3.0` or `livingproof-evaluator-result/1.4.0`. The descriptor names the one version it writes. Consumers must check that the produced result's format equals the declared value and that its major is one they support.

## Advisory

`kind` may be `advisory`. `grading` is `none`: an advisory implementation does not grade. `result` names `livingproof-evaluator-result/1.<minor>.<patch>` with minor 1.3 or any later 1.x minor. The descriptor names the one version it writes. The format identifier stays `/1`. `{media_dir}` may appear only in a conditional whose `if` is `media_dir`. An advisory descriptor has no `media` run and rejects `{thresholds}`.

The result contract for this kind is in [advisory](advisory.md). A consumer MUST refuse a kind it does not know.

## Scenario

`kind` may be `scenario`. `grading` is `robot`: this is the implementation that grades the robot. `result` uses the same `livingproof-evaluator-result/1.<minor>.<patch>` rule as any other descriptor. The first-party scenario evaluator writes `livingproof-evaluator-result/1.1.0`. The format identifier stays `/1`.

This descriptor covers the walk-hallway trial only. The consumer writes the hallway thresholds into `{thresholds}`, and world and parameters are absent, so there is no world document and the media run does not run. World-graded scenarios, including walk-corner, are not expressed here. They stay on capability-verifier's wrappers until that work moves. Additive `{world}` on the trial run and `{parameters}` on both runs are follow-up work.

The trial run is `entrypoint` and `arguments`, as for every kind. The media run is the optional `media` object: `module` and a flat `arguments` list. `integrity` and `advisory` reject that key. A consumer runs the media run only when it has both a media directory and a world document; otherwise it runs no media process and writes no media result. The consumer substitutes `{result_dir}` separately so the two runs write different directories.

`{result_dir}` is a directory a scenario run writes into. The per-trial result files in that directory are the results, and each one carries the declared result format. `thresholds.json` and any other file in the directory are not results.

The worked example is [`examples/implementation/scenario.json`](../examples/implementation/scenario.json). It declares the two commands the scenario package accepts for walk-hallway:

```text
python -m livingproof_evaluator_scenario {evidence_manifest} --thresholds {thresholds} --out {result_dir}
python -m livingproof_evaluator_scenario.media {evidence_manifest} {media_dir} {result_dir} --world {world} --identity {identity}
```

Those are `python -m livingproof_evaluator_scenario` and `python -m livingproof_evaluator_scenario.media`. The trial CLI defaults `--started-at` to the current minute and `--completed-at` to that same started-at. The media CLI has `--started-at` only, defaulting to the current minute, and writes that value as both timestamps. It has no `--completed-at`. The descriptor omits them. The media module is not the trial module: the recordings run is `livingproof_evaluator_scenario.media`.

Exit `0` writes results. The example maps exit `1` to `refused`. At scenario package v1.5.21, exit 1 is also an uncaught crash: a missing or non-JSON thresholds file, a missing manifest, or a missing media.json. A distinct refusal exit code is follow-up work for [livingproof-evaluator-scenario#60](https://github.com/Living-Proof-Labs/livingproof-evaluator-scenario/issues/60). Exit 2 is an argparse usage error, including a missing `--thresholds` or `--world`. The example does not list exit 2, so it is a failure, not a refusal. Any exit code not listed in exit_codes is a failure with no result.

## One grading evaluator

At most one evaluator in a run may grade the robot. A descriptor is one evaluator, so the descriptor cannot state that rule. A consumer that loads a list of descriptors MUST refuse a list with two `grading` values of `robot`.

The schema validates one descriptor and does not see the run's list, so the rule is left to consumers. [`examples/implementation/consumer/two-robot-graders.json`](../examples/implementation/consumer/two-robot-graders.json) is two scenario descriptors that each validate. A consumer test refuses that list before it installs either one.
