# SPDX-License-Identifier: Apache-2.0
"""Validate an evaluator request or result.

The envelope schema checks the shared fields, rejects unknown check ids, and
rejects verdict-like finding categories. Each integrity check is then validated
against the schema named in schema/integrity/checks/registry.json. A 1.1 result
may carry a descriptor. Strict validation applies that schema and the SVG
subset. On a 1.1 or later result, an omitted descriptor title makes
display_name and publisher follow the descriptor plain-text pattern.
A consumer of major version 1 also accepts a later 1.minor document by
ignoring an unknown kind and unknown fields, including the descriptor.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import support as contract

FORMAT = re.compile(r"^livingproof-evaluator-(request|result)/1\.(\d+)\.\d+$")
KNOWN_KINDS = {"scenario", "integrity"}
RESULT_KEYS = {"format", "evaluator", "inputs", "timestamps", "scenario", "integrity"}
REQUEST_KEYS = RESULT_KEYS
EVALUATOR_KEYS = {"id", "version", "kind", "execution", "display_name", "publisher", "icon"}
# descriptor is a 1.1 field. It stays out of RESULT_KEYS so a 1.0 consumer drops it.
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
CHILD_ELEMENTS = {"path", "circle", "rect", "line", "polyline", "polygon", "g"}
ALLOWED_PAINT = {"currentColor", "none", "transparent"}
ICON_MAX_BYTES = 8192
_EXTERNAL_VALUE = re.compile(r"(?i)(?:url\s*\(|javascript:|data:|https?:|file:|blob:)")
_LATER_RESULT = re.compile(r"^livingproof-evaluator-result/1\.[1-9][0-9]*\.(?:0|[1-9][0-9]*)$")
_PLAIN = re.compile(
    json.loads((ROOT / "schema" / "descriptor.schema.json").read_text())["$defs"]["plain"][
        "pattern"
    ]
)


def _errors(schema: dict, instance: object) -> list[str]:
    return contract.schema_errors(schema, instance)


def dispatch_checks(document: dict) -> list[str]:
    """Apply each integrity check's registry schema. Unknown ids are errors."""
    if document.get("evaluator", {}).get("kind") != "integrity":
        return []
    payload = document.get("integrity")
    if not isinstance(payload, dict):
        return []
    registry = {entry["id"]: entry for entry in contract.check_registry()}
    errors: list[str] = []
    for index, check in enumerate(payload.get("checks") or []):
        if not isinstance(check, dict):
            continue
        entry = registry.get(check.get("id"))
        if entry is None:
            errors.append(f"checks/{index}: id {check.get('id')!r} is not in the registry")
            continue
        if check.get("version") != entry["version"]:
            errors.append(
                f"checks/{index}: version {check.get('version')!r} does not match {entry['version']}"
            )
        schema = contract.load_json(ROOT / entry["schema"])
        errors.extend(f"checks/{index}: {item}" for item in _errors(schema, check))
    return errors


def validate_document(document: dict) -> list[str]:
    """Envelope schema plus registry dispatch. Empty means the document is valid."""
    kind = document.get("format", "")
    schema = (
        contract.request_schema()
        if str(kind).endswith("request/1.0.0") or (isinstance(kind, str) and "request/" in kind)
        else contract.result_schema()
    )
    if isinstance(document.get("format"), str) and "request/" in document["format"]:
        schema = contract.request_schema()
    elif isinstance(document.get("format"), str) and "result/" in document["format"]:
        schema = contract.result_schema()
    errors = _errors(schema, document)
    if document.get("evaluator", {}).get("kind") == "integrity" and "result/" in str(
        document.get("format")
    ):
        errors.extend(dispatch_checks(document))
    if _LATER_RESULT.fullmatch(str(document.get("format", ""))):
        errors.extend(_omitted_title_plain_text_errors(document))
    if isinstance(document, dict) and "descriptor" in document:
        errors.extend(descriptor_errors(document))
    return errors


def _omitted_title_plain_text_errors(document: dict) -> list[str]:
    """A later result with no descriptor title renders display_name, so both names are plain text."""
    descriptor = document.get("descriptor")
    if isinstance(descriptor, dict) and "title" in descriptor:
        return []
    evaluator = document.get("evaluator")
    if not isinstance(evaluator, dict):
        return []
    errors: list[str] = []
    for field in ("display_name", "publisher"):
        value = evaluator.get(field)
        if isinstance(value, str) and _PLAIN.search(value) is None:
            errors.append(
                f"evaluator/{field}: must be plain text with a visible character, "
                "without markup or controls, because descriptor.title is omitted"
            )
    return errors


