# Run integrity

Run integrity grows one check at a time. Every time we lose time to something that wasn't the robot, the follow-up is a new integrity check, plus the run that would have caught it.

Use that paragraph as the opening paragraph of the integrity evaluator repository's README.

This note is the contract for that evaluator. It also records the shared envelope that lets a scenario evaluator and an integrity evaluator return results side by side. The repository holds the contract. An implementation, a report layout, and a new repository are outside this change. Art is designing the display.

## Two evaluator kinds, one envelope

A request uses `livingproof-evaluator-request/1.0.0`. A result uses `livingproof-evaluator-result/1.0.0`. Both carry:

- evaluator id, version, and kind
- execution, `deterministic` or `agentic`
- display name, publisher, and an SVG icon
- the inputs the evaluator reads, each as a role, a URI, and a sha256
- timestamps: `requested_at` on a request, `started_at` and `completed_at` on a result

`kind` selects the payload.

**Scenario.** The payload is one trial. The evaluator grades that trial's steps against its recording and returns a robot result for each step: `PASS`, `FAIL`, `INCONCLUSIVE`, or `NOT_EVALUATED`. `NOT_EVALUATED` is the not-evaluated result. Its reason is `unknown_step` or `unbound_observable`. The scenario payload has step verdicts and has no test-system status. Folding those verdicts into a grade stays deferred.

**Integrity.** The payload is one run's manifest, verification lock, and trial evidence, plus the checks that were reported. It reports test-system status for the run and for each planned trial, together with findings. `success` is test-system success. `percentage` is a share from 0 to 100. The run percentage is the minimum percentage among the applicable checks in that result. When every reported check is not applicable, the run percentage is 100. A result whose checks succeeded has test-system status `COMPLETED`. A result with a failed check has test-system status `ERROR` and conclusion `INCONCLUSIVE`.

The integrity schemas reject `verdict`, `grade`, `pass`, and `fail`. Finding categories are lowercase slugs, so a robot verdict token has no field to occupy. An integrity result also rejects the scenario payload, and a scenario result rejects the integrity payload.

`kind` is `scenario` or `integrity` because those are the two payloads. `execution` keeps the separate distinction between a fixed procedure and an agentic one. A new integrity check leaves the envelope unchanged. A further evaluator kind would be a new envelope version.

## Checks

Each integrity check is a small rule with its own id, version, schema, recorded run, and test.

| Id | Version | Rule |
| --- | --- | --- |
| `completeness` | 1.0.0 | Every planned trial has a recording and observations. None are missing, truncated, or empty. The trial ended on its own: termination `completed`. `timeout` and `crash` are test-system findings. |
| `pins` | 1.0.0 | The manifest pin hashes match the verification lock for specs, runner, verifier, world, and configuration. |
| `same-input-agreement` | 1.0.0 | Identical recordings with different outcomes are a grader problem. Different recordings follow `robot_determinism`. |
| `ci-publisher` | 1.0.0 | A check run left open after the publisher received HTTP 404 is a test-system finding. |

The first three are the checks named on issue 6. `ci-publisher` is the check named in the owner's note on that issue: a GitHub or CI publisher glitch that leaves a check run open after HTTP 404 has to come back as a test-system result. Timing, broader CI job status, and infrastructure signatures in logs remain later checks, added the same way.

`completeness` percentage is 100 times the complete planned trials divided by the planned trials. `pins` percentage is 100 times the matching subjects divided by the five subjects. `same-input-agreement` percentage is 100 times the agreeing comparable groups divided by the comparable groups, and 100 when the run has no comparable group. A comparable group is two or more trials that share an input hash and have recording hashes. `ci-publisher` percentage is 100 times the check runs that were not left open after HTTP 404, divided by the check runs in the evidence.

### Same input

The manifest carries `robot_determinism`, either `deterministic` or `non-deterministic`. On a simulation, and `environment` defaults to simulation when it is omitted, a missing declaration is treated as deterministic so the mismatch is investigated.

