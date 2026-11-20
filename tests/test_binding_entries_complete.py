# SPDX-License-Identifier: Apache-2.0
"""Every channel entry of every bound term is closed and complete, in producer and merged bindings.

The schema describes each term's entry separately (base, base_height), in the producer and the
merged binding. test_binding_rejections.py drops keys from `base` in the producer binding; this
covers the other entries: each required key missing, and an extra key, for both terms and both
kinds, plus the robot base_height entry (`nominal` required, no other key).
"""

from __future__ import annotations

import copy

import pytest

from support import EXAMPLES, SCHEMA_ROOT, assert_invalid, load_json

SCHEMA = load_json(SCHEMA_ROOT / "binding.schema.json")
DIR = EXAMPLES / "binding"
ROBOT = load_json(DIR / "robot" / "unitree-g1-stock.json")
PRODUCER = load_json(DIR / "producer" / "livingproof-sim-mujoco.json")
MERGED = load_json(DIR / "merged" / "unitree-g1-stock-livingproof-sim-mujoco.json")
CHANNEL_KEYS = ["topic", "encoding", "schema", "fields", "frame"]
CASES = [(kind, term) for kind in ("producer", "merged") for term in ("base", "base_height")]


def _binding(kind: str) -> dict:
    return copy.deepcopy({"producer": PRODUCER, "merged": MERGED}[kind])


@pytest.mark.parametrize("key", CHANNEL_KEYS)
@pytest.mark.parametrize(("kind", "term"), CASES)
def test_a_channel_entry_missing_a_required_key_is_rejected(kind: str, term: str, key: str):
    broken = _binding(kind)
    broken["observables"][term].pop(key)
    assert_invalid(SCHEMA, broken)


@pytest.mark.parametrize(("kind", "term"), CASES)
def test_a_channel_entry_with_an_extra_key_is_rejected(kind: str, term: str):
    broken = _binding(kind)
    broken["observables"][term]["extra"] = 1
    assert_invalid(SCHEMA, broken)


def test_the_robot_base_height_entry_needs_its_nominal_and_nothing_else():
    missing = copy.deepcopy(ROBOT)
    missing["observables"]["base_height"].pop("nominal")
    assert_invalid(SCHEMA, missing)
    extra = copy.deepcopy(ROBOT)
    extra["observables"]["base_height"]["body"] = "pelvis"
    assert_invalid(SCHEMA, extra)
