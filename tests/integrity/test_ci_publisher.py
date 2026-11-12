# SPDX-License-Identifier: Apache-2.0
"""ci-publisher 1.0.0: a check run left open after HTTP 404."""

from __future__ import annotations

from support import ROOT, load_json

EXAMPLE = ROOT / "examples" / "integrity" / "ci-publisher"


def test_open_check_run_after_http_404_is_a_test_system_finding() -> None:
    request = load_json(EXAMPLE / "request.json")["integrity"]
    result = load_json(EXAMPLE / "result.json")["integrity"]
    evidence = request["evidence"]["ci-publisher"]
    assert evidence["publisher_http_status"] == 404
    assert any(run["status"] != "completed" for run in evidence["check_runs"])
    finding = result["checks"][0]["findings"][0]
    assert finding["category"] == "check-run-left-open"
    assert finding["classification"] == "test_system"
    assert {item["check_run"] for item in result["checks"][0]["findings"]} == {
        "Reporter tests (amd64)",
        "Reporter tests (arm64)",
    }
    assert all(run["status"] == "in_progress" for run in evidence["check_runs"])
    assert result["checks"][0]["success"] is False
    assert result["checks"][0]["percentage"] == 0
    assert result["run"]["success"] is False
    assert result["run"]["test_system_status"] == "ERROR"
    assert result["run"]["conclusion"] == "INCONCLUSIVE"
    assert "verdict" not in result
    assert all(trial["success"] is True for trial in result["trials"])
