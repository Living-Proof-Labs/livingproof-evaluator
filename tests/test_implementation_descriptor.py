# SPDX-License-Identifier: Apache-2.0
"""Implementation descriptor: the file an evaluator implementation ships (issue 74).

The format name is defined once, as properties.format.const. These tests read that
const and do not spell it themselves.
"""

from __future__ import annotations

import copy

import pytest

from support import EXAMPLES, ROOT, SCHEMA_ROOT, load_json, schema_errors

SCHEMA = SCHEMA_ROOT / "implementation.schema.json"
VALID = EXAMPLES / "implementation" / "run-integrity.json"
INVALID = EXAMPLES / "implementation" / "invalid"
GUIDE = ROOT / "docs" / "implementation-descriptor.md"

INVALID_PATHS = {
    "unknown-placeholder.json": "arguments/2",
    "unknown-kind.json": "kind",
    "extra-field.json": "<root>",
    "missing-exit-0.json": "exit_codes",
    "absolute-package-source.json": "package/name",
    "url-package-source.json": "package/name",
    "nested-extra-field.json": "package",
}


def schema() -> dict:
    return load_json(SCHEMA)


def format_const() -> str:
    return schema()["properties"]["format"]["const"]


def paths(document: dict) -> list[str]:
    return [error.split(": ", 1)[0] for error in schema_errors(schema(), document)]


def test_the_run_integrity_descriptor_validates() -> None:
    document = load_json(VALID)
    assert schema_errors(schema(), document) == []
    assert document["id"] == "livingproof-run-integrity"
    assert document["kind"] == "integrity"
    assert document["grading"] == "none"
    assert document["package"] == {"name": "livingproof-evaluator-run"}
    assert document["runtime"] == {"python": "3.12"}
    assert document["entrypoint"] == {"module": "livingproof_evaluator_run"}
    assert document["arguments"] == [
        "{evidence_manifest}",
        {"if": "media_dir", "then": ["--media", "{media_dir}"]},
        "--out",
        "{result}",
    ]
    assert document["exit_codes"] == {"0": "result", "2": "refused"}
    assert document["result"] == "livingproof-evaluator-result/1.1.0"


@pytest.mark.parametrize("name", sorted(INVALID_PATHS))
def test_each_invalid_example_fails_at_its_path(name: str) -> None:
    assert paths(load_json(INVALID / name)) == [INVALID_PATHS[name]]


def test_examples_and_the_guide_use_the_format_const() -> None:
    name = format_const()
    assert isinstance(name, str) and name
    assert SCHEMA.read_text().count(name) == 1
    guide = GUIDE.read_text()
    assert name in guide
    readme = (ROOT / "README.md").read_text()
    assert name in readme
    found = sorted(VALID.parent.rglob("*.json"))
    assert [path.relative_to(VALID.parent).as_posix() for path in found] == [
        "invalid/absolute-package-source.json",
        "invalid/extra-field.json",
        "invalid/missing-exit-0.json",
        "invalid/nested-extra-field.json",
        "invalid/unknown-kind.json",
        "invalid/unknown-placeholder.json",
        "invalid/url-package-source.json",
        "run-integrity.json",
    ]
    for path in found:
        assert load_json(path)["format"] == name
        assert path.name not in {"request.json", "result.json"}


def test_the_guide_and_schema_state_the_closed_rules() -> None:
    guide = GUIDE.read_text()
    raw = SCHEMA.read_text()
    for text in (guide, raw):
        assert "The format stays /1." in text
        assert "A consumer MUST refuse a kind it does not know." in text
        assert "Any exit code not listed in exit_codes is a failure with no result." in text
        assert "Fixed at 3.12 for now and will widen later." in text
        assert "at the same commit" in text
    assert "later minor version" in guide
    assert "Later kinds arrive as minor versions" in guide
    assert "evaluator-descriptor.md" in guide
    assert (
        "Implementation descriptor: docs/implementation-descriptor.md"
        in (ROOT / "tools/manual/mkdocs.yml").read_text()
    )


