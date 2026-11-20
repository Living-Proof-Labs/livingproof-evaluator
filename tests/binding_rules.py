# SPDX-License-Identifier: Apache-2.0
"""Reference merge rules for the observation binding (issue 3).

The contract repository ships no runner, so this is the written-down rule in executable form.
A test derives the merged binding from a robot binding and a producer binding with it, and
compares that to the merged example. It is not an implementation for producers to import.

An observable is bound only when both owners supply what it needs: the producer names the
channel and fields that carry it, and the robot supplies its own entries (the base body for
`base`, the nominal for a term whose nominal applies per robot configuration). Anything else
is unbound, with the reason. Nothing is guessed: a missing or doubled entry is not filled in.
"""

from __future__ import annotations

from typing import Any

PRODUCER_MISSING = "producer-does-not-carry"
ROBOT_MISSING = "robot-entry-missing"
# What a robot must supply for an observable, besides the producer's channel.
ROBOT_NEEDS = {"base": "body"}


def robot_needs(term: dict[str, Any], name: str) -> list[str]:
    needs = [ROBOT_NEEDS[name]] if name in ROBOT_NEEDS else []
    if term["nominal"]["applies"] == "per-robot-configuration":
        needs.append("nominal")
    return needs


def merge(robot: dict, producer: dict, vocabulary: dict, trial_id: str, recording: dict) -> dict:
    """The merged per-trial binding, in vocabulary order."""
    observables: dict[str, Any] = {}
    unbound: list[dict] = []
    for term in vocabulary["terms"]:
        name = term["id"]
        carried = producer["observables"].get(name)
        supplied = robot["observables"].get(name, {})
        if carried is None:
            unbound.append({"id": name, "reason": PRODUCER_MISSING})
            continue
        if any(need not in supplied for need in robot_needs(term, name)):
            unbound.append({"id": name, "reason": ROBOT_MISSING})
            continue
        observables[name] = {**carried, **supplied}
    return {
        "format": "livingproof-observation-binding/1.0.0",
        "kind": "merged",
        "trial_id": trial_id,
        "robot": {"id": robot["robot"]["id"], "configuration": robot["configuration"]},
        "producer": {"id": producer["producer"]["id"]},
        "recording": recording,
        "observables": observables,
        "bound_observables": list(observables),
        "unbound": unbound,
    }


def merged_problems(binding: dict, vocabulary: dict) -> list[str]:
    """What a merged binding gets wrong that its schema cannot say. Empty when sound."""
    terms = {term["id"]: term for term in vocabulary["terms"]}
    problems: list[str] = []
    bound = binding["bound_observables"]
    unbound = [item["id"] for item in binding["unbound"]]
    if bound != list(binding["observables"]):
        problems.append("bound_observables must list exactly the observables, in order")
    if set(bound) & set(unbound):
        problems.append("an observable is both bound and unbound")
    if set(bound) | set(unbound) != set(terms) or len(bound) + len(unbound) != len(terms):
        problems.append("every vocabulary term is either bound or unbound, once")
    for name, entry in binding["observables"].items():
        term = terms.get(name)
        if term is None:
            problems.append(f"{name} is not in the vocabulary")
            continue
        for need in robot_needs(term, name):
            if need not in entry:
                problems.append(f"{name} is bound without its {need}")
        if "nominal" in entry and term["nominal"]["applies"] == "never":
            problems.append(f"{name} has no per-robot nominal, so it must not carry one")
    return problems
