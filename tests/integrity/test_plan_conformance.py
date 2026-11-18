# SPDX-License-Identifier: Apache-2.0
"""plan-conformance 1.0.0: the plan, the trials and the lock agree."""

from __future__ import annotations

import json
from collections import Counter

from integrity_rules import finding_keys, matches_rules, plan_conformance, reported
from support import (
    ROOT,
    SCHEMA_ROOT,
    assert_invalid,
    assert_valid,
    load_json,
    result_schema,
)

EXAMPLES = ROOT / "examples" / "integrity" / "plan-conformance"
SCHEMA = load_json(SCHEMA_ROOT / "integrity" / "checks" / "plan-conformance.schema.json")


def load(name: str) -> tuple[dict, dict]:
    request = load_json(EXAMPLES / name / "request.json")
    result = load_json(EXAMPLES / name / "result.json")
    return request, result


def test_a_conformant_run_has_no_findings() -> None:
    request, result = load("conformant")
    check = reported(result, "plan-conformance")
    assert check["success"] is True
    assert check["percentage"] == 100
    assert check["findings"] == []
    matches_rules(check, plan_conformance(request["integrity"]))
    assert result["integrity"]["run"]["test_system_status"] == "COMPLETED"


def test_every_finding_category_has_a_triggering_fixture() -> None:
    request, result = load("findings")
    check = reported(result, "plan-conformance")
    assert Counter(category for category, _ in finding_keys(check)) == {
        "trial-count-mismatch": 2,
        "command-speed-mismatch": 1,
        "index-duplicate": 1,
        "index-missing": 2,
        "path-mismatch": 1,
        "index-out-of-range": 1,
    }
    assert check["success"] is False
    # 10 subjects: 3 counts, the command speed, 5 index slots, 1 out-of-range entry.
    # Only index slot 1 conforms and every other subject has a finding.
    assert check["percentage"] == 20
    matches_rules(check, plan_conformance(request["integrity"]))
    assert result["integrity"]["run"]["test_system_status"] == "ERROR"
    assert result["integrity"]["run"]["conclusion"] == "INCONCLUSIVE"
    assert all(item["classification"] == "test_system" for item in check["findings"])


def test_unmet_preconditions_are_not_applicable_and_not_an_error() -> None:
    request, result = load("preconditions-unmet")
    check = reported(result, "plan-conformance")
    assert request["integrity"]["evidence"]["plan-conformance"]["preconditions"] == {"met": False}
    assert check["applicable"] is False
    assert check["success"] is True
    assert "percentage" not in check
    assert check["findings"] == []
    matches_rules(check, plan_conformance(request["integrity"]))
    assert result["integrity"]["run"]["test_system_status"] == "COMPLETED"
    assert result["integrity"]["run"]["percentage"] == 100


def test_the_lock_comparison_is_skipped_when_the_manifest_has_no_lock_block() -> None:
    request, _ = load("conformant")
    evidence = request["integrity"]["evidence"]["plan-conformance"]
    del evidence["lock"]
    expected = plan_conformance(request["integrity"])
    assert expected["findings"] == []
    assert expected["percentage"] == 100
    assert_valid(SCHEMA["$defs"]["evidence"], evidence)


def test_a_doctored_conformant_fixture_is_caught_per_category() -> None:
    request, _ = load("conformant")
    base = request["integrity"]
    cases = {
        "trial-count-mismatch": lambda e: e["trials"].__setitem__("count", 5),
        "command-speed-mismatch": lambda e: e["lock"]["plan"].__setitem__("command_speed", 0.5),
        "index-missing": lambda e: e["trials"]["results"].pop(),
        "index-duplicate": lambda e: e["trials"]["results"].__setitem__(
            3, dict(e["trials"]["results"][0])
        ),
        "path-mismatch": lambda e: e["trials"]["results"][1].__setitem__(
            "path", "trials/trial-9.json"
        ),
        "index-out-of-range": lambda e: e["trials"]["results"][3].__setitem__("index", 0),
    }
    for category, doctor in cases.items():
        doctored = json.loads(json.dumps(base))
        doctor(doctored["evidence"]["plan-conformance"])
        found = {item["category"] for item in plan_conformance(doctored)["findings"]}
        assert category in found, category
        assert plan_conformance(doctored)["percentage"] < 100


def test_trial_indexes_are_exactly_one_to_n() -> None:
    request, _ = load("conformant")
    results = request["integrity"]["evidence"]["plan-conformance"]["trials"]["results"]
    assert [entry["index"] for entry in results] == [1, 2, 3, 4]
    assert [entry["path"] for entry in results] == [
        f"trials/trial-{index:02d}.json" for index in (1, 2, 3, 4)
    ]


def test_the_check_does_not_repeat_completeness_findings() -> None:
    _, result = load("findings")
    check = reported(result, "plan-conformance")
    completeness_categories = {
        "missing-trial",
        "missing-recording",
        "missing-observations",
        "truncated-recording",
        "truncated-observations",
        "empty-recording",
        "empty-observations",
        "ended-by-timeout",
        "ended-by-crash",
    }
    assert completeness_categories.isdisjoint(item["category"] for item in check["findings"])
    for category in sorted(completeness_categories):
        borrowed = json.loads(json.dumps(check))
        borrowed["findings"][0] = {
            "category": category,
            "classification": "test_system",
            "summary": "A completeness finding repeated here.",
        }
        assert_invalid(SCHEMA, borrowed)
    with_trial = json.loads(json.dumps(check))
    with_trial["findings"][0]["trial_id"] = "trial-01"
    assert_invalid(SCHEMA, with_trial)


def test_a_robot_verdict_has_no_field_to_occupy() -> None:
    _, result = load("findings")
    document = json.loads(json.dumps(result))
    document["integrity"]["checks"][0]["verdict"] = "FAIL"
    assert_invalid(result_schema(), document)
    non_test_system = json.loads(json.dumps(result))
    non_test_system["integrity"]["checks"][0]["findings"][0]["classification"] = "robot_variation"
    assert_invalid(result_schema(), non_test_system)


def test_the_evidence_schema_rejects_a_negative_count_and_a_verdict() -> None:
    request, _ = load("conformant")
    evidence = request["integrity"]["evidence"]["plan-conformance"]
    negative = json.loads(json.dumps(evidence))
    negative["plan"]["trial_count"] = -1
    assert_invalid(SCHEMA["$defs"]["evidence"], negative)
    with_extra = json.loads(json.dumps(evidence))
    with_extra["verdict"] = "PASS"
    assert_invalid(SCHEMA["$defs"]["evidence"], with_extra)
