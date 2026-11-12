# SPDX-License-Identifier: Apache-2.0
"""same-input-agreement 1.0.0 after the determinism correction."""

from __future__ import annotations

from support import ROOT, load_json

BASE = ROOT / "examples" / "integrity" / "same-input-agreement"


def _pair(name: str) -> tuple[dict, dict]:
    example = BASE / name
    return (
        load_json(example / "request.json")["integrity"],
        load_json(example / "result.json")["integrity"],
    )


def _recording_hashes(payload: dict) -> set[str]:
    return {trial["recording"]["sha256"] for trial in payload["trials"]}


def _outcomes(payload: dict) -> set[str]:
    return {trial["outcome"] for trial in payload["trials"]}


def test_different_recordings_are_a_test_system_finding_when_declared_deterministic() -> None:
    request, result = _pair("recording-mismatch")
    assert request["manifest"]["robot_determinism"] == "deterministic"
    assert len({trial["input_sha256"] for trial in request["trials"]}) == 1
    assert len(_recording_hashes(request)) > 1
    assert len(_outcomes(request)) == 1
    finding = result["checks"][0]["findings"][0]
    assert finding["category"] == "recording-mismatch"
    assert finding["classification"] == "test_system"
    assert result["checks"][0]["success"] is False
    assert result["run"]["success"] is False
    assert result["run"]["test_system_status"] == "ERROR"
    assert result["run"]["conclusion"] == "INCONCLUSIVE"


def test_identical_recordings_with_different_outcomes_are_a_grader_problem() -> None:
    request, result = _pair("grader-disagreement")
    assert len(_recording_hashes(request)) == 1
    assert len(_outcomes(request)) > 1
    finding = result["checks"][0]["findings"][0]
    assert finding["category"] == "outcome-disagreement"
    assert finding["classification"] == "test_system"
    assert result["checks"][0]["success"] is False
    assert result["checks"][0]["percentage"] == 0
    assert result["run"]["success"] is False
    assert result["run"]["conclusion"] == "INCONCLUSIVE"


def test_different_recordings_are_robot_variation_when_the_robot_is_non_deterministic() -> None:
    request, result = _pair("robot-variation")
    assert request["manifest"]["robot_determinism"] == "non-deterministic"
    assert len(_recording_hashes(request)) > 1
    finding = result["checks"][0]["findings"][0]
    assert finding["category"] == "robot-variation"
    assert finding["classification"] == "robot_variation"
    assert result["checks"][0]["success"] is True
    assert result["checks"][0]["percentage"] == 100
    assert result["run"]["success"] is True
    assert result["run"]["percentage"] == 100
    assert result["run"]["test_system_status"] == "COMPLETED"
    assert "conclusion" not in result["run"]


def test_an_undeclared_simulation_treats_a_recording_mismatch_as_test_system() -> None:
    request, result = _pair("undeclared")
    assert "robot_determinism" not in request["manifest"]
    assert request["manifest"]["environment"] == "simulation"
    assert len(_recording_hashes(request)) > 1
    finding = result["checks"][0]["findings"][0]
    assert finding["category"] == "recording-mismatch"
    assert finding["classification"] == "test_system"
    assert result["run"]["success"] is False
    assert result["run"]["conclusion"] == "INCONCLUSIVE"
