# SPDX-License-Identifier: Apache-2.0
"""Review checks for the not_checked and version change (livingproof-evaluator#34).

Each test is a hand check from independent review that no other test pins. The oracles here do
not import the reference rules they check, except where the test says it compares two versions
of one rule.
"""

from __future__ import annotations

import copy
import itertools
import random

import pytest

from integrity_rules import pins, recording, termination
from support import ROOT, example_dirs, load_json

EXAMPLES = ROOT / "examples" / "integrity"
SUBJECTS = ["specs", "runner", "verifier", "world", "configuration"]
VOCABULARY = {
    "time-limit",
    "mission-done",
    "left-world",
    "simulation-broken",
    "adapter-or-scenario-done",
}


def integrity_examples():
    for example in example_dirs():
        result = load_json(example / "result.json")
        if result["evaluator"]["kind"] == "integrity":
            yield example, load_json(example / "request.json")["integrity"], result["integrity"]


# completeness has no reference rule, so nothing derived its percentage from a request.


def test_completeness_percentage_and_findings_follow_from_the_request_in_every_example() -> None:
    """Complete planned trials over planned trials, and a finding only for a trial that is not
    complete. 66.67 for one of three listed recordings missing is derived here, not typed."""
    seen = 0
    for example, request, payload in integrity_examples():
        check = next((c for c in payload["checks"] if c["id"] == "completeness"), None)
        if check is None:
            continue
        seen += 1
        precondition = request.get("evidence", {}).get("plan-conformance", {}).get("preconditions")
        if check["version"] == "1.1.0" and precondition and precondition["met"] is False:
            assert check["applicable"] is False and "percentage" not in check, example
            continue
        planned = [item["id"] for item in request["manifest"]["planned_trials"]]
        trials = {trial["id"]: trial for trial in request["trials"]}
        complete = {
            trial_id
            for trial_id in planned
            if trial_id in trials
            and trials[trial_id]["recording"]["state"] == "present"
            and trials[trial_id]["observations"]["state"] == "present"
            and trials[trial_id]["termination"] == "completed"
        }
        assert check["applicable"] is True, example
        assert check["percentage"] == pytest.approx(100 * len(complete) / len(planned)), example
        found = {item["trial_id"] for item in check["findings"]}
        assert found == set(planned) - complete, example
        assert check["success"] is (not found), example
    assert seen >= 5


def test_one_of_three_listed_recordings_missing_reads_66_67_not_100() -> None:
    request = load_json(EXAMPLES / "completeness-recording-listed-missing" / "request.json")
    states = [trial["recording"]["state"] for trial in request["integrity"]["trials"]]
    assert sorted(states) == ["missing", "present", "present"]
    result = load_json(EXAMPLES / "completeness-recording-listed-missing" / "result.json")
    check = next(c for c in result["integrity"]["checks"] if c["id"] == "completeness")
    assert round(check["percentage"], 2) == 66.67
    assert result["integrity"]["run"]["percentage"] == check["percentage"]


# pins 1.1.0 against an oracle written differently from the reference rule.


def _oracle(manifest: dict, lock: dict) -> tuple[float | None, list[str], dict[str, str]]:
    both = [s for s in SUBJECTS if s in manifest and s in lock]
    differing = [s for s in both if manifest[s] != lock[s]]
    percentage = None if not both else 100 * (len(both) - len(differing)) / len(both)
    reasons = {}
    for subject in SUBJECTS:
        if subject in manifest and subject not in lock:
            reasons[subject] = "not-declared"
        elif subject in lock and subject not in manifest:
            reasons[subject] = "not-recorded"
    return percentage, differing, reasons


def test_the_pins_rule_agrees_with_an_independent_oracle() -> None:
    rng = random.Random(2037)
    for _ in range(2000):
        manifest = {s: rng.choice("ab") for s in SUBJECTS if rng.random() < 0.7}
        lock = {s: rng.choice("ab") for s in SUBJECTS if rng.random() < 0.7}
        payload = {
            "manifest": {"pins": {s: {"sha256": v * 64} for s, v in manifest.items()}},
            "lock": {"pins": {s: {"sha256": v * 64} for s, v in lock.items()}},
        }
        got = pins(payload)
        percentage, differing, reasons = _oracle(manifest, lock)
        assert got["applicable"] is (percentage is not None)
        if percentage is None:
            assert "percentage" not in got
        else:
            assert got["percentage"] == pytest.approx(percentage)
        assert [item["subject"] for item in got["findings"]] == differing
        listed = {item["subject"]: item["reason"] for item in got["not_checked"]}
        assert {s: r for s, r in listed.items() if s in reasons} == reasons
        assert set(listed) == {s for s in SUBJECTS if s not in manifest or s not in lock}
        assert len(got["not_checked"]) == len(listed)


# termination 1.1.0 against 1.0.0: what an adopter's results can change by.


