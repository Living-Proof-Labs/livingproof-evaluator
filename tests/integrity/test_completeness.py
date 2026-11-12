# SPDX-License-Identifier: Apache-2.0
"""completeness 1.0.0: missing, truncated, empty, timeout, and crash."""

from __future__ import annotations

from support import ROOT, load_json

EXAMPLE = ROOT / "examples" / "integrity" / "completeness"

EXPECTED = {
    "trial-missing-recording": "missing-recording",
    "trial-missing-observations": "missing-observations",
    "trial-truncated-recording": "truncated-recording",
    "trial-truncated-observations": "truncated-observations",
    "trial-empty-recording": "empty-recording",
    "trial-empty-observations": "empty-observations",
    "trial-timeout": "ended-by-timeout",
    "trial-crash": "ended-by-crash",
    "trial-absent": "missing-trial",
}


def test_every_completeness_category_has_a_triggering_trial() -> None:
    request = load_json(EXAMPLE / "request.json")["integrity"]
    result = load_json(EXAMPLE / "result.json")["integrity"]
    evidence = {trial["id"]: trial for trial in request["trials"]}
    assert "trial-absent" not in evidence
    findings = {finding["trial_id"]: finding for finding in result["checks"][0]["findings"]}
    assert set(findings) == set(EXPECTED)
    complete = 0
    for planned in request["manifest"]["planned_trials"]:
        trial = evidence.get(planned["id"])
        if (
            trial
            and trial["recording"]["state"] == "present"
            and trial["observations"]["state"] == "present"
            and trial["termination"] == "completed"
        ):
            complete += 1
            assert planned["id"] not in findings
        else:
            finding = findings[planned["id"]]
            assert finding["category"] == EXPECTED[planned["id"]]
            assert finding["classification"] == "test_system"
    planned_count = len(request["manifest"]["planned_trials"])
    check = result["checks"][0]
    assert check["id"] == "completeness"
    assert check["percentage"] == 100 * complete / planned_count
    assert check["success"] is False
    assert result["run"]["conclusion"] == "INCONCLUSIVE"
    assert result["trials"][0]["success"] is True
    assert all(trial["success"] is False for trial in result["trials"][1:])
