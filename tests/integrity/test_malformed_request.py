# SPDX-License-Identifier: Apache-2.0
"""Inconsistent input to recording 1.1.0 fails closed (Rivet's decision on PR 37).

A trial whose ``recording.state`` is ``present`` while ``evidence.recording`` says its MCAP file
is ``incomplete`` is inconsistent: the producer must classify a file with no valid footer as
``truncated`` while reading, so completeness reports it. Silently listing the trial as
``not-present`` would leave nothing reporting it. From 1.1.0 the request is malformed: an
evaluator writes no result and exits with status 2, as it does for any other malformed request.
The reference rules express that as ``MalformedRequest``. 1.0.0 keeps its published behaviour.

The contract has no request-schema way to say this: the two facts sit in different arrays, and
the published 1.0.0 ``recording/findings`` request has to stay valid.
"""

from __future__ import annotations

import copy
import random

import pytest

import integrity_rules
from support import ROOT, SCHEMA_ROOT, assert_invalid, assert_valid, example_dirs, load_json

EXAMPLES = ROOT / "examples" / "integrity"
RECORDING_SCHEMA = load_json(SCHEMA_ROOT / "integrity" / "checks" / "recording.schema.json")
DOC = (ROOT / "docs" / "run-integrity.md").read_text()


def clean() -> dict:
    return copy.deepcopy(load_json(EXAMPLES / "recording" / "clean" / "request.json")["integrity"])


def inconsistent() -> dict:
    payload = clean()
    payload["evidence"]["recording"]["trials"][0]["mcap"]["state"] = "incomplete"
    return payload


def _set_recording_state(payload: dict, index: int, state: str) -> None:
    payload["trials"][index]["recording"] = (
        {"state": state, "sha256": "a" * 64}
        if state in ("present", "truncated")
        else {"state": state}
    )


def test_a_present_trial_whose_evidence_says_incomplete_is_rejected() -> None:
    assert issubclass(integrity_rules.MalformedRequest, ValueError)
    with pytest.raises(integrity_rules.MalformedRequest) as raised:
        integrity_rules.recording(inconsistent())
    message = str(raised.value)
    assert "trial-01" in message and "truncated" in message


def test_the_default_version_is_1_1_0_so_the_default_call_rejects_it() -> None:
    with pytest.raises(integrity_rules.MalformedRequest):
        integrity_rules.recording(inconsistent(), "1.1.0")
    with pytest.raises(integrity_rules.MalformedRequest):
        integrity_rules.recording(inconsistent())


def test_version_1_0_0_keeps_its_published_behaviour() -> None:
    old = integrity_rules.recording(inconsistent(), "1.0.0")
    assert [i["category"] for i in old["findings"]] == ["mcap-incomplete"]
    assert "not_checked" not in old and old["percentage"] == 50


def test_the_published_1_0_0_findings_request_is_rejected_at_1_1_0_and_judged_at_1_0_0() -> None:
    request = load_json(EXAMPLES / "recording" / "findings" / "request.json")["integrity"]
    with pytest.raises(integrity_rules.MalformedRequest):
        integrity_rules.recording(request, "1.1.0")
    assert integrity_rules.recording(request, "1.0.0")["applicable"] is True


def test_a_consistent_request_is_not_rejected() -> None:
    assert integrity_rules.recording(clean())["not_checked"] == []
    truncated = inconsistent()
    truncated["trials"][0]["recording"]["state"] = "truncated"  # classified, as the decision says
    result = integrity_rules.recording(truncated)
    assert result["not_checked"] == [{"trial_id": "trial-01", "reason": "not-present"}]
    assert result["findings"] == []


def test_an_incomplete_entry_for_a_trial_that_is_not_present_is_not_inconsistent() -> None:
    for state in ("missing", "empty"):
        payload = inconsistent()
        payload["trials"][0]["recording"] = {"state": state}
        result = integrity_rules.recording(payload)
        assert result["not_checked"] == [{"trial_id": "trial-01", "reason": "not-present"}]


def test_no_media_means_nothing_to_be_inconsistent_about() -> None:
    payload = clean()
    payload["evidence"]["recording"] = {"media_available": False, "trials": []}
    assert integrity_rules.recording(payload)["applicable"] is False


def test_rejection_is_total_not_per_trial() -> None:
    """One inconsistent trial among clean ones still rejects the whole request: no result."""
    payload = clean()
    donor = copy.deepcopy(payload["evidence"]["recording"]["trials"][1])
    donor["mcap"]["state"] = "incomplete"
    payload["evidence"]["recording"]["trials"][1] = donor
    with pytest.raises(integrity_rules.MalformedRequest):
        integrity_rules.recording(payload)


