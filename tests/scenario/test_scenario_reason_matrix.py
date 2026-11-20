# SPDX-License-Identifier: Apache-2.0
"""The reason on a scenario step: every verdict against every reason (Vera, verification of PR 59).

`reason` belongs to NOT_EVALUATED alone, and NOT_EVALUATED must always carry one of the three.
The first test of the PR pins FAIL only; a mutation that let PASS or INCONCLUSIVE carry a reason
survived. The docs and the schema description must also name every reason the enum allows.
"""

from __future__ import annotations

import pytest

from support import ROOT, SCHEMA_ROOT, assert_invalid, assert_valid, load_json

SCHEMA = SCHEMA_ROOT / "scenario" / "result.schema.json"
REASONS = ["unknown_step", "unbound_observable", "missing_threshold"]


def _payload(verdict: str, reason: str | None) -> dict:
    step = {"id": "hallway-fall", "verdict": verdict, "summary": "x"}
    if reason is not None:
        step["reason"] = reason
    return {"trial_id": "stock-seed-01", "steps": [step]}


@pytest.mark.parametrize("reason", REASONS)
@pytest.mark.parametrize("verdict", ["PASS", "FAIL", "INCONCLUSIVE"])
def test_only_not_evaluated_carries_a_reason(verdict: str, reason: str) -> None:
    schema = load_json(SCHEMA)
    assert_valid(schema, _payload(verdict, None))
    assert_invalid(schema, _payload(verdict, reason))


@pytest.mark.parametrize("reason", REASONS)
def test_not_evaluated_takes_each_of_the_three_reasons_and_needs_one(reason: str) -> None:
    schema = load_json(SCHEMA)
    assert_valid(schema, _payload("NOT_EVALUATED", reason))
    assert_invalid(schema, _payload("NOT_EVALUATED", None))


def test_the_enum_is_exactly_the_three_reasons() -> None:
    step = load_json(SCHEMA)["$defs"]["step"]["properties"]["reason"]
    assert step == {"enum": REASONS}


def test_the_docs_and_the_schema_description_name_every_reason() -> None:
    docs = " ".join((ROOT / "docs" / "run-integrity.md").read_text().split())
    description = load_json(SCHEMA)["description"]
    for reason in REASONS:
        assert f"`{reason}`" in docs, reason
        assert reason in description, reason
