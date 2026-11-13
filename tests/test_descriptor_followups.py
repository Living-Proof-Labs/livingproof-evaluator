# SPDX-License-Identifier: Apache-2.0
"""Issue 16 follow-ups: the cases checked by hand in Vera's review of PR 19.

Each new rule applies to a result at format 1.1 or a later 1.minor and leaves a
1.0 result on its 1.0 checks. Plain text means at least one character that is
neither whitespace nor a Unicode format character (category Cf).
"""

from __future__ import annotations

import json
import re

import pytest
from validate_contract import validate_document

from support import EXAMPLES, SCHEMA_ROOT, load_json

FORMAT_ONLY = {
    "U+FEFF": "\ufeff",
    "U+200B": "\u200b",
    "U+200C": "\u200c",
    "U+200D": "\u200d",
    "U+2060": "\u2060",
    "U+00AD": "\u00ad",
    "all six": "\ufeff\u200b\u200c\u200d\u2060\u00ad",
    "with spaces": " \u200b \u2060 ",
    "bidi controls": "\u202a\u202c\u2066\u2069",
    "astral tag": "\U000e0001\U000e0020",
}
NOT_PLAIN = {
    "markup": "<b>Scenario</b>",
    "less-than": "a < b",
    "bell": "Sc\x07enario",
    "newline": "Sce\nnario",
    "line separator": "Sce\u2028nario",
    "C1 control": "Sce\x85nario",
    "whitespace only": "   ",
    **FORMAT_ONLY,
}
STILL_PLAIN = {
    "ampersand": "R&D",
    "emoji ZWJ sequence": "\U0001f468\u200d\U0001f469\u200d\U0001f467",
    "flag ZWJ sequence": "\U0001f3f3\ufe0f\u200d\U0001f308",
    "word with ZWJ": "Visible\u200dtext",
    "leading BOM": "\ufeffScenario",
    "soft hyphen in a word": "co\u00adoperate",
    "Persian ZWNJ": "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",
}
DISALLOWED_ICONS = {
    "script": "<script>alert(1)</script>",
    "external href on use": '<use xlink:href="https://evil.example/x.svg#a"/>',
    "external href on image": '<image href="https://evil.example/x.png" width="24" height="24"/>',
    "href on a path": '<path href="https://evil.example" d="M0 0L1 1"/>',
    "event handler": '<rect onclick="alert(1)" width="1" height="1"/>',
    "foreignObject": "<foreignObject><div>x</div></foreignObject>",
    "url paint": '<rect fill="url(https://evil.example/#g)" width="1" height="1"/>',
}


def _icon(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 24 24">' + body + "</svg>"
    )


def _later(*, title: bool = True, icon: bool = True, descriptor: bool = True) -> dict:
    document = load_json(EXAMPLES / "descriptor" / "scenario-with-icon" / "result.json")
    assert document["format"] == "livingproof-evaluator-result/1.1.0"
    if not descriptor:
        document.pop("descriptor")
        return document
    if not title:
        document["descriptor"].pop("title")
    if not icon:
        document["descriptor"].pop("icon")
    return document


def _legacy(kind: str) -> dict:
    name = {"scenario": "scenario/graded", "integrity": "integrity/clean"}[kind]
    document = load_json(EXAMPLES / name / "result.json")
    assert document["format"] == "livingproof-evaluator-result/1.0.0"
    return document


@pytest.mark.parametrize("field", ["display_name", "publisher"])
@pytest.mark.parametrize("label", sorted(NOT_PLAIN))
def test_omitted_title_rejects_each_kind_of_non_plain_name(field: str, label: str) -> None:
    for document in (_later(title=False), _later(descriptor=False)):
        document["evaluator"][field] = NOT_PLAIN[label]
        errors = validate_document(document)
        assert any(error.startswith(f"evaluator/{field}:") for error in errors), errors


@pytest.mark.parametrize("field", ["display_name", "publisher"])
@pytest.mark.parametrize("label", sorted(STILL_PLAIN))
def test_omitted_title_accepts_plain_names(field: str, label: str) -> None:
    document = _later(title=False)
    document["evaluator"][field] = STILL_PLAIN[label]
    assert validate_document(document) == []