def _local(name: str) -> str:
    if name.startswith("{"):
        return name.split("}", 1)[1]
    return name


def _namespace(name: str) -> str | None:
    if name.startswith("{") and "}" in name:
        return name[1:].split("}", 1)[0]
    return None


def _short_title_error(title: str, short_title: str) -> str | None:
    """short_title must be the same name, with words shortened, not replaced."""
    if short_title == title:
        return None
    title_words = title.split()
    short_words = short_title.split()
    if len(short_words) != len(title_words) or not short_words:
        return "must keep every word of the title so it stays the same name, not a different label"
    for index, (short_word, title_word) in enumerate(zip(short_words, title_words, strict=True)):
        if not short_word or not title_word.startswith(short_word):
            return (
                f"word {index + 1} must be the start of {title_word!r} "
                "so the short title stays the same name"
            )
    return None


def svg_subset_errors(icon: str) -> list[str]:
    """Return why an icon is outside the descriptor SVG subset. Empty means it is inside."""
    if not isinstance(icon, str):
        return ["must be a string"]
    size = len(icon.encode("utf-8"))
    if size > ICON_MAX_BYTES:
        return [f"is {size} UTF-8 bytes, and the cap is {ICON_MAX_BYTES}"]
    if not icon.strip():
        return ["is empty"]
    lowered = icon.lower()
    if "<?" in icon:
        return ["contains a processing instruction"]
    if "<![cdata[" in lowered:
        return ["contains CDATA"]
    if "<!--" in icon:
        return ["contains a comment"]
    if "<!" in icon:
        return ["contains a declaration"]
    if "&" in icon:
        return ["contains an entity reference"]
    try:
        root = fromstring(icon)
    except DefusedXmlException as exc:
        return [f"was rejected while parsing ({exc.__class__.__name__})"]
    except ParseError as exc:
        return [f"is not well-formed XML ({exc})"]
    errors: list[str] = []
    _walk_svg(root, errors, root=True)
    return errors


def _walk_svg(element, errors: list[str], *, root: bool) -> None:
    name = _local(element.tag)
    namespace = _namespace(element.tag)
    if namespace not in (None, SVG_NAMESPACE):
        errors.append(f"{name} is not in the SVG namespace")
    if root:
        if name != "svg":
            errors.append(f"root is {name!r}, and the root must be svg")
        if not any(_local(key) == "viewBox" for key in element.attrib):
            errors.append("is missing viewBox")
    elif name not in CHILD_ELEMENTS:
        errors.append(
            f"has an element {name!r}, and the allowed elements are "
            "path, circle, rect, line, polyline, polygon, and g"
        )
    errors.extend(_attribute_errors(name, element.attrib))
    if element.text and element.text.strip():
        errors.append(f"{name} has text content")
    if element.tail and element.tail.strip():
        errors.append(f"{name} has trailing text")
    for child in list(element):
        _walk_svg(child, errors, root=False)


def _attribute_errors(element_name: str, attrib: dict) -> list[str]:
    errors: list[str] = []
    for raw_name, value in attrib.items():
        name = _local(raw_name)
        lowered = name.lower()
        if lowered == "xmlns" or raw_name.startswith("{http://www.w3.org/2000/xmlns/}"):
            continue
        if lowered.startswith("on"):
            errors.append(f"{element_name} has an event attribute {name}")
            continue
        if lowered in {"href", "src", "srcset"}:
            errors.append(f"{element_name} has an external reference {name}")
            continue
        if lowered == "style":
            errors.append(f"{element_name} has a style attribute")
            continue
        if _EXTERNAL_VALUE.search(value):
            errors.append(f"{element_name} {name} contains an external reference")
            continue
        if lowered in {"fill", "stroke"} and value not in ALLOWED_PAINT:
            errors.append(
                f"{element_name} {lowered} is {value!r}, and it must be "
                "currentColor, none, or transparent"
            )
    return errors


