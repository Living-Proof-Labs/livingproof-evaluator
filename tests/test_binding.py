# SPDX-License-Identifier: Apache-2.0
"""The observation binding format, livingproof-observation-binding/1.0.0 (issue 3).

Built on the hallway vocabulary (issue 2): a binding speaks only of its terms. Scope is what the
existing fixtures and checks need: one supported recording (the MCAP that livingproof-sim-mujoco
writes, with `/base_pose`), a robot binding, a producer binding and the merged per-trial binding.
Ambiguous or missing entries are rejected, not guessed.
"""

from __future__ import annotations

import copy
import json

import pytest

from binding_rules import PRODUCER_MISSING, merge, merged_problems, robot_needs
from support import EXAMPLES, ROOT, SCHEMA_ROOT, assert_invalid, assert_valid, load_json

SCHEMA = SCHEMA_ROOT / "binding.schema.json"
DIR = EXAMPLES / "binding"
VOCABULARY = load_json(EXAMPLES / "vocabulary" / "hallway" / "vocabulary.json")
TERMS = {term["id"]: term for term in VOCABULARY["terms"]}
ROBOT = DIR / "robot" / "unitree-g1-stock.json"
PRODUCER = DIR / "producer" / "livingproof-sim-mujoco.json"
MERGED = DIR / "merged" / "unitree-g1-stock-livingproof-sim-mujoco.json"
KINDS = {"robot": ROBOT, "producer": PRODUCER, "merged": MERGED}


def schema() -> dict:
    return load_json(SCHEMA)


def doc(path) -> dict:
    return copy.deepcopy(load_json(path))


@pytest.mark.parametrize("kind", KINDS)
def test_each_worked_example_validates_against_the_schema(kind: str) -> None:
    document = load_json(KINDS[kind])
    assert document["format"] == "livingproof-observation-binding/1.0.0"
    assert document["kind"] == kind
    assert_valid(schema(), document)


def test_the_schema_names_the_format_and_covers_all_three_kinds() -> None:
    document = schema()
    assert document["$id"].endswith("/schema/binding.schema.json")
    assert "livingproof-observation-binding/1.0.0" in json.dumps(document)
    for kind in KINDS:
        assert f'"{kind}"' in json.dumps(document)


@pytest.mark.parametrize("kind", KINDS)
def test_a_binding_speaks_only_of_vocabulary_terms(kind: str) -> None:
    document = load_json(KINDS[kind])
    assert set(document["observables"]) <= set(TERMS)
    assert document["observables"], kind


def test_the_robot_binding_owns_the_base_body_and_the_nominal() -> None:
    robot = load_json(ROBOT)
    assert robot["observables"]["base"] == {"body": "pelvis"}
    nominal = robot["observables"]["base_height"]["nominal"]
    assert (nominal["value"], nominal["unit"]) == (0.78, "meters")
    assert nominal["source"] == "measured"
    assert robot["configuration"] == "stock"
    # Only a term whose nominal applies per robot configuration carries a nominal.
    for name, entry in robot["observables"].items():
        assert ("nominal" in entry) == (TERMS[name]["nominal"]["applies"] != "never"), name
    assert "feet" not in json.dumps(robot).lower()


def test_the_producer_binding_names_the_channel_and_fields_the_recording_has() -> None:
    producer = load_json(PRODUCER)
    pose = producer["observables"]["base"]
    assert (pose["topic"], pose["encoding"], pose["schema"]) == (
        "/base_pose",
        "json",
        "foxglove.PoseInFrame",
    )
    assert pose["fields"] == {"x": "pose.position.x", "y": "pose.position.y"}
    assert pose["frame"] == "world"
    height = producer["observables"]["base_height"]
    assert height["topic"] == "/base_pose" and height["fields"] == {"z": "pose.position.z"}
    # The contacts channel livingproof-sim-mujoco writes (#28): one message per contact event.
    contact = producer["observables"]["body_contact"]
    assert (contact["topic"], contact["encoding"], contact["schema"]) == (
        "/wall_contacts",
        "json",
        "livingproof.WallContact",
    )
    assert contact["fields"] == {
        "wall": "wall",
        "start": "start",
        "end": "end",
        "depth": "depth",
    }
    assert contact["frame"] == "world"
    # Producer-owned entries never carry robot-owned ones.
    assert all({"body", "nominal"}.isdisjoint(entry) for entry in producer["observables"].values())


