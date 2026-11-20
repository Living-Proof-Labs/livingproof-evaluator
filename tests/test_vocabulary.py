# SPDX-License-Identifier: Apache-2.0
"""The hallway observable vocabulary (issue 2).

Only the terms the hallway scenario and its fixtures use: base, base_height, body_contact.
Each has a meaning, a frame, units and a rule for when a per-robot nominal applies. There is
no broader ontology, and no mapping to MCAP channels or to a robot model.
"""

from __future__ import annotations

from support import EXAMPLES, ROOT, SCHEMA_ROOT, assert_invalid, assert_valid, load_json

SCHEMA = SCHEMA_ROOT / "vocabulary.schema.json"
FIXTURE = EXAMPLES / "vocabulary" / "hallway" / "vocabulary.json"
DOC = ROOT / "docs" / "observable-vocabulary.md"
FIELDS = ("meaning", "frame", "units", "nominal")
# An observable some fixture names on purpose without binding it: the not-evaluated example.
UNBOUND = {"tail"}


def vocabulary() -> dict:
    return load_json(FIXTURE)


def terms() -> dict[str, dict]:
    return {term["id"]: term for term in vocabulary()["terms"]}


def used_observables() -> dict[str, set[str]]:
    """Observable -> the example files that bind or grade it (hallway scenario fixtures)."""
    used: dict[str, set[str]] = {}
    for request in sorted(EXAMPLES.rglob("request.json")):
        document = load_json(request)
        scenario = document.get("scenario")
        if not isinstance(scenario, dict):
            continue
        where = str(request.relative_to(ROOT))
        for name in scenario.get("binding", {}).get("bound_observables", []):
            used.setdefault(name, set()).add(where)
        for step in scenario.get("scenario", {}).get("steps", []):
            if step.get("bound") is True:
                used.setdefault(step["observable"], set()).add(where)
    return used


def test_the_fixture_validates_against_the_schema() -> None:
    assert_valid(load_json(SCHEMA), vocabulary())


def test_the_schema_rejects_a_term_missing_a_field() -> None:
    schema = load_json(SCHEMA)
    for field in FIELDS:
        broken = vocabulary()
        del broken["terms"][0][field]
        assert_invalid(schema, broken)
    empty = vocabulary()
    empty["terms"][0]["meaning"] = ""
    assert_invalid(schema, empty)
    odd = vocabulary()
    odd["terms"][0]["nominal"]["applies"] = "sometimes"
    assert_invalid(schema, odd)


def test_every_term_has_all_four_fields() -> None:
    for name, term in terms().items():
        for field in FIELDS:
            assert term.get(field), (name, field)
        assert term["nominal"]["applies"] in {"never", "per-robot-configuration"}, name
        assert term["nominal"]["rule"].strip(), name
        assert term["sources"], f"{name} names where the hallway evaluator uses it"


def test_every_observable_the_fixtures_use_is_defined() -> None:
    defined = set(terms())
    used = used_observables()
    assert used, "the scenario fixtures bind observables"
    assert set(used) <= defined, sorted(set(used) - defined)


def test_no_term_is_defined_that_the_fixtures_do_not_use() -> None:
    """No broad ontology: the vocabulary is exactly what the hallway fixtures use."""
    assert set(terms()) == set(used_observables())
    assert not (UNBOUND & set(terms()))


def test_the_terms_are_unique_and_named_as_the_fixtures_name_them() -> None:
    ids = [term["id"] for term in vocabulary()["terms"]]
    assert ids == sorted(set(ids), key=ids.index)
    assert ids == ["base", "base_height", "body_contact"]


def test_base_height_has_a_per_robot_nominal_and_the_others_have_none() -> None:
    by_id = terms()
    assert by_id["base_height"]["nominal"]["applies"] == "per-robot-configuration"
    assert by_id["base"]["nominal"]["applies"] == "never"
    assert by_id["body_contact"]["nominal"]["applies"] == "never"


def test_the_fall_threshold_is_relative_to_nominal_and_today_s_absolute_value_is_recorded() -> None:
    """Rivet's decision 3: specs stay robot-neutral; the binding supplies the nominal."""
    nominal = terms()["base_height"]["nominal"]
    assert "60% of nominal" in nominal["rule"]
    assert "robot binding supplies the nominal" in nominal["rule"]
    assert "tuning value" in nominal["rule"]
    today = nominal["current_implementation"]
    assert "fall_base_height" in today and "min_base_height" in today
    assert "0.5 m" in today and "0.78 m" in today
    assert "reads bindings" in today


def test_body_contact_is_contact_with_a_named_surface_and_wall_contacts_maps_to_it() -> None:
    """Rivet's decision 2: general name and meaning; the metric is the hallway-wall count."""
    term = terms()["body_contact"]
    assert "named environment surface" in term["meaning"]
    assert "hallway wall" in term["meaning"]
    assert [metric["id"] for metric in term["metrics"]] == ["wall_contacts"]
    assert "count of body_contact events with hallway walls" in term["metrics"][0]["maps"]
    others = {name: t for name, t in terms().items() if name != "body_contact"}
    assert all("metrics" not in t for t in others.values())


def test_feet_stay_out_until_something_observes_them() -> None:
    """Rivet's decision 1: a term goes in when a fixture or check first observes it."""
    assert not any("feet" in name or "foot" in name for name in terms())
    assert "feet" not in used_observables()
    assert "a term goes in when a fixture or check first observes it" in DOC.read_text()


def test_the_doc_states_every_definition_as_the_fixture_does() -> None:
    text = DOC.read_text()
    for term in vocabulary()["terms"]:
        assert f"`{term['id']}`" in text
        for field in ("meaning", "frame", "units"):
            assert term[field] in text, (term["id"], field)
        assert term["nominal"]["rule"] in text, term["id"]
        if "current_implementation" in term["nominal"]:
            assert term["nominal"]["current_implementation"] in text, term["id"]
        for metric in term.get("metrics", []):
            assert f"`{metric['id']}`" in text and metric["maps"] in text, term["id"]
    for heading in ("Meaning", "Frame", "Units", "Nominal"):
        assert heading in text
    assert "no mapping" in text.lower() or "does not map" in text.lower()


def test_the_doc_has_no_open_points_left() -> None:
    assert "Open points" not in DOC.read_text()


def test_the_doc_is_in_the_manual_and_the_readme_no_longer_calls_the_terms_design() -> None:
    assert "docs/observable-vocabulary.md" in (ROOT / "tools/manual/mkdocs.yml").read_text()
    readme = (ROOT / "README.md").read_text()
    assert "docs/observable-vocabulary.md" in readme
    assert (
        "The observable vocabulary and the observation-binding format are still design"
        not in readme
    )
