# SVG size: what was done and what is left

Recorded on 2026-11-19, when the largest example went from 277,954 bytes to 117,517 bytes.
This note is closed at that date.
It keeps the measurements and the options that were not applied, so that the next person who needs bytes does not have to measure again from nothing.

## Where the bytes were

Measured on `examples/full.svg` (every signal at 1) before the change, by summing the length of every start tag per element kind.

| Part                                              | Bytes   |
| ------------------------------------------------- | ------- |
| Whole file                                        | 277,954 |
| Palm fronds, 108 groups on 9 palms                | 123,904 |
| Filled polygons with a seam stroke, 382 of them   | 126,560 |
| The repeated stroke attributes on those polygons  | 19,482  |

The frond figure and the polygon figure overlap, because each frond contains one filled polygon.

## What was done

- Fronds are defined once per crown, for two crowns, and every palm places them with `use`, mirrored for half of the palms and scaled with the trunk.
- The bungalow, one jetty segment, one post and the glint are defined once and placed with `use` and a translation.
- A filled polygon carries `class="s"` and one `color` attribute. The class fills and strokes with `currentColor`.
- Coordinates drop a trailing `.0`.
- The island outline has 48 points and an islet outline has 24. Both had 72.
- Pebbles on the cut faces share two groups that hold the fill and the opacity.

| Example          | Before  | After   |
| ---------------- | ------- | ------- |
| `quiet.svg`      | 79,050  | 62,504  |
| `builder.svg`    | 107,202 | 76,896  |
| `reviewer.svg`   | 180,074 | 88,266  |
| `island.svg`     | 165,891 | 93,626  |
| `maintainer.svg` | 178,732 | 86,540  |
| `full.svg`       | 277,954 | 117,517 |

## Where the bytes are now

Measured the same way on `examples/full.svg` after the change.

| Part                          | Bytes  |
| ----------------------------- | ------ |
| Filled polygons, 170 of them  | 41,108 |
| The shared `defs` block       | 30,604 |
| Paths, 90 of them             | 18,539 |
| Lines, 128 of them            | 12,337 |
| Circles, 202 of them          | 11,719 |

The same file is 29,852 bytes after gzip at level 9.

## Options that were not applied

The savings below are estimates, not measurements.

| Option                                                       | Estimated saving | What it costs                                           |
| ------------------------------------------------------------ | ---------------- | ------------------------------------------------------- |
| Draw the island with about 8 contour rings in place of 15    | about 10 kB      | Visible steps on the sand slope                         |
| Keep one palm crown in place of two                          | about 9 kB       | Palms look even more alike                              |
| Round coordinates to whole pixels                            | 10 kB to 15 kB   | Thin shapes such as posts and planks shift slightly     |
| Define one reef and reuse it                                 | about 7 kB       | Every reef has the same shape                           |
| Define the shoreline path once and reuse it for foam and swash | about 3 kB     | Nothing visible; a little more code                     |
| Shorter colors and attribute spellings                       | 3 kB to 5 kB     | The output is harder to read                            |

Applied together they would bring the largest example to roughly 80 kB.
That total is the sum of the estimates above.

## Why the work stopped here

- The largest example is at 59% of the 200 kB budget that github-terrarium enforces, so there is room for more animals and visitors.
- Most of the options remove repetition that a compressor already removes, so the transferred size would shrink less than the file size.
  Whether GitHub serves a README image compressed was not checked.
- Every option except the shoreline one trades away some picture quality or variety.

Use this list when a validator with a size budget exists and a real scene comes close to it.

## One trap found on the way

The `animation` shorthand resets `animation-delay`.
A delay class that is declared before a rule with the shorthand loses to it at equal specificity, and every element then animates in step.
The glints did exactly that until the delay classes moved to the end of the stylesheet.
A still capture with motion enabled shows the fault as glints that are all invisible at the same moment.
