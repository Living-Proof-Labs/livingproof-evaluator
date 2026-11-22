# SPDX-License-Identifier: Apache-2.0
"""Exercise exact release binding and delivery-only retry with local fixtures."""

import io
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

import pytest
from manual.delivery import edition, require_archive

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / ".github/workflows/deploy-manual.yml"
VERSION = "1.8.7"
TAG = f"v{VERSION}"


@pytest.mark.parametrize(
    "version,kind",
    [
        (None, "development"),
        (VERSION, "release"),
        ("1.8.7-pr.64.41.2", "preview"),
        ("1.8.7-main.42.1", "preview"),
    ],
)
def test_manual_edition_uses_the_planned_version(version, kind):
    assert edition(version) == kind


def test_no_guidance_tag_as_contract_version():
    with pytest.raises(ValueError):
        edition("v9.9.2")


@pytest.mark.parametrize(
    "changed",
    [
        None,
        "version",
        "source_commit",
        "run_id",
        "run_attempt",
        "source_dirty",
        "edition",
        "duplicate",
    ],
)
def test_integrity_of_sealed_manual(tmp_path, changed):
    path = tmp_path / "artifact.tar"
    identity = {
        "version": VERSION,
        "edition": "release",
        "source_commit": "a" * 40,
        "run_id": "12345",
        "run_attempt": "1",
        "source_dirty": False,
    }
    if changed and changed != "duplicate":
        identity[changed] = "unexpected value"
    with tarfile.open(path, "w:") as archive:
        content = json.dumps(identity).encode()
        entry = tarfile.TarInfo("./build.json")
        entry.size = len(content)
        for _ in range(2 if changed == "duplicate" else 1):
            archive.addfile(entry, io.BytesIO(content))
    arguments = (str(path), VERSION, "a" * 40, "12345", "1")
    if changed is None:
        require_archive(*arguments)
    else:
        with pytest.raises(ValueError):
            require_archive(*arguments)


def _git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.mark.parametrize(
    "case",
    [
        "first",
        "retry",
        "explicit-replay",
        "dispatch-prior-attempt",
        "dispatch-wrong-tag",
        "mutable",
        "future-attempt",
        "wrong-run",
        "no-tag",
        "wrong-sha",
        "no-release",
        "draft",
        "unpublished",
        "mismatch",
    ],
)
def test_real_published_release_guard_allows_only_exact_same_run(tmp_path, case):
    work = tmp_path / "repo"
    work.mkdir()
    _git(work, "init", "-q")
    _git(work, "config", "user.name", "Unit Test")
    _git(work, "config", "user.email", "fixture@example.invalid")
    _git(work, "commit", "--allow-empty", "-m", "fixture")
    commit = _git(work, "rev-parse", "HEAD")
    if case != "no-tag":
        _git(work, "tag", "-a", TAG, "-m", "fixture")
    if case == "wrong-sha":
        _git(work, "commit", "--allow-empty", "-m", "not the tagged fixture")
        commit = _git(work, "rev-parse", "HEAD")
    tool = work / "tools/manual/delivery.py"
    tool.parent.mkdir(parents=True)
    tool.write_bytes((ROOT / "tools/manual/delivery.py").read_bytes())
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'test "$GH_TOKEN" = fixture-read-token || exit 3\n'
        'test "$1 $2" = "api repos/fixture/evaluator/releases/tags/v1.8.7" || exit 4\n'
        'if [ "$GITHUB_RELEASE" = missing ]; then exit 22; fi\n'
        'printf "%s\\n" "$GITHUB_RELEASE"\n'
    )
    gh.chmod(0o755)
    release = json.dumps(
        {
            "tag_name": "v1.8.6" if case == "mismatch" else TAG,
            "draft": case == "draft",
            "immutable": case != "mutable",
            "prerelease": False,
            "published_at": None if case == "unpublished" else "2026-11-22T10:00:00Z",
        }
    )
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_TOKEN": "fixture-read-token",
        "GITHUB_REPOSITORY": "fixture/evaluator",
        "GITHUB_EVENT_NAME": (
            "workflow_dispatch"
            if case.startswith("dispatch-") or case == "explicit-replay"
            else "push"
        ),
        "REPLAY_TAG": "v1.8.6" if case == "dispatch-wrong-tag" else TAG,
        "VERSION": VERSION,
        "RELEASE_TAG": TAG,
        "SOURCE": commit,
        "GITHUB_SHA": commit,
        "PLAN_RUN": "99" if case == "wrong-run" else "100",
        "GITHUB_RUN_ID": "100",
        "PLAN_ATTEMPT": "3" if case == "future-attempt" else "1",
        "GITHUB_RUN_ATTEMPT": "2" if case in {"retry", "dispatch-prior-attempt"} else "1",
        "ARTIFACT_ID": "42",
        "GITHUB_RELEASE": "missing" if case == "no-release" else release,
    }
    section = DEPLOY.read_text().split(
        "- name: Require exact published stable tag and same-run build"
    )[1]
    script = re.search(r"        run: \|\n((?:          .*\n)+)", section).group(1)
    before = _git(work, "show-ref", "--tags") if case != "no-tag" else ""
    result = subprocess.run(
        ["bash", "-c", script], cwd=work, env=env, capture_output=True, check=False
    )
    assert (result.returncode == 0) == (case in {"first", "retry", "explicit-replay"}), (
        result.stderr
    )
    if before:
        assert _git(work, "show-ref", "--tags") == before
