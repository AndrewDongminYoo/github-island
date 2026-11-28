import json
import runpy
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from github_island import lambda_preview
from github_island.preview import PreviewApp

ROOT = Path(__file__).resolve().parents[1]


def event(query="login=octocat", method="GET", origin="https://example.test"):
    return {
        "headers": {"origin": origin},
        "rawPath": "/preview",
        "rawQueryString": query,
        "requestContext": {"http": {"method": method}},
        "version": "2.0",
    }


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.app = PreviewApp("token", "owner/island", "https://example.test")
        self.patch = patch.object(lambda_preview, "application", self.app)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_raw_duplicate_query_is_rejected_without_upstream_access(self):
        result = lambda_preview.handler(event("login=one&login=two"), None)
        self.assertEqual(result["statusCode"], 400)
        self.assertEqual(json.loads(result["body"])["error"]["code"], "invalid_login")
        self.assertFalse(result["isBase64Encoded"])

    def test_method_and_origin_are_preserved(self):
        self.assertEqual(
            lambda_preview.handler(event(method="POST"), None)["statusCode"], 405
        )
        self.assertEqual(
            lambda_preview.handler(event(origin="https://other.test"), None)[
                "statusCode"
            ],
            403,
        )

    def test_application_response_is_forwarded_and_url_layer_owns_cors(self):
        self.app.token = ""
        result = lambda_preview.handler(event(), None)
        self.assertEqual(result["statusCode"], 503)
        self.assertEqual(result["headers"]["Cache-Control"], "no-store")
        self.assertFalse(
            any(key.lower().startswith("access-control-") for key in result["headers"])
        )
        self.assertEqual(json.loads(result["body"])["error"]["code"], "unavailable")

    def test_malformed_event_is_not_interpreted_as_a_request(self):
        for payload in ({}, None, {"version": "1.0"}, {**event(), "headers": None}):
            with self.subTest(payload=payload):
                self.assertEqual(
                    lambda_preview.handler(payload, None)["statusCode"], 400
                )


class BundleTests(unittest.TestCase):
    def test_bundle_is_reproducible_and_contains_only_package_sources(self):
        tool = runpy.run_path(str(ROOT / "tools" / "lambda_bundle.py"))
        with tempfile.TemporaryDirectory() as directory:
            first = tool["build"](Path(directory) / "one.zip")
            second = tool["build"](Path(directory) / "two.zip")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                expected = sorted(
                    "github_island/" + file.name
                    for file in (ROOT / "src" / "github_island").glob("*.py")
                )
                self.assertEqual(archive.namelist(), expected)
                self.assertIn("github_island/preview_worker.py", archive.namelist())
                self.assertIn("github_island/lambda_preview.py", archive.namelist())
                self.assertEqual(
                    archive.read("github_island/preview.py"),
                    (ROOT / "src" / "github_island" / "preview.py").read_bytes(),
                )
