# SPDX-License-Identifier: Apache-2.0
"""The compatibility note says a new run status reads as not graded (#38)."""

from __future__ import annotations

from support import ROOT, result_schema

NOTE = (
    "A 1.x minor version may add run statuses, and a consumer must treat any run "
    "status it does not recognise as not graded."
)


def test_schema_format_description_has_the_note() -> None:
    description = result_schema()["properties"]["format"]["description"]
    assert NOTE in description
    assert "accepts any 1.minor document" in description


def test_migration_note_has_the_same_wording() -> None:
    text = (ROOT / "docs" / "run-integrity.md").read_text(encoding="utf-8")
    assert NOTE in text
