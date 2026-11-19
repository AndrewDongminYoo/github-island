"""Draw an isometric island as one self-contained animated SVG.

The scene is modelled in 3D world units, projected to 2D here, and painted
back to front. The browser only runs CSS and SMIL animation on the result.
Nothing here reads the clock, the network or the file system: the same traits
and the same key always give the same bytes.
"""

import math
import random

A = math.cos(math.radians(30))
B = 0.5
S = 40.0  # pixels per world unit
CX, CY = 640.0, 225.0  # screen position of the far block corner at z = 0
W = 12.0  # block edge length
H = 1.3  # water depth
DEPTH = 3.2  # thickness of the soil below the seabed
DECK = 1.75  # deck height above the seabed
LOCAL = 100.0  # local units per world unit inside plane-mapped groups
ISLAND = (5.8, 5.8)
ISLAND_R, ISLAND_TOP = 3.7, 2.3
WOOD = "#b98a5a"
POST = "#7d5a3a"
THATCH = "#cfa95f"
WALL = "#f7f0e3"


def P(x, y, z=0.0):
    return (CX + (x - y) * A * S, CY + (x + y) * B * S - z * S)


def P3(points):
    return [P(*p) for p in points]


def num(value):
    """Format a coordinate to one decimal place without a trailing `.0`."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def offset(x, y, z=0.0):
    """Screen offset of a world displacement. The projection is translation-invariant,
    so a shape drawn once can be reused anywhere with a plain translate."""
    return ((x - y) * A * S, (x + y) * B * S - z * S)


def place(x, y):
    dx, dy = offset(x, y)
    return f"translate({num(dx)} {num(dy)})"


def fmt(points):
    return " ".join(f"{num(x)},{num(y)}" for x, y in points)


def attrs(kw):
    return "".join(f' {k.rstrip("_").replace("_", "-")}="{v}"' for k, v in kw.items())


def poly(points, **kw):
    return f'<polygon points="{fmt(points)}"{attrs(kw)}/>'


def solid(points, fill):
    # The "s" class fills with `color` and adds a hairline stroke in the same color,
    # which hides seams between adjacent faces at the cost of one attribute.
    return f'<polygon class="s" color="{fill}" points="{fmt(points)}"/>'


def line(a, b, **kw):
    return (
        f'<line x1="{num(a[0])}" y1="{num(a[1])}" x2="{num(b[0])}" y2="{num(b[1])}"'
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
    return (
        f"matrix({A * k:.4f} {-B * k:.4f} 0 {k:.4f} {CX:.1f} {CY + 2 * B * S * W:.1f})"
    )


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
        solid(
            P3([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]),
            shade(color, fx),
        ),
        solid(
            P3([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]),
            shade(color, fy),
        ),
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
    for a, b, f in (
        (c00, c10, 1.04),
        (c00, c01, 0.96),
        (c10, c11, 0.74),
        (c01, c11, 0.9),
    ):
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
            out.append(
                line(P(x0, y, DECK), P(x1, y, DECK), stroke=stroke, stroke_width="0.6")
            )
    else:
        steps = int((x1 - x0) / 0.18)
        for i in range(1, steps):
            x = x0 + (x1 - x0) * i / steps
            out.append(
                line(P(x, y0, DECK), P(x, y1, DECK), stroke=stroke, stroke_width="0.6")
            )
    return out


def bungalow(xc, yc):
    x0, x1, y0, y1 = xc - 0.75, xc + 0.75, yc - 0.75, yc + 1.25
    out = []
    corners = [
        (x0 + 0.1, y0 + 0.1),
        (x1 - 0.1, y0 + 0.1),
        (x0 + 0.1, y1 - 0.1),
        (x1 - 0.1, y1 - 0.1),
    ]
    for px, py in corners:
        out += post(px, py, H, DECK - 0.1)
    out += deck(x0, y0, x1, y1)
    # Ladder from the porch into the water.
    for dx in (0.25, 0.45):
        out.append(
            line(
                P(xc + dx, y1, DECK),
                P(xc + dx, y1 + 0.12, H - 0.1),
                stroke="#f3ede0",
                stroke_width="1.3",
            )
        )
    # Sun loungers on the porch.
    for lx in (xc - 0.55, xc - 0.15):
        out += box(lx, yc + 0.72, DECK, lx + 0.26, yc + 1.15, DECK + 0.07, "#ffffff")
        out += box(
            lx, yc + 0.72, DECK + 0.07, lx + 0.26, yc + 0.84, DECK + 0.17, "#8fd6d0"
        )
    wz = DECK + 1.0
    out += box(xc - 0.6, yc - 0.6, DECK, xc + 0.6, yc + 0.6, wz, WALL)
    door = [
        (xc - 0.2, yc + 0.6, DECK),
        (xc + 0.2, yc + 0.6, DECK),
        (xc + 0.2, yc + 0.6, DECK + 0.58),
        (xc - 0.2, yc + 0.6, DECK + 0.58),
    ]
    out.append(solid(P3(door), "#6b4a33"))
    window = [
        (xc + 0.6, yc - 0.3, DECK + 0.3),
        (xc + 0.6, yc + 0.3, DECK + 0.3),
        (xc + 0.6, yc + 0.3, DECK + 0.6),
        (xc + 0.6, yc - 0.3, DECK + 0.6),
    ]
    out.append(poly(P3(window), fill="#8fcfe0", stroke="#fffaf0", stroke_width="1"))
    # Eave shadow on the two visible walls.
    for band in (
        [
            (xc + 0.6, yc - 0.6, wz - 0.16),
            (xc + 0.6, yc + 0.6, wz - 0.16),
            (xc + 0.6, yc + 0.6, wz),
            (xc + 0.6, yc - 0.6, wz),
        ],
        [
            (xc - 0.6, yc + 0.6, wz - 0.16),
            (xc + 0.6, yc + 0.6, wz - 0.16),
            (xc + 0.6, yc + 0.6, wz),
            (xc - 0.6, yc + 0.6, wz),
        ],
    ):
        out.append(poly(P3(band), fill="#3a2a18", opacity="0.22"))
    out += roof(xc, yc, 0.86, wz, 0.7, THATCH)
    return out


def island_radius(theta, z, radius=None, top=None):
    radius = ISLAND_R if radius is None else radius
    top = ISLAND_TOP if top is None else top
    wobble = (
        1
        + 0.10 * math.sin(3 * theta + 0.6)
        + 0.06 * math.sin(5 * theta + 2.1)
        + 0.04 * math.sin(2 * theta + 4)
    )
    return radius * (1 - 0.7 * (z / top) ** 1.6) * wobble


def island_ring(z, scale=1.0, n=48, center=None, radius=None, top=None):
    cx, cy = ISLAND if center is None else center
    return [
        (
            cx
            + island_radius(2 * math.pi * i / n, z, radius, top)
            * scale
            * math.cos(2 * math.pi * i / n),
            cy
            + island_radius(2 * math.pi * i / n, z, radius, top)
            * scale
            * math.sin(2 * math.pi * i / n),
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


CROWN_FRONDS = 12


def crown_defs(variant, key):
    """Define one palm crown around the origin, frond by frond in paint order.

    Every palm reuses these fronds, so a scene pays for the frond geometry once.
    """
    rnd = random.Random(f"{key}:crown:{variant}")
    fronds = []
    for k in range(CROWN_FRONDS):
        theta = 2 * math.pi * k / CROWN_FRONDS + rnd.uniform(-0.2, 0.2)
        fronds.append((math.cos(theta) + math.sin(theta), theta, k))
    fronds.sort()
    out = []
    for order, (depth, theta, k) in enumerate(fronds):
        reach = rnd.uniform(1.45, 1.95)
        rise = rnd.uniform(0.9, 1.4)
        droop = rise + rnd.uniform(0.6, 1.0)
        mid = [
            offset(
                math.cos(theta) * reach * i / 12,
                math.sin(theta) * reach * i / 12,
                rise * i / 12 - droop * (i / 12) ** 2,
            )
            for i in range(13)
        ]
        widths = [9.5 * 2.3 * (i / 12) ** 0.5 * (1 - i / 12) ** 0.7 for i in range(13)]
        left, right = ribbon(mid, widths)
        base = "#2a8348" if depth < -0.3 else ("#3f9f55" if k % 2 else "#57b866")
        cuts = "".join(
            f"M{num(left[i][0])} {num(left[i][1])}L{num(mid[i - 1][0])} {num(mid[i - 1][1])}"
            f"L{num(right[i][0])} {num(right[i][1])}"
            for i in range(2, 12)
        )
        out.append(
            f'<g id="c{variant}f{order}">'
            + solid(left + right[::-1], base)
            + f'<path d="{cuts}" fill="none" stroke="{shade(base, 0.68)}" stroke-width="0.8" opacity="0.6"/>'
            + f'<polyline points="{fmt(mid)}" fill="none" stroke="{shade(base, 1.3)}" stroke-width="1"/>'
            + "</g>"
        )
    return "".join(out)


def palm(bx, by, height, lean, seed, bz=None, size=1.0):
    if bz is None:
        bz = island_height(bx - ISLAND[0], by - ISLAND[1])
    out = []
    spine = [
        P(
            bx + lean[0] * (i / 10) ** 2,
            by + lean[1] * (i / 10) ** 2,
            bz + height * i / 10,
        )
        for i in range(11)
    ]
    widths = [(5.6 - 2.6 * i / 10) * size for i in range(11)]
    left, right = ribbon(spine, widths)
    out.append(solid(left + right[::-1], "#b08d63"))
    for i in range(1, 10):
        out.append(
            line(left[i], right[i], stroke="#8a6b47", stroke_width="1", opacity="0.7")
        )
    sx, sy = P(bx + lean[0], by + lean[1], bz + height)
    # The crown is one of two shared shapes, mirrored for half of the palms and
    # scaled with the trunk. Each frond sways about the crown, the group's origin.
    scale = size * (0.75 + height / 12)
    variant, mirror = seed % 2, -1 if seed % 4 > 1 else 1
    fronds = "".join(
        f'<g class="frond d{(order * 3 + seed) % 8}"><use href="#c{variant}f{order}"/></g>'
        for order in range(CROWN_FRONDS)
    )
    out.append(
        f'<g transform="translate({num(sx)} {num(sy)}) scale({mirror * scale:.2f} {scale:.2f})">'
        f'{fronds}<use href="#nuts"/></g>'
    )
    return out


def bush(x, y, key, index):
    rnd = random.Random(f"{key}:bush:{index}")
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
.s { fill: currentColor; stroke: currentColor; stroke-width: 0.7px; stroke-linejoin: round; }
.frond { transform-origin: 0 0; animation: sway 6s ease-in-out infinite alternate; }
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
/* Delay classes come after every `animation` shorthand, which would reset the delay. */
.d1 { animation-delay: -0.7s; }
.d2 { animation-delay: -1.4s; }
.d3 { animation-delay: -2.1s; }
.d4 { animation-delay: -2.8s; }
.d5 { animation-delay: -3.5s; }
.d6 { animation-delay: -4.2s; }
.d7 { animation-delay: -4.9s; }
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
DOLPHIN_OUTLINE = (
    "M56 0C42 -12 4 -15 -34 -5L-50 -2C-58 -9 -66 -15 -74 -15C-69 -6 -67 0 -67 0"
    "C-67 0 -69 6 -74 15C-66 15 -58 9 -50 2L-34 5C4 15 42 12 56 0Z"
)
DOLPHIN_FIN = "M20 -11C12 -25 0 -30 -8 -27C0 -21 6 -15 8 -10Z"
DOLPHIN = (
    f'<path d="{DOLPHIN_FIN}" fill="#5d7f99"/><path d="{DOLPHIN_FIN}" transform="scale(1 -1)" fill="#5d7f99"/>'
    f'<path d="{DOLPHIN_OUTLINE}" fill="#6f93ad"/>'
    '<path d="M56 0L70 0" stroke="#6f93ad" stroke-width="5" stroke-linecap="round"/>'
    '<path d="M40 0C20 -4 -10 -4 -30 0C-10 4 20 4 40 0Z" fill="#a9c4d6" opacity="0.6"/>'
)
WHALE_OUTLINE = (
    "M120 0C118 -22 90 -30 50 -26C0 -22 -60 -10 -95 -3C-105 -12 -118 -24 -130 -26"
    "C-124 -12 -120 0 -120 0C-120 0 -124 12 -130 26C-118 24 -105 12 -95 3"
    "C-60 10 0 22 50 26C90 30 118 22 120 0Z"
)
WHALE_FIN = "M62 -26C52 -54 30 -64 12 -62C26 -50 34 -38 36 -25Z"
TURTLE_FRONT = "M10 -12C22 -30 34 -30 38 -22C28 -22 20 -14 14 -8Z"
TURTLE_REAR = "M-14 -10C-24 -20 -30 -18 -30 -12C-24 -12 -18 -8 -14 -6Z"
TURTLE = (
    '<g transform="scale(1.25)">'
    f'<path d="{TURTLE_FRONT}" fill="#7fae6a"/><path d="{TURTLE_FRONT}" transform="scale(1 -1)" fill="#7fae6a"/>'
    f'<path d="{TURTLE_REAR}" fill="#7fae6a"/><path d="{TURTLE_REAR}" transform="scale(1 -1)" fill="#7fae6a"/>'
    '<circle cx="26" r="7" fill="#7fae6a"/><ellipse rx="22" ry="17" fill="#4f8a52"/>'
    '<ellipse rx="14" ry="10" fill="#74ad6b"/></g>'
)
RAY_BODY = (
    f'<path d="{RAY}" fill="#2a5f73" opacity="0.8"/>'
    '<path d="M-10 0L-52 0" stroke="#2a5f73" stroke-width="3" stroke-linecap="round" opacity="0.8"/>'
)
PALMS = [
    (-0.3, -0.4, 3.4, (-1.0, -0.3)),
    (0.5, -0.6, 3.0, (0.6, -1.0)),
    (-0.7, 0.5, 2.8, (-0.8, 0.8)),
    (0.6, 0.5, 2.4, (1.0, 0.4)),
    (1.3, -0.2, 2.0, (0.9, -0.2)),
    (-0.2, 1.3, 2.1, (-0.2, 0.9)),
]
BUSHES = [(-1.2, -0.2), (0.1, -1.2), (1.0, 1.0), (-0.9, 1.1), (1.5, 0.4), (0.2, 0.3)]
SPREAD = 1.35  # palm and bush offsets are scaled out to fill the island top
ISLETS = [(10.7, 1.7), (1.7, 10.7), (10.6, 10.6)]
ISLET_R, ISLET_TOP = 0.95, 1.6
REEFS = [
    (10.9, 6.2),
    (6.0, 11.0),
    (9.6, 9.0),
    (1.0, 6.0),
    (2.4, 8.9),
    (6.2, 0.9),
    (1.2, 1.4),
    (8.9, 2.6),
    (3.6, 10.9),
    (9.0, 11.0),
]
RIPPLES = [(10.2, 9.6), (2.0, 9.8), (9.8, 2.2), (8.6, 10.8), (11.0, 7.4), (4.0, 11.0)]
# Visitors arrive in this order as the review signal grows.
RINGS = [(2.0, 7.9, "#ff7fa0"), (4.3, 9.3, "#ffb347"), (8.0, 9.4, "#7fb6ff")]
PARASOLS = [(1.3, 1.9, "#e8504a"), (1.9, -0.9, "#3f8fd0"), (0.2, 2.2, "#f2b134")]
HOMES = [(10.9, 5.8), (9.3, 4.3), (9.3, 7.55)]
JETTY_X, JETTY_Y, JETTY_SEGMENT = 8.0, 5.55, 1.075
SHADOW = (1.0, -0.55)  # offset of a deck's shadow on the seabed
DEFAULT = {"prs": 0.5, "reviews": 0.5, "issues": 0.5, "stars": 0.5, "forks": 0.34}


def steps(value, *cuts):
    """Count the thresholds that `value` has passed."""
    return sum(value > cut for cut in cuts)


def lane(radius, clockwise=True):
    cx, cy = ISLAND[0] * LOCAL, ISLAND[1] * LOCAL
    return ellipse_path(cx, cy, radius * LOCAL, radius * LOCAL, clockwise)


def swim(path, duration, begin, body):
    return (
        f'<g><animateMotion dur="{duration}s" begin="-{begin:.2f}s" repeatCount="indefinite" '
        f'rotate="auto" path="{path}"/>{body}</g>'
    )


def wildlife(prs, key):
    """Return swimmers and their seabed shadows. Larger animals join as `prs` grows."""
    rnd = random.Random(f"{key}:wildlife")
    bodies, shadows = [], []
    schools = [
        (lane(4.7), 34, 3 + round(6 * prs), "#1d6f7a"),
        (lane(5.3, False), 46, round(6 * prs), "#235f86"),
        (ellipse_path(600, 1090, 110, 55), 12, round(4 * prs), "#1d6f7a"),
    ]
    for path, duration, count, color in schools:
        for i in range(count):
            fish = (
                f'<path d="{FISH}" transform="translate(0 {rnd.uniform(-26, 26):.0f}) scale(1.6)" '
                f'fill="{color}" opacity="0.75"/>'
            )
            bodies.append(swim(path, duration, i * 0.45 + rnd.uniform(0, 0.2), fish))
    for i in range(steps(prs, 0.2, 0.5)):
        bodies.append(
            swim(lane((4.55, 5.15)[i], i == 0), (52, 64)[i], (32, 13)[i], TURTLE)
        )
    for i in range(steps(prs, 0.4, 0.7)):
        bodies.append(
            swim(lane((5.0, 4.4)[i], i == 1), (70, 58)[i], (33, 40)[i], RAY_BODY)
        )
    if prs > 0.6:
        for i in range(3):
            place = f"translate({-i * 20} {(-36, 32, 0)[i]})"
            path, begin = lane(4.9, False), 8.4 + i * 1.1
            bodies.append(
                swim(path, 30, begin, f'<g transform="{place}">{DOLPHIN}</g>')
            )
            shadows.append(
                swim(
                    path,
                    30,
                    begin,
                    f'<path d="{DOLPHIN_OUTLINE}" transform="{place}"/>',
                )
            )
    if prs > 0.85:
        spots = ""
        for _ in range(30):
            x = rnd.uniform(-70, 105)
            half = 9 + 15 * min(1.0, (x + 70) / 110)
            spots += (
                f'<circle cx="{x:.0f}" cy="{rnd.uniform(-half, half) * 0.8:.0f}" r="{rnd.uniform(1.8, 3.2):.1f}" '
                'fill="#ffffff" opacity="0.65"/>'
            )
        whale = (
            f'<path d="{WHALE_FIN}" fill="#34546b"/><path d="{WHALE_FIN}" transform="scale(1 -1)" fill="#34546b"/>'
            f'<path d="{WHALE_OUTLINE}" fill="#3f627c"/>{spots}'
        )
        path = lane(5.2, False)
        bodies.append(swim(path, 90, 33, whale))
        shadows.append(swim(path, 90, 33, f'<path d="{WHALE_OUTLINE}"/>'))
    return bodies, shadows


def parasol(x, y, color):
    """A beach parasol with a towel and a sunbather beside it."""
    z = island_height(x - ISLAND[0], y - ISLAND[1])
    out = []
    towel = [
        (x - 0.58, y + 0.12),
        (x - 0.12, y + 0.12),
        (x - 0.12, y + 0.78),
        (x - 0.58, y + 0.78),
    ]
    out.append(solid(P3([(tx, ty, z + 0.02) for tx, ty in towel]), "#ffffff"))
    stripe = [
        (x - 0.42, y + 0.12),
        (x - 0.28, y + 0.12),
        (x - 0.28, y + 0.78),
        (x - 0.42, y + 0.78),
    ]
    out.append(solid(P3([(tx, ty, z + 0.02) for tx, ty in stripe]), color))
    head, hip, feet = (
        P(x - 0.35, y + 0.24, z + 0.07),
        P(x - 0.35, y + 0.46, z + 0.07),
        P(x - 0.35, y + 0.7, z + 0.07),
    )
    out.append(
        line(hip, feet, stroke="#e9a97f", stroke_width="4", stroke_linecap="round")
    )
    out.append(
        line(head, hip, stroke="#2f6f8f", stroke_width="4.6", stroke_linecap="round")
    )
    out.append(
        f'<circle cx="{head[0]:.1f}" cy="{head[1] - 2.5:.1f}" r="2.8" fill="#4a3324"/>'
    )
    out.append(
        line(P(x, y, z), P(x, y, z + 0.95), stroke="#8a6b47", stroke_width="1.8")
    )
    apex = (x, y, z + 0.98)
    faces = []
    for k in range(8):
        a0, a1 = 2 * math.pi * k / 8, 2 * math.pi * (k + 1) / 8
        mid = (a0 + a1) / 2
        rim = [
            (x + 0.52 * math.cos(a), y + 0.52 * math.sin(a), z + 0.72) for a in (a0, a1)
        ]
        facing = 0.8 + 0.2 * math.cos(mid - math.radians(200))
        faces.append(
            (
                math.cos(mid) + math.sin(mid),
                rim,
                shade(color if k % 2 else "#fdf8ee", facing),
            )
        )
    for _, rim, fill in sorted(faces, key=lambda face: face[0]):
        out.append(solid(P3([rim[0], rim[1], apex]), fill))
    return out


def render_scene(traits=None, transparent=False, key="example"):
    """Draw the island. `traits` maps each activity signal to a number from 0 to 1.

    Pull requests bring larger sea animals, reviews bring visitors, issues build
    reefs, stars add glints on the water, and forks raise satellite islets. The
    vegetation follows `growth`, which defaults to the mean of the first three.
    `key` seeds every random choice, so each key gets its own island and the
    same key always gets the same one.
    """
    traits = {**DEFAULT, **(traits or {})}
    growth = traits.get(
        "growth", (traits["prs"] + traits["reviews"] + traits["issues"]) / 3
    )
    reviews = traits["reviews"]
    rnd = random.Random(f"{key}:scene")
    homes = HOMES[: steps(reviews, 0.6, 0.75, 0.9)]
    rings = RINGS[: steps(reviews, 0.15, 0.35, 0.55)]
    parasols = PARASOLS[: steps(reviews, 0.45, 0.6, 0.8)]
    canoe = reviews > 0.3
    islets = ISLETS[: round(traits["forks"] * len(ISLETS))]
    palms = 1 + round(growth * 5)
    bodies, shadows = wildlife(traits["prs"], key)
    jetty = [
        (JETTY_X + i * JETTY_SEGMENT, JETTY_X + (i + 1) * JETTY_SEGMENT)
        for i in range(2 if homes else 0)
    ]
    jetty_length = len(jetty) * JETTY_SEGMENT * LOCAL

    def clear_of(x, y, places, gap):
        return all(math.hypot(x - p[0], y - p[1]) > gap for p in places)

    o = []
    add = o.append
    # The transparent variant is cropped to the block, its palms and its shadow.
    view = "200 90 1000 790" if transparent else "0 0 1200 890"
    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img" aria-labelledby="t d">'
    )
    add('<title id="t">GitHub island</title>')
    add(
        '<desc id="d">An isometric cut block of a tropical island in translucent water. '
        "Sea animals, visitors, reefs and islets appear as GitHub activity grows.</desc>"
    )
    add(f"<style>{CSS}{DARK_CSS if transparent else ''}</style>")
    top_y, bottom_y = CY - H * S, CY + W * S - H * S
    # Shapes that repeat are defined once, at the world origin, and placed with `use`.
    shared = (
        crown_defs(0, key)
        + crown_defs(1, key)
        + '<g id="nuts" fill="#5b4027"><circle cx="-3" cy="3" r="3.2"/><circle cx="3" cy="4" r="3.2"/>'
        '<circle cy="6" r="3.2"/></g>'
        f'<path id="k" d="{SPARK}" fill="#ffffff"/>'
    )
    if homes:
        walk = (
            post(0.1, JETTY_Y + 0.05, H, DECK - 0.1)
            + post(0.1, JETTY_Y + 0.45, H, DECK - 0.1)
            + deck(0, JETTY_Y, JETTY_SEGMENT, JETTY_Y + 0.5, along_x=False)
        )
        shared += (
            '<g id="post">' + "".join(post(0, 0, 0, H)) + "</g>"
            '<g id="home">' + "".join(bungalow(0, 0)) + "</g>"
            '<g id="walk">' + "".join(walk) + "</g>"
        )
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
        + shared
        + "</defs>"
    )
    if not transparent:
        add('<rect width="1200" height="890" fill="url(#bg)"/>')

    # Shadow of the whole block on the table.
    base = [(0, 0), (W, 0), (W, W), (0, W)]
    cast = [P(x, y, -DEPTH) for x, y in base] + [
        P(x + 2.2, y - 1.2, -DEPTH) for x, y in base
    ]
    add(
        poly(
            hull(cast),
            class_="cast",
            fill="#5b5346",
            opacity="0.3",
            filter="url(#soft)",
        )
    )

    # Soil strata on the two visible cut faces.
    bounds = [
        (0, 0, 0, 0),
        (-0.75, 0.06, 1.3, 0.4),
        (-1.2, 0.08, 0.9, 2.0),
        (-1.95, 0.1, 0.7, 4.1),
        (-2.6, 0.08, 1.1, 1.0),
        (-DEPTH, 0, 0, 0),
    ]
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
    pebbles = {"#fff8ea": [], "#6d5038": []}
    for _ in range(90):
        u, z = rnd.uniform(0.1, 2 * W - 0.1), rnd.uniform(-3.1, -1.3)
        x, y = P(*edge(u), z)
        r = rnd.uniform(1.3, 3.2)
        fill = "#fff8ea" if rnd.random() < 0.75 else "#6d5038"
        pebbles[fill].append(
            f'<ellipse cx="{num(x)}" cy="{num(y)}" rx="{num(r)}" ry="{num(r * 0.7)}"/>'
        )
    for fill, marks in pebbles.items():
        add(f'<g fill="{fill}" opacity="0.85">' + "".join(marks) + "</g>")
    for matrix in (face_y(), face_x()):
        add(
            f'<g transform="{matrix}"><rect width="{W * LOCAL:.0f}" height="{DEPTH * LOCAL:.0f}" '
            'filter="url(#grain)" opacity="0.55"/></g>'
        )
    add(
        line(
            P(W, W, 0),
            P(W, W, -DEPTH),
            stroke="#ffffff",
            stroke_width="1.2",
            opacity="0.3",
        )
    )

    # Inner back walls of the water volume, then the seabed.
    add(poly(P3([(0, 0, 0), (W, 0, 0), (W, 0, H), (0, 0, H)]), fill="#bfeee4"))
    add(poly(P3([(0, 0, 0), (0, W, 0), (0, W, H), (0, 0, H)]), fill="#d2f4ea"))
    add(poly(P3([(0, 0, 0), (W, 0, 0), (W, W, 0), (0, W, 0)]), fill="#eedcb2"))

    canoe_path = ellipse_path(560, 1040, 260, 90)
    add(f'<g transform="{ground(0)}" clip-path="url(#seabed-clip)">')
    for _ in range(14):
        x, y = rnd.uniform(60, 1140), rnd.uniform(60, 1140)
        add(
            f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{rnd.uniform(60, 150):.0f}" '
            f'ry="{rnd.uniform(30, 70):.0f}" fill="#fbf0d2" opacity="0.5"/>'
        )
    add(
        f'<rect width="{W * LOCAL:.0f}" height="{W * LOCAL:.0f}" filter="url(#caustic)" opacity="0.5"/>'
    )
    add('<g filter="url(#soft-local)" fill="#16484a" opacity="0.3">')
    for xc, yc in homes:
        x0, y0 = (xc - 0.75 + SHADOW[0]) * LOCAL, (yc - 0.75 + SHADOW[1]) * LOCAL
        add(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="150" height="200"/>')
    if jetty:
        x0, y0 = (JETTY_X + SHADOW[0]) * LOCAL, (JETTY_Y + SHADOW[1]) * LOCAL
        add(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{jetty_length:.0f}" height="50"/>')
    add("</g>")
    palette = ["#ff8a7a", "#ffb347", "#b07cff", "#5fd3a8", "#ff6fb5", "#ffd95e"]
    reefs = [
        reef
        for reef in REEFS[: round(2 + traits["issues"] * 8)]
        if clear_of(*reef, homes, 1.7)
    ]
    for x, y in reefs:
        cx, cy = x * LOCAL, y * LOCAL
        add(
            f'<ellipse cx="{cx + 14:.0f}" cy="{cy - 8:.0f}" rx="52" ry="40" fill="#16484a" opacity="0.2"/>'
        )
        add(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="46" ry="36" fill="#d6caa8"/>')
        for _ in range(7):
            px, py, r = (
                cx + rnd.uniform(-34, 34),
                cy + rnd.uniform(-26, 26),
                rnd.uniform(8, 17),
            )
            color = rnd.choice(palette)
            add(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="{r:.0f}" fill="{color}"/>')
            add(
                f'<circle cx="{px - r * 0.3:.0f}" cy="{py - r * 0.3:.0f}" r="{r * 0.4:.0f}" fill="{shade(color, 1.18)}"/>'
            )
    for x, y, _ in rings:
        add(
            f'<circle cx="{(x + 0.75) * LOCAL:.0f}" cy="{(y - 0.4) * LOCAL:.0f}" r="22" fill="none" '
            'stroke="#16484a" stroke-width="13" opacity="0.2"/>'
        )
    # Shadows of the canoe and of the large animals, which swim above the seabed.
    add('<g fill="#16484a" opacity="0.2">')
    if canoe:
        hull_shadow = '<path d="M48 0C20 -14 -20 -14 -48 0C-20 14 20 14 48 0Z"/>'
        add(
            f'<g transform="translate(75 -40)">{swim(canoe_path, 30, 0, hull_shadow)}</g>'
        )
    if shadows:
        add('<g transform="translate(40 -22)">' + "".join(shadows) + "</g>")
    add("</g>")
    add("</g>")

    # Submerged part of the island, tinted by depth.
    for z in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.15):
        add(solid(P3(island_ring(z)), mix("#e2d3a4", "#f7ebcb", z / H)))
    for center in islets:
        for z in (0.0, 0.3, 0.6, 0.9, 1.15):
            ring = island_ring(z, n=24, center=center, radius=ISLET_R, top=ISLET_TOP)
            add(solid(P3(ring), mix("#e2d3a4", "#f7ebcb", z / H)))

    # Full-height posts, seen through the water below the surface.
    posts = []
    for xc, yc in homes:
        x0, x1, y0, y1 = xc - 0.65, xc + 0.65, yc - 0.65, yc + 1.15
        posts += [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
    for x0, _ in jetty:
        posts += [(x0 + 0.1, JETTY_Y + 0.05), (x0 + 0.1, JETTY_Y + 0.45)]
    posts.sort(key=lambda p: p[0] + p[1])
    for px, py in posts:
        add(f'<use href="#post" transform="{place(px, py)}"/>')

    # Sea animals swim in a plane below the surface.
    add(f'<g transform="{ground(0.5)}">' + "".join(bodies) + "</g>")

    # Water volume: translucent top, two cut faces, glass-edge highlights.
    top = P3([(0, 0, H), (W, 0, H), (W, W, H), (0, W, H)])
    add(poly(top, fill="url(#water-top)", fill_opacity="0.6"))
    add(
        poly(
            P3([(0, W, 0), (W, W, 0), (W, W, H), (0, W, H)]),
            fill="url(#water-side)",
            fill_opacity="0.62",
        )
    )
    add(
        poly(
            P3([(W, W, 0), (W, 0, 0), (W, 0, H), (W, W, H)]),
            fill="url(#water-side)",
            fill_opacity="0.72",
        )
    )
    add(
        poly(
            P3([(0, W, H - 0.13), (W, W, H - 0.13), (W, W, H), (0, W, H)]),
            fill="#ffffff",
            opacity="0.28",
        )
    )
    add(
        poly(
            P3([(W, W, H - 0.13), (W, 0, H - 0.13), (W, 0, H), (W, W, H)]),
            fill="#ffffff",
            opacity="0.2",
        )
    )
    add(
        f'<polyline points="{fmt(P3([(0, W, H), (0, 0, H), (W, 0, H)]))}" fill="none" stroke="#ffffff" stroke-width="1.2" opacity="0.45"/>'
    )
    add(
        f'<polyline points="{fmt(P3([(0, W, H), (W, W, H), (W, 0, H)]))}" fill="none" stroke="#ffffff" stroke-width="1.8" opacity="0.85"/>'
    )
    add(
        line(
            P(W, W, H), P(W, W, 0), stroke="#ffffff", stroke_width="1.4", opacity="0.5"
        )
    )

    # Everything that lies flat on the water surface.
    add(f'<g transform="{ground(H)}">')
    add(
        f'<rect width="{W * LOCAL:.0f}" height="{W * LOCAL:.0f}" filter="url(#waves)" '
        'opacity="0.32" style="mix-blend-mode:soft-light"/>'
    )
    shore = (
        "M"
        + "L".join(
            f"{x * LOCAL:.0f} {y * LOCAL:.0f}" for x, y, _ in island_ring(H, 1.04)
        )
        + "Z"
    )
    wide = (
        "M"
        + "L".join(
            f"{x * LOCAL:.0f} {y * LOCAL:.0f}" for x, y, _ in island_ring(H, 1.16)
        )
        + "Z"
    )
    add(f'<path d="{wide}" fill="#eafff8" opacity="0.3"/>')
    # Small waves roll in toward the beach, half a cycle apart.
    for delay in (0, 3.5):
        add(
            f'<path class="swash" d="{shore}" fill="none" stroke="#ffffff" stroke-width="5" '
            f'stroke-linejoin="round" style="animation-delay:-{delay}s"/>'
        )
    add(
        f'<path class="foam" d="{shore}" fill="none" stroke="#ffffff" stroke-width="9" stroke-linejoin="round"/>'
    )
    for center in islets:
        ring = island_ring(H, 1.08, n=24, center=center, radius=ISLET_R, top=ISLET_TOP)
        d = "M" + "L".join(f"{x * LOCAL:.0f} {y * LOCAL:.0f}" for x, y, _ in ring) + "Z"
        add(
            f'<path class="foam" d="{d}" fill="none" stroke="#ffffff" stroke-width="7" stroke-linejoin="round"/>'
        )
    add('<g filter="url(#soft-local)" fill="#0c5558" opacity="0.3">')
    for xc, yc in homes:
        add(
            f'<rect x="{(xc - 0.6) * LOCAL:.0f}" y="{(yc - 0.85) * LOCAL:.0f}" width="150" height="200"/>'
        )
    if jetty:
        x0, y0 = (JETTY_X + 0.15) * LOCAL, (JETTY_Y - 0.1) * LOCAL
        add(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{jetty_length:.0f}" height="50"/>')
    add("</g>")
    for x, y in RIPPLES:
        if not (clear_of(x, y, homes, 1.5) and clear_of(x, y, rings, 1.0)):
            continue
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
    if canoe:
        add(
            swim(
                canoe_path,
                30,
                0,
                '<path d="M-48 0C-70 -10 -86 -4 -96 0C-86 4 -70 10 -48 0Z" fill="#ffffff" opacity="0.45"/>'
                '<path d="M48 0C20 -14 -20 -14 -48 0C-20 14 20 14 48 0Z" fill="#e8704a"/>'
                '<path d="M40 0C18 -9 -18 -9 -40 0C-18 9 18 9 40 0Z" fill="#f4a57f"/>'
                '<path d="M6 -26L-6 26" stroke="#5b4027" stroke-width="3" stroke-linecap="round"/>'
                '<circle r="8" fill="#3b2f2a"/>',
            )
        )
    add("</g>")
    for index in range(round(4 + traits["stars"] * 20)):
        while True:
            x, y = rnd.uniform(0.4, W - 0.4), rnd.uniform(0.4, W - 0.4)
            if math.hypot(x - ISLAND[0], y - ISLAND[1]) > ISLAND_R * 0.93:
                break
        sx, sy = P(x, y, H)
        add(
            f'<g transform="translate({num(sx)} {num(sy)})">'
            f'<use href="#k" class="glint d{index * 5 % 8}"/></g>'
        )

    # Island above the waterline.
    for i in range(8):
        z = H + (ISLAND_TOP - H) * i / 7
        add(solid(P3(island_ring(z)), mix("#f6e9c8", "#fff7e2", i / 7)))
    add(poly(P3(island_ring(ISLAND_TOP, 0.8)), fill="#a9d481", opacity="0.85"))

    # Standing objects, painted far to near.
    items = []
    for i, (dx, dy, height, lean) in enumerate(PALMS[:palms]):
        x, y = ISLAND[0] + dx * SPREAD, ISLAND[1] + dy * SPREAD
        items.append((x + y, palm(x, y, height * (0.7 + 0.45 * growth), lean, 100 + i)))
    for i, center in enumerate(islets):
        parts = []
        for k in range(5):
            z = H + (ISLET_TOP - H) * k / 4
            ring = island_ring(z, n=24, center=center, radius=ISLET_R, top=ISLET_TOP)
            parts.append(solid(P3(ring), mix("#f6e9c8", "#fff7e2", k / 4)))
        parts += palm(
            center[0], center[1], 1.3, (0.3, -0.2), 300 + i, bz=ISLET_TOP, size=0.55
        )
        items.append((center[0] + center[1], parts))
    for i, (dx, dy) in enumerate(BUSHES[: round(1 + growth * 5)]):
        x, y = ISLAND[0] + dx * SPREAD, ISLAND[1] + dy * SPREAD
        items.append((x + y - 0.2, bush(x, y, key, i)))
    for dx, dy, color in parasols:
        x, y = ISLAND[0] + dx, ISLAND[1] + dy
        items.append((x + y + 0.3, parasol(x, y, color)))
    for xc, yc in homes:
        items.append(
            (xc + yc + 0.25, [f'<use href="#home" transform="{place(xc, yc)}"/>'])
        )
    for x0, x1 in jetty:
        items.append(
            (
                (x0 + x1) / 2 + JETTY_Y + 0.25,
                [f'<use href="#walk" transform="{place(x0, 0)}"/>'],
            )
        )
    # The third bungalow sits in front of the jetty and needs a short walkway to it.
    for xc, yc in homes[2:]:
        items.append(
            (xc + JETTY_Y + 0.9, deck(xc - 0.25, JETTY_Y + 0.5, xc + 0.25, yc - 0.75))
        )
    items.sort(key=lambda item: item[0])
    for _, parts in items:
        add("".join(parts))

    if not transparent:
        add(
            '<g fill="#2b2925" font-family="Georgia, serif">'
            '<text x="44" y="64" font-family="sans-serif" font-size="11" letter-spacing="2.4">SVG STUDY</text>'
            '<text x="42" y="134" font-size="66" font-style="italic">GitHub</text>'
            '<text x="42" y="198" font-size="66" font-style="italic">Island.</text>'
            '<text x="44" y="236" font-size="14" fill="#5a564d">One static file. No script, no canvas,</text>'
            '<text x="44" y="256" font-size="14" fill="#5a564d">no external assets.</text>'
            "</g>"
        )
    add("</svg>")
    return "\n".join(o) + "\n"
