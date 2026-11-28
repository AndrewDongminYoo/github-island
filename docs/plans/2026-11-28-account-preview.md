# Account Preview Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task in the existing workspace.

**Goal:** Let a visitor preview an island from a GitHub username without signing in or supplying credentials.

**Architecture:** A bounded Python WSGI API reuses collection and bootstrap logic and returns scene settings.
GitHub Pages continues serving the existing Pyodide renderer and calls the separately hosted API.

**Tech Stack:** Python 3.12+, standard-library WSGI and unittest, browser JavaScript, Pyodide, GitHub Pages.

**Spec:** [Account preview](../specs/2026-11-28-account-preview.md), approved on 2026-11-28.

## Global Constraints

- Keep the package free of runtime dependencies and preserve existing CLI defaults.
- Use the last 30 completed UTC days and the existing public-only collector.
- Use a 60-second collection budget and at most 64 upstream requests, including retries.
- Cache successful results for 15 minutes, at most 128 entries, never across UTC midnight.
- Allow one active collection and at most two misses per minute and 60 per hour per application process.
- Keep the service credential on the server and the API URL in public build configuration.
- Implement in the existing workspace; commits, external configuration, and deployment are outside this execution.

## Review Focus

- Invalid or duplicated query parameters must not cause upstream requests.
- Failed, canceled, or superseded requests must preserve the user's current scene.
- Cache hits near midnight must not report yesterday's collection as today's result.
- Shared links must preserve account signal precision and the versioned identity seed.
- A malformed API response must not be partially applied or echoed as HTML.

## Task 1: Bounded preview service

**Files:** Create `src/github_island/preview.py` and `tests/test_preview.py`; modify `src/github_island/github.py` and `tests/test_github.py`.

**Interfaces:** `collect_preview(login, repository, client, *, clock)` returns a JSON-compatible version-one response with subject, activity bounds, observation timestamp, exclusion repository, raw counts, and settings.
`PreviewApp(token, repository, origin, *, clock, monotonic, client_factory)` is a WSGI callable.
`GraphQLClient` adds an optional `max_seconds=240` argument; temporary upstream failures remain subclasses of `GitHubError`.

- [x] Write transport tests for custom deadlines, late responses, and exhaustion classification; run `python -m unittest discover -s tests -p test_github.py -v` and observe failure before implementation.
- [x] Add the optional transport budget and sanitized unavailable errors; rerun the transport tests and expect all tests to pass.
- [x] Write service tests with the existing GraphQL fixture and injected clocks: exact bootstrap counts/stage/key, zero activity, partial data, malformed queries, quotas, expiry, midnight, concurrent misses, cache eviction, CORS, missing configuration, and secret sanitization.
- [x] Run `python -m unittest discover -s tests -p test_preview.py -v` before implementing the service and confirm the missing behavior.
- [x] Implement the service and a loopback-only threaded development entry point, with complete-response application and bounded shared state.
- [x] Rerun the service and transport tests and expect all tests to pass.

## Task 2: Static build and account interaction

**Files:** Modify `playground/index.html`, `tools/playground.py`, `tests/test_playground.py`, and `.github/workflows/pages.yml`; create `playground/account.js` and `tests/test_account.mjs`.

**Interfaces:** The build writes `config.json` with `{ "previewApi": "" }` or a validated API base URL.
The browser controller consumes the version-one service response and publishes validated settings through a callback.
It uses a generation counter and AbortController to prevent stale applications.

- [x] Write build tests proving safe API URL handling, optional configuration, asset copying, and the unchanged renderer-only Python bundle; run the playground test file and observe the missing configuration behavior.
- [x] Implement `build(output, preview_api="")`, emit public configuration, and read the API URL from the Pages build environment.
- [x] Write `node --test tests/test_account.mjs` tests for result validation, exact settings links, errors, cancellation, overlapping requests, and an unavailable API; observe failure before implementing the controller.
- [x] Implement the controller and connect an accessible username field, submission, cancellation, status, exact counts, and edited-result attribution to the existing page.
- [x] Preserve exact signal values in links and mark presets/manual edits independently from presentation changes.
- [x] Rerun the Python playground tests and Node tests and expect all tests to pass.

## Task 3: Documentation, browser checks, and final review

**Files:** Update `README.md` and `.github/workflows/ci.yml` to document and continuously test the feature; complete this plan's checkboxes after verification.

**Interfaces:** Existing README commands plus `node --test tests/test_account.mjs`; local static site and loopback preview API.

- [x] Document development startup, environment variables, Pages/API separation, single-process service limits, and the production prerequisites; remove the claim that account lookup sends nothing anywhere.
- [x] Run `python -m unittest discover -s tests -v`, `ruff check src tests tools`, `ruff format --check src tests tools`, and `node --test tests/test_account.mjs` with Python 3.12+.
- [x] Build the site and use a named browser session to exercise success, empty activity, invalid input, failure, loading/cancel, manual edits, SVG download, and settings-link reload, including narrow/light/dark layouts.
- [x] If an authorized server credential is already available, run one read-only live lookup without exposing it; otherwise report that live verification is unperformed.
- [x] Obtain one independent review of the complete diff, fix substantive findings with regression tests, and verify the final diff.
- [x] Report local results and deployment prerequisites without claiming the feature is publicly deployed.

