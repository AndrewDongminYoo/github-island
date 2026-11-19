import re
import unittest
import xml.etree.ElementTree as ET

from github_island.render import DEFAULT, render_scene

NS = "{http://www.w3.org/2000/svg}"
# The byte budget that github-terrarium enforces on its published image.
BUDGET = 200 * 1024


def scene(prs=0.5, reviews=0.5, issues=0.5, stars=0.5, forks=0.34, **options):
    traits = dict(zip(DEFAULT, (prs, reviews, issues, stars, forks)))
    return render_scene(traits, **options)


def uses(svg, fragment):
    return len(re.findall(f'<use href="#{fragment}"', svg))


class RenderTests(unittest.TestCase):
    def test_same_input_gives_the_same_bytes(self):
        self.assertEqual(scene(), scene())

    def test_key_changes_the_island_but_not_its_contents(self):
        first, second = scene(key="one"), scene(key="two")
        self.assertNotEqual(first, second)
        for fragment in ("home", "walk", "k"):
            self.assertEqual(uses(first, fragment), uses(second, fragment))

    def test_output_is_well_formed_svg(self):
        root = ET.fromstring(scene(1, 1, 1, 1, 1).encode())
        self.assertEqual(root.tag, NS + "svg")
        self.assertEqual(root.get("role"), "img")
        self.assertTrue(root.find(NS + "title").text)
        self.assertTrue(root.find(NS + "desc").text)

    def test_every_local_reference_resolves(self):
        svg = scene(1, 1, 1, 1, 1)
        ids = set(re.findall(r'\bid="([^"]+)"', svg))
        targets = set(re.findall(r'href="#([^"]+)"', svg))
        targets |= set(re.findall(r"url\(#([^)]+)\)", svg))
        self.assertTrue(targets)
        self.assertEqual(targets - ids, set())

    def test_nothing_reaches_outside_the_file(self):
        svg = scene(1, 1, 1, 1, 1)
        self.assertNotIn("<script", svg)
        self.assertNotIn("<foreignObject", svg)
        self.assertNotIn("<image", svg)
        for link in re.findall(r'href="([^"]*)"', svg):
            self.assertTrue(link.startswith("#"), link)
        self.assertEqual(re.findall(r"url\((?!#)", svg), [])

    def test_largest_scene_fits_the_byte_budget(self):
        self.assertLess(len(scene(1, 1, 1, 1, 1).encode()), BUDGET)

    def test_reviews_bring_visitors_in_order(self):
        quiet = scene(reviews=0.1)
        self.assertEqual(uses(quiet, "home"), 0)
        self.assertNotIn('class="bob', quiet)
        rings = scene(reviews=0.2)
        self.assertEqual(rings.count('class="bob'), 1)
        self.assertEqual(uses(rings, "home"), 0)
        self.assertEqual(uses(scene(reviews=0.65), "home"), 1)
        self.assertEqual(uses(scene(reviews=0.8), "home"), 2)
        busy = scene(reviews=1)
        self.assertEqual(uses(busy, "home"), 3)
        self.assertEqual(uses(busy, "walk"), 2)
        self.assertEqual(busy.count('class="bob'), 3)

    def test_pull_requests_bring_larger_animals(self):
        def swimmers(svg):
            return svg.count("<animateMotion")

        counts = [swimmers(scene(prs=value, reviews=0)) for value in (0, 0.3, 0.65, 1)]
        self.assertEqual(counts, sorted(counts))
        self.assertLess(counts[0], counts[-1])
        # The whale shark is the only animal drawn with white spots.
        self.assertNotIn('fill="#ffffff" opacity="0.65"', scene(prs=0.8, reviews=0))
        self.assertIn('fill="#ffffff" opacity="0.65"', scene(prs=0.9, reviews=0))

    def test_forks_raise_islets_and_stars_add_glints(self):
        self.assertLess(
            scene(forks=0).count('class="foam"'), scene(forks=1).count('class="foam"')
        )
        self.assertLess(uses(scene(stars=0), "k"), uses(scene(stars=1), "k"))

    def test_transparent_variant_has_no_backdrop_and_no_text(self):
        clear = scene(transparent=True)
        self.assertNotIn("<text", clear)
        self.assertNotIn('fill="url(#bg)"', clear)
        self.assertIn("prefers-color-scheme: dark", clear)
        poster = scene(transparent=False)
        self.assertIn("<text", poster)
        self.assertIn('fill="url(#bg)"', poster)


if __name__ == "__main__":
    unittest.main()
