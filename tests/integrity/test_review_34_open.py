# SPDX-License-Identifier: Apache-2.0
"""Review checks for livingproof-evaluator#34 that fail at a914fb9 until the contract says one thing.

1. A pin neither side carries has two readings: the rule lists it as not-declared (the lock is
   tested first), the PR description says not-recorded, and no schema or doc sentence says either.
2. A recording check that judged nothing (every trial not present, or present and never read)
   drops its not_checked list, while pins keeps all five in the same situation and the docs list
   every trial that was not judged.
"""

from __future__ import annotations

import copy
import re

from integrity_rules import pins, recording
from support import ROOT, SCHEMA_ROOT, load_json

EXAMPLES = ROOT / "examples" / "integrity"


def test_the_contract_states_the_reason_for_a_pin_neither_side_carries() -> None:
    description = load_json(SCHEMA_ROOT / "integrity" / "checks" / "pins.schema.json")[
        "description"
    ]
    stated = re.search(r"neither[^.]*?(not-recorded|not-declared)", description)
    assert stated, "pins.schema.json does not say which reason a pin neither side carries has"
    payload = {
        "manifest": {"pins": {"runner": {"sha256": "a" * 64}}},
        "lock": {"pins": {"runner": {"sha256": "a" * 64}}},
    }
    reasons = {item["subject"]: item["reason"] for item in pins(payload)["not_checked"]}
    assert reasons["world"] == stated.group(1)


def _request() -> dict:
    return load_json(EXAMPLES / "completeness-recording-listed-missing" / "request.json")[
        "integrity"
    ]


def test_a_recording_check_that_judged_nothing_still_lists_what_it_did_not_judge() -> None:
    request = _request()
    missing = copy.deepcopy(request)
    for trial in missing["trials"]:
        trial["recording"] = {"state": "missing"}
    expected = recording(missing)
    assert expected["applicable"] is False and "percentage" not in expected
    assert expected.get("not_checked") == [
        {"trial_id": t["id"], "reason": "not-present"} for t in missing["trials"]
    ]
    unread = copy.deepcopy(request)
    for trial in unread["trials"]:
        trial["recording"] = {"state": "present", "sha256": "a" * 64}
    unread["evidence"]["recording"]["trials"] = []
    expected = recording(unread)
    assert expected["applicable"] is False
    assert expected.get("not_checked") == [
        {"trial_id": t["id"], "reason": "not-recorded"} for t in unread["trials"]
    ]
