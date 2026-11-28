# Account preview in the Playground

Status: approved on 2026-11-28; implemented and publicly deployed, with verification recorded in the [implementation plan](../plans/2026-11-28-account-preview.md#2026-11-28-public-deployment-completed).

## Intent and approved direction

A visitor enters a GitHub username and sees an island grown from that account's public activity, without signing in or supplying a token.
The user approved adding a small server-side lookup API alongside the existing static Playground.
The technical choices below are proposed implementation decisions, not additional user requirements.

The source of the current behavior is [README](../../README.md#playground), [the collector](../../src/github_island/normalize.py), and [growth reconciliation](../../src/github_island/growth.py).

## Result and boundaries

The result represents a new island bootstrapped from the last 30 completed UTC days.
It is not a reconstruction of an account's lifetime growth or an already published island.
Stars and forks are observed at collection time.
Show the account, activity dates, observation time, and the bootstrap explanation next to the result.

Keep the current renderer, activity mapping, presets, sliders, SVG download, and settings links.
Do not add account registration, OAuth, persistent growth histories, automatic publication, a database, or a second renderer.
Do not change the image or regenerate example SVGs.

## Approaches

The selected direction is a server-side lookup followed by rendering in the existing browser runtime.
This keeps credentials out of the page and supports the existing public-activity collection rules.
A browser-only approximation would avoid a service but would require different collection semantics.
Asking visitors for a personal token would preserve authenticated access but add friction to the first-use experience.
Those alternatives were not selected; only the server-side direction has user approval.

Use a small Python WSGI application that imports the existing collector and growth functions.
This avoids porting the pagination, UTC boundary workaround, daily review collection, and growth rules to another language.
The package remains free of runtime dependencies.
A production WSGI host is an operational requirement, not a new renderer dependency.
The implementation will provide a loopback-only development entry point; that server is not the production hosting recommendation, consistent with the [Python WSGI reference documentation](https://docs.python.org/3.12/library/wsgiref.html).

## Account lookup contract

Expose `GET /preview?login=USERNAME` and accept exactly one login parameter.
Validate the username with the existing `config.LOGIN` grammar before making a GitHub request.
Do not accept a token, GraphQL query, target URL, date range, or arbitrary repository from the visitor.
Resolve GitHub identity and construct the rendering key as `island-seed-v1:{node_id}`, including the existing seed-version prefix used by published islands.

The server fixes the exclusion repository through deployment configuration, initially `AndrewDongminYoo/github-island`.
Return that repository in result metadata and explain that activity there is omitted.
A visitor's eventual publication can differ if they configure another exclusion repository.

Run `normalize.collect` for the last 30 completed UTC days and `growth.advance` with no previous state.
Compute the stage from the reconciled XP and normalized signals with the existing growth functions, following the existing draw command.
Return only a versioned result containing the canonical account identity, window, observation timestamp, excluded repository, raw signal counts, stage, and normalized signals.
Do not return the snapshot, per-repository records, daily records, credentials, or upstream error bodies.

Retain all current public-only filtering and collection completeness checks.
Only apply a complete result; a failed or truncated lookup must never become an empty island.
The existing collector's UTC rollover check remains active.
Preserve current CLI defaults when adding configurable preview time and request limits to the transport.

## Service limits and credential boundary

Read a dedicated public-data GitHub credential from server environment configuration.
Never include it in site assets, responses, URLs, exception messages, or request logs.
Do not enable lookup if required configuration is missing.

Use a 60-second collection deadline and at most 64 upstream requests per cache miss, counting retries.
These are initial limits; an account that exceeds them receives an explicit unavailable result rather than partial counts.
Bound each upstream response using the existing transport limit.

Cache successful results for 15 minutes in memory, with at most 128 entries.
Key the cache by normalized username, UTC date, and exclusion repository.
Expire entries at UTC midnight even if their TTL has not elapsed.
Use a single in-flight collection slot and reject additional cache misses promptly with a retry hint.
Limit cache misses globally to two per minute and 60 per hour, including failed collection attempts.
Cache hits do not spend that collection allowance.
Use a bounded cache with deterministic eviction and synchronize cache and limiter access across request threads.

The first production deployment must run one application process and one instance because these limits are in memory.
Do not claim that these limits protect a deployment with multiple processes or replicas.
Restarting the process resets them; enforce a provider-side request limit before exposing the endpoint publicly.
Production requires HTTPS and a configured exact Playground origin for CORS.
CORS is a browser access rule, not authentication or abuse protection.
Do not use incoming forwarded headers to construct trusted origins or URLs.

Map malformed input to 400, unsupported methods to 405, application quotas to 429, incomplete upstream responses to 502, and temporary service unavailability or upstream exhaustion to 503.
Return stable error codes and short sanitized messages, with `Retry-After` where applicable.
Distinguish a confirmed absent user from transport or permission failures; never infer absence from a generic GraphQL error.
If the current collector cannot identify absence safely, use a generic lookup failure rather than reporting a false 404.

## Playground behavior

Add a labeled username input and a `Preview my island` action before the existing presets.
Reuse the current page styling; this is a functional addition, not a visual redesign.
Make submission work with the keyboard and announce loading, success, and failure through a live status region.
Keep account lookup errors separate from Python runtime and rendering errors.

Keep the existing island visible while loading and after a failed lookup.
Disable duplicate submission while a lookup is pending and let the visitor cancel it locally.
Canceling a browser request does not promise to cancel an upstream collection already running.
Associate each lookup with a request generation so canceled or superseded responses cannot overwrite newer state.
Changing a signal, stage, key, or preset during lookup cancels that pending application and invalidates its request generation.
Preserve the later manual edit even if the network response subsequently arrives.
Changing poster presentation alone does not cancel lookup.
Apply the validated account result atomically after the renderer is ready.

After success, set the six signals, growth stage, and island key from the response.
Show exact collected counts separately from the existing approximate slider labels.
Retain the current poster preference.
Manual changes to signals, stage, or key mark the scene as an edited preview; changing only poster presentation does not change its activity provenance.
Presets clear the account-result attribution.

Copy link continues to share the exact current scene settings without an automatic account lookup on opening the link.
Preserve the full numeric precision of normalized signals when writing new settings links instead of the current two-decimal serialization.
Continue accepting existing two-decimal links and keep the slider's existing step for manual input.
Account results must not be rounded to slider steps before rendering; compare the scene before and after a shared-link reload.
Do not encode tokens or imply that a settings link is a live account result.
Downloading the SVG continues to use the locally rendered image.
Update the current claim that nothing is sent anywhere: entering an account sends that username to the lookup service, while rendering and slider changes remain local.

## Build and deployment

Keep GitHub Pages as the static host.
Have `tools/playground.py` write a small public configuration file containing the optional API base URL.
Allow only HTTPS production URLs and an explicit loopback HTTP development exception.
An empty API URL disables account lookup with a clear availability message while preserving the existing Playground.
Do not accept an API URL from a query parameter or fragment.
Pass the API URL into the Pages build through repository configuration; it is not a secret.

Production hosting, the service URL, credential provisioning, and the provider-side request limit require separate approval and verification before deployment.
Do not deploy or change external account configuration without that approval.
The feature is locally complete only after both API and browser acceptance checks pass, and publicly available only after a deployed end-to-end lookup succeeds.

## Acceptance checks

Use deterministic GraphQL fixtures to prove the API produces the same signals, stage, and identity key as the existing collect, bootstrap, and draw pipeline.
Cover UTC boundaries, daily review deduplication, public-only filtering, incomplete pagination, absent users, upstream throttling, and exhausted budgets.
Use an injected clock to test cache expiry, midnight invalidation, global quotas, and busy-service behavior without sleeps.
Verify that errors and static build output never contain a sentinel credential.

In a real browser, check successful lookup, a zero-activity account fixture, invalid input, failed lookup, loading and cancellation, response races, manual edits, download, and settings-link reload.
Check keyboard submission and a narrow viewport with the current light and dark themes.
If an authorized server credential is available, additionally perform one read-only live lookup and report whether it succeeded.
Fixture success alone is not evidence that a production credential or deployment works.

Run the README's Python unit tests, Ruff lint, and Ruff format check in Python 3.12 or later.
Build the static site and verify the credential-free configuration and unchanged renderer module boundary.
Document any live-service or deployment verification that remains blocked.

## 2026-11-28: Language selection added to scope

The user requested language settings while implementation was underway.
Support English and Korean in the existing Playground and the new account flow without adding a localization dependency.
Use a valid saved preference first, otherwise Korean for a Korean browser language and English for other languages.
Remember explicit choices in local storage, but continue working if storage is unavailable.
Changing language preserves the scene, account attribution, and pending lookup.
Translate visible labels, hints, counts, loading and failure states, accessibility labels, and document title, and update the document language.
Keep SVG rendering and identity keys language-independent.
Language preference is local and does not alter scene-sharing parameters.

## 2026-11-28: Review corrections

A socket-operation timeout does not bound a complete response that keeps sending bytes.
Run each uncached collection in one child Python process, pass credentials through stdin, and kill and reap the process at the 60-second deadline before releasing the collection slot.
The production host must support child processes; the one-process constraint above refers to the WSGI server, with at most one collection child in addition.
Disable upstream redirects to keep authorization at the fixed GitHub endpoint and count every request.
Treat GraphQL rate-limit errors inside HTTP 200 responses as temporary unavailability and retain a bounded retry hint.
Reject malformed ports and even empty query or fragment delimiters in API configuration.
