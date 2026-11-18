# SPDX-License-Identifier: Apache-2.0
"""pins 1.0.0: manifest hashes against the verification lock."""

from __future__ import annotations

from integrity_rules import matches_rules
from integrity_rules import pins as pins_rules
from support import ROOT, load_json

EXAMPLE = ROOT / "examples" / "integrity" / "pins"
SUBJECTS = ("specs", "runner", "verifier", "world", "configuration")


def test_each_pin_mismatch_is_a_test_system_finding() -> None:
    request = load_json(EXAMPLE / "request.json")["integrity"]
    result = load_json(EXAMPLE / "result.json")["integrity"]
    findings = result["checks"][0]["findings"]
    assert [finding["subject"] for finding in findings] == list(SUBJECTS)
    matches = 0
    for finding in findings:
        subject = finding["subject"]
        manifest_hash = request["manifest"]["pins"][subject]["sha256"]
        lock_hash = request["lock"]["pins"][subject]["sha256"]
        assert manifest_hash != lock_hash
        assert finding["category"] == "hash-mismatch"
        assert finding["classification"] == "test_system"
        matches += manifest_hash == lock_hash
    check = result["checks"][0]
    assert check["percentage"] == 100 * matches / len(SUBJECTS)
    assert check["success"] is False
    assert result["run"]["test_system_status"] == "ERROR"
    assert result["run"]["conclusion"] == "INCONCLUSIVE"
    assert all(trial["success"] is True for trial in result["trials"])


def test_a_partial_pin_mismatch_reports_the_matching_share() -> None:
    example = ROOT / "examples" / "integrity" / "pins-partial"
    request = load_json(example / "request.json")["integrity"]
    result = load_json(example / "result.json")["integrity"]
    matches = 0
    for subject in SUBJECTS:
        same = (
            request["manifest"]["pins"][subject]["sha256"]
            == request["lock"]["pins"][subject]["sha256"]
        )
        matches += same
    reported = {finding["subject"] for finding in result["checks"][0]["findings"]}
    assert reported == {"specs", "world"}
    assert result["checks"][0]["percentage"] == 100 * matches / len(SUBJECTS)
    assert result["checks"][0]["success"] is False
    assert result["run"]["percentage"] == 60


# pins 1.1.0 (livingproof-evaluator#34): not-checked subjects, and the denominator.


def test_a_run_that_cannot_check_every_subject_reads_the_share_of_those_it_checked() -> None:
    """Three subjects are checkable and one of them differs; specs and verifier are not checked.
    1.0.0 would read 40. 1.1.0 reads the two matching of the three checked."""
    example = ROOT / "examples" / "integrity" / "pins-not-checked"
    request = load_json(example / "request.json")["integrity"]
    result = load_json(example / "result.json")["integrity"]
    check = result["checks"][0]
    assert check["version"] == "1.1.0"
    assert check["percentage"] == 100 * 2 / 3
    assert [finding["subject"] for finding in check["findings"]] == ["world"]
    assert check["not_checked"] == [
        {"subject": "specs", "reason": "not-recorded"},
        {"subject": "verifier", "reason": "not-declared"},
    ]
    assert check["success"] is False
    assert result["run"]["percentage"] == 100 * 2 / 3
    matches_rules(check, pins_rules(request))


def test_a_pins_check_with_nothing_checked_is_not_applicable() -> None:
    example = ROOT / "examples" / "integrity" / "pins-none-checked"
    request = load_json(example / "request.json")["integrity"]
    result = load_json(example / "result.json")["integrity"]
    check = result["checks"][0]
    assert check["applicable"] is False
    assert check["success"] is True
    assert "percentage" not in check and check["findings"] == []
    assert [item["subject"] for item in check["not_checked"]] == list(SUBJECTS)
    assert result["run"]["test_system_status"] == "COMPLETED"
    assert result["run"]["percentage"] == 100
    matches_rules(check, pins_rules(request))


def test_the_1_0_0_examples_keep_their_rule_and_their_percentage() -> None:
    for name, percentage in (("pins", 0), ("pins-partial", 60)):
        result = load_json(ROOT / "examples" / "integrity" / name / "result.json")["integrity"]
        check = result["checks"][0]
        assert check["version"] == "1.0.0"
        assert "not_checked" not in check
        assert check["percentage"] == percentage


def test_a_pin_the_lock_does_not_declare_is_not_the_same_as_one_the_run_did_not_record() -> None:
    example = ROOT / "examples" / "integrity" / "pins-not-checked"
    result = load_json(example / "result.json")["integrity"]
    reasons = {item["subject"]: item["reason"] for item in result["checks"][0]["not_checked"]}
    request = load_json(example / "request.json")["integrity"]
    assert "specs" in request["lock"]["pins"] and "specs" not in request["manifest"]["pins"]
    assert "verifier" not in request["lock"]["pins"]
    assert reasons == {"specs": "not-recorded", "verifier": "not-declared"}
