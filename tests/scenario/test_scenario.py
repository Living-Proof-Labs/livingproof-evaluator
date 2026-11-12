# SPDX-License-Identifier: Apache-2.0
"""Scenario payloads: robot step verdicts, including not evaluated."""

from __future__ import annotations

from support import EXAMPLES, load_json


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