def test_the_merged_binding_is_the_merge_of_the_robot_and_producer_bindings() -> None:
    merged = load_json(MERGED)
    expected = merge(
        load_json(ROBOT),
        load_json(PRODUCER),
        VOCABULARY,
        merged["trial_id"],
        merged["recording"],
    )
    assert merged == expected
    assert merged["bound_observables"] == ["base", "base_height", "body_contact"]
    assert merged["unbound"] == []
    assert merged_problems(merged, VOCABULARY) == []


def test_a_bound_observable_has_its_channel_fields_and_the_robot_entries_it_needs() -> None:
    merged = load_json(MERGED)
    for name, entry in merged["observables"].items():
        assert entry["topic"].startswith("/") and entry["fields"], name
        for need in robot_needs(TERMS[name], name):
            assert need in entry, (name, need)


def test_body_contact_is_bound_to_the_wall_contacts_channel_in_the_merged_example() -> None:
    """The sim writes the contacts channel (livingproof-sim-mujoco#28), so the term is bound."""
    merged = load_json(MERGED)
    entry = merged["observables"]["body_contact"]
    assert entry["topic"] == "/wall_contacts"
    assert entry == load_json(PRODUCER)["observables"]["body_contact"]
    assert "body_contact" in merged["bound_observables"]
    text = " ".join((ROOT / "docs" / "observation-binding.md").read_text().split())
    assert "/wall_contacts" in text and "until then `body_contact` is unbound" not in text


def test_the_binding_is_for_mcap_recordings_only() -> None:
    merged = load_json(MERGED)
    assert merged["recording"]["uri"].endswith(".mcap")
    text = (ROOT / "docs" / "observation-binding.md").read_text()
    assert "MCAP recordings only" in text
    assert "livingproof-sim-mujoco#28" in text


def test_placeholders_are_plainly_marked_and_schema_valid() -> None:
    merged = load_json(MERGED)
    assert merged["recording"]["uri"].startswith("https://example.invalid/")
    assert merged["recording"]["sha256"] == "0" * 64
    for path in (ROBOT, MERGED):
        nominal = load_json(path)["observables"]["base_height"]["nominal"]
        assert nominal["source"] == "measured", path
        assert nominal["ref"].startswith("placeholder:"), path
    text = (ROOT / "docs" / "observation-binding.md").read_text()
    assert "example.invalid" in text and "placeholder" in text


def test_pinning_is_left_to_verification_100() -> None:
    text = (ROOT / "docs" / "observation-binding.md").read_text()
    assert "livingproof-verification#100" in text
    assert "https://github.com/Living-Proof-Labs/livingproof-verification/issues/100" in text


def test_the_merged_bound_list_matches_the_scenario_request_shape() -> None:
    """The scenario request already carries `binding.bound_observables`; this is that list."""
    request = load_json(EXAMPLES / "scenario" / "graded" / "request.json")
    shape = request["scenario"]["binding"]
    assert set(shape) == {"bound_observables"}
    assert isinstance(load_json(MERGED)["bound_observables"], list)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(format="livingproof-observation-binding/2.0.0"),
        lambda d: d.update(kind="robot"),
        lambda d: d.pop("recording"),
        lambda d: d["recording"].update(sha256="nothex"),
        lambda d: d.update(extra=1),
        lambda d: d["observables"]["base"].pop("topic"),
        lambda d: d["observables"]["base"].update(fields={}),
        lambda d: d["observables"]["base"].update(topic=["/a", "/b"]),
        lambda d: d["observables"].update(unknown_term=d["observables"]["base"]),
    ],
)
def test_the_schema_rejects_a_malformed_merged_binding(mutate) -> None:
    broken = doc(MERGED)
    mutate(broken)
    assert_invalid(schema(), broken)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["observables"]["base"].pop("body"),
        lambda d: d["observables"]["base_height"].pop("nominal"),
        lambda d: d["observables"]["base"].update(nominal={"value": 1, "unit": "m"}),
        lambda d: d["bound_observables"].reverse(),
        lambda d: d["unbound"].append({"id": "base", "reason": PRODUCER_MISSING}),
        lambda d: d["unbound"].append({"id": "body_contact", "reason": PRODUCER_MISSING}),
        lambda d: d["bound_observables"].remove("body_contact"),
    ],
)
def test_the_merge_rules_reject_an_ambiguous_or_missing_entry(mutate) -> None:
    broken = doc(MERGED)
    mutate(broken)
    assert merged_problems(broken, VOCABULARY), "an unsound merged binding must be rejected"


