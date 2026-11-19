# SPDX-License-Identifier: Apache-2.0
"""A run where no check is applicable reads INCONCLUSIVE with no percentage (livingproof-evaluator#38).

Aaron's decision: if every reported check is not applicable, the run is not a pass. From result
format 1.2.0 the run has ``test_system_status`` ``INCONCLUSIVE``, ``conclusion`` ``INCONCLUSIVE``,
``success`` false, and no ``percentage``. Results at 1.0.0 and 1.1.0 keep the old reading
(COMPLETED, 100) and stay valid.
"""

from __future__ import annotations

import copy

from validate_contract import validate_document

from integrity_rules import run_summary
from support import ROOT, assert_invalid, assert_valid, load_json, result_schema

EXAMPLE = ROOT / "examples" / "integrity" / "all-not-applicable"
DOC = (ROOT / "docs" / "run-integrity.md").read_text()
LEGACY = ROOT / "examples" / "integrity" / "completeness-preconditions-unmet"


def _result() -> dict:
    return load_json(EXAMPLE / "result.json")


def test_the_example_is_a_valid_1_2_0_result_with_no_applicable_check() -> None:
    result = _result()
    assert result["format"] == "livingproof-evaluator-result/1.2.0"
    assert validate_document(result) == []
    checks = result["integrity"]["checks"]
    assert checks and all(check["applicable"] is False for check in checks)
    run = result["integrity"]["run"]
    assert run["test_system_status"] == "INCONCLUSIVE"
    assert run["conclusion"] == "INCONCLUSIVE"
    assert run["success"] is False
    assert "percentage" not in run


def test_the_example_run_is_what_the_reference_rule_derives() -> None:
    result = _result()["integrity"]
    request = load_json(EXAMPLE / "request.json")["integrity"]
    assert result["run"] == run_summary(request["manifest"]["id"], result["checks"], 2)
    assert [t["id"] for t in result["trials"]] == [
        t["id"] for t in request["manifest"]["planned_trials"]
    ]


def test_the_rule_for_the_other_cases() -> None:
    applicable = {"applicable": True, "success": True, "percentage": 80}
    failed = {"applicable": True, "success": False, "percentage": 40}
    off = {"applicable": False, "success": True}
    assert run_summary("r", [applicable, off], 2) == {
        "id": "r",
        "test_system_status": "COMPLETED",
        "success": True,
        "percentage": 80,
    }
    assert run_summary("r", [failed, off], 2)["test_system_status"] == "ERROR"
    assert run_summary("r", [failed, off], 2)["percentage"] == 40
    # Before 1.2.0 the same all-not-applicable checks read COMPLETED and 100.
    assert run_summary("r", [off, off], 1) == {
        "id": "r",
        "test_system_status": "COMPLETED",
        "success": True,
        "percentage": 100,
    }
    assert run_summary("r", [off], 2)["test_system_status"] == "INCONCLUSIVE"


def test_a_1_2_0_result_with_nothing_applicable_cannot_read_completed_100() -> None:
    document = _result()
    document["integrity"]["run"] = {
        "id": document["integrity"]["run"]["id"],
        "test_system_status": "COMPLETED",
        "success": True,
        "percentage": 100,
    }
    assert validate_document(document) != []


def test_an_inconclusive_run_may_not_carry_a_percentage_or_success() -> None:
    schema = result_schema()
    for edit in ({"percentage": 100}, {"success": True}):
        document = _result()
        document["integrity"]["run"].update(edit)
        assert_invalid(schema, document)


def test_the_inconclusive_status_needs_result_format_1_2_0() -> None:
    document = _result()
    document["format"] = "livingproof-evaluator-result/1.1.0"
    assert_invalid(result_schema(), document)


def test_an_applicable_check_keeps_the_old_reading_at_1_2_0() -> None:
    document = copy.deepcopy(load_json(ROOT / "examples" / "integrity" / "clean" / "result.json"))
    document["format"] = "livingproof-evaluator-result/1.2.0"
    assert validate_document(document) == []
    assert document["integrity"]["run"]["test_system_status"] == "COMPLETED"


def test_a_1_1_0_result_with_nothing_applicable_stays_valid() -> None:
    legacy = load_json(LEGACY / "result.json")
    assert legacy["integrity"]["run"]["percentage"] == 100
    assert_valid(result_schema(), legacy)
    assert validate_document(legacy) == []


def test_the_docs_state_the_rule_and_the_migration() -> None:
    assert "examples/integrity/all-not-applicable/" in DOC
    assert "INCONCLUSIVE" in DOC and "no percentage" in DOC
    assert "livingproof-evaluator-result/1.2.0" in DOC
    assert "Migration" in DOC and "1.2.0" in DOC


def test_the_run_schema_describes_the_new_reading() -> None:
    run = load_json(ROOT / "schema" / "integrity" / "result.schema.json")["$defs"]["run"]
    assert "INCONCLUSIVE" in run["properties"]["test_system_status"]["enum"]
    assert "percentage" not in run["required"]
    assert "not applicable" in run["properties"]["percentage"]["description"].lower()