def test_the_rule_rejects_exactly_the_inconsistent_inputs() -> None:
    rng = random.Random(37)
    base = clean()
    for _ in range(300):
        payload = copy.deepcopy(base)
        expected = False
        for trial, entry in zip(payload["trials"], payload["evidence"]["recording"]["trials"]):
            state = rng.choice(["present", "present", "missing", "truncated", "empty"])
            trial["recording"] = (
                {"state": state, "sha256": "a" * 64}
                if state in ("present", "truncated")
                else {"state": state}
            )
            entry["mcap"]["state"] = rng.choice(["complete", "incomplete"])
            expected |= state == "present" and entry["mcap"]["state"] == "incomplete"
        if expected:
            with pytest.raises(integrity_rules.MalformedRequest):
                integrity_rules.recording(payload)
        else:
            integrity_rules.recording(payload)


@pytest.mark.parametrize("bad_state", ["garbled", None])
@pytest.mark.parametrize("recording_state", ["present", "missing", "truncated", "empty"])
def test_an_unknown_mcap_state_is_rejected_and_names_the_actual_state(
    recording_state: str, bad_state: str | None
) -> None:
    payload = clean()
    _set_recording_state(payload, 0, recording_state)
    payload["evidence"]["recording"]["trials"][0]["mcap"]["state"] = bad_state
    assert_invalid(RECORDING_SCHEMA["$defs"]["evidence"], payload["evidence"]["recording"])
    with pytest.raises(integrity_rules.MalformedRequest) as raised:
        integrity_rules.recording(payload)
    message = str(raised.value)
    assert "trial-01" in message
    assert repr(bad_state) in message
    assert recording_state in message
    assert "incomplete" not in message
    assert "missing" not in message.replace(f"recording.state is {recording_state}", "")
    old = integrity_rules.recording(payload, "1.0.0")
    if recording_state == "present":
        assert [i["category"] for i in old["findings"]] == ["mcap-incomplete"]
    else:
        assert old["findings"] == [] and old["percentage"] == 100


@pytest.mark.parametrize("recording_state", ["present", "missing", "truncated", "empty"])
def test_a_missing_mcap_state_raises_malformed_request_not_key_error(
    recording_state: str,
) -> None:
    payload = clean()
    _set_recording_state(payload, 0, recording_state)
    del payload["evidence"]["recording"]["trials"][0]["mcap"]["state"]
    assert_invalid(RECORDING_SCHEMA["$defs"]["evidence"], payload["evidence"]["recording"])
    with pytest.raises(integrity_rules.MalformedRequest) as raised:
        integrity_rules.recording(payload)
    message = str(raised.value)
    assert "trial-01" in message
    assert "missing" in message
    assert recording_state in message
    if recording_state == "present":
        with pytest.raises(KeyError):
            integrity_rules.recording(payload, "1.0.0")
    else:
        old = integrity_rules.recording(payload, "1.0.0")
        assert old["findings"] == [] and old["percentage"] == 100


@pytest.mark.parametrize("mcap_state", ["complete", "incomplete", None])
def test_an_evidence_trial_not_in_trials_is_rejected_at_1_1_0_and_ignored_at_1_0_0(
    mcap_state: str | None,
) -> None:
    payload = clean()
    extra = copy.deepcopy(payload["evidence"]["recording"]["trials"][0])
    extra["id"] = "trial-unknown"
    if mcap_state is None:
        del extra["mcap"]["state"]
    else:
        extra["mcap"]["state"] = mcap_state
    payload["evidence"]["recording"]["trials"].append(extra)
    if mcap_state is not None:
        assert_valid(RECORDING_SCHEMA["$defs"]["evidence"], payload["evidence"]["recording"])
    with pytest.raises(integrity_rules.MalformedRequest) as raised:
        integrity_rules.recording(payload)
    message = str(raised.value)
    assert "trial-unknown" in message
    assert (mcap_state or "missing") in message
    assert integrity_rules.recording(payload, "1.0.0") == integrity_rules.recording(
        clean(), "1.0.0"
    )


def test_every_1_1_0_example_request_is_consistent() -> None:
    seen = 0
    for example in example_dirs():
        result = load_json(example / "result.json")
        if result["evaluator"]["kind"] != "integrity":
            continue
        request = load_json(example / "request.json")["integrity"]
        for check in result["integrity"]["checks"]:
            if check["id"] == "recording" and check["version"] == "1.1.0":
                seen += 1
                integrity_rules.recording(request, "1.1.0")  # does not raise
    assert seen >= 3


def test_the_schema_and_docs_say_the_request_is_rejected() -> None:
    schema = load_json(SCHEMA_ROOT / "integrity" / "checks" / "recording.schema.json")
    state = schema["$defs"]["evidence"]["properties"]["trials"]["items"]["properties"]["mcap"][
        "properties"
    ]["state"]["description"]
    assert "malformed" in state and "present" in state
    assert "malformed" in schema["description"] and "not in trials" in schema["description"]
    assert "MalformedRequest" in DOC and "no result" in DOC and "status 2" in DOC
    assert "not in `trials`" in DOC
    assert "is not `complete` or `incomplete`" in DOC and "instead of a `KeyError`" in DOC
    assert "not judged either" not in DOC  # the earlier, silent reading
