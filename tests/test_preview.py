import contextlib
import io
import json
import subprocess
import sys
import threading
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

from test_normalize import FixtureClient, page

from github_island.github import GitHubError, GitHubUnavailable
from github_island.preview import PreviewApp, collect_preview


class DeadlineTests(unittest.TestCase):
    def test_worker_runs_the_existing_collector_and_sanitizes_throttling(self):
        from github_island import preview_worker

        payload = json.dumps(
            {"login": "octocat", "repository": "owner/island", "token": "SENTINEL"}
        ).encode()
        for failure in (None, GitHubUnavailable("SENTINEL", retry_after=300)):
            output = io.StringIO()
            with (
                patch("sys.stdin", io.TextIOWrapper(io.BytesIO(payload))),
                patch(
                    "github_island.preview_worker.GraphQLClient",
                    return_value=FixtureClient(),
                    side_effect=failure,
                ),
                contextlib.redirect_stdout(output),
            ):
                preview_worker.main()
            response = json.loads(output.getvalue())
            self.assertNotIn("SENTINEL", output.getvalue())
            if failure:
                self.assertEqual(response, {"error": "unavailable", "retry_after": 300})
            else:
                self.assertEqual(response["settings"]["key"], "island-seed-v1:U1")
                self.assertEqual(response["counts"]["reviews"], 30)

    def test_collection_is_killed_and_reaped_at_total_deadline(self):
        from github_island import preview

        children = []
        real_popen = subprocess.Popen

        def sleeping_child(command, **kwargs):
            child = real_popen(
                [sys.executable, "-c", "import time; time.sleep(30)"], **kwargs
            )
            children.append(child)
            return child

        with patch(
            "github_island.preview.subprocess.Popen", side_effect=sleeping_child
        ):
            with self.assertRaises(GitHubUnavailable):
                preview.collect_bounded(
                    "octocat", "owner/island", "SENTINEL", timeout=0.1
                )
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_worker_result_and_secret_stdin_protocol(self):
        from github_island import preview

        real_popen = subprocess.Popen

        def child(command, **kwargs):
            self.assertNotIn("SENTINEL", " ".join(command))
            program = (
                "import json,sys; r=json.load(sys.stdin); "
                "print(json.dumps({'subject': r['login'], "
                "'safe': r['token']=='SENTINEL'}))"
            )
            return real_popen([sys.executable, "-c", program], **kwargs)

        with patch("github_island.preview.subprocess.Popen", side_effect=child):
            self.assertEqual(
                preview.collect_bounded("octocat", "owner/island", "SENTINEL"),
                {"subject": "octocat", "safe": True},
            )


class Clock:
    def __init__(self):
        self.value = datetime(2026, 11, 28, 12, tzinfo=UTC)
        self.seconds = 0

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)
        self.seconds += seconds


def request(app, query="login=octocat", *, method="GET", origin=None, path="/preview"):
    environ = {}
    setup_testing_defaults(environ)
    environ.update(PATH_INFO=path, QUERY_STRING=query, REQUEST_METHOD=method)
    if origin:
        environ["HTTP_ORIGIN"] = origin
    response = []
    body = b"".join(
        app(environ, lambda status, headers: response.extend([status, headers]))
    )
    return (
        int(response[0].split()[0]),
        dict(response[1]),
        json.loads(body) if body else None,
    )


