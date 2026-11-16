# SPDX-License-Identifier: Apache-2.0
"""The release workflow SHA must be the published commit of its tag comment.

Rivet's pin tests on this repository check shape and that the tag comment agrees
with the Renovate preset and AGENTS.md. They do not resolve the SHA, so a typo
or a leftover SHA from an older tag still passes. Offline cases use a fake
GitHub; LIVINGPROOF_NETWORK=1 checks the real release (set GITHUB_TOKEN to
avoid the anonymous rate limit).
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest

from test_release_workflow import RELEASE, _guidelines_pins

API = "https://api.github.com/repos/Living-Proof-Labs/collaboration-guidelines"


def _problems(sha: str, tag: str, get) -> list[str]:
    found: list[str] = []
    release = json.loads(get(f"{API}/releases/tags/{tag}"))
    if release.get("tag_name") != tag or release.get("draft") or release.get("prerelease"):
        found.append(f"{tag} is not a published stable release")
    commit = json.loads(get(f"{API}/commits/{tag}"))["sha"]
    if commit != sha:
        found.append(f"{tag} is commit {commit}, workflow pins {sha}")
    return found


def _get_from(pages):
    def get(url):
        body = pages[url]
        return body if isinstance(body, bytes) else body.encode()

    return get


V940 = ("v9.4.0", "dac1f0ad5454d03107a0d71cd953a6d08244511b")
V920 = ("v9.2.0", "8c8155ec9db30dbe19ce5c2a71cf10f3f71271b0")


def fake_github(*releases, draft=()):
    pages = {}
    for tag, commit in releases:
        pages[f"{API}/releases/tags/{tag}"] = json.dumps(
            {"tag_name": tag, "draft": tag in draft, "prerelease": False}
        )
        pages[f"{API}/commits/{tag}"] = json.dumps({"sha": commit})
    return _get_from(pages)


def test_a_sha_that_matches_the_published_tag_passes():
    sha, tag = V940[1], V940[0]
    assert _problems(sha, tag, fake_github(V920, V940)) == []


def test_a_last_hex_typo_is_reported():
    typo = V940[1][:-1] + "c"
    found = _problems(typo, V940[0], fake_github(V920, V940))
    assert found == [f"v9.4.0 is commit {V940[1]}, workflow pins {typo}"]


def test_a_stale_sha_from_an_older_tag_is_reported():
    found = _problems(V920[1], V940[0], fake_github(V920, V940))
    assert found == [f"v9.4.0 is commit {V940[1]}, workflow pins {V920[1]}"]


def test_a_draft_release_is_refused():
    found = _problems(V940[1], V940[0], fake_github(V940, draft={"v9.4.0"}))
    assert found == ["v9.4.0 is not a published stable release"]


@pytest.mark.skipif(not os.environ.get("LIVINGPROOF_NETWORK"), reason="set LIVINGPROOF_NETWORK=1")
def test_workflow_sha_is_the_published_tag_commit():
    pins = _guidelines_pins(RELEASE.read_text())
    assert len(pins) == 1
    sha, tag = pins[0]
    token = os.environ.get("GITHUB_TOKEN")

    def get(url):
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"} if token else {}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()

    assert _problems(sha, tag, get) == []
