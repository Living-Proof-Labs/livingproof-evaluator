# SPDX-License-Identifier: Apache-2.0
"""Advisory kind on the implementation descriptor and the result envelope (issue 80)."""

from __future__ import annotations

import hashlib
import json
import subprocess

from validate_contract import consumer_accepts, validate_document

from support import (
    EXAMPLES,
    ROOT,
    SCHEMA_ROOT,
    load_json,
    request_schema,
    result_schema,
    schema_errors,
)

INVALID = EXAMPLES / "advisory" / "invalid"
RECORDED = EXAMPLES / "advisory" / "recorded-observation"
BATTERY = EXAMPLES / "advisory" / "battery-thermal"
PUBLISHED = ROOT / "tests" / "data" / "examples-v1.9.1.sha256"
KIND_SENTENCE = "advisory never grades and produces no robot result or test-system status."


def _copy(document: dict) -> dict:
    return json.loads(json.dumps(document))


def _errors(document: dict) -> list[str]:
    return schema_errors(result_schema(), document)


def _recorded() -> dict:
    return load_json(RECORDED / "result.json")


def _advisory_thens(document: dict) -> list[dict]:
    found = []
    for clause in document["allOf"]:
        kind = (
            clause.get("if", {})
            .get("properties", {})
            .get("evaluator", {})
            .get("properties", {})
            .get("kind", {})
        )
        if kind.get("const") == "advisory":
            found.append(clause["then"])
    return found


def _kind_then(document: dict, kind: str) -> dict:
    for clause in document["allOf"]:
        found = (
            clause.get("if", {})
            .get("properties", {})
            .get("evaluator", {})
            .get("properties", {})
            .get("kind", {})
        )
        if found.get("const") == kind:
            return clause["then"]
    raise AssertionError(kind)


def test_kind_description_says_advisory_never_grades() -> None:
    description = load_json(SCHEMA_ROOT / "defs.schema.json")["$defs"]["evaluator"]["properties"][
        "kind"
    ]["description"]
    assert KIND_SENTENCE in description


def test_recorded_observation_and_battery_thermal_validate_on_the_same_schema() -> None:
    implementation = load_json(SCHEMA_ROOT / "implementation.schema.json")
    assert implementation["properties"]["id"]["$ref"] == "defs.schema.json#/$defs/slug"
    assert implementation["properties"]["kind"]["enum"] == ["integrity", "advisory"]
    for name in ("advisory.json", "battery-thermal.json"):
        assert schema_errors(implementation, load_json(EXAMPLES / "implementation" / name)) == []
    recorded = _recorded()
    battery = load_json(BATTERY / "result.json")
    assert validate_document(recorded) == []
    assert validate_document(battery) == []
    assert recorded["evaluator"]["id"] != battery["evaluator"]["id"]
    notes = (BATTERY / "notes.txt").read_bytes()
    assert battery["advisory"]["details_file"]["sha256"] == hashlib.sha256(notes).hexdigest()
    blob = (RECORDED / "health.json").read_bytes()
    assert recorded["advisory"]["details_file"]["sha256"] == hashlib.sha256(blob).hexdigest()
    tool = json.loads(blob)
    assert tool["evaluator_version"] == "1.1.2"
    assert tool["trial"]["index"] == 1
    assert (
        tool["trial"]["observation_sha256"]
        == recorded["advisory"]["trials"][0]["observation_sha256"]
    )
    for text in (implementation, load_json(SCHEMA_ROOT / "evaluator-result.schema.json")):
        raw = json.dumps(text)
        assert "battery-thermal" not in raw
        assert "health" not in raw.lower()


_CLOSED_READER = (
    "A 1.2 reader that projects known fields ignores the unknown kind. "
    "A 1.2 consumer that validates against the v1.9.1 schema refuses the document "
    "at `evaluator/kind`. Both fail closed."
)
_REPEATED_INDEX_GUIDE = (
    "JSON Schema cannot require unique `index` values when the hashes differ, "
    "so the schema alone accepts a repeated index. `tools/validate_contract.py` refuses it, "
    "and a consumer MUST also refuse it: a loader that validates only against the schema "
    "has to add this check."
)
_REPEATED_INDEX_SCHEMA = (
    "The schema cannot require unique index values; a consumer MUST refuse a repeated index "
    "(tools/validate_contract.py does)."
)


