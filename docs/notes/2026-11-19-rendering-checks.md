# How rendering was checked, and what the checks cannot see

Recorded on 2026-11-19.
The island is one SVG shown through an `<img>` tag, so what matters is how that mode behaves in each renderer, not what the SVG specification allows.

## What was confirmed, and where

| Renderer                                    | Result                                                                                         | Basis                                                                              |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| GitHub README on the web, Chrome, dark theme | The transparent island renders, and CSS and SMIL animation both play                            | Two captures a few seconds apart showed the fish school and a ray in new positions |
| GitHub mobile app on iOS                    | Renders and animates                                                                           | Looked at by hand                                                                  |
| Headless Chrome, local file                 | Every example renders; filters, masks, blend modes and `prefers-color-scheme` work in `<img>`  | Captures of each feature on its own and of the scenes                              |

Not confirmed: Firefox, Safari with the current scenes, the light theme on GitHub, and playback cost.

## What an `<img>` SVG cannot do

- Script does not run.
- An external image does not load. Chrome draws a broken-image icon in its place and Safari leaves the area empty, so never reference anything outside the file.
- Pointer input does not reach it, so hover and click do nothing.

## How to capture a scene

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --hide-scrollbars --window-size=1000,790 --screenshot=shot.png "file://$PWD/examples/full.svg"
```

Useful flags:

- `--force-dark-mode` renders with `prefers-color-scheme: dark`.
- `--blink-settings=preferredColorScheme=1` renders with the light scheme even when the system is in dark mode.
- `--force-prefers-reduced-motion` turns every CSS animation off, which shows each animated element in its resting state.

## What a capture does not prove

- **A headless capture is one frame near the start of the animation.**
  `--virtual-time-budget` did not move the animation forward: captures at 1,000 ms and 2,600 ms were nearly the same.
  A capture shows that animation started, never that it plays to the end. Open the file in a browser for that.
- **The capture follows the system color scheme.**
  A capture meant to be light came out dark once the Mac had switched to dark mode in the evening.
  Force the scheme with the flags above.
- **An element can be invisible in a capture because of its animation phase.**
  When glints all vanished from a capture, the reduced-motion flag showed that they were drawn, which pointed at the animation and not at the shape.
- **A frond that sways about the wrong point shows up in a still.**
  Fronds rotate about the origin of their palm's group. If that origin were wrong, a few degrees of rotation would move each frond tens of pixels away from its trunk, so fronds that sit on their trunks in a capture confirm the pivot.

## Theme caveat for the transparent variant

`prefers-color-scheme` inside the SVG follows the system or browser setting.
It is believed not to follow a theme chosen in GitHub settings; this was not measured.
That is why the transparent variant carries no text, and only the shadow under the block reacts to the scheme.
