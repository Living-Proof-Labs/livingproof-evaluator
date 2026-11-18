# SPDX-License-Identifier: Apache-2.0
"""recording 1.0.0: each trial recording is a usable MCAP file that matches media.json."""

from __future__ import annotations

import json
from collections import Counter

from integrity_rules import finding_keys, matches_rules, recording, reported
from support import (
    ROOT,
    SCHEMA_ROOT,
    assert_invalid,
    assert_valid,
    check_registry,
    load_json,
    result_schema,
)

EXAMPLES = ROOT / "examples" / "integrity" / "recording"
SCHEMA = load_json(SCHEMA_ROOT / "integrity" / "checks" / "recording.schema.json")


def load(name: str) -> tuple[dict, dict]:
    return (
        load_json(EXAMPLES / name / "request.json"),
        load_json(EXAMPLES / name / "result.json"),
    )


def test_usable_recordings_have_no_findings() -> None:
    request, result = load("clean")
    check = reported(result, "recording")
    assert check["success"] is True
    assert check["percentage"] == 100
    assert check["findings"] == []
    matches_rules(check, recording(request["integrity"]))


def test_every_finding_category_has_a_triggering_trial() -> None:
    request, result = load("findings")
    check = reported(result, "recording")
    assert finding_keys(check) == [
        ("mcap-incomplete", "trial-incomplete"),
        ("media-file-mismatch", "trial-file-mismatch"),
        ("message-gap-exceeded", "trial-gap"),
        ("missing-channel", "trial-channel"),
        ("observation-link-mismatch", "trial-link"),
        ("timestamps-backwards", "trial-backwards"),
    ]
    assert check["success"] is False
    # Seven present recordings are judged and only trial-usable has no finding.
    assert check["percentage"] == 100 * 1 / 7
    assert all(item["classification"] == "test_system" for item in check["findings"])
    matches_rules(check, recording(request["integrity"]))
    assert result["integrity"]["run"]["conclusion"] == "INCONCLUSIVE"


def test_a_recording_completeness_calls_missing_is_not_judged_here() -> None:
    request, result = load("findings")
    states = {trial["id"]: trial["recording"]["state"] for trial in request["integrity"]["trials"]}
    assert states["trial-absent-file"] == "missing"
    assert "trial-absent-file" not in {
        entry["id"] for entry in request["integrity"]["evidence"]["recording"]["trials"]
    }
    assert "trial-absent-file" not in {
        item["trial_id"] for item in reported(result, "recording")["findings"]
    }


def test_no_media_is_not_applicable_and_not_an_error() -> None:
    request, result = load("no-media")
    check = reported(result, "recording")
    assert request["integrity"]["evidence"]["recording"]["media_available"] is False
    assert check["applicable"] is False
    assert check["success"] is True
    assert "percentage" not in check
    assert check["findings"] == []
    matches_rules(check, recording(request["integrity"]))
    assert result["integrity"]["run"]["test_system_status"] == "COMPLETED"


def test_a_doctored_clean_fixture_is_caught_per_category() -> None:
    request, _ = load("clean")
    cases = {
        "mcap-incomplete": lambda e: e["mcap"].__setitem__("state", "incomplete"),
        "missing-channel": lambda e: e["mcap"]["channels"].pop(),
        "timestamps-backwards": lambda e: e["mcap"]["channels"][0].__setitem__("backward_steps", 1),
        "message-gap-exceeded": lambda e: e["mcap"]["channels"][0].__setitem__(
            "max_gap_seconds", 0.5
        ),
        "media-file-mismatch": lambda e: e["mcap"].__setitem__("bytes", 1),
        "observation-link-mismatch": lambda e: e.__setitem__(
            "evidence_observation_sha256", "0" * 64
        ),
    }
    for category, doctor in cases.items():
        payload = json.loads(json.dumps(request["integrity"]))
        doctor(payload["evidence"]["recording"]["trials"][0])
        found = Counter(item["category"] for item in recording(payload)["findings"])
        assert found[category] == 1, category
        assert recording(payload)["percentage"] == 50


def test_an_empty_channel_counts_as_missing() -> None:
    request, _ = load("clean")
    payload = json.loads(json.dumps(request["integrity"]))
    payload["evidence"]["recording"]["trials"][0]["mcap"]["channels"][0]["message_count"] = 0
    found = [item["category"] for item in recording(payload)["findings"]]
    assert found == ["missing-channel"]


def test_the_limit_and_channels_are_declared_in_the_evidence() -> None:
    request, _ = load("clean")
    evidence = request["integrity"]["evidence"]["recording"]
    assert evidence["required_channels"] == ["/base_pose", "/joint_states"]
    assert evidence["max_gap_seconds"] == 0.1
    assert_valid(SCHEMA["$defs"]["evidence"], evidence)
    without_limit = json.loads(json.dumps(evidence))
    del without_limit["max_gap_seconds"]
    assert_invalid(SCHEMA["$defs"]["evidence"], without_limit)
    no_media_with_trials = json.loads(json.dumps(evidence))
    no_media_with_trials["media_available"] = False
    assert_invalid(SCHEMA["$defs"]["evidence"], no_media_with_trials)