def _assert_closed_reader_sentence() -> None:
    for path in (
        ROOT / "docs" / "advisory.md",
        ROOT / "docs" / "evaluator-descriptor.md",
        SCHEMA_ROOT / "evaluator-result.schema.json",
    ):
        assert _CLOSED_READER in path.read_text(encoding="utf-8"), path
    schema = (SCHEMA_ROOT / "evaluator-result.schema.json").read_text(encoding="utf-8")
    assert schema.count(_CLOSED_READER) >= 2


def test_format_1_2_rejects_the_recorded_advisory_document() -> None:
    _assert_closed_reader_sentence()
    document = _recorded()
    document["format"] = "livingproof-evaluator-result/1.2.0"
    assert _errors(document)
    assert validate_document(document)
    assert consumer_accepts(document) is True
    assert consumer_accepts(_recorded()) is True


def test_the_guide_states_what_advisory_may_not_do() -> None:
    guide = (ROOT / "docs" / "advisory.md").read_text()
    assert "It never grades the robot." in guide
    assert "It never changes Scenario, Run Integrity, or the evidence." in guide
    assert "tier` is `observation`" in guide
    _assert_closed_reader_sentence()
    for path in (
        ROOT / "docs" / "index.md",
        ROOT / "docs" / "manual.md",
        ROOT / "tools" / "manual" / "mkdocs.yml",
        ROOT / "docs" / "implementation-descriptor.md",
        ROOT / "docs" / "evaluator-descriptor.md",
    ):
        assert "advisory.md" in path.read_text()
    banned = (
        SCHEMA_ROOT / "implementation.schema.json",
        SCHEMA_ROOT / "evaluator-result.schema.json",
        SCHEMA_ROOT / "defs.schema.json",
        SCHEMA_ROOT / "evaluator-request.schema.json",
        ROOT / "docs" / "advisory.md",
        ROOT / "docs" / "implementation-descriptor.md",
        ROOT / "docs" / "run-integrity.md",
    )
    for path in banned:
        assert "health" not in path.read_text().lower(), path
    descriptor = (ROOT / "docs" / "evaluator-descriptor.md").read_text()
    assert "for example `1.2.0`" not in descriptor
    assert "`advisory`, at `1.3.0`" in descriptor


def test_html_in_details_is_refused() -> None:
    document = load_json(INVALID / "details-html.json")
    assert _errors(document)[0].startswith("advisory/details:")
    loosened = result_schema()
    loosened["$defs"]["advisory_text"]["pattern"] = "^[\\s\\S]*$"
    assert schema_errors(loosened, document) == []
    blank = _recorded()
    blank["advisory"]["summary"] = "   "
    assert _errors(blank)[0].startswith("advisory/summary:")
    newline = _recorded()
    newline["advisory"]["details"] = "line\nbreak"
    assert _errors(newline) == []


def test_summary_over_400_characters_is_refused() -> None:
    document = load_json(INVALID / "summary-too-long.json")
    assert _errors(document)[0].startswith("advisory/summary:")
    loosened = result_schema()
    del loosened["$defs"]["advisory"]["properties"]["summary"]["maxLength"]
    assert schema_errors(loosened, document) == []


def test_details_over_2000_characters_is_refused() -> None:
    document = _recorded()
    document["advisory"]["details"] = "a" * 2001
    assert _errors(document)[0].startswith("advisory/details:")
    loosened = result_schema()
    del loosened["$defs"]["advisory"]["properties"]["details"]["maxLength"]
    assert schema_errors(loosened, document) == []


