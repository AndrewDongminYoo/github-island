"""Offline validation of the published island image: an allowlist with budgets.

The gate accepts only the elements, attributes, classes and stylesheet that the
renderer writes, rejects script and anything that reaches outside the file, and
checks that every reference resolves inside the file and within budgets. It does
not parse geometry: a path or a number is checked for its shape of characters,
not for its meaning. It never opens files, URLs or sockets.
"""

import re
import xml.etree.ElementTree as ET
from collections import defaultdict, deque

from .models import iso_day
from .render import CSS, DARK_CSS, RENDERER_VERSION, STAGE_GROWTH

NS = "{http://www.w3.org/2000/svg}"
MAX_BYTES = 200 * 1024
MAX_ELEMENTS = 2000
MAX_DEPTH = 12
MAX_MOTION = 64
MAX_EXPANSION = 20000
MAX_VALUE = 8192
VIEW_BOX = "200 90 1000 790"
IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_-]*"
REFERENCE = re.compile(r"url\(#(" + IDENTIFIER + r")\)")
# Geometry and paint values: digits, signs, separators, letters and "#" for
# colors, path commands, keywords and transform functions.
PLAIN = re.compile(r"[A-Za-z0-9#.,;() \-+%]*")
STYLE = re.compile(r"animation-delay:-[0-9]+(?:\.[0-9]+)?s|mix-blend-mode:soft-light")
CLASSES = frozenset(
    {"bob", "cast", "foam", "frond", "glint", "ripple", "s", "swash"}
    | {f"d{index}" for index in range(8)}
)
PAINT = {"fill", "opacity", "stroke", "stroke-width"}
# element: (allowed attributes, allowed children)
ELEMENTS = {
    "svg": (
        {
            "aria-labelledby",
            "data-activity-through",
            "data-renderer-version",
            "data-stage",
            "role",
            "viewBox",
        },
        {
            "circle",
            "defs",
            "desc",
            "g",
            "line",
            "polygon",
            "polyline",
            "style",
            "title",
            "use",
        },
    ),
    "title": ({"id"}, set()),
    "desc": ({"id"}, set()),
    "style": (set(), set()),
    "defs": (
        set(),
        {"clipPath", "filter", "g", "linearGradient", "path", "radialGradient"},
    ),
    "g": (
        {"class", "clip-path", "fill", "filter", "id", "opacity", "style", "transform"},
        {
            "animateMotion",
            "circle",
            "ellipse",
            "g",
            "line",
            "path",
            "polygon",
            "polyline",
            "rect",
            "use",
        },
    ),
    "use": ({"class", "href", "transform"}, set()),
    "path": (
        PAINT
        | {
            "class",
            "d",
            "id",
            "stroke-linecap",
            "stroke-linejoin",
            "style",
            "transform",
        },
        set(),
    ),
    "polygon": (
        PAINT | {"class", "color", "fill-opacity", "filter", "points"},
        set(),
    ),
    "polyline": (PAINT | {"points"}, set()),
    "line": (
        {"opacity", "stroke", "stroke-linecap", "stroke-width"}
        | {"x1", "x2", "y1", "y2"},
        set(),
    ),
    "circle": (
        PAINT | {"class", "cx", "cy", "r", "stroke-dasharray", "style"},
        set(),
    ),
    "ellipse": ({"cx", "cy", "fill", "opacity", "rx", "ry"}, set()),
    "rect": ({"filter", "height", "opacity", "style", "width", "x", "y"}, set()),
    "clipPath": ({"id"}, {"rect"}),
    "linearGradient": (
        {"gradientUnits", "id", "x1", "x2", "y1", "y2"},
        {"stop"},
    ),
    "radialGradient": ({"cx", "cy", "id", "r"}, {"stop"}),
    "stop": ({"offset", "stop-color"}, set()),
    "filter": (
        {"color-interpolation-filters", "height", "id", "width", "x", "y"},
        {
            "feColorMatrix",
            "feComposite",
            "feDiffuseLighting",
            "feGaussianBlur",
            "feSpecularLighting",
            "feTurbulence",
        },
    ),
    "feGaussianBlur": ({"stdDeviation"}, set()),
    "feTurbulence": (
        {"baseFrequency", "numOctaves", "result", "seed", "type"},
        {"animate"},
    ),
    "feColorMatrix": ({"values"}, set()),
    "feComposite": ({"in", "in2", "k1", "k2", "k3", "k4", "operator"}, set()),
    "feDiffuseLighting": (
        {"diffuseConstant", "in", "lighting-color", "result", "surfaceScale"},
        {"feDistantLight"},
    ),
    "feSpecularLighting": (
        {
            "in",
            "lighting-color",
            "result",
            "specularConstant",
            "specularExponent",
            "surfaceScale",
        },
        {"feDistantLight"},
    ),
    "feDistantLight": ({"azimuth", "elevation"}, set()),
    "animate": ({"attributeName", "dur", "repeatCount", "values"}, set()),
    "animateMotion": ({"begin", "dur", "path", "repeatCount", "rotate"}, set()),
}
# Where a local reference may point, by the attribute that holds it.
TARGETS = {
    "href": {"g", "path"},
    "fill": {"linearGradient", "radialGradient"},
    "filter": {"filter"},
    "clip-path": {"clipPath"},
}
TEXT = {"title", "desc", "style"}