def test_a_robot_verdict_has_no_field_to_occupy() -> None:
    _, result = load("findings")
    document = json.loads(json.dumps(result))
    reported(document, "recording")["grade"] = "FAIL"
    assert_invalid(result_schema(), document)
    robot_class = json.loads(json.dumps(result))
    reported(robot_class, "recording")["findings"][0]["classification"] = "robot_variation"
    assert_invalid(result_schema(), robot_class)
    unknown_category = json.loads(json.dumps(result))
    reported(unknown_category, "recording")["findings"][0]["category"] = "robot-fell"
    assert_invalid(result_schema(), unknown_category)


def test_the_result_states_the_gap_limit_it_used() -> None:
    for name in ("clean", "findings"):
        request, result = load(name)
        check = reported(result, "recording")
        declared = request["integrity"]["evidence"]["recording"]["max_gap_seconds"]
        assert check["limits"] == {"max_gap_seconds": declared}, name
        assert recording(request["integrity"])["limits"] == {"max_gap_seconds": declared}, name
        assert_valid(result_schema(), result)


def test_changing_the_evidence_limit_changes_the_stated_limit() -> None:
    request, _ = load("clean")
    for limit in (0.05, 0.1, 2):
        payload = json.loads(json.dumps(request["integrity"]))
        payload["evidence"]["recording"]["max_gap_seconds"] = limit
        assert recording(payload)["limits"] == {"max_gap_seconds": limit}
    # The stated limit is the one that was judged against: 0.01 s is below the 0.02 s gaps.
    strict = json.loads(json.dumps(request["integrity"]))
    strict["evidence"]["recording"]["max_gap_seconds"] = 0.01
    result = recording(strict)
    assert result["limits"] == {"max_gap_seconds": 0.01}
    assert {item["category"] for item in result["findings"]} == {"message-gap-exceeded"}


def test_an_example_whose_stated_limit_differs_from_the_evidence_is_caught() -> None:
    request, result = load("clean")
    doctored = json.loads(json.dumps(result))
    reported(doctored, "recording")["limits"]["max_gap_seconds"] = 0.2
    # The schema alone cannot compare it with the evidence, so the reference rules do.
    assert_valid(result_schema(), doctored)
    try:
        matches_rules(reported(doctored, "recording"), recording(request["integrity"]))
    except AssertionError:
        return
    raise AssertionError("a stated limit that differs from the evidence was accepted")


def test_the_schema_requires_the_limit_when_recording_is_applicable() -> None:
    for name in ("clean", "findings"):
        _, result = load(name)
        assert_valid(result_schema(), result)
        missing = json.loads(json.dumps(result))
        del reported(missing, "recording")["limits"]
        assert_invalid(result_schema(), missing)
        empty = json.loads(json.dumps(result))
        reported(empty, "recording")["limits"] = {}
        assert_invalid(result_schema(), empty)
        for bad in (0, -0.1, "0.1", None):
            wrong = json.loads(json.dumps(result))
            reported(wrong, "recording")["limits"]["max_gap_seconds"] = bad
            assert_invalid(result_schema(), wrong)
        extra = json.loads(json.dumps(result))
        reported(extra, "recording")["limits"]["max_channel_count"] = 2
        assert_invalid(result_schema(), extra)


def test_the_schema_refuses_limits_on_every_other_check() -> None:
    limits = {"max_gap_seconds": 0.1}
    refused = 0
    for entry in check_registry():
        if entry["id"] == "recording":
            continue
        for path in sorted((ROOT / entry["examples"][0]).glob("result.json")):
            result = load_json(path)
            assert_valid(result_schema(), result)
            doctored = json.loads(json.dumps(result))
            reported(doctored, entry["id"])["limits"] = limits
            assert_invalid(result_schema(), doctored)
            refused += 1
    assert refused == len(check_registry()) - 1


def test_a_check_that_is_not_applicable_states_no_limit() -> None:
    request, result = load("no-media")
    check = reported(result, "recording")
    assert check["applicable"] is False
    assert "limits" not in check
    assert "limits" not in recording(request["integrity"])
    assert_valid(result_schema(), result)
    doctored = json.loads(json.dumps(result))
    reported(doctored, "recording")["limits"] = {"max_gap_seconds": 0.1}
    assert_invalid(result_schema(), doctored)


def test_the_contract_fixes_no_gap_limit_in_the_limits_field() -> None:
    integrity = load_json(SCHEMA_ROOT / "integrity" / "result.schema.json")
    limits = integrity["$defs"]["check"]["properties"]["limits"]
    assert "const" not in limits["properties"]["max_gap_seconds"]
    assert "enum" not in limits["properties"]["max_gap_seconds"]