def test_details_file_uri_rejects_traversal_and_a_scheme() -> None:
    for name in ("details-file-traversal.json", "details-file-scheme.json"):
        document = load_json(INVALID / name)
        assert _errors(document)[0].startswith("advisory/details_file/uri:")
    loosened = result_schema()
    uri = loosened["$defs"]["advisory"]["properties"]["details_file"]["properties"]["uri"]
    uri["pattern"] = "^[\\s\\S]*$"
    for name in ("details-file-traversal.json", "details-file-scheme.json"):
        assert schema_errors(loosened, load_json(INVALID / name)) == []
    for value in ("notes.json?x=1", "notes.json#part", "/tmp/notes.json", "file:notes.json"):
        document = _recorded()
        document["advisory"]["details_file"]["uri"] = value
        assert _errors(document)[0].startswith("advisory/details_file/uri:"), value


def test_details_file_uri_rejects_more_than_256_characters() -> None:
    document = _recorded()
    document["advisory"]["details_file"]["uri"] = ("a" * 252) + ".json"
    assert len(document["advisory"]["details_file"]["uri"]) == 257
    assert _errors(document)[0].startswith("advisory/details_file/uri:")
    loosened = result_schema()
    del loosened["$defs"]["advisory"]["properties"]["details_file"]["properties"]["uri"][
        "maxLength"
    ]
    assert schema_errors(loosened, document) == []


def test_details_file_sha256_must_be_64_hex_characters() -> None:
    document = load_json(INVALID / "details-file-sha256.json")
    assert _errors(document)[0].startswith("advisory/details_file/sha256:")
    loosened = result_schema()
    loosened["$defs"]["advisory"]["properties"]["details_file"]["properties"]["sha256"] = {
        "type": "string"
    }
    assert schema_errors(loosened, document) == []


def test_advisory_forbids_scenario_and_integrity() -> None:
    scenario = load_json(INVALID / "with-scenario.json")
    integrity = load_json(INVALID / "with-integrity.json")
    assert _errors(scenario)[0].startswith("<root>:")
    assert "trial_id" in _errors(scenario)[0]
    assert "test_system_status" in _errors(integrity)[0]
    without_scenario = result_schema()
    for then in _advisory_thens(without_scenario):
        if then.get("properties", {}).keys() == {"scenario"}:
            then["properties"].pop("scenario")
    assert schema_errors(without_scenario, scenario) == []
    assert schema_errors(without_scenario, integrity)
    without_integrity = result_schema()
    for then in _advisory_thens(without_integrity):
        if then.get("properties", {}).keys() == {"integrity"}:
            then["properties"].pop("integrity")
    assert schema_errors(without_integrity, integrity) == []
    assert schema_errors(without_integrity, scenario)


def test_scenario_and_integrity_forbid_advisory() -> None:
    on_integrity = load_json(INVALID / "integrity-carries-advisory.json")
    on_scenario = load_json(INVALID / "scenario-carries-advisory.json")
    assert _errors(on_integrity)
    assert _errors(on_scenario)
    loosened = result_schema()
    _kind_then(loosened, "integrity")["properties"].pop("advisory")
    assert schema_errors(loosened, on_integrity) == []
    assert schema_errors(loosened, on_scenario)
    other = result_schema()
    _kind_then(other, "scenario")["properties"].pop("advisory")
    assert schema_errors(other, on_scenario) == []
    assert schema_errors(other, on_integrity)


def test_advisory_payload_and_descriptor_are_required() -> None:
    missing_payload = _recorded()
    missing_payload.pop("advisory")
    assert any("advisory" in error for error in _errors(missing_payload))
    missing_descriptor = load_json(INVALID / "missing-descriptor.json")
    assert _errors(missing_descriptor) == ["<root>: 'descriptor' is a required property"]
    loosened = result_schema()
    for then in _advisory_thens(loosened):
        if then.get("required") == ["descriptor"]:
            then.pop("required")
    assert schema_errors(loosened, missing_descriptor) == []
    still_required = result_schema()
    for then in _advisory_thens(still_required):
        if then.get("required") == ["advisory"]:
            then.pop("required")
    assert schema_errors(still_required, missing_payload) == []