- The same input and the same recording with different outcomes is `outcome-disagreement`, classified `test_system`. The robot did the same thing, so the difference comes from the grader. The check fails and the run is `ERROR` and `INCONCLUSIVE`.
- Different recordings for the same input, when the robot is declared deterministic or the declaration is omitted on a simulation, are `recording-mismatch`, classified `test_system`. The run is inconclusive.
- Different recordings for the same input, when the robot is declared `non-deterministic`, are `robot-variation`. The check stays successful, its percentage stays 100, and the run stays `COMPLETED`. The finding is how the result reports the variation. It does not lower the success rate.

`success` on a run, trial, or check is a boolean. It is the test-system success flag. The word `success` is rejected as a finding category, along with `failure`, `robot-fail`, and the other verdict words, so it cannot be stored as a verdict. A document may still contain `"success": true`.

### Validating a result

Validating an integrity result is two steps, and both are part of the contract. The envelope schema checks the shared fields, rejects a check id that is not in `schema/integrity/checks/registry.json`, and rejects verdict-like categories. Then each check object is validated against that registry entry's schema, which is what binds the category to `test_system` or `robot_variation`.

`tools/validate_contract.py` does both steps. `validate_document` returns the errors. The command is `uv run python tools/validate_contract.py <result.json>`.

A consumer of major version 1 accepts any format `livingproof-evaluator-result/1.<minor>` or the matching request format. It ignores unknown fields and an unknown `kind`. Result `1.1.0` adds an optional `descriptor` on the result. The object, the SVG subset, and the way it sits beside `display_name` and `kind` are in [docs/evaluator-descriptor.md](evaluator-descriptor.md). A 1.0 reader drops that object. Health and an observations-only evaluator remain a later minor: a new kind, a new payload, and a format such as `1.2.0`. A 1.0 reader skips that kind instead of failing the document. The strict schema still rejects an unknown kind, which is how a producer stays closed. The consumer rule is what keeps the minor bump compatible.

`execution` uses `agentic`. capability-verifier names the same assessor type `agent`. This contract does not accept `agent` in `execution`.

### Adding a check

1. Add `schema/integrity/checks/<id>.schema.json` with the rule, the version, the finding categories, and any evidence object.
2. Append one entry to `schema/integrity/checks/registry.json`, and add the id to the check id enum in `schema/integrity/result.schema.json`.
3. Add the example under `examples/integrity/<id>/` as `request.json` and `result.json`.
4. Add `tests/integrity/test_<id>.py` with the assertions for that rule.

The other check schemas, fixtures, and tests stay as they are. Evidence for the new check goes under `evidence.<id>`. A check that needs a new finding field, or a pin subject outside the five names, edits the shared finding definition in `schema/integrity/result.schema.json`. The category text must not contain the verdict words `pass`, `fail`, `verdict`, `grade`, or `success`.

## Where the implementation should live

The contract stays in this repository. The implementation should live in a new repository, `livingproof-evaluator-run-integrity`, created after the owner approves it. That split matches `livingproof-evaluator-scenario`: this repository owns the wire format, and the implementation repository owns the version, the tests against published runs, and the icon the publisher ships.

Other candidates, and the trade-off each one carries:

- A package in `capability-verifier`. The call site is already there, and the verifier is what stores evaluator results. The package would release together with the program that folds step verdicts into a robot grade, which puts the integrity opinion in the same repository as that grade.
- A package in `livingproof-sim-mujoco`. The parked runner rule that flags disagreeing trials lives there today, so the replacement would sit next to the code it retires. The publisher check is a GitHub result, and later runs can come from producers other than MuJoCo.
- An implementation package in this repository. This repository is the contract: the shared vocabulary, the binding format, and evaluator input and output.
- A package in `livingproof-common`. The evaluator proposal keeps that repository for dependency-free utilities.

Recommendation: `livingproof-evaluator-run-integrity`, after owner approval. Until that approval, the implementation has nowhere to land, and this repository still does not gain one.

## How it plugs into the pipeline

The scenario evaluator reads one trial's recording, the merged observation binding, the scenario, and the run manifest. Those are the envelope inputs, with the steps and the binding in the scenario payload. It can run once that trial's recording and binding exist. It returns the scenario payload of step verdicts.

The integrity evaluator reads the run manifest, the verification lock, and the trial evidence in the integrity payload. A check reads `evidence.<check id>` when it has any. It can run once the run has its manifest, lock, and trial evidence. It does not read scenario verdicts.

