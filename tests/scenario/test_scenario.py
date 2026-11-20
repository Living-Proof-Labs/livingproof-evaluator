# SPDX-License-Identifier: Apache-2.0
"""Scenario payloads: robot step verdicts, including not evaluated."""

from __future__ import annotations

from support import EXAMPLES, SCHEMA_ROOT, assert_invalid, assert_valid, load_json


def _steps(name: str) -> tuple[list[dict], list[dict]]:
    example = EXAMPLES / "scenario" / name
    request = load_json(example / "request.json")["scenario"]["scenario"]["steps"]
    result = load_json(example / "result.json")["scenario"]["steps"]
    return request, result


def test_graded_trial_returns_robot_verdicts() -> None:
    request_steps, result_steps = _steps("graded")
    assert [step["id"] for step in result_steps] == [step["id"] for step in request_steps]
    assert {step["verdict"] for step in result_steps} == {"PASS", "FAIL", "INCONCLUSIVE"}
    for request_step, result_step in zip(request_steps, result_steps, strict=True):
        assert request_step["known"] is True
        assert request_step["bound"] is True
        assert "reason" not in result_step


def test_unknown_step_and_unbound_observable_are_not_evaluated() -> None:
    request_steps, result_steps = _steps("not-evaluated")
    by_id = {step["id"]: step for step in result_steps}
    assert [step["id"] for step in result_steps] == [step["id"] for step in request_steps]
    for request_step in request_steps:
        result_step = by_id[request_step["id"]]
        if request_step["known"] is False:
            assert result_step["verdict"] == "NOT_EVALUATED"
            assert result_step["reason"] == "unknown_step"
        elif request_step["bound"] is False:
            assert result_step["verdict"] == "NOT_EVALUATED"
            assert result_step["reason"] == "unbound_observable"
        else:
            assert result_step["verdict"] != "NOT_EVALUATED"
            assert "reason" not in result_step


def _payload(reason: str | None) -> dict:
    step = {"id": "hallway-fall", "verdict": "NOT_EVALUATED", "summary": "x"}
    if reason is not None:
        step["reason"] = reason
    return {"trial_id": "stock-seed-01", "steps": [step]}


def _scenario_schema() -> dict:
    return load_json(SCHEMA_ROOT / "scenario" / "result.schema.json")


def test_a_missing_threshold_is_a_not_evaluated_reason() -> None:
    """A limit the run manifest does not give leaves its step not evaluated."""
    assert_valid(_scenario_schema(), _payload("missing_threshold"))
    assert_invalid(_scenario_schema(), _payload(None))
    assert_invalid(_scenario_schema(), _payload("missing_limit"))


def test_a_missing_threshold_reason_is_only_for_not_evaluated() -> None:
    payload = _payload("missing_threshold")
    payload["steps"][0]["verdict"] = "FAIL"
    assert_invalid(_scenario_schema(), payload)
