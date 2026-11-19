# github-island

An isometric island, drawn as one animated SVG, that is meant to grow with public GitHub activity.

![An isometric island with palms, parasols, a stilt bungalow, a canoe and sea animals in translucent water](examples/island.svg)

## Status

This is an early prototype.
The renderer is a Python package that draws the scene from activity numbers passed on the command line.
Collecting real GitHub activity, keeping growth between runs, and publishing the image every day are not implemented yet.
[github-terrarium](https://github.com/AndrewDongminYoo/github-terrarium) has that pipeline for a different scene, and [the port plan](docs/plans/2026-11-19-pipeline-port.md) lists the steps that bring it here.

## How it works

- The scene is modelled in 3D world units in Python, projected to an isometric view, and painted from far to near.
- The output is one SVG file with no script, no canvas and no external assets, so it renders inside an `<img>` tag, which is how a README shows it.
- CSS keyframes move the palm fronds, the ripples, the glints and the small waves on the beach.
- SMIL moves the sea animals and the canoe along paths that lie in a plane below or on the water surface.
- The water shading is filter lighting on a noise height map, blended over the scene.
- Shapes that repeat are defined once and placed with `use`: the fronds of two palm crowns, the bungalow, a jetty segment, a post and a glint. The projection is isometric, so a copy only needs a translation.
- The transparent variant carries no text and no backdrop, so it sits on light and dark pages alike; only the shadow under the block follows `prefers-color-scheme`.

## Activity mapping

The island is always the same island.
What changes with activity is who comes to it.
Each signal is a number from 0 to 1.

| Signal        | What it brings                                                                                      |
| ------------- | --------------------------------------------------------------------------------------------------- |
| Pull requests | Sea animals, larger with more activity: fish, then turtles, rays, a pod of dolphins, a whale shark  |
| Reviews       | Visitors: float rings, then a canoe, parasols with sunbathers, and up to three bungalows on a jetty |
| Issues        | Reefs on the seabed                                                                                 |
| Stars         | Glints on the water                                                                                 |
| Forks         | Satellite islets around the island                                                                  |

The number and height of the palms follow overall growth, which the prototype takes as the mean of pull requests, reviews and issues.

**Quiet**

![An island with two palms and a few fish](examples/quiet.svg)

**Mostly pull requests**

![An island with dolphins, turtles, rays and a whale shark in the water](examples/builder.svg)

**Mostly reviews**

![An island with parasols, a canoe, float rings and three bungalows on a jetty](examples/reviewer.svg)

**Many stars and forks**

![An island with three satellite islets and many glints on the water](examples/maintainer.svg)

**Everything**

![An island with every animal, every visitor, all reefs and all islets](examples/full.svg)

## Usage

The package needs Python 3.12 or later and has no runtime dependencies.

```bash
python -m pip install -e .
python -m github_island scene OUTPUT.svg [--profile PROFILE] [--transparent] [--key KEY]
```

- `--profile` is five comma-separated numbers from 0 to 1 in the order pull requests, reviews, issues, stars, forks.
- `--transparent` removes the backdrop and the title text and crops the view to the block.
- `--key` seeds the random choices, so each key gets its own island and the same key always gets the same one.

```bash
python -m github_island scene island.svg --profile 0.65,0.65,0.6,0.6,0.34 --transparent
```

`python tools/examples.py` rewrites the scenes under `examples/`, and a test fails when they no longer match the renderer.
Open `preview.html` in a browser to see them side by side.

## Development

```bash
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip install -e .
python -m unittest discover -s tests -v
ruff check src tests tools
ruff format --check src tests tools
```

## Known limits

- The viewpoint is fixed. An image in a README cannot run script or receive pointer input, so there is no camera control, no interaction and no physics.
- The examples are between 62 kB and 118 kB. Every palm shares one of two crowns, mirrored and scaled, so palms look more alike than hand-drawn ones would. [The size note](docs/notes/2026-11-19-svg-size-options.md) lists what would shrink them further.
- Objects are sorted by the distance of their centre, so objects that pass through each other are painted in the wrong order. Sea animals and the canoe also pass under jetties and through posts without being hidden by them.
- Animals and visitors hold one pose. They move along a path, but they do not jump, walk or react to each other.
- The water shading recomputes a filter on every frame. Its playback cost is not measured.
- Rendering and animation were checked in a GitHub README on the web in Chrome with the dark theme, and in the GitHub mobile app on iOS. Other browsers and the light theme on GitHub are not confirmed yet. [The rendering note](docs/notes/2026-11-19-rendering-checks.md) says how to capture a scene and what a capture cannot prove.

## License

[MIT](LICENSE)
