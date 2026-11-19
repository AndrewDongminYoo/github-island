"""Scene, collection, offline growth and bundle commands."""

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .bundle import build_files, source_commit, validate_bundle, write_bundle
from .config import load_config
from .github import GraphQLClient
from .growth import advance
from .models import canonical_json
from .normalize import collect
from .probe import probe
from .render import DEFAULT, render, render_scene
from .state import read_json, validate_state


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
    command = commands.add_parser(
        "scene", help="Draw the island from explicit signal values"
    )
    command.add_argument("output", type=Path)
    command.add_argument("--profile", type=profile, default=None)
    command.add_argument("--key", default="example", help="Seed for the island's shape")
    command.add_argument(
        "--transparent",
        action="store_true",
        help="Drop the backdrop and the title, and crop the view to the block",
    )
    command = commands.add_parser("probe", help="Read first-page public API samples")
    command.add_argument("--config", type=Path, default=Path("island.toml"))
    command.add_argument(
        "--repository", default=os.environ.get("GITHUB_REPOSITORY", "")
    )
    command.add_argument(
        "--day",
        type=date.fromisoformat,
        default=datetime.now(UTC).date() - timedelta(days=1),
    )
    command = commands.add_parser(
        "collect", help="Collect complete public daily counts"
    )
    command.add_argument("--config", type=Path, default=Path("island.toml"))
    command.add_argument(
        "--repository", default=os.environ.get("GITHUB_REPOSITORY", "")
    )
    command.add_argument("--start", type=date.fromisoformat, required=True)
    command.add_argument(
        "--end", type=date.fromisoformat, default=datetime.now(UTC).date()
    )
    command.add_argument(
        "--expected-subject", help="Reject a different immutable user ID"
    )
    command = commands.add_parser(
        "grow", help="Reconcile local growth state without network access"
    )
    command.add_argument("--snapshot", type=Path, required=True)
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--state", type=Path)
    source.add_argument("--bootstrap", action="store_true")
    command.add_argument("--recover-through", type=date.fromisoformat)
    command = commands.add_parser(
        "draw", help="Draw the island for a growth state without network access"
    )
    command.add_argument("--state", type=Path, required=True)
    command.add_argument("output", type=Path)
    command = commands.add_parser(
        "build", help="Build and validate a three-file output bundle offline"
    )
    command.add_argument("--snapshot", type=Path, required=True)
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--state", type=Path)
    source.add_argument("--bootstrap", action="store_true")
    command.add_argument("--bundle-dir", type=Path, required=True)
    command.add_argument("--source-commit", type=source_commit, required=True)
    command = commands.add_parser(
        "validate", help="Validate an existing three-file output bundle"
    )
    command.add_argument("--bundle-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "scene":
        svg = render_scene(args.profile, args.transparent, args.key)
        args.output.write_text(svg, encoding="utf-8")
        print(f"{args.output.name}: {len(svg.encode())} bytes")
        return 0
    try:
        if args.command == "draw":
            svg = render(validate_state(read_json(args.state)))
            args.output.write_bytes(svg)
            print(f"{args.output.name}: {len(svg)} bytes")
            return 0
        if args.command == "build":
            previous = (
                validate_state(read_json(args.state))
                if args.state is not None
                else None
            )
            files = build_files(
                advance(read_json(args.snapshot), previous), args.source_commit
            )
            result = write_bundle(files, args.bundle_dir, previous=previous)
            print(canonical_json(result), end="")
            return 0
        if args.command == "validate":
            print(canonical_json(validate_bundle(args.bundle_dir)), end="")
            return 0
        if args.command == "grow":
            previous = (
                validate_state(read_json(args.state))
                if args.state is not None
                else None
            )
            result = advance(
                read_json(args.snapshot), previous, recover_through=args.recover_through
            )
            print(canonical_json(result), end="")
            return 0
        if args.command == "probe" and args.day >= datetime.now(UTC).date():
            raise ValueError("Probe day must be a completed UTC day")
        config = load_config(args.config, args.repository)
        client = GraphQLClient(
            os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        )
        if args.command == "probe":
            result = probe(config, args.day, client)
        else:
            result = collect(
                config,
                args.start,
                args.end,
                client,
                expected_subject=args.expected_subject,
            )
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(canonical_json(result), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