class _BoundedTree(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.count = 0
        self.depth = 0

    def start(self, tag, attrs):
        self.count += 1
        self.depth += 1
        if self.count > MAX_ELEMENTS:
            raise ValueError("SVG element budget exceeded")
        if self.depth > MAX_DEPTH:
            raise ValueError("SVG depth budget exceeded")
        return super().start(tag, attrs)

    def end(self, tag):
        self.depth -= 1
        return super().end(tag)

    def doctype(self, name, pubid, system):
        raise ValueError("SVG DTD and entity declarations are prohibited")

    def pi(self, target, text):
        raise ValueError("SVG processing instructions are prohibited")


def _attributes(node, tag, references):
    allowed = ELEMENTS[tag][0]
    for name, value in node.attrib.items():
        if name not in allowed:
            raise ValueError("Unsupported SVG attribute")
        if len(value) > MAX_VALUE:
            raise ValueError("SVG attribute value budget exceeded")
        if name == "id":
            if not re.fullmatch(IDENTIFIER, value):
                raise ValueError("Invalid SVG ID")
        elif name == "href":
            if not re.fullmatch("#" + IDENTIFIER, value):
                raise ValueError("Nonlocal SVG reference")
            references[node].append((value[1:], TARGETS[name]))
        elif name == "class":
            tokens = value.split()
            if not tokens or set(tokens) - CLASSES or len(set(tokens)) != len(tokens):
                raise ValueError("Unsupported SVG class")
        elif name == "style":
            if not STYLE.fullmatch(value):
                raise ValueError("Unsupported SVG inline style")
        elif name == "attributeName":
            if value != "baseFrequency":
                raise ValueError("Unsupported SVG animation target")
        elif "url(" in value:
            match = REFERENCE.fullmatch(value)
            if not match or name not in TARGETS:
                raise ValueError("Nonlocal or misplaced SVG reference")
            references[node].append((match[1], TARGETS[name]))
        elif not PLAIN.fullmatch(value):
            raise ValueError("Unsupported SVG attribute value")


def _metadata(root, ids):
    expected = {
        "role": "img",
        "aria-labelledby": "t d",
        "viewBox": VIEW_BOX,
        "data-renderer-version": str(RENDERER_VERSION),
    }
    if any(root.get(name) != value for name, value in expected.items()):
        raise ValueError("Invalid SVG root metadata or viewBox")
    if root.get("data-stage") not in STAGE_GROWTH:
        raise ValueError("Invalid SVG stage metadata")
    try:
        iso_day(root.get("data-activity-through"))
    except ValueError:
        raise ValueError("Invalid SVG activity date metadata") from None
    for tag, identifier in (("title", "t"), ("desc", "d")):
        nodes = root.findall(NS + tag)
        if (
            len(nodes) != 1
            or ids.get(identifier) is not nodes[0]
            or not (nodes[0].text or "").strip()
        ):
            raise ValueError("Missing accessible SVG title or description")


def _references(nodes, ids, definitions, references):
    # Edges are child containment and typed local references. Bottom-up
    # evaluation finds cycles and bounds repeated expansion without recursion.
    dependencies = {node: list(node) for node in nodes}
    for node, targets in references.items():
        for name, tags in targets:
            target = ids.get(name)
            if (
                target is None
                or target not in definitions
                or target.tag.removeprefix(NS) not in tags
            ):
                raise ValueError("Unresolved or wrong-type SVG reference")
            dependencies[node].append(target)
    parents = defaultdict(list)
    pending = {}
    costs = dict.fromkeys(nodes, 1)
    for node, children in dependencies.items():
        pending[node] = len(children)
        for child in children:
            parents[child].append(node)
    ready = deque(node for node in nodes if not pending[node])
    visited = 0
    while ready:
        node = ready.popleft()
        visited += 1
        for parent in parents[node]:
            costs[parent] += costs[node]
            if costs[parent] > MAX_EXPANSION:
                raise ValueError("SVG reference expansion budget exceeded")
            pending[parent] -= 1
            if not pending[parent]:
                ready.append(parent)
    if visited != len(nodes):
        raise ValueError("SVG reference cycle")


def validate_svg(raw):
    """Accept the bytes of a published island image unchanged, or raise ValueError.

    This is a gate for this renderer's own output, not a general SVG sanitizer.
    """
    if not isinstance(raw, bytes):
        raise ValueError("SVG input must be UTF-8 bytes")
    if len(raw) > MAX_BYTES:
        raise ValueError("SVG byte budget exceeded")
    try:
        text = raw.decode("utf-8")
        # Do not let a byte parser autodetect UTF-16/32 or honor a conflicting
        # declaration after the UTF-8 check.
        if "\x00" in text:
            raise ValueError("Invalid UTF-8 SVG XML")
        declaration = re.match(r"\A﻿?<\?xml\s+[^?]*\?>", text)
        if declaration:
            encoding = re.search(r"\bencoding\s*=\s*(['\"])([^'\"]+)\1", declaration[0])
            if encoding and encoding[2].lower() not in {"utf-8", "utf8"}:
                raise ValueError("SVG XML declaration must use UTF-8")
        root = ET.fromstring(raw, parser=ET.XMLParser(target=_BoundedTree()))
    except (UnicodeError, ET.ParseError):
        raise ValueError("Invalid UTF-8 SVG XML") from None
    if root.tag != NS + "svg":
        raise ValueError("Invalid SVG root or namespace")
    nodes = list(root.iter())
    # Name every element before judging placement, so an unknown element is
    # reported as unknown and not as a misplaced child of its parent.
    for node in nodes:
        tag = node.tag.removeprefix(NS)
        if node.tag != NS + tag or tag not in ELEMENTS:
            raise ValueError("Unsupported SVG element or namespace")
    if len(root.findall(NS + "defs")) != 1 or len(root.findall(NS + "style")) != 1:
        raise ValueError("SVG requires one definitions block and one stylesheet")
    definitions = set(root.find(NS + "defs").iter())
    ids = {}
    references = defaultdict(list)
    motion = 0
    for node in nodes:
        tag = node.tag.removeprefix(NS)
        # The child table also keeps svg, defs, title, desc and style at the root:
        # no other element lists them as children.
        if any(child.tag.removeprefix(NS) not in ELEMENTS[tag][1] for child in node):
            raise ValueError("Unsupported SVG child placement")
        if ((node.text or "").strip() and tag not in TEXT) or (node.tail or "").strip():
            raise ValueError("Unexpected SVG character content")
        _attributes(node, tag, references)
        identifier = node.get("id")
        if identifier:
            if identifier in ids:
                raise ValueError("Duplicate SVG ID")
            ids[identifier] = node
        if tag == "style" and node.text != CSS + DARK_CSS:
            raise ValueError("Unsupported SVG stylesheet")
        if tag in {"animate", "animateMotion"}:
            motion += 1
            if node.get("repeatCount") != "indefinite":
                raise ValueError("Unsupported SVG animation repeat")
    if motion > MAX_MOTION:
        raise ValueError("SVG animation budget exceeded")
    _metadata(root, ids)
    _references(nodes, ids, definitions, references)
