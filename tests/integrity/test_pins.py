# SPDX-License-Identifier: Apache-2.0
"""pins 1.0.0: manifest hashes against the verification lock."""

from __future__ import annotations

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
