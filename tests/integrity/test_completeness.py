# SPDX-License-Identifier: Apache-2.0
"""completeness 1.0.0: missing, truncated, empty, timeout, and crash."""

from __future__ import annotations

from integrity_rules import completeness_applicable
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


# completeness 1.1.0 (livingproof-evaluator#34): follow plan-conformance's applicability.


def test_unmet_preconditions_make_completeness_not_applicable() -> None:
    """A run whose preconditions are unmet ran no trials. 1.0.0 counted every planned trial as
    missing and the run read ERROR where the verifier grades UNSUPPORTED."""
    example = ROOT / "examples" / "integrity" / "completeness-preconditions-unmet"
    request = load_json(example / "request.json")["integrity"]
    result = load_json(example / "result.json")["integrity"]
    assert request["evidence"]["plan-conformance"]["preconditions"]["met"] is False
    assert request["trials"] == []
    check = next(c for c in result["checks"] if c["id"] == "completeness")
    assert check["version"] == "1.1.0"
    assert check["applicable"] is False and check["success"] is True
    assert check["findings"] == [] and "percentage" not in check
    assert completeness_applicable(request) is False
    plan = next(c for c in result["checks"] if c["id"] == "plan-conformance")
    assert plan["applicable"] is False
    # Nothing is wrong with the planned trials, and nothing applicable failed.
    assert result["run"]["test_system_status"] == "COMPLETED"
    assert result["run"]["percentage"] == 100
    assert all(trial["success"] is True for trial in result["trials"])
    assert len(result["trials"]) == len(request["manifest"]["planned_trials"])


def test_completeness_still_judges_a_run_whose_preconditions_are_met_or_unstated() -> None:
    request = load_json(EXAMPLE / "request.json")["integrity"]
    assert completeness_applicable(request) is True
    request["evidence"] = {"plan-conformance": {"preconditions": {"met": True}}}
    assert completeness_applicable(request) is True


def test_version_1_0_0_was_always_applicable() -> None:
    request = load_json(EXAMPLE / "request.json")["integrity"]
    request["evidence"] = {"plan-conformance": {"preconditions": {"met": False}}}
    assert completeness_applicable(request, "1.0.0") is True
    assert completeness_applicable(request, "1.1.0") is False


def test_the_existing_completeness_example_is_still_1_0_0() -> None:
    result = load_json(EXAMPLE / "result.json")["integrity"]
    assert result["checks"][0]["version"] == "1.0.0"
