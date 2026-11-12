# SPDX-License-Identifier: Apache-2.0
"""Validate an evaluator request or result.

The envelope schema checks the shared fields, rejects unknown check ids, and
rejects verdict-like finding categories. Each integrity check is then validated
against the schema named in schema/integrity/checks/registry.json. A consumer of
major version 1 also accepts a later 1.minor document by ignoring an unknown
kind and unknown fields.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import support as contract

FORMAT = re.compile(r"^livingproof-evaluator-(request|result)/1\.(\d+)\.\d+$")
KNOWN_KINDS = {"scenario", "integrity"}
RESULT_KEYS = {"format", "evaluator", "inputs", "timestamps", "scenario", "integrity"}
REQUEST_KEYS = RESULT_KEYS
EVALUATOR_KEYS = {"id", "version", "kind", "execution", "display_name", "publisher", "icon"}


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
    return errors


def _project(value: object, allowed: set[str]) -> object:
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if key in allowed}


def consumer_accepts(document: dict) -> bool:
    """A major-1 consumer accepts any 1.minor and ignores unknown kinds and fields.

    The boolean success field is unchanged: it is a test-system flag, not a
    verdict word. Unknown properties are dropped before the 1.0 schema runs.
    An unknown kind is ignored instead of rejected, which is how health and
    observations can arrive as a later 1.minor without breaking a 1.0 reader.
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
