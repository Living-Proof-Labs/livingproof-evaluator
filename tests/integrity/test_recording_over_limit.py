# SPDX-License-Identifier: Apache-2.0
"""recording 1.2.0: a named finding when a recording expands past the reader's limits.

livingproof-evaluator#42: when an MCAP goes over the reader's decompression caps (chunk
bytes, total bytes, records, or chunks), the producer reports ``recording-over-limit``,
which names the limit that was hit and its value. The trial is judged and fails closed.
This replaces the 1.1.0 mapping (completeness ``truncated-recording`` plus recording
``not-present``). Version 1.1.0 stays valid and does not emit the new finding.
"""

from __future__ import annotations

import copy
import inspect
import json

import pytest

from integrity_rules import MalformedRequest, matches_rules, recording, reported
from support import (
    ROOT,
    SCHEMA_ROOT,
    assert_invalid,
    assert_valid,
    check_registry,
    load_json,
    result_schema,
)

EXAMPLES = ROOT / "examples" / "integrity" / "recording"
SCHEMA = load_json(SCHEMA_ROOT / "integrity" / "checks" / "recording.schema.json")
EVIDENCE_SCHEMA = SCHEMA["$defs"]["evidence"]
DOC = (ROOT / "docs" / "run-integrity.md").read_text()
OVER_LIMIT = EXAMPLES / "over-limit"

# The four reader limits, with values evaluator-run uses today. The contract does not
# fix the numbers; the evidence carries the cap that was applied.
LIMITS = (
    ("chunk-bytes", 33_554_432, "bytes"),
    ("total-bytes", 2_147_483_648, "bytes"),
    ("records", 50_000_000, None),
    ("chunks", 100_000, None),
)


def _summary(limit: str, value: int, unit: str | None) -> str:
    measured = f"{value} {unit}" if unit else f"{value}"
    return (
        f"The recording expands past the reader's {limit} limit of {measured},"
        " so it was not fully read."
    )


SUMMARIES = {limit: _summary(limit, value, unit) for limit, value, unit in LIMITS}


def load(name: str) -> tuple[dict, dict]:
    return (
        load_json(EXAMPLES / name / "request.json"),
        load_json(EXAMPLES / name / "result.json"),
    )


def payload_with_over_limit(
    limit: str = "chunk-bytes",
    value: int = 33_554_432,
    *,
    mcap_state: str = "complete",
    channels: list | None = None,
) -> dict:
    """A two-trial clean payload whose second present recording hit a reader limit."""
    request, _ = load("clean")
    payload = json.loads(json.dumps(request["integrity"]))
    entry = payload["evidence"]["recording"]["trials"][1]
    entry["over_limit"] = {"limit": limit, "value": value}
    entry["mcap"]["state"] = mcap_state
    if channels is not None:
        entry["mcap"]["channels"] = channels
    return payload


def over_limit_check(version: str = "1.2.0") -> dict:
    check = {
        "id": "recording",
        "version": version,
        "applicable": True,
        "success": False,
        "percentage": 50,
        "limits": {"max_gap_seconds": 0.1},
        "findings": [
            {
                "category": "recording-over-limit",
                "classification": "test_system",
                "summary": SUMMARIES["chunk-bytes"],
                "trial_id": "trial-02",
            }
        ],
        "not_checked": [],
    }
    if version == "1.0.0":
        del check["not_checked"]
    return check


# Versions and the registry.


def test_recording_is_at_1_2_0_and_keeps_the_earlier_versions() -> None:
    entry = next(item for item in check_registry() if item["id"] == "recording")
    assert entry["version"] == "1.2.0"
    assert entry["previous_versions"] == ["1.0.0", "1.1.0"]
    assert "examples/integrity/recording/over-limit" in entry["examples"]
    assert SCHEMA["title"] == "recording 1.2.0"
    assert "1.2.0" in SCHEMA["properties"]["version"]["enum"]
    assert "1.1.0" in SCHEMA["properties"]["version"]["enum"]
    assert "1.0.0" in SCHEMA["properties"]["version"]["enum"]


