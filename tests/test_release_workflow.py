# SPDX-License-Identifier: Apache-2.0
"""Release caller: main-only trigger, pinned shared workflow, no extra secrets."""

from __future__ import annotations

import re
from pathlib import Path

from support import ROOT

RELEASE = ROOT / ".github" / "workflows" / "release.yml"
VERIFY = ROOT / ".github" / "workflows" / "verify.yml"
GUIDELINES_WORKFLOW = (
    "Living-Proof-Labs/collaboration-guidelines/.github/workflows/semantic-release.yml"
)
RENOVATE = ROOT / "renovate.json"
AGENTS = ROOT / "AGENTS.md"
ALLOWED_SECRET_NAMES = {"GITHUB_TOKEN", "github.token"}
RELEASE_CONFIG_NAMES = (
    "release.config.js",
    "release.config.cjs",
    "release.config.mjs",
    ".releaserc",
    ".releaserc.json",
    ".releaserc.yml",
    ".releaserc.yaml",
    ".releaserc.js",
)


def _text(path: Path) -> str:
    return path.read_text()


def _permission_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() == "permissions:" and not line.lstrip().startswith("#"):
            indent = len(line) - len(line.lstrip())
            granted: dict[str, str] = {}
            index += 1
            while index < len(lines):
                body = lines[index]
                if body.strip() == "" or body.lstrip().startswith("#"):
                    index += 1
                    continue
                body_indent = len(body) - len(body.lstrip())
                if body_indent <= indent:
                    break
                key, value = body.strip().split(":", 1)
                granted[key] = value.strip()
                index += 1
            blocks.append(granted)
            continue
        index += 1
    return blocks


def _job(text: str, name: str) -> str:
    match = re.search(rf"^  {name}:\n(?P<body>(?:    .*\n)*)", text, re.MULTILINE)
    assert match is not None, name
    return match.group("body")


def _on_body(text: str) -> str:
    match = re.search(r"^on:\n(?P<body>(?:  .*\n|    .*\n)*)", text, re.MULTILINE)
    assert match is not None
    return match.group("body")


def test_release_workflow_triggers_only_on_push_to_main() -> None:
    assert RELEASE.is_file()
    text = _text(RELEASE)
    assert _on_body(text) == "  push:\n    branches: [main]\n"
    for trigger in ("pull_request:", "workflow_dispatch:", "workflow_run:", "schedule:"):
        assert trigger not in text
    release = _job(text, "release")
    assert "needs: verify\n" in release
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'\n" in release


def _guidelines_pins(text: str) -> list[tuple[str, str]]:
    return re.findall(
        rf"^    uses: {re.escape(GUIDELINES_WORKFLOW)}@([0-9a-f]{{40}}) # (v\d+\.\d+\.\d+)\s*$",
        text,
        re.MULTILINE,
    )


def test_release_workflow_pins_guidelines_commit_with_tag_comment() -> None:
    """The shared workflow is pinned by full commit SHA with its release tag.

    Renovate moves the SHA and tag together, so this checks shape and that the
    tag agrees with the other Renovate-managed guidelines references instead of
    freezing one release.
    """

    text = _text(RELEASE)
    pins = _guidelines_pins(text)
    assert len(pins) == 1
    assert text.count(f"{GUIDELINES_WORKFLOW}@") == 1
    sha, tag = pins[0]
    assert len(sha) == 40
    assert set(sha) != {"0"}

    preset = re.search(r"renovate-preset#(v\d+\.\d+\.\d+)\"", _text(RENOVATE))
    assert preset is not None
    assert preset.group(1) == tag

    agents = re.search(
        r"\[collaboration-guidelines (v\d+\.\d+\.\d+)\]\("
        r"https://github\.com/Living-Proof-Labs/collaboration-guidelines/blob/(v\d+\.\d+\.\d+)/AGENTS\.md\)",
        _text(AGENTS),
    )
    assert agents is not None
    assert agents.group(1) == agents.group(2) == tag


def test_guidelines_pin_rejects_mutable_or_mismatched_refs() -> None:
    good = f"    uses: {GUIDELINES_WORKFLOW}@{'a' * 40} # v1.2.3\n"
    assert _guidelines_pins(good) == [("a" * 40, "v1.2.3")]
    for bad in (
        f"    uses: {GUIDELINES_WORKFLOW}@v1.2.3\n",
        f"    uses: {GUIDELINES_WORKFLOW}@main # v1.2.3\n",
        f"    uses: {GUIDELINES_WORKFLOW}@{'a' * 39} # v1.2.3\n",
        f"    uses: {GUIDELINES_WORKFLOW}@{'a' * 40}\n",
        f"    uses: {GUIDELINES_WORKFLOW}@{'A' * 40} # v1.2.3\n",
    ):
        assert _guidelines_pins(bad) == []


def test_release_workflow_references_no_other_secrets() -> None:
    for path in (RELEASE, VERIFY):
        text = _text(path)
        assert "secrets: inherit" not in text
        names = set(re.findall(r"secrets\.([A-Za-z0-9_]+)", text))
        names.update(re.findall(r"\bgithub\.token\b", text))
        assert names <= ALLOWED_SECRET_NAMES


def test_release_workflow_permissions_match_the_caller_set() -> None:
    blocks = _permission_blocks(_text(RELEASE))
    assert blocks == [
        {"contents": "read"},
        {"contents": "read", "checks": "write"},
        {"contents": "write"},
    ]


def test_verify_runs_on_main_once_through_release() -> None:
    verify = _text(VERIFY)
    assert _on_body(verify) == "  pull_request:\n  workflow_call:\n"
    assert "push:" not in _on_body(verify)
    assert "workflow_run:" not in verify

    release = _text(RELEASE)
    assert _on_body(release) == "  push:\n    branches: [main]\n"
    assert "workflow_run:" not in release
    calls = re.findall(
        r"^    uses: \./\.github/workflows/verify\.yml\s*$",
        release,
        re.MULTILINE,
    )
    assert calls == ["    uses: ./.github/workflows/verify.yml"]

    contract = re.compile(r"(?m)^[ \t]*- run: task verify\s*$")
    caller = re.compile(r"(?m)^[ \t]*uses: \./\.github/workflows/verify\.yml\s*$")
    workflows = ROOT / ".github" / "workflows"
    for path in sorted(workflows.glob("*.yml")):
        if path.name in {"release.yml", "manual.yml"}:
            continue
        text = path.read_text()
        pushes_main = bool(re.search(r"(?m)^  push:\n    branches: \[main\]\n", _on_body(text)))
        runs_contract = bool(caller.search(text) or contract.search(text))
        assert not (pushes_main and runs_contract)


def test_verify_permissions_are_unchanged() -> None:
    blocks = _permission_blocks(_text(VERIFY))
    assert blocks == [
        {"contents": "read"},
        {"contents": "read", "checks": "write"},
    ]


def test_caller_does_not_override_first_release_version() -> None:
    """The shared engine's first release is 1.0.0 when main has no tag.

    semantic-release 25.0.9 (the version pinned by the shared action) sets
    that version from FIRST_RELEASE in get-next-version.js and does not apply
    the commit's major, minor, or patch increment until a tag exists. This
    caller passes no version input and ships no release config of its own.
    """

    release = _job(_text(RELEASE), "release")
    assert "with:" not in release
    assert "tagFormat" not in _text(RELEASE)
    for name in RELEASE_CONFIG_NAMES:
        assert not (ROOT / name).exists()
    package_json = ROOT / "package.json"
    if package_json.exists():
        assert "release" not in package_json.read_text()
