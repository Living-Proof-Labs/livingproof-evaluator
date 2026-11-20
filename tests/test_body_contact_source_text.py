# SPDX-License-Identifier: Apache-2.0
"""The prose that cites the merged example must say what the example says (Vera, verification).

The merged example binds body_contact on /wall_contacts. The vocabulary's source line and the
docs that quote it must not still call the term unbound, which a mutation of PR 56 left alive.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MERGED = "examples/binding/merged/unitree-g1-stock-livingproof-sim-mujoco.json"


def test_the_sources_that_cite_the_merged_example_say_body_contact_is_bound() -> None:
    merged = json.loads((ROOT / MERGED).read_text())
    assert "body_contact" in merged["bound_observables"] and merged["unbound"] == []
    vocabulary = json.loads((ROOT / "examples/vocabulary/hallway/vocabulary.json").read_text())
    term = next(t for t in vocabulary["terms"] if t["id"] == "body_contact")
    cited = [s for s in term["sources"] if s.startswith(MERGED)]
    assert len(cited) == 1
    assert "/wall_contacts" in cited[0] and "unbound" not in cited[0], cited[0]
    docs = " ".join((ROOT / "docs/observable-vocabulary.md").read_text().split())
    line = next(s for s in docs.split("- ") if s.startswith(MERGED))
    assert "/wall_contacts" in line and "unbound" not in line, line