def test_the_reference_rule_defaults_to_1_2_0() -> None:
    assert inspect.signature(recording).parameters["version"].default == "1.2.0"


# Schema: the finding is 1.2.0 only.


def test_the_schema_accepts_recording_over_limit_at_1_2_0() -> None:
    assert_valid(SCHEMA, over_limit_check())


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0"])
def test_the_schema_rejects_recording_over_limit_at_earlier_versions(version: str) -> None:
    assert_invalid(SCHEMA, over_limit_check(version))


def test_recording_1_2_0_still_rejects_mcap_incomplete() -> None:
    check = over_limit_check()
    check["findings"][0]["category"] = "mcap-incomplete"
    check["findings"][0]["summary"] = (
        "The recording does not open or has no valid footer and summary."
    )
    assert_invalid(SCHEMA, check)


def test_the_envelope_accepts_a_1_2_0_result_with_the_finding() -> None:
    _, result = load("over-limit")
    assert_valid(result_schema(), result)
    check = reported(result, "recording")
    assert check["version"] == "1.2.0"
    assert_valid(SCHEMA, check)


# Evidence: the trial names the limit and its value.


def test_evidence_accepts_over_limit_with_each_named_limit() -> None:
    request, _ = load("clean")
    evidence = json.loads(json.dumps(request["integrity"]["evidence"]["recording"]))
    for limit, value, _unit in LIMITS:
        trial = copy.deepcopy(evidence)
        trial["trials"][1]["over_limit"] = {"limit": limit, "value": value}
        assert_valid(EVIDENCE_SCHEMA, trial)


def test_evidence_rejects_an_unknown_limit_name_or_a_non_positive_value() -> None:
    request, _ = load("clean")
    evidence = request["integrity"]["evidence"]["recording"]
    bad_name = json.loads(json.dumps(evidence))
    bad_name["trials"][1]["over_limit"] = {"limit": "size", "value": 33_554_432}
    assert_invalid(EVIDENCE_SCHEMA, bad_name)
    zero = json.loads(json.dumps(evidence))
    zero["trials"][1]["over_limit"] = {"limit": "chunk-bytes", "value": 0}
    assert_invalid(EVIDENCE_SCHEMA, zero)
    missing = json.loads(json.dumps(evidence))
    missing["trials"][1]["over_limit"] = {"limit": "chunk-bytes"}
    assert_invalid(EVIDENCE_SCHEMA, missing)


def test_evidence_rejects_the_other_malformed_over_limit_shapes() -> None:
    """Shape is the evidence schema's job. An evaluator rejects a schema-invalid
    request with no result and exit status 2. The reference rule assumes valid
    evidence; MalformedRequest is reserved for present-plus-incomplete."""
    request, _ = load("clean")
    evidence = request["integrity"]["evidence"]["recording"]
    cases = (
        {"value": 33_554_432},  # missing limit
        {"limit": "chunk-bytes", "value": -1},
        {"limit": "chunk-bytes", "value": 1.5},
        {"limit": "chunk-bytes", "value": "33554432"},
        {"limit": 1, "value": 33_554_432},
        {"limit": "chunk-bytes", "value": 33_554_432, "measured": 33_554_433},
        None,
        {},
        ["chunk-bytes", 33_554_432],
    )
    for over_limit in cases:
        ev = json.loads(json.dumps(evidence))
        ev["trials"][1]["over_limit"] = over_limit
        assert_invalid(EVIDENCE_SCHEMA, ev)
    # The cap that was applied must be a positive integer; 1 is the smallest.
    ok = json.loads(json.dumps(evidence))
    ok["trials"][1]["over_limit"] = {"limit": "records", "value": 1}
    assert_valid(EVIDENCE_SCHEMA, ok)


