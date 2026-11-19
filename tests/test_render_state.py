import copy
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from github_island.growth import advance, stage
from github_island.render import RENDERER_VERSION, render
from github_island.state import read_json

FIXTURES = Path(__file__).parent / "fixtures"
NS = "{http://www.w3.org/2000/svg}"
BUDGET = 200 * 1024


def states():
    for path in sorted(FIXTURES.glob("*.json")):
        yield path.stem, advance(read_json(path))


class RenderStateTests(unittest.TestCase):
    def test_every_fixture_renders_within_budget(self):
        names = []
        for name, state in states():
            names.append(name)
            with self.subTest(fixture=name):
                svg = render(state)
                self.assertIsInstance(svg, bytes)
                self.assertLess(len(svg), BUDGET)
                self.assertEqual(ET.fromstring(svg).tag, NS + "svg")
        self.assertIn("reviews", names)

    def test_rendering_is_deterministic(self):
        for name, state in states():
            with self.subTest(fixture=name):
                self.assertEqual(render(state), render(copy.deepcopy(state)))

    def test_metadata_names_the_subject_stage_and_day(self):
        _, state = next(states())
        root = ET.fromstring(render(state))
        xp = sum(
            day["activity_xp_awarded"] + day["popularity_xp_awarded"]
            for day in state["days"].values()
        )
        self.assertEqual(root.get("data-stage"), stage(xp))
        self.assertEqual(
            root.get("data-activity-through"), state["last_complete_activity_day"]
        )
        self.assertEqual(root.get("data-renderer-version"), str(RENDERER_VERSION))
        self.assertIn(state["subject"]["login"], root.find(NS + "title").text)
        description = root.find(NS + "desc").text
        self.assertIn(state["subject"]["id"], description)
        self.assertIn(state["last_complete_activity_day"], description)

    def test_published_image_has_no_text_and_no_backdrop(self):
        _, state = next(states())
        svg = render(state).decode()
        self.assertNotIn("<text", svg)
        self.assertNotIn('fill="url(#bg)"', svg)

    def test_each_subject_gets_its_own_island(self):
        _, state = next(states())
        other = copy.deepcopy(state)
        other["subject"]["id"] = state["subject"]["id"] + "x"
        self.assertNotEqual(render(state), render(other))

    def test_login_change_keeps_the_shape(self):
        _, state = next(states())
        renamed = copy.deepcopy(state)
        renamed["subject"]["login"] = "renamed-user"
        before = render(state).decode().split("</desc>", 1)[1]
        after = render(renamed).decode().split("</desc>", 1)[1]
        self.assertEqual(before, after)

    def test_invalid_state_is_rejected(self):
        _, state = next(states())
        broken = copy.deepcopy(state)
        del broken["current_traits"]
        with self.assertRaises(ValueError):
            render(broken)


if __name__ == "__main__":
    unittest.main()
