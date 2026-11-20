# Contributing

Thanks for looking at github-island.
Issues and pull requests are welcome, whether they fix a bug, improve a scene, or correct the documentation.

## Before you start

- For a small fix, open a pull request directly.
- For a new animal, visitor or change to the activity mapping, open an issue first and describe what it would look like and which signal would bring it. The island is meant to stay one island; activity changes who comes to it, not what it is.
- [README.md](README.md) explains how the island works, and [docs/notes/](docs/notes) holds the measurements behind the current limits.

## Set up

Use Python 3.12 or later, then follow the commands in the [Development section of the README](README.md#development).
They install the pinned development tools, install the package in editable mode, and run the tests and the linters.
The package itself has no runtime dependencies; keep it that way unless an issue agrees otherwise.

## Rules for changes

### The image

- The image stays one self-contained SVG: no script, no external reference, and nothing that needs pointer input, because a README shows it in an `<img>` tag.
- Rendering is deterministic. The same traits and the same key must give the same bytes, and the renderer must not read the clock, the network or the file system.
- The transparent variant carries no text. Titles and dates belong in the README or in metadata.
- Keep each scene under the byte budget that the tests check. [The size note](docs/notes/2026-11-19-svg-size-options.md) lists ways to save bytes.

### The validator

The validator is an allowlist.
When the renderer starts to write a new element, attribute, class or style, add it to the allowlist in the same pull request, with a test that shows that the old output is still refused where it should be.
Give every new attribute its own grammar; do not add a generic fallback, because a fallback once let `URL(...)` and `begin="click"` through.

### Examples

When the renderer output changes, run `python tools/examples.py` and commit the regenerated files under `examples/`.
A test fails when they no longer match the renderer.

### Activity and state

- Treat incomplete collection as a failure, never as zero activity.
- A repeated run must not earn the same growth twice.
- A snapshot or a state from github-terrarium is not valid here, because each day here also counts `outside`.

### Published output

Generated images and growth state live together on the `output` branch.
Never force-push it and never reset an existing island; `restore` brings back an earlier bundle through a new commit.

## Check your change

Run the tests and both ruff commands from the README before you open a pull request; CI runs the same commands.
A passing suite says that the SVG is well formed, self-contained and within budget.
It does not say that the scene looks right, so open `preview.html` in a browser, or build the playground as described in the [Playground section of the README](README.md#playground), and look at the result.
Animation needs a real browser: [the rendering note](docs/notes/2026-11-19-rendering-checks.md) explains what a still capture cannot show.

## Pull requests

- Write commit messages and pull request titles in the [Conventional Commits](https://www.conventionalcommits.org/) form, such as `fix: keep rays below the jetty`.
- Keep code, identifiers and documentation in English.
- Keep one concern per pull request, and say in the description how you checked it.

By contributing, you agree that your work is released under the [MIT License](LICENSE).
