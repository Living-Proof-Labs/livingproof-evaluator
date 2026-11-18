# SPDX-License-Identifier: Apache-2.0
"""Review checks for plan-conformance, termination and recording 1.0.0 that no other test pins.

Each test below was a hand check during independent review. A mutation of the schema or the
rules that the existing tests let through is named in the docstring.
"""

from __future__ import annotations

import copy
import json
import re

import pytest

from integrity_rules import recording, reported
from support import (
    ROOT,
    SCHEMA_ROOT,
    assert_invalid,
    assert_valid,
    check_registry,
    load_json,
    result_schema,
)

EXAMPLES = ROOT / "examples" / "integrity"
CHECKS = SCHEMA_ROOT / "integrity" / "checks"

CATEGORIES = {
    "plan-conformance": {
        "trial-count-mismatch",
        "command-speed-mismatch",
        "index-missing",
        "index-duplicate",
        "index-out-of-range",
        "path-mismatch",
    },
    "termination": {
        "missing-stop-reason",
        "unknown-stop-reason",
        "disallowed-stop-reason",
        "stop-reason-mismatch",
    },
    "recording": {
        "mcap-incomplete",
        "missing-channel",
        "timestamps-backwards",
        "message-gap-exceeded",
        "media-file-mismatch",
        "observation-link-mismatch",
    },
}
# plan-conformance findings are about the run as a whole. The other two name a trial.
NAMES_A_TRIAL = {"plan-conformance": False, "termination": True, "recording": True}
FINDINGS_EXAMPLE = {
    "plan-conformance": "plan-conformance/findings",
    "termination": "termination/findings",
    "recording": "recording/findings",
}


def schema_of(check_id: str) -> dict:
    return load_json(CHECKS / f"{check_id}.schema.json")


def result_of(name: str) -> dict:
    return load_json(EXAMPLES / name / "result.json")


def check_in(result: dict, check_id: str) -> dict:
    return reported(result, check_id)


@pytest.mark.parametrize("check_id", sorted(CATEGORIES))
def test_each_new_check_has_exactly_its_documented_categories(check_id: str) -> None:
    """Mutations that survived: a `completeness` category added to plan-conformance or
    recording."""
    enum = schema_of(check_id)["properties"]["findings"]["items"]["properties"]["category"]["enum"]
    assert set(enum) == CATEGORIES[check_id]
    assert len(enum) == len(set(enum))


@pytest.mark.parametrize("check_id", sorted(CATEGORIES))
def test_a_trial_id_is_required_or_forbidden_as_the_issue_says(check_id: str) -> None:
    """Mutation that survived: `trial_id` no longer required on recording findings."""
    result = result_of(FINDINGS_EXAMPLE[check_id])
    assert_valid(result_schema(), result)
    doctored = copy.deepcopy(result)
    finding = check_in(doctored, check_id)["findings"][0]
    if NAMES_A_TRIAL[check_id]:
        del finding["trial_id"]
    else:
        finding["trial_id"] = "trial-01"
    assert_invalid(result_schema(), doctored)


@pytest.mark.parametrize("check_id", sorted(CATEGORIES))
def test_a_finding_is_never_a_robot_variation_even_on_a_successful_check(check_id: str) -> None:
    """Mutation that survived: the `test_system` classification const removed from each check.
    The shared rule only forces test_system when a check fails, so the check schema has to."""
    result = result_of(FINDINGS_EXAMPLE[check_id])
    doctored = copy.deepcopy(result)
    check = check_in(doctored, check_id)
    check["findings"][0]["classification"] = "robot_variation"
    assert_invalid(result_schema(), doctored)
    # A successful check whose only finding is a robot_variation passes the shared rule.
    # Only the check schema can refuse it.
    check["findings"] = check["findings"][:1]
    check["success"] = True
    check["percentage"] = 100
    assert_invalid(schema_of(check_id), check)


def test_a_referral_can_only_name_a_completeness_timeout_or_crash() -> None:
    """Mutation that survived: the referral category enum widened."""
    referral = load_json(SCHEMA_ROOT / "integrity" / "result.schema.json")["$defs"]["referral"]
    assert referral["properties"]["check"]["const"] == "completeness"
    assert set(referral["properties"]["category"]["enum"]) == {
        "ended-by-timeout",
        "ended-by-crash",
    }
    assert set(referral["required"]) == {"trial_id", "check", "category"}


def example_with_check(check_id: str) -> dict:
    for path in sorted(EXAMPLES.rglob("result.json")):
        result = load_json(path)
        if any(check["id"] == check_id for check in result["integrity"]["checks"]):
            return result
    raise AssertionError(f"no example reports {check_id}")


def test_referrals_are_refused_on_every_registered_check_but_termination() -> None:
    for entry in check_registry():
        result = copy.deepcopy(example_with_check(entry["id"]))
        check = check_in(result, entry["id"])
        for value in (
            [],
            [{"trial_id": "t", "check": "completeness", "category": "ended-by-crash"}],
        ):
            check["referrals"] = value
            if entry["id"] == "termination":
                assert_valid(result_schema(), result)
            else:
                assert_invalid(result_schema(), result)


