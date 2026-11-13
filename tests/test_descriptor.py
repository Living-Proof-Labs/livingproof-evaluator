# SPDX-License-Identifier: Apache-2.0
"""Optional result descriptor, format 1.1, including the SVG subset."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from defusedxml.common import DefusedXmlException
from validate_contract import (
    consumer_accepts,
    fromstring,
    svg_subset_errors,
    validate_document,
)

from support import EXAMPLES, ROOT, SCHEMA_ROOT, example_dirs, load_json

DESCRIPTOR_EXAMPLES = EXAMPLES / "descriptor"
PLACEHOLDER_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    '<rect width="16" height="16" fill="none"/></svg>'
)
SOURCE_ART = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">'
    "<title>Living Proof Labs Scenario evaluator</title>"
    '<g stroke="#0E8785"><path d="M6.5 7L10.5 11L17.5 4"/></g>'
    "</svg>"
)


def _svg(body: str = "", *, view_box: bool = True) -> str:
    box = ' viewBox="0 0 24 24"' if view_box else ""
    return f"<svg{box}>{body}</svg>"


def _copy(document: dict) -> dict:
    return json.loads(json.dumps(document))


def _scenario_with_icon() -> dict:
    return load_json(DESCRIPTOR_EXAMPLES / "scenario-with-icon" / "result.json")


def _with_both_icons(document: dict, icon: str) -> dict:
    copied = _copy(document)
    copied["descriptor"]["icon"] = icon
    copied["evaluator"]["icon"] = icon
    return copied


def test_descriptor_examples_are_strictly_valid() -> None:
    specs = {
        "scenario-with-icon": ("scenario", True),
        "scenario-without-icon": ("scenario", False),
        "integrity-with-icon": ("integrity", True),
        "integrity-without-icon": ("integrity", False),
    }
    seen = sorted(path.name for path in DESCRIPTOR_EXAMPLES.iterdir() if path.is_dir())
    assert seen == sorted(specs)
    for name, (kind, has_icon) in specs.items():
        result = load_json(DESCRIPTOR_EXAMPLES / name / "result.json")
        request = load_json(DESCRIPTOR_EXAMPLES / name / "request.json")
        assert result["format"] == "livingproof-evaluator-result/1.1.0"
        assert request["format"] == "livingproof-evaluator-request/1.0.0"
        assert "descriptor" not in request
        assert validate_document(result) == []
        assert validate_document(request) == []
        descriptor = result["descriptor"]
        assert result["evaluator"]["kind"] == kind
        assert descriptor["kind"] != kind
        assert descriptor["title"] == result["evaluator"]["display_name"]
        assert descriptor["version"] == result["evaluator"]["version"]
        assert not descriptor["title"].lower().endswith("evaluator")
        assert "short_title" not in descriptor
        if has_icon:
            assert descriptor["icon"] == result["evaluator"]["icon"]
            assert svg_subset_errors(descriptor["icon"]) == []
            assert "<title" not in descriptor["icon"]
            assert "#0E8785" not in descriptor["icon"]
            assert descriptor["icon_accessible_name"] == descriptor["title"]
        else:
            assert "icon" not in descriptor
            assert result["evaluator"]["icon"] == PLACEHOLDER_ICON
            assert svg_subset_errors(result["evaluator"]["icon"]) == []


def test_descriptor_fixtures_are_labelled_example_data() -> None:
    text = (ROOT / "docs" / "evaluator-descriptor.md").read_text()
    assert "example data" in text
    assert "Aaron's decision" in text
    assert "used exactly" in text
    assert 'never appends the word "evaluator"' in text
    assert "`Health` is not a valid `short_title`" in text
    assert "Robot health" in text
    for name in (
        "scenario-with-icon",
        "scenario-without-icon",
        "integrity-with-icon",
        "integrity-without-icon",
    ):
        assert name in text


def test_existing_1_0_results_stay_valid_without_a_descriptor() -> None:
    for example in example_dirs():
        if "descriptor" in example.parts:
            continue
        result = load_json(example / "result.json")
        assert result["format"] == "livingproof-evaluator-result/1.0.0"
        assert "descriptor" not in result
        assert validate_document(result) == []
        assert consumer_accepts(result) is True


def test_format_1_1_without_a_descriptor_stays_valid() -> None:
    document = load_json(EXAMPLES / "integrity" / "clean" / "result.json")
    document["format"] = "livingproof-evaluator-result/1.1.0"
    assert "descriptor" not in document
    assert validate_document(document) == []
    assert consumer_accepts(document) is True


def test_a_1_0_format_rejects_a_descriptor_and_a_1_0_consumer_drops_it() -> None:
    document = _scenario_with_icon()
    document["format"] = "livingproof-evaluator-result/1.0.0"
    assert validate_document(document)
    assert consumer_accepts(document) is True


def test_a_request_rejects_a_descriptor() -> None:
    request = load_json(DESCRIPTOR_EXAMPLES / "scenario-with-icon" / "request.json")
    request["descriptor"] = {"tier": "verdict"}
    assert validate_document(request)


def test_a_1_0_consumer_drops_a_descriptor_including_a_malicious_one() -> None:
    document = _scenario_with_icon()
    assert consumer_accepts(document) is True
    assert validate_document(document) == []
    malicious = _copy(document)
    malicious["descriptor"]["findings"][0]["text"] = "<script>alert(1)</script>"
    malicious["descriptor"]["icon"] = _svg("<script>alert(1)</script>")
    malicious["evaluator"]["icon"] = malicious["descriptor"]["icon"]
    malicious["future_field"] = {"ignored": True}
    assert consumer_accepts(malicious) is True
    errors = validate_document(malicious)
    assert errors
    assert any("findings" in error and "text" in error for error in errors)
    assert any("script" in error for error in errors)


def test_grade_is_independent_of_integrity_percentage() -> None:
    document = load_json(DESCRIPTOR_EXAMPLES / "integrity-with-icon" / "result.json")
    assert document["integrity"]["run"]["percentage"] == 60
    assert "grade" not in document["descriptor"]
    document["descriptor"]["grade"] = 40
    assert validate_document(document) == []
    assert document["integrity"]["run"]["percentage"] == 60


def test_committed_examples_stay_valid() -> None:
    for example in example_dirs():
        assert validate_document(load_json(example / "request.json")) == []
        assert validate_document(load_json(example / "result.json")) == []


def test_omitted_title_applies_plain_text_to_display_name_and_publisher() -> None:
    markup = "<b>Scenario</b>"
    omitted = _scenario_with_icon()
    omitted["descriptor"].pop("title")
    assert validate_document(omitted) == []

    named = _copy(omitted)
    named["evaluator"]["display_name"] = markup
    assert any("display_name" in error for error in validate_document(named))
    named["descriptor"]["title"] = "Scenario"
    named["evaluator"]["display_name"] = "Scenario"
    assert validate_document(named) == []

    published = _copy(omitted)
    published["evaluator"]["publisher"] = markup
    errors = validate_document(published)
    assert any("publisher" in error for error in errors)
    assert all("display_name" not in error for error in errors)

    present = _scenario_with_icon()
    assert present["descriptor"]["title"] == present["evaluator"]["display_name"]
    assert validate_document(present) == []
    present["evaluator"]["publisher"] = markup
    assert validate_document(present) == []

    legacy = load_json(EXAMPLES / "scenario" / "graded" / "result.json")
    assert legacy["format"] == "livingproof-evaluator-result/1.0.0"
    legacy["evaluator"]["display_name"] = markup
    legacy["evaluator"]["publisher"] = markup
    assert validate_document(legacy) == []


def test_title_matches_the_display_name_and_is_not_suffixed_by_the_consumer() -> None:
    document = _scenario_with_icon()
    document["descriptor"]["title"] = "Scenario evaluator"
    errors = validate_document(document)
    assert any("display_name" in error for error in errors)
    chosen = _copy(document)
    chosen["evaluator"]["display_name"] = "Scenario evaluator"
    chosen["descriptor"]["title"] = "Scenario evaluator"
    assert validate_document(chosen) == []


def test_short_title_is_a_shortening_of_the_same_name() -> None:
    document = _scenario_with_icon()
    document["evaluator"]["display_name"] = "Robot health"
    document["descriptor"]["title"] = "Robot health"
    document["descriptor"]["short_title"] = "Health"
    assert any("short_title" in error for error in validate_document(document))
    document["descriptor"]["short_title"] = "Robot"
    assert any("short_title" in error for error in validate_document(document))
    document["descriptor"]["short_title"] = "Rob health"
    assert validate_document(document) == []
    document["descriptor"]["short_title"] = "Robot health"
    assert validate_document(document) == []


def test_version_matches_the_envelope_version() -> None:
    document = _scenario_with_icon()
    document["descriptor"]["version"] = "9.9.9"
    errors = validate_document(document)
    assert any("version" in error for error in errors)


def test_omitted_descriptor_icon_rechecks_evaluator_icon_on_later_results() -> None:
    bad = _svg("<script>alert(1)</script>")
    omitted = _scenario_with_icon()
    omitted["descriptor"].pop("icon")
    omitted["evaluator"]["icon"] = bad
    errors = validate_document(omitted)
    assert any("evaluator/icon" in error and "script" in error for error in errors)

    present = _scenario_with_icon()
    assert "icon" in present["descriptor"]
    assert present["descriptor"]["icon"] == present["evaluator"]["icon"]
    assert validate_document(present) == []

    legacy = load_json(EXAMPLES / "scenario" / "graded" / "result.json")
    assert legacy["format"] == "livingproof-evaluator-result/1.0.0"
    legacy["evaluator"]["icon"] = bad
    assert validate_document(legacy) == []


def test_icon_matches_the_envelope_icon() -> None:
    document = _scenario_with_icon()
    document["descriptor"].pop("icon")
    assert validate_document(document) == []
    other = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4" fill="currentColor"/></svg>'
    document["descriptor"]["icon"] = other
    errors = validate_document(document)
    assert any("must equal evaluator.icon" in error for error in errors)
    assert svg_subset_errors(other) == []


def test_reported_by_and_a_per_finding_tier_override() -> None:
    document = _scenario_with_icon()
    assert document["descriptor"]["tier"] == "verdict"
    document["descriptor"]["findings"].append(
        {
            "text": "Joint temperature is above the internal watch value.",
            "severity": "Worth a look",
            "tier": "health_finding",
            "reported_by": "Reviewer 1",
            "trial": "trial-01",
        }
    )
    assert validate_document(document) == []
    document["descriptor"]["findings"][1]["tier"] = "urgent"
    assert validate_document(document)
    document["descriptor"]["findings"][1]["tier"] = "health_finding"
    document["descriptor"]["findings"][1]["reported_by"] = "<script>"
    assert validate_document(document)


@pytest.mark.parametrize(
    "grade",
    [-1, 101, 50.5, 100.0, True, False, "80", None],
)
def test_grade_must_be_an_integer_from_0_to_100(grade: object) -> None:
    document = _scenario_with_icon()
    document["descriptor"]["grade"] = grade
    assert validate_document(document)
    document["descriptor"]["grade"] = 0
    assert validate_document(document) == []
    document["descriptor"]["grade"] = 100
    assert validate_document(document) == []


@pytest.mark.parametrize(
    "finding",
    [{}, {"severity": "Needs attention"}, {"text": ""}, {"text": "   "}],
)
def test_a_finding_requires_text(finding: dict) -> None:
    document = _scenario_with_icon()
    document["descriptor"]["findings"] = [finding]
    assert validate_document(document)


@pytest.mark.parametrize("tier", ["Verdict", "health", "test_system", "urgent", ""])
def test_bad_tier_is_rejected(tier: str) -> None:
    document = _scenario_with_icon()
    document["descriptor"]["tier"] = tier
    assert validate_document(document)


@pytest.mark.parametrize("trial", [7.5, 7.0, -1, True, 1_000_000])
def test_trial_number_is_a_short_non_negative_integer(trial: object) -> None:
    document = _scenario_with_icon()
    document["descriptor"]["findings"][0]["trial"] = trial
    assert validate_document(document)
    document["descriptor"]["findings"][0]["trial"] = "7.5"
    assert validate_document(document) == []


def test_ampersand_in_descriptor_text_is_plain_text() -> None:
    document = _scenario_with_icon()
    document["evaluator"]["display_name"] = "R&D"
    document["descriptor"]["title"] = "R&D"
    document["descriptor"]["purpose"] = "Judges R&D trials and Q&A notes."
    document["descriptor"]["findings"][0]["text"] = "The R&D limit was missed."
    assert validate_document(document) == []


@pytest.mark.parametrize(
    "text",
    [
        "<script>alert(1)</script>",
        "<b>bold</b>",
        "3 < 5",
        "3 > 5",
        "line\nbreak",
        "line\rbreak",
        "line\tbreak",
        "null\x00byte",
        "esc\x1bape",
        "del\x7fchar",
        "c1\x85char",
        "line\u2028sep",
        "line\u2029sep",
    ],
)
def test_text_rejects_markup_entities_and_controls(text: str) -> None:
    document = _scenario_with_icon()
    document["descriptor"]["findings"][0]["text"] = text
    assert validate_document(document)
    document["descriptor"]["purpose"] = text
    document["descriptor"]["findings"][0]["text"] = "The centerline limit was missed."
    assert validate_document(document)


def test_text_rejects_strings_over_the_published_maximum() -> None:
    schema = load_json(SCHEMA_ROOT / "descriptor.schema.json")
    assert schema["properties"]["title"]["maxLength"] == 80
    assert schema["properties"]["short_title"]["maxLength"] == 40
    assert schema["properties"]["icon"]["maxLength"] == 8192
    assert schema["properties"]["purpose"]["maxLength"] == 400
    assert schema["properties"]["grade"]["maximum"] == 100
    assert schema["properties"]["findings"]["maxItems"] == 50
    finding = schema["$defs"]["finding"]["properties"]
    assert finding["text"]["maxLength"] == 280
    assert finding["reported_by"]["maxLength"] == 80
    document = _scenario_with_icon()
    document["descriptor"]["findings"][0]["text"] = "x" * 280
    assert validate_document(document) == []
    document["descriptor"]["findings"][0]["text"] = "x" * 281
    assert validate_document(document)
    document["descriptor"]["findings"][0]["text"] = "The centerline limit was missed."
    long_name = "S" * 81
    document["evaluator"]["display_name"] = long_name
    document["descriptor"]["title"] = long_name
    assert validate_document(document)


def test_parser_is_defusedxml() -> None:
    import defusedxml.ElementTree as defused_tree

    assert fromstring is defused_tree.fromstring


def test_external_entity_is_not_resolved(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET-MARKER")
    icon = (
        '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file://'
        + str(secret)
        + '">]><svg viewBox="0 0 24 24">&xxe;</svg>'
    )
    errors = svg_subset_errors(icon)
    assert errors
    assert "SECRET-MARKER" not in "\n".join(errors)
    with pytest.raises(DefusedXmlException):
        fromstring(icon)


def test_allowed_shapes_and_paints() -> None:
    icon = _svg(
        "<line x1='0' y1='0' x2='1' y2='1' stroke='currentColor'/>"
        "<polyline points='0,0 1,1' fill='none' stroke='currentColor'/>"
        "<polygon points='0,0 1,0 1,1' fill='transparent'/>"
        "<circle cx='1' cy='1' r='1' fill='none'/>"
        "<g><rect width='1' height='1' fill='currentColor'/></g>"
        "<path d='M0 0 L1 1' fill='none' stroke='currentColor'/>"
    )
    assert svg_subset_errors(icon) == []
    document = _with_both_icons(_scenario_with_icon(), icon)
    assert validate_document(document) == []


@pytest.mark.parametrize(
    ("name", "icon", "needle"),
    [
        ("script", _svg("<script>alert(1)</script>"), "script"),
        ("nested-script", _svg("<g><script>alert(1)</script></g>"), "script"),
        ("style", _svg("<style>svg{fill:red}</style>"), "style"),
        ("foreignObject", _svg("<foreignObject width='1' height='1'/>"), "foreignObject"),
        ("image", _svg("<image href='https://example.com/a.png'/>"), "image"),
        ("use", _svg("<use href='#mark'/>"), "use"),
        ("text", _svg("<text>hi</text>"), "element 'text'"),
        ("font", _svg("<font/>"), "font"),
        (
            "anchor",
            _svg("<a href='https://example.com/'><rect width='1' height='1' fill='none'/></a>"),
            "element 'a'",
        ),
        ("title", SOURCE_ART, "title"),
        ("hex-paint", SOURCE_ART, "#0E8785"),
        (
            "href",
            _svg("<rect href='https://example.com/x' width='1' height='1' fill='none'/>"),
            "href",
        ),
        (
            "xlink-href",
            (
                "<svg xmlns:xlink='http://www.w3.org/1999/xlink' viewBox='0 0 24 24'>"
                "<rect width='1' height='1' fill='none' xlink:href='#mark'/>"
                "</svg>"
            ),
            "href",
        ),
        ("url", _svg("<rect filter='url(#f)' width='1' height='1' fill='none'/>"), "external"),
        (
            "javascript",
            _svg("<rect width='1' height='1' fill='none' data='javascript:alert(1)'/>"),
            "external",
        ),
        (
            "onclick",
            _svg("<rect onclick='alert(1)' width='1' height='1' fill='none'/>"),
            "event attribute",
        ),
        ("onload", _svg("<rect ONLOAD='alert(1)' width='1' height='1' fill='none'/>"), "ONLOAD"),
        (
            "style-attribute",
            _svg("<rect style='fill:red' width='1' height='1' fill='none'/>"),
            "style attribute",
        ),
        (
            "missing-viewBox",
            _svg("<rect width='1' height='1' fill='none'/>", view_box=False),
            "viewBox",
        ),
        ("oversize", "<svg viewBox='0 0 24 24'>" + (" " * 8200) + "</svg>", "bytes"),
        ("cdata", "<svg viewBox='0 0 24 24'><![CDATA[x]]></svg>", "CDATA"),
        ("entity", _svg("<rect width='1' height='&amp;' fill='none'/>"), "entity"),
        ("numeric-entity", _svg("<rect width='1' height='&#60;' fill='none'/>"), "entity"),
        ("doctype", "<!DOCTYPE svg><svg viewBox='0 0 24 24'></svg>", "declaration"),
        (
            "processing-instruction",
            "<?xml-stylesheet href='x'?><svg viewBox='0 0 24 24'></svg>",
            "processing",
        ),
        ("xml-declaration", "<?xml version='1.0'?><svg viewBox='0 0 24 24'></svg>", "processing"),
        (
            "comment",
            _svg(
                "<!-- </svg><script>alert(1)</script> --><rect width='1' height='1' fill='none'/>"
            ),
            "comment",
        ),
        (
            "two-roots",
            "<svg viewBox='0 0 24 24'></svg><svg viewBox='0 0 24 24'></svg>",
            "well-formed",
        ),
        ("not-svg", "<rect viewBox='0 0 24 24' width='1' height='1' fill='none'/>", "root"),
        (
            "lowercase-currentcolor",
            _svg("<rect width='1' height='1' fill='currentcolor'/>"),
            "currentColor",
        ),
        ("black-fill", _svg("<rect width='1' height='1' fill='black'/>"), "black"),
    ],
)
def test_svg_subset_rejects(name: str, icon: str, needle: str) -> None:
    del name
    errors = svg_subset_errors(icon)
    assert errors
    assert any(needle in error for error in errors)
    document = _with_both_icons(_scenario_with_icon(), icon)
    strict = validate_document(document)
    assert any(needle in error for error in strict)


def test_svg_byte_cap_counts_utf_8_bytes() -> None:
    icon = "<svg viewBox='0 0 24 24' id='" + ("é" * 4096) + "'></svg>"
    assert len(icon) <= 8192
    assert len(icon.encode("utf-8")) > 8192
    assert any("bytes" in error for error in svg_subset_errors(icon))
    document = _with_both_icons(_scenario_with_icon(), icon)
    assert any("bytes" in error for error in validate_document(document))
