# Adapted from collaboration-guidelines v7.8.2 tools/manual/build.py.
# SPDX-License-Identifier: Apache-2.0
"""Render allowlisted repository Markdown and actual Task information."""

import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
from importlib.metadata import version as installed_version
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml
from delivery import edition

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/manual"
REPO = "https://github.com/Living-Proof-Labs/livingproof-evaluator"
GUIDELINES = "https://github.com/Living-Proof-Labs/collaboration-guidelines"
BASELINE = "v7.8.2"
BASELINE_SHA = "1470bd46deffd62d6badf568996225e56872258a"


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def build():
    head = run("git", "rev-parse", "HEAD")
    commit = os.environ.get("SOURCE_COMMIT") or head
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Expected an exact source commit")
    dirty_value = os.environ.get("SOURCE_DIRTY")
    if dirty_value is not None and dirty_value not in ("true", "false"):
        raise ValueError("SOURCE_DIRTY must be true or false")
    dirty = (
        dirty_value == "true"
        if dirty_value is not None
        else bool(run("git", "status", "--porcelain"))
    )
    version = os.environ.get("MANUAL_VERSION") or None
    kind = edition(version)
    if version and (commit != head or dirty or run("git", "status", "--porcelain")):
        raise ValueError("Versioned manuals require the exact clean checkout")
    docs_label = (
        f"Docs: v{version}"
        if kind == "release"
        else f"Docs: preview {version}"
        if kind == "preview"
        else "Docs: development"
    )
    repo_label = f"Source · v{version}" if kind == "release" else "Source · development"
    context = (
        f"Documentation version **{version}**. The matching [source release]({REPO}/releases/tag/v{version}) "
        "is the contract version, not an evaluator implementation or package."
        if kind == "release"
        else f"Documentation preview **{version}**. This is not a release."
        if kind == "preview"
        else "This is development documentation, not a package release."
    )
    source = OUT / "source"
    if source.exists():
        shutil.rmtree(source)
    source.mkdir(parents=True)
    paths = ["README.md", "AGENTS.md", "LICENSE"]
    paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "docs").glob("*.md"))]
    mapping = {p: p for p in paths}
    mapping["README.md"] = "overview.md"
    mapping["docs/index.md"] = "index.md"
    mapping["LICENSE"] = "LICENSE.md"
    record = {
        "source_commit": commit,
        "source_dirty": dirty,
        "version": version,
        "edition": kind,
        "docs_label": docs_label,
        "repo_label": repo_label,
        "run_id": os.environ.get("GITHUB_RUN_ID") or None,
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT") or None,
        "guidelines_baseline": BASELINE,
        "guidelines_baseline_commit": BASELINE_SHA,
        "generator": "zensical==" + installed_version("zensical"),
        "workflow_run": (
            REPO + "/actions/runs/" + os.environ["GITHUB_RUN_ID"]
            if os.environ.get("GITHUB_RUN_ID")
            else None
        ),
        "sources": {},
    }
    source_link = REPO + "/tree/" + commit
    for path, destination in mapping.items():
        text = (ROOT / path).read_text()
        record["sources"][path] = hashlib.sha256(text.encode()).hexdigest()

        def rewrite(match, path=path, destination=destination):
            target = match[1]
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                return match[0]
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), url.path))
            if resolved in mapping:
                relative = posixpath.relpath(
                    mapping[resolved], posixpath.dirname(destination) or "."
                )
                return "](" + urlunsplit(("", "", relative, url.query, url.fragment)) + ")"
            if not (ROOT / resolved).exists():
                raise ValueError(f"Missing source link: {path}: {target}")
            return (
                "]("
                + REPO
                + "/blob/"
                + commit
                + "/"
                + resolved
                + (("#" + url.fragment) if url.fragment else "")
                + ")"
            )

        text = re.sub(r"\]\(([^)\s]+)\)", rewrite, text)
        target = source / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        version = posixpath.relpath("version.md", posixpath.dirname(destination) or ".")
        license_path = posixpath.relpath("LICENSE.md", posixpath.dirname(destination) or ".")
        text += (
            f"\n\n---\n\n[Documentation home](https://docs.livingprooflabs.com/) · "
            f'[{docs_label}]({source_link} "{commit}") · '
            f"[Version and source]({version}) · [Help / report an issue]({REPO}/issues) · "
            f"[License]({license_path})\n"
        )
        target.write_text(text)
    task_data = json.loads(run("task", "--list", "--json"))
    tasks = [
        "# Contributor tasks",
        "",
        "Generated from this repository’s real Taskfile.",
        "Run directly with Python 3.12, uv and Task 3.54.0 in the prepared environment.",
        "There is no Docker wrapper or published tooling image in this repository.",
        "",
    ]
    for task in task_data["tasks"]:
        tasks += [
            f"## {task['name']}",
            "",
            "```text",
            run("task", "--summary", task["name"]),
            "```",
            "",
        ]
    (source / "tasks.md").write_text("\n".join(tasks))
    record["sources"]["Taskfile.yml"] = hashlib.sha256(
        (ROOT / "Taskfile.yml").read_bytes()
    ).hexdigest()
    contracts = [
        "# Contracts",
        "",
        "Generated verbatim from the schemas and examples in this revision.",
        "",
    ]
    for directory in ("schema", "examples"):
        for path in sorted((ROOT / directory).rglob("*.json")):
            relative = str(path.relative_to(ROOT))
            contracts += [
                f"## {relative}",
                "",
                f"[Source]({REPO}/blob/{commit}/{relative})",
                "",
                "```json",
                path.read_text().strip(),
                "```",
                "",
            ]
            record["sources"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    (source / "contracts.md").write_text("\n".join(contracts))
    lock = json.loads((ROOT / "docs-brand.lock.json").read_text())
    from urllib.request import urlopen

    url = f"https://raw.githubusercontent.com/{lock['repository']}/{lock['commit']}/{lock['path']}"
    with urlopen(url, timeout=30) as response:
        brand = response.read()
    if hashlib.sha256(brand).hexdigest() != lock["sha256"]:
        raise ValueError("Docs brand checksum mismatch")
    (source / "assets").mkdir()
    (source / "assets/brand.css").write_bytes(brand)
    record["brand"] = lock
    (source / "build.json").write_text(json.dumps(record, indent=2) + "\n")
    (source / "version.md").write_text(
        f"# Version and source\n\n{context} "
        f"Historical rendered manuals are not maintained; see the [source tags]({REPO}/tags).\n\n"
        f'[{docs_label}]({source_link} "{commit}"); dirty checkout: **{str(dirty).lower()}**. '
        "A dirty preview has changes beyond that commit; source hashes below identify its inputs.\n\n"
        f"Recipe baseline: [{BASELINE}]({GUIDELINES}/tree/{BASELINE}), resolved to `{BASELINE_SHA}`. "
        "This is a released guidance dependency, not the version of this evaluator contract manual. "
        f"[Published guidelines releases]({GUIDELINES}/releases) are separate.\n\n"
        "```json\n" + json.dumps(record, indent=2) + "\n```\n\n[Build record](build.json)\n"
    )
    config = yaml.safe_load((ROOT / "tools/manual/mkdocs.yml").read_text())
    config.update(
        docs_dir="source",
        site_dir="html",
        repo_url=source_link,
        repo_name=repo_label,
    )
    (OUT / "mkdocs.yml").write_text(yaml.safe_dump(config, sort_keys=False))
    subprocess.run(
        [sys.executable, "-m", "zensical", "build", "--clean", "-f", str(OUT / "mkdocs.yml")],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    build()