def test_plain_text_rule_applies_to_a_later_minor_format() -> None:
    document = _later(title=False)
    document["format"] = "livingproof-evaluator-result/1.7.3"
    document["evaluator"]["publisher"] = "<b>x</b>"
    assert any(error.startswith("evaluator/publisher:") for error in validate_document(document))


@pytest.mark.parametrize("label", sorted(DISALLOWED_ICONS))
def test_omitted_descriptor_icon_rejects_each_disallowed_construct(label: str) -> None:
    for document in (_later(icon=False), _later(descriptor=False)):
        document["evaluator"]["icon"] = _icon(DISALLOWED_ICONS[label])
        errors = validate_document(document)
        assert any(error.startswith("evaluator/icon:") for error in errors), errors


@pytest.mark.parametrize("label", sorted(FORMAT_ONLY))
def test_format_only_text_is_rejected_in_descriptor_fields(label: str) -> None:
    text = FORMAT_ONLY[label]
    purpose = _later()
    purpose["descriptor"]["purpose"] = text
    assert any("descriptor/purpose" in error for error in validate_document(purpose))
    title = _later()
    title["descriptor"]["title"] = text
    title["evaluator"]["display_name"] = text
    assert any("descriptor/title" in error for error in validate_document(title))


@pytest.mark.parametrize("label", sorted(STILL_PLAIN))
def test_format_characters_beside_visible_text_stay_plain(label: str) -> None:
    document = _later()
    document["descriptor"]["purpose"] = STILL_PLAIN[label]
    document["descriptor"]["findings"][0]["text"] = STILL_PLAIN[label]
    assert validate_document(document) == []


@pytest.mark.parametrize("kind", ["scenario", "integrity"])
def test_a_1_0_result_keeps_exactly_the_1_0_checks(kind: str) -> None:
    """Values the 1.1 rules reject still validate on 1.0, as they did before PR 19."""
    for value in NOT_PLAIN.values():
        for field in ("display_name", "publisher"):
            document = _legacy(kind)
            document["evaluator"][field] = value
            assert validate_document(document) == [], (field, value)
    for body in DISALLOWED_ICONS.values():
        document = _legacy(kind)
        document["evaluator"]["icon"] = _icon(body)
        assert validate_document(document) == [], body


# JSON Schema 2020-12 patterns are ECMA-262 regular expressions. These escapes and
# groups are Python-only: \U is a syntax error under the u flag that Ajv uses, and
# without that flag it is a literal U, so "BAD" and "100" would be rejected.
_NOT_ECMA_262 = re.compile(r"\\U[0-9A-Fa-f]{8}|\\[AZz]|\(\?P[<=]|\(\?#|\(\?[aiLmsux]+[):]")


def _patterns(value: object, where: str):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "pattern" and isinstance(child, str):
                yield where, child
            if key == "patternProperties" and isinstance(child, dict):
                for name in child:
                    yield f"{where}/patternProperties", name
            yield from _patterns(child, f"{where}/{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _patterns(child, f"{where}/{index}")


@pytest.mark.xfail(
    strict=True,
    reason="PR 19 descriptor $defs/plain uses Python-only \\U escapes (Vera review)",
)
def test_schema_patterns_use_ecma_262_syntax() -> None:
    found = []
    for path in sorted(SCHEMA_ROOT.rglob("*.json")):
        for where, pattern in _patterns(json.loads(path.read_text()), path.name):
            if _NOT_ECMA_262.search(pattern):
                found.append(where)
    assert found == []


def test_verify_workflow_permissions_are_exactly_contents_read_and_checks_write() -> None:
    text = (SCHEMA_ROOT.parent / ".github" / "workflows" / "verify.yml").read_text()
    blocks = re.findall(r"(?m)^(\s*)permissions:\n((?:\1  \S.*\n)+)", text)
    found = [sorted(line.strip() for line in body.splitlines()) for _indent, body in blocks]
    assert found == [["contents: read"], ["checks: write", "contents: read"]]
