# SPDX-License-Identifier: Apache-2.0
"""termination 1.0.0: every trial records a stop reason that the plan allows, and a
timeout or crash is reported once, by completeness."""

from __future__ import annotations

import json
from collections import Counter

import pytest

from integrity_rules import finding_keys, matches_rules, reported, termination
from support import (
    ROOT,
    SCHEMA_ROOT,
    assert_invalid,
    assert_valid,
    load_json,
    result_schema,
)

EXAMPLES = ROOT / "examples" / "integrity" / "termination"
SCHEMA = load_json(SCHEMA_ROOT / "integrity" / "checks" / "termination.schema.json")
VOCABULARY = {
    "time-limit",
    "mission-done",
    "left-world",
    "simulation-broken",
    "adapter-or-scenario-done",
}
VOCAB_ENUM = set(SCHEMA["$defs"]["stop_reason"]["enum"])


def load(name: str) -> tuple[dict, dict]:
    return (
        load_json(EXAMPLES / name / "request.json"),
        load_json(EXAMPLES / name / "result.json"),
    )


def test_the_stop_reason_vocabulary_is_the_five_reasons() -> None:
    assert VOCAB_ENUM == VOCABULARY


def test_every_allowed_stop_reason_is_clean() -> None:
    request, result = load("clean")
    check = reported(result, "termination")
    evidence = request["integrity"]["evidence"]["termination"]
    assert {entry["stop_reason"] for entry in evidence["trials"]} == set(
        evidence["allowed_stop_reasons"]
    )
    assert check["success"] is True
    assert check["percentage"] == 100
    assert check["findings"] == []
    assert check["referrals"] == []
    matches_rules(check, termination(request["integrity"], VOCAB_ENUM))


def test_every_finding_category_has_a_triggering_trial() -> None:
    request, result = load("findings")
    check = reported(result, "termination")
    assert finding_keys(check) == [
        ("disallowed-stop-reason", "trial-disallowed"),
        ("missing-stop-reason", "trial-missing"),
        ("stop-reason-mismatch", "trial-mismatch"),
        ("unknown-stop-reason", "trial-unknown"),
    ]
    # Five trials ended on their own, and only trial-clean has no finding.
    assert check["percentage"] == 20
    assert check["success"] is False
    assert all(item["classification"] == "test_system" for item in check["findings"])
    matches_rules(check, termination(request["integrity"], VOCAB_ENUM))
    assert result["integrity"]["run"]["conclusion"] == "INCONCLUSIVE"


def test_the_simulation_breaking_is_a_finding_unless_the_plan_allows_it() -> None:
    request, _ = load("findings")
    payload = json.loads(json.dumps(request["integrity"]))
    evidence = payload["evidence"]["termination"]
    assert "simulation-broken" not in evidence["allowed_stop_reasons"]
    assert any(
        item["category"] == "disallowed-stop-reason"
        for item in termination(payload, VOCAB_ENUM)["findings"]
    )
    evidence["allowed_stop_reasons"].append("simulation-broken")
    assert not any(
        item["category"] == "disallowed-stop-reason"
        for item in termination(payload, VOCAB_ENUM)["findings"]
    )


def test_time_limit_is_a_clean_ending_and_a_timeout_is_not_the_same_thing() -> None:
    request, _ = load("clean")
    reasons = request["integrity"]["evidence"]["termination"]["allowed_stop_reasons"]
    assert "time-limit" in reasons
    trial_terminations = {trial["termination"] for trial in request["integrity"]["trials"]}
    assert trial_terminations == {"completed"}


def completeness_and_termination_findings(result: dict) -> Counter:
    """Findings per trial across the two checks that can report how a trial ended."""
    counts: Counter = Counter()
    for check_id in ("completeness", "termination"):
        for check in result["integrity"]["checks"]:
            if check["id"] == check_id:
                counts.update(item["trial_id"] for item in check["findings"])
    return counts


def assert_each_ending_is_reported_once(result: dict) -> None:
    """A timeout or crash is a completeness finding, and termination only refers to it."""
    completeness = reported(result, "completeness")
    termination_check = reported(result, "termination")
    ended = {
        item["trial_id"]: item["category"]
        for item in completeness["findings"]
        if item["category"] in ("ended-by-timeout", "ended-by-crash")
    }
    counts = completeness_and_termination_findings(result)
    for trial_id in ended:
        assert counts[trial_id] == 1, f"{trial_id} is reported more than once"
    assert {item["trial_id"]: item["category"] for item in termination_check["referrals"]} == ended
    for item in termination_check["referrals"]:
        assert item["check"] == "completeness"


