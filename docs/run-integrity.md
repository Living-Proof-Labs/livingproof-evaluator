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
| `completeness` | 1.1.0 | Every planned trial has a recording and observations. None are missing, truncated, or empty. The trial ended on its own: termination `completed`. `timeout` and `crash` are test-system findings, and `completeness` is the only check that reports them. When plan-conformance's preconditions are unmet the check is not applicable. |
| `pins` | 1.1.0 | The manifest pin hashes match the verification lock for specs, runner, verifier, world, and configuration. A subject that cannot be compared is listed in `not_checked` and is not counted. |
| `same-input-agreement` | 1.0.0 | Identical recordings with different outcomes are a grader problem. Different recordings follow `robot_determinism`. |
| `ci-publisher` | 1.0.0 | A check run left open after the publisher received HTTP 404 is a test-system finding. |
| `plan-conformance` | 1.1.0 | The plan, the trials, and the lock agree on the trial count and the command speed. `trials.results[].index` is exactly 1 to N and each path is `trials/trial-NN.json` for its own index. A run whose preconditions are unmet is not applicable. |
| `termination` | 1.1.0 | Every trial that ended on its own records a stop reason, and the plan allows it. `simulation-broken` is never allowed. A timeout or crash is not reported here: the check refers to the `completeness` finding. |
| `recording` | 1.2.0 | Each present recording is a usable MCAP file: it has a valid footer, the required channels have messages, timestamps never go backwards, no gap is over the limit, and the file matches `media.json`. A recording the reader refused at a decompression cap is `recording-over-limit`. No media means not applicable. |

The first three are the checks named on issue 6. `ci-publisher` is the check named in the owner's note on that issue: a GitHub or CI publisher glitch that leaves a check run open after HTTP 404 has to come back as a test-system result. Timing, broader CI job status, and infrastructure signatures in logs remain later checks, added the same way.

### Plan conformance, termination, and recording

These three checks were registered together at 1.0.0. Termination and plan-conformance are at 1.1.0, and recording is at 1.2.0. Termination never allows `simulation-broken`; plan-conformance and recording 1.1.0 require `not_checked` (the denominator rule itself did not change for them); recording 1.2.0 adds `recording-over-limit`. Version 1.0.0 of each stays valid, and recording 1.1.0 stays valid. They are the contract for the evaluator implementation that builds them next. The contract carries the rule, the evidence, and the finding categories. Reading a trial file or an MCAP recording belongs to the implementation, which puts what it read into `evidence.<check id>`.

**`plan-conformance`.** The evidence is the plan's trial count and command speed, `trials.count`, the `trials.results` entries (`index` and `path`), and the lock's own plan when the manifest embeds a lock block.

- The plan trial count, `trials.count`, the number of `trials.results` entries, and the lock's plan trial count must agree. Each disagreeing comparison is `trial-count-mismatch`.
- The plan `command_speed` must equal the lock's, or the finding is `command-speed-mismatch`.
- The indexes must be exactly 1 to N, where N is the plan trial count: `index-missing`, `index-duplicate`, and `index-out-of-range`. Each path must be `trials/trial-NN.json` for its own index, or the finding is `path-mismatch`.
- When the manifest has no lock block, the lock comparisons are not made, are not counted, and are listed in `not_checked` as `lock-trial-count` and `lock-command-speed`. A lock with no `command_speed`, or a plan with none, lists `lock-command-speed` alone.
- A run whose preconditions are unmet runs no trials, and `evidence['plan-conformance'].preconditions.met` is `false`. The check is then not applicable, not an error.
- The findings carry no trial id. A missing or hash-mismatched trial file stays a `completeness` finding, so this check never repeats one.
- `percentage` is 100 times the subjects without a finding divided by the subjects. The subjects are the comparisons that were made, one per index 1 to N, and one per result entry whose index is outside 1 to N. A run with two disagreeing counts and nothing else wrong, out of three counts, one command speed, and four indexes, is 6 of 8 subjects clean and reads 75.

