"""Adapt Lambda Function URL payloads to the existing preview application."""

import io
import json
import sys

from .preview import application


def handler(event, context):
    try:
        if not isinstance(event, dict) or event.get("version") != "2.0":
            raise ValueError("Unsupported event")
        method = event["requestContext"]["http"]["method"]
        path = event["rawPath"]
        query = event["rawQueryString"]
        headers = event["headers"]
        if not all(isinstance(value, str) for value in (method, path, query)):
            raise ValueError("Invalid request")
        if not isinstance(headers, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in headers.items()
        ):
            raise ValueError("Invalid headers")
    except (KeyError, TypeError, ValueError):
        return {
            "body": json.dumps({"error": {"code": "invalid_request"}}),
            "headers": {"Content-Type": "application/json"},
            "isBase64Encoded": False,
            "statusCode": 400,
        }
    environ = {
        "HTTP_ORIGIN": {key.lower(): value for key, value in headers.items()}.get(
            "origin", ""
        ),
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "REQUEST_METHOD": method,
        "SCRIPT_NAME": "",
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.errors": sys.stderr,
        "wsgi.input": io.BytesIO(),
        "wsgi.multiprocess": False,
        "wsgi.multithread": False,
        "wsgi.run_once": False,
        "wsgi.url_scheme": "https",
        "wsgi.version": (1, 0),
    }
    response = {}

    def start_response(status, headers):
        response["statusCode"] = int(status.split()[0])
        # Configure CORS on the Function URL, including responses from AWS itself.
        # Sending the application headers too would duplicate those headers.
        response["headers"] = {
            key: value
            for key, value in headers
            if not key.lower().startswith("access-control-")
        }

    response["body"] = b"".join(application(environ, start_response)).decode("utf-8")
    response["isBase64Encoded"] = False
    return response