def test_a_timeout_and_a_crash_yield_exactly_one_finding_across_both_checks() -> None:
    request, result = load("timeout-single-report")
    trials = {trial["id"]: trial for trial in request["integrity"]["trials"]}
    assert trials["trial-timeout"]["termination"] == "timeout"
    assert trials["trial-crash"]["termination"] == "crash"
    completeness = reported(result, "completeness")
    termination_check = reported(result, "termination")
    assert finding_keys(completeness) == [
        ("ended-by-crash", "trial-crash"),
        ("ended-by-timeout", "trial-timeout"),
    ]
    assert termination_check["findings"] == []
    assert termination_check["success"] is True
    counts = completeness_and_termination_findings(result)
    assert counts == {"trial-timeout": 1, "trial-crash": 1}
    assert_each_ending_is_reported_once(result)
    matches_rules(termination_check, termination(request["integrity"], VOCAB_ENUM))
    assert termination_check["referrals"] == [
        {"trial_id": "trial-timeout", "check": "completeness", "category": "ended-by-timeout"},
        {"trial_id": "trial-crash", "check": "completeness", "category": "ended-by-crash"},
    ]
    assert result["integrity"]["run"]["conclusion"] == "INCONCLUSIVE"


def test_the_single_report_test_catches_a_double_report() -> None:
    _, result = load("timeout-single-report")
    doubled = json.loads(json.dumps(result))
    check = reported(doubled, "termination")
    check["findings"].append(
        {
            "category": "missing-stop-reason",
            "classification": "test_system",
            "summary": "The trial records no stop reason.",
            "trial_id": "trial-timeout",
        }
    )
    check["success"] = False
    with pytest.raises(AssertionError, match="trial-timeout is reported more than once"):
        assert_each_ending_is_reported_once(doubled)
    unreferred = json.loads(json.dumps(result))
    reported(unreferred, "termination")["referrals"].pop()
    with pytest.raises(AssertionError):
        assert_each_ending_is_reported_once(unreferred)


def test_the_rules_never_raise_a_termination_finding_for_a_timeout_or_crash() -> None:
    request, _ = load("timeout-single-report")
    payload = json.loads(json.dumps(request["integrity"]))
    payload["evidence"]["termination"]["trials"] = []
    expected = termination(payload, VOCAB_ENUM)
    assert {item["trial_id"] for item in expected["findings"]} == set()
    for trial in payload["trials"]:
        if trial["termination"] == "completed":
            continue
        assert trial["id"] in {item["trial_id"] for item in expected["referrals"]}
    only_ended = json.loads(json.dumps(payload))
    only_ended["trials"] = [t for t in only_ended["trials"] if t["termination"] != "completed"]
    result = termination(only_ended, VOCAB_ENUM)
    assert result["applicable"] is False
    assert "percentage" not in result


def test_every_example_that_reports_both_checks_reports_each_ending_once() -> None:
    both = 0
    for path in sorted(ROOT.joinpath("examples", "integrity").rglob("result.json")):
        result = load_json(path)
        ids = {check["id"] for check in result["integrity"]["checks"]}
        if {"completeness", "termination"} <= ids:
            both += 1
            assert_each_ending_is_reported_once(result)
    assert both >= 1


def test_the_schema_accepts_referrals_only_on_termination() -> None:
    _, result = load("timeout-single-report")
    document = json.loads(json.dumps(result))
    assert_valid(result_schema(), document)
    completeness = reported(document, "completeness")
    completeness["referrals"] = []
    assert_invalid(result_schema(), document)
    missing = json.loads(json.dumps(result))
    del reported(missing, "termination")["referrals"]
    assert_invalid(result_schema(), missing)
    wrong_target = json.loads(json.dumps(result))
    reported(wrong_target, "termination")["referrals"][0]["check"] = "pins"
    assert_invalid(result_schema(), wrong_target)
    wrong_category = json.loads(json.dumps(result))
    reported(wrong_category, "termination")["referrals"][0]["category"] = "missing-recording"
    assert_invalid(result_schema(), wrong_category)


def test_termination_cannot_report_a_timeout_or_crash_finding_of_its_own() -> None:
    _, result = load("timeout-single-report")
    for category in ("ended-by-timeout", "ended-by-crash", "timeout", "crash"):
        doctored = json.loads(json.dumps(reported(result, "termination")))
        doctored["success"] = False
        doctored["findings"] = [
            {
                "category": category,
                "classification": "test_system",
                "summary": "The trial did not end on its own.",
                "trial_id": "trial-timeout",
            }
        ]
        assert_invalid(SCHEMA, doctored)


def test_a_referral_does_not_fail_the_check() -> None:
    _, result = load("timeout-single-report")
    check = reported(result, "termination")
    assert check["referrals"]
    assert check["success"] is True
    assert check["percentage"] == 100


def test_the_evidence_schema_rejects_an_unlisted_allowed_reason_and_a_verdict() -> None:
    request, _ = load("clean")
    evidence = request["integrity"]["evidence"]["termination"]
    bad = json.loads(json.dumps(evidence))
    bad["allowed_stop_reasons"].append("robot-fell")
    assert_invalid(SCHEMA["$defs"]["evidence"], bad)
    with_verdict = json.loads(json.dumps(evidence))
    with_verdict["trials"][0]["verdict"] = "PASS"
    assert_invalid(SCHEMA["$defs"]["evidence"], with_verdict)
    assert_valid(SCHEMA["$defs"]["evidence"], evidence)
