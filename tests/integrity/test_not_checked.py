# SPDX-License-Identifier: Apache-2.0
"""not_checked: a subject a check did not check, and the denominator of a check's percentage.

The rule these tests pin (livingproof-evaluator#34): a check's percentage is 100 times the
checked subjects without a finding divided by the checked subjects. A subject that was not
checked is listed in ``not_checked`` and is not in the denominator. A check with nothing
checked is not applicable. Versions: pins, completeness and termination move to 1.1.0 and keep
1.0.0 valid; plan-conformance and recording keep 1.0.0 and may report ``not_checked``.
"""

from __future__ import annotations

import copy
import random

import pytest

from integrity_rules import PIN_SUBJECTS, pins
from support import (
    ROOT,
    SCHEMA_ROOT,
    assert_invalid,
    assert_valid,
    check_registry,
    example_dirs,
    load_json,
    request_schema,
    result_schema,
)

CHECKS = SCHEMA_ROOT / "integrity" / "checks"
EXAMPLES = ROOT / "examples" / "integrity"
REASONS = {"not-recorded", "not-declared", "not-present"}
REPORTS_NOT_CHECKED = {"pins", "plan-conformance", "recording"}
LATEST = {
    "completeness": ("1.1.0", ["1.0.0"]),
    "pins": ("1.1.0", ["1.0.0"]),
    "same-input-agreement": ("1.0.0", None),
    "ci-publisher": ("1.0.0", None),
    "plan-conformance": ("1.1.0", ["1.0.0"]),
    "termination": ("1.1.0", ["1.0.0"]),
    "recording": ("1.2.0", ["1.0.0", "1.1.0"]),
}


def schema_for(check_id: str) -> dict:
    return load_json(CHECKS / f"{check_id}.schema.json")


def minimal(check_id: str, version: str) -> dict:
    """A smallest valid check object for each id, not applicable so it needs nothing else."""
    check = {
        "id": check_id,
        "version": version,
        "applicable": False,
        "success": True,
        "findings": [],
    }
    if check_id == "termination":
        check["referrals"] = []
    if check_id in REPORTS_NOT_CHECKED and version != "1.0.0":
        # not_checked is required from 1.1.0. A pins check that is not applicable checked
        # nothing, so it lists all five subjects.
        check["not_checked"] = (
            [{"subject": s, "reason": "not-declared"} for s in PIN_SUBJECTS]
            if check_id == "pins"
            else []
        )
    return check


# The field.


def test_the_shared_check_definition_has_an_optional_not_checked_list() -> None:
    check = load_json(SCHEMA_ROOT / "integrity" / "result.schema.json")["$defs"]["check"]
    assert "not_checked" in check["properties"]
    assert "not_checked" not in check["required"]
    item = load_json(SCHEMA_ROOT / "integrity" / "result.schema.json")["$defs"]["not_checked"]
    assert set(item["properties"]) == {"subject", "trial_id", "reason"}
    assert set(item["properties"]["reason"]["enum"]) == REASONS


@pytest.mark.parametrize(
    "item",
    [
        {"subject": "specs", "reason": "not-recorded"},
        {"subject": "verifier", "reason": "not-declared"},
        {"subject": "configuration", "reason": "not-recorded"},
    ],
)
def test_a_not_checked_pin_subject_is_valid(item: dict) -> None:
    check = minimal("pins", "1.1.0")
    check.update(applicable=True, percentage=100)
    check["not_checked"] = [item]
    assert_valid(schema_for("pins"), check)


@pytest.mark.parametrize(
    "item",
    [
        {"subject": "specs"},  # no reason
        {"reason": "not-recorded"},  # no subject
        {"subject": "specs", "trial_id": "trial-01", "reason": "not-recorded"},  # both
        {"subject": "specs", "reason": "skipped"},  # reason outside the vocabulary
        {"subject": "specs", "reason": ""},
        {"subject": "specs", "reason": "not-recorded", "summary": "Not recorded."},
        {"subject": "specs", "reason": "not-recorded", "category": "hash-mismatch"},
        {"subject": "specs", "reason": "not-recorded", "percentage": 0},
        {"subject": "bogus", "reason": "not-recorded"},  # not one of the five
        {"trial_id": "trial-01", "reason": "not-present"},  # pins has subjects, not trials
    ],
)
def test_a_malformed_not_checked_item_is_rejected_on_pins(item: dict) -> None:
    check = minimal("pins", "1.1.0")
    check.update(applicable=True, percentage=100)
    check["not_checked"] = [item]
    assert_invalid(schema_for("pins"), check)