**`termination`.** The evidence is `allowed_stop_reasons`, which the plan declares, and for each trial the stop reason it records and the stop reason the manifest copies.

The stop reasons are a fixed vocabulary:

| Stop reason | Meaning |
| --- | --- |
| `time-limit` | The scenario's own time limit ran out. This is a robot outcome for the scenario evaluator, not a test-system problem. |
| `mission-done` | The mission finished. |
| `left-world` | The robot left the world. |
| `simulation-broken` | The simulation broke, for example a non-finite physics state. |
| `adapter-or-scenario-done` | The adapter or the scenario said the trial was done. |

For a trial that ended on its own (termination `completed`), the check reports:

- `missing-stop-reason`: the trial records no stop reason.
- `unknown-stop-reason`: the recorded text is outside the vocabulary.
- `disallowed-stop-reason`: the reason is in the vocabulary and the plan does not allow it. From termination 1.1.0, `simulation-broken` is never allowed, whatever the plan lists, so a broken simulation always surfaces here with the summary "The stop reason simulation-broken is never allowed." Version 1.0.0 let a plan list it and so tolerate it. The evidence may still list it and is accepted, and the list is ignored for that one reason.
- `stop-reason-mismatch`: the trial and the manifest record different reasons.

**One report for a timeout or a crash.** `completeness` still owns timeout and crash: a trial that did not finish or produced no usable result. `termination` only checks that every trial that did end records a stop reason and that the plan allows it. When a trial's termination is `timeout` or `crash`, `termination` raises no finding of its own for it. It lists the trial under `referrals`, with the `completeness` category (`ended-by-timeout` or `ended-by-crash`) that reports it, so each event is reported once. This follows from the two words meaning different things: a `time-limit` stop is the scenario ending the trial on its own, and a `timeout` is the trial not finishing at all.

- `referrals` is only allowed on `termination`, and `termination` always has it, empty when there is nothing to refer. A referral is not a finding: it does not change `success` or `percentage`.
- A result that has a referral also reports `completeness` with the finding it points at. Across `completeness` and `termination`, a trial that timed out or crashed has exactly one finding.
- `percentage` counts only the trials that ended on their own. When none did, the check is not applicable.

**`recording`.** The evidence declares the `required_channels` and the `max_gap_seconds` limit, says whether media was available, and carries for each trial what an MCAP reader found (state, size, sha256, and per channel the message count, the number of backwards timestamps, and the longest gap), the size and hashes that `media.json` records, the observation hash from the run evidence, and, when the reader stopped at a decompression cap, `over_limit` (the limit that was hit and its value).