def test_the_schema_identity_and_closed_objects() -> None:
    document = schema()
    assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert document["$id"] == (
        "https://github.com/Living-Proof-Labs/livingproof-evaluator/"
        "schema/implementation.schema.json"
    )
    assert document["title"] == "Evaluator implementation descriptor"
    assert document["required"] == [
        "format",
        "id",
        "kind",
        "grading",
        "package",
        "runtime",
        "entrypoint",
        "arguments",
        "exit_codes",
        "result",
    ]
    assert document["properties"]["id"]["$ref"] == "defs.schema.json#/$defs/slug"
    name = document["properties"]["package"]["properties"]["name"]
    assert name["pattern"] == r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$"
    arguments = document["properties"]["arguments"]
    assert arguments["minItems"] == 1
    assert [clause["contains"]["pattern"] for clause in arguments["allOf"]] == [
        r"\{evidence_manifest\}",
        r"\{result\}",
    ]
    assert document["$defs"]["argument"]["pattern"] == (
        r"^(?:[^{}]|\{(?:evidence_manifest|media_dir|result)\})*$"
    )
    exit_codes = document["properties"]["exit_codes"]
    assert exit_codes["required"] == ["0"]
    assert exit_codes["properties"]["0"]["const"] == "result"
    found: list[tuple[str, object]] = []

    def walk(value: object, where: str) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                found.append((where, value.get("additionalProperties")))
            for key, child in value.items():
                walk(child, f"{where}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{where}/{index}")

    walk(document, "<schema>")
    assert found
    assert all(flag is False for _, flag in found), found


def _drop_root_additional_properties(document: dict) -> dict:
    copied = copy.deepcopy(document)
    del copied["additionalProperties"]
    return copied


def _drop_package_additional_properties(document: dict) -> dict:
    copied = copy.deepcopy(document)
    del copied["properties"]["package"]["additionalProperties"]
    return copied


def _widen_argument_pattern(document: dict) -> dict:
    copied = copy.deepcopy(document)
    copied["$defs"]["argument"]["pattern"] = ".*"
    return copied


def _drop_required_exit_zero(document: dict) -> dict:
    copied = copy.deepcopy(document)
    copied["properties"]["exit_codes"]["required"].remove("0")
    return copied


def _open_kind(document: dict) -> dict:
    copied = copy.deepcopy(document)
    kind = copied["properties"]["kind"]
    kind.pop("enum")
    kind["type"] = "string"
    return copied


def _drop_package_name_pattern(document: dict) -> dict:
    copied = copy.deepcopy(document)
    del copied["properties"]["package"]["properties"]["name"]["pattern"]
    return copied


_PROBES = [
    ("extra-field.json", _drop_root_additional_properties),
    ("nested-extra-field.json", _drop_package_additional_properties),
    ("unknown-placeholder.json", _widen_argument_pattern),
    ("missing-exit-0.json", _drop_required_exit_zero),
    ("unknown-kind.json", _open_kind),
    ("absolute-package-source.json", _drop_package_name_pattern),
]


@pytest.mark.parametrize(("name", "loosen"), _PROBES, ids=[name for name, _ in _PROBES])
def test_loosening_the_schema_accepts_the_matching_invalid_example(name: str, loosen) -> None:
    instance = load_json(INVALID / name)
    assert schema_errors(schema(), instance)
    assert schema_errors(loosen(schema()), instance) == []


def test_a_forty_hex_commit_or_a_url_is_rejected_as_the_package_name() -> None:
    commit = "e8d825fcd5ea61d8a49cefcf4c41a321519e1893"
    assert len(commit) == 40
    url = "https://github.com/Living-Proof-Labs/livingproof-evaluator"
    for name in (commit, url):
        document = load_json(VALID)
        document["package"]["name"] = name
        assert paths(document) == ["package/name"]


def test_a_conditional_without_then_is_rejected() -> None:
    document = load_json(VALID)
    document["arguments"][1] = {"if": "media_dir"}
    assert paths(document) == ["arguments/1"]


def test_arguments_without_a_top_level_result_placeholder_are_rejected() -> None:
    missing = load_json(VALID)
    missing["arguments"] = [item for item in missing["arguments"] if item != "{result}"]
    nested = load_json(VALID)
    nested["arguments"] = [
        "{evidence_manifest}",
        {"if": "result", "then": ["{result}"]},
    ]
    for document in (missing, nested):
        assert "arguments" in paths(document)


def test_id_must_be_the_shared_slug() -> None:
    document = load_json(VALID)
    document["id"] = "Not a slug"
    assert paths(document) == ["id"]


def test_a_nested_conditional_is_rejected() -> None:
    document = load_json(VALID)
    document["arguments"][1]["then"].append({"if": "media_dir", "then": ["--more"]})
    assert paths(document) == ["arguments/1"]
