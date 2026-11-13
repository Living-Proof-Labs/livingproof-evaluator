# Verification and publication

This manual adopts the documentation recipe and brand from collaboration-guidelines
v7.8.2, resolved to `1470bd46deffd62d6badf568996225e56872258a`.
The two pre-existing guides remain canonical and keep their file names and headings.
Schemas and example JSON are rendered from the checked-out files; Task reference
comes from native `task --list --json` and `task --summary`.

```sh
task manual:setup
.venv-docs/bin/python -m playwright install chromium
task manual:build
task manual:verify
```

The build downloads the immutable shared brand and checks its SHA-256. It needs
public network access for that download. Browser setup may need operating-system
dependencies (`playwright install --with-deps chromium` on a supported CI host).
There is no published tooling image; the manual uses the existing repository's
prepared-host fallback (Ubuntu 24.04 in CI, Python 3.12 and Task 3.54.0), an explicit
local exception until image publication is separately undertaken.

Checks cover generated local links and fragments, source hashes, native Task
reference, brand application, search and result opening, a deep-link reload,
mobile navigation and theme persistence. External availability is a separate check. For an explicitly reported local browser
fallback, set `MANUAL_BROWSER_PATH` to an installed Chromium executable. CI uses
the browser downloaded by the locked Playwright version.
Contract tests run in the existing Verify workflow; this manual does not claim
fresh runtime results or measured software coverage. No executable feature suite
or released evaluator binary exists here. Historical rendered manuals are not maintained.

The Repository manual workflow retains HTML and individual JUnit checks for 14 days.
Its trusted main build alone uploads a Pages artifact. A separate deploy job has
Pages and identity-token write permissions and uses the github-pages environment;
it rejects stale main revisions within the deployment lock. PR code never deploys.
Before production, verify Pages uses GitHub Actions and github-pages permits only
main. Changes to security-sensitive settings require owner confirmation. This PR
changes no repository settings and does not merge or dispatch production.

Publication remains pending until the deployment URL, build.json source identity,
README journey, desktop/mobile/keyboard navigation, search and result opening,
deep-link reload and related-manual destinations are verified live. The README
therefore labels its source preview honestly. The organization directory is managed
separately. Current organization/manual/source directory links are a bounded
navigation exception to dependency pinning, not permission for floating guidance.
