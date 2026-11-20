# SPDX-License-Identifier: Apache-2.0
"""The binding schema rejects bad robot and producer bindings, not only merged ones (issue 3).

test_binding.py mutates the merged example. A robot or producer binding with an unknown term, a
missing nominal source or unit, a missing channel field or an extra entry is rejected by the same
schema; this pins that for those two kinds. The xfail cases are gaps the schema and merge rules
do not close yet: a unit that disagrees with the vocabulary, a frame that is not the vocabulary's,
a base without its y field, and a nominal on a term whose nominal never applies. Each is strict:
it starts passing when the gap is closed, and then the marker must go.
"""

from __future__ import annotations

import copy

import pytest

from binding_rules import merged_problems
from support import EXAMPLES, SCHEMA_ROOT, assert_invalid, load_json

SCHEMA = load_json(SCHEMA_ROOT / "binding.schema.json")
DIR = EXAMPLES / "binding"
VOCABULARY = load_json(EXAMPLES / "vocabulary" / "hallway" / "vocabulary.json")
ROBOT = load_json(DIR / "robot" / "unitree-g1-stock.json")
PRODUCER = load_json(DIR / "producer" / "livingproof-sim-mujoco.json")
MERGED = load_json(DIR / "merged" / "unitree-g1-stock-livingproof-sim-mujoco.json")


def _nominal(d):
    return d["observables"]["base_height"]["nominal"]


ROBOT_BAD = {
    "unknown term": lambda d: d["observables"].update(feet={"body": "left_ankle_link"}),
    "no observables": lambda d: d.update(observables={}),
    "empty entry": lambda d: d["observables"].update(base={}),
    "nominal unit missing": lambda d: _nominal(d).pop("unit"),
    "nominal source missing": lambda d: _nominal(d).pop("source"),
    "nominal value not a number": lambda d: _nominal(d).update(value="0.78"),
    "nominal value zero": lambda d: _nominal(d).update(value=0),
    "blank body": lambda d: d["observables"]["base"].update(body=" "),
    "a producer-owned key": lambda d: d["observables"]["base"].update(topic="/base_pose"),
}
PRODUCER_BAD = {
    "unknown term": lambda d: d["observables"].update(tail=copy.deepcopy(d["observables"]["base"])),
    "topic missing": lambda d: d["observables"]["base"].pop("topic"),
    "encoding missing": lambda d: d["observables"]["base"].pop("encoding"),
    "schema missing": lambda d: d["observables"]["base"].pop("schema"),
    "fields missing": lambda d: d["observables"]["base"].pop("fields"),
    "frame missing": lambda d: d["observables"]["base"].pop("frame"),
    "blank topic": lambda d: d["observables"]["base"].update(topic="  "),
    "field name not a value name": lambda d: d["observables"]["base"]["fields"].update(X="a.b"),
    "a robot-owned key": lambda d: d["observables"]["base"].update(body="pelvis"),
}


@pytest.mark.parametrize("name", ROBOT_BAD)
def test_the_schema_rejects_a_bad_robot_binding(name: str) -> None:
    broken = copy.deepcopy(ROBOT)
    ROBOT_BAD[name](broken)
    assert_invalid(SCHEMA, broken)


@pytest.mark.parametrize("name", PRODUCER_BAD)
def test_the_schema_rejects_a_bad_producer_binding(name: str) -> None:
    broken = copy.deepcopy(PRODUCER)
    PRODUCER_BAD[name](broken)
    assert_invalid(SCHEMA, broken)


GAPS = {
    "nominal unit that is not meters": lambda d: _nominal(d).update(unit="kg"),
    "frame that is not the vocabulary's world": lambda d: d["observables"]["base"].update(
        frame="map"
    ),
    "base without its y field": lambda d: d["observables"]["base"]["fields"].pop("y"),
    "base_height without its z field": lambda d: d["observables"]["base_height"].update(
        fields={"w": "pose.position.z"}
    ),
}


@pytest.mark.xfail(strict=True, reason="neither the schema nor the merge rules check these yet")
@pytest.mark.parametrize("name", GAPS)
def test_a_merged_binding_that_contradicts_its_term_is_rejected(name: str) -> None:
    broken = copy.deepcopy(MERGED)
    GAPS[name](broken)
    try:
        assert_invalid(SCHEMA, broken)
    except AssertionError:
        assert merged_problems(broken, VOCABULARY), "the merge rules must reject it"


@pytest.mark.xfail(
    strict=True, reason="a robot binding may carry a nominal for a term that has none"
)
def test_a_robot_binding_rejects_a_nominal_on_a_term_whose_nominal_never_applies() -> None:
    broken = copy.deepcopy(ROBOT)
    broken["observables"]["base"]["nominal"] = {"value": 1, "unit": "m", "source": "x"}
    assert_invalid(SCHEMA, broken)