def test_the_same_subject_cannot_be_listed_twice() -> None:
    check = minimal("pins", "1.1.0")
    check.update(applicable=True, percentage=100)
    check["not_checked"] = [
        {"subject": "specs", "reason": "not-recorded"},
        {"subject": "specs", "reason": "not-recorded"},
    ]
    assert_invalid(schema_for("pins"), check)


@pytest.mark.parametrize(
    "check_id", ["completeness", "termination", "same-input-agreement", "ci-publisher"]
)
def test_checks_with_nothing_to_skip_reject_not_checked(check_id: str) -> None:
    version = LATEST[check_id][0]
    check = minimal(check_id, version)
    assert_valid(schema_for(check_id), check)
    check["not_checked"] = [{"subject": "specs", "reason": "not-recorded"}]
    assert_invalid(schema_for(check_id), check)


def test_the_envelope_rejects_not_checked_on_a_check_that_does_not_report_it() -> None:
    result = load_json(EXAMPLES / "clean" / "result.json")
    completeness = next(c for c in result["integrity"]["checks"] if c["id"] == "completeness")
    completeness["not_checked"] = [{"subject": "specs", "reason": "not-recorded"}]
    assert_invalid(result_schema(), result)


def test_a_not_applicable_check_may_say_what_it_did_not_check() -> None:
    check = minimal("pins", "1.1.0")
    assert_valid(schema_for("pins"), check)
    check["percentage"] = 100
    assert_invalid(schema_for("pins"), check)


def test_plan_conformance_and_recording_name_what_they_may_skip() -> None:
    plan = minimal("plan-conformance", "1.1.0")
    plan["not_checked"] = [{"subject": "lock-command-speed", "reason": "not-declared"}]
    assert_valid(schema_for("plan-conformance"), plan)
    plan["not_checked"] = [{"subject": "specs", "reason": "not-declared"}]
    assert_invalid(schema_for("plan-conformance"), plan)
    plan["not_checked"] = [{"trial_id": "trial-01", "reason": "not-present"}]
    assert_invalid(schema_for("plan-conformance"), plan)
    recording = minimal("recording", "1.1.0")
    recording["not_checked"] = [{"trial_id": "trial-01", "reason": "not-present"}]
    assert_valid(schema_for("recording"), recording)
    recording["not_checked"] = [{"subject": "specs", "reason": "not-present"}]
    assert_invalid(schema_for("recording"), recording)


@pytest.mark.parametrize("check_id", ["plan-conformance", "recording"])
def test_not_checked_is_required_from_1_1_0_and_not_allowed_at_1_0_0(check_id: str) -> None:
    new = minimal(check_id, "1.1.0")
    assert_valid(schema_for(check_id), new)
    del new["not_checked"]
    assert_invalid(schema_for(check_id), new)
    old = minimal(check_id, "1.0.0")
    assert_valid(schema_for(check_id), old)
    old["not_checked"] = []
    assert_invalid(schema_for(check_id), old)


# The denominator.


def _request(manifest: dict[str, str | None], lock: dict[str, str | None]) -> dict:
    def block(values: dict[str, str | None]) -> dict:
        return {k: {"sha256": v * 64} for k, v in values.items() if v is not None}

    return {"manifest": {"pins": block(manifest)}, "lock": {"pins": block(lock)}}


def test_the_worked_example_one_of_three_checkable_subjects_mismatching() -> None:
    """Three subjects can be checked. One of them differs. Two are not checked. The percentage is
    the two matching of the three checked, 66.67, and not two of five (40)."""
    payload = _request(
        {"runner": "a", "world": "b", "configuration": "c", "specs": None, "verifier": None},
        {"runner": "a", "world": "d", "configuration": "c", "specs": "e", "verifier": None},
    )
    expected = pins(payload)
    assert expected["applicable"] is True
    assert expected["percentage"] == pytest.approx(100 * 2 / 3)
    assert expected["percentage"] != 40
    assert [f["subject"] for f in expected["findings"]] == ["world"]
    assert expected["not_checked"] == [
        {"subject": "specs", "reason": "not-recorded"},
        {"subject": "verifier", "reason": "not-declared"},
    ]


def test_two_mismatches_among_three_checked_read_a_third_not_twenty() -> None:
    payload = _request(
        {"runner": "a", "world": "b", "configuration": "c"},
        {"runner": "a", "world": "d", "configuration": "e", "specs": "f", "verifier": "g"},
    )
    assert pins(payload)["percentage"] == pytest.approx(100 / 3)


def test_all_five_checked_keeps_the_old_share() -> None:
    same = {s: "a" for s in PIN_SUBJECTS}
    other = {**same, "specs": "b", "world": "c"}
    expected = pins(_request(other, same))
    assert expected["percentage"] == 60
    assert expected["not_checked"] == []


