# SPDX-License-Identifier: Apache-2.0
"""Reference rules for plan-conformance, termination and recording.

The contract repository ships no evaluator, so these functions are the written-down
rules in executable form. A test derives the expected check object from an example
request with them, and compares that to the example result. They are not an
implementation for producers to import. Each returns None when the request carries no
evidence for the check. Otherwise it returns a dict with the fields of the check object
that the rules fix: applicable, percentage, findings as (category, trial_id) pairs with a
summary, and for termination its referrals.
"""

from __future__ import annotations

from typing import Any

COMPLETENESS_CATEGORY = {"timeout": "ended-by-timeout", "crash": "ended-by-crash"}


def _share(good: int, total: int) -> float:
    return 100 * good / total


def _finding(category: str, summary: str, trial_id: str | None = None) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "category": category,
        "classification": "test_system",
        "summary": summary,
    }
    if trial_id is not None:
        finding["trial_id"] = trial_id
    return finding


def _not_applicable() -> dict[str, Any]:
    return {"applicable": False, "findings": []}


def _trial_path(index: int) -> str:
    return f"trials/trial-{index:02d}.json"


def plan_conformance(payload: dict[str, Any]) -> dict[str, Any] | None:
    """The plan, the trials and the lock agree. Subjects are the comparisons made,
    one per index 1..N, and one per result entry whose index is outside 1..N."""
    evidence = payload.get("evidence", {}).get("plan-conformance")
    if evidence is None:
        return None
    if not evidence.get("preconditions", {}).get("met", True):
        return _not_applicable()
    planned = evidence["plan"]["trial_count"]
    results = evidence["trials"]["results"]
    findings: list[dict[str, Any]] = []
    subjects = 0
    failing = 0

    counts = [
        ("trials.count", evidence["trials"]["count"]),
        ("the number of trials.results entries", len(results)),
    ]
    lock_plan = evidence.get("lock", {}).get("plan")
    if lock_plan is not None:
        counts.append(("the lock's plan trial count", lock_plan["trial_count"]))
    for name, value in counts:
        subjects += 1
        if value != planned:
            failing += 1
            findings.append(
                _finding(
                    "trial-count-mismatch",
                    f"The plan has {planned} trials and {name} is {value}.",
                )
            )
    plan_speed = evidence["plan"].get("command_speed")
    if lock_plan is not None and plan_speed is not None and "command_speed" in lock_plan:
        subjects += 1
        if lock_plan["command_speed"] != plan_speed:
            failing += 1
            findings.append(
                _finding(
                    "command-speed-mismatch",
                    f"The plan's command_speed is {plan_speed}"
                    f" and the lock's is {lock_plan['command_speed']}.",
                )
            )
    for index in range(1, planned + 1):
        subjects += 1
        entries = [entry for entry in results if entry["index"] == index]
        slot_findings: list[dict[str, Any]] = []
        if not entries:
            slot_findings.append(
                _finding("index-missing", f"No trials.results entry has index {index}.")
            )
        elif len(entries) > 1:
            slot_findings.append(
                _finding(
                    "index-duplicate",
                    f"{len(entries)} trials.results entries have index {index}.",
                )
            )
        for entry in entries:
            if entry["path"] != _trial_path(index):
                slot_findings.append(
                    _finding(
                        "path-mismatch",
                        f"The entry for index {index} has path {entry['path']},"
                        f" not {_trial_path(index)}.",
                    )
                )
        if slot_findings:
            failing += 1
            findings.extend(slot_findings)
    for entry in results:
        if not 1 <= entry["index"] <= planned:
            subjects += 1
            failing += 1
            findings.append(
                _finding(
                    "index-out-of-range",
                    f"A trials.results entry has index {entry['index']}, outside 1 to {planned}.",
                )
            )
    return {
        "applicable": True,
        "percentage": _share(subjects - failing, subjects),
        "findings": findings,
    }


