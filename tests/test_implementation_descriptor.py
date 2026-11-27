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
    "scenario-grading-none.json": "grading",
    "unknown-kind-name.json": "kind",
    "extra-field.json": "<root>",
    "missing-exit-0.json": "exit_codes",
    "absolute-package-source.json": "package/name",
    "url-package-source.json": "package/name",
    "nested-extra-field.json": "package",
    "result-major-2.json": "result",
    "advisory-grading.json": "grading",
    "advisory-result-minor.json": "result",
    "integrity-media-run.json": "media",
    "advisory-media-run.json": "media",
    "integrity-thresholds.json": "arguments/1",
    "advisory-thresholds.json": "arguments/1",
}

MEDIA_RUN = (
    "A consumer runs the media run only when it has both a media directory and a world document; "
    "otherwise it runs no media process and writes no media result."
)

SCENARIO = EXAMPLES / "implementation" / "scenario.json"
ONE_GRADER = (
    "At most one evaluator in a run may grade the robot. "
    "A descriptor is one evaluator, so the descriptor cannot state that rule. "
    "A consumer that loads a list of descriptors MUST refuse a list with two "
    "`grading` values of `robot`."
)


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
    assert document["result"] == "livingproof-evaluator-result/1.2.0"


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
        "advisory.json",
        "battery-thermal.json",
        "consumer/two-robot-graders.json",
        "invalid/absolute-package-source.json",
        "invalid/advisory-grading.json",
        "invalid/advisory-media-run.json",
        "invalid/advisory-result-minor.json",
        "invalid/advisory-thresholds.json",
        "invalid/extra-field.json",
        "invalid/integrity-media-run.json",
        "invalid/integrity-thresholds.json",
        "invalid/missing-exit-0.json",
        "invalid/nested-extra-field.json",
        "invalid/result-major-2.json",
        "invalid/scenario-grading-none.json",
        "invalid/unknown-kind-name.json",
        "invalid/unknown-kind.json",
        "invalid/unknown-placeholder.json",
        "invalid/url-package-source.json",
        "run-integrity.json",
        "scenario.json",
    ]
    for path in found:
        relative = path.relative_to(VALID.parent).as_posix()
        if relative == "consumer/two-robot-graders.json":
            pair = load_json(path)
            assert [item["format"] for item in pair] == [name, name]
            continue
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
    assert name["pattern"] == r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?(?!\n)$"
    arguments = document["properties"]["arguments"]
    assert arguments["minItems"] == 1
    assert [clause["contains"]["pattern"] for clause in arguments["allOf"]] == [
        r"\{evidence_manifest\}",
    ]
    assert document["$defs"]["argument"]["pattern"] == (
        r"^(?:[^{}\u0000]|\{(?:evidence_manifest|media_dir|result|result_dir|thresholds)\})*(?!\n)$"
    )
    assert document["$defs"]["argument_without_media_dir"]["pattern"] == (
        r"^(?:[^{}\u0000]|\{(?:evidence_manifest|result|result_dir|thresholds)\})*(?!\n)$"
    )
    assert document["$defs"]["media_argument"]["pattern"] == (
        r"^(?:[^{}\u0000]|\{(?:evidence_manifest|media_dir|result|result_dir|world|identity)\})*(?!\n)$"
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
    for name in ("argument", "argument_without_media_dir"):
        copied["$defs"][name]["pattern"] = ".*"
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


def _drop_clause(document: dict, *, kind: str, field: str) -> dict:
    copied = copy.deepcopy(document)
    copied["allOf"] = [
        clause
        for clause in copied["allOf"]
        if not (
            clause.get("if", {}).get("properties", {}).get("kind", {}).get("const") == kind
            and field in clause.get("then", {}).get("properties", {})
        )
    ]
    return copied


def _drop_advisory_grading(document: dict) -> dict:
    return _drop_clause(document, kind="advisory", field="grading")


def _drop_scenario_grading(document: dict) -> dict:
    return _drop_clause(document, kind="scenario", field="grading")


def _drop_thresholds_ban(kind: str):
    def loosen(document: dict) -> dict:
        return _drop_clause(document, kind=kind, field="arguments")

    return loosen


def _drop_media_ban(kind: str):
    def loosen(document: dict) -> dict:
        return _drop_clause(document, kind=kind, field="media")

    return loosen


def _drop_advisory_result_minor(document: dict) -> dict:
    return _drop_clause(document, kind="advisory", field="result")


def _drop_package_name_pattern(document: dict) -> dict:
    copied = copy.deepcopy(document)
    del copied["properties"]["package"]["properties"]["name"]["pattern"]
    return copied


_PROBES = [
    ("extra-field.json", _drop_root_additional_properties),
    ("nested-extra-field.json", _drop_package_additional_properties),
    ("unknown-placeholder.json", _widen_argument_pattern),
    ("missing-exit-0.json", _drop_required_exit_zero),
    ("scenario-grading-none.json", _drop_scenario_grading),
    ("unknown-kind-name.json", _open_kind),
    ("absolute-package-source.json", _drop_package_name_pattern),
    ("advisory-grading.json", _drop_advisory_grading),
    ("advisory-result-minor.json", _drop_advisory_result_minor),
    ("integrity-media-run.json", _drop_media_ban("integrity")),
    ("advisory-media-run.json", _drop_media_ban("advisory")),
    ("integrity-thresholds.json", _drop_thresholds_ban("integrity")),
    ("advisory-thresholds.json", _drop_thresholds_ban("advisory")),
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


def test_a_trailing_newline_is_rejected_in_names_and_exit_codes() -> None:
    named = load_json(VALID)
    named["package"]["name"] += "\n"
    assert paths(named) == ["package/name"]

    module = load_json(VALID)
    module["entrypoint"]["module"] += "\n"
    assert paths(module) == ["entrypoint/module"]

    codes = load_json(VALID)
    codes["exit_codes"]["2\n"] = codes["exit_codes"].pop("2")
    assert paths(codes) == ["exit_codes", "exit_codes"]


def _widen_exit_code_key_pattern(document: dict) -> dict:
    copied = copy.deepcopy(document)
    exit_codes = copied["properties"]["exit_codes"]
    pattern = exit_codes["propertyNames"]["pattern"]
    exit_codes["propertyNames"]["pattern"] = "^.*$"
    exit_codes["patternProperties"]["^.*$"] = exit_codes["patternProperties"].pop(pattern)
    return copied


def test_exit_code_keys_are_0_through_255() -> None:
    for code in ("1", "99", "199", "255"):
        document = load_json(VALID)
        document["exit_codes"][code] = "result"
        assert schema_errors(schema(), document) == [], code
    for code in ("256", "999", "1000", "02", "-1"):
        document = load_json(VALID)
        document["exit_codes"][code] = "refused"
        assert paths(document) == ["exit_codes", "exit_codes"], code
    # Replacing the key pattern with ^.*$ accepts a code the strict pattern refuses.
    out_of_range = load_json(VALID)
    out_of_range["exit_codes"]["256"] = "result"
    assert schema_errors(_widen_exit_code_key_pattern(schema()), out_of_range) == []


def _with_result(version: str) -> dict:
    document = load_json(VALID)
    document["result"] = f"livingproof-evaluator-result/{version}"
    return document


def _widen_result_pattern_to_unicode_digits(document: dict) -> dict:
    copied = copy.deepcopy(document)
    copied["properties"]["result"]["pattern"] = r"^livingproof-evaluator-result/1\.\d+\.\d+(?!\n)$"
    return copied


def _drop_result_newline_guard(document: dict) -> dict:
    copied = copy.deepcopy(document)
    pattern = copied["properties"]["result"]["pattern"]
    copied["properties"]["result"]["pattern"] = pattern.replace(r"(?!\n)", "")
    return copied


def test_result_accepts_1_minor_versions_and_refuses_another_major() -> None:
    rule = "`result` is `livingproof-evaluator-result/1.<minor>.<patch>`. Another major is refused."
    consumer = (
        "Consumers must check that the produced result's format equals the declared value "
        "and that its major is one they support."
    )
    guide = GUIDE.read_text()
    raw = SCHEMA.read_text()
    assert rule in raw and consumer in raw
    fields = guide.split("## Fields", 1)[1].split("\n## ", 1)[0]
    assert rule in fields
    assert rule in guide.split("## Result", 1)[1]
    assert consumer in guide
    for version in ("1.0.0", "1.2.0", "1.12.3"):
        assert schema_errors(schema(), _with_result(version)) == [], version
    for version in ("1.\u0662.0", "1.02.0", "1.2.0\n"):
        assert paths(_with_result(version)) == ["result"], version
    assert paths(load_json(INVALID / "result-major-2.json")) == ["result"]
    widened = _widen_result_pattern_to_unicode_digits(schema())
    assert schema_errors(widened, _with_result("1.\u0662.0")) == []
    assert schema_errors(widened, _with_result("1.02.0")) == []
    assert schema_errors(_drop_result_newline_guard(schema()), _with_result("1.2.0\n")) == []


def _allow_nul_in_arguments(document: dict) -> dict:
    copied = copy.deepcopy(document)
    for definition in copied["$defs"].values():
        pattern = definition.get("pattern")
        if isinstance(pattern, str) and r"\u0000" in pattern:
            definition["pattern"] = pattern.replace(r"\u0000", "")
    return copied


def test_an_argument_with_nul_is_refused() -> None:
    document = load_json(VALID)
    document["arguments"][1]["then"][0] = "--media\u0000"
    assert paths(document) == ["arguments/1"]
    assert schema_errors(_allow_nul_in_arguments(schema()), document) == []


def test_a_newline_in_an_argument_is_allowed() -> None:
    embedded = load_json(VALID)
    embedded["arguments"][1]["then"][0] = "--media\ndir"
    trailing = load_json(VALID)
    trailing["arguments"][2] = "--out\n"
    assert schema_errors(schema(), embedded) == []
    assert schema_errors(schema(), trailing) == []


def _allow_media_dir_anywhere(document: dict) -> dict:
    copied = copy.deepcopy(document)
    media = {"$ref": "#/$defs/argument"}
    copied["properties"]["arguments"]["items"]["oneOf"][0] = media
    for branch in copied["$defs"]["conditional"]["allOf"]:
        branch["then"]["properties"]["then"]["items"] = dict(media)
    return copied


def test_media_dir_appears_only_in_its_conditional() -> None:
    assert schema_errors(schema(), load_json(VALID)) == []
    top_level = load_json(VALID)
    top_level["arguments"][2] = "{media_dir}"
    assert paths(top_level) == ["arguments/2"]
    wrong_if = load_json(VALID)
    wrong_if["arguments"][1] = {"if": "result", "then": ["{media_dir}"]}
    assert paths(wrong_if) == ["arguments/1"]
    loosened = _allow_media_dir_anywhere(schema())
    assert schema_errors(loosened, top_level) == []
    assert schema_errors(loosened, wrong_if) == []


def test_integrity_grading_stays_none() -> None:
    document = load_json(VALID)
    document["grading"] = "robot"
    assert paths(document) == ["grading"]
    assert schema_errors(_drop_clause(schema(), kind="integrity", field="grading"), document) == []


def test_advisory_result_accepts_minor_1_3_or_later() -> None:
    for version in ("1.3.0", "1.3.1", "1.4.0", "1.10.0"):
        document = _with_result(version)
        document["kind"] = "advisory"
        assert schema_errors(schema(), document) == [], version


def test_advisory_result_refuses_a_minor_before_1_3_and_another_major() -> None:
    for version in ("1.2.0", "1.2.1"):
        document = _with_result(version)
        document["kind"] = "advisory"
        assert paths(document) == ["result"], version
    # Major 2 misses both the shared 1.x pattern and the advisory minor rule.
    another_major = _with_result("2.0.0")
    another_major["kind"] = "advisory"
    assert paths(another_major) == ["result", "result"]


def test_advisory_descriptors_validate_and_keep_the_media_dir_conditional() -> None:
    for name in ("advisory.json", "battery-thermal.json"):
        document = load_json(VALID.parent / name)
        assert schema_errors(schema(), document) == []
        assert document["kind"] == "advisory"
        assert document["grading"] == "none"
        assert document["result"] == "livingproof-evaluator-result/1.3.0"
        assert document["arguments"][1] == {"if": "media_dir", "then": ["--media", "{media_dir}"]}
    moved = load_json(VALID.parent / "advisory.json")
    moved["arguments"][2] = "{media_dir}"
    assert paths(moved) == ["arguments/2"]


def test_the_guide_says_to_refuse_duplicate_object_keys() -> None:
    fields = GUIDE.read_text().split("## Fields", 1)[1].split("\n## ", 1)[0]
    assert "A consumer MUST refuse a document with duplicate JSON object keys." in fields


def test_the_scenario_descriptor_matches_the_two_package_commands() -> None:
    document = load_json(SCENARIO)
    assert schema_errors(schema(), document) == []
    assert schema()["properties"]["kind"]["enum"] == ["integrity", "advisory", "scenario"]
    assert document["id"] == "livingproof-scenario"
    assert document["kind"] == "scenario"
    assert document["grading"] == "robot"
    assert document["package"] == {"name": "livingproof-evaluator-scenario"}
    assert document["entrypoint"] == {"module": "livingproof_evaluator_scenario"}
    assert document["arguments"] == [
        "{evidence_manifest}",
        "--thresholds",
        "{thresholds}",
        "--out",
        "{result_dir}",
    ]
    assert document["media"] == {
        "module": "livingproof_evaluator_scenario.media",
        "arguments": [
            "{evidence_manifest}",
            "{media_dir}",
            "{result_dir}",
            "--world",
            "{world}",
            "--identity",
            "{identity}",
        ],
    }
    assert document["exit_codes"] == {"0": "result", "1": "refused"}
    assert "2" not in document["exit_codes"]
    assert document["result"] == "livingproof-evaluator-result/1.1.0"
    narrowed = schema()
    narrowed["properties"]["kind"]["enum"] = ["integrity", "advisory"]
    assert schema_errors(narrowed, document)


def test_kind_and_grading_pair_only_three_ways() -> None:
    bases = {
        "integrity": load_json(VALID),
        "advisory": load_json(VALID.parent / "advisory.json"),
        "scenario": load_json(SCENARIO),
    }
    accepted = {("integrity", "none"), ("advisory", "none"), ("scenario", "robot")}
    for kind, grading in (
        ("integrity", "none"),
        ("integrity", "robot"),
        ("integrity", "other"),
        ("advisory", "none"),
        ("advisory", "robot"),
        ("advisory", "other"),
        ("scenario", "robot"),
        ("scenario", "none"),
        ("scenario", "other"),
    ):
        document = copy.deepcopy(bases[kind])
        document["kind"] = kind
        document["grading"] = grading
        errors = schema_errors(schema(), document)
        assert (errors == []) is ((kind, grading) in accepted), (kind, grading, errors)


def _drop_media_contains(document: dict, token: str) -> dict:
    copied = copy.deepcopy(document)
    arguments = copied["properties"]["media"]["properties"]["arguments"]
    arguments["allOf"] = [
        clause for clause in arguments["allOf"] if token not in clause["contains"]["pattern"]
    ]
    return copied


def _allow_token(document: dict, definition: str, token: str) -> dict:
    copied = copy.deepcopy(document)
    pattern = copied["$defs"][definition]["pattern"]
    copied["$defs"][definition]["pattern"] = pattern.replace("result", f"result|{token}", 1)
    return copied


def test_world_and_identity_stay_on_the_media_run() -> None:
    for token in ("world", "identity"):
        document = load_json(SCENARIO)
        document["arguments"].append("{" + token + "}")
        assert paths(document) == ["arguments/5"], token
        loosened = _allow_token(schema(), "argument_without_media_dir", token)
        assert schema_errors(loosened, document) == [], token


RESULT_FILE = "integrity and advisory write that file. It is not a directory."
RESULT_DIR = (
    "`{result_dir}` is a directory a scenario run writes into. "
    "The per-trial result files in that directory are the results, "
    "and each one carries the declared result format. "
    "`thresholds.json` and any other file in the directory are not results."
)
THRESHOLDS_ROW = (
    "| `{thresholds}` | Path of the thresholds file a scenario trial reads. "
    "Only `kind: scenario` may use it, in a top-level trial argument or inside `then`. "
    "`integrity` and `advisory` reject it. |"
)
WORLD_ROW = (
    "| `{world}` | Path of the world file the media run reads. "
    "It may appear only in `media.arguments`. |"
)
EXIT_1 = (
    "At scenario package v1.5.21, exit 1 is also an uncaught crash: "
    "a missing or non-JSON thresholds file, a missing manifest, or a missing media.json."
)
EXIT_1_FOLLOWUP = (
    "A distinct refusal exit code is follow-up work for "
    "[livingproof-evaluator-scenario#60]"
    "(https://github.com/Living-Proof-Labs/livingproof-evaluator-scenario/issues/60)."
)
EXIT_2 = (
    "Exit 2 is an argparse usage error, including a missing `--thresholds` or `--world`. "
    "The example does not list exit 2, so it is a failure, not a refusal."
)
HALLWAY_ONLY = "This descriptor covers the walk-hallway trial only."


def _drop_ref_clause(kind: str, ref: str):
    def loosen(document: dict) -> dict:
        copied = copy.deepcopy(document)
        copied["allOf"] = [
            clause
            for clause in copied["allOf"]
            if not (
                clause.get("if", {}).get("properties", {}).get("kind", {}).get("const") == kind
                and clause.get("then", {}).get("properties", {}).get("arguments", {}).get("$ref")
                == ref
            )
        ]
        return copied

    return loosen


def _drop_contains_clause(kind: str, token: str):
    needle = "\\{" + token + "\\}"

    def loosen(document: dict) -> dict:
        copied = copy.deepcopy(document)
        copied["allOf"] = [
            clause
            for clause in copied["allOf"]
            if not (
                clause.get("if", {}).get("properties", {}).get("kind", {}).get("const") == kind
                and clause.get("then", {})
                .get("properties", {})
                .get("arguments", {})
                .get("contains", {})
                .get("pattern")
                == needle
            )
        ]
        return copied

    return loosen


def test_the_media_run_needs_a_directory_and_a_world() -> None:
    scenario = GUIDE.read_text().split("## Scenario", 1)[1].split("\n## ", 1)[0]
    assert MEDIA_RUN in scenario
    assert MEDIA_RUN in schema()["properties"]["media"]["description"]


def test_thresholds_inside_then_are_rejected_for_integrity_and_advisory() -> None:
    for name, kind in (("run-integrity.json", "integrity"), ("advisory.json", "advisory")):
        document = load_json(VALID.parent / name)
        document["arguments"][1]["then"].append("{thresholds}")
        assert paths(document) == ["arguments/1"], kind
        assert schema_errors(_drop_thresholds_ban(kind)(schema()), document) == [], kind
    scenario = load_json(SCENARIO)
    scenario["arguments"].append({"if": "result", "then": ["{thresholds}"]})
    assert schema_errors(schema(), scenario) == []


def test_result_stays_a_file_for_integrity_and_advisory() -> None:
    guide = GUIDE.read_text()
    assert RESULT_FILE in guide
    assert RESULT_FILE in SCHEMA.read_text()
    assert "a path for the result file" in guide
    for name in ("run-integrity.json", "advisory.json", "battery-thermal.json"):
        document = load_json(VALID.parent / name)
        assert schema_errors(schema(), document) == [], name
        assert "{result}" in document["arguments"]
        assert "{result_dir}" not in str(document["arguments"])
    missing = load_json(VALID)
    missing["arguments"] = [item for item in missing["arguments"] if item != "{result}"]
    assert "arguments" in paths(missing)
    assert schema_errors(_drop_contains_clause("integrity", "result")(schema()), missing) == []


def test_result_dir_is_scenario_only() -> None:
    scenario = load_json(SCENARIO)
    assert schema_errors(schema(), scenario) == []
    assert "{result_dir}" in scenario["arguments"]
    assert "{result_dir}" in scenario["media"]["arguments"]
    assert RESULT_DIR in GUIDE.read_text().split("## Scenario", 1)[1]
    assert RESULT_DIR in schema()["properties"]["media"]["description"]
    for name, kind in (("run-integrity.json", "integrity"), ("advisory.json", "advisory")):
        document = load_json(VALID.parent / name)
        document["arguments"].append("{result_dir}")
        assert paths(document) == ["arguments/4"], kind
        assert (
            schema_errors(_drop_ref_clause(kind, "#/$defs/no_result_dir")(schema()), document) == []
        )
    omitted = load_json(SCENARIO)
    omitted["arguments"] = [item for item in omitted["arguments"] if item != "{result_dir}"]
    assert "arguments" in paths(omitted)
    assert schema_errors(_drop_contains_clause("scenario", "result_dir")(schema()), omitted) == []


def test_the_scenario_descriptor_is_walk_hallway_only() -> None:
    scenario = GUIDE.read_text().split("## Scenario", 1)[1].split("\n## ", 1)[0]
    assert HALLWAY_ONLY in scenario
    assert "walk-corner" in scenario
    assert "follow-up work" in scenario


def test_scenario_exit_2_is_a_failure() -> None:
    document = load_json(SCENARIO)
    assert document["exit_codes"] == {"0": "result", "1": "refused"}
    assert "2" not in document["exit_codes"]
    assert EXIT_2 in GUIDE.read_text()


def test_scenario_exit_1_covers_refusals_and_crashes() -> None:
    document = load_json(SCENARIO)
    assert document["exit_codes"]["1"] == "refused"
    guide = GUIDE.read_text()
    assert EXIT_1 in guide
    assert EXIT_1_FOLLOWUP in guide


def test_media_module_rejects_a_trailing_newline() -> None:
    document = load_json(SCENARIO)
    document["media"]["module"] += "\n"
    assert paths(document) == ["media/module"]
    loosened = schema()
    module = loosened["properties"]["media"]["properties"]["module"]
    module["pattern"] = module["pattern"].replace("(?!\\n)", "")
    assert schema_errors(loosened, document) == []


@pytest.mark.parametrize("module", ["../x", "-c"])
def test_media_module_pattern_is_enforced(module: str) -> None:
    document = load_json(SCENARIO)
    document["media"]["module"] = module
    assert paths(document) == ["media/module"]
    loosened = schema()
    del loosened["properties"]["media"]["properties"]["module"]["pattern"]
    assert schema_errors(loosened, document) == []


def test_media_arguments_are_required() -> None:
    document = load_json(SCENARIO)
    del document["media"]["arguments"]
    assert paths(document) == ["media"]
    loosened = schema()
    loosened["properties"]["media"]["required"].remove("arguments")
    assert schema_errors(loosened, document) == []


@pytest.mark.parametrize("media", ["python -m x", [1]])
def test_media_must_be_an_object(media: object) -> None:
    document = load_json(SCENARIO)
    document["media"] = media
    assert paths(document) == ["media"]
    loosened = schema()
    del loosened["properties"]["media"]["type"]
    assert schema_errors(loosened, document) == []


def test_the_thresholds_placeholder_row() -> None:
    assert THRESHOLDS_ROW in GUIDE.read_text()


def test_world_appears_only_in_media_arguments() -> None:
    assert WORLD_ROW in GUIDE.read_text()


def test_thresholds_stay_off_the_media_run() -> None:
    document = load_json(SCENARIO)
    document["media"]["arguments"].append("{thresholds}")
    assert paths(document) == ["media/arguments/7"]
    loosened = _allow_token(schema(), "media_argument", "thresholds")
    assert schema_errors(loosened, document) == []


def test_the_media_run_requires_its_three_placeholders() -> None:
    for token in ("evidence_manifest", "media_dir", "result_dir"):
        document = load_json(SCENARIO)
        document["media"]["arguments"] = [
            item for item in document["media"]["arguments"] if "{" + token + "}" not in item
        ]
        assert "media/arguments" in paths(document), token
        assert schema_errors(_drop_media_contains(schema(), token), document) == [], token


def test_a_media_run_names_its_module() -> None:
    document = load_json(SCENARIO)
    del document["media"]["module"]
    assert paths(document) == ["media"]
    loosened = schema()
    loosened["properties"]["media"]["required"].remove("module")
    assert schema_errors(loosened, document) == []


def test_media_arguments_are_flat_strings() -> None:
    document = load_json(SCENARIO)
    document["media"]["arguments"].append({"if": "media_dir", "then": ["{media_dir}"]})
    assert paths(document) == ["media/arguments/7"]
    loosened = schema()
    loosened["properties"]["media"]["properties"]["arguments"]["items"] = {}
    assert schema_errors(loosened, document) == []


def test_two_robot_graders_are_each_valid_and_left_to_the_consumer() -> None:
    pair = load_json(VALID.parent / "consumer" / "two-robot-graders.json")
    assert [item["grading"] for item in pair] == ["robot", "robot"]
    assert [item["id"] for item in pair] == ["livingproof-scenario", "other-scenario"]
    for item in pair:
        assert schema_errors(schema(), item) == []
    assert schema_errors(schema(), pair)
    guide = GUIDE.read_text()
    raw = SCHEMA.read_text()
    for text in (guide, raw):
        assert ONE_GRADER in text
    section = guide.split("## One grading evaluator", 1)[1]
    assert "The schema validates one descriptor and does not see the run's list" in section
    assert "examples/implementation/consumer/two-robot-graders.json" in section
