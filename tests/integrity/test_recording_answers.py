# SPDX-License-Identifier: Apache-2.0
"""Rivet's answers on livingproof-evaluator#34 to the recording questions (evaluator-run#16).

1. Gaps are measured in log-time order, not file order. Out-of-order writes are not a gap.
2. A truncated file is reported once (superseded by Rivet's decision on the review: completeness
   owns a file with no valid footer, and recording 1.1.0 lists it as not-present).
3. completeness reads the recordings the manifest lists, so a listed recording that is missing
   or truncated makes the run incomplete.
4. A run with one of three listed recordings missing is never COMPLETED and 100. It counts
   against completeness, and a remark in a summary is not enough.
"""

from __future__ import annotations

import json

from integrity_rules import finding_keys, matches_rules, recording, reported
from support import ROOT, SCHEMA_ROOT, example_dirs, load_json

EXAMPLES = ROOT / "examples" / "integrity"
CHECKS = SCHEMA_ROOT / "integrity" / "checks"
DOC = (ROOT / "docs" / "run-integrity.md").read_text()
COMPLETENESS_RECORDING = {"missing-recording", "truncated-recording", "empty-recording"}


def integrity_examples():
    for example in example_dirs():
        result = load_json(example / "result.json")
        if result["evaluator"]["kind"] == "integrity":
            yield example, result


# 1. Gap order.


def test_the_gap_is_measured_in_log_time_order() -> None:
    schema = load_json(CHECKS / "recording.schema.json")
    assert "log-time order" in schema["description"]
    assert "file order" in schema["description"]
    channel = schema["$defs"]["evidence"]["properties"]["trials"]["items"]["properties"]["mcap"][
        "properties"
    ]["channels"]["items"]["properties"]
    assert "log-time order" in channel["max_gap_seconds"]["description"]
    assert "file order" in channel["backward_steps"]["description"]
    assert "log-time order" in DOC


def test_out_of_order_writes_are_not_a_capture_gap() -> None:
    """trial-backwards has 3 backwards steps and a longest gap of 0.02 s, in log-time order."""
    request = load_json(EXAMPLES / "recording" / "findings" / "request.json")["integrity"]
    entry = next(
        e for e in request["evidence"]["recording"]["trials"] if e["id"] == "trial-backwards"
    )
    assert entry["mcap"]["channels"][0]["backward_steps"] == 3
    limit = request["evidence"]["recording"]["max_gap_seconds"]
    assert all(c["max_gap_seconds"] <= limit for c in entry["mcap"]["channels"])
    result = load_json(EXAMPLES / "recording" / "findings" / "result.json")
    found = [
        i["category"]
        for i in reported(result, "recording")["findings"]
        if i["trial_id"] == "trial-backwards"
    ]
    assert found == ["timestamps-backwards"]


# 2. A truncated file is reported once. Rivet's decision on the review: completeness owns a file
# that exists but has no valid footer, as truncated-recording. From recording 1.1.0 this check
# does not judge it, lists it as not-present, and no longer emits mcap-incomplete.


def test_a_file_with_no_valid_footer_is_completeness_s_and_listed_not_present() -> None:
    request = load_json(EXAMPLES / "recording" / "not-checked" / "request.json")["integrity"]
    result = load_json(EXAMPLES / "recording" / "not-checked" / "result.json")
    state = next(t for t in request["trials"] if t["id"] == "trial-incomplete")["recording"]
    assert state["state"] == "truncated" and "sha256" in state  # the file exists
    ids = {e["id"] for e in request["evidence"]["recording"]["trials"]}
    assert "trial-incomplete" not in ids
    by_check = {
        c["id"]: [(i["category"], i["trial_id"]) for i in c["findings"]]
        for c in result["integrity"]["checks"]
    }
    assert ("truncated-recording", "trial-incomplete") in by_check["completeness"]
    assert all(trial != "trial-incomplete" for _, trial in by_check["recording"])
    matches_rules(reported(result, "recording"), recording(request))