def test_a_clean_trial_need_not_carry_over_limit() -> None:
    request, _ = load("clean")
    assert_valid(EVIDENCE_SCHEMA, request["integrity"]["evidence"]["recording"])


# Reference rule at 1.2.0.


@pytest.mark.parametrize("limit,value,unit", LIMITS)
def test_the_rule_reports_recording_over_limit_and_names_the_cap(
    limit: str, value: int, unit: str | None
) -> None:
    # Empty channels would be missing-channel if the rule kept reading; it must stop.
    result = recording(payload_with_over_limit(limit, value, channels=[]), "1.2.0")
    assert result["applicable"] is True
    assert result["percentage"] == 50
    assert result["not_checked"] == []
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["category"] == "recording-over-limit"
    assert finding["classification"] == "test_system"
    assert finding["trial_id"] == "trial-02"
    assert finding["summary"] == _summary(limit, value, unit)
    assert str(value) in finding["summary"] and limit in finding["summary"]
    assert finding["summary"] == SUMMARIES[limit]


def test_the_over_limit_trial_is_judged_and_fails_closed() -> None:
    result = recording(payload_with_over_limit(), "1.2.0")
    assert result["applicable"] is True
    assert result["percentage"] == 50
    assert result["not_checked"] == []
    assert [item["trial_id"] for item in result["findings"]] == ["trial-02"]
    # The default is the current rule.
    assert recording(payload_with_over_limit()) == result


def test_an_over_limit_trial_does_not_also_get_missing_channel() -> None:
    result = recording(payload_with_over_limit(channels=[]), "1.2.0")
    assert [item["category"] for item in result["findings"]] == ["recording-over-limit"]


def test_a_truncated_trial_is_still_not_present_even_with_over_limit_in_evidence() -> None:
    """Over-limit is not truncation. A file with no valid footer stays completeness's."""
    request, _ = load("not-checked")
    payload = json.loads(json.dumps(request["integrity"]))
    # The truncated trial has no evidence entry in this fixture; add one with over_limit
    # so the rule cannot be tricked into judging it.
    payload["evidence"]["recording"]["trials"].append(
        {
            "id": "trial-incomplete",
            "over_limit": {"limit": "chunk-bytes", "value": 33_554_432},
            "mcap": {
                "state": "incomplete",
                "bytes": 0,
                "sha256": "0" * 64,
                "channels": [],
            },
            "media": {
                "mcap_bytes": 0,
                "mcap_sha256": "0" * 64,
                "observation_sha256": "0" * 64,
            },
            "evidence_observation_sha256": "0" * 64,
        }
    )
    result = recording(payload, "1.2.0")
    assert {"trial_id": "trial-incomplete", "reason": "not-present"} in result["not_checked"]
    assert "recording-over-limit" not in {item["category"] for item in result["findings"]}


def test_present_plus_incomplete_is_still_malformed_without_over_limit() -> None:
    request, _ = load("clean")
    payload = json.loads(json.dumps(request["integrity"]))
    payload["evidence"]["recording"]["trials"][0]["mcap"]["state"] = "incomplete"
    with pytest.raises(MalformedRequest):
        recording(payload, "1.2.0")


def test_present_plus_incomplete_is_accepted_when_over_limit_is_set() -> None:
    result = recording(payload_with_over_limit(mcap_state="incomplete", channels=[]), "1.2.0")
    assert [item["category"] for item in result["findings"]] == ["recording-over-limit"]
    assert result["not_checked"] == []


# Earlier versions keep their published rule.


def test_1_1_0_does_not_emit_the_new_finding_and_still_rejects_present_incomplete() -> None:
    # A complete present file with over_limit evidence is unknown to 1.1.0, so it is
    # judged as a usable recording when the channel and media facts hold.
    result = recording(payload_with_over_limit(), "1.1.0")
    assert result["findings"] == []
    assert result["percentage"] == 100
    with pytest.raises(MalformedRequest):
        recording(payload_with_over_limit(mcap_state="incomplete"), "1.1.0")