def test_descriptor_tier_must_be_observation() -> None:
    document = load_json(INVALID / "tier-not-observation.json")
    assert _errors(document) == ["descriptor/tier: 'observation' was expected"]
    loosened = result_schema()
    for then in _advisory_thens(loosened):
        tier = (
            then.get("properties", {}).get("descriptor", {}).get("properties", {}).get("tier", {})
        )
        tier.pop("const", None)
    assert schema_errors(loosened, document) == []


def test_format_before_1_3_cannot_carry_advisory() -> None:
    document = load_json(INVALID / "format-1-2-0.json")
    assert _errors(document)[0].startswith("format:")
    loosened = result_schema()
    for then in _advisory_thens(loosened):
        then.get("properties", {}).get("format", {}).pop("pattern", None)
    assert schema_errors(loosened, document) == []
    for minor in ("0", "1", "2"):
        older = _recorded()
        older["format"] = f"livingproof-evaluator-result/1.{minor}.0"
        assert _errors(older), minor
    later = _recorded()
    later["format"] = "livingproof-evaluator-result/1.3.1"
    assert _errors(later) == []


def test_advisory_rejects_a_grade_and_trials_bind_a_hash() -> None:
    graded = _recorded()
    graded["advisory"]["grade"] = 1
    assert _errors(graded)[0].startswith("advisory:")
    loosened = result_schema()
    del loosened["$defs"]["advisory"]["additionalProperties"]
    assert schema_errors(loosened, graded) == []
    bad_trial = _recorded()
    bad_trial["advisory"]["trials"][0]["observation_sha256"] = "abcd"
    assert _errors(bad_trial)[0].startswith("advisory/trials/0/observation_sha256:")
    missing = _recorded()
    missing["advisory"]["trials"][0].pop("observation_sha256")
    assert _errors(missing)
    opened = result_schema()
    opened["$defs"]["advisory"]["properties"]["trials"]["items"]["required"].remove(
        "observation_sha256"
    )
    assert schema_errors(opened, missing) == []
    negative = _recorded()
    negative["advisory"]["trials"][0]["index"] = -1
    assert _errors(negative)[0].startswith("advisory/trials/0/index:")


def test_a_request_rejects_kind_advisory() -> None:
    document = load_json(EXAMPLES / "integrity" / "clean" / "request.json")
    document["evaluator"]["kind"] = "advisory"
    assert schema_errors(request_schema(), document) == [
        "evaluator/kind: 'advisory' is not one of ['scenario', 'integrity']"
    ]
    loosened = request_schema()
    loosened["allOf"] = [
        clause
        for clause in loosened["allOf"]
        if clause.get("properties", {})
        .get("evaluator", {})
        .get("properties", {})
        .get("kind", {})
        .get("enum")
        != ["scenario", "integrity"]
    ]
    assert schema_errors(loosened, document) == []


def test_examples_at_v1_9_1_are_unchanged_and_still_validate() -> None:
    r"""Examples published at v1.9.1 (4dc90a9) still match their recorded hashes.

    The manifest is generated once, while that commit is available:

        git ls-tree -r --name-only 4dc90a9 examples | while IFS= read -r path; do
          printf '%s  %s\n' "$(git show "4dc90a9:$path" | sha256sum | awk '{print $1}')" "$path"
        done > tests/data/examples-v1.9.1.sha256
    """
    listed = []
    for line in PUBLISHED.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        listed.append((digest, relative))
    implementation = load_json(SCHEMA_ROOT / "implementation.schema.json")
    binding = load_json(SCHEMA_ROOT / "binding.schema.json")
    vocabulary = load_json(SCHEMA_ROOT / "vocabulary.schema.json")
    valid = invalid = 0
    for digest, relative in listed:
        path = ROOT / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, relative
        if relative.startswith("examples/implementation/invalid/"):
            assert schema_errors(implementation, load_json(path)), relative
            invalid += 1
            continue
        if relative.startswith("examples/implementation/"):
            assert schema_errors(implementation, load_json(path)) == [], relative
        elif relative.endswith(("/request.json", "/result.json")):
            assert validate_document(load_json(path)) == [], relative
        elif relative.startswith("examples/binding/"):
            assert schema_errors(binding, load_json(path)) == [], relative
        elif relative.startswith("examples/vocabulary/"):
            assert schema_errors(vocabulary, load_json(path)) == [], relative
        else:
            raise AssertionError(relative)
        valid += 1
    assert (valid, invalid, len(listed)) == (75, 8, 83)


