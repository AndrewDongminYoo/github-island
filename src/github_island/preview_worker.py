"""One bounded preview collection; credentials arrive through a private pipe."""

import json
import sys

from .github import GitHubError, GraphQLClient
from .preview import collect_preview


def main():
    try:
        request = json.loads(sys.stdin.buffer.read(16384))
        client = GraphQLClient(request["token"], max_requests=64, max_seconds=60)
        result = collect_preview(request["login"], request["repository"], client)
    except GitHubError as error:
        result = {
            "error": "unavailable" if error.unavailable else "lookup_failed",
            "retry_after": error.retry_after,
        }
    except Exception:
        result = {"error": "lookup_failed"}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
