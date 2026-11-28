"""Read-only account previews, served separately from the static Playground."""

import argparse
import json
import math
import os
import subprocess
import sys
import threading
import time
from collections import OrderedDict, deque
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .config import LOGIN, REPOSITORY, Config
from .github import GitHubError, GitHubUnavailable
from .growth import advance, stage, traits
from .normalize import collect


def utc_now():
    return datetime.now(UTC)


def collect_preview(login, repository, client, *, clock=utc_now):
    observed = clock()
    end = observed.date()
    snapshot = collect(
        Config(login, repository),
        end - timedelta(days=30),
        end,
        client,
        clock=lambda: clock().date(),
    )
    state = advance(snapshot)
    xp = sum(
        day["activity_xp_awarded"] + day["popularity_xp_awarded"]
        for day in state["days"].values()
    )
    return {
        "activity_end": end.isoformat(),
        "activity_start": snapshot["activity_start"],
        "counts": state["current_traits"],
        "excluded_repository": repository,
        "observed_at": observed.isoformat(),
        "schema_version": 1,
        "settings": {
            **traits(state["current_traits"]),
            "key": f"island-seed-v1:{state['subject']['id']}",
            "stage": stage(xp),
        },
        "subject": snapshot["subject"],
    }


def collect_bounded(login, repository, token, *, timeout=60):
    """End the entire collection at its deadline, including DNS and slow reads."""
    request = json.dumps(
        {"login": login, "repository": repository, "token": token}
    ).encode()
    with subprocess.Popen(
        [sys.executable, "-m", "github_island.preview_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        try:
            output, _ = process.communicate(request, timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise GitHubUnavailable("Preview collection deadline exceeded") from None
        if process.returncode or len(output) > 10000:
            raise GitHubUnavailable("Preview collection failed")
    try:
        result = json.loads(output)
    except (ValueError, UnicodeError):
        raise GitHubError("Invalid preview result") from None
    if not isinstance(result, dict):
        raise GitHubError("Invalid preview result")
    if "error" in result:
        failure = GitHubUnavailable if result["error"] == "unavailable" else GitHubError
        raise failure(
            "Preview collection failed", retry_after=result.get("retry_after")
        )
    return result


def valid_origin(value):
    try:
        parsed = urlsplit(value)
        return (
            bool(parsed.hostname)
            and parsed.port != 0
            and parsed.path == ""
            and not parsed.query
            and not parsed.fragment
            and "?" not in value
            and "#" not in value
            and not parsed.username
            and not parsed.password
            and not any(char.isspace() for char in value)
            and (
                parsed.scheme == "https"
                or (
                    parsed.scheme == "http"
                    and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
                )
            )
        )
    except ValueError:
        return False


class PreviewApp:
    """One-process WSGI service with bounded cache, concurrency, and quotas."""

    def __init__(
        self,
        token,
        repository,
        origin,
        *,
        clock=utc_now,
        monotonic=time.monotonic,
        collector=collect_bounded,
    ):
        parts = repository.split("/")
        if (
            len(parts) != 2
            or not LOGIN.fullmatch(parts[0])
            or not REPOSITORY.fullmatch(parts[1])
            or parts[1] in {".", ".."}
        ):
            raise ValueError("Invalid preview exclusion repository")
        if origin and not valid_origin(origin):
            raise ValueError("Invalid preview origin")
        self.token = token
        self.repository = repository
        self.origin = origin
        self.clock = clock
        self.monotonic = monotonic
        self.collector = collector
        self.cache = OrderedDict()
        self.attempts = deque()
        self.busy = False
        self.lock = threading.Lock()

    @staticmethod
    def error(code, message, status, retry=None):
        return status, {"error": {"code": code, "message": message}}, retry

    def lookup(self, login):
        with self.lock:
            now = self.monotonic()
            day = self.clock().date().isoformat()
            for key, (expires, _) in list(self.cache.items()):
                if expires <= now or key[1] != day:
                    del self.cache[key]
            key = (login.lower(), day)
            if key in self.cache:
                self.cache.move_to_end(key)
                return 200, self.cache[key][1], None
            if self.busy:
                return self.error(
                    "busy", "Another lookup is running. Try again shortly.", 503, 10
                )
            while self.attempts and self.attempts[0] <= now - 3600:
                self.attempts.popleft()
            minute = [stamp for stamp in self.attempts if stamp > now - 60]
            waits = []
            if len(minute) >= 2:
                waits.append(minute[0] + 60 - now)
            if len(self.attempts) >= 60:
                waits.append(self.attempts[0] + 3600 - now)
            if waits:
                return self.error(
                    "rate_limited",
                    "Lookup limit reached. Try again later.",
                    429,
                    max(1, math.ceil(max(waits))),
                )
            self.attempts.append(now)
            self.busy = True
        try:
            result = self.collector(login, self.repository, self.token)
            with self.lock:
                # A result may still be returned across a later midnight, but cannot
                # be cached as a new day's result. Its original dates stay visible.
                if self.clock().date().isoformat() == result["activity_end"]:
                    key = (login.lower(), result["activity_end"])
                    self.cache[key] = (self.monotonic() + 900, result)
                    while len(self.cache) > 128:
                        self.cache.popitem(last=False)
            return 200, result, None
        except GitHubError as error:
            if error.unavailable:
                return self.error(
                    "upstream_unavailable",
                    "GitHub is temporarily unavailable.",
                    503,
                    error.retry_after or 60,
                )
            return self.error(
                "lookup_failed", "Complete public activity could not be loaded.", 502
            )
        except ValueError:
            return self.error(
                "lookup_failed", "Complete public activity could not be loaded.", 502
            )
        except Exception:
            # Never echo upstream bodies, credentials, or tracebacks to visitors.
            return self.error(
                "unavailable", "Account lookup is temporarily unavailable.", 503, 60
            )
        finally:
            with self.lock:
                self.busy = False

    def dispatch(self, environ):
        if environ.get("PATH_INFO") != "/preview":
            return self.error("not_found", "Unknown endpoint.", 404)
        origin = environ.get("HTTP_ORIGIN")
        if origin and origin != self.origin:
            return self.error("origin_denied", "This origin is not allowed.", 403)
        method = environ.get("REQUEST_METHOD")
        if method == "OPTIONS":
            return 204, None, None
        if method != "GET":
            return self.error("method_not_allowed", "Use GET for account lookup.", 405)
        try:
            query = environ.get("QUERY_STRING", "")
            if len(query) > 128:
                raise ValueError("Query too long")
            params = parse_qs(
                query,
                keep_blank_values=True,
                strict_parsing=True,
                errors="strict",
                max_num_fields=1,
            )
            if set(params) != {"login"} or not LOGIN.fullmatch(params["login"][0]):
                raise ValueError("Invalid login")
        except (ValueError, UnicodeError):
            return self.error("invalid_login", "Enter a valid GitHub username.", 400)
        if (
            not self.token
            or not self.origin
            or any(char.isspace() for char in self.token)
        ):
            return self.error("unavailable", "Account lookup is not configured.", 503)
        return self.lookup(params["login"][0])

    def __call__(self, environ, start_response):
        status, payload, retry = self.dispatch(environ)
        body = (
            json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            if payload
            else b""
        )
        headers = [
            ("Cache-Control", "no-store"),
            ("Content-Length", str(len(body))),
            ("Content-Type", "application/json; charset=utf-8"),
            ("Vary", "Origin"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        if self.origin and environ.get("HTTP_ORIGIN") == self.origin:
            headers.extend(
                [
                    ("Access-Control-Allow-Methods", "GET, OPTIONS"),
                    ("Access-Control-Allow-Origin", self.origin),
                    ("Access-Control-Expose-Headers", "Retry-After"),
                ]
            )
        if status == 405:
            headers.append(("Allow", "GET, OPTIONS"))
        if retry:
            headers.append(("Retry-After", str(retry)))
        start_response(f"{status} {HTTPStatus(status).phrase}", headers)
        return [body]


def from_environment():
    return PreviewApp(
        os.environ.get("PREVIEW_GH_TOKEN", ""),
        os.environ.get("PREVIEW_REPOSITORY", "AndrewDongminYoo/github-island"),
        os.environ.get("PREVIEW_ORIGIN", ""),
    )


application = from_environment()


def main():
    parser = argparse.ArgumentParser(
        description="Run the loopback preview development API"
    )
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    class ThreadedServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format, *args):
            # Do not log requested usernames or query strings.
            pass

    with make_server(
        "127.0.0.1",
        args.port,
        application,
        server_class=ThreadedServer,
        handler_class=QuietHandler,
    ) as server:
        print(f"Preview development API: http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
