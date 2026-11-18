# SPDX-License-Identifier: Apache-2.0
"""Reference rules for plan-conformance, termination and recording.

The contract repository ships no evaluator, so these functions are the written-down
rules in executable form. A test derives the expected check object from an example
request with them, and compares that to the example result. They are not an
implementation for producers to import. Each returns None when the request carries no
evidence for the check. Otherwise it returns a dict with the fields of the check object
that the rules fix: applicable, percentage, findings as (category, trial_id) pairs with a
summary, and for termination its referrals.

Five checks have a rule that changed in a later check version. ``pins`` is 1.1.0 only (its
1.0.0 rule divided by five and had no ``not_checked``). ``termination``, ``recording``,
``plan_conformance`` and ``completeness_applicable`` take ``version`` and **default to 1.1.0**,
the current rule, so a caller that forgets it tests the current one; pass ``"1.0.0"`` for the
old rule. 1.1.0 never allows ``simulation-broken``, reports ``not_checked`` (recording and
plan-conformance), and leaves a file with no valid footer to completeness. Where a check reports
``not_checked``, its subjects are outside the denominator of ``percentage``.
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


class MalformedRequest(ValueError):
    """The request is inconsistent, so no check result can be trusted. An evaluator rejects it:
    it writes no result and exits with status 2, as it does for any other malformed request."""


def _not_applicable() -> dict[str, Any]:
    return {"applicable": False, "findings": []}


def _trial_path(index: int) -> str:
    return f"trials/trial-{index:02d}.json"


def plan_conformance(payload: dict[str, Any], version: str = "1.1.0") -> dict[str, Any] | None:
    """The plan, the trials and the lock agree. Subjects are the comparisons made,
    one per index 1..N, and one per result entry whose index is outside 1..N."""
    evidence = payload.get("evidence", {}).get("plan-conformance")
    if evidence is None:
        return None
    if not evidence.get("preconditions", {}).get("met", True):
        return _not_applicable() if version == "1.0.0" else {**_not_applicable(), "not_checked": []}
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
    # The comparisons with the lock that were not made are not in the subjects either.
    not_checked: list[dict[str, Any]] = []
    if lock_plan is None:
        not_checked.append({"subject": "lock-trial-count", "reason": "not-declared"})
    if lock_plan is None or plan_speed is None or "command_speed" not in lock_plan:
        not_checked.append({"subject": "lock-command-speed", "reason": "not-declared"})
    result = {
        "applicable": True,
        "percentage": _share(subjects - failing, subjects),
        "findings": findings,
    }
    if version != "1.0.0":
        result["not_checked"] = not_checked
    return result


PIN_SUBJECTS = ("specs", "runner", "verifier", "world", "configuration")


def _pin(pins: dict[str, Any], subject: str) -> str | None:
    value = pins.get(subject)
    return value.get("sha256") if isinstance(value, dict) else None


def pins(payload: dict[str, Any]) -> dict[str, Any]:
    """pins 1.1.0. A subject is checked when the manifest and the lock both carry its sha256.
    One the lock does not declare is ``not-declared``, and one the manifest does not record is
    ``not-recorded``. The percentage is 100 times the matching checked subjects divided by the
    checked subjects, so a subject that was not checked is not in it. With no checked subject
    the check is not applicable."""
    manifest = payload["manifest"]["pins"]
    lock = payload["lock"]["pins"]
    findings: list[dict[str, Any]] = []
    not_checked: list[dict[str, Any]] = []
    checked = 0
    for subject in PIN_SUBJECTS:
        declared = _pin(lock, subject)
        recorded = _pin(manifest, subject)
        if declared is None or recorded is None:
            reason = "not-declared" if declared is None else "not-recorded"
            not_checked.append({"subject": subject, "reason": reason})
            continue
        checked += 1
        if declared != recorded:
            findings.append(
                {
                    "category": "hash-mismatch",
                    "classification": "test_system",
                    "summary": f"The {subject} pin hash differs between the run manifest"
                    " and the verification lock.",
                    "subject": subject,
                }
            )
    if not checked:
        return {"applicable": False, "findings": [], "not_checked": not_checked}
    return {
        "applicable": True,
        "percentage": _share(checked - len(findings), checked),
        "findings": findings,
        "not_checked": not_checked,
    }


def completeness_applicable(payload: dict[str, Any], version: str = "1.1.0") -> bool:
    """Whether completeness applies. 1.0.0 always did. From 1.1.0 it follows
    plan-conformance: when ``evidence['plan-conformance'].preconditions.met`` is false the run
    ran no trials, and completeness is not applicable instead of reporting every planned
    trial as missing."""
    if version == "1.0.0":
        return True
    preconditions = payload.get("evidence", {}).get("plan-conformance", {}).get("preconditions", {})
    return preconditions.get("met", True)


def termination(
    payload: dict[str, Any], vocabulary: set[str], version: str = "1.1.0"
) -> dict[str, Any] | None:
    """Every trial that ended on its own records a stop reason that the plan allows.
    A trial whose termination is timeout or crash is referred to completeness.

    From 1.1.0 ``simulation-broken`` is never allowed, whatever the plan lists, so it is always
    a ``disallowed-stop-reason`` finding. 1.0.0 allowed it when the plan listed it."""
    evidence = payload.get("evidence", {}).get("termination")
    if evidence is None:
        return None
    allowed = set(evidence["allowed_stop_reasons"])
    never = version != "1.0.0"
    if never:
        allowed.discard("simulation-broken")
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
            text = (
                f"The stop reason {reason} is never allowed."
                if never and reason == "simulation-broken"
                else f"The stop reason {reason} is not one the plan allows."
            )
            findings.append(_finding("disallowed-stop-reason", text, trial_id))
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


def recording(payload: dict[str, Any], version: str = "1.1.0") -> dict[str, Any] | None:
    """Each present recording is a usable MCAP file that matches media.json. Trials whose
    recording completeness does not report as present are not judged here.

    1.1.0 (the default): a file with no valid footer is completeness's, as a ``truncated``
    recording, so this check does not judge it and does not emit ``mcap-incomplete``. A present
    trial whose evidence says ``incomplete``, an evidence trial not in ``trials``, or an unknown
    or missing ``mcap.state`` is inconsistent or malformed and raises ``MalformedRequest``. Every
    trial it did not judge is listed in ``not_checked``, also when it judged nothing. 1.0.0, the
    old rule, judged such a file, emitted ``mcap-incomplete`` and had no ``not_checked``."""
    evidence = payload.get("evidence", {}).get("recording")
    if evidence is None:
        return None
    new = version != "1.0.0"
    if not evidence["media_available"]:
        # The whole check is not applicable, so there is no trial to list.
        return {**_not_applicable(), "not_checked": []} if new else _not_applicable()
    trial_states = {trial["id"]: trial["recording"]["state"] for trial in payload["trials"]}
    present = {trial_id for trial_id, state in trial_states.items() if state == "present"}
    if new:
        # Fail closed on inconsistent or malformed recording evidence: an evidence entry for an
        # unknown trial, a missing or unknown mcap.state, or a present trial whose evidence says
        # incomplete (which belongs to completeness as a truncated recording).
        for entry in evidence["trials"]:
            trial_id = entry["id"]
            mcap = entry.get("mcap")
            has_state = isinstance(mcap, dict) and "state" in mcap
            mcap_state = mcap["state"] if has_state else None
            state_desc = repr(mcap_state) if has_state else "missing"
            if trial_id not in trial_states:
                raise MalformedRequest(
                    f"trial {trial_id}: evidence.recording has an entry (mcap.state is"
                    f" {state_desc}) for a trial that is not in trials."
                )
            recording_state = trial_states[trial_id]
            if not has_state:
                raise MalformedRequest(
                    f"trial {trial_id}: evidence.recording mcap.state is missing"
                    f" (recording.state is {recording_state})."
                )
            if mcap_state not in ("complete", "incomplete"):
                raise MalformedRequest(
                    f"trial {trial_id}: recording.state is {recording_state} and"
                    f" evidence.recording mcap.state is {state_desc},"
                    " which is not a known state."
                )
            if trial_id in present and mcap_state == "incomplete":
                raise MalformedRequest(
                    f"trial {trial_id}: recording.state is present but evidence.recording"
                    " says the file is incomplete. A file with no valid footer is truncated:"
                    " classify it as truncated."
                )
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
    not_checked: list[dict[str, Any]] = []
    if new:
        # A trial that was not judged is listed, so a reader can tell it from a clean one. No
        # readable recording (missing, truncated, empty, or a file with no valid footer) is
        # not-present, and completeness reports it. A present one that the evidence has no entry
        # for was never read: not-recorded.
        by_id = {entry["id"]: entry for entry in evidence["trials"]}
        for trial in payload["trials"]:
            entry = by_id.get(trial["id"])
            if trial["recording"]["state"] != "present":
                not_checked.append({"trial_id": trial["id"], "reason": "not-present"})
            elif entry is None:
                not_checked.append({"trial_id": trial["id"], "reason": "not-recorded"})
    if not judged:
        return {**_not_applicable(), "not_checked": not_checked} if new else _not_applicable()
    result: dict[str, Any] = {
        "applicable": True,
        "percentage": _share(judged - len(failing), judged),
        "limits": {"max_gap_seconds": evidence["max_gap_seconds"]},
        "findings": findings,
    }
    if new:
        result["not_checked"] = not_checked
    return result


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
    if "not_checked" in expected:
        assert check.get("not_checked", []) == expected["not_checked"]
    assert check["success"] is (not expected["findings"])


def finding_keys(check: dict[str, Any]) -> list[tuple[str, str | None]]:
    return sorted((item["category"], item.get("trial_id")) for item in check["findings"])