def test_nothing_checked_is_not_applicable_and_has_no_percentage() -> None:
    expected = pins(_request({}, {s: "a" for s in PIN_SUBJECTS}))
    assert expected["applicable"] is False
    assert "percentage" not in expected and expected["findings"] == []
    assert [item["subject"] for item in expected["not_checked"]] == list(PIN_SUBJECTS)


def test_a_subject_is_checked_or_not_checked_never_both_and_never_neither() -> None:
    rng = random.Random(34)
    for _ in range(400):
        pick = lambda: {s: rng.choice(["a", "b", None]) for s in PIN_SUBJECTS}
        expected = pins(_request(pick(), pick()))
        skipped = {item["subject"] for item in expected["not_checked"]}
        found = {item["subject"] for item in expected["findings"]}
        assert not skipped & found
        checked = len(PIN_SUBJECTS) - len(skipped)
        assert (checked > 0) is expected["applicable"]
        if checked:
            good = checked - len(found)
            assert expected["percentage"] == pytest.approx(100 * good / checked)
            assert (expected["percentage"] == 100) is (not found)


def test_the_request_may_leave_a_pin_out() -> None:
    document = load_json(EXAMPLES / "pins-partial" / "request.json")
    del document["integrity"]["manifest"]["pins"]["specs"]
    del document["integrity"]["lock"]["pins"]["verifier"]
    assert_valid(request_schema(), document)
    document["integrity"]["manifest"]["pins"] = {}
    assert_valid(request_schema(), document)


def test_the_other_checks_already_leave_unjudged_subjects_out_of_the_denominator() -> None:
    """plan-conformance, termination and recording count only what they judged (their 1.0.0
    rules), so the denominator rule itself needed no change for them. plan-conformance and
    recording are bumped to 1.1.0 for ``not_checked``, not for the denominator."""
    from integrity_rules import plan_conformance, recording, termination

    vocab = {
        "time-limit",
        "mission-done",
        "left-world",
        "simulation-broken",
        "adapter-or-scenario-done",
    }
    plan = load_json(EXAMPLES / "plan-conformance" / "conformant" / "request.json")["integrity"]
    plan_no_lock = copy.deepcopy(plan)
    del plan_no_lock["evidence"]["plan-conformance"]["lock"]
    with_lock = plan_conformance(plan)
    without = plan_conformance(plan_no_lock)
    # 4 index slots + 3 counts + 1 speed with a lock; 4 + 2 without: nothing skipped is counted.
    assert with_lock["percentage"] == without["percentage"] == 100
    assert [i["subject"] for i in without["not_checked"]] == [
        "lock-trial-count",
        "lock-command-speed",
    ]
    findings = load_json(EXAMPLES / "termination" / "findings" / "request.json")["integrity"]
    # Five trials ended on their own; the timeout and the crash are referrals, not counted.
    assert termination(findings, vocab, "1.0.0")["percentage"] == 20
    rec = load_json(EXAMPLES / "recording" / "findings" / "request.json")["integrity"]
    # Seven present recordings are judged; the missing one is not in the denominator.
    assert recording(rec, "1.0.0")["percentage"] == pytest.approx(100 / 7)


# Versions: the old ones stay valid.


def test_the_registry_names_the_current_version_and_the_ones_that_stay_valid() -> None:
    schema = load_json(CHECKS / "registry.schema.json")
    assert "previous_versions" in schema["properties"]["checks"]["items"]["properties"]
    for entry in check_registry():
        version, previous = LATEST[entry["id"]]
        assert entry["version"] == version
        assert entry.get("previous_versions") == previous


@pytest.mark.parametrize(
    "check_id", ["pins", "completeness", "termination", "plan-conformance", "recording"]
)
def test_version_1_0_0_results_are_still_valid(check_id: str) -> None:
    old = minimal(check_id, "1.0.0")
    assert_valid(schema_for(check_id), old)
    assert_valid(schema_for(check_id), minimal(check_id, LATEST[check_id][0]))
    assert_invalid(schema_for(check_id), {**old, "version": "1.2.0"})


def test_pins_1_1_0_always_says_what_it_did_not_check_and_1_0_0_cannot() -> None:
    new = minimal("pins", "1.1.0")
    assert_valid(schema_for("pins"), new)
    del new["not_checked"]
    assert_invalid(schema_for("pins"), new)
    old = minimal("pins", "1.0.0")
    old["not_checked"] = []
    assert_invalid(schema_for("pins"), old)


