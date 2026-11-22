# SPDX-License-Identifier: Apache-2.0
"""A workflow that reads current main at git/ref/heads/main must send the workflow token.

An anonymous call shares the runner rate limit, fails with HTTP 403, and leaves
the published site on the previous release. contents: read is enough; the deploy
job must not gain contents: write.

The manual deploy job already uses ``gh api`` with ``GH_TOKEN``. ``urllib`` is
accepted only when the request sends ``Authorization: Bearer``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from support import ROOT

WORKFLOWS = ROOT / ".github" / "workflows"
FRESHNESS = "git/ref/heads/main"
FRESHNESS_API = "repos/Living-Proof-Labs/livingproof-evaluator/git/ref/heads/main"
TOKEN_VALUE = re.compile(r"\$\{\{\s*(?:github\.token|secrets\.GITHUB_TOKEN)\s*\}\}")
DIRECT_HTTP = re.compile(
    r"urlopen|urllib\.request|requests\.(?:get|post|request)"
    r"|(?:^|[^\w])curl\s|http\.client|\bfetch\("
)
GH_API = re.compile(r"\bgh\s+api\b")
EXPECTED_SHA = "a" * 40

UNAUTHENTICATED = """\
jobs:
  deploy:
    permissions:
      pages: write
      id-token: write
    steps:
      - name: Check current main inside deployment lock
        env:
          EXPECTED_SHA: abcdef
        run: |
          python - <<'PYCODE'
          import json, os, urllib.request
          url = 'https://api.github.com/repos/example/repo/git/ref/heads/main'
          with urllib.request.urlopen(url, timeout=30) as response:
              current = json.load(response)['object']['sha']
          PYCODE
"""

TOKEN_PRESENT_BUT_UNUSED = """\
jobs:
  deploy:
    permissions:
      contents: read
    steps:
      - name: Check current main
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: |
          python - <<'PYCODE'
          import urllib.request
          url = 'https://api.github.com/repos/example/repo/git/ref/heads/main'
          urllib.request.urlopen(url)
          PYCODE
"""

GH_WITHOUT_TOKEN = """\
permissions:
  contents: read
jobs:
  deploy:
    steps:
      - name: Require current main
        run: |
          current=$(gh api repos/example/repo/git/ref/heads/main --jq .object.sha)
          test "$current" = "$GITHUB_SHA"
"""

AUTHENTICATED_GH = """\
permissions:
  contents: read
jobs:
  deploy:
    permissions:
      contents: read
    steps:
      - name: Require current main
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          ref="repos/${GITHUB_REPOSITORY}/git/ref/heads/main"
          current=$(gh api "$ref" --jq .object.sha)
          test "$current" = "$GITHUB_SHA"
"""

AUTHENTICATED_URLLIB = """\
jobs:
  deploy:
    permissions:
      contents: read
      pages: write
      id-token: write
    steps:
      - name: Require current main
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: |
          python - <<'PYCODE'
          import json, os, urllib.request
          token = os.environ["GITHUB_TOKEN"]
          repo = os.environ["GITHUB_REPOSITORY"]
          url = f"https://api.github.com/repos/{repo}/git/ref/heads/main"
          request = urllib.request.Request(
              url,
              headers={"Authorization": f"Bearer {token}"},
          )
          with urllib.request.urlopen(request, timeout=30) as response:
              current = json.load(response)["object"]["sha"]
          PYCODE
"""

FAKE_GH = """\
#!/usr/bin/env python3
import json
import os
import sys

token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
record = {"argv": sys.argv[1:], "token": token}
with open(os.environ["GH_CAPTURE"], "w", encoding="utf-8") as handle:
    json.dump(record, handle)
status = int(os.environ.get("GH_STATUS", "0"))
if status != 0:
    sys.stderr.write("HTTP Error 403: rate limit exceeded\\n")
    raise SystemExit(status)
