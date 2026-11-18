# SPDX-License-Identifier: Apache-2.0
"""Exercise the real release condition as main advances during Verify (#44)."""

from __future__ import annotations

import os
import re
import urllib.request

import pytest

from test_release_workflow import RELEASE, _guidelines_pins, _job

REPO = "Living-Proof-Labs/livingproof-evaluator"


def release_if() -> str:
    job = _job(RELEASE.read_text(), "release")
    match = re.search(r"    if: >-\n((?:      .*\n)+)", job)
    assert match
    return match.group(1).strip()


def allows(expr: str, context: dict) -> bool:
    """Evaluate this gate's deliberately restricted conjunction of equalities.

    Fail on unsupported syntax instead of silently modelling a changed condition.
    Values are strings, as are all properties used by the release gate.
    """
    results = []
    for clause in expr.split("&&"):
        match = re.fullmatch(r"\s*([\w.]+)\s*==\s*('[^']*'|[\w.]+)\s*", clause)
        assert match, clause
        left, right = match.groups()
        expected = right[1:-1] if right.startswith("'") else context.get(right, "")
        results.append(context.get(left, "") == expected)
    return all(results)


def completion(tip: str, tested: str, conclusion: str = "success", **overrides) -> dict:
    context = {
        "github.event_name": "workflow_run",
        "github.repository": REPO,
        "github.sha": tip,
        "github.event.workflow_run.event": "push",
        "github.event.workflow_run.head_branch": "main",
        "github.event.workflow_run.head_repository.full_name": REPO,
        "github.event.workflow_run.conclusion": conclusion,
        "github.event.workflow_run.head_sha": tested,
    }
    context.update(overrides)
    return context


@pytest.mark.parametrize(
    "events,expected",
    [
        ([("push", "A"), ("push", "B"), ("success", "A"), ("success", "B")], ["B"]),
        ([("push", "A"), ("push", "B"), ("success", "B"), ("success", "A")], ["B"]),
        ([("push", "A"), ("success", "A"), ("push", "B"), ("success", "B")], ["A", "B"]),
        ([("push", "A"), ("push", "B"), ("success", "A"), ("failure", "B")], []),
        ([("push", "A"), ("failure", "A"), ("push", "B"), ("success", "B")], ["B"]),
        ([("push", "A"), ("success", "A"), ("push", "B"), ("success", "A")], ["A"]),
    ],
)
def test_release_race_model(events: list, expected: list) -> None:
    tip = None
    released = []
    for event, sha in events:
        if event == "push":
            tip = sha
        elif allows(release_if(), completion(tip, sha, event)):
            assert sha == tip
            released.append(sha)
    assert released == expected


BAD_CONTEXTS = [
    {"github.event_name": "push"},
    {"github.event.workflow_run.event": "pull_request"},
    {"github.event.workflow_run.event": "workflow_dispatch"},
    {"github.event.workflow_run.event": "merge_group"},
    {"github.event.workflow_run.head_branch": "feature"},
    {"github.event.workflow_run.head_repository.full_name": "fork/repo"},
    {"github.event.workflow_run.head_sha": "old"},
    *[
        {"github.event.workflow_run.conclusion": value}
        for value in ("failure", "cancelled", "skipped", "timed_out", "neutral", "")
    ],
]


@pytest.mark.parametrize("overrides", BAD_CONTEXTS)
def test_only_successful_same_repository_main_push_at_exact_sha_releases(overrides: dict) -> None:
    assert allows(release_if(), completion("A", "A"))
    assert not allows(release_if(), completion("A", "A", **overrides))


def test_removing_any_gate_clause_admits_an_unsafe_context() -> None:
    clauses = release_if().split("&&")
    for index in range(len(clauses)):
        weakened = "&&".join(clauses[:index] + clauses[index + 1 :])
        assert any(allows(weakened, completion("A", "A", **case)) for case in BAD_CONTEXTS)


@pytest.mark.skipif(not os.environ.get("LIVINGPROOF_NETWORK"), reason="set LIVINGPROOF_NETWORK=1")
def test_pinned_shared_release_checks_out_and_asserts_github_sha() -> None:
    """Default checkout uses the event SHA even if main moves while queued.

    Pin the shared runner's existing guard and non-cancelling concurrency too;
    no new privileged repository steps are needed in the caller.
    """
    [(sha, _tag)] = _guidelines_pins(RELEASE.read_text())

    def raw(path: str) -> str:
        url = f"https://raw.githubusercontent.com/Living-Proof-Labs/collaboration-guidelines/{sha}/{path}"
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.read().decode()

    workflow = raw(".github/workflows/semantic-release.yml")
    assert "cancel-in-progress: false" in workflow
    assert "if: github.ref == 'refs/heads/main'" in workflow
    checkout = re.search(r"- uses: actions/checkout@[^\n]+\n((?:        .*\n)+)", workflow)
    assert checkout
    assert "ref:" not in checkout.group(1)
    assert "fetch-depth: 0" in checkout.group(1)
    assert "persist-credentials: false" in checkout.group(1)
    runner = raw(".github/actions/semantic-release/run.mjs")
    assert "execFileSync('git', ['rev-parse', 'HEAD']" in runner
    assert "if (head !== process.env.GITHUB_SHA)" in runner
    assert "throw new Error('Checked-out HEAD must match the triggering commit')" in runner
    assert "git fetch" not in runner and "git pull" not in runner