- `mcap-incomplete`: the file does not open or has no valid footer and summary.
- `missing-channel`: a required channel is absent or has no messages.
- `timestamps-backwards`: a channel has messages whose log time is earlier than the message before it.
- `message-gap-exceeded`: a channel has a gap longer than the declared limit.
- `media-file-mismatch`: the file's size or sha256 differs from `media.json`.
- `observation-link-mismatch`: `observation_sha256` in `media.json` differs from the run evidence for that trial.
- `recording-over-limit`: the reader refused the file because a decompression cap was hit. The finding is 1.2.0 only. The evidence names the limit (`chunk-bytes`, `total-bytes`, `records`, or `chunks`) and its value in `over_limit`, and the summary names both. The trial is judged and fails closed. This is not truncation: `recording.state` stays `present`, `completeness` does not report `truncated-recording`, and this check does not also emit `missing-channel` or other findings for that trial, because the read stopped. Version 1.1.0 does not emit this finding.
- Only trials whose recording `completeness` reports as present are judged. A missing, truncated, or empty recording stays a `completeness` finding, and the trial is listed in `not_checked` with reason `not-present` (1.1.0). A present recording that the evidence has no entry for is listed with reason `not-recorded`. A recording that `media.json` lists and that is missing from the media output is a trial that was not judged, so it has this home. It is also a `completeness` finding (see below), so it is never only a remark in a summary.
- Without media (`media_available` is `false`, with no trials) the check is not applicable, not an error.
- Gaps are measured in log-time order: the messages on a channel are ordered by log time before the gaps are taken, so a write that is out of file order is not a capture gap. Timestamps that go backwards are counted in file order and reported as `timestamps-backwards`.
- **`completeness` owns a file that exists but has no valid footer.** The producer classifies it while reading (`recording.state` is `truncated`), `completeness` reports `truncated-recording`, and the run is incomplete. From 1.1.0 this check does not judge that trial. It lists it in `not_checked` as `not-present`, so the truncation is reported once, and it no longer emits `mcap-incomplete`. `mcap-incomplete` is a finding of 1.0.0 only. The producer must do that classification. An evidence entry that says `incomplete` for a trial whose `recording.state` is `present` is inconsistent, so from 1.1.0 the request is malformed (see Malformed requests below), except from 1.2.0 when `over_limit` is set: the reader stopped, so the footer may be unknown, and the trial is a `recording-over-limit` finding. From 1.1.0, an evidence entry for a trial that is not in `trials`, or a missing or unknown `mcap.state`, is also malformed.
- Every trial that was not judged is listed in `not_checked`, also when nothing was judged. The check is then not applicable, has no percentage, and the list says why. `examples/integrity/recording/none-judged/` is this case. When there is no media at all, the whole check is not applicable and the list is empty.
- The check judges structure, channels, and time. It does not judge what the recorded motion means, and the channel list and the gap limit are declared in the evidence and are not part of the check version.
- The result states the limit it used: `limits.max_gap_seconds`, always equal to `evidence.recording.max_gap_seconds`. It is required whenever the check is applicable and absent when it is not. `limits` is only allowed on `recording`. The limit in the example data is a proposal that has not been approved.

`success` and `percentage` follow the rule for every check: a check with a finding has `success` false, and a not-applicable check has no percentage.

### Not-checked subjects and the percentage denominator

A check can be unable to look at a subject. The pin the lock does not declare, the pin the run did not record, the recording that is not there to read. Such a subject is not a finding, because nothing was found, and it is not a clean one, because nothing was looked at. A check object lists it in `not_checked`.

```json
{"subject": "verifier", "reason": "not-declared"}
{"trial_id": "trial-02", "reason": "not-present"}
```

An item has `reason` and exactly one of `subject` (a check whose subjects are named) and `trial_id` (a check whose subjects are trials). The reasons are:

- `not-recorded`: the run's own record has no value to compare.
- `not-declared`: the plan or the lock has no value to compare with.
- `not-present`: there is no readable recording, because it is missing, truncated or empty (a file with no valid footer is truncated), and `completeness` reports that.

**The rule.** `percentage` is 100 times the checked subjects without a finding divided by the checked subjects. A subject that was not checked is outside the denominator. It does not count as a mismatch and it does not count as a match. A check with no checked subject is not applicable and has no percentage. A subject is never both a finding and not checked. A pin that neither the manifest nor the lock carries is not checked with reason `not-declared`, because the lock is tested first and there is nothing declared to compare with. This is the rule for every check, and `not_checked` is how a check says which subjects it left out.

**Worked example.** Three pin subjects can be checked: runner, world, and configuration. The world hashes differ, and runner and configuration match. The specs hash is in the lock and the run did not record it, and the verifier hash is in the manifest and the lock does not declare it. Those two are not checked.

- Divided by the five subjects, as `pins` 1.0.0 did, one mismatch with two subjects unchecked reads 40. That treats a pin nobody compared as a pin that failed.
- Divided by the checked subjects, as `pins` 1.1.0 does, two of the three checked subjects are clean and the check reads 66.67.

