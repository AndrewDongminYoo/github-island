"""Build the playground site: the page and the renderer modules it runs in the browser.

Usage: python tools/playground.py OUTPUT_DIRECTORY

The page loads the modules listed here and nothing else, so the browser draws
the island with the same files that draw the published image. This script only
copies files and needs no installed package.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "playground" / "index.html"
PACKAGE = ROOT / "src" / "github_island"
# The renderer and everything it imports. It must not reach the network, the
# clock or the command line, so the collector and the publisher stay out.
MODULES = ("__init__", "config", "models", "growth", "state", "render")


def build(output):
    output = Path(output)
    package = output / "py" / "github_island"
    package.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PAGE, output / "index.html")
    for name in MODULES:
        shutil.copyfile(PACKAGE / f"{name}.py", package / f"{name}.py")
    (output / "py" / "modules.json").write_text(json.dumps(list(MODULES)) + "\n")
    # GitHub Pages must serve the files as they are, without a Jekyll build.
    (output / ".nojekyll").write_text("")
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(build(sys.argv[1]))
