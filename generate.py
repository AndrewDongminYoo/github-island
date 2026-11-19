"""Generate an isometric lagoon diorama as one self-contained animated SVG.

Usage: python3 generate.py OUTPUT.svg [BUNGALOWS] [PROFILE] [transparent]

PROFILE is prs,reviews,issues,stars,forks, each from 0 to 1.

The scene is modelled in 3D world units, projected to 2D here, and painted
back to front. The browser only runs CSS and SMIL animation on the result.
"""

import math
import random
import sys
from pathlib import Path

A = math.cos(math.radians(30))
B = 0.5
S = 40.0  # pixels per world unit
CX, CY = 640.0, 225.0  # screen position of the far block corner at z = 0
W = 12.0  # block edge length
H = 1.3  # water depth
DEPTH = 3.2  # thickness of the soil below the seabed
DECK = 1.75  # deck height above the seabed
LOCAL = 100.0  # local units per world unit inside plane-mapped groups
ISLAND = (3.2, 3.2)
ISLAND_R, ISLAND_TOP = 3.0, 2.0
WOOD = "#b98a5a"
POST = "#7d5a3a"
THATCH = "#cfa95f"
WALL = "#f7f0e3"


def P(x, y, z=0.0):
    return (CX + (x - y) * A * S, CY + (x + y) * B * S - z * S)


def P3(points):
    return [P(*p) for p in points]


def fmt(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def attrs(kw):
    return "".join(
        f' {k.rstrip("_").replace("_", "-")}="{v}"' for k, v in kw.items()
    )


def poly(points, **kw):
    return f'<polygon points="{fmt(points)}"{attrs(kw)}/>'


def solid(points, fill):
    # A hairline stroke in the fill color hides seams between adjacent faces.
    return poly(points, fill=fill, stroke=fill, stroke_width="0.7", stroke_linejoin="round")


def line(a, b, **kw):
    return (
        f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"'
        f"{attrs(kw)}/>"
    )


def rgb(color):
    color = color.lstrip("#")
    return [int(color[i : i + 2], 16) for i in (0, 2, 4)]


def hexc(values):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in values)


def shade(color, factor):
    return hexc([v * factor for v in rgb(color)])


def mix(a, b, t):
    return hexc([x + (y - x) * t for x, y in zip(rgb(a), rgb(b))])


def lerp3(a, b, t):
    return tuple(p + (q - p) * t for p, q in zip(a, b))


def ground(z):
    k = S / LOCAL
    return (
        f"matrix({A * k:.4f} {B * k:.4f} {-A * k:.4f} {B * k:.4f} "
        f"{CX:.1f} {CY - z * S:.1f})"
    )


def face_y():
    # Plane y = W. Local u runs along x, local v runs downward from z = 0.
    k = S / LOCAL
    return (
        f"matrix({A * k:.4f} {B * k:.4f} 0 {k:.4f} "
        f"{CX - A * S * W:.1f} {CY + B * S * W:.1f})"
    )


def face_x():
    # Plane x = W. Local u runs from the near corner toward y = 0.
    k = S / LOCAL
    return f"matrix({A * k:.4f} {-B * k:.4f} 0 {k:.4f} {CX:.1f} {CY + 2 * B * S * W:.1f})"