`examples/integrity/pins-not-checked/` is this case. With nothing checked, `examples/integrity/pins-none-checked/` shows a check that is not applicable and lists all five subjects.

**Which checks.** `not_checked` is allowed on `pins`, `plan-conformance`, and `recording`, the checks that can skip a subject, and the envelope rejects it elsewhere. It is required from 1.1.0 on all three, and an empty list means every subject was checked. It is not allowed at 1.0.0 of any of them, so one version label is one schema.

| Check | Already followed the denominator rule? | What `not_checked` holds |
| --- | --- | --- |
| `pins` | No. 1.0.0 divided by five. | Pin subjects with `not-recorded` or `not-declared`. |
| `plan-conformance` | Yes. Only the comparisons that were made are subjects. | `lock-trial-count` and `lock-command-speed` with `not-declared`. |
| `termination` | Yes. Only trials that ended on their own count, and a timeout or crash is a referral. | Nothing. The check has no skipped subject, so it does not report the field. |
| `recording` | Yes. Only recordings completeness reports as present are judged. | Trials with `not-present` or `not-recorded`. |
| `completeness` | Not a denominator question: planned trials are all subjects. | Nothing. See below for when it applies. |

The denominator rule itself needed no change for plan-conformance, termination and recording: their 1.0.0 rule already counted only what they judged. plan-conformance and recording move to 1.1.0 because `not_checked` is now required on them, and termination because of `simulation-broken`.

The schema enforces two of the pins rules: a pins check that is not applicable lists all five subjects, and an applicable one does not. The other rules are rule-level, which means the reference rules and the tests check them and the schema does not: a subject is never both a finding and not checked, a subject is listed once, and the percentage equals the rule's value.

**Versions and migration.** The change is additive for results that exist.

- `pins` 1.1.0 changes the denominator and requires `not_checked`. `plan-conformance` 1.1.0 and `recording` 1.1.0 require `not_checked` and change nothing else about the percentage. A run that records all five pins on both sides reads the same percentage under 1.0.0 and 1.1.0. The two differ only when a subject is not checked, which 1.0.0 could not express because the request required all five pins. The request no longer requires them: any of the five may be left out of the manifest or the lock.
- The registry lists `previous_versions` for a check, and a result at one of them validates against the same schema. 1.0.0 results of `pins`, `completeness`, `termination`, `plan-conformance` and `recording` stay valid, and a result must not carry `not_checked` at 1.0.0. The 1.0.0 examples are kept as they were published; the 1.1.0 readings have their own examples.
- A producer moves to `pins`, `plan-conformance` or `recording` 1.1.0 by setting the version and reporting `not_checked`. For `recording` it also stops judging a file with no valid footer and leaves it to `completeness`. A consumer that ignores unknown fields reads a 1.1.0 result and sees only a different percentage.
- A producer moves to `recording` 1.2.0 by setting the version and reporting `recording-over-limit` for a present recording the reader refused at a decompression cap, instead of classifying that file as truncated. 1.0.0 and 1.1.0 results stay valid.

**Completeness follows plan-conformance (completeness 1.1.0).** A run whose preconditions are unmet runs no trials. Under 1.0.0 `completeness` still judged it, so every planned trial was a `missing-trial`, Run Integrity read ERROR, and the verifier grades that run UNSUPPORTED. From 1.1.0 `completeness` is not applicable when `evidence['plan-conformance'].preconditions.met` is `false`, which is the same condition that makes `plan-conformance` not applicable. When the preconditions are met, or the evidence says nothing, it judges as before. `examples/integrity/completeness-preconditions-unmet/` is this case: both checks are not applicable, nothing is wrong with a trial that never ran, and the run reads COMPLETED and 100. That reading means no applicable check failed. It does not mean the run was trustworthy, so a consumer that needs to tell the two apart reads `applicable`.