def test_the_rule_does_not_judge_a_file_the_evidence_calls_incomplete() -> None:
    request = load_json(EXAMPLES / "recording" / "clean" / "request.json")["integrity"]
    for channels in (
        [],
        [{"topic": "/base_pose", "message_count": 7, "backward_steps": 0, "max_gap_seconds": 0.01}],
    ):
        payload = json.loads(json.dumps(request))
        mcap = payload["evidence"]["recording"]["trials"][0]["mcap"]
        mcap["state"], mcap["channels"] = "incomplete", channels
        expected = recording(payload)
        assert expected["findings"] == []
        assert expected["not_checked"] == [{"trial_id": "trial-01", "reason": "not-present"}]
    payload = json.loads(json.dumps(request))
    payload["evidence"]["recording"]["trials"][0]["mcap"]["channels"] = []
    categories = [i["category"] for i in recording(payload)["findings"]]
    assert categories == ["missing-channel", "missing-channel"]  # a complete file still is judged


def test_the_schema_and_docs_say_completeness_owns_a_truncated_file() -> None:
    schema = load_json(CHECKS / "recording.schema.json")
    text = schema["description"]
    assert "truncated-recording" in text and "mcap-incomplete" in text and "1.0.0" in text
    assert "truncated-recording" in DOC and "1.0.0 only" in DOC


# 3 and 4. completeness reads the listed recordings, and a missing one is a finding.


def test_completeness_says_it_reads_the_recordings_the_manifest_lists() -> None:
    schema = load_json(CHECKS / "completeness.schema.json")
    assert "lists" in schema["description"] and "manifest" in schema["description"]
    assert "listed" in DOC and "a remark" in DOC


def test_one_of_three_listed_recordings_missing_is_not_completed_and_100() -> None:
    example = EXAMPLES / "completeness-recording-listed-missing"
    request = load_json(example / "request.json")["integrity"]
    payload = load_json(example / "result.json")["integrity"]
    assert len(request["manifest"]["planned_trials"]) == 3
    states = [t["recording"]["state"] for t in request["trials"]]
    assert sorted(states) == ["missing", "present", "present"]
    missing = next(t["id"] for t in request["trials"] if t["recording"]["state"] == "missing")
    completeness = reported(load_json(example / "result.json"), "completeness")
    assert completeness["version"] == "1.1.0" and completeness["applicable"] is True
    assert finding_keys(completeness) == [("missing-recording", missing)]
    assert completeness["percentage"] == 100 * 2 / 3 and completeness["success"] is False
    run = payload["run"]
    assert run["success"] is False and run["test_system_status"] == "ERROR"
    assert run["conclusion"] == "INCONCLUSIVE" and run["percentage"] == 100 * 2 / 3
    by_id = {t["id"]: t for t in payload["trials"]}
    assert by_id[missing]["success"] is False
    assert sum(t["success"] for t in payload["trials"]) == 2
    rec = reported(load_json(example / "result.json"), "recording")
    assert rec["percentage"] == 100 and rec["not_checked"] == [
        {"trial_id": missing, "reason": "not-present"}
    ]
    matches_rules(rec, recording(request))


def test_a_recording_that_was_not_judged_is_always_a_completeness_finding() -> None:
    """A not-present recording is never only a note: the same result has the completeness finding."""
    seen = 0
    for example, result in integrity_examples():
        checks = {c["id"]: c for c in result["integrity"]["checks"]}
        skipped = [
            i["trial_id"]
            for i in checks.get("recording", {}).get("not_checked", [])
            if i["reason"] == "not-present"
        ]
        if not skipped:
            continue
        seen += 1
        found = {
            i["trial_id"]
            for i in checks["completeness"]["findings"]
            if i["category"] in COMPLETENESS_RECORDING
        }
        assert set(skipped) <= found, example
        assert result["integrity"]["run"]["success"] is False, example
    assert seen >= 4


def test_a_recording_problem_is_reported_by_one_check_only() -> None:
    for example, result in integrity_examples():
        checks = {c["id"]: c for c in result["integrity"]["checks"]}
        if "completeness" not in checks or "recording" not in checks:
            continue
        by_completeness = {
            i["trial_id"]
            for i in checks["completeness"]["findings"]
            if i["category"] in COMPLETENESS_RECORDING
        }
        by_recording = {i["trial_id"] for i in checks["recording"]["findings"]}
        assert not by_completeness & by_recording, example