_SHA = "ab" * 32
_INVISIBLE = (
    "\u200b",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2060",
    "\u2061",
    "\u2062",
    "\u2063",
    "\u2064",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
)


def _summary(text: str) -> dict:
    document = _recorded()
    document["advisory"]["summary"] = text
    return document


def _assert_summary_refused(text: str) -> None:
    assert _errors(_summary(text))[0].startswith("advisory/summary:"), repr(text)


def test_plain_text_refuses_a_trailing_newline() -> None:
    assert _errors(_summary("abc")) == []
    _assert_summary_refused("abc\n")


def test_plain_text_refuses_each_angle_bracket_alone() -> None:
    assert _errors(_summary("a&b")) == []
    _assert_summary_refused("a<b")
    _assert_summary_refused("a>b")


def test_plain_text_refuses_c0_controls_other_than_lf() -> None:
    assert _errors(_summary("abc")) == []
    for control in ("\x00", "\t", "\r"):
        _assert_summary_refused(f"a{control}b")


def test_plain_text_refuses_del_and_c1() -> None:
    assert _errors(_summary("abc")) == []
    for control in ("\u007f", "\u0085", "\u009f"):
        _assert_summary_refused(f"a{control}b")


def test_plain_text_refuses_line_separators() -> None:
    assert _errors(_summary("abc")) == []
    _assert_summary_refused("a\u2028b")
    _assert_summary_refused("a\u2029b")


def test_summary_of_only_bom_is_refused() -> None:
    _assert_summary_refused("\ufeff")
    _assert_summary_refused("a\ufeffb")


def test_plain_text_refuses_invisible_and_bidi_controls() -> None:
    assert _errors(_summary("abc")) == []
    for character in _INVISIBLE:
        _assert_summary_refused(character)
        _assert_summary_refused(f"a{character}b")


def test_plain_text_refuses_mongolian_vowel_separator_and_a_lone_surrogate() -> None:
    _assert_summary_refused("\u180e")
    _assert_summary_refused("ab\ud800c")
    _assert_summary_refused("ab\udc00c")
    emoji = "😀" * 400
    assert len(emoji) == 400
    assert _errors(_summary(emoji)) == []
    _assert_summary_refused("😀" * 401)


def test_advisory_text_allows_joiners_inside_real_text() -> None:
    guide = (ROOT / "docs" / "advisory.md").read_text(encoding="utf-8")
    assert "Anything valid here also passes the Reporter's presentation check." in guide
    assert "U+200D" in guide and "U+200C" in guide
    for text in (
        "👩‍💻",
        "🏳️‍🌈",
        "می‌خواهم",
        "漢字のテスト",
        "مرحبا",
        "שלום",
        "e\u0301",
        "a\u200db",
        "a\u200cb",
    ):
        assert _errors(_summary(text)) == [], text
    details = _recorded()
    details["advisory"]["details"] = "\nThe observation is on the second line."
    assert _errors(details) == []


def test_advisory_text_refuses_a_value_made_only_of_joiners() -> None:
    _assert_summary_refused("\u200d")
    _assert_summary_refused("\u200c")
    _assert_summary_refused(" \u200d ")


def test_summary_and_details_accept_their_exact_limits() -> None:
    summary = _summary("a" * 400)
    assert len(summary["advisory"]["summary"]) == 400
    assert _errors(summary) == []
    _assert_summary_refused("a" * 401)
    details = _recorded()
    details["advisory"]["details"] = "b" * 2000
    assert _errors(details) == []
    details["advisory"]["details"] = "b" * 2001
    assert _errors(details)[0].startswith("advisory/details:")