def _termination_requests():
    for example, request, _payload in integrity_examples():
        if "termination" in request.get("evidence", {}):
            yield example, request


def test_termination_1_1_0_differs_from_1_0_0_only_where_simulation_broken_was_allowed() -> None:
    """The same evidence reads the same under both versions unless a trial stopped for
    simulation-broken and the plan listed it. There the 1.0.0 result was clean and 1.1.0 is a
    disallowed-stop-reason finding."""
    differing = 0
    for example, request in _termination_requests():
        for listed in (False, True):
            payload = copy.deepcopy(request)
            allowed = payload["evidence"]["termination"]["allowed_stop_reasons"]
            if listed and "simulation-broken" not in allowed:
                allowed.append("simulation-broken")
            old = termination(payload, VOCABULARY, "1.0.0")
            new = termination(payload, VOCABULARY, "1.1.0")
            broke = [
                t["id"]
                for t in payload["evidence"]["termination"]["trials"]
                if t.get("stop_reason") == "simulation-broken"
            ]
            plan_lists_it = "simulation-broken" in allowed
            if not (broke and plan_lists_it):
                # Same verdict and findings. Only the summary of a disallowed simulation-broken
                # names the new reason ("is never allowed"), whatever the plan lists.
                assert old["percentage"] == new["percentage"], (example, listed)
                assert old["referrals"] == new["referrals"], (example, listed)
                assert finding_keys(old) == finding_keys(new), (example, listed)
                continue
            differing += 1
            assert old["percentage"] > new["percentage"], example
            extra = [f for f in new["findings"] if f not in old["findings"]]
            assert {f["trial_id"] for f in extra} == set(broke) - {
                f["trial_id"] for f in old["findings"]
            }
            assert {f["category"] for f in extra} == {"disallowed-stop-reason"}
    assert differing >= 1


# recording: what the two clarifications can and cannot change.


def finding_keys(check: dict) -> list[tuple[str, str | None]]:
    return sorted((i["category"], i.get("trial_id")) for i in check["findings"])


def _facts(times: list[float]) -> tuple[int, float, float]:
    """backward_steps in file order, the longest gap in log-time order, and in file order."""
    backward = sum(1 for a, b in itertools.pairwise(times) if b < a)
    ordered = sorted(times)
    log_gap = max((b - a for a, b in itertools.pairwise(ordered)), default=0.0)
    file_gap = max((b - a for a, b in itertools.pairwise(times)), default=0.0)
    return backward, log_gap, file_gap


def test_gap_order_never_changes_whether_a_channel_fails_only_which_findings_it_has() -> None:
    """A file with no backwards step is already in log-time order, so both readings agree. A file
    with one fails timestamps-backwards under either reading. The change is in the finding list."""
    rng = random.Random(34)
    for _ in range(3000):
        times = [round(rng.random(), 2) for _ in range(rng.randint(1, 8))]
        backward, log_gap, file_gap = _facts(times)
        if backward == 0:
            assert log_gap == pytest.approx(file_gap)
        limit = 0.1
        fails_new = backward > 0 or log_gap > limit
        fails_old = backward > 0 or file_gap > limit
        assert fails_new is fails_old


def test_a_concrete_out_of_order_channel_has_different_findings_and_the_same_verdict() -> None:
    times = [0.00, 0.05, 0.30, 0.10, 0.15, 0.20, 0.25]
    backward, log_gap, file_gap = _facts(times)
    assert backward == 1
    assert log_gap == pytest.approx(0.05) and file_gap == pytest.approx(0.25)
    request = load_json(EXAMPLES / "recording" / "clean" / "request.json")["integrity"]

    def judge(gap: float) -> list[str]:
        payload = copy.deepcopy(request)
        channel = payload["evidence"]["recording"]["trials"][0]["mcap"]["channels"][0]
        channel["backward_steps"], channel["max_gap_seconds"] = backward, gap
        payload["evidence"]["recording"]["max_gap_seconds"] = 0.1
        return sorted(item["category"] for item in recording(payload)["findings"])

    assert judge(log_gap) == ["timestamps-backwards"]
    assert judge(file_gap) == ["message-gap-exceeded", "timestamps-backwards"]


def test_reporting_a_truncation_once_does_not_change_which_trials_fail() -> None:
    request = load_json(EXAMPLES / "recording" / "clean" / "request.json")["integrity"]
    results = []
    for channels in (
        [],
        copy.deepcopy(request["evidence"]["recording"]["trials"][0]["mcap"]["channels"]),
    ):
        payload = copy.deepcopy(request)
        mcap = payload["evidence"]["recording"]["trials"][0]["mcap"]
        mcap["state"], mcap["channels"] = "incomplete", channels
        results.append(recording(payload))
    assert results[0]["percentage"] == results[1]["percentage"] == 50
    assert [i["category"] for i in results[0]["findings"]] == ["mcap-incomplete"]
    assert [i["category"] for i in results[1]["findings"]] == ["mcap-incomplete"]