**Recordings the manifest lists (completeness).** `completeness` reads the recordings the manifest lists. A listed recording that is missing is `missing-recording`, a truncated one is `truncated-recording`, and an empty one is `empty-recording`, as for a request's `trials[].recording.state`. A run with a listed recording missing is incomplete: with one of three listed recordings missing, `completeness` reads 66.67 and the run is ERROR and INCONCLUSIVE, not COMPLETED and 100. A remark in a summary is not enough, and a recording that `recording` lists in `not_checked` as `not-present` always has this finding in the same result. `examples/integrity/completeness-recording-listed-missing/` is this case, and `recording` reads 100 over the two recordings it judged. An implementation that reads a manifest takes the listing from `media.json`.

**`simulation-broken` (termination 1.1.0).** A plan cannot allow a broken simulation. From 1.1.0 it is a `disallowed-stop-reason` finding for every trial that records it, so it always surfaces as a failure. `examples/integrity/termination/simulation-broken/` is a plan that lists it and a trial that records it.

`completeness` percentage is 100 times the complete planned trials divided by the planned trials. `pins` percentage is 100 times the matching checked subjects divided by the checked subjects (1.0.0: divided by five). `same-input-agreement` percentage is 100 times the agreeing comparable groups divided by the comparable groups, and 100 when the run has no comparable group. A comparable group is two or more trials that share an input hash and have recording hashes. `ci-publisher` percentage is 100 times the check runs that were not left open after HTTP 404, divided by the check runs in the evidence.

### Validating a result

Validating an integrity result is two steps, and both are part of the contract. The envelope schema checks the shared fields, rejects a check id that is not in `schema/integrity/checks/registry.json`, and rejects verdict-like categories. Then each check object is validated against that registry entry's schema, which is what binds the category to `test_system` or `robot_variation`.

`tools/validate_contract.py` does both steps. `validate_document` returns the errors. The command is `uv run python tools/validate_contract.py <result.json>`.

`tools/validate_contract.py` accepts a check's current version and each of its registry `previous_versions`.

A consumer of major version 1 accepts any format `livingproof-evaluator-result/1.<minor>` or the matching request format. It ignores unknown fields and an unknown `kind`. Result `1.1.0` adds an optional `descriptor` on the result. The object, the SVG subset, and the way it sits beside `display_name` and `kind` are in [docs/evaluator-descriptor.md](evaluator-descriptor.md). A 1.0 reader drops that object. Health and an observations-only evaluator remain a later minor: a new kind, a new payload, and a format such as `1.2.0`. A 1.0 reader skips that kind instead of failing the document. The strict schema still rejects an unknown kind, which is how a producer stays closed. The consumer rule is what keeps the minor bump compatible.

`execution` uses `agentic`. capability-verifier names the same assessor type `agent`. This contract does not accept `agent` in `execution`.

### Malformed requests

A request can be well-formed JSON that passes the request schema and still contradict itself. Some of those contradictions would leave a fact with no check reporting it, so a check does not guess. It treats the request as malformed. An evaluator then writes **no result** and exits with **status 2**, the same as for any other malformed request. A result with a made-up reading is worse than no result.

The request schema cannot say these rules, because the two facts sit in different arrays or because a published request has to stay valid under the version that accepted it. The reference rules in `tests/integrity_rules.py` raise `MalformedRequest` (a `ValueError`) instead, and the tests pin each one. The rule is part of the check's version.

| Check | Version | Malformed request |
| --- | --- | --- |
| `recording` | 1.1.0 and 1.2.0 | A trial whose `recording.state` is `present` while `evidence.recording` says its MCAP file is `incomplete`, unless from 1.2.0 `over_limit` is set. A file with no valid footer is `truncated`, which the producer sets while reading and `completeness` reports. Listing the trial as `not-present` would leave nothing reporting it. A present over-limit trial may say `incomplete` because the reader stopped. |
| `recording` | 1.1.0 and 1.2.0 | An `evidence.recording.trials` entry whose `id` is not in `trials`. Silently ignoring it would drop evidence for an unknown trial. |
| `recording` | 1.1.0 and 1.2.0 | An `evidence.recording.trials` entry whose `mcap.state` is missing, or is not `complete` or `incomplete`. The request schema rejects these first. The reference rule raises `MalformedRequest` as well, naming the trial and the actual state (`missing` when the key is absent), instead of a `KeyError` or a message that calls the file incomplete. |

