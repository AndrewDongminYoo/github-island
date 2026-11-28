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

- The repository has a read-only public collector, local growth reconciliation, a renderer for a growth state, an SVG validator, offline bundle build and validation, a `publish` command, a `generate` command that publishes with one conflict retry, a manual `restore` command, a guarded `generate.yml` workflow, and example scenes. Live output was first published by a manual bootstrap on 2026-11-19 ([publication note](docs/notes/2026-11-19-first-publication.md)); the first scheduled run, on 2026-11-20, succeeded 7 hours after its cron time ([scheduled run note](docs/notes/2026-11-20-first-scheduled-run.md)), so do not claim that scheduled runs start on time.
- Keep source and documentation on `main`; generated images and growth state go together on `output`.
- Follow the [account preview documentation](README.md#account-previews) for the Playground's separate API, server-only credential, request limits, and Lambda deployment.
- Follow [CONTRIBUTING.md](CONTRIBUTING.md) for the rules on the image, the validator, the examples, activity and state, the `output` branch, and language.

## Verification

Run the commands in the README's Development section in a Python 3.12 environment, as [CONTRIBUTING.md](CONTRIBUTING.md#check-your-change) describes, and look at the scene in a browser before you call a renderer change done.
