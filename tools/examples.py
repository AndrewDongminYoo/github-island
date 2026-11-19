"""Write the example scenes under `examples/`, or check that they are current.

Usage: python tools/examples.py [--check]
"""

import sys
from pathlib import Path

from github_island.render import DEFAULT, render_scene

ROOT = Path(__file__).resolve().parent.parent / "examples"
# Signal order: prs, reviews, issues, stars, forks.
EXAMPLES = {
    "quiet": (0.1, 0.1, 0.2, 0.2, 0),
    "builder": (0.95, 0.2, 0.3, 0.4, 0),
    "reviewer": (0.25, 0.95, 0.5, 0.3, 0.34),
    "island": (0.65, 0.65, 0.6, 0.6, 0.34),
    "maintainer": (0.5, 0.4, 0.4, 1, 1),
    "full": (1, 1, 1, 1, 1),
}


def scenes():
    for name, values in EXAMPLES.items():
        svg = render_scene(dict(zip(DEFAULT, values)), transparent=True)
        yield ROOT / f"{name}.svg", svg


def main(argv):
    stale = []
    for path, svg in scenes():
        if "--check" in argv:
            if not path.exists() or path.read_text(encoding="utf-8") != svg:
                stale.append(path.name)
        else:
            path.write_text(svg, encoding="utf-8")
            print(f"{path.name}: {len(svg.encode())} bytes")
    if stale:
        print("Stale examples: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