`recording` 1.0.0 keeps its published behaviour: the same request is judged and gives `mcap-incomplete`, and an evidence entry for a trial not in `trials` is ignored. So the published 1.0.0 `recording/findings` request is valid and is judged at 1.0.0, and an evaluator at 1.1.0 or 1.2.0 rejects it, unless at 1.2.0 the trial also carries `over_limit`. One inconsistent trial rejects the whole request. An `incomplete` entry for a trial in `trials` that is `missing`, `truncated` or `empty` is not inconsistent: the trial is not present, so the entry is not read.

### Adding a check

1. Add `schema/integrity/checks/<id>.schema.json` with the rule, the version, the finding categories, and any evidence object.
2. Append one entry to `schema/integrity/checks/registry.json`, and add the id to the check id enum in `schema/integrity/result.schema.json`.
3. Add the example under `examples/integrity/<id>/` as `request.json` and `result.json`.
4. Add `tests/integrity/test_<id>.py` with the assertions for that rule.

The other check schemas, fixtures, and tests stay as they are. Evidence for the new check goes under `evidence.<id>`. A check that needs a new finding field, or a pin subject outside the five names, edits the shared finding definition in `schema/integrity/result.schema.json`. `referrals` and `limits` are the check-level fields that are not findings: the shared check definition allows `referrals` on `termination` only, and `limits` on `recording` only, when it is applicable. The category text must not contain the verdict words `pass`, `fail`, `verdict`, `grade`, or `success`.

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
- `examples/integrity/pins-partial/` is example data whose specs and world hashes differ and whose other three pins match, so the percentage is 60. It is a `pins` 1.0.0 result.
- `examples/integrity/pins-not-checked/` is example data for `pins` 1.1.0. One of three checked subjects differs and two are not checked, so the check reads 66.67.
- `examples/integrity/pins-none-checked/` is example data for `pins` 1.1.0 with no pin recorded by the manifest. The check is not applicable and lists all five subjects.
- `examples/integrity/completeness-recording-listed-missing/` is example data for `completeness` 1.1.0 with one of three listed recordings missing. `completeness` reports it, `recording` lists it in `not_checked`, and the run is ERROR.
- `examples/integrity/completeness-preconditions-unmet/` is example data for `completeness` 1.1.0. A run with unmet preconditions has `completeness` and `plan-conformance` both not applicable.
- `examples/integrity/same-input-agreement/recording-mismatch/` is example data for different recordings with the robot declared deterministic.
- `examples/integrity/same-input-agreement/grader-disagreement/` is example data for identical recordings and different outcomes.
- `examples/integrity/same-input-agreement/robot-variation/` is example data for different recordings with `robot_determinism` set to `non-deterministic`. The percentage stays 100.
- `examples/integrity/same-input-agreement/undeclared/` is example data for a simulation that omits `robot_determinism`.
- `examples/integrity/plan-conformance/conformant/` is example data in which the plan, the trials, and the lock agree.
- `examples/integrity/plan-conformance/findings/` is example data that triggers every plan-conformance category. Two of its 10 subjects are clean (the number of `trials.results` entries, and index 1), so the percentage is 20.
- `examples/integrity/plan-conformance/preconditions-unmet/` is example data for a run that ran no trials. The check is not applicable.
- `examples/integrity/plan-conformance/no-lock/` is example data for `plan-conformance` 1.1.0 with no lock block. The lock comparisons are listed in `not_checked`.
- `examples/integrity/plan-conformance/lock-checked/` is example data for `plan-conformance` 1.1.0 where every comparison was made. `not_checked` is empty.
- `examples/integrity/termination/clean/` is example data in which every allowed stop reason is clean.
- `examples/integrity/termination/findings/` is example data that triggers every termination category.
- `examples/integrity/termination/simulation-broken/` is example data for `termination` 1.1.0: the plan lists `simulation-broken`, a trial records it, and it is a finding.
- `examples/integrity/termination/timeout-single-report/` is example data with one timeout and one crash. `completeness` reports each once, and `termination` refers to both and has no finding.
- `examples/integrity/recording/clean/` is example data for two usable recordings.
- `examples/integrity/recording/findings/` is the `recording` 1.0.0 example as published: it triggers every 1.0.0 category, including `mcap-incomplete`, plus a trial whose recording is missing and is left to `completeness`.
- `examples/integrity/recording/not-checked/` is example data for `recording` 1.1.0: five categories, a truncated file and a missing recording. `completeness` reports both, and `recording` lists both as `not-present` and judges the other six.
- `examples/integrity/recording/none-judged/` is example data for `recording` 1.1.0 where every recording is missing or truncated. The check is not applicable and lists both trials.
- `examples/integrity/recording/no-media/` is example data for a run without media. The check is not applicable.
- `examples/integrity/recording/over-limit/` is example data for `recording` 1.2.0: one present recording is over the reader's chunk-bytes limit. The check reports `recording-over-limit`, judges both trials, and `completeness` does not report `truncated-recording`.
- `examples/integrity/ci-publisher/` is the contract shape of a real run. On 2026-11-12 at 02:08:22Z (13:08:22 AEDT), job `130921936148` of [capability-report run 43139248932](https://github.com/Living-Proof-Labs/livingproof-capability-report/actions/runs/43139248932) logged `HttpError: Not Found` while updating a check-run conclusion. The log names the report `Reporter tests (amd64)`. The check-run API, read on 2026-11-12, still shows check run `130922092615` (`Reporter tests (amd64)`, started 02:08:22Z) and check run `130922085540` (`Reporter tests (arm64)`, started 02:08:20Z) as `in_progress` with no conclusion. The job log does not print those numeric ids. The ids and the `in_progress` status come from the API. The HTTP error line comes from the job log.

Descriptor fixtures, all example data, are listed in [docs/evaluator-descriptor.md](evaluator-descriptor.md). They are 1.1 results. Their payloads are copies of the graded scenario fixture, the partial pins fixture, and the clean integrity fixture.

Recording and manifest hashes on the scenario examples are the sha256 of the URI text. This repository does not ship the MCAP or the run manifest bytes. Integrity examples hash the embedded manifest, lock, trials, and evidence, and the tests check those hashes.

The icon in every example is a placeholder rectangle. The publisher owns the real mark.

## Open questions

- The five pin hashes need a canonical byte string. Published locks record commits for specs, runner, verifier, and world, a configuration sha256, and a verifier image digest. This contract compares sha256 values that both the manifest and the lock already carry.
- A crash caused by the robot's controller and a crash caused by the simulator or the runner still need a way to be told apart. Timeout and crash are completeness findings here. The evaluator proposal leaves that distinction open. `termination` does not draw it either: it refers every timeout and crash to `completeness`.
- Published runs need a home for `manifest.deterministic`. The proposal treats a certification run as deterministic.
- An implementation that always emits `ci-publisher` needs a result for a run that has no CI record. The contract allows the check to be absent, or present with `applicable` false. It does not treat missing CI evidence as a failed check.
- The report label for `robot_variation` is part of the display design.
- Outcome strings are compared for equality. The scenario vocabulary owns their meaning.
- The first implementation corpus is the published G1, Go1, and T1 runs, plus a doctored run. Those runs are not fixtures in this repository.
