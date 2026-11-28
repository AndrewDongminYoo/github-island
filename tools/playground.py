"""Build the playground site: the page and the renderer modules it runs in the browser.

Usage: python tools/playground.py OUTPUT_DIRECTORY

The page loads the modules listed here and nothing else, so the browser draws
the island with the same files that draw the published image. This script only
copies files and needs no installed package.
"""

import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "playground" / "index.html"
PACKAGE = ROOT / "src" / "github_island"
# The renderer and everything it imports. It must not reach the network, the
# clock or the command line, so the collector and the publisher stay out.
MODULES = ("__init__", "config", "models", "growth", "state", "render")


def build(output, preview_api=""):
    if preview_api:
        parsed = urlsplit(preview_api)
        if (
            not parsed.hostname
            or parsed.port == 0
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or "?" in preview_api
            or "#" in preview_api
            or any(char.isspace() for char in preview_api)
            or not (
                parsed.scheme == "https"
                or (
                    parsed.scheme == "http"
                    and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
                )
            )
        ):
            raise ValueError(
                "Preview API must be HTTPS or loopback HTTP "
                "without credentials, query, or fragment"
            )
        preview_api = preview_api.rstrip("/")
    output = Path(output)
    package = output / "py" / "github_island"
    package.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PAGE, output / "index.html")
    for name in ("account.js", "i18n.js"):
        shutil.copyfile(PAGE.parent / name, output / name)
    (output / "config.json").write_text(json.dumps({"previewApi": preview_api}) + "\n")
    for name in MODULES:
        shutil.copyfile(PACKAGE / f"{name}.py", package / f"{name}.py")
    (output / "py" / "modules.json").write_text(json.dumps(list(MODULES)) + "\n")
    # GitHub Pages must serve the files as they are, without a Jekyll build.
    (output / ".nojekyll").write_text("")
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(build(sys.argv[1], preview_api=os.environ.get("PREVIEW_API_URL", "")))