def hull(points):
    points = sorted(set(points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def half(sequence):
        chain = []
        for p in sequence:
            while len(chain) >= 2 and cross(chain[-2], chain[-1], p) <= 0:
                chain.pop()
            chain.append(p)
        return chain[:-1]

    return half(points) + half(reversed(points))


def box(x0, y0, z0, x1, y1, z1, color, fx=0.72, fy=0.87):
    return [
        solid(P3([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]), shade(color, fx)),
        solid(P3([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]), shade(color, fy)),
        solid(P3([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]), color),
    ]


def post(x, y, z0, z1):
    return box(x - 0.05, y - 0.05, z0, x + 0.05, y + 0.05, z1, POST)


def roof(xc, yc, h, z0, t, color):
    c00, c10 = (xc - h, yc - h, z0), (xc + h, yc - h, z0)
    c11, c01 = (xc + h, yc + h, z0), (xc - h, yc + h, z0)
    apex = (xc, yc, z0 + t)
    out = []
    for a, b, f in ((c10, c11, 0.55), (c01, c11, 0.68)):
        drop = [(a[0], a[1], z0 - 0.1), (b[0], b[1], z0 - 0.1)]
        out.append(solid(P3([a, b, drop[1], drop[0]]), shade(color, f)))
    for a, b, f in ((c00, c10, 1.04), (c00, c01, 0.96), (c10, c11, 0.74), (c01, c11, 0.9)):
        out.append(solid(P3([a, b, apex]), shade(color, f)))
        for q in (0.22, 0.44, 0.64, 0.82):
            out.append(
                line(
                    P(*lerp3(a, apex, q)),
                    P(*lerp3(b, apex, q)),
                    stroke=shade(color, f * 0.78),
                    stroke_width="1.1",
                    opacity="0.75",
                )
            )
    out.append(line(P(*apex), P(*c11), stroke=shade(color, 0.6), stroke_width="1"))
    return out


def deck(x0, y0, x1, y1, along_x=True):
    out = box(x0, y0, DECK - 0.1, x1, y1, DECK, WOOD)
    stroke = shade(WOOD, 0.8)
    if along_x:
        steps = int((y1 - y0) / 0.18)
        for i in range(1, steps):
            y = y0 + (y1 - y0) * i / steps
            out.append(line(P(x0, y, DECK), P(x1, y, DECK), stroke=stroke, stroke_width="0.6"))
    else:
        steps = int((x1 - x0) / 0.18)
        for i in range(1, steps):
            x = x0 + (x1 - x0) * i / steps
            out.append(line(P(x, y0, DECK), P(x, y1, DECK), stroke=stroke, stroke_width="0.6"))
    return out


def bungalow(xc, yc):
    x0, x1, y0, y1 = xc - 0.75, xc + 0.75, yc - 0.75, yc + 1.25
    out = []
    corners = [(x0 + 0.1, y0 + 0.1), (x1 - 0.1, y0 + 0.1), (x0 + 0.1, y1 - 0.1), (x1 - 0.1, y1 - 0.1)]
    for px, py in corners:
        out += post(px, py, H, DECK - 0.1)
    out += deck(x0, y0, x1, y1)
    # Ladder from the porch into the water.
    for dx in (0.25, 0.45):
        out.append(
            line(P(xc + dx, y1, DECK), P(xc + dx, y1 + 0.12, H - 0.1), stroke="#f3ede0", stroke_width="1.3")
        )
    # Sun loungers on the porch.
    for lx in (xc - 0.55, xc - 0.15):
        out += box(lx, yc + 0.72, DECK, lx + 0.26, yc + 1.15, DECK + 0.07, "#ffffff")
        out += box(lx, yc + 0.72, DECK + 0.07, lx + 0.26, yc + 0.84, DECK + 0.17, "#8fd6d0")
    wz = DECK + 1.0
    out += box(xc - 0.6, yc - 0.6, DECK, xc + 0.6, yc + 0.6, wz, WALL)
    door = [(xc - 0.2, yc + 0.6, DECK), (xc + 0.2, yc + 0.6, DECK), (xc + 0.2, yc + 0.6, DECK + 0.58), (xc - 0.2, yc + 0.6, DECK + 0.58)]
    out.append(solid(P3(door), "#6b4a33"))
    window = [(xc + 0.6, yc - 0.3, DECK + 0.3), (xc + 0.6, yc + 0.3, DECK + 0.3), (xc + 0.6, yc + 0.3, DECK + 0.6), (xc + 0.6, yc - 0.3, DECK + 0.6)]
    out.append(poly(P3(window), fill="#8fcfe0", stroke="#fffaf0", stroke_width="1"))
    # Eave shadow on the two visible walls.
    for band in (
        [(xc + 0.6, yc - 0.6, wz - 0.16), (xc + 0.6, yc + 0.6, wz - 0.16), (xc + 0.6, yc + 0.6, wz), (xc + 0.6, yc - 0.6, wz)],
        [(xc - 0.6, yc + 0.6, wz - 0.16), (xc + 0.6, yc + 0.6, wz - 0.16), (xc + 0.6, yc + 0.6, wz), (xc - 0.6, yc + 0.6, wz)],
    ):
        out.append(poly(P3(band), fill="#3a2a18", opacity="0.22"))
    out += roof(xc, yc, 0.86, wz, 0.7, THATCH)
    return out


def island_radius(theta, z, radius=None, top=None):
    radius = ISLAND_R if radius is None else radius
    top = ISLAND_TOP if top is None else top
    wobble = 1 + 0.10 * math.sin(3 * theta + 0.6) + 0.06 * math.sin(5 * theta + 2.1) + 0.04 * math.sin(2 * theta + 4)
    return radius * (1 - 0.7 * (z / top) ** 1.6) * wobble


def island_ring(z, scale=1.0, n=72, center=None, radius=None, top=None):
    cx, cy = ISLAND if center is None else center
    return [
        (
            cx + island_radius(2 * math.pi * i / n, z, radius, top) * scale * math.cos(2 * math.pi * i / n),
            cy + island_radius(2 * math.pi * i / n, z, radius, top) * scale * math.sin(2 * math.pi * i / n),
            z,
        )
        for i in range(n)
    ]


def island_height(dx, dy):
    r = math.hypot(dx, dy) / ISLAND_R
    if r >= 1:
        return 0.0
    return min(ISLAND_TOP, ISLAND_TOP * ((1 - r) / 0.7) ** (1 / 1.6))


def ribbon(points, widths):
    left, right = [], []
    for i, (x, y) in enumerate(points):
        ax, ay = points[max(i - 1, 0)]
        bx, by = points[min(i + 1, len(points) - 1)]
        length = math.hypot(bx - ax, by - ay) or 1.0
        nx, ny = -(by - ay) / length, (bx - ax) / length
        left.append((x + nx * widths[i], y + ny * widths[i]))
        right.append((x - nx * widths[i], y - ny * widths[i]))
    return left, right


def palm(bx, by, height, lean, seed, bz=None, size=1.0):
    rnd = random.Random(seed)
    if bz is None:
        bz = island_height(bx - ISLAND[0], by - ISLAND[1])
    out = []
    spine = [
        P(bx + lean[0] * (i / 10) ** 2, by + lean[1] * (i / 10) ** 2, bz + height * i / 10)
        for i in range(11)
    ]
    widths = [(5.6 - 2.6 * i / 10) * size for i in range(11)]
    left, right = ribbon(spine, widths)
    out.append(solid(left + right[::-1], "#b08d63"))
    for i in range(1, 10):
        out.append(line(left[i], right[i], stroke="#8a6b47", stroke_width="1", opacity="0.7"))
    crown = (bx + lean[0], by + lean[1], bz + height)
    sx, sy = P(*crown)
    fronds = []
    count = 12
    for k in range(count):
        theta = 2 * math.pi * k / count + rnd.uniform(-0.2, 0.2)
        fronds.append((math.cos(theta) + math.sin(theta), theta, k))
    fronds.sort()
    for depth, theta, k in fronds:
        reach = rnd.uniform(1.45, 1.95) * (0.75 + height / 12) * size
        rise = rnd.uniform(0.9, 1.4)
        droop = rise + rnd.uniform(0.6, 1.0)
        mid = []
        for i in range(13):
            u = i / 12
            mid.append(
                P(
                    crown[0] + math.cos(theta) * reach * u,
                    crown[1] + math.sin(theta) * reach * u,
                    crown[2] + rise * u - droop * u * u,
                )
            )
        widths = [9.5 * 2.3 * size * (i / 12) ** 0.5 * (1 - i / 12) ** 0.7 for i in range(13)]
        left, right = ribbon(mid, widths)
        base = "#2a8348" if depth < -0.3 else ("#3f9f55" if k % 2 else "#57b866")
        cuts = "".join(
            f"M{left[i][0]:.1f} {left[i][1]:.1f}L{mid[i - 1][0]:.1f} {mid[i - 1][1]:.1f}"
            f"L{right[i][0]:.1f} {right[i][1]:.1f}"
            for i in range(2, 12)
        )
        out.append(
            f'<g class="frond" style="transform-origin:{sx:.1f}px {sy:.1f}px;'
            f'animation-delay:-{rnd.uniform(0, 6):.2f}s">'
            + solid(left + right[::-1], base)
            + f'<path d="{cuts}" fill="none" stroke="{shade(base, 0.68)}" stroke-width="0.8" opacity="0.6"/>'
            + f'<polyline points="{fmt(mid)}" fill="none" stroke="{shade(base, 1.3)}" stroke-width="1"/>'
            + "</g>"
        )
    for dx, dy in ((-3, 3), (3, 4), (0, 6)):
        out.append(f'<circle cx="{sx + dx:.1f}" cy="{sy + dy:.1f}" r="3.2" fill="#5b4027"/>')
    return out


def bush(x, y, seed):
    rnd = random.Random(seed)
    z = island_height(x - ISLAND[0], y - ISLAND[1])
    sx, sy = P(x, y, z)
    out = []
    for i in range(5):
        color = ("#2f8a4c", "#3fa257", "#57b866", "#2a7a44", "#6cc474")[i]
        out.append(
            f'<circle cx="{sx + rnd.uniform(-11, 11):.1f}" cy="{sy - 5 + rnd.uniform(-7, 4):.1f}" '
            f'r="{rnd.uniform(6, 10):.1f}" fill="{color}"/>'
        )
    return out


def ellipse_path(cx, cy, rx, ry, clockwise=True):
    sweep = 1 if clockwise else 0
    return (
        f"M{cx - rx:.0f} {cy:.0f}a{rx:.0f} {ry:.0f} 0 1 {sweep} {2 * rx:.0f} 0"
        f"a{rx:.0f} {ry:.0f} 0 1 {sweep} {-2 * rx:.0f} 0"
    )


CSS = """
.frond { animation: sway 6s ease-in-out infinite alternate; }
.ripple { transform-box: fill-box; transform-origin: center; animation: ripple 5s ease-out infinite; }
.glint { transform-box: fill-box; transform-origin: center; animation: glint 3.2s ease-in-out infinite; }
.bob { animation: bob 4s ease-in-out infinite alternate; }
.foam { animation: foam 4.5s ease-in-out infinite alternate; }
.swash { transform-box: fill-box; transform-origin: center; animation: swash 7s ease-out infinite; }
@keyframes swash {
  0% { transform: scale(1.17); opacity: 0; }
  35% { opacity: 0.75; }
  100% { transform: scale(1); opacity: 0; }
}
@keyframes sway { from { transform: rotate(-2deg); } to { transform: rotate(2.5deg); } }
@keyframes ripple {
  0% { transform: scale(0.3); opacity: 0; }
  15% { opacity: 0.85; }
  100% { transform: scale(1.7); opacity: 0; }
}
@keyframes glint {
  0%, 100% { transform: scale(0.2); opacity: 0; }
  50% { transform: scale(1); opacity: 0.95; }
}
@keyframes bob { from { transform: translate(-4px, 2px); } to { transform: translate(5px, -3px); } }
@keyframes foam { from { opacity: 0.55; } to { opacity: 0.95; } }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
""".strip()

# Without a backdrop the table shadow must follow the page theme. The transparent
# variant carries no text: titles belong in the README, which knows the real theme.
DARK_CSS = """
@media (prefers-color-scheme: dark) {
  .cast { fill: #000000; opacity: 0.55; }
}
""".strip()

FISH = "M14 0C6 -7 -6 -6 -12 0C-6 6 6 7 14 0ZM-12 0L-21 -6V6Z"
RAY = "M28 0C12 -6 2 -32 -12 -36C-7 -14 -7 14 -12 36C2 32 12 6 28 0Z"
SPARK = "M0 -5L1.2 -1.2L5 0L1.2 1.2L0 5L-1.2 1.2L-5 0L-1.2 -1.2Z"
SLOTS = [(6.2, 1.9), (8.4, 1.9), (6.2, 4.9), (8.4, 4.9), (10.4, 3.4), (3.4, 8.75), (1.6, 6.6)]
PALMS = [
    (-0.3, -0.4, 3.4, (-1.0, -0.3)),
    (0.5, -0.6, 3.0, (0.6, -1.0)),
    (-0.7, 0.5, 2.8, (-0.8, 0.8)),
    (0.6, 0.5, 2.4, (1.0, 0.4)),
    (1.3, -0.2, 2.0, (0.9, -0.2)),
    (-0.2, 1.3, 2.1, (-0.2, 0.9)),
]


ISLETS = [(10.7, 1.7), (1.7, 10.7), (10.6, 10.6)]
ISLET_R, ISLET_TOP = 0.95, 1.6
FULL = {"prs": 1.0, "reviews": 1.0, "issues": 1.0, "stars": 0.6, "forks": 0.0}


def build(bungalows, palms, traits=None, transparent=False):
    """Draw the scene. `traits` maps each activity signal to 0..1 and shapes the island.

    Pull requests grow the vegetation, reviews bring sea life, issues build reefs,
    stars add sparkle on the water, and forks raise satellite islets.
    """
    global ISLAND, ISLAND_R, ISLAND_TOP
    traits = {**FULL, **(traits or {})}
    rnd = random.Random(7)
    slots = SLOTS[:bungalows]
    # Without bungalows the island moves to the middle and fills the block.
    deserted = not slots
    islets = []
    if deserted:
        ISLAND, ISLAND_R, ISLAND_TOP = (5.8, 5.8), 3.7, 2.3
        islets = ISLETS[: round(traits["forks"] * len(ISLETS))]
        palms = min(palms, 1 + round(traits["prs"] * 5))
    o = []
    add = o.append
    # The transparent variant is cropped to the block, its palms and its shadow.
    view = "200 90 1000 790" if transparent else "0 0 1200 890"
    add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img" aria-labelledby="t d">')
    add('<title id="t">Lagoon block</title>')
    add(
        '<desc id="d">An isometric cut block of a tropical lagoon with an island, palms, '
        "stilt bungalows and translucent water, drawn and animated without script.</desc>"
    )
    add(f"<style>{CSS}{DARK_CSS if transparent else ''}</style>")
    top_y, bottom_y = CY - H * S, CY + W * S - H * S
    add(
        "<defs>"
        '<radialGradient id="bg" cx="0.5" cy="0.45" r="0.75">'
        '<stop offset="0" stop-color="#f6f4ee"/><stop offset="1" stop-color="#e6e2d8"/></radialGradient>'
        f'<linearGradient id="water-top" gradientUnits="userSpaceOnUse" x1="0" y1="{top_y:.0f}" x2="0" y2="{bottom_y:.0f}">'
        '<stop offset="0" stop-color="#c4f4e8"/><stop offset="0.55" stop-color="#63d9cf"/>'
        '<stop offset="1" stop-color="#2fc4c2"/></linearGradient>'
        '<linearGradient id="water-side" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#7fe3d8"/><stop offset="1" stop-color="#1fa7a8"/></linearGradient>'
        '<filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="16"/></filter>'
        '<filter id="soft-local" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>'
        '<filter id="caustic" x="0" y="0" width="1" height="1">'
        '<feTurbulence type="turbulence" baseFrequency="0.011" numOctaves="2" seed="4"/>'
        '<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  -6 0 0 0 1"/></filter>'
        # Wave shading: noise is the height map, lit once for shade and once for glints.
        '<filter id="waves" x="0" y="0" width="1" height="1" color-interpolation-filters="sRGB">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.008 0.021" numOctaves="1" seed="21" result="n">'
        '<animate attributeName="baseFrequency" dur="16s" repeatCount="indefinite" '
        'values="0.008 0.021;0.0088 0.0231;0.008 0.021"/></feTurbulence>'
        '<feDiffuseLighting in="n" surfaceScale="8" diffuseConstant="1" lighting-color="#ffffff" result="d">'
        '<feDistantLight azimuth="250" elevation="30"/></feDiffuseLighting>'
        '<feSpecularLighting in="n" surfaceScale="8" specularConstant="1.1" specularExponent="28" '
        'lighting-color="#ffffff" result="s"><feDistantLight azimuth="250" elevation="38"/></feSpecularLighting>'
        '<feComposite in="d" in2="s" operator="arithmetic" k1="0" k2="1" k3="1" k4="0"/></filter>'
        '<filter id="grain" x="0" y="0" width="1" height="1">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.09" numOctaves="2" seed="9"/>'
        '<feColorMatrix values="0 0 0 0 0.35  0 0 0 0 0.22  0 0 0 0 0.1  0 0 0 0.9 -0.35"/></filter>'
        f'<clipPath id="seabed-clip"><rect width="{W * LOCAL:.0f}" height="{W * LOCAL:.0f}"/></clipPath>'
        "</defs>"
    )
    if not transparent:
        add('<rect width="1200" height="890" fill="url(#bg)"/>')

    # Shadow of the whole block on the table.
    base = [(0, 0), (W, 0), (W, W), (0, W)]
    cast = [P(x, y, -DEPTH) for x, y in base] + [P(x + 2.2, y - 1.2, -DEPTH) for x, y in base]
    add(poly(hull(cast), class_="cast", fill="#5b5346", opacity="0.3", filter="url(#soft)"))

    # Soil strata on the two visible cut faces.
    bounds = [(0, 0, 0, 0), (-0.75, 0.06, 1.3, 0.4), (-1.2, 0.08, 0.9, 2.0), (-1.95, 0.1, 0.7, 4.1), (-2.6, 0.08, 1.1, 1.0), (-DEPTH, 0, 0, 0)]
    layers = ["#f3e6c8", "#fbf5e6", "#e6cba0", "#cfa97a", "#8f6a49"]

    def edge(u):
        return (u, W) if u <= W else (W, 2 * W - u)

    def level(i, u):
        b, a, f, p = bounds[i]
        return b + a * math.sin(u * f + p) + a * 0.5 * math.sin(u * f * 2.3 + p * 1.7)

    for start, factor in ((0.0, 1.0), (W, 0.86)):
        us = [start + W * i / 24 for i in range(25)]
        for i, color in enumerate(layers):
            upper = [P(*edge(u), level(i, u)) for u in us]
            lower = [P(*edge(u), level(i + 1, u)) for u in reversed(us)]
            add(solid(upper + lower, shade(color, factor)))
        wet = [P(*edge(u), 0) for u in us] + [P(*edge(u), -0.1) for u in reversed(us)]
        add(poly(wet, fill="#5fc9bf", opacity="0.75"))
    for _ in range(90):
        u, z = rnd.uniform(0.1, 2 * W - 0.1), rnd.uniform(-3.1, -1.3)
        x, y = P(*edge(u), z)
        r = rnd.uniform(1.3, 3.2)
        fill = "#fff8ea" if rnd.random() < 0.75 else "#6d5038"
        add(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{r:.1f}" ry="{r * 0.7:.1f}" fill="{fill}" opacity="0.85"/>')
    for matrix in (face_y(), face_x()):
        add(
            f'<g transform="{matrix}"><rect width="{W * LOCAL:.0f}" height="{DEPTH * LOCAL:.0f}" '
            'filter="url(#grain)" opacity="0.55"/></g>'
        )
    add(line(P(W, W, 0), P(W, W, -DEPTH), stroke="#ffffff", stroke_width="1.2", opacity="0.3"))

    # Inner back walls of the water volume, then the seabed.
    add(poly(P3([(0, 0, 0), (W, 0, 0), (W, 0, H), (0, 0, H)]), fill="#bfeee4"))
    add(poly(P3([(0, 0, 0), (0, W, 0), (0, W, H), (0, 0, H)]), fill="#d2f4ea"))
    add(poly(P3([(0, 0, 0), (W, 0, 0), (W, W, 0), (0, W, 0)]), fill="#eedcb2"))

    shadow = (1.0, -0.55)
    rings = [] if deserted else [(5.6, 9.7, "#ff7fa0"), (11.0, 6.7, "#ffb347"), (6.0, 6.9, "#7fb6ff")]
    canoe_path = ellipse_path(860, 890, 190, 150)
    add(f'<g transform="{ground(0)}" clip-path="url(#seabed-clip)">')
    for _ in range(14):
        x, y = rnd.uniform(60, 1140), rnd.uniform(60, 1140)
        add(
            f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{rnd.uniform(60, 150):.0f}" '
            f'ry="{rnd.uniform(30, 70):.0f}" fill="#fbf0d2" opacity="0.5"/>'
        )
    add(f'<rect width="{W * LOCAL:.0f}" height="{W * LOCAL:.0f}" filter="url(#caustic)" opacity="0.5"/>')
    add('<g filter="url(#soft-local)" fill="#16484a" opacity="0.3">')
    for xc, yc in slots:
        x0, y0 = (xc - 0.75 + shadow[0]) * LOCAL, (yc - 0.75 + shadow[1]) * LOCAL
        add(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="150" height="200"/>')
    if slots:
        add(f'<rect x="{(4.4 + shadow[0]) * LOCAL:.0f}" y="{(3.15 + shadow[1]) * LOCAL:.0f}" width="525" height="50"/>')
    if len(slots) > 5:
        add(f'<rect x="{(3.15 + shadow[0]) * LOCAL:.0f}" y="{(4.6 + shadow[1]) * LOCAL:.0f}" width="50" height="340"/>')
    add("</g>")
    palette = ["#ff8a7a", "#ffb347", "#b07cff", "#5fd3a8", "#ff6fb5", "#ffd95e"]
    reefs = [(9.5, 7.2), (7.2, 9.6), (10.3, 10.2), (5.2, 8.0), (1.6, 10.3), (10.6, 5.6), (8.6, 6.8), (6.0, 10.8), (1.0, 6.0), (10.8, 1.2), (4.6, 11.0)]
    if deserted:
        reefs = [(10.9, 6.2), (6.0, 11.0), (9.6, 9.0), (1.0, 6.0), (2.4, 8.9), (6.2, 0.9), (1.2, 1.4), (8.9, 2.6), (3.6, 10.9), (9.0, 11.0)]
        reefs = reefs[: round(2 + traits["issues"] * 8)]
    for x, y in reefs:
        cx, cy = x * LOCAL, y * LOCAL
        add(f'<ellipse cx="{cx + 14:.0f}" cy="{cy - 8:.0f}" rx="52" ry="40" fill="#16484a" opacity="0.2"/>')
        add(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="46" ry="36" fill="#d6caa8"/>')
        for _ in range(7):
            px, py, r = cx + rnd.uniform(-34, 34), cy + rnd.uniform(-26, 26), rnd.uniform(8, 17)
            color = rnd.choice(palette)
            add(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="{r:.0f}" fill="{color}"/>')
            add(f'<circle cx="{px - r * 0.3:.0f}" cy="{py - r * 0.3:.0f}" r="{r * 0.4:.0f}" fill="{shade(color, 1.18)}"/>')
    for x, y, _ in rings:
        add(
            f'<circle cx="{(x + 0.75) * LOCAL:.0f}" cy="{(y - 0.4) * LOCAL:.0f}" r="22" fill="none" '
            'stroke="#16484a" stroke-width="13" opacity="0.2"/>'
        )
    if not deserted:
        add(
            '<g transform="translate(75 -40)" opacity="0.22">'
            f'<g><animateMotion dur="26s" repeatCount="indefinite" rotate="auto" path="{canoe_path}"/>'
            '<path d="M48 0C20 -14 -20 -14 -48 0C-20 14 20 14 48 0Z" fill="#16484a"/></g></g>'
        )
    add("</g>")

    # Submerged part of the island, tinted by depth.
    for z in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.15):
        add(solid(P3(island_ring(z)), mix("#e2d3a4", "#f7ebcb", z / H)))
    for center in islets:
        for z in (0.0, 0.3, 0.6, 0.9, 1.15):
            ring = island_ring(z, center=center, radius=ISLET_R, top=ISLET_TOP)
            add(solid(P3(ring), mix("#e2d3a4", "#f7ebcb", z / H)))

    # Full-height posts, seen through the water below the surface.
    posts = []
    for xc, yc in slots:
        x0, x1, y0, y1 = xc - 0.65, xc + 0.65, yc - 0.65, yc + 1.15
        posts += [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    segments_a = [(4.4 + i * 1.05, 4.4 + (i + 1) * 1.05) for i in range(5 if slots else 0)]
    segments_b = [(4.6 + i * 0.85, 4.6 + (i + 1) * 0.85) for i in range(4)]
    for x0, _ in segments_a:
        posts += [(x0 + 0.1, 3.2), (x0 + 0.1, 3.6)]
    if len(slots) > 5:
        for y0, _ in segments_b:
            posts += [(3.2, y0 + 0.1), (3.6, y0 + 0.1)]
    posts.sort(key=lambda p: p[0] + p[1])
    for px, py in posts:
        add("".join(post(px, py, 0, H)))

    # Fish and rays swim in a plane below the surface.
    add(f'<g transform="{ground(0.5)}">')
    schools = [
        (ellipse_path(520, 930, 260, 140), 18, 7, "#1d6f7a"),
        (ellipse_path(980, 960, 150, 120, False), 14, 5, "#235f86"),
        (ellipse_path(1020, 130, 110, 70), 12, 4, "#1d6f7a"),
    ]
    rays = [(ellipse_path(760, 860, 330, 230, False), 44, 0), (ellipse_path(960, 640, 160, 100), 30, 9)]
    if deserted:
        # Everything circles the island, in both directions and at two radii.
        schools = [
            (ellipse_path(580, 580, 470, 470), 34, 9, "#1d6f7a"),
            (ellipse_path(580, 580, 530, 530, False), 46, 6, "#235f86"),
            (ellipse_path(600, 1090, 110, 55), 12, 4, "#1d6f7a"),
        ]
        schools = [(p, d, round(n * traits["reviews"]), c) for p, d, n, c in schools]
        rays = [(ellipse_path(580, 580, 500, 500, False), 70, 0), (ellipse_path(580, 580, 440, 440), 58, 20)]
        rays = rays[: (traits["reviews"] > 0.35) + (traits["reviews"] > 0.7)]
    for path, duration, count, color in schools:
        for i in range(count):
            add(
                f'<g><animateMotion dur="{duration}s" begin="-{i * 0.45 + rnd.uniform(0, 0.2):.2f}s" '
                f'repeatCount="indefinite" rotate="auto" path="{path}"/>'
                f'<path d="{FISH}" transform="translate(0 {rnd.uniform(-26, 26):.0f}) scale(1.6)" fill="{color}" opacity="0.75"/></g>'
            )
    for path, duration, begin in rays:
        add(
            f'<g><animateMotion dur="{duration}s" begin="-{begin}s" repeatCount="indefinite" rotate="auto" path="{path}"/>'
            f'<path d="{RAY}" fill="#2a5f73" opacity="0.8"/>'
            '<path d="M-10 0L-52 0" stroke="#2a5f73" stroke-width="3" stroke-linecap="round" opacity="0.8"/></g>'
        )
    add("</g>")

    # Water volume: translucent top, two cut faces, glass-edge highlights.
    top = P3([(0, 0, H), (W, 0, H), (W, W, H), (0, W, H)])
    add(poly(top, fill="url(#water-top)", fill_opacity="0.6"))
    add(poly(P3([(0, W, 0), (W, W, 0), (W, W, H), (0, W, H)]), fill="url(#water-side)", fill_opacity="0.62"))
    add(poly(P3([(W, W, 0), (W, 0, 0), (W, 0, H), (W, W, H)]), fill="url(#water-side)", fill_opacity="0.72"))
    add(poly(P3([(0, W, H - 0.13), (W, W, H - 0.13), (W, W, H), (0, W, H)]), fill="#ffffff", opacity="0.28"))
    add(poly(P3([(W, W, H - 0.13), (W, 0, H - 0.13), (W, 0, H), (W, W, H)]), fill="#ffffff", opacity="0.2"))
    add(f'<polyline points="{fmt(P3([(0, W, H), (0, 0, H), (W, 0, H)]))}" fill="none" stroke="#ffffff" stroke-width="1.2" opacity="0.45"/>')
    add(f'<polyline points="{fmt(P3([(0, W, H), (W, W, H), (W, 0, H)]))}" fill="none" stroke="#ffffff" stroke-width="1.8" opacity="0.85"/>')
    add(line(P(W, W, H), P(W, W, 0), stroke="#ffffff", stroke_width="1.4", opacity="0.5"))

    # Everything that lies flat on the water surface.
    add(f'<g transform="{ground(H)}">')
    add(
        f'<rect width="{W * LOCAL:.0f}" height="{W * LOCAL:.0f}" filter="url(#waves)" '
        'opacity="0.32" style="mix-blend-mode:soft-light"/>'
    )
    shore ="M" + "L".join(f"{x * LOCAL:.0f} {y * LOCAL:.0f}" for x, y, _ in island_ring(H, 1.04)) + "Z"
    wide = "M" + "L".join(f"{x * LOCAL:.0f} {y * LOCAL:.0f}" for x, y, _ in island_ring(H, 1.16)) + "Z"
    add(f'<path d="{wide}" fill="#eafff8" opacity="0.3"/>')
    # Small waves roll in toward the beach, half a cycle apart.
    for delay in (0, 3.5):
        add(
            f'<path class="swash" d="{shore}" fill="none" stroke="#ffffff" stroke-width="5" '
            f'stroke-linejoin="round" style="animation-delay:-{delay}s"/>'
        )
    add(f'<path class="foam" d="{shore}" fill="none" stroke="#ffffff" stroke-width="9" stroke-linejoin="round"/>')
    for center in islets:
        ring = island_ring(H, 1.08, center=center, radius=ISLET_R, top=ISLET_TOP)
        d = "M" + "L".join(f"{x * LOCAL:.0f} {y * LOCAL:.0f}" for x, y, _ in ring) + "Z"
        add(f'<path class="foam" d="{d}" fill="none" stroke="#ffffff" stroke-width="7" stroke-linejoin="round"/>')
    add('<g filter="url(#soft-local)" fill="#0c5558" opacity="0.3">')
    for xc, yc in slots:
        add(f'<rect x="{(xc - 0.6) * LOCAL:.0f}" y="{(yc - 0.85) * LOCAL:.0f}" width="150" height="200"/>')
    if slots:
        add('<rect x="455" y="305" width="525" height="50"/>')
    if len(slots) > 5:
        add('<rect x="330" y="450" width="50" height="340"/>')
    add("</g>")
    ripples = [(7.6, 8.4), (10.2, 9.4), (4.9, 10.2), (9.6, 0.9), (1.2, 8.6), (11.0, 5.2)]
    if deserted:
        ripples = [(10.2, 9.6), (2.0, 9.8), (9.8, 2.2), (8.6, 10.8), (11.0, 7.4), (4.0, 11.0)]
    for x, y in ripples:
        for k in range(2):
            add(
                f'<circle class="ripple" cx="{x * LOCAL:.0f}" cy="{y * LOCAL:.0f}" r="34" fill="none" '
                f'stroke="#ffffff" stroke-width="3.5" style="animation-delay:-{rnd.uniform(0, 5) + k * 2.5:.2f}s"/>'
            )
    for x, y, color in rings:
        add(
            f'<g class="bob" style="animation-delay:-{rnd.uniform(0, 4):.2f}s">'
            f'<circle cx="{x * LOCAL:.0f}" cy="{y * LOCAL:.0f}" r="22" fill="none" stroke="{color}" stroke-width="13"/>'
            f'<circle cx="{x * LOCAL:.0f}" cy="{y * LOCAL:.0f}" r="22" fill="none" stroke="#ffffff" stroke-width="13" stroke-dasharray="17.3 17.3"/>'
            "</g>"
        )
    if not deserted:
        add(
            f'<g><animateMotion dur="26s" repeatCount="indefinite" rotate="auto" path="{canoe_path}"/>'
            '<path d="M-48 0C-70 -10 -86 -4 -96 0C-86 4 -70 10 -48 0Z" fill="#ffffff" opacity="0.45"/>'
            '<path d="M48 0C20 -14 -20 -14 -48 0C-20 14 20 14 48 0Z" fill="#e8704a"/>'
            '<path d="M40 0C18 -9 -18 -9 -40 0C-18 9 18 9 40 0Z" fill="#f4a57f"/>'
            '<path d="M6 -26L-6 26" stroke="#5b4027" stroke-width="3" stroke-linecap="round"/>'
            '<circle r="8" fill="#3b2f2a"/></g>'
        )
    add("</g>")
    for _ in range(round(4 + traits["stars"] * 20)):
        while True:
            x, y = rnd.uniform(0.4, W - 0.4), rnd.uniform(0.4, W - 0.4)
            if math.hypot(x - ISLAND[0], y - ISLAND[1]) > ISLAND_R * 0.93:
                break
        sx, sy = P(x, y, H)
        add(
            f'<g transform="translate({sx:.1f} {sy:.1f})"><path class="glint" d="{SPARK}" fill="#ffffff" '
            f'style="animation-delay:-{rnd.uniform(0, 3.2):.2f}s"/></g>'
        )

    # Island above the waterline.
    for i in range(8):
        z = H + (ISLAND_TOP - H) * i / 7
        add(solid(P3(island_ring(z)), mix("#f6e9c8", "#fff7e2", i / 7)))
    add(poly(P3(island_ring(ISLAND_TOP, 0.8)), fill="#a9d481", opacity="0.85"))

    # Standing objects, painted far to near.
    items = []
    spread = 1.35 if deserted else 1.0
    for i, (dx, dy, height, lean) in enumerate(PALMS[:palms]):
        x, y = ISLAND[0] + dx * spread, ISLAND[1] + dy * spread
        grown = height * (0.7 + 0.45 * traits["prs"]) if deserted else height
        items.append((x + y, palm(x, y, grown, lean, 100 + i)))
    for i, center in enumerate(islets):
        parts = []
        for k in range(5):
            z = H + (ISLET_TOP - H) * k / 4
            ring = island_ring(z, center=center, radius=ISLET_R, top=ISLET_TOP)
            parts.append(solid(P3(ring), mix("#f6e9c8", "#fff7e2", k / 4)))
        parts += palm(center[0], center[1], 1.3, (0.3, -0.2), 300 + i, bz=ISLET_TOP, size=0.55)
        items.append((center[0] + center[1], parts))
    bushes = ((-1.2, -0.2), (0.1, -1.2), (1.0, 1.0), (-0.9, 1.1), (1.5, 0.4), (0.2, 0.3))
    if deserted:
        bushes = bushes[: round(1 + traits["prs"] * 5)]
    for i, (dx, dy) in enumerate(bushes):
        x, y = ISLAND[0] + dx * spread, ISLAND[1] + dy * spread
        items.append((x + y - 0.2, bush(x, y, 200 + i)))
    for xc, yc in slots:
        items.append((xc + yc + 0.25, bungalow(xc, yc)))
    for x0, x1 in segments_a:
        part = post(x0 + 0.1, 3.2, H, DECK - 0.1) + post(x0 + 0.1, 3.6, H, DECK - 0.1)
        items.append(((x0 + x1) / 2 + 3.4, part + deck(x0, 3.15, x1, 3.65, along_x=False)))
    for xc, yc in slots[2:4]:
        items.append((xc + 3.9, deck(xc - 0.25, 3.65, xc + 0.25, yc - 0.75)))
    if len(slots) > 5:
        for y0, y1 in segments_b:
            part = post(3.2, y0 + 0.1, H, DECK - 0.1) + post(3.6, y0 + 0.1, H, DECK - 0.1)
            items.append((3.4 + (y0 + y1) / 2, part + deck(3.15, y0, 3.65, y1)))
    if len(slots) > 6:
        items.append((2.75 + 6.6, deck(2.35, 6.35, 3.15, 6.85, along_x=False)))
    items.sort(key=lambda item: item[0])
    for _, parts in items:
        add("".join(parts))

    if not transparent:
        add(
            '<g fill="#2b2925" font-family="Georgia, serif">'
            '<text x="44" y="64" font-family="sans-serif" font-size="11" letter-spacing="2.4">SVG STUDY</text>'
            '<text x="42" y="134" font-size="66" font-style="italic">Lagoon</text>'
            '<text x="42" y="198" font-size="66" font-style="italic">Block.</text>'
            '<text x="44" y="236" font-size="14" fill="#5a564d">One static file. No script, no canvas,</text>'
            '<text x="44" y="256" font-size="14" fill="#5a564d">no external assets.</text>'
            "</g>"
        )
    add("</svg>")
    return "\n".join(o) + "\n"


if __name__ == "__main__":
    clear = "transparent" in sys.argv
    if clear:
        sys.argv.remove("transparent")
    target = Path(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else len(SLOTS)
    trees, profile = len(PALMS), None
    if len(sys.argv) > 3 and "," in sys.argv[3]:
        # prs,reviews,issues,stars,forks, each from 0 to 1.
        profile = dict(zip(FULL, (float(v) for v in sys.argv[3].split(","))))
    elif len(sys.argv) > 3:
        trees = int(sys.argv[3])
    svg = build(count, trees, profile, clear)
    target.write_text(svg, encoding="utf-8")
    print(f"{target.name}: {len(svg.encode())} bytes, {svg.count('<') - svg.count('</')} elements")
