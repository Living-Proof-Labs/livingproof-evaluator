# SPDX-License-Identifier: Apache-2.0
"""Exercise the real release condition as main advances during Verify (#44)."""

from __future__ import annotations

import os
import re
import urllib.request

import pytest

from test_release_workflow import RELEASE, VERIFY, _guidelines_pins, _job


def condition(path, name) -> str:
    job = _job(path.read_text(), name)
    match = re.search(r"    if: >-\n((?:      .*\n)+)", job)
    assert match
    return match.group(1).strip()


def allows(expr: str, context: dict) -> bool:
    """Evaluate the exact workflow condition, rejecting unsupported syntax."""
    results = []
    for clause in expr.split("&&"):
        match = re.fullmatch(
            r"\s*([\w.-]+)\s*(==|!=)\s*('[^']*'|[\w.-]+|format\('v\{0\}', [\w.-]+\))\s*",
            clause,
        )
        assert match, clause
        left, operation, right = match.groups()
        if right.startswith("format"):
            expected = "v" + context.get(right.removesuffix(")").split(", ")[1], "")
        else:
            expected = right[1:-1] if right.startswith("'") else context.get(right, "")
        equal = context.get(left, "") == expected
        results.append(equal if operation == "==" else not equal)
    return all(results)


CONTEXT = {
    "github.event_name": "push",
    "github.ref": "refs/heads/main",
    "github.sha": "head",
    "github.run_id": "100",
    "github.run_attempt": "3",
    "needs.verify.result": "success",
    "needs.version.result": "success",
    "needs.manual.result": "success",
    "needs.version.outputs.version": "1.8.7",
    "needs.version.outputs.semver-version": "1.8.7",
    "needs.version.outputs.git-tag": "v1.8.7",
    "needs.version.outputs.commit": "head",
    "needs.version.outputs.run-id": "100",
    "needs.version.outputs.run-attempt": "3",
    "needs.manual.outputs.artifact-id": "42",
    "needs.manual.outputs.digest": "a" * 64,
    "needs.release.outputs.published": "true",
    "needs.release.outputs.git-tag": "v1.8.7",
    "needs.release.outputs.version": "1.8.7",
    "needs.release.outputs.commit": "head",
    "inputs.commit": "head",
}


BAD_CONTEXTS = [
    {"github.event_name": "workflow_run"},
    {"github.event_name": "pull_request"},
    {"github.event_name": "workflow_dispatch"},
    {"github.event_name": "merge_group"},
    {"github.ref": "refs/heads/feature"},
    {"needs.verify.result": "failure"},
    {"needs.version.result": "cancelled"},
    {"needs.manual.result": "skipped"},
    {
        "needs.version.outputs.version": "",
        "needs.version.outputs.semver-version": "",
        "needs.version.outputs.git-tag": "v",
    },
    {"needs.version.outputs.semver-version": "1.8.7-pr.64.2.1"},
    {"needs.version.outputs.git-tag": "v1.8.6"},
    {"needs.version.outputs.commit": "old"},
    {"needs.version.outputs.run-id": "99"},
    {"needs.version.outputs.run-attempt": "2"},
    {"needs.manual.outputs.artifact-id": ""},
    {"needs.manual.outputs.digest": ""},
]


@pytest.mark.parametrize("overrides", BAD_CONTEXTS)
def test_only_verified_current_attempt_main_plan_with_sealed_build_releases(overrides):
    gate = condition(VERIFY, "release")
    assert allows(gate, CONTEXT)
    assert not allows(gate, CONTEXT | overrides)


def test_removing_any_gate_clause_admits_an_invalid_context():
    clauses = condition(VERIFY, "release").split("&&")
    for index in range(len(clauses)):
        weakened = "&&".join(clauses[:index] + clauses[index + 1 :])
        assert any(allows(weakened, CONTEXT | case) for case in BAD_CONTEXTS), clauses[index]


@pytest.mark.parametrize(
    "overrides",
    [
        {"github.event_name": "pull_request"},
        {"github.ref": "refs/heads/feature"},
        {"needs.release.outputs.published": "false"},
        {"needs.release.outputs.git-tag": "v1.8.6"},
        {"needs.release.outputs.version": "1.8.6"},
        {"needs.release.outputs.commit": "old"},
    ],
)
def test_pages_only_consumes_an_exact_published_stable_release(overrides):
    gate = condition(VERIFY, "deploy-manual")
    assert allows(gate, CONTEXT)
    assert not allows(gate, CONTEXT | overrides)


def test_release_child_still_requires_trusted_same_source():
    for name in ("current-main", "release"):
        gate = condition(RELEASE, name)
        assert allows(gate, CONTEXT)
        for invalid in ("pull_request", "workflow_dispatch", "workflow_run"):
            assert not allows(gate, CONTEXT | {"github.event_name": invalid})
        assert not allows(gate, CONTEXT | {"inputs.commit": "old"})


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
