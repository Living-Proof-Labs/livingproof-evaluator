# SPDX-License-Identifier: Apache-2.0
"""Loaders for the evaluator contract fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schema"
EXAMPLES = ROOT / "examples"
REGISTRY_PATH = SCHEMA_ROOT / "integrity" / "checks" / "registry.json"

ROBOT_KEYS = {
    "verdict",
    "grade",
    "pass",
    "fail",
    "passed",
    "failed",
    "total",
    "count",
    "counts",
    "required_passes",
    "fraction",
    "ratio",
    "pass_count",
    "fail_count",
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def schema_registry() -> Registry:
    resources = []
    for path in SCHEMA_ROOT.rglob("*.schema.json"):
        contents = json.loads(path.read_text())
        resources.append((contents["$id"], Resource.from_contents(contents)))
    return Registry().with_resources(resources)


def validator_for(schema: dict) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=schema_registry())


def schema_errors(schema: dict, instance: object) -> list[str]:
    errors = sorted(
        validator_for(schema).iter_errors(instance),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    ]


def assert_valid(schema: dict, instance: object) -> None:
    errors = schema_errors(schema, instance)
    if errors:
        raise AssertionError("\n".join(errors))


def assert_invalid(schema: dict, instance: object) -> None:
    if not schema_errors(schema, instance):
        raise AssertionError("document validated and should have been rejected")


def request_schema() -> dict:
    return load_json(SCHEMA_ROOT / "evaluator-request.schema.json")


def result_schema() -> dict:
    return load_json(SCHEMA_ROOT / "evaluator-result.schema.json")


def check_registry() -> list[dict]:
    document = load_json(REGISTRY_PATH)
    return document["checks"]


def example_dirs() -> list[Path]:
    return sorted(path.parent for path in EXAMPLES.rglob("request.json"))


def walk_keys(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        found.extend(value)
        for child in value.values():
            found.extend(walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_keys(child))
    return found


def walk_strings(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            found.extend(walk_strings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_strings(child))
    return found