class CollectionTests(unittest.TestCase):
    def test_bootstrap_matches_public_collection_counts_and_identity_seed(self):
        result = collect_preview(
            "octocat",
            "owner/island",
            FixtureClient(),
            clock=lambda: datetime(2026, 11, 28, 12, tzinfo=UTC),
        )
        self.assertEqual(
            result["counts"],
            {
                "forks": 1,
                "issues": 1,
                "outside": 0,
                "prs": 1,
                "reviews": 30,
                "stars": 3,
            },
        )
        self.assertEqual(result["activity_start"], "2026-10-29")
        self.assertEqual(result["activity_end"], "2026-11-28")
        self.assertEqual(result["excluded_repository"], "owner/island")
        self.assertEqual(result["settings"]["key"], "island-seed-v1:U1")
        self.assertEqual(result["settings"]["stage"], "sprout")
        self.assertAlmostEqual(result["settings"]["prs"], 0.20184908658209985)

    def test_zero_activity_is_a_successful_seed(self):
        client = FixtureClient()

        def empty(query, variables, user):
            if "repositories" in user:
                user["repositories"] = page()
            for key in user.get("contributionsCollection", {}):
                user["contributionsCollection"][key] = page()
            return user

        client.transform = empty
        result = collect_preview(
            "octocat",
            "owner/island",
            client,
            clock=lambda: datetime(2026, 11, 28, tzinfo=UTC),
        )
        self.assertEqual(set(result["counts"].values()), {0})
        self.assertEqual(result["settings"]["stage"], "seed")

    def test_midnight_during_collection_fails_closed(self):
        moments = iter(
            [
                datetime(2026, 11, 28, 23, 59, tzinfo=UTC),
                datetime(2026, 11, 28, 23, 59, tzinfo=UTC),
                datetime(2026, 11, 29, tzinfo=UTC),
            ]
        )
        with self.assertRaisesRegex(ValueError, "UTC date changed"):
            collect_preview(
                "octocat", "owner/island", FixtureClient(), clock=lambda: next(moments)
            )


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.created = []
        self.factory = self.make_client
        self.app = PreviewApp(
            "SENTINEL-TOKEN",
            "owner/island",
            "https://example.test",
            clock=lambda: self.clock.value,
            monotonic=lambda: self.clock.seconds,
            collector=lambda login, repository, token: collect_preview(
                login,
                repository,
                self.factory(token, max_requests=64, max_seconds=60),
                clock=lambda: self.clock.value,
            ),
        )

    def make_client(self, token, **kwargs):
        self.assertEqual(kwargs, {"max_requests": 64, "max_seconds": 60})
        client = FixtureClient()
        client.transform = lambda query, variables, user: {
            **user,
            "login": variables["login"],
        }
        self.created.append(client)
        return client

    def test_valid_response_and_exact_cors_origin(self):
        code, headers, body = request(self.app, origin="https://example.test")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "https://example.test")
        self.assertEqual(body["schema_version"], 1)
        self.assertNotIn("SENTINEL-TOKEN", json.dumps(body))
        self.assertNotIn("days", body)
        self.assertNotIn("repositories", body)

    def test_invalid_query_does_not_collect(self):
        for query in (
            "",
            "login=",
            "login=-bad",
            "login=a--b",
            "login=a&login=b",
            "login=a&token=secret",
            "login=" + "x" * 100,
            "login=%FF",
        ):
            with self.subTest(query=query):
                self.assertEqual(request(self.app, query)[0], 400)
        self.assertEqual(self.created, [])

    def test_methods_routes_and_disallowed_origins_do_not_collect(self):
        self.assertEqual(request(self.app, method="POST")[0], 405)
        self.assertEqual(request(self.app, path="/")[0], 404)
        self.assertEqual(request(self.app, origin="https://evil.test")[0], 403)
        self.assertEqual(
            request(self.app, method="OPTIONS", origin="https://example.test")[0], 204
        )
        self.assertEqual(self.created, [])

    def test_cache_hit_is_case_insensitive_and_expires(self):
        first = request(self.app)[2]
        self.assertEqual(request(self.app, "login=Octocat")[2], first)
        self.assertEqual(len(self.created), 1)
        self.clock.advance(900)
        self.assertEqual(request(self.app)[0], 200)
        self.assertEqual(len(self.created), 2)

    def test_cache_expires_at_midnight(self):
        self.clock.value = datetime(2026, 11, 28, 23, 59, 59, tzinfo=UTC)
        self.assertEqual(request(self.app)[0], 200)
        self.clock.advance(2)
        result = request(self.app)
        self.assertEqual(result[2]["activity_end"], "2026-11-29")
        self.assertEqual(len(self.created), 2)

    def test_minute_quota_keeps_cache_hits_available(self):
        self.assertEqual(request(self.app, "login=one")[0], 200)
        self.assertEqual(request(self.app, "login=two")[0], 200)
        code, headers, body = request(self.app, "login=three")
        self.assertEqual(code, 429)
        self.assertEqual(headers["Retry-After"], "60")
        self.assertEqual(body["error"]["code"], "rate_limited")
        self.assertEqual(request(self.app, "login=one")[0], 200)
        self.clock.advance(60)
        self.assertEqual(request(self.app, "login=three")[0], 200)

    def test_hour_quota_and_failed_attempts(self):
        self.factory = lambda *a, **k: (_ for _ in ()).throw(GitHubError("secret"))
        for index in range(60):
            self.assertEqual(request(self.app, f"login=user{index}")[0], 502)
            self.clock.advance(30)
        self.assertEqual(request(self.app, "login=next")[0], 429)
        self.clock.advance(1800)
        self.assertEqual(request(self.app, "login=next")[0], 502)

    def test_errors_are_sanitized_and_never_cached(self):
        for failure, code in (
            (GitHubError("SENTINEL-TOKEN"), 502),
            (GitHubUnavailable("SENTINEL-TOKEN"), 503),
            (ValueError("SENTINEL-TOKEN"), 502),
        ):
            self.factory = lambda *a, **k: (_ for _ in ()).throw(failure)
            response = request(self.app)
            self.assertEqual(response[0], code)
            self.assertNotIn("SENTINEL-TOKEN", json.dumps(response))
            self.clock.advance(60)
        self.factory = self.make_client
        self.assertEqual(request(self.app)[0], 200)

    def test_upstream_retry_hint_is_preserved(self):
        def fail(*args, **kwargs):
            raise GitHubUnavailable("secret", retry_after=300)

        self.factory = fail
        code, headers, _ = request(self.app)
        self.assertEqual(code, 503)
        self.assertEqual(headers["Retry-After"], "300")

    def test_absent_user_and_incomplete_pages_do_not_become_empty_islands(self):
        for transform in (
            lambda q, v, u: None,
            lambda q, v, u: (
                {**u, "repositories": page([], "again")} if "repositories" in u else u
            ),
        ):

            def factory(*args, **kwargs):
                client = FixtureClient()
                client.transform = transform
                return client

            self.factory = factory
            code, _, body = request(self.app)
            self.assertEqual(code, 502)
            self.assertNotIn("settings", body)

    def test_busy_service_rejects_a_second_miss_without_blocking(self):
        entered, release = threading.Event(), threading.Event()

        def factory(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise AssertionError("Test did not release collection")
            return self.make_client(*args, **kwargs)

        self.factory = factory
        result = []
        thread = threading.Thread(target=lambda: result.append(request(self.app)))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(request(self.app, "login=other")[0], 503)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0][0], 200)

    def test_missing_configuration_disables_collection(self):
        app = PreviewApp("", "owner/island", "https://example.test")
        self.assertEqual(request(app)[0], 503)


if __name__ == "__main__":
    unittest.main()