def test_a_run_where_every_trial_timed_out_or_crashed_is_not_applicable_for_termination() -> None:
    """The referrals stay, the check has no percentage, and the run is still ERROR through
    completeness."""
    result = copy.deepcopy(result_of("termination/timeout-single-report"))
    check = check_in(result, "termination")
    check["applicable"] = False
    del check["percentage"]
    result["integrity"]["trials"] = [
        trial for trial in result["integrity"]["trials"] if trial["id"] != "trial-ended"
    ]
    assert_valid(result_schema(), result)
    assert result["integrity"]["run"]["test_system_status"] == "ERROR"
    check["percentage"] = 100
    assert_invalid(result_schema(), result)


def test_the_allowed_stop_reasons_refuse_the_runner_values() -> None:
    """The contract uses the five stop reasons. Mapping `crossed_exit`, `left_hallway`,
    `left_world`, `time_limit` and `non_finite_state` onto them is the implementation's job."""
    evidence = schema_of("termination")["$defs"]["evidence"]
    request = load_json(EXAMPLES / "termination" / "clean" / "request.json")
    good = request["integrity"]["evidence"]["termination"]
    assert_valid(evidence, good)
    for runner_value in (
        "crossed_exit",
        "left_hallway",
        "left_world",
        "time_limit",
        "non_finite_state",
        "timeout",
        "crash",
        "completed",
    ):
        doctored = copy.deepcopy(good)
        doctored["allowed_stop_reasons"] = [runner_value]
        assert_invalid(evidence, doctored)


def recording_payload() -> dict:
    request = load_json(EXAMPLES / "recording" / "findings" / "request.json")
    return copy.deepcopy(request["integrity"])


@pytest.mark.parametrize("state", ["missing", "truncated", "empty"])
def test_evidence_for_a_recording_completeness_does_not_call_present_is_ignored(state: str) -> None:
    """Mutation that survived: judging trials whose recording is not present. The shipped
    fixture leaves the missing trial out of the evidence, so the rule was never exercised."""
    payload = recording_payload()
    before = recording(payload)
    donor = next(
        entry for entry in payload["evidence"]["recording"]["trials"] if entry["id"] == "trial-gap"
    )
    extra = copy.deepcopy(donor)
    extra["id"] = "trial-absent-file"
    payload["evidence"]["recording"]["trials"].append(extra)
    for trial in payload["trials"]:
        if trial["id"] == "trial-absent-file":
            trial["recording"] = {"state": state}
            trial["recording"].pop("sha256", None)
    after = recording(payload)
    assert after == before
    assert "trial-absent-file" not in {item.get("trial_id") for item in after["findings"]}


def test_a_gap_equal_to_the_limit_is_not_a_finding() -> None:
    """Mutation that survived: `>=` instead of `>`. The check reports a gap *longer* than the
    declared limit."""
    request = load_json(EXAMPLES / "recording" / "clean" / "request.json")
    payload = copy.deepcopy(request["integrity"])
    limit = payload["evidence"]["recording"]["max_gap_seconds"]
    for entry in payload["evidence"]["recording"]["trials"]:
        for channel in entry["mcap"]["channels"]:
            channel["max_gap_seconds"] = limit
    assert recording(payload)["findings"] == []
    channel = payload["evidence"]["recording"]["trials"][0]["mcap"]["channels"][0]
    channel["max_gap_seconds"] = limit * 1.0001
    assert [item["category"] for item in recording(payload)["findings"]] == ["message-gap-exceeded"]


def test_the_contract_fixes_no_gap_limit_and_no_channel_list() -> None:
    """The limit and the channels are declared in the evidence. Nothing in the schema or the
    docs says 0.1 or names a channel."""
    schema_text = (CHECKS / "recording.schema.json").read_text()
    docs = (ROOT / "docs" / "run-integrity.md").read_text()
    recording_docs = docs.split("**`recording`.**", 1)[1].split("`success` and `percentage`", 1)[0]
    for text in (schema_text, recording_docs):
        assert not re.search(r"\b0\.1\b", text)
        assert "/base_pose" not in text
        assert "/joint_states" not in text
    schema = json.loads(schema_text)
    limit = schema["$defs"]["evidence"]["properties"]["max_gap_seconds"]
    assert "default" not in limit
    assert "const" not in limit and "enum" not in limit
    assert "default" not in schema["$defs"]["evidence"]["properties"]["required_channels"]


FIXTURE_LINE = re.compile(
    r"^- `examples/integrity/([^`]+)/`.*?percentage (?:is|stays) (\d+)", re.MULTILINE
)


def test_every_percentage_the_docs_quote_for_a_fixture_is_the_fixtures_percentage() -> None:
    """The fixtures list said plan-conformance/findings reads 10. The fixture and its test say 20."""
    lines = FIXTURE_LINE.findall((ROOT / "docs" / "run-integrity.md").read_text())
    assert len(lines) >= 3
    for name, quoted in lines:
        run = result_of(name)["integrity"]["run"]
        assert run["percentage"] == int(quoted), f"docs say {quoted} for {name}"
