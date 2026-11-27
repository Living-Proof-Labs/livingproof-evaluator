# Advisory

An advisory result reports an observation. It never grades the robot. It never changes Scenario, Run Integrity, or the evidence.

`evaluator.kind` selects the payload. For this kind it is `advisory`. The payload is the `advisory` object. That object cannot appear beside `scenario` or `integrity`, and those payloads cannot appear beside it.

Title, purpose, and version come from the existing [descriptor](evaluator-descriptor.md). On an advisory result the descriptor is required, and `tier` is `observation`. The descriptor's own `kind` stays a display label. It does not select the payload.

## What the payload may contain

| Field | Required | Meaning |
| --- | --- | --- |
| `summary` | yes | Plain text, 1 to 400 characters. |
| `details` | yes | Plain text, 1 to 2000 characters. |
| `details_file` | no | A relative `.json` or `.txt` path and the sha256 of that file. The path is at most 256 characters. It has no scheme, no `..` traversal, and no query or fragment. |
| `trials` | no | The observations this result read. Each entry has `index` and `observation_sha256`. |

Plain text rejects `<`, `>`, and control characters, including newlines. An ampersand is allowed. A value that is only whitespace is rejected. The same limits are what a report already uses for advisory presentation text.

The object rejects any other key. It has no grade, no robot verdict, and no test-system status.

## Format

The result format that carries this payload is `livingproof-evaluator-result/1.3.0`. A later 1.3 patch is the same minor. Documents that already validate as 1.0, 1.1, or 1.2 still validate. An advisory document does not validate when its format is `1.2.x`.

A 1.2 consumer ignores the unknown kind. It drops fields it does not know and does not grade from them.

## Implementation descriptor

An implementation descriptor may set `kind` to `advisory`. `grading` is `none`. `result` names minor 1.3 of the result format. The implementation format stays `livingproof-evaluator-implementation/1`. Placeholders and exit codes are unchanged, including `{media_dir}` under its existing conditional. See [implementation descriptor](implementation-descriptor.md).
