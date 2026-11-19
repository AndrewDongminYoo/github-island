# Project Guide

## Identity and purpose

Canonical project ID: `github-island`.
Personal-account repository: `AndrewDongminYoo/github-island`.
Draw an isometric island as one animated SVG, and grow it from public GitHub activity.

## Start here

- Read [README.md](README.md) for the current status and the activity mapping.
- Follow [the port plan](docs/plans/2026-11-19-pipeline-port.md) for the ordered work that brings the github-terrarium pipeline here, and for the decisions already made.
- Read [the rendering note](docs/notes/2026-11-19-rendering-checks.md) before judging a scene from a capture.
- Read [the size note](docs/notes/2026-11-19-svg-size-options.md) when a scene comes close to the byte budget.

## Boundaries

- The repository has a read-only public collector, local growth reconciliation, a renderer for a growth state, and example scenes. It does not validate the image, bundle it or publish yet; do not claim that it does.
- Collection, scoring and the state schema are copies of github-terrarium version 1. Treat incomplete collection as failure, never as zero activity, and keep repeated runs from earning duplicate growth.
- The image must stay one self-contained SVG: no script, no external reference, nothing that needs pointer input.
- Keep rendering deterministic. The same traits and the same key must give the same bytes, and nothing in the renderer may read the clock, the network or the file system.
- The transparent variant carries no text. Titles and dates belong in the README or in metadata.
- Regenerate `examples/` with `python tools/examples.py` whenever the renderer output changes; a test compares them.
- Keep technical documentation and identifiers in English.

## Verification

Run `python -m unittest discover -s tests -v`, `ruff check src tests tools`, and `ruff format --check src tests tools` in a Python 3.12 environment with `requirements-dev.txt` and the package installed.
A passing suite says the SVG is well formed, self-contained and within budget; it does not say the scene looks right.
For that, render `preview.html` in a browser.