def descriptor_errors(document: dict) -> list[str]:
    """Cross-field descriptor rules the schema cannot see, including the SVG subset."""
    descriptor = document.get("descriptor")
    if not isinstance(descriptor, dict):
        return []
    evaluator = document.get("evaluator")
    if not isinstance(evaluator, dict):
        evaluator = {}
    errors: list[str] = []
    display_name = evaluator.get("display_name")
    title = descriptor.get("title")
    if isinstance(title, str) and isinstance(display_name, str) and title != display_name:
        errors.append("descriptor/title: must equal evaluator.display_name")
    name = title if isinstance(title, str) else display_name
    short_title = descriptor.get("short_title")
    if isinstance(short_title, str) and isinstance(name, str):
        message = _short_title_error(name, short_title)
        if message:
            errors.append(f"descriptor/short_title: {message}")
    version = descriptor.get("version")
    evaluator_version = evaluator.get("version")
    if (
        isinstance(version, str)
        and isinstance(evaluator_version, str)
        and version != evaluator_version
    ):
        errors.append("descriptor/version: must equal evaluator.version")
    grade = descriptor.get("grade")
    if isinstance(grade, float):
        errors.append("descriptor/grade: must be an integer, not a fractional token")
    findings = descriptor.get("findings")
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            if isinstance(finding, dict) and isinstance(finding.get("trial"), float):
                errors.append(
                    f"descriptor/findings/{index}/trial: must be an integer or text, "
                    "not a fractional token"
                )
    if "icon" in descriptor:
        icon = descriptor.get("icon")
        if not isinstance(icon, str):
            errors.append("descriptor/icon: must be a string")
        else:
            errors.extend(f"descriptor/icon: {item}" for item in svg_subset_errors(icon))
            evaluator_icon = evaluator.get("icon")
            if isinstance(evaluator_icon, str) and icon != evaluator_icon:
                errors.append("descriptor/icon: must equal evaluator.icon")
    return errors


def _project(value: object, allowed: set[str]) -> object:
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if key in allowed}


def consumer_accepts(document: dict) -> bool:
    """A major-1 consumer accepts any 1.minor and ignores unknown kinds and fields.

    The boolean success field is unchanged: it is a test-system flag, not a
    verdict word. Unknown properties are dropped before the 1.0 schema runs.
    descriptor is one of those properties: it is not in RESULT_KEYS, so a 1.0
    reader never sees it and does not apply the SVG subset. An unknown kind is
    ignored instead of rejected, which is how a later kind can arrive as a
    later 1.minor without breaking a 1.0 reader.
    """
    match = FORMAT.fullmatch(str(document.get("format", "")))
    if match is None:
        return False
    message = match.group(1)
    evaluator = document.get("evaluator")
    if not isinstance(evaluator, dict):
        return False
    kind = evaluator.get("kind")
    projected_evaluator = _project(evaluator, EVALUATOR_KEYS)
    if kind not in KNOWN_KINDS:
        projected_evaluator = dict(projected_evaluator)
        projected_evaluator["kind"] = "integrity"
        shell = {
            "format": f"livingproof-evaluator-{message}/1.0.0",
            "evaluator": projected_evaluator,
            "inputs": document.get("inputs"),
            "timestamps": document.get("timestamps"),
        }
        if message == "result":
            shell["integrity"] = {
                "run": {
                    "id": "ignored-kind",
                    "test_system_status": "COMPLETED",
                    "success": True,
                    "percentage": 100,
                },
                "trials": [
                    {
                        "id": "ignored",
                        "test_system_status": "COMPLETED",
                        "success": True,
                        "percentage": 100,
                    }
                ],
                "checks": [
                    {
                        "id": "completeness",
                        "version": "1.0.0",
                        "applicable": True,
                        "success": True,
                        "percentage": 100,
                        "findings": [],
                    }
                ],
            }
        else:
            return _errors(
                contract.request_schema(),
                {
                    "format": "livingproof-evaluator-request/1.0.0",
                    "evaluator": projected_evaluator,
                    "inputs": document.get("inputs"),
                    "timestamps": document.get("timestamps"),
                    "integrity": {
                        "manifest": {
                            "id": "ignored-kind",
                            "deterministic": True,
                            "pins": {
                                name: {"sha256": "ab" * 32}
                                for name in (
                                    "specs",
                                    "runner",
                                    "verifier",
                                    "world",
                                    "configuration",
                                )
                            },
                            "planned_trials": [{"id": "ignored"}],
                        },
                        "lock": {
                            "pins": {
                                name: {"sha256": "ab" * 32}
                                for name in (
                                    "specs",
                                    "runner",
                                    "verifier",
                                    "world",
                                    "configuration",
                                )
                            }
                        },
                        "trials": [],
                    },
                },
            ) == [] and isinstance(document.get("inputs"), list)
        return _errors(contract.result_schema(), shell) == []

    allowed = RESULT_KEYS if message == "result" else REQUEST_KEYS
    projected = _project(document, allowed)
    projected["format"] = f"livingproof-evaluator-{message}/1.0.0"
    projected["evaluator"] = projected_evaluator
    return validate_document(projected) == []


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_contract.py <request-or-result.json>", file=sys.stderr)
        return 2
    document = json.loads(Path(argv[1]).read_text())
    errors = validate_document(document)
    if errors:
        print("\n".join(errors))
        return 1
    print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
