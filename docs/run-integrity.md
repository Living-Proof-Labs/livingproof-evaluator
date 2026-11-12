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
| `same-input-agreement` | 1.0.0 | Where the run is deterministic, trials with the same input hash have the same recording hash. |
| `ci-publisher` | 1.0.0 | A check run left open after the publisher received HTTP 404 is a test-system finding. |

The first three are the checks named on issue 6. `ci-publisher` is the check named in the owner's note on that issue: a GitHub or CI publisher glitch that leaves a check run open after HTTP 404 has to come back as a test-system result. Timing, broader CI job status, and infrastructure signatures in logs remain later checks, added the same way.

`completeness` percentage is 100 times the complete planned trials divided by the planned trials. `pins` percentage is 100 times the matching subjects divided by the five subjects. `same-input-agreement` percentage is 100 times the agreeing comparable groups divided by the comparable groups, and 100 when the run has no comparable group. A comparable group is two or more trials that share an input hash and have recording hashes. `ci-publisher` percentage is 100 times the check runs that were not left open after HTTP 404, divided by the check runs in the evidence.

### Same input

When `manifest.deterministic` is true:

- Recordings that differ for the same input hash are a `recording-mismatch` finding classified `test_system`. The check fails, and the run is `ERROR` and `INCONCLUSIVE`. The run is untrustworthy.
- Outcomes that differ while the recording hashes match are a `robot-variation` finding classified `robot_variation`. The check stays successful, its percentage stays 100, and the run stays `COMPLETED`. That difference is robot variation, a real result.

When `manifest.deterministic` is false, the check is not applicable, it has no percentage, and differing recordings produce no finding.

### Adding a check

1. Add `schema/integrity/checks/<id>.schema.json` with the rule, the version, the finding categories, and any evidence object.
2. Append one entry to `schema/integrity/checks/registry.json`.
3. Add the recorded run under `examples/integrity/<id>/` as `request.json` and `result.json`.
4. Add `tests/integrity/test_<id>.py` with the assertions for that rule.

The new schema is the only check schema that changes. The other check schemas, fixtures, and tests stay as they are. Evidence for the new check goes under `evidence.<id>` in the integrity request. The shared request schema already allows that object.

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

Scenario fixtures:

- `examples/scenario/graded/` has step verdicts `PASS`, `FAIL`, and `INCONCLUSIVE`.
- `examples/scenario/not-evaluated/` has a known bound step, an unknown step, and an unbound observable.

Integrity fixtures:

- `examples/integrity/clean/` reports `completeness`, `pins`, and `same-input-agreement` all successful.
- `examples/integrity/completeness/` is the run that triggers every completeness category.
- `examples/integrity/pins/` is the run whose five pin hashes differ from the lock.
- `examples/integrity/same-input-agreement/recording-mismatch/` is the triggering run for differing recordings.
- `examples/integrity/same-input-agreement/robot-variation/` is the run whose outcomes differ and whose recordings match.
- `examples/integrity/same-input-agreement/not-deterministic/` is a run that is allowed to differ.
- `examples/integrity/ci-publisher/` is the run whose check was left open after HTTP 404.

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
