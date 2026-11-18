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
        ("media-file-mismatch", "trial-file-mismatch"),
        ("mcap-incomplete", "trial-incomplete"),
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
