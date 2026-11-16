# SPDX-License-Identifier: Apache-2.0
"""Playwright pin agreement and driver runtime libraries (Vera review of #23).

living-proof-labs.github.io#52 showed Playwright 1.65's bundled Node driver needs
libatomic.so.1; a host without it fails before any browser test runs. This checks the
driver's shared libraries resolve on the host running the manual checks, and that the
requirements pin, the hash lock and the installed package name one version.
"""

import importlib.metadata
import re
import shutil
import subprocess
import sys
from pathlib import Path

import playwright
import pytest

ROOT = Path(__file__).resolve().parents[3]
MANUAL = ROOT / "tools/manual"


def pinned(path, pattern):
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"no playwright pin in {path.name}"
    return match.group(1)


def test_requirements_lock_and_installed_playwright_agree():
    wanted = pinned(MANUAL / "requirements.in", r"^playwright==(\S+)\s*$")
    locked = pinned(MANUAL / "requirements.lock", r"^playwright==(\S+) \\$")
    assert wanted == locked
    assert importlib.metadata.version("playwright") == wanted


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="ldd check is Linux only")
@pytest.mark.skipif(shutil.which("ldd") is None, reason="ldd is not installed")
def test_playwright_driver_shared_libraries_resolve():
    node = Path(playwright.__file__).resolve().parent / "driver" / "node"
    assert node.is_file(), f"missing Playwright driver at {node}"
    result = subprocess.run(["ldd", str(node)], capture_output=True, text=True, check=False)
    missing = [line.strip() for line in result.stdout.splitlines() if "not found" in line]
    assert not missing, f"Playwright driver libraries not found: {missing}"
