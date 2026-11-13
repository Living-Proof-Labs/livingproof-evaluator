# SPDX-License-Identifier: Apache-2.0
import functools
import hashlib
import json
import os
import threading
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
SITE = ROOT / "artifacts/manual/html"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag in ("script", "img") and "src" in attrs:
            self.links.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.links.append(attrs["href"])


def test_generated_links_and_fragments():
    pages = {}
    for path in SITE.rglob("*.html"):
        parser = Links()
        parser.feed(path.read_text())
        pages[path.resolve()] = parser
    assert len(pages) >= 10
    for path, parser in pages.items():
        for link in parser.links:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            if url.path.startswith("/livingproof-evaluator/"):
                target = (
                    SITE / unquote(url.path.removeprefix("/livingproof-evaluator/"))
                ).resolve()
            else:
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
            if target.is_dir():
                target /= "index.html"
            assert target.is_relative_to(SITE.resolve()), (path, link)
            assert target.exists(), (path, link)
            if url.fragment and target in pages:
                assert unquote(url.fragment) in pages[target].ids, (path, link)


def test_source_identity_and_actual_tasks():
    record = json.loads((SITE / "build.json").read_text())
    for path, digest in record["sources"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    tasks = (SITE / "tasks.html").read_text()
    assert "manual:verify" in tasks and "tools/manual/build.py" in tasks
    assert record["guidelines_baseline"] == "v7.8.2"
    home = (SITE / "index.html").read_text()
    assert f"/tree/{record['source_commit']}" in home
    assert "Docs: development" in home


@pytest.fixture(scope="module")
def base_url():
    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            prefix = "/livingproof-evaluator/"
            if path.startswith(prefix):
                path = "/" + path[len(prefix) :]
            return super().translate_path(path)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(SITE)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/livingproof-evaluator/"
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("MANUAL_BROWSER_PATH"))
        yield browser
        browser.close()


def test_browser_search_and_deep_link(browser, base_url):
    page = browser.new_page()
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    page.goto(base_url)
    page.keyboard.press("/")
    page.get_by_role("combobox", name="Search", exact=True).fill("evaluator descriptor")
    result = page.locator('a[role="option"]').first
    result.wait_for(state="visible")
    result.click()
    page.wait_for_url("**/*.html*")
    page.reload()
    assert page.locator("main").inner_text()
    page.goto(base_url + "docs/evaluator-descriptor.html#title")
    page.reload()
    assert page.locator("#title").is_visible()
    assert (
        page.get_by_role("link", name="Documentation home", exact=True).first.get_attribute("href")
        == "https://docs.livingprooflabs.com/"
    )
    assert not failures
    page.close()


def test_browser_mobile_navigation_and_theme(browser, base_url):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(base_url)
    page.locator('label.md-header__button[for="__drawer"]').click()
    page.get_by_role("link", name="Contribute", exact=True).first.click()
    page.wait_for_url("**/docs/contribute.html")
    page.locator("h1").filter(has_text="Contribute").wait_for(state="visible")
    page.locator('label[title="Switch to dark mode"]').click()
    page.reload()
    assert page.locator("body").get_attribute("data-md-color-scheme") == "slate"
    page.close()


def test_shared_brand():
    record = json.loads((SITE / "build.json").read_text())
    assert (
        hashlib.sha256((SITE / "assets/brand.css").read_bytes()).hexdigest()
        == record["brand"]["sha256"]
    )
    for path in SITE.rglob("*.html"):
        if path.name == "404.html":
            continue
        html = path.read_text()
        assert "assets/brand.css" in html
        assert 'data-md-color-primary="indigo"' not in html