sys.stdout.write(os.environ.get("GH_SHA", "") + "\\n")
"""


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_value(value: str) -> str:
    return re.sub(r"\s+#.*$", "", value.strip()).strip("'\"")


def _envs_at(lines: list[str], env_indent: int) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for index, line in enumerate(lines):
        if _indent(line) != env_indent or line.strip() != "env:":
            continue
        for inner in lines[index + 1 :]:
            if not inner.strip() or inner.lstrip().startswith("#"):
                continue
            indent = _indent(inner)
            if indent <= env_indent:
                break
            match = re.match(r"^ +([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", inner)
            if match and indent == env_indent + 2:
                found.append({"name": match.group(1), "value": _strip_value(match.group(2))})
    return found


def _permission_block(lines: list[str], block_indent: int) -> dict[str, str] | None:
    for index, line in enumerate(lines):
        if _indent(line) != block_indent or not line.strip().startswith("permissions:"):
            continue
        inline = _strip_value(line.strip()[len("permissions:") :])
        if inline and inline not in {"|", ">", "|-", ">-", "|+", ">+"}:
            return {"_scalar": inline}
        block: dict[str, str] = {}
        for inner in lines[index + 1 :]:
            if not inner.strip() or inner.lstrip().startswith("#"):
                continue
            indent = _indent(inner)
            if indent <= block_indent:
                break
            match = re.match(r"^ +([\w-]+):\s*(.*)$", inner)
            if match and indent == block_indent + 2:
                block[match.group(1)] = _strip_value(match.group(2))
        return block
    return None


def _jobs(text: str) -> list[dict[str, object]]:
    jobs: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    in_jobs = False
    for line in text.splitlines():
        if line == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line.strip() and _indent(line) == 0:
            break
        if re.fullmatch(r"  [\w-]+:\s*", line):
            if current is not None:
                jobs.append(current)
            current = {"name": line.strip()[:-1], "lines": [line]}
            continue
        if current is not None:
            lines = current["lines"]
            assert isinstance(lines, list)
            lines.append(line)
    if current is not None:
        jobs.append(current)
    return jobs


def _steps(job_lines: list[str]) -> list[list[str]]:
    steps: list[list[str]] = []
    current: list[str] | None = None
    in_steps = False
    for line in job_lines:
        if line == "    steps:":
            in_steps = True
            continue
        if not in_steps:
            continue
        if line.strip() and _indent(line) <= 4:
            break
        if line.startswith("      - "):
            if current is not None:
                steps.append(current)
            current = [line]
            continue
        if current is not None:
            current.append(line)
    if current is not None:
        steps.append(current)
    return steps


def _run_script(step_lines: list[str]) -> str:
    scripts: list[str] = []
    for index, line in enumerate(step_lines):
        match = re.match(r"^( +)run:\s*(.*)$", line)
        if match is None:
            continue
        indent = len(match.group(1))
        rest = match.group(2).strip()
        if rest in {"|", ">", "|-", ">-", "|+", ">+"}:
            body: list[str] = []
            for inner in step_lines[index + 1 :]:
                if not inner.strip():
                    body.append("")
                    continue
                if _indent(inner) <= indent:
                    break
                body.append(inner)
            scripts.append("\n".join(body))
        else:
            scripts.append(_strip_value(rest))
    return "\n".join(scripts)


def _token_names(entries: list[dict[str, str]]) -> list[str]:
    return [
        entry["name"]
        for entry in entries
        if entry["name"] in {"GH_TOKEN", "GITHUB_TOKEN"} and TOKEN_VALUE.search(entry["value"])
    ]


def _sends_bearer(script: str, token_names: list[str]) -> bool:
    if "Authorization" not in script or "Bearer" not in script:
        return False
    return any(name in script for name in token_names)


def _contents(job_lines: list[str], workflow_text: str) -> str | None:
    job = _permission_block(job_lines, 4)
    if job is not None:
        return job.get("contents")
    workflow = _permission_block(workflow_text.splitlines(), 0)
    if workflow is None:
        return None
    return workflow.get("contents")


def freshness_problems(filename: str, text: str) -> list[str]:
    """Problems for one workflow. An empty list means every freshness read is authenticated."""

    problems: list[str] = []
    jobs = _jobs(text)
    workflow_tokens = _token_names(_envs_at(text.splitlines(), 0))
    seen_in_step = False
    for job in jobs:
        job_lines = job["lines"]
        assert isinstance(job_lines, list)
        job_name = str(job["name"])
        job_tokens = _token_names(_envs_at(job_lines, 4))
        for step in _steps(job_lines):
            step_text = "\n".join(step)
            if FRESHNESS not in step_text:
                continue
            seen_in_step = True
            script = _run_script(step)
            tokens = _token_names([*_envs_at(step, 8)])
            token_names = [*workflow_tokens, *job_tokens, *tokens]
            where = f"{filename} job {job_name}"
            if FRESHNESS not in script:
                problems.append(
                    f"{where}: {FRESHNESS} is outside the run script, "
                    "so the call is not an authenticated read"
                )
                continue
            gh_api = GH_API.search(script) is not None
            direct_http = DIRECT_HTTP.search(script) is not None
            if not gh_api and not direct_http:
                problems.append(
                    f"{where}: {FRESHNESS} is called without authentication. "
                    "Pass GH_TOKEN or GITHUB_TOKEN from github.token and use gh api, "
                    "or send Authorization: Bearer."
                )
                continue
            if gh_api and not token_names:
                problems.append(
                    f"{where}: gh api reads {FRESHNESS} without authentication. "
                    "Set GH_TOKEN or GITHUB_TOKEN to ${{ github.token }} in the step env."
                )
            if direct_http and (not token_names or not _sends_bearer(script, token_names)):
                problems.append(
                    f"{where}: {FRESHNESS} is called without authentication. "
                    "Pass GITHUB_TOKEN from github.token in the step env and send "
                    "Authorization: Bearer with that token."
                )
            if _contents(job_lines, text) != "read":
                problems.append(
                    f"{where}: the freshness read must set permissions contents: read. "
                    "That scope is enough; do not grant contents: write."
                )
    if FRESHNESS in text and not seen_in_step:
        problems.append(
            f"{filename}: {FRESHNESS} is outside the run script, "
            "so the call is not an authenticated read"
        )
    return problems


def _workflow_texts() -> list[tuple[str, str]]:
    return [
        (path.name, path.read_text()) for path in sorted(WORKFLOWS.glob("*.yml")) if path.is_file()
    ]


def _manual_guard(
    filename="deploy-manual.yml", job_name="deploy"
) -> tuple[str, dict[str, str], list[list[str]]]:
    text = (WORKFLOWS / filename).read_text()
    job = next(item for item in _jobs(text) if item["name"] == job_name)
    lines = job["lines"]
    assert isinstance(lines, list)
    steps = _steps(lines)
    guard = next(step for step in steps if FRESHNESS in "\n".join(step))
    env = {entry["name"]: entry["value"] for entry in _envs_at(guard, 8)}
    return _run_script(guard), env, steps


def test_repository_workflows_authenticate_every_main_freshness_read() -> None:
    calls = []
    problems = []
    for name, text in _workflow_texts():
        if FRESHNESS in text:
            calls.append(name)
        problems.extend(freshness_problems(name, text))
    assert problems == [], "\n".join(problems)
    assert calls == ["deploy-manual.yml", "release.yml"]

    text = (WORKFLOWS / "deploy-manual.yml").read_text()
    job = next(item for item in _jobs(text) if item["name"] == "deploy")
    lines = job["lines"]
    assert isinstance(lines, list)
    assert _permission_block(lines, 4) == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    script, env, steps = _manual_guard()
    assert "Require current main inside deployment lock" in "\n".join(steps[-2])
    assert env["GH_TOKEN"] == "${{ github.token }}"
    assert env["CANDIDATE"] == "${{ github.sha }}"
    assert "gh api" in script
    assert FRESHNESS_API in script
    assert "urlopen" not in script
    assert 'test "$current" = "$CANDIDATE"' in script
    deploy = "\n".join(steps[-1])
    assert "actions/deploy-pages@" in deploy
    assert "continue-on-error" not in deploy
    assert "continue-on-error" not in "\n".join(steps[-2])


def test_manual_freshness_read_fails_when_the_workflow_token_is_removed() -> None:
    text = (WORKFLOWS / "deploy-manual.yml").read_text()
    stripped = text.replace(
        "          GH_TOKEN: ${{ github.token }}\n          CANDIDATE:",
        "          CANDIDATE:",
        1,
    )
    assert stripped != text
    problems = freshness_problems("deploy-manual.yml", stripped)
    assert any("without authentication" in problem for problem in problems), problems


def test_unauthenticated_urllib_freshness_read_fails() -> None:
    problems = freshness_problems("sample.yml", UNAUTHENTICATED)
    assert any("without authentication" in problem for problem in problems), problems
    assert any("contents: read" in problem for problem in problems), problems
    assert any("contents: write" in problem for problem in problems), problems


def test_token_that_is_not_sent_on_the_request_still_fails() -> None:
    problems = freshness_problems("sample.yml", TOKEN_PRESENT_BUT_UNUSED)
    assert any("without authentication" in problem for problem in problems), problems


def test_gh_api_without_a_token_fails() -> None:
    problems = freshness_problems("sample.yml", GH_WITHOUT_TOKEN)
    assert any("without authentication" in problem for problem in problems), problems


def test_gh_api_with_gh_token_and_urllib_with_authorization_bearer_pass() -> None:
    assert freshness_problems("gh.yml", AUTHENTICATED_GH) == []
    assert freshness_problems("urllib.yml", AUTHENTICATED_URLLIB) == []


def test_contents_write_fails_even_when_the_read_sends_a_token() -> None:
    text = AUTHENTICATED_URLLIB.replace("contents: read", "contents: write", 1)
    problems = freshness_problems("sample.yml", text)
    assert any("contents: read" in problem and "contents: write" in problem for problem in problems)


def _run_guard(
    tmp_path: Path, *, remote_sha: str, gh_status: int, prewriter: bool = False
) -> tuple[subprocess.CompletedProcess[str], dict | None]:
    script, env_map, _steps = (
        _manual_guard("release.yml", "current-main") if prewriter else _manual_guard()
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gh"
    fake.write_text(FAKE_GH)
    fake.chmod(0o755)
    capture = tmp_path / "capture.json"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "GH_CAPTURE": str(capture),
        "GH_SHA": remote_sha,
        "GH_STATUS": str(gh_status),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for name, value in env_map.items():
        env[name] = (
            value.replace("${{ github.token }}", "workflow-token")
            .replace("${{ github.sha }}", EXPECTED_SHA)
            .replace("${{ inputs.commit }}", EXPECTED_SHA)
        )
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    record = json.loads(capture.read_text()) if capture.is_file() else None
    return result, record


@pytest.mark.parametrize(
    ("remote_sha", "gh_status", "expected_code"),
    [
        (EXPECTED_SHA, 0, 0),
        ("b" * 40, 0, 1),
        ("", 0, 1),
        (EXPECTED_SHA, 1, 1),
    ],
)
@pytest.mark.parametrize("prewriter", [False, True], ids=["pre-Pages", "pre-writer"])
def test_deploy_guard_aborts_when_main_moved_or_the_read_fails(
    tmp_path: Path, remote_sha: str, gh_status: int, expected_code: int, prewriter: bool
) -> None:
    result, record = _run_guard(
        tmp_path, remote_sha=remote_sha, gh_status=gh_status, prewriter=prewriter
    )
    assert result.returncode == expected_code, result.stderr
    assert record is not None, result.stderr
    assert record["token"] == "workflow-token"
    assert FRESHNESS_API in record["argv"]
    if gh_status != 0:
        assert "rate limit exceeded" in result.stderr
    assert "workflow-token" not in result.stdout
    assert "workflow-token" not in result.stderr
