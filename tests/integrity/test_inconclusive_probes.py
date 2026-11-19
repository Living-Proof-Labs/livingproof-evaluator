# SPDX-License-Identifier: Apache-2.0
"""Independent schema probes for the INCONCLUSIVE run reading (livingproof-evaluator#38)."""

from __future__ import annotations

import copy

import pytest
from validate_contract import validate_document

from support import ROOT, load_json, result_schema, schema_errors

NA = load_json(ROOT / "examples" / "integrity" / "all-not-applicable" / "result.json")
CLEAN = load_json(ROOT / "examples" / "integrity" / "clean" / "result.json")
INCONCLUSIVE = {
    "test_system_status": "INCONCLUSIVE",
    "conclusion": "INCONCLUSIVE",
    "success": False,
}
COMPLETED = {"test_system_status": "COMPLETED", "success": True, "percentage": 100}


def _doc(base: dict, minor: int, run_edit: dict, drop: tuple[str, ...] = ()) -> dict:
    document = copy.deepcopy(base)
    document["format"] = f"livingproof-evaluator-result/1.{minor}.0"
    run = document["integrity"]["run"]
    for key in drop:
        run.pop(key, None)
    run.update(run_edit)
    return document


def _mixed() -> dict:
    document = copy.deepcopy(CLEAN)
    document["format"] = "livingproof-evaluator-result/1.2.0"
    not_applicable = copy.deepcopy(NA["integrity"]["checks"][0])
    checks = document["integrity"]["checks"]
    document["integrity"]["checks"] = [c for c in checks if c["id"] != not_applicable["id"]]
    document["integrity"]["checks"].append(not_applicable)
    return document


def _valid(document: dict) -> bool:
    return schema_errors(result_schema(), document) == [] and validate_document(document) == []


@pytest.mark.parametrize(
    ("minor", "edit", "drop", "expected"),
    [
        (2, {}, (), True),
        (2, {"percentage": 100}, (), False),
        (2, {"success": True}, (), False),
        (2, {}, ("conclusion",), False),
        (2, {**COMPLETED}, ("conclusion",), False),
        (2, {"test_system_status": "ERROR", "success": False, "percentage": 0}, (), False),
        (1, {}, (), False),
        (1, {"percentage": 100}, (), False),
        (0, {}, (), False),
        (0, {"percentage": 100}, (), False),
        (1, {**COMPLETED}, ("conclusion",), True),
        (0, {**COMPLETED}, ("conclusion",), True),
    ],
)
def test_all_not_applicable_probe_matrix(minor, edit, drop, expected) -> None:
    assert _valid(_doc(NA, minor, edit, drop)) is expected


def test_mixed_run_reads_as_before_at_1_2_0() -> None:
    assert _valid(_mixed())


def test_empty_checks_are_refused_at_1_2_0() -> None:
    document = copy.deepcopy(NA)
    document["integrity"]["checks"] = []
    assert not _valid(document)


def test_a_run_with_an_applicable_check_cannot_be_inconclusive_at_1_2_0() -> None:
    for base in (_mixed(), _doc(CLEAN, 2, {}, ())):
        document = _doc(base, 2, INCONCLUSIVE, ("percentage",))
        assert not _valid(document)
