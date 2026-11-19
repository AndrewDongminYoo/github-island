# Port the github-terrarium pipeline

Approved on 2026-11-19.
This plan brings the collection, growth and publication pipeline of [github-terrarium](https://github.com/AndrewDongminYoo/github-terrarium) to this repository, so that the island grows from real public activity.

## Decisions

- **Copy, do not share.** The pipeline modules are copied into the `github_island` package and renamed. A shared package is the next step only if a third scene appears.
- **Growth stays, visitors come and go.** Cumulative experience sets the growth stage, which drives the palms and never goes down. Sea animals, visitors, reefs, glints and islets follow the traits of the current window, exactly as github-terrarium computes them.
- **No text in the image.** The subject and the last complete activity day go into the SVG title, description and data attributes, and into the manifest.
- **The validator is an allowlist with budgets.** It accepts only known elements and attributes, rejects script and anything that reaches outside the file, checks that references resolve, and enforces byte and element budgets. It does not parse every attribute value against a grammar.
- **Scoring is unchanged.** Experience, stages, caps and the state schema are version 1 of github-terrarium.

## Steps

Each step is one pull request that passes the tests and `ruff`.

1. **Package and continuous integration.** Move the generator into the `github_island` package as the renderer, seed its random choices from a key, add `pyproject.toml`, the pinned development requirements, the test suite and the CI workflow.
2. **Collection and growth.** Port `config`, `models`, `github`, `probe`, `normalize`, `growth` and `state` with their tests. Add `render(state)`, which turns a validated state into the traits, the growth and the key that `render_scene` takes.
3. **Validator and output bundle.** Write the SVG validator for the island vocabulary, and port the bundle step that builds and checks the image, the state and the manifest together.
4. **Publication and schedule.** Port `publish`, `generate` and `restore`, add the guarded daily workflow, and point the README image at the published output once the `output` branch exists.

The first publication needs a manual workflow run with the bootstrap input.
That run changes the repository, so it waits for an explicit go-ahead.

## Known gaps to carry forward

- **Reduced motion.** The fish, the canoe and the water shading move with SMIL, which `prefers-reduced-motion` cannot turn off. github-terrarium requires a reduced-motion override for every animation. Moving the swimmers to CSS motion paths would close most of the gap and is not part of this plan.
- **Calm and active motion.** github-terrarium slows its animation after a week without activity. The island has no such mode yet.
- **Depth order.** Moving animals and fixed structures are not sorted against each other.

## Verification

```bash
python -m unittest discover -s tests -v
ruff check src tests tools
ruff format --check src tests tools
```

## Reconciliation, 2026-11-19

The validator decision above says that it does not parse every attribute value against a grammar.
The shipped validator in `src/github_island/validate.py` is stricter, and it is the authority.
Review of the pull request for step 3 found two values that a generic fallback let through: a URL function written in capitals, and `begin="click"` on an animation.
Both passed because the fallback accepted any letters.
The fallback is removed, and every allowed attribute has a grammar of its own, checked by `tests/test_validate.py`.
The validator still does not parse geometry: a path is checked for its alphabet, not for the shape it draws.

## Reconciliation, 2026-11-19, outside contributions

The decisions above say that scoring and the state schema are version 1 of github-terrarium, and that visitors follow reviews.
The shipped code in `src/github_island/growth.py`, `models.py`, `normalize.py` and `state.py` is the authority, and it differs in one place.
A first live collection showed 868 pull requests and 0 reviews in 30 days, so an account that works mostly alone would never see a visitor.
Compatibility with github-terrarium was dropped as a goal on the same day.
Each day now also counts `outside`: the pull requests and issues opened in public repositories that the account does not own.
The count is a subset of the pull requests and issues of that day, earns no experience, and has a trait that reaches 1 at 10.
Visitors follow the larger of the review trait and the outside trait.
The change was made before the first publication, so no published state had to be migrated.
