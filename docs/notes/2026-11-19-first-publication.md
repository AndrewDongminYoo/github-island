# First publication

Recorded on 2026-11-19.
This note is the evidence for the first live output of this repository and is closed at that date.

## The run

| Fact               | Value                                                                                   |
| ------------------ | --------------------------------------------------------------------------------------- |
| Workflow           | `Daily generation`, manual dispatch with `bootstrap=true`                               |
| Run                | [44542227258](https://github.com/AndrewDongminYoo/github-island/actions/runs/44542227258) |
| Source commit      | `a617671bef670b16cc9801ee89461352f6ac8d5e` on `main`                                    |
| Result             | Every step succeeded                                                                    |
| Output commit      | `9da4a1082c7c46133d1cf5803b0a196790dc32e6`, the first commit on `output`                |
| Commit subject     | `Publish island through 2026-11-18`                                                     |
| Files on `output`  | `island.svg`, `manifest.json`, `state.json`                                             |

## What the manifest says

| Field                   | Value                                                              |
| ----------------------- | ------------------------------------------------------------------ |
| `complete_activity_day` | `2026-11-18`                                                       |
| `stock_observation_day` | `2026-11-19`                                                       |
| `renderer_version`      | 1                                                                  |
| `sha256` of the image   | `50e4a2ca0bf97e5246728312d68198160f369cb9019a143dbd4a8e5bc80e07b1` |
| `sha256` of the state   | `7f90d9ed3256eac0d55cec85d42e8359b21b4f21e37db0268328cae6e9a419dd` |

## What was checked afterwards

- The three files were read back from `origin/output` and `python -m github_island validate` accepted them with exit code 0.
- The published `island.svg` is byte for byte the image that a local run drew a few minutes earlier from a separate collection with a personal token. Both are 108,690 bytes. Two tokens and two machines gave the same bytes.
- The published state counts 5 outside contributions in the 30-day window. The run used the workflow token, so that token can read the owner of a repository in the activity queries. This had been an open question.
- The raw address of the image answers with `content-type: image/svg+xml`, `cache-control: max-age=300` and a content security policy that allows inline style and nothing else.

## Counts in the first state

| Signal                | Count in 30 days | Trait |
| --------------------- | ---------------- | ----- |
| Pull requests         | 868              | 1.0   |
| Reviews               | 0                | 0.0   |
| Issues                | 242              | 1.0   |
| Outside contributions | 5                | 0.747 |
| Stars                 | 137              | 0.793 |
| Forks                 | 38               | 0.794 |

The state covers 94 public repositories.

## What this does not show

- No scheduled run had happened when this note was written. Whether the schedule starts, and how late, is unknown.
- A second run that updates an existing `output` branch has not happened on GitHub. Only the tests with local remotes cover that path.