def test_a_missing_robot_entry_leaves_the_observable_unbound_not_guessed() -> None:
    robot = doc(ROBOT)
    del robot["observables"]["base_height"]["nominal"]
    robot["observables"]["base_height"] = {}
    merged = load_json(MERGED)
    result = merge(robot, load_json(PRODUCER), VOCABULARY, merged["trial_id"], merged["recording"])
    assert "base_height" not in result["observables"]
    assert {"id": "base_height", "reason": "robot-entry-missing"} in result["unbound"]


def test_the_guide_is_in_the_manual_and_the_readme_no_longer_calls_bindings_design() -> None:
    text = (ROOT / "docs" / "observation-binding.md").read_text()
    for needle in (
        "livingproof-observation-binding/1.0.0",
        "robot binding",
        "producer binding",
        "merged binding",
        "/base_pose",
        "unbound",
        "nominal",
    ):
        assert needle in text, needle
    assert "docs/observation-binding.md" in (ROOT / "tools/manual/mkdocs.yml").read_text()
    readme = (ROOT / "README.md").read_text()
    assert "docs/observation-binding.md" in readme
    assert "The observation-binding format is still design" not in readme


def test_the_schema_observable_list_is_exactly_the_vocabulary_terms() -> None:
    enum = schema()["$defs"]["observable"]["enum"]
    assert enum == [term["id"] for term in VOCABULARY["terms"]]


def test_no_example_step_states_the_fall_threshold_relative_to_nominal() -> None:
    """The spec grades the absolute fall_height; nominal is reference only (PR 52)."""
    checked = 0
    paths = [*(EXAMPLES / "scenario").rglob("*.json"), *(EXAMPLES / "descriptor").rglob("*.json")]
    for path in sorted(paths):
        text = path.read_text()
        assert "60%" not in text and "of nominal" not in text, str(path.relative_to(ROOT))
        for step in load_json(path).get("scenario", {}).get("scenario", {}).get("steps", []):
            if step.get("observable") == "base_height":
                assert step["text"] == "the base height stays above the fall height", path
                checked += 1
    assert checked >= 3


def _each_kind():
    return {"robot": doc(ROBOT), "producer": doc(PRODUCER), "merged": doc(MERGED)}


@pytest.mark.parametrize("kind", ["producer", "merged"])
def test_a_channel_entry_takes_no_extra_property(kind: str) -> None:
    broken = _each_kind()[kind]
    broken["observables"]["base"]["extra"] = 1
    assert_invalid(schema(), broken)


@pytest.mark.parametrize("kind", ["robot", "merged"])
@pytest.mark.parametrize(
    "mutate",
    [
        lambda n: n.pop("unit"),
        lambda n: n.pop("source"),
        lambda n: n.update(value=-0.1),
        lambda n: n.update(unit="cm"),
        lambda n: n.update(extra=1),
    ],
)
def test_a_nominal_needs_its_unit_and_source_and_a_positive_value_in_meters(kind, mutate) -> None:
    broken = _each_kind()[kind]
    mutate(broken["observables"]["base_height"]["nominal"])
    assert_invalid(schema(), broken)


@pytest.mark.parametrize("kind", ["producer", "merged"])
@pytest.mark.parametrize("field", ["topic", "frame"])
def test_a_channel_entry_needs_its_topic_and_frame(kind: str, field: str) -> None:
    broken = _each_kind()[kind]
    del broken["observables"]["base_height"][field]
    assert_invalid(schema(), broken)


@pytest.mark.parametrize("kind", ["producer", "merged"])
def test_the_frame_and_fields_are_the_vocabularys_for_every_bound_term(kind: str) -> None:
    for name, fields in (("base", {"x", "y"}), ("base_height", {"z"})):
        good = _each_kind()[kind]
        assert good["observables"][name]["frame"] == "world"
        assert set(good["observables"][name]["fields"]) == fields
        extra = _each_kind()[kind]
        extra["observables"][name]["fields"]["q"] = "pose.position.q"
        assert_invalid(schema(), extra)
