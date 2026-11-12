# SPDX-License-Identifier: Apache-2.0
"""Shared envelope, both evaluator kinds, and the integrity check index."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from support import (
    EXAMPLES,
    REGISTRY_PATH,
    ROBOT_KEYS,
    ROOT,
    SCHEMA_ROOT,
    assert_invalid,
    assert_valid,
    check_registry,
    example_dirs,
    load_json,
    request_schema,
    result_schema,
    schema_registry,
    validator_for,
    walk_keys,
    walk_strings,
)

K_OF_N = re.compile(r"\b\d+\s+of\s+\d+\b|\b\d+\s*/\s*\d+\b")
ROBOT_TOKENS = {"PASS", "FAIL", "pass", "fail"}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def test_schemas_are_draft_2020_12() -> None:
    registry = schema_registry()
    assert registry.contents(
        "https://github.com/Living-Proof-Labs/livingproof-evaluator/schema/defs.schema.json"
    )
    for path in SCHEMA_ROOT.rglob("*.schema.json"):
        schema = load_json(path)
        validator_for(schema)


def test_check_registry_matches_its_schema() -> None:
    schema = load_json(SCHEMA_ROOT / "integrity" / "checks" / "registry.schema.json")
    assert_valid(schema, load_json(REGISTRY_PATH))
    ids = [entry["id"] for entry in check_registry()]
    assert ids == sorted(set(ids), key=ids.index)
    assert len(ids) == len(set(ids))


def test_check_schemas_do_not_reference_each_other() -> None:
    paths = sorted((SCHEMA_ROOT / "integrity" / "checks").glob("*.schema.json"))
    check_paths = [path for path in paths if path.name != "registry.schema.json"]
    for path in check_paths:
        text = path.read_text()
        for other in check_paths:
            if other != path:
                assert other.name not in text


@pytest.mark.parametrize(
    "example", example_dirs(), ids=lambda path: str(path.relative_to(EXAMPLES))
)
def test_example_validates_against_the_envelope(example: Path) -> None:
    request = load_json(example / "request.json")
    result = load_json(example / "result.json")
    assert_valid(request_schema(), request)
    assert_valid(result_schema(), result)
    kind = request["evaluator"]["kind"]
    assert result["evaluator"] == request["evaluator"]
    assert result["inputs"] == request["inputs"]
    assert kind in request and kind in result
    other = "scenario" if kind == "integrity" else "integrity"
    assert other not in request
    assert other not in result
    assert request["timestamps"]["requested_at"] <= result["timestamps"]["started_at"]
    assert result["timestamps"]["started_at"] <= result["timestamps"]["completed_at"]


@pytest.mark.parametrize(
    "example", example_dirs(), ids=lambda path: str(path.relative_to(EXAMPLES))
)
def test_embedded_inputs_match_their_hashes(example: Path) -> None:
    request = load_json(example / "request.json")
    payload = request[request["evaluator"]["kind"]]
    for ref in request["inputs"]:
        if ref["role"] in payload:
            digest = hashlib.sha256(canonical(payload[ref["role"]])).hexdigest()
            assert ref["sha256"] == digest


def test_integrity_results_have_no_robot_verdict_shape() -> None:
    for example in example_dirs():
        result = load_json(example / "result.json")
        if result["evaluator"]["kind"] != "integrity":
            continue
        keys = set(walk_keys(result["integrity"]))
        assert keys.isdisjoint(ROBOT_KEYS)
        tokens = set(walk_strings(result["integrity"]))
        assert tokens.isdisjoint(ROBOT_TOKENS)
        for text in walk_strings(result["integrity"]):
            assert K_OF_N.search(text) is None


def test_integrity_run_uses_success_and_percentage() -> None:
    for example in example_dirs():
        result = load_json(example / "result.json")
        if result["evaluator"]["kind"] != "integrity":
            continue
        request = load_json(example / "request.json")
        payload = result["integrity"]
        planned = [item["id"] for item in request["integrity"]["manifest"]["planned_trials"]]
        evidence_ids = [trial["id"] for trial in request["integrity"]["trials"]]
        assert len(planned) == len(set(planned))
        assert len(evidence_ids) == len(set(evidence_ids))
        assert set(evidence_ids) <= set(planned)
        assert [trial["id"] for trial in payload["trials"]] == planned
        checks = payload["checks"]
        assert len({check["id"] for check in checks}) == len(checks)
        success = all(check["success"] for check in checks)
        applicable = [check["percentage"] for check in checks if check["applicable"]]
        expected = min(applicable) if applicable else 100
        assert payload["run"]["success"] is success
        assert payload["run"]["percentage"] == expected
        assert payload["run"]["id"] == request["integrity"]["manifest"]["id"]
        if success:
            assert payload["run"]["test_system_status"] == "COMPLETED"
            assert "conclusion" not in payload["run"]
        else:
            assert payload["run"]["test_system_status"] == "ERROR"
            assert payload["run"]["conclusion"] == "INCONCLUSIVE"
        by_id = {entry["id"]: entry for entry in check_registry()}
        for check in checks:
            entry = by_id[check["id"]]
            assert check["version"] == entry["version"]
            assert_valid(load_json(ROOT / entry["schema"]), check)


def test_registry_examples_validate_their_check_and_evidence() -> None:
    for entry in check_registry():
        schema = load_json(ROOT / entry["schema"])
        for relative in entry["examples"]:
            example = ROOT / relative
            result = load_json(example / "result.json")
            reported = [
                check for check in result["integrity"]["checks"] if check["id"] == entry["id"]
            ]
            assert len(reported) == 1
            assert_valid(schema, reported[0])
            evidence_schema = schema.get("$defs", {}).get("evidence")
            evidence = load_json(example / "request.json")["integrity"].get("evidence", {})
            if evidence_schema is None:
                assert entry["id"] not in evidence
            else:
                assert_valid(evidence_schema, evidence[entry["id"]])


def test_integrity_schema_rejects_a_robot_verdict() -> None:
    schema = result_schema()
    document = load_json(EXAMPLES / "integrity" / "clean" / "result.json")
    with_verdict = json.loads(json.dumps(document))
    with_verdict["integrity"]["verdict"] = "PASS"
    assert_invalid(schema, with_verdict)
    with_grade = json.loads(json.dumps(document))
    with_grade["integrity"]["run"]["grade"] = "FAIL"
    assert_invalid(schema, with_grade)
    with_scenario = json.loads(json.dumps(document))
    with_scenario["scenario"] = {"trial_id": "trial-01", "steps": []}
    assert_invalid(schema, with_scenario)
    with_category = json.loads(json.dumps(document))
    with_category["integrity"]["checks"][0]["findings"] = [
        {
            "category": "pass",
            "classification": "test_system",
            "summary": "Robot verdict stored as a finding.",
        }
    ]
    with_category["integrity"]["checks"][0]["success"] = False
    with_category["integrity"]["run"]["success"] = False
    with_category["integrity"]["run"]["test_system_status"] = "ERROR"
    with_category["integrity"]["run"]["conclusion"] = "INCONCLUSIVE"
    with_category["integrity"]["run"]["percentage"] = 0
    assert_invalid(schema, with_category)


def test_scenario_schema_rejects_an_integrity_payload() -> None:
    schema = result_schema()
    document = load_json(EXAMPLES / "scenario" / "graded" / "result.json")
    mixed = json.loads(json.dumps(document))
    mixed["integrity"] = {"run": {"success": True}}
    assert_invalid(schema, mixed)
    missing_reason = json.loads(json.dumps(document))
    missing_reason["scenario"]["steps"][0]["verdict"] = "NOT_EVALUATED"
    assert_invalid(schema, missing_reason)


def test_clean_run_reports_successful_checks() -> None:
    result = load_json(EXAMPLES / "integrity" / "clean" / "result.json")
    checks = {check["id"]: check for check in result["integrity"]["checks"]}
    assert set(checks) == {"completeness", "pins", "same-input-agreement"}
    for check in checks.values():
        assert check["success"] is True
        assert check["percentage"] == 100
        assert check["findings"] == []
    assert result["integrity"]["run"]["success"] is True
    assert result["integrity"]["run"]["percentage"] == 100


def test_design_note_opens_with_the_growth_principle() -> None:
    text = (ROOT / "docs" / "run-integrity.md").read_text()
    opening, _rest = text.split("##", 1)
    assert "Run integrity grows one check at a time." in opening
    assert "the run that would have caught it." in opening
    assert "livingproof-evaluator-run-integrity" in text
    assert "HTTP 404" in text
    assert "robot variation" in text
