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
| `trials` | no | The observations this result read. When present, at least one entry. Each entry has `index` and `observation_sha256`. The entries are unique, and each `index` appears once. An index is at most 9007199254740991 (2^53-1). |

JSON Schema cannot require unique `index` values when the hashes differ, so the schema alone accepts a repeated index. `tools/validate_contract.py` refuses it, and a consumer MUST also refuse it: a loader that validates only against the schema has to add this check.

Plain text rejects `<`, `>`, and control characters, including newlines, DEL and the C1 controls. It also rejects U+180E, U+FEFF, lone surrogates U+D800 through U+DFFF, U+2028 and U+2029, U+200B, U+200E and U+200F, the bidi controls U+202A through U+202E, and U+2060 through U+2064 and U+2066 through U+2069. ZWJ (U+200D) and ZWNJ (U+200C) are allowed inside text. An ampersand is allowed. A value that is only whitespace, or only those joiners, is rejected. Anything valid here also passes the Reporter's presentation check. This contract is stricter than that check.

The object rejects any other key. It has no grade, no robot verdict, and no test-system status. A consumer MUST refuse a document with duplicate JSON object keys.

## Format

The result format that carries this payload is minor 1.3 or any later 1.x minor, for example `livingproof-evaluator-result/1.3.0` or `livingproof-evaluator-result/1.4.0`. Documents that already validate as 1.0, 1.1, or 1.2 still validate. An advisory document does not validate when its format is `1.2.x`.

A 1.2 reader that projects known fields ignores the unknown kind. A 1.2 consumer that validates against the v1.9.1 schema refuses the document at `evaluator/kind`. Both fail closed.

## Implementation descriptor

An implementation descriptor may set `kind` to `advisory`. `grading` is `none`. `result` names minor 1.3 or any later 1.x minor, the one version that implementation writes. The implementation format stays `livingproof-evaluator-implementation/1`. An advisory descriptor still has one trial argument list, with `{media_dir}` only under its existing conditional, and it has no media run. The scenario kind is the one that grades the robot. See [implementation descriptor](implementation-descriptor.md).