def termination(payload: dict[str, Any], vocabulary: set[str]) -> dict[str, Any] | None:
    """Every trial that ended on its own records a stop reason that the plan allows.
    A trial whose termination is timeout or crash is referred to completeness."""
    evidence = payload.get("evidence", {}).get("termination")
    if evidence is None:
        return None
    allowed = set(evidence["allowed_stop_reasons"])
    recorded = {entry["id"]: entry for entry in evidence["trials"]}
    findings: list[dict[str, Any]] = []
    referrals: list[dict[str, str]] = []
    judged = 0
    failing: set[str] = set()
    for trial in payload["trials"]:
        trial_id = trial["id"]
        if trial["termination"] in COMPLETENESS_CATEGORY:
            referrals.append(
                {
                    "trial_id": trial_id,
                    "check": "completeness",
                    "category": COMPLETENESS_CATEGORY[trial["termination"]],
                }
            )
            continue
        judged += 1
        entry = recorded.get(trial_id, {})
        reason = entry.get("stop_reason")
        if reason is None:
            failing.add(trial_id)
            findings.append(
                _finding("missing-stop-reason", "The trial records no stop reason.", trial_id)
            )
        elif reason not in vocabulary:
            failing.add(trial_id)
            findings.append(
                _finding(
                    "unknown-stop-reason",
                    f"The stop reason {reason} is not in the stop reason vocabulary.",
                    trial_id,
                )
            )
        elif reason not in allowed:
            failing.add(trial_id)
            findings.append(
                _finding(
                    "disallowed-stop-reason",
                    f"The stop reason {reason} is not one the plan allows.",
                    trial_id,
                )
            )
        manifest_reason = entry.get("manifest_stop_reason")
        if reason is not None and manifest_reason not in (None, reason):
            failing.add(trial_id)
            findings.append(
                _finding(
                    "stop-reason-mismatch",
                    f"The trial records {reason} and the manifest records {manifest_reason}.",
                    trial_id,
                )
            )
    result: dict[str, Any] = {
        "applicable": judged > 0,
        "findings": findings,
        "referrals": referrals,
    }
    if judged:
        result["percentage"] = _share(judged - len(failing), judged)
    return result


def recording(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Each present recording is a usable MCAP file that matches media.json. Trials whose
    recording completeness does not report as present are not judged here."""
    evidence = payload.get("evidence", {}).get("recording")
    if evidence is None:
        return None
    if not evidence["media_available"]:
        return _not_applicable()
    present = {
        trial["id"] for trial in payload["trials"] if trial["recording"]["state"] == "present"
    }
    findings: list[dict[str, Any]] = []
    judged = 0
    failing: set[str] = set()
    for entry in evidence["trials"]:
        trial_id = entry["id"]
        if trial_id not in present:
            continue
        judged += 1
        trial_findings: list[dict[str, Any]] = []
        mcap = entry["mcap"]
        if mcap["state"] != "complete":
            trial_findings.append(
                _finding(
                    "mcap-incomplete",
                    "The recording does not open or has no valid footer and summary.",
                    trial_id,
                )
            )
        channels = {channel["topic"]: channel for channel in mcap["channels"]}
        for topic in evidence["required_channels"]:
            channel = channels.get(topic)
            if channel is None or channel["message_count"] == 0:
                trial_findings.append(
                    _finding(
                        "missing-channel",
                        f"The required channel {topic} is absent or has no messages.",
                        trial_id,
                    )
                )
        for topic, channel in channels.items():
            if channel["backward_steps"] > 0:
                trial_findings.append(
                    _finding(
                        "timestamps-backwards",
                        f"Channel {topic} has {channel['backward_steps']} timestamps"
                        " that go backwards.",
                        trial_id,
                    )
                )
            if channel["max_gap_seconds"] > evidence["max_gap_seconds"]:
                trial_findings.append(
                    _finding(
                        "message-gap-exceeded",
                        f"Channel {topic} has a gap of {channel['max_gap_seconds']} s,"
                        f" over the limit of {evidence['max_gap_seconds']} s.",
                        trial_id,
                    )
                )
        media = entry["media"]
        if mcap["sha256"] != media["mcap_sha256"] or mcap["bytes"] != media["mcap_bytes"]:
            trial_findings.append(
                _finding(
                    "media-file-mismatch",
                    "The recording's size or sha256 differs from media.json.",
                    trial_id,
                )
            )
        if media["observation_sha256"] != entry["evidence_observation_sha256"]:
            trial_findings.append(
                _finding(
                    "observation-link-mismatch",
                    "The observation_sha256 in media.json differs from the run evidence.",
                    trial_id,
                )
            )
        if trial_findings:
            failing.add(trial_id)
            findings.extend(trial_findings)
    if not judged:
        return _not_applicable()
    return {
        "applicable": True,
        "percentage": _share(judged - len(failing), judged),
        "limits": {"max_gap_seconds": evidence["max_gap_seconds"]},
        "findings": findings,
    }


def reported(result: dict[str, Any], check_id: str) -> dict[str, Any]:
    """The one check object with this id in an integrity result document."""
    matches = [check for check in result["integrity"]["checks"] if check["id"] == check_id]
    assert len(matches) == 1
    return matches[0]


def matches_rules(check: dict[str, Any], expected: dict[str, Any]) -> None:
    """Assert that a reported check object is the one the rules derive from its request."""
    assert check["applicable"] is expected["applicable"]
    assert ("percentage" in check) is ("percentage" in expected)
    if "percentage" in expected:
        assert check["percentage"] == expected["percentage"]
    assert check["findings"] == expected["findings"]
    if "referrals" in expected:
        assert check["referrals"] == expected["referrals"]
    assert check.get("limits") == expected.get("limits")
    assert check["success"] is (not expected["findings"])


def finding_keys(check: dict[str, Any]) -> list[tuple[str, str | None]]:
    return sorted((item["category"], item.get("trial_id")) for item in check["findings"])
