"""Bounded HTTPS GraphQL transport with sanitized failures."""

import json
import math
import random
import time
import urllib.error
import urllib.request


class GitHubError(ValueError):
    """An API response cannot be trusted as collection evidence."""

    unavailable = False

    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class GitHubUnavailable(GitHubError):
    """The upstream service or this collection's request budget is unavailable."""

    unavailable = True


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def retry_after(headers):
    try:
        delay = (
            float(headers["retry-after"])
            if "retry-after" in headers
            else float(headers["x-ratelimit-reset"]) - time.time()
        )
        if math.isfinite(delay):
            return max(1, min(86400, math.ceil(delay)))
    except (KeyError, TypeError, ValueError):
        pass
    return None


class GraphQLClient:
    def __init__(
        self,
        token,
        opener=None,
        *,
        sleep=time.sleep,
        max_requests=1000,
        max_seconds=240,
    ):
        if not token or any(char.isspace() for char in token):
            raise GitHubError("A valid GH_TOKEN or GITHUB_TOKEN is required")
        self.token = token
        self.opener = opener or urllib.request.build_opener(NoRedirect()).open
        self.sleep = sleep
        self.max_requests = max_requests
        self.requests = 0
        self.deadline = time.monotonic() + max_seconds

    def __call__(self, query, variables):
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
                "User-Agent": "github-island",
            },
            method="POST",
        )
        for attempt in range(3):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise GitHubUnavailable("GitHub collection deadline exceeded")
            if self.requests >= self.max_requests:
                raise GitHubUnavailable("GitHub request budget exhausted")
            self.requests += 1
            delay = 2**attempt + random.random()
            try:
                with self.opener(request, timeout=min(30, remaining)) as response:
                    response_headers = {
                        key.lower(): value
                        for key, value in getattr(response, "headers", {}).items()
                    }
                    body = response.read(2 * 1024 * 1024 + 1)
                break
            except urllib.error.HTTPError as error:
                headers = error.headers or {}
                limited = error.code == 429 or (
                    error.code == 403
                    and (
                        headers.get("Retry-After") is not None
                        or headers.get("X-RateLimit-Remaining") == "0"
                    )
                )
                retryable = limited or 500 <= error.code < 600
                message = f"GitHub HTTP {error.code}; no data accepted"
                if limited:
                    try:
                        if headers.get("Retry-After") is not None:
                            delay = max(delay, float(headers["Retry-After"]))
                        elif headers.get("X-RateLimit-Reset") is not None:
                            delay = max(
                                delay, float(headers["X-RateLimit-Reset"]) - time.time()
                            )
                    except (TypeError, ValueError):
                        retryable = False
                error.close()
                if not retryable or attempt == 2 or not 0 <= delay <= 30:
                    failure = (
                        GitHubUnavailable
                        if limited or error.code >= 500
                        else GitHubError
                    )
                    raise failure(
                        message,
                        retry_after=retry_after(
                            {key.lower(): value for key, value in headers.items()}
                        ),
                    ) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise GitHubUnavailable(
                        "GitHub transport failed; no data accepted"
                    ) from None
            if delay >= self.deadline - time.monotonic():
                raise GitHubUnavailable("GitHub collection deadline exceeded")
            self.sleep(delay)
        if time.monotonic() >= self.deadline:
            raise GitHubUnavailable("GitHub collection deadline exceeded")
        if len(body) > 2 * 1024 * 1024:
            raise GitHubError("GitHub response exceeds response budget")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            raise GitHubError("GitHub returned invalid JSON") from None
        if isinstance(payload, dict) and payload.get("errors"):
            errors = payload["errors"]
            limited = (
                "retry-after" in response_headers
                or response_headers.get("x-ratelimit-remaining") == "0"
                or (
                    isinstance(errors, list)
                    and any(
                        isinstance(error, dict) and error.get("type") == "RATE_LIMITED"
                        for error in errors
                    )
                )
            )
            if limited:
                raise GitHubUnavailable(
                    "GitHub rate limit reached; no data accepted",
                    retry_after=retry_after(response_headers),
                )
        if not isinstance(payload, dict) or payload.get("errors"):
            raise GitHubError("GitHub GraphQL errors; no partial data accepted")
        if not isinstance(payload.get("data"), dict):
            raise GitHubError("GitHub response is missing data")
        return payload["data"]