def test_every_example_check_is_at_a_registered_version() -> None:
    accepted = {
        entry["id"]: {entry["version"], *entry.get("previous_versions", [])}
        for entry in check_registry()
    }
    seen: set[tuple[str, str]] = set()
    for example in example_dirs():
        result = load_json(example / "result.json")
        if result["evaluator"]["kind"] != "integrity":
            continue
        for check in result["integrity"]["checks"]:
            assert check["version"] in accepted[check["id"]], (example, check["id"])
            seen.add((check["id"], check["version"]))
    # Both versions of each bumped check are shown by an example.
    for check_id in ("pins", "completeness", "termination", "plan-conformance", "recording"):
        assert (check_id, "1.0.0") in seen and (check_id, "1.1.0") in seen
    assert ("recording", "1.2.0") in seen


def test_an_example_that_reports_not_checked_never_also_finds_the_same_subject() -> None:
    reported = 0
    for example in example_dirs():
        result = load_json(example / "result.json")
        if result["evaluator"]["kind"] != "integrity":
            continue
        for check in result["integrity"]["checks"]:
            skipped = {
                item.get("subject") or item.get("trial_id") for item in check.get("not_checked", [])
            }
            if not skipped:
                continue
            reported += 1
            found = {item.get("subject") or item.get("trial_id") for item in check["findings"]}
            assert not skipped & found
    assert reported >= 4


# Review of PR 37 (Vera) and Rivet's decisions on it.


def test_pins_applicability_and_the_five_subjects_agree() -> None:
    """A pins check lists all five subjects exactly when nothing was checked (F4)."""
    applicable = minimal("pins", "1.1.0")
    applicable.update(applicable=True, percentage=100, not_checked=[])
    assert_valid(schema_for("pins"), applicable)
    applicable["not_checked"] = [{"subject": s, "reason": "not-declared"} for s in PIN_SUBJECTS]
    assert_invalid(schema_for("pins"), applicable)  # applicable, yet nothing was checked
    applicable["not_checked"] = [{"subject": s, "reason": "not-declared"} for s in PIN_SUBJECTS[:4]]
    assert_valid(schema_for("pins"), applicable)
    not_applicable = minimal("pins", "1.1.0")
    assert_valid(schema_for("pins"), not_applicable)
    for short in (
        [],
        [{"subject": "specs", "reason": "not-declared"}],
        not_applicable["not_checked"][:4],
    ):
        broken = {**not_applicable, "not_checked": short}
        assert_invalid(schema_for("pins"), broken)  # not applicable, yet a subject was checked


def test_the_docs_say_which_pins_rules_the_schema_cannot_enforce() -> None:
    doc = (ROOT / "docs" / "run-integrity.md").read_text()
    assert "rule-level" in doc
    assert "neither" in doc and "not-declared" in doc


def test_a_pin_neither_side_carries_is_not_declared() -> None:
    payload = _request({"runner": "a"}, {"runner": "a"})
    reasons = {item["subject"]: item["reason"] for item in pins(payload)["not_checked"]}
    assert reasons == {s: "not-declared" for s in PIN_SUBJECTS if s != "runner"}


def test_not_present_means_no_readable_recording() -> None:
    result = load_json(SCHEMA_ROOT / "integrity" / "result.schema.json")
    definition = result["$defs"]["not_checked"]["properties"]["reason"]["description"]
    assert "missing, truncated or empty" in definition
    assert "does not exist" not in definition


def test_the_termination_evidence_description_says_simulation_broken_is_ignored() -> None:
    schema = schema_for("termination")
    text = schema["$defs"]["evidence"]["properties"]["allowed_stop_reasons"]["description"]
    assert "simulation-broken" in text and "never" in text


def test_the_reference_rules_default_to_the_current_version() -> None:
    import inspect

    import integrity_rules

    for function in (
        integrity_rules.termination,
        integrity_rules.plan_conformance,
        integrity_rules.completeness_applicable,
    ):
        assert inspect.signature(function).parameters["version"].default == "1.1.0", function
    assert inspect.signature(integrity_rules.recording).parameters["version"].default == "1.2.0"


# Published examples stay as they were at v1.1.0, so one version label is one reading. The digests
# are those of the example files in the v1.1.0 tag. Only new examples may be added.
def test_every_example_published_at_v1_1_0_is_unchanged() -> None:
    import hashlib

    published = load_json(ROOT / "tests" / "integrity" / "published_examples_v1_1_0.json")
    assert len(published) >= 36
    for relative, digest in published.items():
        data = (ROOT / relative).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, relative


def test_the_docs_table_names_every_current_version() -> None:
    doc = (ROOT / "docs" / "run-integrity.md").read_text()
    for check_id, (version, _) in LATEST.items():
        assert f"| `{check_id}` | {version} |" in doc, check_id