def test_1_0_0_does_not_emit_the_new_finding() -> None:
    result = recording(payload_with_over_limit(), "1.0.0")
    assert "recording-over-limit" not in {item["category"] for item in result["findings"]}
    assert "not_checked" not in result
    # present + incomplete stays mcap-incomplete at 1.0.0, even with over_limit set.
    old = recording(payload_with_over_limit(mcap_state="incomplete"), "1.0.0")
    assert [item["category"] for item in old["findings"]] == ["mcap-incomplete"]


# Docs and the published example.


def test_the_docs_name_the_finding_at_1_2_0_and_say_it_is_not_truncation() -> None:
    assert "| `recording` | 1.2.0 |" in DOC
    assert "recording-over-limit" in DOC
    assert "chunk-bytes" in DOC and "total-bytes" in DOC
    assert "records" in DOC and "chunks" in DOC
    assert "truncated-recording" in DOC
    # The over-limit case is a recording finding, not completeness truncation.
    assert (
        "not a truncated recording" in DOC
        or "is not truncation" in DOC
        or ("not truncation" in DOC)
    )


def test_the_published_example_is_recording_1_2_0_over_limit() -> None:
    assert OVER_LIMIT.is_dir(), "examples/integrity/recording/over-limit is missing"
    request, result = load("over-limit")
    check = reported(result, "recording")
    assert check["version"] == "1.2.0"
    assert check["success"] is False
    assert check["percentage"] == 50
    assert check["not_checked"] == []
    assert [item["category"] for item in check["findings"]] == ["recording-over-limit"]
    finding = check["findings"][0]
    assert finding["trial_id"] == "trial-02"
    assert finding["summary"] == SUMMARIES["chunk-bytes"]
    assert request["integrity"]["trials"][1]["recording"]["state"] == "present"
    evidence = request["integrity"]["evidence"]["recording"]["trials"][1]
    assert evidence["over_limit"] == {"limit": "chunk-bytes", "value": 33_554_432}
    assert evidence["mcap"]["state"] == "incomplete"
    matches_rules(check, recording(request["integrity"], "1.2.0"))
    assert_valid(EVIDENCE_SCHEMA, request["integrity"]["evidence"]["recording"])
    assert_valid(SCHEMA, check)
    assert_valid(result_schema(), result)
    run = result["integrity"]["run"]
    assert run["success"] is False
    assert run["test_system_status"] == "ERROR"
    assert run["conclusion"] == "INCONCLUSIVE"
    # Completeness does not treat this as truncation.
    completeness = reported(result, "completeness")
    assert "truncated-recording" not in {item["category"] for item in completeness["findings"]}
    assert completeness["success"] is True
    states = {trial["id"]: trial["recording"]["state"] for trial in request["integrity"]["trials"]}
    assert states == {"trial-01": "present", "trial-02": "present"}


def test_the_published_1_0_0_findings_request_is_rejected_at_1_2_0() -> None:
    request, _ = load("findings")
    with pytest.raises(MalformedRequest):
        recording(request["integrity"], "1.2.0")
    # 1.0.0 keeps the published reading.
    old = recording(request["integrity"], "1.0.0")
    assert "mcap-incomplete" in {item["category"] for item in old["findings"]}


def test_published_1_1_0_recording_examples_read_the_same_at_1_2_0() -> None:
    """Without over_limit, 1.2.0 does not change a 1.1.0 reading."""
    for name in ("not-checked", "none-judged"):
        request, result = load(name)
        assert reported(result, "recording")["version"] == "1.1.0"
        payload = request["integrity"]
        earlier = recording(payload, "1.1.0")
        current = recording(payload, "1.2.0")
        assert current["applicable"] == earlier["applicable"]
        assert current["findings"] == earlier["findings"]
        assert current["not_checked"] == earlier["not_checked"]
        assert current.get("percentage") == earlier.get("percentage")
