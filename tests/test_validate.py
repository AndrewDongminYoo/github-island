import unittest
from pathlib import Path

from github_island import validate
from github_island.growth import advance
from github_island.render import render
from github_island.state import read_json
from github_island.validate import validate_svg

FIXTURES = Path(__file__).parent / "fixtures"
# The reviews fixture draws bungalows, a jetty, glints and every kind of reference.
VALID = render(advance(read_json(FIXTURES / "reviews.json"))).decode()


def swap(old, new, count=1):
    """Return VALID with `old` replaced; fail loudly if the fixture lacks `old`."""
    if old not in VALID:
        raise AssertionError(f"Fixture does not contain {old!r}")
    return VALID.replace(old, new, count).encode()


def before_end(fragment):
    return swap("</svg>", fragment + "</svg>")


def in_defs(fragment):
    return swap("</defs>", fragment + "</defs>")


class AcceptTests(unittest.TestCase):
    def test_every_fixture_state_passes(self):
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=path.stem):
                self.assertIsNone(validate_svg(render(advance(read_json(path)))))

    def test_validation_does_not_change_the_bytes(self):
        raw = VALID.encode()
        validate_svg(raw)
        self.assertEqual(raw, VALID.encode())


class RejectTests(unittest.TestCase):
    def assertRejects(self, raw, message):
        with self.assertRaisesRegex(ValueError, message):
            validate_svg(raw)

    def test_input_must_be_bounded_utf8_bytes(self):
        self.assertRejects(VALID, "must be UTF-8 bytes")
        padded = VALID.encode() + b" " * validate.MAX_BYTES
        self.assertRejects(padded, "byte budget")
        self.assertRejects(VALID.encode("utf-16"), "Invalid UTF-8")
        declared = b'<?xml version="1.0" encoding="latin-1"?>' + VALID.encode()
        self.assertRejects(declared, "must use UTF-8")

    def test_dtd_and_processing_instructions_are_refused(self):
        doctype = b'<!DOCTYPE svg [<!ENTITY a "b">]>' + VALID.encode()
        self.assertRejects(doctype, "DTD and entity")
        self.assertRejects(
            before_end('<?xml-stylesheet href="a.css"?>'), "processing instructions"
        )

    def test_elements_outside_the_allowlist_are_refused(self):
        for fragment in (
            "<script>alert(1)</script>",
            "<foreignObject/>",
            '<image href="#k"/>',
            "<text>hello</text>",
            "<a/>",
            '<g xmlns="http://www.w3.org/1999/xhtml"/>',
        ):
            with self.subTest(fragment=fragment):
                self.assertRejects(before_end(fragment), "element or namespace")

    def test_an_allowed_element_in_the_wrong_place_is_refused(self):
        self.assertRejects(before_end("<stop/>"), "child placement")
        self.assertRejects(before_end("<g><defs/></g>"), "child placement")
        self.assertRejects(before_end("<defs/>"), "one definitions block")

    def test_attributes_outside_the_allowlist_are_refused(self):
        self.assertRejects(
            swap('role="img"', 'role="img" onload="x()"'), "Unsupported SVG attribute"
        )
        self.assertRejects(
            before_end('<g onclick="x()"/>'), "Unsupported SVG attribute"
        )
        linked = swap(
            'role="img"', 'role="img" xmlns:xlink="http://www.w3.org/1999/xlink"'
        ).decode()
        linked = linked.replace("</svg>", '<use xlink:href="#k"/></svg>').encode()
        self.assertRejects(linked, "Unsupported SVG attribute")

    def test_references_must_stay_inside_the_file(self):
        self.assertRejects(
            swap('href="#k"', 'href="https://example.com/a.svg#k"'), "Nonlocal"
        )
        self.assertRejects(
            swap('fill="url(#water-top)"', 'fill="url(https://example.com/a)"'),
            "Nonlocal or misplaced",
        )
        self.assertRejects(
            before_end('<g opacity="url(#soft)"/>'), "Nonlocal or misplaced"
        )

    def test_references_must_resolve_to_the_right_kind_of_definition(self):
        self.assertRejects(swap('href="#k"', 'href="#missing"'), "Unresolved")
        # The title exists but is not a definition.
        self.assertRejects(swap('href="#k"', 'href="#t"'), "Unresolved or wrong-type")
        # A filter is a definition but not something `use` may place.
        self.assertRejects(swap('href="#k"', 'href="#soft"'), "wrong-type")
        self.assertRejects(
            swap('fill="url(#water-top)"', 'fill="url(#soft)"'), "wrong-type"
        )

    def test_reference_cycles_and_expansion_are_bounded(self):
        self.assertRejects(
            in_defs('<g id="loop"><use href="#loop"/></g>'), "reference cycle"
        )
        chain = "".join(
            f'<g id="x{i}"><use href="#x{i + 1}"/><use href="#x{i + 1}"/></g>'
            for i in range(16)
        )
        self.assertRejects(in_defs(chain + '<g id="x16"/>'), "expansion budget")

    def test_ids_must_be_unique_and_well_formed(self):
        self.assertRejects(in_defs('<g id="nuts"/>'), "Duplicate SVG ID")
        self.assertRejects(in_defs('<g id="1 bad"/>'), "Invalid SVG ID")

    def test_style_and_class_are_closed(self):
        self.assertRejects(
            swap('style="mix-blend-mode:soft-light"', 'style="background:url(x)"'),
            "inline style",
        )
        self.assertRejects(
            before_end('<g style="animation-delay:-1s;color:red"/>'), "inline style"
        )
        self.assertRejects(
            before_end('<g class="s unknown"/>'), "Unsupported SVG class"
        )
        self.assertRejects(swap(".frond {", ".frond, .x {"), "stylesheet")

    def test_attribute_values_use_a_plain_alphabet(self):
        self.assertRejects(before_end('<g opacity="javascript:1"/>'), "attribute value")
        self.assertRejects(before_end('<g transform="a&amp;b"/>'), "attribute value")
        long_value = "1 " * validate.MAX_VALUE
        self.assertRejects(
            before_end(f'<polyline points="{long_value}"/>'), "value budget"
        )

    def test_character_content_is_refused_outside_text_elements(self):
        self.assertRejects(before_end("<g>hello</g>"), "character content")
        self.assertRejects(before_end("<g/>stray"), "character content")

    def test_budgets_bound_elements_depth_and_motion(self):
        self.assertRejects(before_end("<g/>" * validate.MAX_ELEMENTS), "element budget")
        nested = "<g>" * validate.MAX_DEPTH + "</g>" * validate.MAX_DEPTH
        self.assertRejects(before_end(nested), "depth budget")
        motion = '<animateMotion dur="1s" repeatCount="indefinite" path="M0 0"/>'
        self.assertRejects(
            before_end("<g>" + motion * (validate.MAX_MOTION + 1) + "</g>"),
            "animation budget",
        )

    def test_animation_is_limited_to_what_the_renderer_uses(self):
        self.assertRejects(
            swap('attributeName="baseFrequency"', 'attributeName="href"'),
            "animation target",
        )
        self.assertRejects(
            before_end('<g><animateMotion dur="1s" repeatCount="3" path="M0 0"/></g>'),
            "animation repeat",
        )

    def test_root_metadata_is_required(self):
        for old, new in (
            ('viewBox="200 90 1000 790"', 'viewBox="0 0 10 10"'),
            ('role="img"', 'role="presentation"'),
            ('aria-labelledby="t d"', 'aria-labelledby="t"'),
            (
                f'data-renderer-version="{validate.RENDERER_VERSION}"',
                'data-renderer-version="99"',
            ),
        ):
            with self.subTest(change=new):
                self.assertRejects(swap(old, new), "root metadata or viewBox")
        self.assertRejects(swap('data-stage="', 'data-stage="x'), "stage metadata")
        self.assertRejects(
            swap('data-activity-through="', 'data-activity-through="x'), "date"
        )

    def test_title_and_description_are_required(self):
        title = VALID[VALID.index("<title") : VALID.index("</title>") + 8]
        self.assertRejects(swap(title, '<title id="t"> </title>'), "title")
        self.assertRejects(swap(title, ""), "title")
        self.assertRejects(swap('<desc id="d">', '<desc id="e">'), "description")


if __name__ == "__main__":
    unittest.main()