## 2026-11-28: Added language settings

The user added language selection during implementation.
Extend Task 2 with `playground/i18n.js` and `tests/test_i18n.mjs`: English and Korean dictionaries, saved-preference/browser-language selection, storage-failure handling, and live page updates that preserve scene and request state.
Extend the build to copy that module and the Node verification command to `node --test tests/test_*.mjs`.
Task 3 includes browser checks of switching languages while a lookup is pending and retaining the selected language after reload.

## 2026-11-28: Review corrections during execution

Task 1 adds `src/github_island/preview_worker.py` and changes `PreviewApp`'s injected boundary from a transport factory to a complete collector.
Production uses `collect_bounded(login, repository, token, *, timeout=60)` to start one child process, send credentials through stdin, and kill and reap it at the deadline.
Tests inject a fixture collector for deterministic collection and use real child processes to verify timeout cleanup and the stdin protocol.
Transport regression tests cover disabled redirects and GraphQL rate-limit errors in HTTP 200 responses.
Task 2 rejects empty URL query/fragment delimiters and invalid ports, distinguishes Korean `ko` from Konkani `kok`, and separates account submission from the island key input.

## Verification results

Python 3.12.16: 265 unit tests passed.
Node.js: 9 controller and language tests passed.
Ruff lint and format checks passed, and the tracked diff has no whitespace errors.
Browser checks passed for account success, zero activity, invalid input, upstream failure, cancellation, language switching during lookup, manual edits during lookup, saved language, and exact SVG/settings preservation on link reload.
The account form was separated from other controls after reproducing unintended submission from the island key field.
A 390-pixel viewport had no horizontal overflow in light and dark themes.
The downloaded SVG matched the expected renderer bytes and was 76,710 bytes.
The published-bundle validator requires publication metadata and is not the validator for a generic Playground scene; the download was checked against the actual scene renderer instead.
A build without an API URL retained its renderer, controls, and language selector while disabling account lookup.
Cache expiry was tested at TTL and midnight boundaries; the 128-entry capacity is a defensive bound above the number reachable under the current TTL and lookup quotas.
The actual child-process entry point rejected an invalid credential without network access or credential disclosure.
No dedicated server credential was configured, so a live GitHub account lookup remains unverified.
No commit, external configuration change, or deployment was performed.
The browser session and both temporary development servers were stopped.

## 2026-11-28: Authorized deployment continuation

The user authorized API hosting and server credential configuration on AWS or Cloudflare.
Use AWS Lambda in `ap-northeast-2` with a Python 3.12 Function URL adapter, preserving the existing collector and subprocess deadline.
Use reserved concurrency 1, memory 256 MiB, function timeout 70 seconds, and seven-day log retention.
The Function URL owns CORS for the existing GitHub Pages origin; the application continues enforcing that origin.
The server token must be a dedicated public-data credential, not the operator's broad CLI token.

- [x] Add and test `src/github_island/lambda_preview.py` and deterministic `tools/lambda_bundle.py`.
- [x] Deploy the package to the verified personal AWS account and verify runtime, concurrency, timeout, and child-process execution.
- [x] Configure a dedicated GitHub credential and verify a live account result through the deployed endpoint.
- [x] Set the Pages API URL, publish the verified source changes, and verify the public browser flow.

### Deployment verification in progress

The `github-island-preview` Lambda function is active in `ap-northeast-2`, with the planned runtime, memory, timeout, concurrency, and log retention.
The Function URL returns 400 for duplicate login parameters, 403 for an unexpected origin, and 503 for the missing server credential.
Allowed-origin responses include the configured CORS header; the rejected origin receives none.
The repository's `PREVIEW_API_URL` variable points to the Function URL.
The deployment preparation passed 270 Python tests.
A dedicated GitHub credential is still missing, so live collection and its child process on Lambda remain unverified.
Source changes remain uncommitted and the updated Pages interface has not been published.

### 2026-11-28: Live collection and final deployment review

After the server credential was configured, the deployed endpoint collected `AndrewDongminYoo` successfully in 45 seconds.
The result covers 2026-10-29 through 2026-11-27 UTC and uses the `mature` stage.
A lowercase lookup returned the identical cached payload in 0.143 seconds.
The deployed package SHA-256 matched the locally built ZIP.
The final deployment review added regressions for GraphQL secondary limits identified by `Retry-After` and provider-generated HTTP 429 responses without an application error body.
Both now produce retry guidance and preserve the current scene.

### 2026-11-28: Public deployment completed

Implementation commit `5ee517b` passed [CI](https://github.com/AndrewDongminYoo/github-island/actions/runs/46133305403) and the [Pages deployment](https://github.com/AndrewDongminYoo/github-island/actions/runs/46133305375).
Python 3.12.16 passed 271 tests; Node passed 10 tests; Ruff lint and format checks passed.
The public HTML, JavaScript, configuration, and renderer module list matched the local build byte for byte.
The public Playground successfully loaded the account and rendered its island after switching to Korean while collection was running.
A concurrent request received AWS's 429 response with the allowed-origin CORS header.
The downloadable SVG was 108,449 bytes and matched the Python renderer's SHA-256.
Reloading the settings link preserved those exact SVG bytes and the saved language without making another account lookup.