def test_details_file_requires_both_fields_and_rejects_an_extra_key() -> None:
    present = _recorded()
    assert _errors(present) == []
    missing_hash = _recorded()
    del missing_hash["advisory"]["details_file"]["sha256"]
    assert _errors(missing_hash)[0].startswith("advisory/details_file:")
    missing_uri = _recorded()
    del missing_uri["advisory"]["details_file"]["uri"]
    assert _errors(missing_uri)[0].startswith("advisory/details_file:")
    extra = _recorded()
    extra["advisory"]["details_file"]["note"] = "x"
    assert _errors(extra)[0].startswith("advisory/details_file:")


def test_details_file_uri_rejects_a_trailing_newline_and_other_extensions() -> None:
    for uri in ("record.json", "record.txt", "dir/record.json"):
        document = _recorded()
        document["advisory"]["details_file"]["uri"] = uri
        assert _errors(document) == [], uri
    for uri in ("a.json\n", "a.JSON", "a.yaml", "a.json.exe"):
        document = _recorded()
        document["advisory"]["details_file"]["uri"] = uri
        assert _errors(document)[0].startswith("advisory/details_file/uri:"), repr(uri)


def test_trial_items_reject_an_extra_key_and_require_an_integer_index() -> None:
    valid = _recorded()
    assert _errors(valid) == []
    extra = _recorded()
    extra["advisory"]["trials"][0]["note"] = "x"
    assert _errors(extra)[0].startswith("advisory/trials/0:")
    missing = _recorded()
    del missing["advisory"]["trials"][0]["index"]
    assert _errors(missing)
    fractional = _recorded()
    fractional["advisory"]["trials"][0]["index"] = 1.5
    assert _errors(fractional)[0].startswith("advisory/trials/0/index:")
    text = _recorded()
    text["advisory"]["trials"][0]["index"] = "1"
    assert _errors(text)[0].startswith("advisory/trials/0/index:")


def test_advisory_summary_and_details_are_each_required() -> None:
    assert _errors(_recorded()) == []
    missing_summary = _recorded()
    del missing_summary["advisory"]["summary"]
    assert any("summary" in error for error in _errors(missing_summary))
    missing_details = _recorded()
    del missing_details["advisory"]["details"]
    assert any("details" in error for error in _errors(missing_details))


def test_advisory_result_format_accepts_later_minors_and_refuses_a_trailing_newline() -> None:
    for version in ("1.3.0", "1.4.0", "1.10.0"):
        document = _recorded()
        document["format"] = f"livingproof-evaluator-result/{version}"
        assert _errors(document) == [], version
    newline = _recorded()
    newline["format"] = "livingproof-evaluator-result/1.3.0\n"
    assert _errors(newline)[0].startswith("format:")


def test_trials_when_present_have_at_least_one_entry() -> None:
    omitted = _recorded()
    del omitted["advisory"]["trials"]
    assert _errors(omitted) == []
    empty = _recorded()
    empty["advisory"]["trials"] = []
    assert _errors(empty)[0].startswith("advisory/trials:")


def test_trials_reject_a_duplicate_entry() -> None:
    document = _recorded()
    document["advisory"]["trials"] = [
        document["advisory"]["trials"][0],
        dict(document["advisory"]["trials"][0]),
    ]
    assert _errors(document)[0].startswith("advisory/trials:")
    distinct = _recorded()
    second = dict(distinct["advisory"]["trials"][0])
    second["index"] = 2
    second["observation_sha256"] = _SHA
    distinct["advisory"]["trials"].append(second)
    assert _errors(distinct) == []


def _with_indexes(*indexes: object) -> dict:
    document = _recorded()
    document["advisory"]["trials"] = [
        {"index": index, "observation_sha256": f"{position:064x}"}
        for position, index in enumerate(indexes)
    ]
    return document


