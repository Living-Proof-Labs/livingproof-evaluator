# SPDX-License-Identifier: Apache-2.0
"""Hand checks for the hallway vocabulary's repository-local sources (verification of PR 52).

A source that names a file in this repository must name one that exists, and the steps it
names must be steps of that file. Every term in the fixture must also be used by the example
the sources point at, and ids must be unique (the schema alone does not enforce that).
"""

from __future__ import annotations

import re

from support import ROOT, load_json

FIXTURE = ROOT / "examples" / "vocabulary" / "hallway" / "vocabulary.json"


def _terms() -> list[dict]:
    return load_json(FIXTURE)["terms"]


def test_local_sources_name_files_that_exist() -> None:
    for term in _terms():
        for source in term["sources"]:
            match = re.match(r"(examples/[\w./-]+\.json)\b", source)
            if match:
                assert (ROOT / match.group(1)).is_file(), (term["id"], source)


def test_steps_named_in_a_local_source_are_steps_of_that_request() -> None:
    for term in _terms():
        for source in term["sources"]:
            match = re.match(r"(examples/[\w./-]+\.json): steps? (.+)$", source)
            if not match:
                continue
            request = load_json(ROOT / match.group(1))
            steps = {s["id"]: s for s in request["scenario"]["scenario"]["steps"]}
            named = re.findall(r"[a-z]+(?:-[a-z]+)+", match.group(2))
            assert named, (term["id"], source)
            for step_id in named:
                assert step_id in steps, (term["id"], step_id)
                assert steps[step_id]["observable"] == term["id"], (term["id"], step_id)


def test_term_ids_are_unique() -> None:
    ids = [term["id"] for term in _terms()]
    assert len(ids) == len(set(ids))
    names = [term["name"] for term in _terms()]
    assert len(names) == len(set(names))