`capability-verifier` calls each evaluator, keeps each envelope result, and leaves the two opinions separate. The report shows them separately. That layout is Art's work and is outside this contract.

The MuJoCo runner currently exits when identical trials disagree and records that as a test-system reproducibility finding. Check `same-input-agreement` is the replacement. Retiring the runner exit is a change in `livingproof-sim-mujoco` after this contract is accepted.

Outages and infrastructure failures are the cases this contract is for. A missing, truncated, or empty recording, a missing trial, a timeout, a crash, a pin hash that differs from the lock, a nondeterministic recording, or a check run left open after HTTP 404 comes back as a test-system result. That is the signal that investigation time belongs on the test system.

## Examples

Every fixture under `examples/` except the publisher case is example data. The hashes, run ids, trial outcomes, and URIs are synthetic. They are not recordings from a published G1, Go1, or T1 run.

Scenario fixtures, all example data:

- `examples/scenario/graded/` has step verdicts `PASS`, `FAIL`, and `INCONCLUSIVE`.
- `examples/scenario/not-evaluated/` has a known bound step, an unknown step, and an unbound observable.

Integrity fixtures, example data unless noted:

- `examples/integrity/clean/` reports `completeness`, `pins`, and `same-input-agreement` all successful.
- `examples/integrity/completeness/` triggers every completeness category.
- `examples/integrity/pins/` has five pin hashes that differ.
- `examples/integrity/pins-partial/` is example data whose specs and world hashes differ and whose other three pins match, so the percentage is 60.
- `examples/integrity/same-input-agreement/recording-mismatch/` is example data for different recordings with the robot declared deterministic.
- `examples/integrity/same-input-agreement/grader-disagreement/` is example data for identical recordings and different outcomes.
- `examples/integrity/same-input-agreement/robot-variation/` is example data for different recordings with `robot_determinism` set to `non-deterministic`. The percentage stays 100.
- `examples/integrity/same-input-agreement/undeclared/` is example data for a simulation that omits `robot_determinism`.
- `examples/integrity/ci-publisher/` is the contract shape of a real run. On 2026-11-12 at 02:08:22Z (13:08:22 AEDT), job `130921936148` of [capability-report run 43139248932](https://github.com/Living-Proof-Labs/livingproof-capability-report/actions/runs/43139248932) logged `HttpError: Not Found` while updating a check-run conclusion. The log names the report `Reporter tests (amd64)`. The check-run API, read on 2026-11-12, still shows check run `130922092615` (`Reporter tests (amd64)`, started 02:08:22Z) and check run `130922085540` (`Reporter tests (arm64)`, started 02:08:20Z) as `in_progress` with no conclusion. The job log does not print those numeric ids. The ids and the `in_progress` status come from the API. The HTTP error line comes from the job log.

Descriptor fixtures, all example data, are listed in [docs/evaluator-descriptor.md](evaluator-descriptor.md). They are 1.1 results. Their payloads are copies of the graded scenario fixture, the partial pins fixture, and the clean integrity fixture.

Recording and manifest hashes on the scenario examples are the sha256 of the URI text. This repository does not ship the MCAP or the run manifest bytes. Integrity examples hash the embedded manifest, lock, trials, and evidence, and the tests check those hashes.

The icon in every example is a placeholder rectangle. The publisher owns the real mark.

## Open questions

- The five pin hashes need a canonical byte string. Published locks record commits for specs, runner, verifier, and world, a configuration sha256, and a verifier image digest. This contract compares sha256 values that both the manifest and the lock already carry.
- A crash caused by the robot's controller and a crash caused by the simulator or the runner still need a way to be told apart. Timeout and crash are completeness findings here. The evaluator proposal leaves that distinction open.
- Published runs need a home for `manifest.deterministic`. The proposal treats a certification run as deterministic.
- An implementation that always emits `ci-publisher` needs a result for a run that has no CI record. The contract allows the check to be absent, or present with `applicable` false. It does not treat missing CI evidence as a failed check.
- The report label for `robot_variation` is part of the display design.
- Outcome strings are compared for equality. The scenario vocabulary owns their meaning.
- The first implementation corpus is the published G1, Go1, and T1 runs, plus a doctored run. Those runs are not fixtures in this repository.