def test_trials_reject_a_duplicate_index() -> None:
    document = _recorded()
    second = dict(document["advisory"]["trials"][0])
    second["observation_sha256"] = _SHA
    document["advisory"]["trials"].append(second)
    assert _errors(document) == []
    errors = validate_document(document)
    assert errors == ["advisory/trials/1/index: repeats advisory/trials/0/index"]
    repeated = _with_indexes(1, 2, 1)
    assert validate_document(repeated) == [
        "advisory/trials/2/index: repeats advisory/trials/0/index"
    ]
    whole_float = _with_indexes(1, 1.0)
    assert validate_document(whole_float) == [
        "advisory/trials/1/index: repeats advisory/trials/0/index"
    ]


def test_advisory_guide_refuses_duplicate_json_keys() -> None:
    text = (ROOT / "docs" / "advisory.md").read_text(encoding="utf-8")
    assert "A consumer MUST refuse a document with duplicate JSON object keys." in text


def test_the_repeated_index_limit_is_stated_for_schema_only_consumers() -> None:
    guide = (ROOT / "docs" / "advisory.md").read_text(encoding="utf-8")
    schema = (SCHEMA_ROOT / "evaluator-result.schema.json").read_text(encoding="utf-8")
    assert _REPEATED_INDEX_GUIDE in guide
    assert _REPEATED_INDEX_SCHEMA in schema


def _advisory_fixtures() -> list:
    found = []
    for path in sorted((EXAMPLES / "advisory").rglob("*.json")):
        document = load_json(path)
        if isinstance(document, dict) and str(document.get("format", "")).startswith(
            "livingproof-evaluator-"
        ):
            found.append(path)
    found.extend(
        [
            EXAMPLES / "implementation" / "advisory.json",
            EXAMPLES / "implementation" / "battery-thermal.json",
            EXAMPLES / "implementation" / "invalid" / "advisory-grading.json",
            EXAMPLES / "implementation" / "invalid" / "advisory-result-minor.json",
        ]
    )
    return found


def _ajv_accepts(path) -> bool:
    completed = subprocess.run(
        ["node", str(ROOT / "tools" / "ajv" / "validate.mjs"), str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode not in (0, 1):
        raise AssertionError(completed.stderr or completed.stdout)
    return completed.returncode == 0


def _python_and_ajv_agree(document: dict, label: str) -> None:
    python_accepts = schema_errors(_schema_for(document), document) == []
    path = ROOT / "artifacts" / "ajv-parity.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    assert python_accepts == _ajv_accepts(path), label


def test_python_and_ajv_agree_on_advisory_fixtures() -> None:
    for path in _advisory_fixtures():
        _python_and_ajv_agree(load_json(path), str(path))
    _python_and_ajv_agree(_summary("\u180e"), "U+180E")
    _python_and_ajv_agree(_summary("ab\ud800c"), "lone high surrogate")
    _python_and_ajv_agree(_summary("ab\udc00c"), "lone low surrogate")
    _python_and_ajv_agree(_summary("😀" * 400), "400 astral emoji")
    _python_and_ajv_agree(_summary("\ufeff"), "U+FEFF only")
    for label, text in (
        ("woman technologist", "👩‍💻"),
        ("rainbow flag", "🏳️‍🌈"),
        ("Persian", "می‌خواهم"),
        ("CJK", "漢字のテスト"),
        ("Arabic", "مرحبا"),
        ("Hebrew", "שלום"),
        ("combining mark", "e\u0301"),
        ("ZWJ only", "\u200d"),
        ("ZWNJ only", "\u200c"),
        ("ZWJ and spaces", " \u200d "),
    ):
        _python_and_ajv_agree(_summary(text), label)
    multiline = _recorded()
    multiline["advisory"]["details"] = "\nThe observation is on the second line."
    _python_and_ajv_agree(multiline, "multi-line details")


def _schema_for(document: dict) -> dict:
    if str(document.get("format", "")).startswith("livingproof-evaluator-implementation/"):
        return load_json(SCHEMA_ROOT / "implementation.schema.json")
    return result_schema()
