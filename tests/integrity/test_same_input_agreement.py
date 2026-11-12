# SPDX-License-Identifier: Apache-2.0
"""same-input-agreement 1.0.0: recording mismatch and robot variation."""

from __future__ import annotations

from support import ROOT, load_json

BASE = ROOT / "examples" / "integrity" / "same-input-agreement"


def _pair(name: str) -> tuple[dict, dict]:
    example = BASE / name
    return load_json(example / "request.json")["integrity"], load_json(example / "result.json")[
        "integrity"
    ]


def _recording_hashes(payload: dict) -> list[str]:
    return [trial["recording"]["sha256"] for trial in payload["trials"]]


def _outcomes(payload: dict) -> list[str]:
    return [trial["outcome"] for trial in payload["trials"]]


def test_recordings_that_differ_are_a_test_system_finding() -> None:
    request, result = _pair("recording-mismatch")
    assert request["manifest"]["deterministic"] is True
    assert len({trial["input_sha256"] for trial in request["trials"]}) == 1
    assert len(set(_recording_hashes(request))) > 1
    assert len(set(_outcomes(request))) == 1
    finding = result["checks"][0]["findings"][0]
    assert finding["category"] == "recording-mismatch"
    assert finding["classification"] == "test_system"
    assert result["checks"][0]["success"] is False
    assert result["checks"][0]["percentage"] == 0
    assert result["run"]["success"] is False
    assert result["run"]["test_system_status"] == "ERROR"
    assert result["run"]["conclusion"] == "INCONCLUSIVE"
    assert all(trial["success"] is True for trial in result["trials"])


def test_outcomes_that_differ_with_matching_recordings_are_robot_variation() -> None:
    request, result = _pair("robot-variation")
    assert request["manifest"]["deterministic"] is True
    assert len(set(_recording_hashes(request))) == 1
    assert len(set(_outcomes(request))) > 1
    finding = result["checks"][0]["findings"][0]
    assert finding["category"] == "robot-variation"
    assert finding["classification"] == "robot_variation"
    assert result["checks"][0]["success"] is True
    assert result["checks"][0]["percentage"] == 100
    assert result["run"]["success"] is True
    assert result["run"]["percentage"] == 100
    assert result["run"]["test_system_status"] == "COMPLETED"
    assert "conclusion" not in result["run"]
    assert all(item["classification"] != "test_system" for item in result["checks"][0]["findings"])


def test_a_run_that_is_not_deterministic_skips_the_check() -> None:
    request, result = _pair("not-deterministic")
    assert request["manifest"]["deterministic"] is False
    assert len(set(_recording_hashes(request))) > 1
    check = result["checks"][0]
    assert check["applicable"] is False
    assert check["success"] is True
    assert "percentage" not in check
    assert check["findings"] == []
    assert result["run"]["success"] is True
    assert result["run"]["test_system_status"] == "COMPLETED"
