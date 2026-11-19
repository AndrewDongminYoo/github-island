"""Command line entry point."""

import argparse
import sys
from pathlib import Path

from .render import DEFAULT, render_scene


def profile(text):
    """Parse `prs,reviews,issues,stars,forks`, each a number from 0 to 1."""
    try:
        values = [float(part) for part in text.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError("Profile values must be numbers") from None
    if len(values) != len(DEFAULT) or not all(0 <= value <= 1 for value in values):
        raise argparse.ArgumentTypeError(
            "Profile needs five numbers from 0 to 1: prs,reviews,issues,stars,forks"
        )
    return dict(zip(DEFAULT, values))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="github-island", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    scene = commands.add_parser(
        "scene", help="Draw the island from explicit signal values"
    )
    scene.add_argument("output", type=Path)
    scene.add_argument("--profile", type=profile, default=None)
    scene.add_argument("--key", default="example", help="Seed for the island's shape")
    scene.add_argument(
        "--transparent",
        action="store_true",
        help="Drop the backdrop and the title, and crop the view to the block",
    )
    args = parser.parse_args(argv)
    svg = render_scene(args.profile, args.transparent, args.key)
    args.output.write_text(svg, encoding="utf-8")
    print(f"{args.output.name}: {len(svg.encode())} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
